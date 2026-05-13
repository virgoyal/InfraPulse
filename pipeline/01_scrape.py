"""
Step 1: Scrape MoRTH tender listings from eprocure.gov.in.

Flow:
  1. Warm up session (sets JSESSIONID cookie)
  2. POST to org listing → find 'Ministry of Road Transport' DirectLink
  3. GET that DirectLink → all ~231 tenders on one page (no pagination)
  4. Parse table rows with 6 cells: S.No / Published / Closing / Opening / Title+ID / Org chain

Outputs: pipeline/data/raw_tenders.json
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_DIR

OUTPUT = DATA_DIR / "raw_tenders.json"

BASE = "https://eprocure.gov.in"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Regex to extract tender ID like 2026_MoRTH_908152_1
TENDER_ID_RE = re.compile(r"\[(\d{4}_\w+_\d+_\d+)\]")

# RO city → state mapping (extracted from org chain "RO <City>")
RO_STATE_MAP = {
    "Dehradun": "Uttarakhand",
    "Bhubaneswar": "Odisha",
    "Hyderabad": "Telangana",
    "Chennai": "Tamil Nadu",
    "Mumbai": "Maharashtra",
    "Pune": "Maharashtra",
    "Lucknow": "Uttar Pradesh",
    "Patna": "Bihar",
    "Jaipur": "Rajasthan",
    "Chandigarh": "Punjab",
    "Ahmedabad": "Gujarat",
    "Bhopal": "Madhya Pradesh",
    "Raipur": "Chhattisgarh",
    "Ranchi": "Jharkhand",
    "Guwahati": "Assam",
    "Kolkata": "West Bengal",
    "Bangalore": "Karnataka",
    "Bengaluru": "Karnataka",
    "Thiruvananthapuram": "Kerala",
    "Jammu": "Jammu and Kashmir",
    "Srinagar": "Jammu and Kashmir",
    "Shimla": "Himachal Pradesh",
    "Delhi": "Delhi",
    "Nagpur": "Maharashtra",
    "Vijayawada": "Andhra Pradesh",
    "Agartala": "Tripura",
    "Imphal": "Manipur",
    "Shillong": "Meghalaya",
    "Aizawl": "Mizoram",
    "Kohima": "Nagaland",
    "Itanagar": "Arunachal Pradesh",
    "Gangtok": "Sikkim",
    "Panaji": "Goa",
}

# State names that appear literally in title text
STATE_TITLE_RE = re.compile(
    r"\b(Andhra Pradesh|Arunachal Pradesh|Assam|Bihar|Chhattisgarh|Goa|Gujarat|"
    r"Haryana|Himachal Pradesh|Jharkhand|Karnataka|Kerala|Madhya Pradesh|Maharashtra|"
    r"Manipur|Meghalaya|Mizoram|Nagaland|Odisha|Punjab|Rajasthan|Sikkim|Tamil Nadu|"
    r"Telangana|Tripura|Uttar Pradesh|Uttarakhand|West Bengal|"
    r"Delhi|Jammu and Kashmir|Ladakh|Chandigarh)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def warmup(session: requests.Session) -> None:
    session.get(
        f"{BASE}/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
        timeout=30,
    )


def get_morth_directlink(session: requests.Session) -> str:
    """
    POST to org listing page, then walk all cells in DOM order to find
    the DirectLink anchor that immediately follows the 'Ministry of Road
    Transport and Highways' text cell.
    Returns the full absolute URL.
    """
    r = session.post(
        f"{BASE}/eprocure/app?page=FrontEndTendersByOrganisation&service=page",
        data={"organisationName": "Ministry of Road Transport", "action": "search"},
        timeout=30,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # Walk every cell in DOM order; when we hit the MoRTH name cell,
    # the very next cell with a DirectLink anchor is our target.
    all_cells = soup.find_all(["td", "th"])
    found_morth = False
    for cell in all_cells:
        text = cell.get_text(strip=True)
        if "Ministry of Road Transport and Highways" == text:
            found_morth = True
            continue
        if found_morth:
            a = cell.find("a", href=lambda h: h and "DirectLink" in h)
            if a:
                return BASE + a["href"]
            # If the next cell has no link, keep looking a few more cells
            # (sometimes there's an empty cell between name and count)
            if text:  # non-empty cell with no link = wrong table, reset
                found_morth = False

    raise RuntimeError(
        "Could not locate MoRTH DirectLink. "
        "Try running debug_scrape.py to inspect the page structure."
    )


def fetch_morth_page(session: requests.Session, url: str) -> BeautifulSoup:
    r = session.get(url, timeout=60)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def find_tender_table(soup: BeautifulSoup):
    """
    The tender data is in a table that has a 6-cell header row:
    S.No | e-Published Date | Closing Date | Opening Date | Title... | Organisation Chain
    """
    EXPECTED_HEADERS = {"s.no", "e-published date", "closing date", "title"}

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) == 6:
                headers = {c.get_text(strip=True).lower() for c in cells}
                if len(headers & EXPECTED_HEADERS) >= 3:
                    return table
    return None


def extract_state_from_org(org_chain: str) -> str:
    """Extract state from org chain like '...||RO Bhubaneswar - MoRTH||...'"""
    # Look for "RO <City>"
    m = re.search(r"\bRO\s+(\w+)", org_chain)
    if m:
        city = m.group(1)
        if city in RO_STATE_MAP:
            return RO_STATE_MAP[city]
    return ""


def extract_state_from_title(title: str) -> str:
    """Match state name directly in title text."""
    m = STATE_TITLE_RE.search(title)
    return m.group(0).title() if m else ""


def parse_title_cell(cell) -> tuple[str, str, str]:
    """
    Returns (title, tender_id, detail_url).
    Cell format: [Clean title] [ref_no][YYYY_MoRTH_XXXXXX_X]
    """
    anchor = cell.find("a", href=True)
    detail_url = (BASE + anchor["href"]) if anchor else ""

    # Clean title: anchor text, strip surrounding brackets
    title = anchor.get_text(" ", strip=True) if anchor else cell.get_text(" ", strip=True)
    title = title.strip("[] \t\n")

    # Tender ID: last [XXXX_XXX_XXXXXX_X] pattern in cell text
    full_text = cell.get_text(" ", strip=True)
    ids = TENDER_ID_RE.findall(full_text)
    tender_id = ids[-1] if ids else ""

    return title, tender_id, detail_url


def parse_tenders(soup: BeautifulSoup) -> list[dict]:
    table = find_tender_table(soup)
    if not table:
        return []

    tenders: list[dict] = []
    rows = table.find_all("tr")

    # Find header row index
    header_idx = None
    for i, row in enumerate(rows):
        cells = row.find_all(["td", "th"])
        if len(cells) == 6:
            texts = [c.get_text(strip=True).lower() for c in cells]
            if "s.no" in texts and "closing date" in texts:
                header_idx = i
                break

    if header_idx is None:
        return []

    for row in rows[header_idx + 1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) != 6:
            continue

        published = cells[1].get_text(strip=True)
        closing = cells[2].get_text(strip=True)
        org_chain = cells[5].get_text(" ", strip=True)

        title, tender_id, detail_url = parse_title_cell(cells[4])

        if not title or not tender_id:
            continue

        # State: try org chain first, then title text
        state = extract_state_from_org(org_chain) or extract_state_from_title(title)

        # Simplify org chain to last meaningful segment
        org_parts = [p.strip() for p in org_chain.split("||") if p.strip()]
        organization = org_parts[-1].replace(" - MoRTH", "").strip() if org_parts else org_chain

        tenders.append({
            "tender_id": tender_id,
            "title": title,
            "organization": organization,
            "org_chain": org_chain,
            "published_date": published,
            "closing_date": closing,
            "state": state,
            "value": "",        # not on listing page — filled by enrichment or detail scrape
            "detail_url": detail_url,
        })

    return tenders


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_existing() -> list[dict]:
    if OUTPUT.exists():
        with open(OUTPUT) as f:
            return json.load(f)
    return []


def merge(existing: list[dict], scraped: list[dict]) -> tuple[list[dict], int, int, int]:
    """
    Merge freshly scraped tenders with the existing dataset.

    Rules:
      - Tender still on page  → status "active", refresh listing fields
      - Tender gone from page → status "archived" (kept for historical insight data)
      - Brand new tender      → status "active", append

    Returns (merged_list, new_count, archived_count, reactivated_count).
    """
    prev_by_id: dict[str, dict] = {t["tender_id"]: t for t in existing}
    scraped_by_id: dict[str, dict] = {t["tender_id"]: t for t in scraped}

    combined: list[dict] = []
    new_count = archived_count = reactivated_count = 0

    # Process every previously-known tender
    for tid, prev in prev_by_id.items():
        if tid in scraped_by_id:
            # Merge: keep enriched/detail fields from prev, refresh listing fields
            fresh = scraped_by_id[tid]
            merged = {**prev}
            # Listing fields that may have changed (dates, org chain)
            for key in ("published_date", "closing_date", "org_chain", "organization"):
                if fresh.get(key):
                    merged[key] = fresh[key]
            was_archived = prev.get("status") == "archived"
            merged["status"] = "active"
            combined.append(merged)
            if was_archived:
                reactivated_count += 1
        else:
            # No longer on page — archive it
            if prev.get("status") != "archived":
                archived_count += 1
                print(f"  ↓ Archived: {prev['tender_id']} — {prev['title'][:60]}")
            prev["status"] = "archived"
            combined.append(prev)

    # Append genuinely new tenders
    for tid, t in scraped_by_id.items():
        if tid not in prev_by_id:
            t["status"] = "active"
            combined.append(t)
            new_count += 1

    return combined, new_count, archived_count, reactivated_count


def main():
    existing = load_existing()
    print(f"Existing tenders on disk: {len(existing)}")

    session = make_session()
    print("Warming up session…")
    warmup(session)
    time.sleep(1)

    print("Fetching org listing to locate MoRTH DirectLink…")
    url = get_morth_directlink(session)
    print(f"MoRTH tender URL: {url[:80]}…")
    time.sleep(1)

    print("Fetching MoRTH tender page…")
    soup = fetch_morth_page(session, url)

    print("Parsing tenders…")
    scraped = parse_tenders(soup)
    print(f"Found {len(scraped)} tenders on page")

    combined, new_count, archived_count, reactivated_count = merge(existing, scraped)

    active = sum(1 for t in combined if t.get("status") != "archived")
    print(
        f"\nMerge result: {new_count} new  |  {archived_count} newly archived"
        f"  |  {reactivated_count} reactivated"
    )
    print(f"Active: {active}  |  Archived: {len(combined) - active}  |  Total: {len(combined)}")

    # State coverage summary (active only)
    state_counts: dict[str, int] = {}
    for t in combined:
        if t.get("status") != "archived":
            s = t["state"] or "Unknown"
            state_counts[s] = state_counts.get(s, 0) + 1
    print("\nState distribution (active):")
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {state or 'Unknown'}: {count}")

    with open(OUTPUT, "w") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → {OUTPUT}")


if __name__ == "__main__":
    main()
