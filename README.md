# InfraPulse

Live tracker for Indian government infrastructure tenders — scraped daily, enriched with AI, visualised on an interactive map.

## What it does

InfraPulse pulls active road and highway procurement tenders from India's [eProcure portal](https://eprocure.gov.in) (Ministry of Road Transport & Highways), enriches each one using Gemini AI, geocodes it to a map coordinate, and serves the result through a Next.js dashboard.

A GitHub Actions workflow runs the full pipeline every morning at 7 AM IST and commits the updated data back to the repo — no server required.

## Why

This data is technically public, but good luck using it. It's buried behind a clunky portal with session timeouts, and titles read like "Strengthening from Km 309.960 to Km 336.700 of NH 52 Mastikatta to Baleguli." InfraPulse makes infrastructure spending transparent at a national scale. Contractors can find relevant opportunities without fighting the portal, journalists and RTI activists can compare spending across states, and there's now a public record of how India's highway budget actually gets deployed.

## Architecture

```
eprocure.gov.in
      │
      ▼
01_scrape.py          Scrape ~230 MoRTH tender listings (session + DOM parsing)
01b_scrape_details.py Fetch individual tender detail pages (work description, value)
      │
      ▼
02_enrich.py          Gemini 2.5 Flash: classify category, write summary, infer state
      │
      ▼
03_geocode.py         Nominatim → real city coordinates; state centroid fallback
      │
      ▼
04_insights.py        Gemini 2.5 Flash: 2–3 sentence regional insight per state
      │
      ▼
05_finalize.py        Validate + copy JSON → frontend/public/data/
      │
      ▼
Next.js 14 frontend   Interactive choropleth map · tender sidebar · insights panel
```

## Pipeline details

| Step | Script | Output |
|---|---|---|
| 1 | `01_scrape.py` | `pipeline/data/raw_tenders.json` |
| 1b | `01b_scrape_details.py` | enriches raw with work description + value |
| 2 | `02_enrich.py` | `pipeline/data/enriched_tenders.json` |
| 3 | `03_geocode.py` | `pipeline/data/geolocated_tenders.json` |
| 4 | `04_insights.py` | `pipeline/data/insights.json` |
| 5 | `05_finalize.py` | `frontend/public/data/tenders.json` + `insights.json` |

Each step is **idempotent** — already-processed records are skipped on reruns. Geocode results are cached in `pipeline/data/geocode_cache.json` to respect Nominatim's 1 req/s rate limit and avoid re-geocoding 130+ cities on every run.

**Tender categories (Gemini-assigned):** Bridge · Road Expansion · Maintenance · Drainage · Flood Mitigation · Consultancy · Safety

## Frontend

Built with Next.js 14, TypeScript, Tailwind CSS, and React-Leaflet.

- **Choropleth map** — India states coloured by tender density; click a state to filter
- **Tender sidebar** — filterable cards (category, state, status) with closing date and AI summary
- **Insights panel** — Gemini-generated 2–3 sentence analysis of infrastructure priorities per state
- **Static data** — frontend reads from `public/data/tenders.json` (no API server needed)

## Running locally

### Pipeline

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export GEMINI_API_KEY=your_key_here

python 01_scrape.py
python 01b_scrape_details.py
python 02_enrich.py
python 03_geocode.py
python 04_insights.py
python 05_finalize.py
```

> Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com). The pipeline uses `gemini-2.5-flash` and stays within the free tier's 10 RPM limit.

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

## Automated updates

The GitHub Actions workflow (`.github/workflows/daily-pipeline.yml`) runs every day at 1:30 AM UTC (7 AM IST). It runs the full pipeline, then commits the updated JSON files back to the repo with the message `chore: daily tender update YYYY-MM-DD`.

To enable it on your fork:
1. Add `GEMINI_API_KEY` as a repository secret (Settings → Secrets → Actions)
2. The workflow has `contents: write` permission and will push automatically

Manual runs are also available from the Actions tab via `workflow_dispatch`.

## Tech stack

| Layer | Technology |
|---|---|
| Scraping | Python, requests, BeautifulSoup4 (lxml) |
| AI enrichment | Google Gemini 2.5 Flash (`google-genai`) |
| Geocoding | Nominatim (OpenStreetMap) |
| Automation | GitHub Actions (daily cron) |
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| Maps | Leaflet, react-leaflet, GeoJSON (India states) |

## Future work

- Cross-reference tenders against Union Budget allocations to check whether states are spending what was planned
- Timeline view to track tender activity month to month
- Expand beyond MoRTH. NHAI, state PWDs, and Railways all post on the same portal, so the pipeline generalizes naturally
- Email alerts for new tenders matching saved filters
- Award tracking: which contractors keep winning in which regions. That data exists on eprocure but sits behind CAPTCHAs, and automating past that needs a careful look at the legal implications first
- Mobile-responsive layout
- User accounts and saved searches
