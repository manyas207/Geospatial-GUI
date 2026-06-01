"""Serve the web UI for local use and iframe embedding."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"
HOST = "127.0.0.1"
PORT = 8080


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self) -> None:
        # Avoid stale CSS/JS while developing (browser often caches these aggressively).
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()


def main() -> None:
    with ThreadingHTTPServer((HOST, PORT), Handler) as httpd:
        url = f"http://{HOST}:{PORT}/"
        print(f"Serving {WEB_DIR}")
        print(f"Open in browser or iframe: {url}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
