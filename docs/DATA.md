# Data guide

Where data lives, how it flows in, and what gets cached.

## Directory layout

```
Geospatial-GUI-1/
├── data/
│   ├── projects/{project_id}/   # Multi-city LST portfolios
│   │   ├── manifest.json
│   │   └── cities/{city_key}/
│   │       ├── uploads/         # Landsat GeoTIFFs
│   │       ├── tracts.gpkg      # Census + lst_mean_C per tract
│   │       └── tracts.geojson
│   └── city_layers_cache/       # Heat & Equity cached downloads
│       ├── tiger/               # State tract shapefiles (.zip)
│       ├── gpkg/                # Per-city tract GeoPackages
│       ├── geojson/
│       ├── demo_snapshots/      # Cached demo city payloads
│       └── maps/                # Optional choropleth PNGs
├── web/                         # Static frontend (not user data)
└── models/                      # LST pipeline code (not user data)
```

`data/` is gitignored. Do not commit large rasters or API keys.

---

## Data by feature

### Ask tab — project uploads

| Item | Location | Format | Source |
|------|----------|--------|--------|
| Landsat bands | `data/projects/{id}/cities/{key}/uploads/` | GeoTIFF | User browser upload |
| LST output | Pipeline temp under uploads | GeoTIFF | `models/lst_pipeline.py` |
| Enriched tracts | `tracts.gpkg`, `tracts.geojson` | Vector | `backend/lst_zonal.py` |

LST expects Landsat Collection 2 bands (`ST_B10`, `SR_B4`, `SR_B5`) in one request.

**City addresses on Ask:** enter a free-text US address in `City, ST` form (e.g. `Round Rock, TX`). The Ask tab no longer uses a preset-city dropdown.

### Heat & Equity — live APIs

| Step | Module | External source | Cached? |
|------|--------|-----------------|---------|
| Geocode | `geocode.py` | [Census Geocoder](https://geocoding.geo.census.gov/) → [Nominatim](https://nominatim.openstreetmap.org/) (fallback) → demo city centroids | No |
| Tract boundaries | `tiger_tracts.py` | [Census TIGER shapefiles](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | Yes — `data/city_layers_cache/tiger/` |
| Demographics | `census_api.py` | [Census ACS API](https://api.census.gov/data/) | No (merged in memory) |
| Map images | `map_render.py` | — (server render) | Yes — `data/city_layers_cache/maps/` |
| Gridded population | `worldpop_raster.py` | [WorldPop USA 2020 COG](https://www.worldpop.org/) | Yes — PNG in `city_layers_cache/` |

**ACS variables used (tract level):**

| Variable | Meaning |
|----------|---------|
| `B19013_001E` | Median household income |
| `B01003_001E` | Total population |
| `B03002_012E` | Hispanic or Latino population |
| `B03002_004E` | Black alone population |

Derived fields: `hispanic_pct`, `black_pct`, `population_density_per_km2` (from tract land area).

### Geocoding (`backend/geocode.py`)

Used when registering a project city (`POST /api/projects/{id}/cities`) and loading city layers (`POST /api/city-layers`):

1. **Census Geocoder** — one-line address and locations API (works well for street addresses)
2. **Nominatim** (OpenStreetMap) — fallback for `City, ST` place names when Census returns no match
3. **Demo centroids** — hardcoded lat/lon for the 11 preset cities in `CITY_CENTROIDS`
4. **Census reverse geocode** — coordinates → county FIPS for steps 2–3

Addresses should use **City, ST** format (e.g. `Round Rock, TX`). Typos and missing state typically return `400 Could not geocode address`.

---

## Configuration (`.env`)

Copy `.env.example` to `.env`. `serve.py` loads `.env` on startup (existing shell variables are not overwritten).

| Variable | Required | Purpose |
|----------|----------|---------|
| `CENSUS_API_KEY` | **Yes** for Heat & Equity | ACS tract demographics |
| `OLLAMA_BASE_URL` | No (default `http://127.0.0.1:11434`) | Local LLM |
| `OLLAMA_MODEL` | No (default `llama3.2`) | Model name |
| `OLLAMA_ENABLED` | No (default `true`) | Set `false` to disable chat LLM |
| `CITY_LAYERS_RENDER_PNG` | No (default `false`) | Server-side map PNGs |
| `CHAT_RATE_LIMIT_MAX` | No (default `15`) | Max follow-up chat requests per IP per window |
| `CHAT_RATE_LIMIT_WINDOW` | No (default `60`) | Rate-limit window in seconds |
| `CHAT_MAX_QUESTION_LENGTH` | No (default `2000`) | Max characters per chat question |

Get a Census key: https://api.census.gov/data/key_signup.html

---

## Cache behavior

### First city load in a state

Downloading `tl_2023_{state}_tract.zip` can take **10–30 seconds** (~20–40 MB per state). Subsequent cities in the same state reuse the zip.

### Demo portfolio

`GET /api/city-layers/demo-portfolio?warm=true` caches full city payloads under `data/city_layers_cache/demo_snapshots/`.

### Clearing caches

```bash
# Windows PowerShell — remove all city-layer caches
Remove-Item -Recurse -Force data\city_layers_cache
```

---

## External API dependencies

| API | Key? | Used when |
|-----|------|-----------|
| Census Geocoder | No | City registration and city-layers (street addresses; city-only names often miss) |
| OpenStreetMap Nominatim | No | Geocode fallback for `City, ST` addresses when Census returns no match |
| Census ACS | Yes (`CENSUS_API_KEY`) | City-layers and demo portfolio |
| Census TIGER shapefiles | No | First request per state |
| WorldPop COG (HTTPS) | No | WorldPop layer toggle |
| Ollama | No (local) | Dashboard chat |

---

## Known data limitations

1. **One county per city** — geocoding uses city centroid → one county (e.g. Atlanta → Fulton only). Use `City, ST` format; typos and missing state often fail geocoding.
2. **Demo LST values** — 11-city temperatures come from `backend/presets.py` (placeholders, not satellite data).
3. **Project mode** — per-tract `lst_mean_C` comes from uploaded Landsat rasters.

---

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — how modules connect
- [API.md](API.md) — endpoints
- [DEMO.md](DEMO.md) — how to present the data live
