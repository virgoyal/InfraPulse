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
# Bulk enrichment is a trivial classify-and-summarise task, so it runs on the
# cheaper model — flash-lite has a noticeably larger free-tier daily allowance,
# which is what the ~200-call enrichment pass actually needs.
GEMINI_ENRICH_MODEL = os.environ.get("GEMINI_ENRICH_MODEL", "gemini-2.5-flash-lite")
GEMINI_RPM_LIMIT = 10  # Gemini 2.5 Flash free tier: 10 RPM

# Hard ceiling on Gemini calls per run, so one run can never drain the whole
# free-tier daily quota. Leftover tenders are picked up by the next day's run.
GEMINI_ENRICH_BUDGET = int(os.environ.get("GEMINI_ENRICH_BUDGET", "200"))
# Tenders classified per Gemini call. Batching is what keeps enrichment inside
# the free tier: ~200 pending tenders costs ~10 calls instead of ~200.
GEMINI_BATCH_SIZE = int(os.environ.get("GEMINI_BATCH_SIZE", "20"))
GEMINI_INSIGHTS_BUDGET = int(os.environ.get("GEMINI_INSIGHTS_BUDGET", "30"))

CATEGORIES = [
    "Bridge",
    "Road Expansion",
    "Maintenance",
    "Drainage",
    "Flood Mitigation",
    "Consultancy",
    "Safety",
]
