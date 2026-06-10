# Architecture

Geospatial GUI is a **terminal-launched** web application: one Python process serves a static frontend (`web/`) and a FastAPI backend (`backend/`). It aligns with the **GUI Frame (GF)** model: an independent frontend, user interaction layer, and backend geospatial/AI analyses.

## High-level diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  User (browser)                                                  │
│    Ask │ Dashboard │ Heat & Equity                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (same origin :8765)
┌───────────────────────────▼─────────────────────────────────────┐
│  INDEPENDENT FRONTEND (web/)                                     │
│    index.html · app.js · gf_frame.js · app.css                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ /api/*
┌───────────────────────────▼─────────────────────────────────────┐
│  BACKEND (backend/ + models/)                                    │
│    FastAPI routes · pipelines · external API clients             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   data/ (disk)      Ollama (local)     External APIs
   uploads, cache    :11434             Census, WorldPop
```

## Application tabs

| Tab | Frontend | Backend | Purpose |
|-----|----------|---------|---------|
| **Ask** | `web/app.js` | `POST /api/query`, `nlu.py`, `router.py` | Upload GeoTIFFs, natural-language routing, run LST or OBIA |
| **Dashboard** | `web/app.js` | Artifacts, previews, `POST /api/followup` | View pipeline results, reference layers, Ollama chat |
| **Heat & Equity** | `web/gf_frame.js` | `POST /api/city-layers` | 11-city GF demo with live census maps |

## Backend modules

### Core API (`backend/main.py`)

- Mounts static `web/` at `/`
- Registers all `/api/*` routes
- Creates cache dirs under `data/`

### Analysis pipelines (`models/`)

| Module | Intent | Output |
|--------|--------|--------|
| `lst_core.py` / `lst_pipeline.py` | Land surface temperature | GeoTIFF + preview PNG |
| `obia_core.py` / `obia_pipeline.py` | Segmentation / classification | GeoPackage, optional GeoTIFF |

Dispatched by `backend/router.py` after `backend/nlu.py` classifies the user question (Ollama JSON or keyword fallback).

### City layers pipeline (`backend/city_layers.py`)

Orchestrates the Heat & Equity data flow:

1. `geocode.py` — Census Geocoder → county FIPS + coordinates
2. `tiger_tracts.py` — tract polygons (cached Census shapefile; TIGERweb fallback)
3. `census_api.py` — ACS 5-year tract demographics
4. `map_render.py` — server-side choropleth PNGs
5. `worldpop_raster.py` — WorldPop 2020 USA raster clip + preview

### Reference layers (`backend/reference_layers.py`)

Scans `REFERENCE_DATA_DIR` for GeoTIFFs; builds previews and stats for the Dashboard.

### AI integration

| Component | Role |
|-----------|------|
| `ollama_client.py` | HTTP client for local Ollama `/api/chat` |
| `nlu.py` | Route questions to LST vs OBIA |
| `dashboard_chat.py` | Follow-up Q&A grounded in dashboard context |

## Request flows

### LST / OBIA analysis

```
POST /api/query (multipart: files + question)
  → save to data/{uuid}/
  → parse_intent (Ollama or keywords)
  → run_model (LST or OBIA)
  → build_artifacts + optional reference_layers overlap
  → JSON dashboard payload
```

### City layers (Heat & Equity)

```
POST /api/city-layers {"address": "Atlanta, GA"}
  → geocode_address
  → fetch_tract_geojson (shapefile cache)
  → fetch_tract_acs + merge
  → render map PNGs (density, income, ethnicity, tracts)
  → optional WorldPop preview
  → JSON with map_layers preview URLs
```

### Follow-up chat

```
POST /api/followup { question, context }
  → Ollama with dashboard/city stats in prompt
  → plain-text answer (keyword fallback if Ollama down)
```

## Design principles

- **Terminal deploy:** `python serve.py` — no separate frontend build step
- **Open source stack:** Python, FastAPI, rasterio, geopandas, matplotlib; optional Ollama
- **Server-rendered maps:** choropleth PNGs avoid client-side GIS libraries
- **Cached external data:** state tract shapefiles and map previews under `data/city_layers_cache/`
- **Configurable projects:** env-driven data paths and API keys (see [DATA.md](DATA.md))

## Known limitations

- Heat & Equity uses **one county per city** (geocoder centroid → primary county; Atlanta → Fulton, not full metro)
- **LST temperatures** in the 11-city list are **demo values** until real multi-city rasters are integrated
- **Report export** is a chat placeholder, not PDF generation
- Census ACS requires `CENSUS_API_KEY`

## Related docs

- [API.md](API.md) — endpoint reference
- [DATA.md](DATA.md) — folders, caches, external sources
- [DEMO.md](DEMO.md) — stakeholder walkthrough
