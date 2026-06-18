# Geospatial GUI

Terminal-launched web dashboard for **pluggable geospatial analysis models** (LST is the first), multi-city projects, and the **Heat & Equity** GUI Frame with live census and population layers.

Users choose a model on **Ask**, upload inputs, run analysis, and explore results on an adapter-driven dashboard with optional LLM chat.

**New to Python on Windows?** See the step-by-step beginner guide: [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) (download from GitHub, install Python, run the site).

## Prerequisites

- **Python 3.10+** with `pip`
- **Git** (to clone the repo)
- **Census API key** (free) for Heat & Equity demographics — [sign up](https://api.census.gov/data/key_signup.html)
- **Ollama** (optional) for dashboard chat — [ollama.com](https://ollama.com/)

## Step-by-step: run the website

### 1. Get the code

```bash
git clone <your-repo-url>
cd Geospatial-GUI-1
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

**Windows (PowerShell / CMD):**

```bash
copy .env.example .env
```

**macOS / Linux:**

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
CENSUS_API_KEY=your_census_api_key_here
```

### 4. Start the app

```bash
python serve.py
```

You should see:

```text
Open: http://127.0.0.1:8765/
```

Open that URL in your browser. The API docs are at http://127.0.0.1:8765/docs

### 5. Use the app

| Tab | What to do |
|-----|------------|
| **Ask** | Choose an **analysis model** (LST or OBIA), enter a US city as `City, ST`, upload required files, run analysis (progress bar while processing) |
| **Demo** | Open the 11-city Heat & Equity preview (no uploads needed) |
| **Your project** | Appears after your first city finishes processing |

**Ask → Your project:** pick a model → upload inputs → after the run completes you are taken to the dashboard with per-tract results (e.g. `lst_mean_C` for LST, `obia_mode_class` for OBIA).

Restart `python serve.py` after pulling code changes (`serve.py` does not auto-reload). Hard-refresh the browser (`Ctrl+Shift+R`) if the UI looks stale.

---

## Ollama for dashboard chat

Chat on the **Demo** and **Your project** tabs calls Ollama from the **Python backend** (not from the browser). The backend reads `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from `.env`.

### Option A — Ollama on the same computer as the website

1. Install Ollama from https://ollama.com/
2. Pull the model (match `.env` or change `OLLAMA_MODEL`):

   ```bash
   ollama pull llama3.2
   ```

3. Start Ollama (the desktop app does this automatically on Windows/macOS). Or run:

   ```bash
   ollama serve
   ```

4. In `.env`, leave the defaults:

   ```env
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   OLLAMA_MODEL=llama3.2
   ```

5. Restart `python serve.py` if it was already running, then open **Demo** or **Your project** and use the chat panel.

### Option B — Ollama on a different computer (e.g. a GPU machine)

Use this when the web app runs on one laptop but you want inference on another box on the same network.

**On the Ollama machine** (call its LAN IP `192.168.1.50` in the examples below):

1. Install Ollama and pull the model:

   ```bash
   ollama pull llama3.2
   ```

2. Allow network access. By default Ollama only listens on `127.0.0.1`. Set `OLLAMA_HOST` so other machines can connect:

   **Windows (PowerShell, current session):**

   ```powershell
   $env:OLLAMA_HOST = "0.0.0.0:11434"
   ollama serve
   ```

   **macOS / Linux:**

   ```bash
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   ```

   To make this permanent, set `OLLAMA_HOST=0.0.0.0` in the Ollama machine’s environment (Windows: System Environment Variables; Linux: systemd unit or shell profile).

3. Open firewall port **11434** on the Ollama machine (Windows Defender Firewall → inbound rule for TCP 11434, or equivalent).

4. Test from the **website machine**:

   ```bash
   curl http://192.168.1.50:11434/api/tags
   ```

   You should get JSON listing installed models.

**On the website machine** (where you run `python serve.py`):

1. Edit `.env`:

   ```env
   OLLAMA_BASE_URL=http://192.168.1.50:11434
   OLLAMA_MODEL=llama3.2
   OLLAMA_TIMEOUT=120
   ```

   Use the Ollama machine’s real IP or hostname. Increase `OLLAMA_TIMEOUT` if the remote GPU is slow.

2. Restart the app:

   ```bash
   python serve.py
   ```

3. Open the dashboard and send a chat message. If Ollama is unreachable, the backend still returns a short stat summary instead of an LLM answer.

**Security:** exposing Ollama on `0.0.0.0` is fine on a trusted home/lab LAN only. Do not expose port 11434 to the public internet without authentication.

### Chat without Ollama

Maps, uploads, and LST still work without Ollama. Chat falls back to a basic summary of dashboard stats when the LLM is unavailable.

---

## Configuration reference

Copy `.env.example` to `.env`. Key variables:

| Variable | Required | Purpose |
|----------|----------|---------|
| `CENSUS_API_KEY` | For Heat & Equity | [Free Census API key](https://api.census.gov/data/key_signup.html) |
| `OLLAMA_BASE_URL` | No | Ollama server URL (default `http://127.0.0.1:11434`; use `http://<remote-ip>:11434` for Option B) |
| `OLLAMA_MODEL` | No | Model name (default `llama3.2`) |
| `OLLAMA_TIMEOUT` | No | Seconds to wait for Ollama (default `60`; raise for remote GPUs) |
| `CHAT_RATE_LIMIT_MAX` | No | Max chat requests per IP per window (default 15) |
| `CHAT_RATE_LIMIT_WINDOW` | No | Rate-limit window in seconds (default 60) |
| `OBIA_N_SEGMENTS` | No | SLIC segment count for OBIA web runs (default `50000`; lower = faster) |
| `OBIA_MIN_CLASS_FRACTION` | No | Labeled-segment purity threshold (default `0`; pixel samples OK) |

See [docs/DATA.md](docs/DATA.md) and [docs/MODELS.md](docs/MODELS.md) for full details.

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| Port 8765 already in use | Stop the other process or change `PORT` in `serve.py` |
| Demographics show `—` | Set `CENSUS_API_KEY` in `.env` and restart `serve.py` |
| Could not geocode address | Use `City, ST` (e.g. `Round Rock, TX`) |
| Chat not using LLM | Check `curl <OLLAMA_BASE_URL>/api/tags`; verify firewall and `OLLAMA_HOST` on the Ollama machine |
| Stale UI after git pull | Hard-refresh the browser (`Ctrl+Shift+R`) |
| `GET /api/models` returns 404 | Restart `python serve.py` (old process still running) |
| Cannot change model on Ask | Model is locked once a project has cities — click **New project** |
| OBIA not in model list | Kill process on port 8765, restart `python serve.py`, hard-refresh browser |
| OBIA “No labeled segments” | Raster and training shapefile must overlap; use a US city matching your data extent |
| OBIA run very slow | Lower `OBIA_N_SEGMENTS` in `.env`; OBIA can take many minutes on large scenes |

## Project layout

```
Geospatial-GUI-1/
├── serve.py              # Entry point: python serve.py
├── backend/              # FastAPI routes and API clients
├── models/               # Analysis model plugins (contract, registry, lst_model, …)
├── web/                  # Static frontend (HTML, CSS, JS)
│   ├── dashboard_adapter.js  # Model list + per-model dashboard presentation
│   ├── app.js            # Ask tab (model picker, uploads)
│   ├── gf_frame.js       # Heat & Equity dashboard
│   └── vendor/maplibre-gl/
├── data/                 # Uploads and caches (gitignored)
└── docs/                 # Architecture, API, models, data, demo guides
```

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and module map |
| [docs/MODELS.md](docs/MODELS.md) | Model plugin contract and lab onboarding |
| [docs/API.md](docs/API.md) | REST endpoint reference |
| [docs/DATA.md](docs/DATA.md) | Data folders, caches, external APIs |
| [docs/DEMO.md](docs/DEMO.md) | Stakeholder demo walkthrough |
| [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) | Beginner Windows setup (GitHub ZIP → browser) |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

Interactive API docs: http://127.0.0.1:8765/docs

## Analysis models

Registered models are listed at `GET /api/models`. The Ask tab loads this list and calls `POST .../run?model={id}`.

| Model | Inputs |
|-------|--------|
| **LST** (`lst`) | Landsat `ST_B10`, `SR_B4`, and `SR_B5` GeoTIFFs per city |
| **OBIA** (`obia`) | Multispectral GeoTIFF + training shapefile (`.shp`, `.shx`, `.dbf`; class column such as `class_id`) |

To add a new lab model, see [docs/MODELS.md](docs/MODELS.md).

Enter each city as **City, ST** on the Ask tab (e.g. `Round Rock, TX`). Geocoding uses Census, then OpenStreetMap Nominatim as a fallback.

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
