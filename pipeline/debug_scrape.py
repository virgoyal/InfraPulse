"""
Debug script — dumps raw HTML and table structure from eprocure.gov.in.
Run: python debug_scrape.py
"""
import sys, json, re
from pathlib import Path
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from config import EPROCURE_BASE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

session = requests.Session()
session.headers.update(HEADERS)

# ── 1. Hit the landing page to get JSESSIONID ──────────────────────────────
print("=== GET landing page ===")
r = session.get(
    "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
    timeout=30,
)
print(f"Status: {r.status_code}")
print(f"Cookies: {dict(session.cookies)}")
Path("debug_landing.html").write_text(r.text, encoding="utf-8")
print(f"Saved debug_landing.html ({len(r.text)} bytes)")

soup = BeautifulSoup(r.text, "lxml")
print(f"\nTables found: {len(soup.find_all('table'))}")
for i, t in enumerate(soup.find_all("table")[:5]):
    print(f"  table[{i}]: id={t.get('id')} class={t.get('class')} rows={len(t.find_all('tr'))}")

# ── 2. Try the org-search POST ──────────────────────────────────────────────
print("\n=== POST org search ===")
# Extract all hidden inputs from landing page
hidden = {inp["name"]: inp.get("value", "") for inp in soup.find_all("input", type="hidden") if inp.get("name")}
print(f"Hidden fields: {list(hidden.keys())[:10]}")

post_data = {
    **hidden,
    "organisationName": "Ministry of Road Transport",
    "action": "search",
    "$startIndex": "0",
    "pageSize": "20",
}
r2 = session.post(
    f"{EPROCURE_BASE}?page=FrontEndTendersByOrganisation&service=page",
    data=post_data,
    timeout=30,
)
print(f"Status: {r2.status_code}")
Path("debug_post.html").write_text(r2.text, encoding="utf-8")
print(f"Saved debug_post.html ({len(r2.text)} bytes)")

soup2 = BeautifulSoup(r2.text, "lxml")
tables = soup2.find_all("table")
print(f"\nTables found: {len(tables)}")
for i, t in enumerate(tables[:8]):
    rows = t.find_all("tr")
    print(f"  table[{i}]: id={t.get('id')} class={t.get('class')} rows={len(rows)}")
    if rows:
        cells = rows[0].find_all(["td","th"])
        print(f"    first row cells: {[c.get_text(strip=True)[:40] for c in cells[:6]]}")

# ── 3. Try the Active Tenders search with keyword ─────────────────────────
print("\n=== POST active tenders keyword search ===")
r3 = session.get(
    "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
    timeout=30,
)
soup3 = BeautifulSoup(r3.text, "lxml")
hidden3 = {inp["name"]: inp.get("value", "") for inp in soup3.find_all("input", type="hidden") if inp.get("name")}

post_data3 = {
    **hidden3,
    "tenderTitle": "highway",
    "action": "search",
    "$startIndex": "0",
    "pageSize": "20",
}
r4 = session.post(
    f"{EPROCURE_BASE}?page=FrontEndLatestActiveTenders&service=page",
    data=post_data3,
    timeout=30,
)
print(f"Status: {r4.status_code}")
Path("debug_keyword.html").write_text(r4.text, encoding="utf-8")
print(f"Saved debug_keyword.html ({len(r4.text)} bytes)")

soup4 = BeautifulSoup(r4.text, "lxml")
tables4 = soup4.find_all("table")
print(f"\nTables: {len(tables4)}")
for i, t in enumerate(tables4[:8]):
    rows = t.find_all("tr")
    print(f"  table[{i}]: id={t.get('id')} class={t.get('class')} rows={len(rows)}")
    if len(rows) > 1:
        cells = rows[1].find_all(["td","th"])
        print(f"    data row: {[c.get_text(strip=True)[:50] for c in cells[:5]]}")

# ── 4. Try NHAI specifically ───────────────────────────────────────────────
print("\n=== POST NHAI search ===")
post_nhai = {
    **hidden3,
    "organisationName": "NHAI",
    "action": "search",
    "$startIndex": "0",
    "pageSize": "20",
}
r5 = session.post(
    f"{EPROCURE_BASE}?page=FrontEndTendersByOrganisation&service=page",
    data=post_nhai,
    timeout=30,
)
print(f"Status: {r5.status_code}")
soup5 = BeautifulSoup(r5.text, "lxml")
tables5 = soup5.find_all("table")
print(f"Tables: {len(tables5)}")
for i, t in enumerate(tables5[:5]):
    rows = t.find_all("tr")
    print(f"  table[{i}]: id={t.get('id')} class={t.get('class')} rows={len(rows)}")
    if len(rows) > 1:
        cells = rows[1].find_all(["td","th"])
        print(f"    data row: {[c.get_text(strip=True)[:50] for c in cells[:5]]}")
