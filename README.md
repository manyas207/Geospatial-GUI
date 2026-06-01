# Geospatial GUI

Python geospatial pipeline with a web UI designed for **embedding on other websites** via `<iframe>`. Processing uses open-source Python libraries only—no commercial GIS vendors.

**Embed on your site:** use `ui/embed/dashboard.html` (or `ui/embed/wizard.html`). See [docs/embed-on-external-site.md](docs/embed-on-external-site.md).

`ui/index.html` is a local dev shell with nested iframes — not the URL to put on external sites.

## Workflow → folders

| Step | Folder |
|------|--------|
| User inputs (years, HLS/Landsat/Sentinel, AOI) | `user_inputs/` |
| Preprocessing (stack, clip, cloud mask, mosaic, indices) | `preprocessing/` |
| Analysis selection (pixel / object / DL) | `analysis/` |
| Accuracy assessment | `accuracy/` |
| Dashboard & exports | `dashboard/` |
| HTML UI (embeddable) | `ui/embed/` |
| HTML UI (local dev shell) | `ui/index.html` |
| Python ↔ UI bridge | `api/` |
| Per-request workspaces | `data/jobs/{job_id}/` via `app/jobs/` |
| GUI host | `app/shell/` |

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The shell starts a local HTTP server. For external sites, iframe `http://127.0.0.1:8765/embed/dashboard.html`. Optional: `python main.py` opens the dev shell (`index.html`) in a desktop window.

## Jobs (one folder per request)

Each API request starts with `create_job`, which creates:

```
data/jobs/{job_id}/
  job.json          # status, timestamps, request metadata
  context.json      # pipeline state (paths, sensor, years, …)
  inputs/           # AOI uploads, reference labels
  processed/        # preprocessing outputs
  analysis/         # classification outputs
  accuracy/         # metrics JSON
  dashboard/        # dashboard.json for embed UI
  exports/          # PDF, CSV, GeoPackage
```

Example (Python):

```python
from api.handlers import handle_request

r = handle_request("create_job", {})
job_id = r["job_id"]

handle_request("save_user_inputs", {
    "job_id": job_id,
    "sensor": "sentinel",
    "years": "2020-2022",
})
handle_request("run_preprocessing", {"job_id": job_id})
handle_request("run_analysis", {"job_id": job_id, "methods": ["pixel_based"]})
handle_request("build_dashboard", {"job_id": job_id})
```

Legacy flat dirs `data/inputs`, `data/processed`, `data/outputs` remain for optional shared assets; job work should stay under `data/jobs/`.
