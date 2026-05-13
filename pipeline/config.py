import os
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
FRONTEND_PUBLIC = ROOT.parent / "frontend" / "public" / "data"

DATA_DIR.mkdir(exist_ok=True)

EPROCURE_BASE = "https://eprocure.gov.in/eprocure/app"
MORTH_ORG_KEYWORDS = ["Ministry of Road Transport", "MoRTH", "NHAI", "National Highways"]
PAGE_SIZE = 20

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_RPM_LIMIT = 10  # Gemini 2.5 Flash free tier: 10 RPM

CATEGORIES = [
    "Bridge",
    "Road Expansion",
    "Maintenance",
    "Drainage",
    "Flood Mitigation",
    "Consultancy",
    "Safety",
]
