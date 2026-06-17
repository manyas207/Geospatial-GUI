# Geospatial GUI

Terminal-launched web dashboard for multi-city **land surface temperature (LST)** analysis and the **Heat & Equity** GUI Frame with live census and population layers.

## Quick start

```bash
pip install -r requirements.txt
copy .env.example .env    # set CENSUS_API_KEY for Heat & Equity
python serve.py
```

Open **http://127.0.0.1:8765/**

Optional: install [Ollama](https://ollama.com/) for dashboard chat:

```bash
ollama pull llama3.2
```

## Application flow

| Tab | What it does |
|-----|----------------|
| **Ask** | Enter a US city address (`City, ST`), upload Landsat bands (`ST_B10`, `SR_B4`, `SR_B5`), run LST |
| **Demo** | 11-city Heat & Equity preview with placeholder LST and live Census maps |
| **Your project** | Dashboard for your uploaded cities (unlocked after first LST completes) |

**Ask → Your project:** enter a city address on **Ask** (e.g. `Round Rock, TX`), upload Landsat GeoTIFFs, run LST → dashboard opens automatically with per-tract `lst_mean_C`.

## Configuration

Copy `.env.example` to `.env`. Key variables:

| Variable | Required | Purpose |
|----------|----------|---------|
| `CENSUS_API_KEY` | For Heat & Equity | [Free Census API key](https://api.census.gov/data/key_signup.html) |
| `CHAT_RATE_LIMIT_MAX` | No | Max chat requests per IP per window (default 15) |
| `CHAT_RATE_LIMIT_WINDOW` | No | Rate-limit window in seconds (default 60) |
| `OLLAMA_BASE_URL` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `llama3.2` |

See [docs/DATA.md](docs/DATA.md) for full details.

## Project layout

```
Geospatial-GUI-1/
├── serve.py              # Entry point: python serve.py
├── backend/              # FastAPI routes and API clients
├── models/               # LST pipeline (and optional OBIA CLI in obia_core.py)
├── web/                  # Static frontend (HTML, CSS, JS)
│   └── vendor/maplibre-gl/  # Self-hosted MapLibre GL JS
├── data/                 # Uploads and caches (gitignored)
└── docs/                 # Architecture, API, data, demo guides
```

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and module map |
| [docs/API.md](docs/API.md) | REST endpoint reference |
| [docs/DATA.md](docs/DATA.md) | Data folders, caches, external APIs |
| [docs/DEMO.md](docs/DEMO.md) | Stakeholder demo walkthrough |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

Interactive API docs: http://127.0.0.1:8765/docs

## LST uploads

Upload Landsat `ST_B10`, `SR_B4`, and `SR_B5` together for each city. The pipeline prefers the thermal band when present.

Enter each city as **City, ST** on the Ask tab (e.g. `Round Rock, TX`). Geocoding uses Census, then OpenStreetMap Nominatim as a fallback.

## Iframe embed

```html
<iframe
  src="http://127.0.0.1:8765/"
  title="Geospatial Dashboard"
  width="100%"
  height="700"
  style="border:0;"
></iframe>
```
