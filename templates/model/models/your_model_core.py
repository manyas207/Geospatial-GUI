"""Raster → GeoTIFF pipeline stub (copy to models/<id>_core.py).

Example: continuous raster index (NDVI-style) from red + NIR bands.
Replace band indices and math with your model. See templates/model/ and
docs/ADDING_A_MODEL.md § Quick checklist.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio


def compute_your_model(raster_path: str, out_dir: str) -> dict:
    """Run pipeline; return {"stats": {...}, "logs": "..."}."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(raster_path) as src:
        if src.count < 4:
            raise ValueError(
                f"Expected at least 4 bands (red=3, nir=4); got {src.count}. "
                "Adjust band order in your input_schema hint if needed."
            )
        red = src.read(3).astype("float64")
        nir = src.read(4).astype("float64")
        index = (nir - red) / np.maximum(nir + red, 1e-6)

        profile = src.profile.copy()
        profile.update(dtype="float32", count=1, nodata=-9999.0)
        out_tif = out_dir / "your_model.tif"
        with rasterio.open(out_tif, "w", **profile) as dst:
            dst.write(index.astype("float32"), 1)

    valid = index[np.isfinite(index)]
    scene_mean = round(float(valid.mean()), 3) if valid.size else None
    return {
        "stats": {"your_model_scene_mean": scene_mean, "geotiff": str(out_tif)},
        "logs": f"Wrote {out_tif} (CRS {src.crs})",
    }
