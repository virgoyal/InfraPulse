"""
Step 4: Generate AI-powered regional infrastructure insights via Gemini Flash.

Groups tenders by state. For each state with ≥3 active tenders, calls Gemini to
produce a 2–3 sentence human-readable insight about infrastructure priorities.

Outputs: pipeline/data/insights.json

Refresh policy: an insight describes a specific set of tenders, so it only goes
stale when that set changes. Each state's insight records a fingerprint of the
tender IDs behind it, and Gemini is called again only when the fingerprint moves
— typically a handful of states a day. The numeric fields are recomputed locally
on every run, so counts and values stay current even when no model call is made.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    DATA_DIR,
    GEMINI_API_KEY,
    GEMINI_INSIGHTS_BUDGET,
    GEMINI_MODEL,
    GEMINI_RPM_LIMIT,
    INSIGHTS_REFRESH_PER_RUN,
)
from utils import gemini
from utils.rate_limiter import GeminiRateLimiter, QuotaExhausted

INPUT = DATA_DIR / "geolocated_tenders.json"
OUTPUT = DATA_DIR / "insights.json"

MIN_TENDERS_FOR_INSIGHT = 3
MAX_SUMMARIES_PER_STATE = 25

INSIGHTS_PROMPT = """\
You are an infrastructure analyst reviewing Indian government procurement data.

Below are {count} active infrastructure tenders from {state}:
{summaries}

In exactly 2–3 sentences, provide an insight covering:
1. The dominant infrastructure focus (what is being built/maintained most)
2. Any notable pattern (e.g., heavy investment in a specific type of work)
3. A data-backed observation about regional priorities

Be factual, concise, and avoid bullet points. Write in plain prose.
""".strip()


def parse_value_crore(value_str: str) -> float:
    """Convert raw value string to crore figure best-effort."""
    if not value_str:
        return 0.0
    digits = re.sub(r"[^\d.]", "", value_str.replace(",", ""))
    try:
        amount = float(digits)
    except ValueError:
        return 0.0
    # Heuristic: if the number looks like it's in lakhs (< 1000), convert
    if amount < 1000:
        return amount / 100  # lakhs → crores (rough)
    return amount / 1e5  # raw rupees → crores (rough)


def fingerprint(tenders: list[dict]) -> str:
    """Stable digest of which tenders an insight was written from.

    Changes when a tender is added, or drops off the listing and is archived —
    exactly the cases where the prose needs rewriting.
    """
    ids = sorted(str(t.get("tender_id", "")) for t in tenders)
    return hashlib.sha1("|".join(ids).encode()).hexdigest()[:16]


def compute_stats(tenders: list[dict]) -> dict:
    """The numeric half of an insight — derived locally, no API call."""
    return {
        "tender_count": len(tenders),
        "total_value_crore": round(
            sum(parse_value_crore(t.get("value", "")) for t in tenders), 2
        ),
        "top_categories": _top_categories(tenders),
    }


def generate_insight(state: str, tenders: list[dict], client, limiter: GeminiRateLimiter) -> dict:
    summaries = "\n".join(
        f"- {t.get('summary', t.get('title', ''))}"
        for t in tenders[:MAX_SUMMARIES_PER_STATE]
    )
    prompt = INSIGHTS_PROMPT.format(count=len(tenders), state=state, summaries=summaries)

    for attempt in range(3):
        try:
            limiter.wait()
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            text = response.text.strip()
            return {
                "text": text,
                **compute_stats(tenders),
                "source_hash": fingerprint(tenders),
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        except QuotaExhausted:
            raise
        except Exception as exc:
            fatal = gemini.classify(exc)
            if fatal is not None:
                raise fatal from exc

            print(f"\n  Gemini error for {state} ({type(exc).__name__}): {exc}", flush=True)
            if attempt == 2:
                break
            import time
            # A per-minute 429 needs a real backoff, not 1-2 seconds.
            time.sleep(gemini.retry_delay_seconds(str(exc)) if gemini.is_rate_limit(str(exc))
                       else 2 ** attempt)

    # Placeholder prose, but no source_hash — so a later run retries this state
    # instead of treating the fallback text as up to date.
    return {
        "text": f"{state} has {len(tenders)} active infrastructure tenders from MoRTH.",
        **compute_stats(tenders),
    }


def _top_categories(tenders: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for t in tenders:
        cat = t.get("category", "Unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda x: -x[1])[:3]]


def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    client = gemini.make_client(GEMINI_API_KEY)
    limiter = GeminiRateLimiter(rpm=GEMINI_RPM_LIMIT, budget=GEMINI_INSIGHTS_BUDGET)

    with open(INPUT) as f:
        tenders = json.load(f)

    by_state: dict[str, list[dict]] = defaultdict(list)
    for t in tenders:
        state = t.get("state", "Unknown")
        # The prose talks about "active" tenders, so archived ones must not
        # feed the counts or the summaries.
        if state != "Unknown" and t.get("status") != "archived":
            by_state[state].append(t)

    eligible = {s: ts for s, ts in by_state.items() if len(ts) >= MIN_TENDERS_FOR_INSIGHT}

    # Load existing to allow reruns
    if OUTPUT.exists():
        with open(OUTPUT) as f:
            insights: dict[str, dict] = json.load(f)
    else:
        insights = {}

    # Drop states that no longer qualify, so nothing lingers indefinitely.
    for state in [s for s in insights if s not in eligible]:
        print(f"  Dropping {state} — below {MIN_TENDERS_FOR_INSIGHT} active tenders.")
        del insights[state]

    # Refresh the free, locally-derived numbers for every state on every run.
    # Only the prose costs a Gemini call.
    stale: list[str] = []
    for state, state_tenders in eligible.items():
        current = fingerprint(state_tenders)
        existing = insights.get(state)
        if existing is None or existing.get("source_hash") != current:
            stale.append(state)
        else:
            existing.update(compute_stats(state_tenders))

    # Biggest states first — their insights are the most visible.
    stale.sort(key=lambda s: -len(eligible[s]))
    todo = stale[:INSIGHTS_REFRESH_PER_RUN]

    print(f"Eligible states: {len(eligible)}  |  Tender set changed: {len(stale)}  "
          f"|  Refreshing now: {len(todo)} (cap {INSIGHTS_REFRESH_PER_RUN})", flush=True)

    for state in tqdm(todo, desc="Insights"):
        try:
            insights[state] = generate_insight(state, eligible[state], client, limiter)
        except QuotaExhausted as exc:
            # Keep whatever we already have; the rest is picked up next run,
            # because their fingerprints still won't match.
            print(f"\nStopping Gemini calls: {exc}", flush=True)
            break

    with open(OUTPUT, "w") as f:
        json.dump(insights, f, indent=2, ensure_ascii=False)

    remaining = len(stale) - sum(1 for s in todo if insights.get(s, {}).get("source_hash"))
    print(f"\nGemini calls used: {limiter.calls_made}", flush=True)
    if remaining > 0:
        print(f"Still awaiting refresh (next run): {remaining}", flush=True)
    print(f"Insights cover {len(insights)} states → {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
