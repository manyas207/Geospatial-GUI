"""Structured tract queries against cached city GeoPackages (SQLite/GPKG)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import geopandas as gpd

from backend.city_layers import decode_preview_token
from backend.constants import TRACT_LAYER
from backend.json_util import to_json_safe

QUERYABLE_FIELDS: dict[str, dict[str, Any]] = {
    "population": {"label": "population", "aliases": ["pop"]},
    "median_income_usd": {"label": "median income", "aliases": ["income", "earnings"]},
    "hispanic_pct": {"label": "Hispanic percentage", "aliases": ["hispanic", "ethnic", "latino"]},
    "black_pct": {"label": "Black percentage", "aliases": ["black", "african"]},
    "population_density_per_km2": {
        "label": "population density",
        "aliases": ["density", "per km", "per square"],
    },
    "lst_mean_C": {"label": "LST", "aliases": ["land surface", "heat", "temperature"]},
}

DISPLAY_COLUMNS = [
    "GEOID",
    "acs_name",
    "population",
    "median_income_usd",
    "hispanic_pct",
    "black_pct",
    "population_density_per_km2",
    "lst_mean_C",
    "lst_max_C",
]


def load_tract_gdf(gpkg_path: Path) -> gpd.GeoDataFrame:
    if not gpkg_path.exists():
        raise FileNotFoundError("Tract GeoPackage not found.")
    return gpd.read_file(gpkg_path, layer=TRACT_LAYER)


def gpkg_path_from_token(token: str, cache_dir: Path) -> Path:
    path = decode_preview_token(token, cache_dir)
    if path.suffix.lower() != ".gpkg":
        raise ValueError("Invalid tract layer token.")
    return path


def _detect_field(question: str) -> str | None:
    q = question.lower()
    for field, meta in QUERYABLE_FIELDS.items():
        label = meta["label"]
        if label in q or field.replace("_", " ") in q:
            return field
        for alias in meta.get("aliases", []):
            if alias in q:
                return field
    return None


def _parse_number(raw: str) -> float:
    return float(raw.replace(",", "").replace("$", "").strip())


def _detect_filter(question: str, field: str) -> tuple[str, float] | None:
    q = question.lower()
    percent = field.endswith("_pct")

    patterns: list[tuple[str, str]] = [
        (r"(?:below|under|less than)\s*\$?\s*([\d,.]+)\s*%?", "<"),
        (r"(?:above|over|more than|greater than|at least)\s*\$?\s*([\d,.]+)\s*%?", ">"),
    ]
    for pattern, op in patterns:
        match = re.search(pattern, q)
        if not match:
            continue
        value = _parse_number(match.group(1))
        if percent and "%" not in match.group(0) and value > 100:
            pass
        return op, value
    return None


def _detect_aggregate(question: str) -> str:
    q = question.lower()
    if any(word in q for word in ("how many", "count", "number of tracts")):
        return "count"
    if any(word in q for word in ("highest", "maximum", "max", "most", "top")):
        return "max"
    if any(word in q for word in ("lowest", "minimum", "min", "least")):
        return "min"
    if any(word in q for word in ("average", "mean", "avg")):
        return "mean"
    if any(word in q for word in ("list", "which tracts", "show tracts")):
        return "list"
    return "summary"


def _row_dict(row: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for col in DISPLAY_COLUMNS:
        if col not in row.index:
            continue
        value = row[col]
        if value is None or (isinstance(value, float) and value != value):
            continue
        data[col] = to_json_safe(value)
    return data


def _apply_filter(gdf: gpd.GeoDataFrame, field: str, op: str, value: float) -> gpd.GeoDataFrame:
    if field not in gdf.columns:
        return gdf.iloc[0:0]
    series = gdf[field]
    if op == "<":
        return gdf[series < value]
    return gdf[series > value]


def query_tract_layer(token: str, question: str, cache_dir: Path) -> dict[str, Any]:
    """Interpret a natural-language question and run a safe query on tract attributes."""
    return query_tract_gpkg(gpkg_path_from_token(token, cache_dir), question)


def query_tract_gpkg(gpkg_path: Path, question: str) -> dict[str, Any]:
    """Run tract query against an explicit GeoPackage path."""
    gdf = load_tract_gdf(gpkg_path)
    field = _detect_field(question)
    aggregate = _detect_aggregate(question)
    filt = _detect_filter(question, field) if field else None

    working = gdf
    if field and filt:
        working = _apply_filter(working, field, filt[0], filt[1])

    label = QUERYABLE_FIELDS.get(field or "", {}).get("label", field or "tracts")
    interpretation_parts = [f"aggregate={aggregate}"]
    if field:
        interpretation_parts.append(f"field={field}")
    if filt:
        interpretation_parts.append(f"filter {filt[0]} {filt[1]}")

    result: dict[str, Any] = {
        "interpretation": ", ".join(interpretation_parts),
        "tract_count_total": int(len(gdf)),
        "tract_count_matched": int(len(working)),
    }

    if aggregate == "count":
        result["answer_value"] = int(len(working))
        result["summary"] = f"{len(working)} tracts match the criteria."
        return to_json_safe(result)

    if field and field in working.columns and not working.empty:
        series = working[field].dropna()
        if aggregate == "mean" and not series.empty:
            mean_val = round(float(series.mean()), 2)
            result["answer_value"] = mean_val
            result["summary"] = f"Average {label}: {mean_val}."
            return to_json_safe(result)

        if aggregate in ("max", "min") and not series.empty:
            idx = series.idxmax() if aggregate == "max" else series.idxmin()
            row = working.loc[idx]
            result["top_tract"] = _row_dict(row)
            extreme = row[field]
            result["answer_value"] = to_json_safe(extreme)
            result["summary"] = (
                f"Tract with {'highest' if aggregate == 'max' else 'lowest'} {label}: "
                f"{result['top_tract'].get('acs_name', result['top_tract'].get('GEOID'))} "
                f"({result['answer_value']})."
            )
            return to_json_safe(result)

        if aggregate == "list":
            top = working.sort_values(field, ascending=False).head(10)
            result["tracts"] = [_row_dict(row) for _, row in top.iterrows()]
            result["summary"] = f"Top {len(result['tracts'])} tracts by {label}."
            return to_json_safe(result)

    # County-wide summary fallback when no specific field detected.
    summary: dict[str, Any] = {}
    for col in ("population", "median_income_usd", "hispanic_pct", "population_density_per_km2"):
        if col in gdf.columns:
            series = gdf[col].dropna()
            if not series.empty:
                summary[f"avg_{col}"] = round(float(series.mean()), 2)
                summary[f"max_{col}"] = to_json_safe(series.max())
                summary[f"min_{col}"] = to_json_safe(series.min())
    result["county_summary"] = summary
    result["summary"] = (
        f"County has {len(gdf)} tracts. "
        "Ask about income, population, density, or ethnicity with count/average/highest/lowest."
    )
    return to_json_safe(result)
