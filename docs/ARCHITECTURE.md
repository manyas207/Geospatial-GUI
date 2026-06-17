# Architecture

Geospatial GUI is a **terminal-launched** web application: one Python process serves a static frontend (`web/`) and a FastAPI backend (`backend/` + `models/`).

## High-level diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  User (browser)                                                  │
│    Ask │ Demo │ Your project (Heat & Equity)                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (same origin :8765)
┌───────────────────────────▼─────────────────────────────────────┐
│  FRONTEND (web/)                                                 │
│    dashboard_adapter.js · app.js · gf_frame.js · app.css         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ /api/*
┌───────────────────────────▼─────────────────────────────────────┐
│  BACKEND (backend/) + MODEL PLUGINS (models/)                    │
│    FastAPI · model registry · project orchestration · APIs       │
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
| **Ask** | `web/app.js`, `web/dashboard_adapter.js` | `GET /api/models`, `POST /api/projects/*` | Pick model, enter city, upload files, run analysis |
| **Demo** | `web/gf_frame.js` | `GET /api/city-layers/demo-portfolio` | 11-city preview with placeholder LST |
| **Your project** | `web/gf_frame.js`, `web/dashboard_adapter.js` | `GET /api/projects/{id}`, `POST /api/followup` | Adapter-driven dashboard (unlocked after ≥1 city ready) |

## Backend modules

### Core API (`backend/main.py`)

- Mounts static `web/` at `/`
- Registers all `/api/*` routes including `GET /api/models`
- Creates cache dirs under `data/`

### Model registry (`models/contract.py`, `models/registry.py`, `models/lst_model.py`)

Plugin contract and registration. Each model defines inputs, `run`, optional `post_process`, dashboard type, and vector fields. See [MODELS.md](MODELS.md).

Dispatched by `backend/router.run_model` and `backend/project.run_city_model_upload`.

### Presets (`backend/presets.py`)

Single source of truth for the 11 demo/preset cities (names, colors, placeholder LST). Used by `project.py`, `city_layers.py`, and the Demo tab via `GET /api/projects/presets`.

### LST implementation (`models/lst_pipeline.py`, `models/lst_core.py`)

Low-level Landsat LST pipeline. Wrapped by `models/lst_model.py` as registry model id `lst`.

### Project pipeline (`backend/project.py`, `backend/lst_zonal.py`)

Multi-city project workflow:

1. `POST /api/projects` — create project under `data/projects/{id}/` (optional `model_id`)
2. `POST /api/projects/{id}/cities` — register city (`geocode.py`: Census → Nominatim → demo centroids)
3. `POST /api/projects/{id}/cities/{key}/run?model=lst` — upload files, run model, tract enrichment when applicable
4. `GET /api/projects/{id}` — portfolio manifest with per-city `run_stats`, `model_id`, tract vector URLs

Legacy: `POST .../lst` aliases `.../run?model=lst`.

### Cross-city comparison (`backend/city_compare.py`)

Detects city names and metrics in follow-up questions; reads `run_stats` (with `lst_stats` fallback). Returns structured `city_comparison` on `POST /api/followup`.

### City layers pipeline (`backend/city_layers.py`)

Orchestrates the Heat & Equity data flow:

1. `geocode.py` — Census Geocoder → Nominatim fallback (`City, ST`) → demo centroids → Census reverse geocode for county FIPS
2. `tiger_tracts.py` — tract polygons (cached Census shapefile; TIGERweb fallback)
3. `census_api.py` — ACS 5-year tract demographics
4. `map_render.py` — optional server-side choropleth PNGs
5. `worldpop_raster.py` — WorldPop 2020 USA raster clip + preview

### AI integration

| Component | Role |
|-----------|------|
| `ollama_client.py` | HTTP client for local Ollama `/api/chat` |
| `dashboard_chat.py` | Follow-up Q&A grounded in dashboard context (`analysis_model` when set) |
| `tract_query.py` | Structured tract attribute queries for chat |

## Frontend modules

### Dashboard adapter (`web/dashboard_adapter.js`)

- Fetches `GET /api/models`
- Merges API metadata with `PRESENTATION` overrides (labels, choropleth field, units)
- Shared by Ask and Heat & Equity project mode

### Ask workflow (`web/app.js`)

Model dropdown, dynamic upload hints, project portfolio, `POST .../run?model={id}`.

### Heat & Equity frame (`web/gf_frame.js`)

MapLibre maps, charts, layer toggles, chat. Project mode uses adapter for primary metric, legend, and `analysis_model` in chat context. Models with `dashboard: "raster"` show a placeholder shell until a dedicated view exists.

## Request flows

### List models (Ask tab bootstrap)

```
GET /api/models
  → [{ id, label, input_schema, dashboard, primary_metric, … }]
```

### City layers (demo mode)

```
GET /api/city-layers/demo-portfolio?warm=true
  → cached payloads for 11 preset cities

POST /api/city-layers {"address": "Round Rock, TX"}
  → geocode → tracts → ACS → vector_layer URLs
```

### Multi-city analysis project

```
GET /api/models
POST /api/projects { "model_id": "lst" }
POST /api/projects/{id}/cities {"address": "Round Rock, TX"}
POST /api/projects/{id}/cities/{key}/run?model=lst (multipart files)
  → run_model (registry)
  → LST post_process: load_city_layers + enrich_tracts_with_lst
  → manifest updated (model_id, run_stats, lst_stats alias)
```

### Follow-up chat

```
POST /api/followup { question, context }
  → validate DashboardContext (context.raster must be a string)
  → context may include analysis_model (active registry model id)
  → if project_id: city_comparison from manifest
  → elif demo_cities: demo cross-city comparison
  → if tract_layer_token: tract query (cache or project GPKG)
  → Ollama with dashboard context (fallback stat summary if Ollama unreachable)
```

## Related docs

- [MODELS.md](MODELS.md) — adding lab models
- [API.md](API.md) — endpoint reference
- [DATA.md](DATA.md) — folders, caches, external sources
- [DEMO.md](DEMO.md) — stakeholder walkthrough
