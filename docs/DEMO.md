# Demo walkthrough

Stakeholder-friendly script for presenting the Geospatial GUI locally.

## Before you start

1. From **Geospatial-GUI-1** (not the older `Geospatial-GUI` folder):

   ```bash
   pip install -r requirements.txt
   copy .env.example .env
   ```

2. Set `CENSUS_API_KEY` in `.env` ([free signup](https://api.census.gov/data/key_signup.html)).

3. Optional but recommended — Ollama for dashboard chat:

   ```bash
   ollama pull llama3.2
   ollama serve
   ```

4. Start the app:

   ```bash
   python serve.py
   ```

   Open **http://127.0.0.1:8765/**

   After code updates, restart `serve.py` and hard-refresh the browser (`Ctrl+Shift+R`).

## Ask → Heat & Equity (production)

1. Open **Ask** (the only nav item until you have processed data).
2. Select **Land Surface Temperature** in the **Analysis model** dropdown (only model today; list comes from `GET /api/models`).
3. Enter a US city address in **City, ST** form (e.g. `Round Rock, TX`).
4. Upload Landsat GeoTIFFs (`ST_B10`, `SR_B4`, `SR_B5`) — file hints update per model.
5. Click **Add city to project**, then **Run LST for city**. You are **redirected automatically** to **Your project** when the run completes.
6. Explore maps, charts, and chat. Use **Back to Ask** to upload another city.
7. **New project** clears the portfolio and returns you to Ask (required to switch analysis models).

**Talking points:** Pluggable model platform (LST first); real per-tract LST from uploads; live Census ACS; cross-city comparison in chat when ≥2 cities are ready.

## Demo mode (11 cities)

1. Click **Demo** in the sidebar (always available).
2. Explore placeholder LST bar charts and live Census tract maps for any preset city.
3. Use suggested chat prompts for cross-city comparisons.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Heat & Equity nav missing | Run analysis for at least one city on **Ask** first |
| Model dropdown empty | Restart `serve.py`; check `GET /api/models` in browser or `/docs` |
| Could not geocode address | Use `City, ST` (e.g. `Round Rock, TX`); fix typos; include state for ambiguous names |
| Chat says "Could not get an answer" | Hard-refresh the page; if it persists, check server logs for `422` on `/api/followup` |
| Demographics show dashes | Set `CENSUS_API_KEY` in `.env` and restart `serve.py` |
| Chat says Ollama unavailable | Start `ollama serve` (fallback stat summary is still returned) |
| "Too many chat requests" | Wait for the rate-limit window (see `CHAT_RATE_LIMIT_*` in `.env`) |
| Project city stuck on `processing` | Check server logs; confirm GeoTIFF band names include `ST_B10` for LST |
| Cannot change analysis model | Click **New project** — model locks once cities are registered |
| Wrong or stale UI | Hard-refresh after updates (`Ctrl+Shift+R`); restart `serve.py` after git pull |

## API reference

Interactive docs: http://127.0.0.1:8765/docs

See also [API.md](API.md), [MODELS.md](MODELS.md), and [DATA.md](DATA.md).
