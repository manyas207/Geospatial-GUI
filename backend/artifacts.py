"""Build downloadable artifact metadata and secure path tokens for the API.

Artifact IDs are base64-encoded paths relative to data/ — not raw filesystem paths.
decode_artifact_path enforces that resolved files stay inside data_dir.
"""

import base64
from pathlib import Path

from fastapi import HTTPException

from backend.constants import RASTER_SUFFIXES, VECTOR_SUFFIXES
from backend.preview import render_geotiff_preview

# Pipeline stats keys that point at output files (label shown in the download list).
STAT_FILE_KEYS = {
    "geotiff": "LST output map",
    "classified_tif": "Classification map",
    "segments_gpkg": "Segment polygons",
    "classified_gpkg": "Classified polygons",
}

def encode_artifact_path(path: Path, data_dir: Path) -> str:
    """Turn a file under data_dir into an opaque URL-safe token."""
    rel = path.resolve().relative_to(data_dir.resolve())
    token = base64.urlsafe_b64encode(str(rel).encode("utf-8")).decode("utf-8")
    return token.rstrip("=")


def decode_artifact_path(token: str, data_dir: Path) -> Path:
    padding = "=" * (-len(token) % 4)
    try:
        rel = base64.urlsafe_b64decode((token + padding).encode("utf-8")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid artifact id.") from exc

    full = (data_dir / rel).resolve()
    # Block path traversal (e.g. token encoding ../../etc/passwd).
    if not str(full).startswith(str(data_dir.resolve())):
        raise HTTPException(status_code=403, detail="Artifact path not allowed.")
    if not full.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return full


def _collect_paths_from_stats(stats: dict) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    seen: set[str] = set()

    for key, label in STAT_FILE_KEYS.items():
        raw = stats.get(key)
        if not raw:
            continue
        path = Path(str(raw))
        if path.exists() and str(path) not in seen:
            found.append((label, path))
            seen.add(str(path))

    return found


def _scan_results_dir(results_dir: Path) -> list[tuple[str, Path]]:
    if not results_dir.exists():
        return []

    items: list[tuple[str, Path]] = []
    for path in sorted(results_dir.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in RASTER_SUFFIXES or suffix == ".gpkg":
            label = path.stem.replace("_", " ")
            items.append((label, path))
    return items


def build_artifacts(
    stats: dict,
    *,
    model: str,
    results_dir: Path | None,
    data_dir: Path,
) -> list[dict]:
    """Build artifact metadata with preview and download URLs."""
    entries = _collect_paths_from_stats(stats)
    seen = {str(path) for _, path in entries}

    # Also pick up any GeoTIFF/GPKG written directly into the results folder.
    if results_dir:
        for label, path in _scan_results_dir(results_dir):
            key = str(path)
            if key not in seen:
                entries.append((label, path))
                seen.add(key)

    artifacts: list[dict] = []

    for label, path in entries:
        suffix = path.suffix.lower()
        token = encode_artifact_path(path, data_dir)
        item = {
            "id": token,
            "label": label,
            "filename": path.name,
            "kind": "vector" if suffix in VECTOR_SUFFIXES else "geotiff",
            "download_url": f"/api/artifacts/{token}/download",
            "preview_url": None,
        }

        # Raster outputs get a cached PNG for the dashboard map viewer.
        if suffix in RASTER_SUFFIXES:
            preview_path = path.with_name(f"{path.stem}_preview.png")
            if not preview_path.exists():
                try:
                    render_geotiff_preview(path, preview_path, model=model)
                except Exception:
                    preview_path = None

            if preview_path and preview_path.exists():
                preview_token = encode_artifact_path(preview_path, data_dir)
                item["preview_url"] = f"/api/artifacts/{preview_token}/preview"

        artifacts.append(item)

    return artifacts
