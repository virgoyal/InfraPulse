from __future__ import annotations

# Approximate centroids for all 28 states + 8 UTs
STATE_COORDINATES: dict[str, tuple[float, float]] = {
    "Andhra Pradesh": (15.9129, 79.7400),
    "Arunachal Pradesh": (28.2180, 94.7278),
    "Assam": (26.2006, 92.9376),
    "Bihar": (25.0961, 85.3131),
    "Chhattisgarh": (21.2787, 81.8661),
    "Delhi": (28.7041, 77.1025),
    "Goa": (15.2993, 74.1240),
    "Gujarat": (22.2587, 71.1924),
    "Haryana": (29.0588, 76.0856),
    "Himachal Pradesh": (31.1048, 77.1734),
    "Jharkhand": (23.6102, 85.2799),
    "Karnataka": (15.3173, 75.7139),
    "Kerala": (10.8505, 76.2711),
    "Madhya Pradesh": (22.9734, 78.6569),
    "Maharashtra": (19.7515, 75.7139),
    "Manipur": (24.6637, 93.9063),
    "Meghalaya": (25.4670, 91.3662),
    "Mizoram": (23.1645, 92.9376),
    "Nagaland": (26.1584, 94.5624),
    "Odisha": (20.9517, 85.0985),
    "Punjab": (31.1471, 75.3412),
    "Rajasthan": (27.0238, 74.2179),
    "Sikkim": (27.5330, 88.5122),
    "Tamil Nadu": (11.1271, 78.6569),
    "Telangana": (18.1124, 79.0193),
    "Tripura": (23.9408, 91.9882),
    "Uttar Pradesh": (26.8467, 80.9462),
    "Uttarakhand": (30.0668, 79.0193),
    "West Bengal": (22.9868, 87.8550),
    # UTs
    "Jammu and Kashmir": (33.7782, 76.5762),
    "Ladakh": (34.1526, 77.5771),
    "Chandigarh": (30.7333, 76.7794),
    "Puducherry": (11.9416, 79.8083),
    "Andaman and Nicobar": (11.7401, 92.6586),
    "Lakshadweep": (10.5667, 72.6417),
    "Dadra and Nagar Haveli": (20.1809, 73.0169),
    # Fallback
    "Unknown": (20.5937, 78.9629),
}

# Aliases for common abbreviations / alternate spellings
_ALIASES: dict[str, str] = {
    "Tamilnadu": "Tamil Nadu",
    "Tamil Nadu": "Tamil Nadu",
    "J&K": "Jammu and Kashmir",
    "J & K": "Jammu and Kashmir",
    "UP": "Uttar Pradesh",
    "MP": "Madhya Pradesh",
    "AP": "Andhra Pradesh",
    "HP": "Himachal Pradesh",
    "TN": "Tamil Nadu",
    "WB": "West Bengal",
    "NCT": "Delhi",
    "NCT of Delhi": "Delhi",
    "New Delhi": "Delhi",
    "Andaman": "Andaman and Nicobar",
    "Nicobar": "Andaman and Nicobar",
    "Pondicherry": "Puducherry",
}


def normalize_state(raw: str) -> str:
    """Return the canonical state name, or 'Unknown'."""
    if not raw:
        return "Unknown"
    raw = raw.strip()

    # Direct match
    if raw in STATE_COORDINATES:
        return raw

    # Alias match
    if raw in _ALIASES:
        return _ALIASES[raw]

    # Case-insensitive substring search
    lower = raw.lower()
    for canonical in STATE_COORDINATES:
        if canonical.lower() in lower or lower in canonical.lower():
            return canonical

    return "Unknown"


def get_coordinates(state: str) -> tuple[float, float]:
    canonical = normalize_state(state)
    return STATE_COORDINATES.get(canonical, STATE_COORDINATES["Unknown"])
