"""
Step 2: AI enrichment via Gemini Flash.

For each tender, extracts:
  - category  (one of 7 fixed values)
  - summary   (one sentence, ≤20 words)
  - state     (Indian state inferred from title/org)

Outputs: pipeline/data/enriched_tenders.json

Idempotent: tenders that already have a 'category' field are skipped.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))

from google import genai

from config import CATEGORIES, DATA_DIR, GEMINI_API_KEY, GEMINI_MODEL, GEMINI_RPM_LIMIT
from utils.rate_limiter import GeminiRateLimiter

INPUT = DATA_DIR / "raw_tenders.json"
OUTPUT = DATA_DIR / "enriched_tenders.json"

ENRICH_PROMPT = """\
You are analysing Indian government road/infrastructure procurement tenders.

Given the information below, respond with a single JSON object (no markdown, no extra text) containing exactly these three fields:

"category": one of [{categories}]
"summary": one sentence (max 20 words) describing what this project does
"state": the Indian state or UT where this project is located (use "Unknown" if genuinely unclear)

Tender title: {title}
Work description: {work_description}
Product category (from site): {product_category}
Organisation chain: {org_chain}
Location: {location_city}
""".strip()


def build_prompt(tender: dict) -> str:
    return ENRICH_PROMPT.format(
        categories=", ".join(CATEGORIES),
        title=tender.get("title", ""),
        work_description=tender.get("work_description", tender.get("title", "")),
        product_category=tender.get("product_category", ""),
        org_chain=tender.get("org_chain", tender.get("organization", "")),
        location_city=tender.get("location_city", ""),
    )


def parse_response(text: str) -> dict:
    """Extract the JSON object from the model response."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def enrich_tender(tender: dict, client, limiter: GeminiRateLimiter) -> dict:
    prompt = build_prompt(tender)

    for attempt in range(3):
        try:
            limiter.wait()
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            enrichment = parse_response(response.text)

            # Validate category
            if enrichment.get("category") not in CATEGORIES:
                enrichment["category"] = "Maintenance"

            return {**tender, **enrichment}
        except json.JSONDecodeError:
            if attempt == 2:
                break
            time.sleep(2 ** attempt)
        except Exception as exc:
            msg = str(exc)
            # 429 = rate limit — wait the suggested retry delay, don't count as attempt
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                import re as _re
                delay_match = _re.search(r"retry.*?(\d+)s", msg, _re.I)
                wait = int(delay_match.group(1)) + 2 if delay_match else 60
                print(f"\n  Rate limit hit — waiting {wait}s…")
                time.sleep(wait)
                # Don't increment attempt — retry immediately after wait
                continue
            print(f"\n  Gemini error ({type(exc).__name__}): {exc}")
            if attempt == 2:
                break
            time.sleep(2 ** attempt)

    # Fallback — keep tender with safe defaults
    return {
        **tender,
        "category": "Maintenance",
        "summary": tender.get("title", "")[:80],
        "state": "Unknown",
    }

def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)
    limiter = GeminiRateLimiter(rpm=GEMINI_RPM_LIMIT)

    with open(INPUT) as f:
        tenders = json.load(f)

    # Load existing enriched output to enable idempotent reruns
    if OUTPUT.exists():
        with open(OUTPUT) as f:
            enriched_map: dict[str, dict] = {t["tender_id"]: t for t in json.load(f)}
    else:
        enriched_map = {}

    to_enrich = [t for t in tenders if t["tender_id"] not in enriched_map or "category" not in enriched_map[t["tender_id"]]]
    print(f"Total tenders: {len(tenders)}  |  To enrich: {len(to_enrich)}")

    for tender in tqdm(to_enrich, desc="Enriching"):
        enriched = enrich_tender(tender, client, limiter)
        enriched_map[enriched["tender_id"]] = enriched

    result = list(enriched_map.values())
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(result)} enriched tenders → {OUTPUT}")


if __name__ == "__main__":
    main()
