"""Wrapper around models/lst_core.py for the dashboard API.

Resolves Landsat scene bands from separate ST_B10/SR_B4/SR_B5 files in the upload
folder, or splits a multi-band stack into single-band temp files for lst_core.
"""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path

import rasterio

from models.lst_core import run_lst_pipeline

# Landsat Collection 2 scene id embedded in standard product filenames.
LANDSAT_SCENE_RE = re.compile(r"(LC\d{2}_L2SP_\d+_\d+_\d+_\d+_T\d+)", re.I)


def _find_landsat_scene_bands(path: Path) -> dict[str, str] | None:
    match = LANDSAT_SCENE_RE.search(path.name)
    if not match:
        return None

    scene_key = match.group(1)
    bands: dict[str, str] = {}

    for candidate in path.parent.iterdir():
        if not candidate.is_file():
            continue
        if scene_key not in candidate.name:
            continue
        upper = candidate.name.upper()
        if "ST_B10" in upper or "ST_B11" in upper:
            bands["b10"] = str(candidate)
        elif "SR_B4" in upper or "_B4." in upper:
            bands["b04"] = str(candidate)
        elif "SR_B5" in upper or "_B5." in upper:
            bands["b05"] = str(candidate)

    if {"b10", "b04", "b05"} <= bands.keys():
        return bands
    return None


def _scene_from_multiband_stack(path: Path) -> dict:
    with rasterio.open(path) as src:
        count = src.count
        if count < 3:
            raise ValueError(
                "LST requires thermal (B10), red (B4), and NIR (B5). "
                "Upload a Landsat ST_B10 GeoTIFF with SR_B4 and SR_B5 in the same folder, "
                "or a multi-band stack with at least 3 bands."
            )

        tmp_dir = path.parent / f"_lst_bands_{path.stem}"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        # Band order matches lst_core expectations for 3-band vs HLS/Landsat stacks.
        if count == 3:
            band_map = {"b10": 1, "b04": 2, "b05": 3}
            product = "landsat_c2"
        elif count >= 10:
            band_map = {"b10": 10, "b04": 4, "b05": 5}
            product = "hls" if "HLS" in path.name.upper() else "landsat_c2"
        elif count >= 5:
            raise ValueError(
                "Stack has red/NIR bands but no thermal band at index 10. "
                "Upload Landsat ST_B10 with SR_B4 and SR_B5, or a 10+ band stack."
            )
        else:
            raise ValueError(
                f"Unsupported band count ({count}). Need 3 bands (thermal, red, NIR) or 10+ bands."
            )

        profile = src.profile.copy()
        profile.update(count=1)
        paths: dict[str, str] = {}

        for key, band_index in band_map.items():
            out_path = tmp_dir / f"{key}.tif"
            if not out_path.exists():
                with rasterio.open(out_path, "w", **profile) as dst:
                    dst.write(src.read(band_index), 1)
            paths[key] = str(out_path)

    return {
        "label": path.stem,
        "product": product,
        "ref_temps_C": [],
        **paths,
    }


def resolve_lst_scene(raster_path: str) -> dict:
    path = Path(raster_path)
    if not path.exists():
        raise FileNotFoundError(f"Raster not found: {raster_path}")

    landsat_bands = _find_landsat_scene_bands(path)
    if landsat_bands:
        return {
            "label": path.stem,
            "ref_temps_C": [],
            **landsat_bands,
        }

    return _scene_from_multiband_stack(path)


def run_lst(raster_path: str) -> dict:
    path = Path(raster_path)
    out_dir = path.parent / "results" / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    # Capture lst_core print output for the dashboard logs panel.
    log_buffer = io.StringIO()
    with redirect_stdout(log_buffer):
        cfg = resolve_lst_scene(raster_path)
        result = run_lst_pipeline(
            cfg,
            export_tif=True,
            verbose=False,
            output_dir=out_dir,
        )

    valid = result.lst_valid_1d
    stats = {
        "min_C": round(float(valid.min()), 2),
        "max_C": round(float(valid.max()), 2),
        "mean_C": round(float(valid.mean()), 2),
        "median_C": round(float(result.median_lst_C), 2),
        "pixel_count": int(valid.size),
    }
    if result.geotiff_path:
        stats["geotiff"] = str(result.geotiff_path)

    return {"stats": stats, "logs": log_buffer.getvalue()}
