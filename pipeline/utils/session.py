"""
Session management for eprocure.gov.in.

The site runs on a Java EE stack. Every interaction requires a valid JSESSIONID
cookie set on the first GET. Pagination uses POST with hidden form state fields
that must be echoed back from the prior page.

If the table is missing from the HTML response (JavaScript-rendered), Playwright
is used as a fallback.
"""
from __future__ import annotations

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import EPROCURE_BASE, PAGE_SIZE


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def create_session() -> requests.Session:
    """Establish a session with eprocure.gov.in (sets JSESSIONID)."""
    session = requests.Session()
    session.headers.update(HEADERS)
    url = f"{EPROCURE_BASE}?page=FrontEndLatestActiveTenders&service=page"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return session


def _extract_hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    """Collect hidden form inputs needed for the re-post pattern."""
    fields: dict[str, str] = {}
    for inp in soup.find_all("input", {"type": "hidden"}):
        name = inp.get("name")
        value = inp.get("value", "")
        if name:
            fields[name] = value
    return fields


def fetch_tender_listing_page(
    session: requests.Session,
    start_index: int,
    org_keyword: str = "Ministry of Road Transport",
    prev_soup: Optional[BeautifulSoup] = None,
) -> BeautifulSoup:
    """
    Fetch one page of tender listings filtered by org_keyword.
    start_index: 0-based row offset for pagination.
    prev_soup: the soup from the previous page (used to extract hidden fields).
    """
    params = {
        "page": "FrontEndTendersByOrganisation",
        "service": "page",
    }
    data: dict[str, str] = {
        "organisationName": org_keyword,
        "$startIndex": str(start_index),
        "pageSize": str(PAGE_SIZE),
        "action": "search",
    }

    if prev_soup:
        data.update(_extract_hidden_fields(prev_soup))

    for attempt in range(3):
        try:
            resp = session.post(
                EPROCURE_BASE,
                params=params,
                data=data,
                timeout=30,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            return soup
        except Exception as exc:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError("fetch_tender_listing_page failed after retries")


def fetch_with_playwright(url: str) -> BeautifulSoup:
    """Playwright fallback for JavaScript-rendered pages."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers(HEADERS)
        page.goto(url, wait_until="networkidle", timeout=30000)
        try:
            page.wait_for_selector("table", timeout=15000)
        except Exception:
            pass
        html = page.content()
        browser.close()

    return BeautifulSoup(html, "lxml")
