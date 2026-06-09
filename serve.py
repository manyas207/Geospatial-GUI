"""Launch the Geospatial Dashboard API and web UI."""

from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
HOST = "127.0.0.1"
PORT = 8765


def verify_ui_files() -> None:
    """Fail fast if the wrong web/ tree is being served (common when cwd differs)."""
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing {index_path}")

    html = index_path.read_text(encoding="utf-8")
    if "brand-title" not in html or 'id="chatThread"' not in html:
        raise RuntimeError(
            f"{index_path} looks like the old layout. "
            "Edit files in this project's web/ folder (Geospatial-GUI-1)."
        )


def main() -> None:
    verify_ui_files()

    url = f"http://{HOST}:{PORT}/"
    print(f"Project: {PROJECT_ROOT.name}")
    print(f"Serving API + web from: {PROJECT_ROOT}")
    print(f"Open: {url}")
    print()
    print("POST /api/query — upload GeoTIFF + natural language question")

    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
