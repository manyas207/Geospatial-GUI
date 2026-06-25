"""Tract zonal join stub (copy to backend/pipelines/<id>_zonal.py).

See templates/model/ and docs/ADDING_A_MODEL.md § Quick checklist.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask

from backend.core.constants import TRACT_LAYER


def enrich_tracts_with_your_model(
    tract_gdf: gpd.GeoDataFrame,
    raster_tif: Path,
    *,
    out_gpkg: Path,
    out_geojson: Path | None = None,
) -> gpd.GeoDataFrame:
    """Add your_model_mean and your_model_max per tract; write GPKG."""
    raster_tif = Path(raster_tif)
    if not raster_tif.exists():
        raise FileNotFoundError(f"Raster not found: {raster_tif}")

    gdf = tract_gdf.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    means: list[float | None] = []
    maxes: list[float | None] = []

    with rasterio.open(raster_tif) as src:
        gdf_proj = gdf.to_crs(src.crs)
        for geom in gdf_proj.geometry:
            if geom is None or geom.is_empty:
                means.append(None)
                maxes.append(None)
                continue
            try:
                data, _ = mask(src, [geom], crop=True, nodata=np.nan)
                band = data[0].astype("float64")
                valid = band[np.isfinite(band)]
                if valid.size == 0:
                    means.append(None)
                    maxes.append(None)
                else:
                    means.append(round(float(valid.mean()), 3))
                    maxes.append(round(float(valid.max()), 3))
            except (ValueError, rasterio.errors.RasterioError):
                means.append(None)
                maxes.append(None)

    gdf["your_model_mean"] = means
    gdf["your_model_max"] = maxes

    out_gpkg.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_gpkg, driver="GPKG", layer=TRACT_LAYER)

    if out_geojson is not None:
        out_geojson.write_text(gdf.to_json(), encoding="utf-8")

    return gdf
