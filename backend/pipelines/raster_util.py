"""Raster file selection for LST uploads."""

from __future__ import annotations

from pathlib import Path

import rasterio

from backend.core.constants import RASTER_SUFFIXES


def _band_count(path: Path) -> int:
    try:
        with rasterio.open(path) as src:
            return src.count
    except Exception:
        return 0


def pick_primary_lst_raster(paths: list[Path]) -> Path:
    """Prefer Landsat thermal band; else richest multi-band stack."""
    rasters = [path for path in paths if path.suffix.lower() in RASTER_SUFFIXES]
    if not rasters:
        raise ValueError("At least one GeoTIFF is required for LST.")

    for path in rasters:
        upper = path.name.upper()
        if "ST_B10" in upper or "ST_B11" in upper:
            return path

    multi_band = [path for path in rasters if _band_count(path) >= 3]
    if multi_band:
        return max(multi_band, key=_band_count)
    return rasters[0]
