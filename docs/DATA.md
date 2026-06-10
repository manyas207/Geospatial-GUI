# Data guide

Where data lives, how it flows in, and what gets cached.

## Directory layout

```
Geospatial-GUI-1/
├── data/
│   ├── {upload_uuid}/          # Per-request uploads from Ask tab
│   │   ├── *.tif               # Uploaded rasters
│   │   └── results/{stem}/     # LST/OBIA pipeline outputs
│   ├── reference_previews/     # PNG previews of REFERENCE_DATA_DIR GeoTIFFs
│   └── city_layers_cache/      # Heat & Equity cached downloads
│       ├── tiger/              # State tract shapefiles (.zip)
│       └── maps/               # Choropleth PNGs per city/layer
├── web/                        # Static frontend (not user data)
└── models/                     # Analysis code (not user data)
```

`data/` is gitignored for uploads and caches in normal use. Do not commit large rasters or API keys.

---

## Data by feature

### Ask tab — user uploads

| Item | Location | Format | Source |
|------|----------|--------|--------|
| Uploaded rasters | `data/{uuid}/` | GeoTIFF | User browser upload |
| Shapefile parts (OBIA) | Same folder | `.shp`, `.shx`, `.dbf`, `.prj` | User upload |
| LST output | `data/{uuid}/results/{stem}/` | GeoTIFF + `_preview.png` | `models/lst_pipeline.py` |
| OBIA output | Same | `.gpkg`, optional GeoTIFF | `models/obia_pipeline.py` |

LST expects Landsat Collection 2 bands (`ST_B10`, `SR_B4`, `SR_B5`) in one request, or a 3+ band stack.

### Dashboard — reference layers

| Item | Location | Format | Source |
|------|----------|--------|--------|
| Reference GeoTIFFs | `REFERENCE_DATA_DIR` (external) | `.tif` | User-provided folder |
| Previews | `data/reference_previews/` | PNG | Generated on first scan |

**Configure:**

```env
REFERENCE_DATA_DIR=C:\path\to\your\GeoTIFFs
```

If unset, the app checks `Desktop\Gridded Population Data` when that folder exists.

Layers with `pop`, `density`, `census`, or `grid` in the filename get a population-style colormap.

### Heat & Equity — live APIs

| Step | Module | External source | Cached? |
|------|--------|-----------------|---------|
| Geocode | `geocode.py` | [Census Geocoder](https://geocoding.geo.census.gov/) | No |
| Tract boundaries | `tiger_tracts.py` | [Census TIGER shapefiles](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | Yes — `data/city_layers_cache/tiger/tl_2023_{state}_tract.zip` |
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
| (+ others for ethnicity breakdown) |

Derived fields: `hispanic_pct`, `black_pct`, `population_density_per_km2` (from tract land area).

---

## Configuration (`.env`)

Copy `.env.example` to `.env`. `serve.py` loads `.env` on startup (existing shell variables are not overwritten).

| Variable | Required | Purpose |
|----------|----------|---------|
| `CENSUS_API_KEY` | **Yes** for Heat & Equity | ACS tract demographics |
| `OLLAMA_BASE_URL` | No (default `http://127.0.0.1:11434`) | Local LLM |
| `OLLAMA_MODEL` | No (default `llama3.2`) | Model name |
| `OLLAMA_ENABLED` | No (default `true`) | Set `false` for keyword-only routing |
| `REFERENCE_DATA_DIR` | No | Reference GeoTIFF folder |
| `EARTHDATA_API_KEY` | No | Reserved for future NASA SEDAC/GPW |

Get a Census key: https://api.census.gov/data/key_signup.html

---

## Cache behavior

### First city load in a state

Downloading `tl_2023_{state}_tract.zip` can take **10–30 seconds** (~20–40 MB per state). Subsequent cities in the same state reuse the zip.

### Map previews

PNG choropleths are keyed by city address + layer id. Delete `data/city_layers_cache/maps/` to force regeneration.

### Clearing caches

```bash
# Windows PowerShell — remove all city-layer caches
Remove-Item -Recurse -Force data\city_layers_cache

# Reference previews only
Remove-Item -Recurse -Force data\reference_previews
```

---

## External API dependencies

| API | Key? | Used when |
|-----|------|-----------|
| Census Geocoder | No | Every `/api/city-layers` request |
| Census ACS | Yes (`CENSUS_API_KEY`) | Every `/api/city-layers` request |
| Census TIGER shapefiles | No | First request per state |
| WorldPop COG (HTTPS) | No | WorldPop layer toggle |
| Ollama | No (local) | Ask routing, Dashboard/HE chat |

---

## Known data limitations

1. **One county per city** — geocoding uses city centroid → one county (e.g. Atlanta → Fulton only).
2. **Demo LST values** — 11-city temperatures in `gf_frame.js` are placeholders, not from satellite data.
3. **Reference folder naming** — `Gridded Population Data` may contain non-population rasters (e.g. ASTER bands); the scanner still lists any GeoTIFF.

---

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — how modules connect
- [API.md](API.md) — endpoints
- [DEMO.md](DEMO.md) — how to present the data live
