"""One-shot migration: flatten backend/ -> structured packages. Run once then delete."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

FILE_MOVES = {
    "constants.py": "core/constants.py",
    "json_util.py": "core/json_util.py",
    "rate_limit.py": "core/rate_limit.py",
    "uploads.py": "core/uploads.py",
    "presets.py": "core/presets.py",
    "schemas.py": "core/schemas.py",
    "project.py": "projects/service.py",
    "city_compare.py": "projects/compare.py",
    "router.py": "projects/dispatch.py",
    "city_layers.py": "layers/orchestrator.py",
    "geocode.py": "layers/geocode.py",
    "census_api.py": "layers/census.py",
    "tiger_tracts.py": "layers/tracts.py",
    "map_render.py": "layers/map_render.py",
    "worldpop_raster.py": "layers/worldpop.py",
    "tract_query.py": "layers/tract_query.py",
    "dashboard_chat.py": "chat/dashboard.py",
    "ollama_client.py": "chat/ollama.py",
    "equity_burden.py": "chat/equity_burden.py",
    "lst_zonal.py": "pipelines/lst_zonal.py",
    "raster_util.py": "pipelines/raster_util.py",
    "report.py": "report/pdf.py",
}

IMPORT_REPLACEMENTS = [
    ("from backend.city_compare", "from backend.projects.compare"),
    ("from backend.city_layers", "from backend.layers.orchestrator"),
    ("from backend.census_api", "from backend.layers.census"),
    ("from backend.constants", "from backend.core.constants"),
    ("from backend.dashboard_chat", "from backend.chat.dashboard"),
    ("from backend.equity_burden", "from backend.chat.equity_burden"),
    ("from backend.geocode", "from backend.layers.geocode"),
    ("from backend.json_util", "from backend.core.json_util"),
    ("from backend.lst_zonal", "from backend.pipelines.lst_zonal"),
    ("from backend.map_render", "from backend.layers.map_render"),
    ("from backend.ollama_client", "from backend.chat.ollama"),
    ("from backend.presets", "from backend.core.presets"),
    ("from backend.project", "from backend.projects.service"),
    ("from backend.raster_util", "from backend.pipelines.raster_util"),
    ("from backend.rate_limit", "from backend.core.rate_limit"),
    ("from backend.report", "from backend.report.pdf"),
    ("from backend.router", "from backend.projects.dispatch"),
    ("from backend.schemas", "from backend.core.schemas"),
    ("from backend.tiger_tracts", "from backend.layers.tracts"),
    ("from backend.tract_query", "from backend.layers.tract_query"),
    ("from backend.uploads", "from backend.core.uploads"),
    ("from backend.worldpop_raster", "from backend.layers.worldpop"),
]

DEAD_FILES = ["artifacts.py", "nlu.py", "preview.py", "reference_layers.py"]

PACKAGES = [
    "core",
    "projects",
    "layers",
    "chat",
    "pipelines",
    "report",
    "api",
    "api/routes",
]


def apply_imports(text: str) -> str:
    for old, new in IMPORT_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def main() -> None:
    for pkg in PACKAGES:
        (BACKEND / pkg).mkdir(parents=True, exist_ok=True)
        init = BACKEND / pkg / "__init__.py"
        if not init.exists():
            init.write_text('"""Backend package."""\n', encoding="utf-8")

    for src_rel, dest_rel in FILE_MOVES.items():
        src = BACKEND / src_rel
        dest = BACKEND / dest_rel
        if not src.exists():
            print(f"skip missing {src_rel}")
            continue
        content = apply_imports(src.read_text(encoding="utf-8"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        print(f"moved {src_rel} -> {dest_rel}")

    for name in DEAD_FILES:
        path = BACKEND / name
        if path.exists():
            path.unlink()
            print(f"deleted {name}")

    # Fix service.py: TRACT_LAYER from constants not orchestrator
    service = BACKEND / "projects" / "service.py"
    if service.exists():
        text = service.read_text(encoding="utf-8")
        text = text.replace(
            "from backend.layers.orchestrator import TRACT_LAYER",
            "from backend.core.constants import TRACT_LAYER",
        )
        service.write_text(text, encoding="utf-8")

    # Fix equity_burden TRACT_LAYER import
    equity = BACKEND / "chat" / "equity_burden.py"
    if equity.exists():
        text = equity.read_text(encoding="utf-8")
        text = text.replace(
            "from backend.layers.orchestrator import TRACT_LAYER",
            "from backend.core.constants import TRACT_LAYER",
        )
        equity.write_text(text, encoding="utf-8")

    # Update repo-root files
    for pattern in ["models/*.py", "docs/*.md", "README.md", "scripts/*.py"]:
        for path in ROOT.glob(pattern):
            if path.name == "migrate_backend_layout.py":
                continue
            text = path.read_text(encoding="utf-8")
            updated = apply_imports(text)
            if updated != text:
                path.write_text(updated, encoding="utf-8")
                print(f"updated imports in {path.relative_to(ROOT)}")

    # Remove old flat files (not main.py)
    for src_rel in FILE_MOVES:
        old = BACKEND / src_rel
        if old.exists():
            old.unlink()
            print(f"removed old {src_rel}")

    print("done")


if __name__ == "__main__":
    main()
