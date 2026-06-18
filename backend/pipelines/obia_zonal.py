"""Join OBIA segment polygons to census tract boundaries (dominant class per tract)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from backend.core.constants import TRACT_LAYER

PREDICTED_FIELD = "predicted"


def enrich_tracts_with_obia(
    tract_gdf: gpd.GeoDataFrame,
    segments_gpkg: Path,
    *,
    predicted_field: str = PREDICTED_FIELD,
    out_gpkg: Path,
    out_geojson: Path | None = None,
) -> gpd.GeoDataFrame:
    """Add OBIA summary fields per tract; write GPKG (+ optional GeoJSON)."""
    segments_gpkg = Path(segments_gpkg)
    if not segments_gpkg.exists():
        raise FileNotFoundError(f"OBIA segments not found: {segments_gpkg}")

    tracts = tract_gdf.copy()
    if tracts.crs is None:
        tracts = tracts.set_crs("EPSG:4326")

    segments = gpd.read_file(segments_gpkg)
    if segments.empty:
        raise ValueError("OBIA segment layer is empty.")

    if segments.crs is None:
        segments = segments.set_crs(tracts.crs)
    else:
        segments = segments.to_crs(tracts.crs)

    has_predicted = predicted_field in segments.columns
    seg_cols = ["geometry"]
    if has_predicted:
        seg_cols.append(predicted_field)
    segments = segments[seg_cols].copy()

    tracts["_tract_idx"] = range(len(tracts))
    joined = gpd.overlay(tracts, segments, how="intersection", keep_geom_type=False)
    if joined.empty:
        tracts["obia_segment_count"] = 0
        if has_predicted:
            tracts["obia_mode_class"] = None
            tracts["obia_mode_pct"] = None
        tracts = tracts.drop(columns=["_tract_idx"], errors="ignore")
        out_gpkg.parent.mkdir(parents=True, exist_ok=True)
        tracts.to_file(out_gpkg, driver="GPKG", layer=TRACT_LAYER)
        if out_geojson is not None:
            out_geojson.write_text(tracts.to_json(), encoding="utf-8")
        return tracts

    joined["intersect_area"] = joined.geometry.area

    mode_classes: list[object] = []
    mode_pcts: list[float | None] = []
    segment_counts: list[int] = []

    for idx in range(len(tracts)):
        group = joined[joined["_tract_idx"] == idx]
        if group.empty:
            segment_counts.append(0)
            mode_classes.append(None)
            mode_pcts.append(None)
            continue

        segment_counts.append(int(group[predicted_field].notna().sum() if has_predicted else len(group)))
        total_area = float(group["intersect_area"].sum())
        if total_area <= 0 or not has_predicted:
            mode_classes.append(None)
            mode_pcts.append(None)
            continue

        by_class = group.groupby(predicted_field, dropna=True)["intersect_area"].sum()
        if by_class.empty:
            mode_classes.append(None)
            mode_pcts.append(None)
            continue

        dominant = by_class.idxmax()
        mode_classes.append(dominant)
        mode_pcts.append(round(100.0 * float(by_class.max()) / total_area, 1))

    tracts["obia_segment_count"] = segment_counts
    if has_predicted:
        tracts["obia_mode_class"] = mode_classes
        tracts["obia_mode_pct"] = mode_pcts

    tracts = tracts.drop(columns=["_tract_idx"], errors="ignore")

    out_gpkg.parent.mkdir(parents=True, exist_ok=True)
    tracts.to_file(out_gpkg, driver="GPKG", layer=TRACT_LAYER)

    if out_geojson is not None:
        out_geojson.write_text(tracts.to_json(), encoding="utf-8")

    return tracts
