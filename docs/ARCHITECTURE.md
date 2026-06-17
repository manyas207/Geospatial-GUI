# Architecture

Geospatial GUI is a **terminal-launched** web application: one Python process serves a static frontend (`web/`) and a FastAPI backend (`backend/`).

## High-level diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  User (browser)                                                  │
│    Ask │ Demo │ Your project (Heat & Equity)                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (same origin :8765)
┌───────────────────────────▼─────────────────────────────────────┐
│  INDEPENDENT FRONTEND (web/)                                     │
│    index.html · app.js · gf_frame.js · app.css                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ /api/*
┌───────────────────────────▼─────────────────────────────────────┐
│  BACKEND (backend/ + models/)                                    │
│    FastAPI routes · LST pipeline · external API clients          │
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
| **Ask** | `web/app.js` | `POST /api/projects/*` | Enter city address, upload Landsat, run LST |
| **Demo** | `web/gf_frame.js` | `GET /api/city-layers/demo-portfolio` | 11-city preview with placeholder LST |
| **Your project** | `web/gf_frame.js` | `GET /api/projects/{id}`, `POST /api/followup` | MapLibre dashboard (unlocked after ≥1 city ready) |

## Backend modules

### Core API (`backend/main.py`)

- Mounts static `web/` at `/`
- Registers all `/api/*` routes
- Creates cache dirs under `data/`

### Presets (`backend/presets.py`)

Single source of truth for the 11 demo/preset cities (names, colors, placeholder LST). Used by `project.py`, `city_layers.py`, and the Demo tab via `GET /api/projects/presets`.

### LST pipeline (`models/lst_core.py`, `models/lst_pipeline.py`, `backend/router.py`)

Dispatched by `backend/router.py` when a project city upload runs LST.

### Project pipeline (`backend/project.py`, `backend/lst_zonal.py`)

Multi-city LST workflow:

1. `POST /api/projects` — create project under `data/projects/{id}/`
2. `POST /api/projects/{id}/cities` — register city (`geocode.py`: Census → Nominatim → demo centroids)
3. `POST /api/projects/{id}/cities/{key}/lst` — upload Landsat bands, run LST, load census tracts (`city_layers.py`), zonal join (`lst_zonal.py`)
4. `GET /api/projects/{id}` — portfolio manifest with per-city status and tract vector URLs

### Cross-city comparison (`backend/city_compare.py`)

Detects city names and metrics in follow-up questions; returns structured `city_comparison` on `POST /api/followup`.

### City layers pipeline (`backend/city_layers.py`)

Orchestrates the Heat & Equity data flow:

1. `geocode.py` — Census Geocoder (street addresses) → Nominatim fallback (`City, ST`) → hardcoded demo centroids → Census reverse geocode for county FIPS
2. `tiger_tracts.py` — tract polygons (cached Census shapefile; TIGERweb fallback)
3. `census_api.py` — ACS 5-year tract demographics
4. `map_render.py` — optional server-side choropleth PNGs
5. `worldpop_raster.py` — WorldPop 2020 USA raster clip + preview

### AI integration

| Component | Role |
|-----------|------|
| `ollama_client.py` | HTTP client for local Ollama `/api/chat` |
| `dashboard_chat.py` | Follow-up Q&A grounded in dashboard context |
| `tract_query.py` | Structured tract attribute queries for chat |

## Request flows

### City layers (demo mode)

```
GET /api/city-layers/demo-portfolio?warm=true
  → cached payloads for 11 preset cities

POST /api/city-layers {"address": "Round Rock, TX"}  (fallback per city)
  → geocode → tracts → ACS → vector_layer URLs
```

### Multi-city LST project

```
POST /api/projects
POST /api/projects/{id}/cities {"address": "Round Rock, TX"}
POST /api/projects/{id}/cities/{key}/lst (multipart GeoTIFFs)
  → run_lst_pipeline
  → load_city_layers(address)
  → enrich_tracts_with_lst (per-tract lst_mean_C)
  → manifest updated
```

### Follow-up chat

```
POST /api/followup { question, context }
  → validate DashboardContext (context.raster must be a string)
  → if project_id: city_comparison from manifest
  → elif demo_cities: demo cross-city comparison
  → if tract_layer_token: tract query (cache or project GPKG)
  → Ollama with dashboard context (fallback stat summary if Ollama unreachable)
```

## Related docs

- [API.md](API.md) — endpoint reference
- [DATA.md](DATA.md) — folders, caches, external sources
- [DEMO.md](DEMO.md) — stakeholder walkthrough
