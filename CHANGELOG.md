# Changelog

All notable changes to this project are documented here.

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
