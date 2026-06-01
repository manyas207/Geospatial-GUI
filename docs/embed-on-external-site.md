# Embedding on another website

## Use the correct URL

| Purpose | URL path | Embed on external site? |
|---------|----------|-------------------------|
| **Dashboard only** | `/embed/dashboard.html` | **Yes** — use this in the parent `<iframe>` |
| **Full workflow (single page)** | `/embed/wizard.html` | **Yes** |
| Dev shell with nested step iframes | `/index.html` | **No** — for local/desktop dev only |

## Parent site example

```html
<iframe
  id="geospatial-dashboard"
  src="https://your-server.example/embed/dashboard.html"
  title="Geospatial analysis dashboard"
  width="100%"
  height="720"
  style="border:0;"
  allow="fullscreen"
></iframe>
```

Replace the `src` host with wherever you serve the `ui/` folder (Python static server, nginx, S3+CloudFront, etc.).

## Send data from the parent page

```javascript
const iframe = document.getElementById("geospatial-dashboard");

iframe.addEventListener("load", () => {
  iframe.contentWindow.postMessage(
    {
      type: "geospatial-gui",
      action: "setData",
      payload: {
        maps: { layers: [] },
        classifications: {},
        model_performance: {},
        summary: { title: "Run 2024-06-01" },
      },
    },
    "https://your-server.example"  // target origin in production
  );
});

window.addEventListener("message", (event) => {
  if (event.data?.type !== "geospatial-gui") return;
  if (event.data.action === "ready") console.log("embed ready", event.data.payload);
  if (event.data.action === "download") console.log("export", event.data.payload);
});
```

## Requirements for cross-site embedding

1. **HTTPS** on both parent and embed origin in production.
2. **CSP `frame-ancestors`** — configured in `app/config/settings.py` (`frame_ancestors`). Restrict to your parent domain in production, e.g. `https://portal.example.com`.
3. **CORS** on the Python API if the iframe calls a different origin than the static files.
4. **No nested iframes** in the embed pages — one document per iframe keeps sizing and security simpler.
5. **Height** — set `height` on the parent `<iframe>`; embed CSS uses `%` / `min-height`, not `100vh`.

## Python backend role

- Serve static `ui/embed/*.html` (this repo’s UI server or any static host).
- Expose REST/RPC for processing; the iframe calls your API or receives data via `postMessage` from the parent.
