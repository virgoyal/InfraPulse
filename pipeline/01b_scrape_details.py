"""
Step 1b: Scrape individual tender detail pages.

For each tender in raw_tenders.json that has a detail_url, fetches the
FrontEndViewTender page and extracts:
  - tender_value      (Tender Value in ₹)
  - work_description  (Work Description)
  - location_city     (Location field)
  - pincode           (Pincode)
  - period_of_work    (Period Of Work(Days))
  - product_category  (Product Category)
  - contract_type     (Form Of Contract)

Idempotent: skips tenders that already have tender_value filled in.
Outputs: pipeline/data/raw_tenders.json  (updated in-place)
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_DIR

TENDERS_FILE = DATA_DIR / "raw_tenders.json"
BASE = "https://eprocure.gov.in"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Fields to extract: label text (lowercase) → output key
WORK_ITEM_FIELDS = {
    "work description":      "work_description",
    "tender value in ₹":     "tender_value",
    "location":              "location_city",
    "pincode":               "pincode",
    "period of work(days)":  "period_of_work",
    "product category":      "product_category",
    "form of contract":      "contract_type",
    "contract type":         "contract_type",
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_detail_page(html: str) -> dict:
    """
    Extract Work Item Details from a tender detail page.
    The page uses <td>Label</td><td>Value</td> pairs inside labeled sections.
    """
    soup = BeautifulSoup(html, "lxml")
    extracted: dict[str, str] = {}

    # Walk all <td> pairs — label in one cell, value in the next
    all_tds = soup.find_all("td")
    for i, td in enumerate(all_tds):
        label = td.get_text(strip=True).lower()
        # Strip trailing colons/spaces
        label = label.rstrip(": ")

        if label in WORK_ITEM_FIELDS and i + 1 < len(all_tds):
            value_td = all_tds[i + 1]
            value = value_td.get_text(" ", strip=True)
            key = WORK_ITEM_FIELDS[label]
            if value and key not in extracted:
                extracted[key] = value

    # Clean up tender value — strip commas, keep raw string
    if "tender_value" in extracted:
        extracted["tender_value"] = extracted["tender_value"].replace("₹", "INR ").strip()

    return extracted


def fetch_detail(session: requests.Session, url: str) -> dict:
    """Fetch one detail page; return parsed fields or empty dict on failure."""
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return parse_detail_page(r.text)
        except Exception as exc:
            if attempt == 2:
                print(f"\n  FAIL {url[-40:]}: {exc}")
                return {}
            time.sleep(2 ** attempt)
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(TENDERS_FILE) as f:
        tenders: list[dict] = json.load(f)

    # Idempotency: skip tenders already enriched with detail data
    to_fetch = [
        t for t in tenders
        if t.get("detail_url") and not t.get("tender_value")
    ]
    already_done = len(tenders) - len(to_fetch)
    print(f"Total tenders: {len(tenders)}")
    print(f"Already have detail data: {already_done}")
    print(f"To fetch: {len(to_fetch)}")

    if not to_fetch:
        print("Nothing to do.")
        return

    session = requests.Session()
    session.headers.update(HEADERS)

    # Warm up session
    session.get(
        f"{BASE}/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
        timeout=30,
    )
    time.sleep(1)

    # Index tenders by ID for easy update
    tender_map = {t["tender_id"]: t for t in tenders}

    ok = 0
    for tender in tqdm(to_fetch, desc="Detail pages"):
        detail = fetch_detail(session, tender["detail_url"])
        if detail:
            tender_map[tender["tender_id"]].update(detail)
            ok += 1
        time.sleep(1.2)  # polite: ~50 req/min

    print(f"\nSuccessfully enriched: {ok}/{len(to_fetch)}")

    # Summary of what we got
    has_value = sum(1 for t in tender_map.values() if t.get("tender_value"))
    has_desc  = sum(1 for t in tender_map.values() if t.get("work_description"))
    has_city  = sum(1 for t in tender_map.values() if t.get("location_city"))
    print(f"Tender value present: {has_value}/{len(tenders)}")
    print(f"Work description:     {has_desc}/{len(tenders)}")
    print(f"Location city:        {has_city}/{len(tenders)}")

    # Save updated tenders
    updated = list(tender_map.values())
    with open(TENDERS_FILE, "w") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)
    print(f"\nUpdated → {TENDERS_FILE}")


if __name__ == "__main__":
    main()
