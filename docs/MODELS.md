# Analysis models

The app uses a **plugin registry** so the lab can add geospatial analysis models (LST is the first; OBIA is the second). Users pick a model on the **Ask** tab, upload inputs, and land on a dashboard driven by that model’s outputs.

## Registered models (today)

| Model id | Label | Dashboard | Inputs |
|----------|-------|-----------|--------|
| `lst` | Land Surface Temperature | `equity` | Landsat `ST_B10`, `SR_B4`, `SR_B5` GeoTIFFs |
| `obia` | OBIA Land Cover | `equity` | Multispectral GeoTIFF + training shapefile (`.shp`, `.shx`, `.dbf`; `.prj` recommended) |

List at runtime: `GET /api/models` or http://127.0.0.1:8765/docs

Restart `python serve.py` after adding models or changing `.env` — stale processes may only expose `lst` on `/api/models`.

## Backend plugin contract

Each model is a `ModelSpec` in `models/contract.py`:

| Piece | Purpose |
|-------|---------|
| `input_schema` | Describes uploads (shown on Ask via API) |
| `run(paths, ctx)` | Executes the pipeline → `ModelResult` (stats, logs, artifacts) |
| `post_process(result, ctx)` | Optional tract enrichment → `PostProcessResult` |
| `dashboard` | `equity` (Heat & Equity frame) or `raster` (placeholder shell) |
| `vector_join` | `tract_zonal` or `none` |
| `primary_metric` | Key in `run_stats` for charts and chat |
| `vector_fields` | Fields joined to tract GeoJSON/GPKG |

**Register** in `models/registry.py`:

```python
_MODELS = {
    LST_MODEL.id: LST_MODEL,
    OBIA_MODEL.id: OBIA_MODEL,
}
```

**Run path:** `POST /api/projects/{id}/cities/{key}/run?model={id}` → background task → `backend/projects/dispatch.py` → `backend/projects/service.py` (`run_city_model_upload`).

**Manifest fields** (per city, when ready):

- `model_id` — which analysis model ran
- `run_stats` — normalized pipeline output
- `lst_stats` — alias of `run_stats` for LST (backward compatibility)
- `vector_fields` — tract attributes for map and chat
- `status` — `pending` \| `processing` \| `ready` \| `error`
- `error` — message when `status` is `error`

## Frontend adapter

`web/dashboard_adapter.js` loads `GET /api/models` and merges API metadata with presentation overrides in `PRESENTATION` (labels, choropleth field, units, bar chart titles).

| File | Role |
|------|------|
| `web/app.js` | Model dropdown on Ask, dynamic file hints, async progress bar, `/run?model=…` |
| `web/gf_frame.js` | Dashboard shell, charts, map layer, chat context via adapter |

When adding a model with dashboard type `equity`, add a `PRESENTATION` block in `dashboard_adapter.js` (choropleth field, metric keys, legend labels). Models with `dashboard: "raster"` show a placeholder map shell until a dedicated view is built.

## Checklist: add model #3

1. Implement `models/your_model.py` with `run` and optional `post_process`.
2. Register in `models/registry.py`.
3. Add `PRESENTATION.your_model` in `web/dashboard_adapter.js`.
4. Smoke-test: Ask → upload → run → dashboard → one chat question.
5. Document inputs in this file and [API.md](API.md).

## OBIA (`obia`)

### Pipeline

- Core: `models/obia_core.py` (`run_obia_pipeline`, `run_obia_segmentation_only`)
- Plugin: `models/obia_model.py`
- Tract join: `backend/pipelines/obia_zonal.py` → `obia_mode_class`, `obia_mode_pct`, `obia_segment_count`

Flow: load raster → SLIC segmentation → per-segment features (spectral, shape, indices, optional GLCM texture) → label segments from training ROIs → Random Forest CV + classify scene → export `classified.gpkg` / `classified.tif` → join to census tracts.

### Raster bands

| Band count | Assumed layout |
|------------|----------------|
| 7+ | HLS L30: coastal, blue, green, red, NIR, SWIR1, SWIR2 |
| 4–6 | Blue, green, red, NIR, (+ SWIR…) from band 1 |
| 3 | Red, green, NIR |
| 2 | Red, NIR |
| 1 | Spectral stats only (no indices) |

Indices (NDVI, NDWI, etc.) are computed only when the required bands exist.

### Training shapefile

| Column | Required | Aliases |
|--------|----------|---------|
| Class label | Yes | `macroclass`, `class_id`, `class`, `landcover`, … |
| ROI id | No | `roi_id`, `id`, `fid`, `polygon_id`, … — auto-generated (one id per polygon) if missing |

**Pixel- and point-sized training samples** are supported for proof-of-concept runs: the pipeline buffers tiny polygons, uses `all_touched` rasterization, and labels the segment under each sample centroid.

**US census tracts** are still required for the dashboard map. Register a **US city that matches your raster extent** (`City, ST`). Raster and training data must cover the same geographic area — mismatched city names (e.g. Austin + Brazil data) produce “no labeled segments” or empty tract joins.

Include a `.prj` file so CRS matches the GeoTIFF.

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OBIA_N_SEGMENTS` | `50000` | SLIC segment count (lower = faster, coarser) |
| `OBIA_MIN_CLASS_FRACTION` | `0` | Minimum purity for a labeled segment (`0` = accept any pixel/point sample) |

Example `.env` for a quick POC:

```env
OBIA_N_SEGMENTS=10000
OBIA_MIN_CLASS_FRACTION=0
```

### Common errors

| Error | Likely cause |
|-------|----------------|
| `No labeled segments` | Raster and training ROIs don’t overlap, CRS mismatch, or wrong registered city |
| `'class_id'` / `'roi_id'` | Missing class column — now auto-mapped from aliases |
| `'b7_mean'` | Fixed — pipeline adapts to band count |
| OBIA missing from dropdown | Restart server; kill stale process on port 8765 |
| Long run time | Normal for OBIA (segmentation + GLCM); lower `OBIA_N_SEGMENTS` |

### Segmentation-only mode

If no training shapefile is uploaded, `run_obia_segmentation_only` exports `segments.gpkg` without classification.

## LST (`lst`)

- Core: `models/lst_core.py`, wrapper `models/lst_pipeline.py`, plugin `models/lst_model.py`
- Tract join: `backend/pipelines/lst_zonal.py` → `lst_mean_C`, etc.
- Expects Landsat `ST_B10`, `SR_B4`, `SR_B5` GeoTIFFs per city.

See [ARCHITECTURE.md](ARCHITECTURE.md) for request flows and [API.md](API.md) for endpoints.
