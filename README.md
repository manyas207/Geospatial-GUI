# Geospatial GUI

Terminal-launched web dashboard for geospatial analysis: upload rasters and run **LST** or **OBIA** pipelines, explore results on an interactive map, and use the **Heat & Equity** GUI Frame with live census and population layers.

## Quick start

Work in **Geospatial-GUI-1** (this folder), not `Desktop\Geospatial-GUI` — that older copy can hold port 8080 with stale files.

```bash
pip install -r requirements.txt
copy .env.example .env    # set CENSUS_API_KEY for Heat & Equity
python serve.py
```

Open **http://127.0.0.1:8765/**

Optional: install [Ollama](https://ollama.com/) and pull a model for natural-language routing and chat:

```bash
ollama pull llama3.2
```

## Application tabs

| Tab | What it does |
|-----|----------------|
| **Ask** | Upload GeoTIFFs + question → LST or OBIA analysis |
| **Dashboard** | Map, metrics, downloads, reference layers, follow-up chat |
| **Heat & Equity** | 11-city GF demo with live Census / WorldPop maps |

**Ask → Dashboard workflow:** upload a raster and ask a question on **Ask** → explore the output on an interactive pan/zoom map on **Dashboard**, with metrics and downloads below → ask follow-up questions in the conversation panel (answered by Ollama using the dashboard context).

## Configuration

Copy `.env.example` to `.env`. Key variables:

| Variable | Required | Purpose |
|----------|----------|---------|
| `CENSUS_API_KEY` | For Heat & Equity | [Free Census API key](https://api.census.gov/data/key_signup.html) |
| `OLLAMA_BASE_URL` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `llama3.2` |
| `REFERENCE_DATA_DIR` | No | Folder of reference GeoTIFFs for Dashboard |

See [docs/DATA.md](docs/DATA.md) for full details.

## Project layout

```
Geospatial-GUI-1/
├── serve.py              # Entry point: python serve.py
├── backend/              # FastAPI routes and API clients
├── models/               # LST and OBIA pipelines
├── web/                  # Static frontend (HTML, CSS, JS)
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

## Analysis models

- **LST** (`models/lst_core.py`): Upload Landsat `ST_B10`, `SR_B4`, and `SR_B5` together in one request, or a 3-band stack (thermal, red, NIR).
- **OBIA** (`models/obia_core.py`): Upload a multi-band GeoTIFF plus training shapefile components (`.shp`, `.shx`, `.dbf`, and optionally `.prj`) in the same request. Without a valid shapefile, only segmentation runs. Set `OBIA_SAMPLES_PATH` to point at a fixed shapefile if needed.

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

When deployed, host the `web/` folder and point the iframe at that URL.
