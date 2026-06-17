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

## Ask → Heat & Equity (production)

1. Open **Ask** (the only nav item until you have processed data).
2. Enter a US city address in **City, ST** form (e.g. `Round Rock, TX`), add Landsat GeoTIFFs (`ST_B10`, `SR_B4`, `SR_B5`).
3. Click **Add city to project**, then **Run LST for city**. You are **redirected automatically** to **Heat & Equity** when LST completes.
4. Explore maps, charts, and chat. Use **Back to Ask** to upload another city.
5. **New project** clears the portfolio and returns you to Ask.

**Talking points:** Real per-tract LST from your uploads, live Census ACS, cross-city comparison in chat when ≥2 cities are ready.

## Demo mode (11 cities)

1. Click **Demo** in the sidebar (always available).
2. Explore placeholder LST bar charts and live Census tract maps for any preset city.
3. Use suggested chat prompts for cross-city comparisons.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Heat & Equity nav missing | Upload and run LST for at least one city on **Ask** first |
| Could not geocode address | Use `City, ST` (e.g. `Round Rock, TX`); fix typos; include state for ambiguous names |
| Chat says "Could not get an answer" | Hard-refresh the page; if it persists, check server logs for `422` on `/api/followup` |
| Demographics show dashes | Set `CENSUS_API_KEY` in `.env` and restart `serve.py` |
| Chat says Ollama unavailable | Start `ollama serve` or set `OLLAMA_ENABLED=false` (fallback stat summary is still returned) |
| "Too many chat requests" | Wait for the rate-limit window (see `CHAT_RATE_LIMIT_*` in `.env`) |
| Project city stuck on `processing` | Check server logs; confirm GeoTIFF band names include `ST_B10` |
| Wrong or stale UI | Hard-refresh after updates (`Ctrl+Shift+R`) |

## API reference

Interactive docs: http://127.0.0.1:8765/docs

See also [API.md](API.md) and [DATA.md](DATA.md).
