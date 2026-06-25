"""ModelSpec wiring stub (copy to models/<id>_model.py).

Rename your_model → your model id everywhere. Register YOUR_MODEL in
models/registry.py. See templates/model/ and docs/ADDING_A_MODEL.md § Quick checklist.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from backend.core.constants import RASTER_SUFFIXES, TRACT_LAYER
from backend.layers.orchestrator import (
    VECTOR_QUERY_FIELDS,
    city_cache_key,
    load_city_layers,
)
from backend.pipelines.your_zonal import enrich_tracts_with_your_model
from models.contract import (
    InputField,
    ModelResult,
    ModelSpec,
    PostProcessResult,
    RunContext,
)
from models.your_model_core import compute_your_model

YOUR_MODEL_VECTOR_FIELDS = (*VECTOR_QUERY_FIELDS, "your_model_mean", "your_model_max")


def _pick_raster(paths: list[Path]) -> Path:
    rasters = [p for p in paths if p.suffix.lower() in RASTER_SUFFIXES]
    if not rasters:
        raise ValueError("Upload at least one GeoTIFF for this model.")
    return max(rasters, key=lambda p: p.stat().st_size)


def _load_tract_gdf(address: str, city_layers_cache: Path) -> gpd.GeoDataFrame:
    load_city_layers(address, cache_dir=city_layers_cache)
    cache_key = city_cache_key(address)
    geojson_path = city_layers_cache / "geojson" / f"{cache_key}.geojson"
    base_gpkg = city_layers_cache / "gpkg" / f"{cache_key}.gpkg"

    if geojson_path.exists():
        return gpd.read_file(geojson_path)
    if base_gpkg.exists():
        return gpd.read_file(base_gpkg, layer=TRACT_LAYER)
    raise FileNotFoundError(
        "Census tract layer not found after city-layers load. "
        "Check CENSUS_API_KEY in .env and that the address geocodes."
    )


def _run_your_model(paths: list[Path], ctx: RunContext) -> ModelResult:
    raster = _pick_raster(paths)
    out_dir = ctx.city_dir / "your_model_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = compute_your_model(str(raster), str(out_dir))
    stats = dict(raw.get("stats") or {})
    artifacts: dict[str, str] = {}
    geotiff = stats.get("geotiff")
    if geotiff:
        artifacts["geotiff"] = str(geotiff)
    return ModelResult(
        stats=stats,
        logs=raw.get("logs") or "",
        artifacts=artifacts,
        primary_raster=raster.name,
    )


def _post_process_your_model(result: ModelResult, ctx: RunContext) -> PostProcessResult:
    geotiff = result.artifacts.get("geotiff") or result.stats.get("geotiff")
    if not geotiff:
        raise ValueError("Pipeline did not produce a GeoTIFF.")

    address = ctx.address
    layers = load_city_layers(address, cache_dir=ctx.city_layers_cache)
    tract_gdf = _load_tract_gdf(address, ctx.city_layers_cache)

    out_gpkg = ctx.city_dir / "tracts.gpkg"
    enriched = enrich_tracts_with_your_model(
        tract_gdf,
        Path(geotiff),
        out_gpkg=out_gpkg,
    )

    stats_updates: dict = {}
    tract_vals = enriched["your_model_mean"].dropna()
    if not tract_vals.empty:
        tract_mean = round(float(tract_vals.mean()), 3)
        stats_updates["tract_mean_your_model"] = tract_mean
        stats_updates["your_model_mean"] = tract_mean
    else:
        stats_updates["tract_zonal_warning"] = (
            "No values overlap census tracts — raster extent may not match "
            "the registered city (check city name and CRS)."
        )

    west, south, east, north = enriched.total_bounds
    return PostProcessResult(
        enriched_gdf=enriched,
        stats_updates=stats_updates,
        vector_fields=list(YOUR_MODEL_VECTOR_FIELDS),
        city_fields={
            "summary": layers.get("summary") or {},
            "map_layers": layers.get("map_layers") or {},
            "geocode": layers.get("geocode") or {},
            "bounds_wgs84": [float(west), float(south), float(east), float(north)],
        },
    )


YOUR_MODEL = ModelSpec(
    id="your_model",
    label="Your Model",
    description="Short description for GET /api/models and the Ask dropdown.",
    input_schema=(
        InputField(
            name="multispectral_raster",
            label="Multispectral GeoTIFF",
            required=True,
            accept=".tif,.tiff,.geotiff,.gtiff",
            hint="Document band order and required inputs here",
        ),
    ),
    dashboard="equity",
    vector_join="tract_zonal",
    vector_fields=YOUR_MODEL_VECTOR_FIELDS,
    primary_metric="your_model_mean",
    pick_primary=_pick_raster,
    run=_run_your_model,
    post_process=_post_process_your_model,
)
