# Analysis models

The app uses a **plugin registry** so the lab can add geospatial analysis models (LST is the first). Users pick a model on the **Ask** tab, upload inputs, and land on a dashboard driven by that model’s outputs.

## Registered models (today)

| Model id | Label | Dashboard | Inputs |
|----------|-------|-----------|--------|
| `lst` | Land Surface Temperature | `equity` | Landsat `ST_B10`, `SR_B4`, `SR_B5` GeoTIFFs |

List at runtime: `GET /api/models` or http://127.0.0.1:8765/docs

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
    # MY_MODEL.id: MY_MODEL,
}
```

**Run path:** `POST /api/projects/{id}/cities/{key}/run?model={id}` → `backend/router.run_model` → `backend/project.run_city_model_upload`.

**Manifest fields** (per city, when ready):

- `model_id` — which analysis model ran
- `run_stats` — normalized pipeline output
- `lst_stats` — alias of `run_stats` for LST (backward compatibility)
- `vector_fields` — tract attributes for map and chat

## Frontend adapter

`web/dashboard_adapter.js` loads `GET /api/models` and merges API metadata with presentation overrides in `PRESENTATION` (labels, choropleth field, units, bar chart titles).

| File | Role |
|------|------|
| `web/app.js` | Model dropdown on Ask, dynamic file hints, `/run?model=…` |
| `web/gf_frame.js` | Dashboard shell, charts, map layer, chat context via adapter |

When adding a model with dashboard type `equity`, add a `PRESENTATION` block in `dashboard_adapter.js` (choropleth field, metric keys, legend labels). Models with `dashboard: "raster"` show a placeholder map shell until a dedicated view is built.

## Checklist: add model #2

1. Implement `models/your_model.py` with `run` and optional `post_process`.
2. Register in `models/registry.py`.
3. Add `PRESENTATION.your_model` in `web/dashboard_adapter.js`.
4. Smoke-test: Ask → upload → run → dashboard → one chat question.
5. Document inputs in this file and [API.md](API.md).

See [ARCHITECTURE.md](ARCHITECTURE.md) for request flows and [API.md](API.md) for endpoints.
