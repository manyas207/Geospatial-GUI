"""Wrapper around models/obia_core.py for the dashboard API.

If a valid training shapefile (.shp+.shx+.dbf) sits in the upload folder, runs full
classification; otherwise segmentation-only. Outputs go to results/{raster_stem}/.
"""

from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from pathlib import Path

from models.obia_core import run_obia_pipeline, run_obia_segmentation_only

# Cap segments for interactive API runs (full script default is 500000).
API_N_SEGMENTS = int(os.environ.get("OBIA_N_SEGMENTS", "50000"))


def _shapefile_is_valid(shp_path: Path) -> bool:
    stem = shp_path.with_suffix("")
    return shp_path.exists() and stem.with_suffix(".shx").exists() and stem.with_suffix(".dbf").exists()


def _find_samples_shapefile(raster_path: Path) -> Path | None:
    parent = raster_path.parent
    stem = raster_path.stem

    candidates: list[Path] = []
    # Prefer a shapefile named like the raster, then any other .shp in the folder.
    exact = parent / f"{stem}.shp"
    if exact.exists():
        candidates.append(exact)
    candidates.extend(sorted(parent.glob("*.shp")))

    seen: set[str] = set()
    for shp in candidates:
        key = str(shp.resolve())
        if key in seen:
            continue
        seen.add(key)
        if _shapefile_is_valid(shp):
            return shp

    return None


def run_obia(raster_path: str) -> dict:
    path = Path(raster_path)
    if not path.exists():
        raise FileNotFoundError(f"Raster not found: {raster_path}")

    out_dir = path.parent / "results" / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    samples = _find_samples_shapefile(path)
    env_samples = os.environ.get("OBIA_SAMPLES_PATH")
    if env_samples and Path(env_samples).exists():
        samples = Path(env_samples)

    log_buffer = io.StringIO()
    with redirect_stdout(log_buffer):
        if samples is None:
            # No training polygons — unsupervised segmentation only.
            result = run_obia_segmentation_only(
                str(path),
                str(out_dir),
                n_segments=API_N_SEGMENTS,
            )
        else:
            result = run_obia_pipeline(
                str(path),
                str(samples),
                str(out_dir),
                n_segments=API_N_SEGMENTS,
            )

    return {"stats": result.get("stats", {}), "logs": log_buffer.getvalue()}
