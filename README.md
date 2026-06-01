# Geospatial GUI

Web UI (replaces Tkinter) for use in a browser or iframe.

## Run locally

```bash
python serve.py
```

Open http://127.0.0.1:8080/

## Iframe embed

```html
<iframe
  src="http://127.0.0.1:8080/"
  title="Geospatial Dashboard"
  width="100%"
  height="700"
  style="border:0;"
></iframe>
```

When deployed, host the `web/` folder and point the iframe at that URL.
