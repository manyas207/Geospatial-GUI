"""Join LST GeoTIFF values to census tract polygons (zonal mean/max)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask

from backend.core.constants import TRACT_LAYER
from backend.core.json_util import to_json_safe


def enrich_tracts_with_lst(
    tract_gdf: gpd.GeoDataFrame,
    lst_tif: Path,
    *,
    out_gpkg: Path,
    out_geojson: Path | None = None,
) -> gpd.GeoDataFrame:
    """Add lst_mean_C and lst_max_C per tract; write GPKG (+ optional GeoJSON)."""
    lst_tif = Path(lst_tif)
    if not lst_tif.exists():
        raise FileNotFoundError(f"LST raster not found: {lst_tif}")

    gdf = tract_gdf.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    means: list[float | None] = []
    maxes: list[float | None] = []

    with rasterio.open(lst_tif) as src:
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
                    means.append(round(float(valid.mean()), 2))
                    maxes.append(round(float(valid.max()), 2))
            except (ValueError, rasterio.errors.RasterioError):
                means.append(None)
                maxes.append(None)

    gdf["lst_mean_C"] = means
    gdf["lst_max_C"] = maxes

    out_gpkg.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_gpkg, driver="GPKG", layer=TRACT_LAYER)

    if out_geojson is not None:
        out_geojson.write_text(gdf.to_json(), encoding="utf-8")

    return gdf
