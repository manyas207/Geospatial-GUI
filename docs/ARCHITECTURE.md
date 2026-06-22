# Architecture

Geospatial GUI is a **terminal-launched** web application: one Python process serves a static frontend (`web/`) and a FastAPI backend (`backend/` + `models/`).

## Application tabs

| Tab | Frontend | Backend | Purpose |
|-----|----------|---------|---------|
| **Ask** | `web/app.js`, `web/dashboard_adapter.js`, `web/plugins/*` | `GET /api/models`, `POST /api/projects/*` | Pick model, add city, upload files, run analysis |
| **Demo** | `web/gf_frame.js`, `web/gf_frame_*.js` | `GET /api/city-layers/demo-portfolio` | 11-city preview with placeholder LST |
| **Your project** | `web/gf_frame.js`, `web/gf_frame_*.js`, `web/dashboard_adapter.js` | `GET /api/projects/{id}`, `POST /api/followup` | Adapter-driven dashboard (unlocked after ≥1 city ready) |

## Backend layout

```
backend/
  main.py              # App factory; mounts routers + static web/
  config.py            # Paths (data/, projects/, city_layers_cache/)

  api/
    deps.py            # Shared request helpers (IP, rate limit, previews)
    routes/
      models.py        # GET /api/models
      projects.py      # /api/projects/*
      reports.py       # POST /api/projects/{id}/report
      city_layers.py   # /api/city-layers/*
      followup.py      # POST /api/followup

  core/                # Schemas, constants, uploads, presets
  projects/            # Project storage, compare, model dispatch
  layers/              # Geocode → census → tracts → maps
  chat/                # Ollama, equity burden, dashboard Q&A
  pipelines/           # LST zonal join, OBIA zonal join, raster file picking
  report/              # PDF export
```

## Backend modules

### Core API (`backend/main.py` + `backend/api/routes/`)

- Mounts static `web/` at `/`
- Registers `/api/*` route modules
- Paths and cache dirs in `backend/config.py`

### Model registry (`models/contract.py`, `models/registry.py`, `models/lst_model.py`, `models/obia_model.py`)

Plugin contract and registration. Each model defines inputs, `run`, optional `post_process`, dashboard type, and vector fields. See [ADDING_A_MODEL.md](ADDING_A_MODEL.md) and [MODELS.md](MODELS.md).

Registered today: `lst` (Land Surface Temperature), `obia` (OBIA land cover).

Dispatched by `backend/projects/dispatch.py` → `backend/projects/service.py` (`run_city_model_upload`). Model runs execute in a **background task**; the Ask tab polls `GET /api/projects/{id}` and shows a **model-aware** progress bar (LST vs OBIA step labels) until the city status is `ready` or `error`.

### Presets (`backend/core/presets.py`)

Single source of truth for the 11 demo/preset cities (names, colors, placeholder LST). Used by project service, layer orchestrator, and the Demo tab via `GET /api/projects/presets`.

### LST implementation (`models/lst_pipeline.py`, `models/lst_core.py`)

Low-level Landsat LST pipeline. Wrapped by `models/lst_model.py` as registry model id `lst`.

### OBIA implementation (`models/obia_core.py`, `models/obia_model.py`)

Object-based image analysis: SLIC segmentation → spectral/shape/texture features → Random Forest classification from training ROIs → tract-level dominant class via `backend/pipelines/obia_zonal.py`.

Supports **1–7+ band** rasters (HLS layout when ≥7 bands; simpler RGBN mapping for fewer bands). Training shapefiles accept flexible column names (`class_id`, `macroclass`, `id` for ROI grouping). **Pixel- and point-sized** training samples are supported via centroid labeling and buffered rasterization.

### Project pipeline (`backend/projects/service.py`, `backend/pipelines/lst_zonal.py`, `backend/pipelines/obia_zonal.py`)

Multi-city project workflow:

1. `POST /api/projects` — create project under `data/projects/{id}/` (optional `model_id`)
2. `POST /api/projects/{id}/cities` — register city (`layers/geocode.py`: Census → Nominatim → demo centroids)
3. `POST /api/projects/{id}/cities/{key}/run?model=lst|obia` — upload files, background model run, tract enrichment when applicable
4. `GET /api/projects/{id}` — portfolio manifest with per-city `run_stats`, `model_id`, tract vector URLs

### Cross-city comparison (`backend/projects/compare.py`)

Detects city names and metrics in follow-up questions; reads `run_stats` (with `lst_stats` fallback). Returns structured `city_comparison` on `POST /api/followup`.

### City layers pipeline (`backend/layers/orchestrator.py`)

Orchestrates the Heat & Equity data flow:

1. `layers/geocode.py` — Census Geocoder → Nominatim fallback (`City, ST`) → demo centroids → Census reverse geocode for county FIPS
2. `layers/tracts.py` — tract polygons (cached Census shapefile; TIGERweb fallback)
3. `layers/census.py` — ACS 5-year tract demographics
4. `layers/map_render.py` — optional server-side choropleth PNGs

### AI integration

| Component | Role |
|-----------|------|
| `chat/ollama.py` | HTTP client for local Ollama `/api/chat` |
| `chat/dashboard.py` | Follow-up Q&A grounded in dashboard context (`analysis_model` when set) |
| `chat/equity_burden.py` | Heat-equity burden ranking for tract questions |
| `layers/tract_query.py` | Structured tract attribute queries for chat |

## Frontend modules

### Dashboard adapter (`web/dashboard_adapter.js`)

- ES module: fetches `GET /api/models`, merges API metadata with per-model plugins
- Plugins: `web/plugins/lst_plugin.js`, `web/plugins/obia_plugin.js` (contract in `web/model_plugin.js`)
- Shared by Ask and Heat & Equity project mode (choropleth, legend, metrics, chat hints)

### Ask workflow (`web/app.js`)

1. Select analysis model and enter city + optional month/year
2. **Add city to project** (registers address in the active portfolio; model locks after first city)
3. Upload input files
4. **Run analysis** (step 2 button appears after step 1; label uses model `runVerb`, e.g. “Run LST for city”)
5. Progress bar polls manifest status with per-model steps; redirects to **Your project** when ready

Project is auto-created on first use (`POST /api/projects`); portfolio stored under `data/projects/{id}/`.

### Heat & Equity frame (`web/gf_frame.js` + `web/gf_frame_*.js`)

| File | Role |
|------|------|
| `gf_frame.js` | Shell bootstrap, city list, page activation |
| `gf_frame_shared.js` | Shared state, top bar, adapter wiring, project load |
| `gf_frame_map.js` | MapLibre map, layers, legend, tract popups |
| `gf_frame_chat.js` | Query panel, follow-up chat, PDF export trigger |

Project mode uses adapter/plugins for primary metric, choropleth field, legend, and `analysis_model` in chat context.

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
POST /api/projects { "model_id": "lst" }          # auto-created from Ask if needed
POST /api/projects/{id}/cities {"address": "Round Rock, TX"}
  → user uploads files on Ask
POST /api/projects/{id}/cities/{key}/run?model=lst (multipart files)
  → background task: run_model (registry)
  → LST post_process: load_city_layers + enrich_tracts_with_lst
  → manifest updated (model_id, run_stats, lst_stats alias)
GET /api/projects/{id}                            # polled by Ask progress bar
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

- [ADDING_A_MODEL.md](ADDING_A_MODEL.md) — end-to-end guide for new models
- [MODELS.md](MODELS.md) — registered models (LST, OBIA)
- [API.md](API.md) — endpoint reference
- [DATA.md](DATA.md) — folders, caches, external sources
- [DEMO.md](DEMO.md) — stakeholder walkthrough
