"""
Step 3: Geocode tenders to real geographic coordinates.

Strategy (in order):
  1. Nominatim (OpenStreetMap) — query "<location_city>, <state>, India"
     Only attempted when location_city looks like an actual place name
     (not a highway ref, km marker, or state-level string).
  2. State centroid fallback — used when Nominatim returns nothing useful
     or location_city isn't a geocodable place.

Results are cached in data/geocode_cache.json so reruns are instant and
we respect Nominatim's usage policy (1 req/s, no bulk hammering).

Outputs: pipeline/data/geolocated_tenders.json
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR
from utils.geo_lookup import get_coordinates, normalize_state

INPUT  = DATA_DIR / "enriched_tenders.json"
OUTPUT = DATA_DIR / "geolocated_tenders.json"
CACHE  = DATA_DIR / "geocode_cache.json"

# India bounding box — reject results outside this
INDIA_LAT = (6.5, 37.5)
INDIA_LNG = (68.0, 97.5)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "InfraPulse/1.0 (github.com/virgoyal/InfraPulse)"}

# Patterns that indicate location_city is NOT a real place name
_SKIP_RE = re.compile(
    r"""
    ^(nh|sh|mh|rnh|nhrw|rdnhd|r\s*and\s*b)[\s\-\d]   # highway refs: NH-07, SH-4
    | ^\d                                                # starts with a digit (km marker)
    | \bkm\b                                             # "Km 0.000 to km 63.000"
    | ^(andhra\s*pradesh|telangana|maharashtra|karnataka
        |gujarat|rajasthan|bihar|odisha|uttar\s*pradesh
        |madhya\s*pradesh|west\s*bengal|punjab|haryana
        |uttarakhand|himachal|arunachal|assam|jharkhand
        |chhattisgarh|delhi|goa|kerala|tamil\s*nadu
        |manipur|meghalaya|mizoram|nagaland|sikkim|tripura
        |jammu|ladakh|chandigarh|puducherry|pondicherry)$   # state-level only
    | division$                                          # "NH Karimnagar Division"
    | iahe\s                                             # institute abbreviations
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_geocodable(location_city: str) -> bool:
    """Return True if location_city looks like a real place worth geocoding."""
    if not location_city or len(location_city.strip()) < 3:
        return False
    return not _SKIP_RE.search(location_city.strip())


def nominatim_geocode(city: str, state: str) -> tuple[float, float] | None:
    """
    Query Nominatim for '<city>, <state>, India'.
    Returns (lat, lng) if a result within India is found, else None.
    """
    query = f"{city.strip()}, {state}, India"
    try:
        r = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "in"},
            headers=HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        results = r.json()
        if not results:
            return None
        lat = float(results[0]["lat"])
        lng = float(results[0]["lon"])
        # Validate within India bounds
        if INDIA_LAT[0] <= lat <= INDIA_LAT[1] and INDIA_LNG[0] <= lng <= INDIA_LNG[1]:
            return round(lat, 5), round(lng, 5)
    except Exception:
        pass
    return None


def load_cache() -> dict[str, list[float] | None]:
    if CACHE.exists():
        with open(CACHE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def main():
    with open(INPUT) as f:
        tenders = json.load(f)

    cache = load_cache()

    # Seed cache from existing geolocated output — this means even if the cache
    # file is stale or keys differ slightly, cities already resolved in a previous
    # run are never re-geocoded via Nominatim.
    if OUTPUT.exists():
        with open(OUTPUT) as f:
            prev = json.load(f)
        seeded = 0
        for t in prev:
            city  = t.get("location_city", "")
            state = t.get("state", "")          # already normalized in prev run
            key   = f"{city}||{state}"
            if key not in cache and t.get("geo_source") == "nominatim" and t.get("coordinates"):
                cache[key] = t["coordinates"]
                seeded += 1
        if seeded:
            print(f"Seeded {seeded} entries from previous geolocated output.")
            save_cache(cache)

    # Identify which (city, state) pairs need geocoding
    to_geocode: list[tuple[str, str]] = []
    for t in tenders:
        city  = t.get("location_city", "")
        state = normalize_state(t.get("state", "Unknown"))
        key   = f"{city}||{state}"
        if key not in cache and is_geocodable(city):
            to_geocode.append((city, state))

    # Deduplicate
    unique_pairs = list(dict.fromkeys(to_geocode))
    print(f"Total tenders: {len(tenders)}")
    print(f"Unique (city, state) pairs to geocode: {len(unique_pairs)}")
    print(f"Already cached: {len(cache)}")

    if unique_pairs:
        print("Geocoding via Nominatim (1 req/s)…")
        for city, state in tqdm(unique_pairs):
            key = f"{city}||{state}"
            result = nominatim_geocode(city, state)
            cache[key] = list(result) if result else None
            save_cache(cache)   # persist after every hit
            time.sleep(1.1)     # Nominatim rate limit: ≤1 req/s

    # Assign coordinates
    unknown_states: set[str] = set()
    geocoded_count = 0
    fallback_count = 0

    for tender in tenders:
        raw_state = tender.get("state", "Unknown")
        canonical = normalize_state(raw_state)
        if canonical == "Unknown":
            unknown_states.add(raw_state)
        tender["state"] = canonical

        city = tender.get("location_city", "")
        key  = f"{city}||{canonical}"

        coords = cache.get(key) if is_geocodable(city) else None
        if coords:
            tender["coordinates"] = [round(coords[0], 5), round(coords[1], 5)]
            tender["geo_source"] = "nominatim"
            geocoded_count += 1
        else:
            lat, lng = get_coordinates(canonical)
            # Jitter centroid fallbacks so they don't all stack on the same pixel.
            # ±0.4° ≈ ±45 km — visible separation, stays inside the state.
            jlat = lat + random.uniform(-0.4, 0.4)
            jlng = lng + random.uniform(-0.4, 0.4)
            tender["coordinates"] = [round(jlat, 4), round(jlng, 4)]
            tender["geo_source"] = "centroid"
            fallback_count += 1

    with open(OUTPUT, "w") as f:
        json.dump(tenders, f, indent=2, ensure_ascii=False)

    state_counts: dict[str, int] = {}
    for t in tenders:
        state_counts[t["state"]] = state_counts.get(t["state"], 0) + 1

    print(f"\nGeolocated {len(tenders)} tenders across {len(state_counts)} states.")
    print(f"  Real coordinates (Nominatim): {geocoded_count}")
    print(f"  State centroid fallback:      {fallback_count}")
    if unknown_states:
        print(f"  Could not resolve states: {sorted(unknown_states)}")
    print(f"Saved → {OUTPUT}")


if __name__ == "__main__":
    main()
