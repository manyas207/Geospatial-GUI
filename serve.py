"""Launch the Geospatial Dashboard API and web UI."""

import os
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent


def load_dotenv() -> None:
    """Load KEY=VALUE lines from .env into os.environ (does not override existing vars)."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


WEB_DIR = PROJECT_ROOT / "web"
HOST = "127.0.0.1"
PORT = 8765


def verify_ui_files() -> None:
    """Fail fast if the wrong web/ tree is being served (common when cwd differs)."""
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing {index_path}")

    html = index_path.read_text(encoding="utf-8")
    markers = ('class="brand-title"', 'id="askRunCityLst"', 'id="page-gfframe"', "gf_frame.js")
    if not all(m in html for m in markers):
        raise RuntimeError(
            f"{index_path} looks like the old layout. "
            "Edit files in this project's web/ folder (Geospatial-GUI-1)."
        )

    gf_frame = WEB_DIR / "gf_frame.js"
    if not gf_frame.exists():
        raise FileNotFoundError(f"Missing {gf_frame}")


def main() -> None:
    load_dotenv()
    verify_ui_files()

    url = f"http://{HOST}:{PORT}/"
    print(f"Project: {PROJECT_ROOT.name}")
    print(f"Serving API + web from: {PROJECT_ROOT}")
    print(f"Open: {url}")
    print()
    print("POST /api/projects - multi-city LST portfolio (Ask -> Heat & Equity)")

    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
