"""OBIA model plugin — multispectral raster + training ROIs → tract-level land cover."""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path

import geopandas as gpd

from backend.core.constants import RASTER_SUFFIXES, TRACT_LAYER
from backend.layers.orchestrator import (
    VECTOR_QUERY_FIELDS,
    city_cache_key,
    load_city_layers,
)
from backend.pipelines.obia_zonal import enrich_tracts_with_obia
from models.contract import (
    InputField,
    ModelResult,
    ModelSpec,
    PostProcessResult,
    RunContext,
)
from models.obia_core import run_obia_pipeline, run_obia_segmentation_only

OBIA_VECTOR_FIELDS = (
    *VECTOR_QUERY_FIELDS,
    "obia_mode_class",
    "obia_mode_pct",
    "obia_segment_count",
)

_DEFAULT_N_SEGMENTS = int(os.environ.get("OBIA_N_SEGMENTS", "50000"))


def _pick_raster(paths: list[Path]) -> Path:
    rasters = [path for path in paths if path.suffix.lower() in RASTER_SUFFIXES]
    if not rasters:
        raise ValueError("Upload at least one multispectral GeoTIFF for OBIA.")
    return max(rasters, key=lambda path: path.stat().st_size)


def _pick_samples_shp(paths: list[Path]) -> Path | None:
    shps = [path for path in paths if path.suffix.lower() == ".shp"]
    if not shps:
        return None
    shp = shps[0]
    stem = shp.with_suffix("")
    for suffix in (".shx", ".dbf"):
        if not Path(f"{stem}{suffix}").exists():
            raise ValueError(
                f"Shapefile {shp.name} is missing {suffix}. "
                "Upload .shp, .shx, and .dbf together."
            )
    return shp


def _run_obia(paths: list[Path], ctx: RunContext) -> ModelResult:
    raster = _pick_raster(paths)
    samples = _pick_samples_shp(paths)
    out_dir = ctx.city_dir / "obia_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    log_buffer = io.StringIO()
    with contextlib.redirect_stdout(log_buffer):
        if samples:
            raw = run_obia_pipeline(
                str(raster),
                str(samples),
                str(out_dir),
                n_segments=_DEFAULT_N_SEGMENTS,
            )
        else:
            raw = run_obia_segmentation_only(
                str(raster),
                str(out_dir),
                n_segments=min(_DEFAULT_N_SEGMENTS, 50_000),
            )

    stats = dict(raw.get("stats") or {})
    artifacts: dict[str, str] = {}

    classified_gpkg = stats.get("classified_gpkg") or stats.get("segments_gpkg")
    if classified_gpkg:
        artifacts["classified_gpkg"] = str(classified_gpkg)
    classified_tif = stats.get("classified_tif")
    if classified_tif:
        artifacts["classified_tif"] = str(classified_tif)

    if stats.get("mode") == "segmentation_only":
        stats["classification_skipped"] = True

    return ModelResult(
        stats=stats,
        logs=log_buffer.getvalue(),
        artifacts=artifacts,
        primary_raster=raster.name,
    )


def _post_process_obia(result: ModelResult, ctx: RunContext) -> PostProcessResult:
    segments_gpkg = result.artifacts.get("classified_gpkg") or result.stats.get(
        "classified_gpkg"
    ) or result.stats.get("segments_gpkg")
    if not segments_gpkg:
        raise ValueError("OBIA pipeline did not produce a segment GeoPackage.")

    address = ctx.address
    layers = load_city_layers(address, cache_dir=ctx.city_layers_cache)
    cache_key = city_cache_key(address)
    geojson_path = ctx.city_layers_cache / "geojson" / f"{cache_key}.geojson"
    base_gpkg = ctx.city_layers_cache / "gpkg" / f"{cache_key}.gpkg"

    if geojson_path.exists():
        tract_gdf = gpd.read_file(geojson_path)
    elif base_gpkg.exists():
        tract_gdf = gpd.read_file(base_gpkg, layer=TRACT_LAYER)
    else:
        raise FileNotFoundError("Census tract layer not found after city-layers load.")

    out_gpkg = ctx.city_dir / "tracts.gpkg"
    enriched = enrich_tracts_with_obia(
        tract_gdf,
        Path(segments_gpkg),
        out_gpkg=out_gpkg,
    )

    stats_updates = dict(result.stats)
    labeled = stats_updates.get("labeled_segments")
    total_segments = stats_updates.get("total_segments") or stats_updates.get("polygons")
    if labeled is not None:
        stats_updates["primary_value"] = labeled
    elif total_segments is not None:
        stats_updates["primary_value"] = total_segments

    mode_pct = enriched["obia_mode_pct"].dropna() if "obia_mode_pct" in enriched.columns else []
    if len(mode_pct):
        stats_updates["tract_mean_mode_pct"] = round(float(mode_pct.mean()), 1)

    seg_counts = enriched["obia_segment_count"].dropna()
    if not seg_counts.empty and float(seg_counts.max()) == 0:
        stats_updates["tract_zonal_warning"] = (
            "No OBIA segments overlap census tracts — check that the raster covers the registered city."
        )

    west, south, east, north = enriched.total_bounds
    return PostProcessResult(
        enriched_gdf=enriched,
        stats_updates=stats_updates,
        vector_fields=list(OBIA_VECTOR_FIELDS),
        city_fields={
            "summary": layers.get("summary") or {},
            "map_layers": layers.get("map_layers") or {},
            "geocode": layers.get("geocode") or {},
            "bounds_wgs84": [float(west), float(south), float(east), float(north)],
        },
    )


OBIA_MODEL = ModelSpec(
    id="obia",
    label="OBIA Land Cover",
    description=(
        "Object-based image analysis: segment a multispectral raster, train from ROI "
        "polygons (macroclass + roi_id), classify segments, and summarize dominant "
        "land-cover class per census tract."
    ),
    input_schema=(
        InputField(
            name="multispectral_raster",
            label="Multispectral GeoTIFF",
            required=True,
            accept=".tif,.tiff,.geotiff,.gtiff",
            hint="Multi-band GeoTIFF (1+ bands; 7-band HLS ideal; fewer bands use RGBN-style mapping)",
        ),
        InputField(
            name="training_rois",
            label="Training shapefile",
            required=False,
            accept=".shp,.shx,.dbf,.prj,.cpg",
            hint="Class column (class_id, macroclass, …). Pixel/point-sized training shapes are OK.",
        ),
    ),
    dashboard="equity",
    vector_join="tract_zonal",
    vector_fields=OBIA_VECTOR_FIELDS,
    primary_metric="primary_value",
    pick_primary=_pick_raster,
    run=_run_obia,
    post_process=_post_process_obia,
)
