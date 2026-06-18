# Changelog

All notable changes to this project are documented here.

## 2026-06-18 (backend reorganization, OBIA, reports, UI)

### Added

#### Backend layout

Reorganized monolithic `backend/main.py` into a modular package:

- `backend/api/routes/` — `models`, `projects`, `reports`, `city_layers`, `followup`
- `backend/core/` — schemas, constants, uploads, presets, rate limit, JSON helpers
- `backend/projects/` — project storage, model dispatch, cross-city compare
- `backend/layers/` — geocode, census, tracts, orchestrator, map render, WorldPop, tract query
- `backend/chat/` — Ollama client, dashboard Q&A, equity burden
- `backend/pipelines/` — LST zonal join, OBIA zonal join, raster utilities
- `backend/report/` — on-demand PDF report generation (`fpdf2`)
- `backend/config.py` — shared paths (`data/`, projects, city-layers cache)
- `scripts/migrate_backend_layout.py` — one-time import-path migration helper

#### OBIA analysis model

- **`models/obia_model.py`** — plugin wrapper registered as `obia`
- **`models/obia_core.py`** — full pipeline: SLIC segmentation → features → ROI labeling → Random Forest CV → classify → export
- **`backend/pipelines/obia_zonal.py`** — joins OBIA segments to census tracts (`obia_mode_class`, `obia_mode_pct`, `obia_segment_count`)
- **Flexible raster bands** — adapts to 1–7+ bands (HLS layout when ≥7; RGBN-style mapping for fewer)
- **Flexible training columns** — `class_id`, `macroclass`, `class`, etc.; `id` / `roi_id` optional (auto-generated per polygon if missing)
- **Pixel/point training samples** — centroid labeling, tiny-polygon buffering, and `all_touched` rasterization for proof-of-concept ROIs
- **Diagnostic labeling errors** — explains bounds overlap, CRS issues, and fraction-threshold failures
- **Segmentation-only mode** — runs without a training shapefile (exports `segments.gpkg`)
- **Env tuning** — `OBIA_N_SEGMENTS`, `OBIA_MIN_CLASS_FRACTION` (default `0`)

#### API & orchestration

- **`POST /api/projects/{id}/report`** — PDF export with map snapshot, run stats, and recent chat (`backend/report/pdf.py`)
- **Async model runs** — `BackgroundTasks` in `projects.py`; city status `processing` → `ready` / `error`
- **Shapefile uploads** — `.shp`/`.shx`/`.dbf` (and `.prj`) accepted alongside rasters (`backend/core/constants.py`)

#### Frontend

- **Ask tab progress bar** — polls `GET /api/projects/{id}` with per-model step labels (LST vs OBIA) while analysis runs
- **OBIA presentation** — `PRESENTATION.obia` in `web/dashboard_adapter.js` (choropleth, metrics, file hints)
- **Model lock hint** — explains that model cannot change after cities are added; **New project** required to switch models
- **`fetchModels({ force: true })`** — bypasses cached model list on Ask bootstrap
- **Export PDF report** button on project dashboard (`web/gf_frame.js` → `POST /api/projects/{id}/report`)
- **Tract overlap warnings** — map overlay when raster/analysis extent does not match registered US city
- **LST-only scale UI** — temperature legend controls hidden for non-LST models (`web/gf_frame.js`)
- **Ask UI refresh** — expanded layout, portfolio chrome, run-progress styling (`web/app.css`, `web/index.html`)

#### Docs & tooling

- **`serve.py`** — prints registered analysis models on startup; UI file sanity check
- **`models/registry.py`** — safe OBIA import (warns and keeps LST available if OBIA deps fail)
- **Docs** — [MODELS.md](MODELS.md), [ARCHITECTURE.md](ARCHITECTURE.md), [API.md](API.md), [README.md](README.md), [SETUP_WINDOWS.md](SETUP_WINDOWS.md) updated for new layout and OBIA

### Changed

- **`backend/main.py`** — slim app factory; routers only (was ~600 lines of inline routes)
- **Import paths** — e.g. `backend/geocode.py` → `backend/layers/geocode.py`, `backend/project.py` → `backend/projects/service.py`
- **`GET /api/models`** — `Cache-Control: no-store` to avoid stale model list in browser
- **`OBIA_MIN_CLASS_FRACTION`** — default `0` (env-configurable); was `0.5`
- **`requirements.txt`** — added `fpdf2` for PDF reports
- **`.env.example`** — documented `OBIA_N_SEGMENTS`, `OBIA_MIN_CLASS_FRACTION`

### Fixed

- OBIA `KeyError` on `b7_mean` for rasters with fewer than 7 bands
- OBIA `KeyError` on `roi_id` when training shapefile uses `id` only
- OBIA `KeyError` on `macroclass` when training shapefile uses `class_id`
- **Unsupported file type: `.shp`** — shapefile suffixes missing from `ALLOWED_UPLOAD_SUFFIXES`
- Training shapefile missing `.prj` — clearer error; can inherit raster CRS when geometries are naive
- **No labeled segments** — improved diagnostics; pixel/point samples now label segments under centroids
- Model dropdown showing only **LST** when an old server process was still bound to port **8765**
- Stale OBIA model list in browser after server restart

### Removed

- Flat backend modules absorbed into package layout (`backend/dashboard_chat.py` merged into `backend/chat/dashboard.py`, etc.)
- Architecture diagram assets (`docs/ARCHITECTURE_DIAGRAM.md`, `docs/geospatial-dashboard-*.png`)
- ASCII high-level diagram block from [ARCHITECTURE.md](ARCHITECTURE.md)

### Notes

- Dashboard map layers still require **US census tracts** — register a US city (`City, ST`) that matches your raster extent; non-US-only workflows need a future custom-region mode
- OBIA runs can take **several minutes** on large scenes (SLIC + GLCM texture); lower `OBIA_N_SEGMENTS` in `.env` for faster POC runs
- Restart `python serve.py` after code or `.env` changes; kill stale processes on port 8765 if the model list looks wrong

## 2026-06-17 (model platform)

### Added

- **Model plugin contract** — `models/contract.py`, `models/lst_model.py`, `models/registry.py`; LST registered as model id `lst`
- **`GET /api/models`** — lists registered models with `input_schema`, `dashboard`, `primary_metric`
- **`POST /api/projects/{id}/cities/{key}/run?model=`** — generic model run (`/lst` kept as legacy alias)
- **Project manifest** — `model_id`, `run_stats` per city (`lst_stats` retained as alias for LST)
- **Ask tab model picker** — dropdown from API, dynamic file hints, runs via `/run?model=…` (`web/app.js`, `web/dashboard_adapter.js`)
- **Dashboard adapter** — per-model charts, map choropleth, and chat context (`web/dashboard_adapter.js`, `web/gf_frame.js`)
- **`analysis_model`** on `DashboardContext` for follow-up chat
- **Docs** — [docs/MODELS.md](docs/MODELS.md) (lab onboarding guide)

### Changed

- **`backend/project.py`** — `run_city_model_upload()` orchestrates registry dispatch and post-process hooks
- **`backend/router.py`** — `run_model()` dispatches by model id
- **`POST /api/projects`** — optional `model_id` in request body (default `lst`)
- **`backend/city_compare.py`** — reads `run_stats` with `lst_stats` fallback

## 2026-06-17

### Added

- **Nominatim geocode fallback** — when the Census Geocoder returns no match for a `City, ST` address, `backend/geocode.py` queries OpenStreetMap Nominatim, then reverse-geocodes coordinates via Census for county FIPS
- **Clearer geocode errors** — registration failures suggest `City, ST` format (e.g. `Round Rock, TX`)

### Changed

- **Ask tab** — removed preset-city dropdown; users enter a free-text **City address** only (`web/index.html`, `web/app.js`)
- **Dashboard chat** — `context.raster` is sent as `""` instead of `null` so `POST /api/followup` passes Pydantic validation (`web/gf_frame.js`)
- **Chat error display** — validation errors from the API (e.g. `422`) show a readable message instead of a generic "Could not get an answer"

### Fixed

- **Chat 422 errors** — follow-up requests failed when `DashboardContext.raster` was `null`; demo and project modes now send an empty string

## 2025-06-09

### Added

- **Heat & Equity** sidebar tab — 11-city GUI Frame with city list, key query buttons, charts, and LLM chat (`web/gf_frame.js`)
- **City layers API pipeline** — geocode → Census ACS → tract shapefiles → server-rendered map PNGs → WorldPop preview
  - `backend/geocode.py`, `census_api.py`, `tiger_tracts.py`, `city_layers.py`, `map_render.py`, `worldpop_raster.py`
  - `POST /api/city-layers`, map/worldpop preview endpoints
- **Reference layers** on Dashboard — scan `REFERENCE_DATA_DIR` GeoTIFFs (`backend/reference_layers.py`)
  - `GET /api/reference-layers` and preview/download routes
  - Overlap detection on LST/OBIA query results
- **Documentation** — `docs/` folder (architecture, API, data, demo) and this changelog
- **`.env` loading** in `serve.py` on startup

### Changed

- Dashboard map viewer supports reference layers alongside pipeline artifacts
- Heat & Equity map uses server PNG + pan/zoom (no Leaflet)
- TIGER tract boundaries: primary source is cached Census shapefile download (TIGERweb GeoJSON fallback)
- Fifth Heat & Equity stat card: **Avg. density** (replaces Avg. Hispanic %)
- `backend/schemas.py` extended with `ReferenceLayer`, `CityLayersRequest`, `CityLayersResponse`
- `README.md` updated with links to detailed docs

### Notes

- `CENSUS_API_KEY` required for Heat & Equity demographic layers
- 11-city LST temperatures remain demo values until multi-city rasters are integrated
