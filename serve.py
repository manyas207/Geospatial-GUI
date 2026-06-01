"""Serve the web UI for local use and iframe embedding."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
HOST = "127.0.0.1"
PORT = 8765


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()


def verify_ui_files() -> None:
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing {index_path}")

    html = index_path.read_text(encoding="utf-8")
    if "brand-title" not in html:
        raise RuntimeError(
            f"{index_path} looks like the old layout. "
            "Edit files in this project's web/ folder (Geospatial-GUI-1)."
        )


def main() -> None:
    verify_ui_files()

    url = f"http://{HOST}:{PORT}/"
    print(f"Project: {PROJECT_ROOT.name}")
    print(f"Serving: {WEB_DIR}")
    print(f"Open: {url}")
    print()
    print("If you still see the gray old UI, you may have another server on port 8080")
    print("(often from Desktop\\Geospatial-GUI). Stop it or ignore it and use the URL above.")

    with ThreadingHTTPServer((HOST, PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
