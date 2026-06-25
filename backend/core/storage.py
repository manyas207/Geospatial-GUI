"""Disk cleanup helpers for project city folders."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_ARTIFACT_PATH_KEYS = (
    "geotiff",
    "classified_gpkg",
    "classified_tif",
    "segments_gpkg",
    "validation_gpkg",
)


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def keep_uploads_after_run() -> bool:
    """When false (default), delete raw uploads after a successful model run."""
    return _env_bool("KEEP_UPLOADS_AFTER_RUN", default=False)


def keep_intermediate_artifacts() -> bool:
    """When false (default), delete LST results/ and obia_output/ after success."""
    return _env_bool("KEEP_INTERMEDIATE_ARTIFACTS", default=False)


def scrub_artifact_paths(stats: dict) -> dict:
    """Remove on-disk artifact paths from persisted run_stats."""
    cleaned = dict(stats)
    for key in _ARTIFACT_PATH_KEYS:
        cleaned.pop(key, None)
    return cleaned


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def cleanup_city_after_success(
    city_dir: Path,
    *,
    model_id: str,
    keep_uploads: bool | None = None,
    keep_intermediates: bool | None = None,
) -> None:
    """Free disk after tract enrichment; keeps tracts.gpkg and manifest stats."""
    keep_uploads = keep_uploads_after_run() if keep_uploads is None else keep_uploads
    keep_intermediates = (
        keep_intermediate_artifacts() if keep_intermediates is None else keep_intermediates
    )

    uploads_dir = city_dir / "uploads"
    if not keep_uploads and uploads_dir.exists():
        shutil.rmtree(uploads_dir, ignore_errors=True)

    if not keep_intermediates:
        if model_id == "lst":
            results_dir = city_dir / "uploads" / "results"
            _remove_path(results_dir)
        elif model_id == "obia":
            _remove_path(city_dir / "obia_output")

    # Legacy duplicate vector export (GeoJSON is served from GPKG on demand).
    _remove_path(city_dir / "tracts.geojson")
