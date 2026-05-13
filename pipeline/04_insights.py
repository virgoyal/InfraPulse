"""
Step 4: Generate AI-powered regional infrastructure insights via Gemini Flash.

Groups tenders by state. For each state with ≥3 tenders, calls Gemini to
produce a 2–3 sentence human-readable insight about infrastructure priorities.

Outputs: pipeline/data/insights.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from google import genai
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, GEMINI_API_KEY, GEMINI_MODEL, GEMINI_RPM_LIMIT
from utils.rate_limiter import GeminiRateLimiter

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
                "tender_count": len(tenders),
                "total_value_crore": round(sum(parse_value_crore(t.get("value", "")) for t in tenders), 2),
                "top_categories": _top_categories(tenders),
            }
        except Exception as exc:
            print(f"\n  Gemini error for {state} ({type(exc).__name__}): {exc}")
            if attempt == 2:
                break
            import time
            time.sleep(2 ** attempt)

    return {
        "text": f"{state} has {len(tenders)} active infrastructure tenders from MoRTH.",
        "tender_count": len(tenders),
        "total_value_crore": 0.0,
        "top_categories": _top_categories(tenders),
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

    client = genai.Client(api_key=GEMINI_API_KEY)
    limiter = GeminiRateLimiter(rpm=GEMINI_RPM_LIMIT)

    with open(INPUT) as f:
        tenders = json.load(f)

    by_state: dict[str, list[dict]] = defaultdict(list)
    for t in tenders:
        state = t.get("state", "Unknown")
        if state != "Unknown":
            by_state[state].append(t)

    eligible = {s: ts for s, ts in by_state.items() if len(ts) >= MIN_TENDERS_FOR_INSIGHT}
    print(f"Generating insights for {len(eligible)} states (≥{MIN_TENDERS_FOR_INSIGHT} tenders each).")

    # Load existing to allow reruns
    if OUTPUT.exists():
        with open(OUTPUT) as f:
            insights: dict[str, dict] = json.load(f)
    else:
        insights = {}

    for state, state_tenders in tqdm(eligible.items(), desc="Insights"):
        if state in insights:
            continue  # already generated
        insights[state] = generate_insight(state, state_tenders, client, limiter)

    with open(OUTPUT, "w") as f:
        json.dump(insights, f, indent=2, ensure_ascii=False)

    print(f"\nInsights generated for {len(insights)} states → {OUTPUT}")


if __name__ == "__main__":
    main()
