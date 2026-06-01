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
| GUI host | `app/shell/` |

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The shell starts a local HTTP server. For external sites, iframe `http://127.0.0.1:8765/embed/dashboard.html`. Optional: `python main.py` opens the dev shell (`index.html`) in a desktop window.

## Data directories

Runtime paths under `data/` (inputs, processed, outputs) are created on first launch. See `.gitignore`.
