# Geospatial GUI

## Run locally

Work in **Geospatial-GUI-1** (this folder), not `Desktop\Geospatial-GUI` — that older copy can hold port 8080 with stale files.

Install dependencies and start [Ollama](https://ollama.com/) with a model (e.g. `ollama pull llama3.2`).

```bash
pip install -r requirements.txt
python serve.py
```

Open http://127.0.0.1:8765/

**Workflow:** upload a raster and ask a question on **Ask** → explore the output on an interactive pan/zoom map on **Dashboard**, with metrics and downloads below → ask follow-up questions in the conversation panel (answered by Ollama using the dashboard context).

**Heat & Equity** tab: 11-city GUI Frame with live API layers per city — Census Geocoder → ACS demographics (requires `CENSUS_API_KEY`) → tract boundaries (Census shapefile download, cached) → server-rendered choropleth PNG maps + WorldPop preview. Pan/zoom on the map like the Dashboard (no Leaflet); LLM Q&A via Ollama.

Natural-language routing uses your local Ollama server (`OLLAMA_BASE_URL`, default `http://127.0.0.1:11434`). If Ollama is not running, keyword fallback is used instead. Copy `.env.example` to `.env` to change the model name.

**Gridded population / reference layers:** place GeoTIFFs in a folder and set `REFERENCE_DATA_DIR` (defaults to `Desktop\Gridded Population Data` if present). Layers appear on the **Dashboard** and are auto-added to the map when they overlap an LST/OBIA result.

### Models

- **LST** (`models/lst_core.py`): Upload Landsat `ST_B10`, `SR_B4`, and `SR_B5` together in one request, or a 3-band stack (thermal, red, NIR).
- **OBIA** (`models/obia_core.py`): Upload a multi-band GeoTIFF plus training shapefile components (`.shp`, `.shx`, `.dbf`, and optionally `.prj`) in the same request. Without a valid shapefile, only segmentation runs. Set `OBIA_SAMPLES_PATH` to point at a fixed shapefile if needed.

## Iframe embed

```html
<iframe
  src="http://127.0.0.1:8765/"
  title="Geospatial Dashboard"
  width="100%"
  height="700"
  style="border:0;"
></iframe>
```

When deployed, host the `web/` folder and point the iframe at that URL.
