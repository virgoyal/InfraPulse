"""
Step 5: Validate pipeline output and copy to frontend/public/data/.

Validation checks:
  - 100–300 valid tenders
  - All required fields present and non-empty
  - Coordinates within India's bounding box
  - Categories within the allowed enum
  - At least 10 distinct states represented

Copies:
  geolocated_tenders.json → frontend/public/data/tenders.json
  insights.json           → frontend/public/data/insights.json
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import CATEGORIES, DATA_DIR, FRONTEND_PUBLIC

TENDERS_INPUT = DATA_DIR / "geolocated_tenders.json"
INSIGHTS_INPUT = DATA_DIR / "insights.json"

REQUIRED_FIELDS = ["tender_id", "title", "state", "coordinates", "category", "summary"]

# Sanity bounds. The archive grows indefinitely by design, so MAX_TOTAL_TENDERS is
# a "something is badly wrong" tripwire, not a real expectation.
MIN_TOTAL_TENDERS = 100
MAX_TOTAL_TENDERS = 5000
MIN_ACTIVE_TENDERS = 10

# Approximate India bounding box
LAT_MIN, LAT_MAX = 6.0, 37.5
LNG_MIN, LNG_MAX = 68.0, 97.5


def validate_tender(t: dict) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if not t.get(field):
            errors.append(f"missing '{field}'")
    coords = t.get("coordinates")
    if coords and len(coords) == 2:
        lat, lng = coords
        if not (LAT_MIN <= lat <= LAT_MAX):
            errors.append(f"lat {lat} out of India bounds")
        if not (LNG_MIN <= lng <= LNG_MAX):
            errors.append(f"lng {lng} out of India bounds")
    if t.get("category") and t["category"] not in CATEGORIES:
        errors.append(f"unknown category '{t['category']}'")
    return errors


def main():
    with open(TENDERS_INPUT) as f:
        tenders = json.load(f)

    valid: list[dict] = []
    rejected = 0

    MAX_SKIP_LINES = 25
    for t in tenders:
        errors = validate_tender(t)
        if errors:
            if rejected < MAX_SKIP_LINES:
                print(f"  SKIP {t.get('tender_id', '?')}: {', '.join(errors)}")
            elif rejected == MAX_SKIP_LINES:
                print("  … further skips suppressed")
            rejected += 1
        else:
            valid.append(t)

    active = [t for t in valid if t.get("status") != "archived"]
    print(f"\nValid: {len(valid)}  |  Rejected: {rejected}  |  Active: {len(active)}")

    # Assertions.
    #
    # The dataset grows over time: tenders that drop off the eProcure listing are
    # kept as "archived" so the frontend can still show them behind the "show
    # closed" filter. So the total has no meaningful upper bound — only sanity
    # bounds on the total floor and on how much of it is currently live.
    assert len(valid) >= MIN_TOTAL_TENDERS, (
        f"Expected at least {MIN_TOTAL_TENDERS} valid tenders, got {len(valid)}. "
        "Run more scrape/enrich steps first."
    )
    assert len(valid) <= MAX_TOTAL_TENDERS, (
        f"Got {len(valid)} valid tenders, above the {MAX_TOTAL_TENDERS} sanity cap — "
        "archived tenders are probably never being pruned."
    )
    assert len(active) >= MIN_ACTIVE_TENDERS, (
        f"Only {len(active)} active tenders — the scrape probably returned a bad page."
    )

    distinct_states = {t["state"] for t in valid}
    assert len(distinct_states) >= 10, (
        f"Only {len(distinct_states)} states represented — need ≥10."
    )

    category_counts: dict[str, int] = {}
    for t in valid:
        c = t["category"]
        category_counts[c] = category_counts.get(c, 0) + 1

    print(f"States represented: {len(distinct_states)}")
    print("Category breakdown:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    # Copy to frontend
    FRONTEND_PUBLIC.mkdir(parents=True, exist_ok=True)

    tenders_out = FRONTEND_PUBLIC / "tenders.json"
    with open(tenders_out, "w") as f:
        json.dump(valid, f, indent=2, ensure_ascii=False)
    print(f"\nCopied {len(valid)} tenders → {tenders_out}")

    if INSIGHTS_INPUT.exists():
        insights_out = FRONTEND_PUBLIC / "insights.json"
        shutil.copy(INSIGHTS_INPUT, insights_out)
        print(f"Copied insights → {insights_out}")
    else:
        print("No insights.json found — skipping.")

    print("\nAll done. Run `npm run dev` in frontend/ to preview.")


if __name__ == "__main__":
    main()
