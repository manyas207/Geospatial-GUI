# Changelog

All notable changes to this project are documented here.

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
