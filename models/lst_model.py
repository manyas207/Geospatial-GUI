"""LST model plugin — Landsat thermal + red/NIR bands → tract zonal stats."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from backend.city_layers import (
    TRACT_LAYER,
    VECTOR_QUERY_FIELDS,
    city_cache_key,
    load_city_layers,
)
from backend.lst_zonal import enrich_tracts_with_lst
from backend.raster_util import pick_primary_lst_raster
from models.contract import (
    InputField,
    ModelResult,
    ModelSpec,
    PostProcessResult,
    RunContext,
)
from models.lst_pipeline import run_lst

LST_VECTOR_FIELDS = (*VECTOR_QUERY_FIELDS, "lst_mean_C", "lst_max_C")


def _run_lst(paths: list[Path], ctx: RunContext) -> ModelResult:
    primary = pick_primary_lst_raster(paths)
    raw = run_lst(str(primary))
    stats = dict(raw.get("stats") or {})
    geotiff = stats.get("geotiff")
    artifacts: dict[str, str] = {}
    if geotiff:
        artifacts["geotiff"] = str(geotiff)
    return ModelResult(
        stats=stats,
        logs=raw.get("logs") or "",
        artifacts=artifacts,
        primary_raster=primary.name,
    )


def _post_process_lst(result: ModelResult, ctx: RunContext) -> PostProcessResult:
    geotiff = result.artifacts.get("geotiff") or result.stats.get("geotiff")
    if not geotiff:
        raise ValueError("LST pipeline did not produce a GeoTIFF.")

    address = ctx.address
    layers = load_city_layers(address, cache_dir=ctx.city_layers_cache)
    cache_key = city_cache_key(address)
    geojson_path = ctx.city_layers_cache / "geojson" / f"{cache_key}.geojson"
    base_gpkg = ctx.city_layers_cache / "gpkg" / f"{cache_key}.gpkg"

    if geojson_path.exists():
        gdf = gpd.read_file(geojson_path)
    elif base_gpkg.exists():
        gdf = gpd.read_file(base_gpkg, layer=TRACT_LAYER)
    else:
        raise FileNotFoundError("Census tract layer not found after city-layers load.")

    out_gpkg = ctx.city_dir / "tracts.gpkg"
    out_geojson = ctx.city_dir / "tracts.geojson"
    enriched = enrich_tracts_with_lst(
        gdf,
        Path(geotiff),
        out_gpkg=out_gpkg,
        out_geojson=out_geojson,
    )

    stats_updates = dict(result.stats)
    tract_lst = enriched["lst_mean_C"].dropna()
    if not tract_lst.empty:
        tract_mean = round(float(tract_lst.mean()), 2)
        stats_updates["tract_mean_lst_C"] = tract_mean
        stats_updates["mean_C"] = tract_mean
    else:
        stats_updates["tract_zonal_warning"] = (
            "No tract LST values — raster extent may not overlap census tracts "
            "(check that Landsat tiles match the registered city)."
        )

    west, south, east, north = enriched.total_bounds
    return PostProcessResult(
        enriched_gdf=enriched,
        stats_updates=stats_updates,
        vector_fields=list(LST_VECTOR_FIELDS),
        city_fields={
            "summary": layers.get("summary") or {},
            "worldpop": layers.get("worldpop") or {},
            "map_layers": layers.get("map_layers") or {},
            "geocode": layers.get("geocode") or {},
            "bounds_wgs84": [float(west), float(south), float(east), float(north)],
        },
    )


LST_MODEL = ModelSpec(
    id="lst",
    label="Land Surface Temperature",
    description=(
        "Compute land surface temperature from Landsat Collection 2 thermal and "
        "surface reflectance bands, then join mean/max LST to census tracts."
    ),
    input_schema=(
        InputField(
            name="landsat_bands",
            label="Landsat GeoTIFFs",
            required=True,
            accept=".tif,.tiff,.geotiff,.gtiff",
            hint="ST_B10 (thermal), SR_B4 (red), and SR_B5 (NIR) for the same scene",
        ),
    ),
    dashboard="equity",
    vector_join="tract_zonal",
    vector_fields=LST_VECTOR_FIELDS,
    primary_metric="mean_C",
    pick_primary=pick_primary_lst_raster,
    run=_run_lst,
    post_process=_post_process_lst,
)
