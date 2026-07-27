"""
Step 2: AI enrichment via Gemini Flash.

For each tender, extracts:
  - category  (one of 7 fixed values)
  - summary   (one sentence, ≤20 words)
  - state     (Indian state inferred from title/org)

Outputs: pipeline/data/enriched_tenders.json

Idempotent: tenders that already have a 'category' field are skipped.

Quota-aware: the run stops calling Gemini as soon as the daily free-tier quota
is gone and leaves the remaining tenders untouched, so the next day's run picks
up exactly where this one stopped.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    CATEGORIES,
    DATA_DIR,
    GEMINI_API_KEY,
    GEMINI_BATCH_SIZE,
    GEMINI_ENRICH_BUDGET,
    GEMINI_ENRICH_MODEL,
    GEMINI_RPM_LIMIT,
)
from utils import gemini
from utils.rate_limiter import GeminiRateLimiter, QuotaExhausted

# At most this many rate-limit backoffs per tender before giving up on it.
MAX_RATE_LIMIT_WAITS = 2

INPUT = DATA_DIR / "raw_tenders.json"
OUTPUT = DATA_DIR / "enriched_tenders.json"

ENRICH_PROMPT = """\
You are analysing Indian government road/infrastructure procurement tenders.

For EACH numbered tender below, produce one JSON object with exactly these fields:

"index": the tender's number, copied exactly
"category": one of [{categories}]
"summary": one sentence (max 20 words) describing what this project does
"state": the Indian state or UT where this project is located (use "Unknown" if genuinely unclear)

Respond with a JSON array of exactly {count} objects, in the same order.
No markdown, no commentary.

{tenders}
""".strip()

TENDER_BLOCK = """\
--- TENDER {index} ---
Title: {title}
Work description: {work_description}
Product category (from site): {product_category}
Organisation chain: {org_chain}
Location: {location_city}"""


def build_prompt(batch: list[dict]) -> str:
    blocks = [
        TENDER_BLOCK.format(
            index=i,
            title=t.get("title", ""),
            work_description=t.get("work_description", t.get("title", "")),
            product_category=t.get("product_category", ""),
            org_chain=t.get("org_chain", t.get("organization", "")),
            location_city=t.get("location_city", ""),
        )
        for i, t in enumerate(batch)
    ]
    return ENRICH_PROMPT.format(
        categories=", ".join(CATEGORIES),
        count=len(batch),
        tenders="\n\n".join(blocks),
    )


def parse_response(text: str) -> list[dict]:
    """Extract the JSON array from the model response."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        # Tolerate a single object, or an array wrapped in a key.
        for value in parsed.values():
            if isinstance(value, list):
                return value
        return [parsed]
    return parsed


# Keyword rules used when Gemini can't be reached at all. Order matters —
# first match wins, so the more specific categories are checked first.
CATEGORY_KEYWORDS = [
    ("Bridge", ("bridge", "rob ", "rub ", "culvert", "flyover", "viaduct", "underpass", "overpass")),
    ("Flood Mitigation", ("flood", "erosion", "embankment", "protection work", "retaining wall")),
    ("Drainage", ("drain", "drainage", "sewer", "catch water", "cross drainage")),
    ("Safety", ("safety", "crash barrier", "signage", "road marking", "guard rail", "blackspot",
                "black spot", "traffic sign")),
    ("Consultancy", ("consultancy", "consultant", "dpr", "detailed project report", "supervision",
                     "feasibility", "authority engineer", "survey")),
    ("Road Expansion", ("widening", "four lane", "4-lane", "six lane", "6-lane", "two lane",
                        "2-lane", "expansion", "new construction", "bypass", "upgradation")),
    ("Maintenance", ("maintenance", "repair", "strengthening", "resurfacing", "renewal",
                     "periodic renewal", "patch", "pothole", "overlay")),
]


def fallback_enrichment(tender: dict) -> dict:
    """Derive category/summary/state locally, with no API call.

    Used only when Gemini is unavailable for a specific tender. Much better than
    labelling everything "Maintenance", and keeps the site useful if the API key
    stops working entirely.
    """
    haystack = " ".join(
        str(tender.get(k, ""))
        for k in ("title", "work_description", "product_category")
    ).lower()

    category = "Maintenance"
    for name, keywords in CATEGORY_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            category = name
            break

    # The scraper already resolves a state for most tenders — prefer it.
    state = tender.get("state") or "Unknown"

    summary = (tender.get("work_description") or tender.get("title") or "").strip()
    if len(summary) > 140:
        summary = summary[:137].rsplit(" ", 1)[0] + "…"

    return {
        **tender,
        "category": category,
        "summary": summary,
        "state": state,
        "enrichment_source": "rules",
    }


def _merge(tender: dict, item: dict) -> dict:
    """Apply one model result to one tender, validating the category."""
    category = item.get("category")
    if category not in CATEGORIES:
        category = fallback_enrichment(tender)["category"]

    summary = str(item.get("summary") or "").strip()
    state = str(item.get("state") or "").strip()
    local = fallback_enrichment(tender)

    return {
        **tender,
        "category": category,
        "summary": summary or local["summary"],
        # Trust the scraper's state over a model "Unknown".
        "state": tender.get("state") or (state if state and state != "Unknown" else local["state"]),
        "enrichment_source": "gemini",
    }


def enrich_batch(batch: list[dict], client, limiter: GeminiRateLimiter) -> list[dict]:
    """Enrich a batch of tenders in a single Gemini call.

    Always returns one result per input tender, in order — any tender the model
    skipped or mangled gets the local rule-based enrichment instead.

    Raises QuotaExhausted if the daily quota is gone; the caller must stop the
    whole pass rather than retrying.
    """
    prompt = build_prompt(batch)
    config = gemini.json_config()
    rate_limit_waits = 0

    for attempt in range(3):
        try:
            limiter.wait()
            response = client.models.generate_content(
                model=GEMINI_ENRICH_MODEL, contents=prompt, config=config
            )
            items = parse_response(response.text)

            # Match on the echoed index, falling back to positional order.
            by_index: dict[int, dict] = {}
            for pos, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                try:
                    idx = int(item.get("index", pos))
                except (TypeError, ValueError):
                    idx = pos
                by_index.setdefault(idx, item)

            results = []
            for i, tender in enumerate(batch):
                item = by_index.get(i)
                results.append(_merge(tender, item) if item else fallback_enrichment(tender))
            return results
        except json.JSONDecodeError:
            if attempt == 2:
                break
            time.sleep(2 ** attempt)
        except QuotaExhausted:
            raise
        except Exception as exc:
            # Daily quota gone / key rejected → stop the entire pass immediately.
            fatal = gemini.classify(exc)
            if fatal is not None:
                raise fatal from exc

            msg = str(exc)
            if gemini.is_rate_limit(msg):
                # Per-minute throttling: back off a bounded number of times,
                # then fall through to the local fallback. Never loop forever.
                if rate_limit_waits >= MAX_RATE_LIMIT_WAITS:
                    print("\n  Rate limited repeatedly — using local fallback.", flush=True)
                    break
                rate_limit_waits += 1
                wait = gemini.retry_delay_seconds(msg)
                print(f"\n  Rate limit hit — waiting {wait}s "
                      f"({rate_limit_waits}/{MAX_RATE_LIMIT_WAITS})…", flush=True)
                time.sleep(wait)
                continue

            print(f"\n  Gemini error ({type(exc).__name__}): {exc}", flush=True)
            if attempt == 2:
                break
            time.sleep(2 ** attempt)

    return [fallback_enrichment(t) for t in batch]


def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    client = gemini.make_client(GEMINI_API_KEY)
    limiter = GeminiRateLimiter(rpm=GEMINI_RPM_LIMIT, budget=GEMINI_ENRICH_BUDGET)

    with open(INPUT) as f:
        tenders = json.load(f)

    # Load existing enriched output to enable idempotent reruns
    if OUTPUT.exists():
        with open(OUTPUT) as f:
            enriched_map: dict[str, dict] = {t["tender_id"]: t for t in json.load(f)}
    else:
        enriched_map = {}

    # Never enriched — these come first.
    pending = [t for t in tenders
               if t["tender_id"] not in enriched_map
               or "category" not in enriched_map[t["tender_id"]]]

    # Enriched by the local keyword rules because Gemini was unavailable at the
    # time. They are already on the site and usable, just lower quality, so they
    # get whatever quota is left over after the genuinely new tenders.
    upgradable = [t for t in tenders
                  if t["tender_id"] in enriched_map
                  and enriched_map[t["tender_id"]].get("enrichment_source") == "rules"]

    to_enrich = pending + upgradable
    batches = [to_enrich[i:i + GEMINI_BATCH_SIZE]
               for i in range(0, len(to_enrich), GEMINI_BATCH_SIZE)]
    print(f"Total tenders: {len(tenders)}  |  New: {len(pending)}  "
          f"|  Rules-labelled to upgrade: {len(upgradable)}  "
          f"|  Batches of {GEMINI_BATCH_SIZE}: {len(batches)}  "
          f"|  Call budget: {GEMINI_ENRICH_BUDGET}", flush=True)

    deferred = 0
    for b, batch in enumerate(tqdm(batches, desc="Enriching")):
        try:
            results = enrich_batch(batch, client, limiter)
        except QuotaExhausted as exc:
            remaining = [t for later in batches[b:] for t in later]
            print(f"\nStopping Gemini calls: {exc}", flush=True)

            if exc.retry_tomorrow:
                # Leave the rest untouched — no 'category' means the next run
                # retries them, so the backlog drains over successive days
                # instead of being frozen with low-quality placeholder data.
                deferred = len(remaining)
                print(f"Deferring {deferred} tender(s) to the next run.", flush=True)
            else:
                # No future run will fare better until the key is fixed, so
                # process locally rather than leaving tenders off the site.
                print(f"Falling back to local rules for {len(remaining)} tender(s).",
                      flush=True)
                for t in remaining:
                    enriched_map[t["tender_id"]] = fallback_enrichment(t)
            break
        for enriched in results:
            enriched_map[enriched["tender_id"]] = enriched

    result = list(enriched_map.values())
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    by_source: dict[str, int] = {}
    for t in result:
        by_source[t.get("enrichment_source", "gemini")] = by_source.get(
            t.get("enrichment_source", "gemini"), 0) + 1

    print(f"\nGemini calls used: {limiter.calls_made}", flush=True)
    print(f"Enrichment sources: {by_source}", flush=True)
    if deferred:
        print(f"Deferred to next run: {deferred}", flush=True)
    print(f"Saved {len(result)} enriched tenders → {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
