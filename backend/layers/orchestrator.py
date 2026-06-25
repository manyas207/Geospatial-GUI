"""Orchestrate geocode → Census ACS + tract boundaries → GeoPackage + map PNGs."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

import geopandas as gpd

from backend.layers.census import fetch_tract_acs, merge_acs_into_geojson
from backend.core.constants import TRACT_LAYER
from backend.layers.geocode import geocode_address
from backend.core.json_util import to_json_safe
from backend.layers.map_render import render_tract_map
from backend.core.presets import DEMO_CITY_ADDRESSES, DEMO_CITY_LST
from backend.layers.tracts import fetch_tract_geojson

MAP_LAYER_SPECS = [
    ("tracts", None, "viridis", "Census tracts"),
    ("density", "population_density_per_km2", "YlOrRd", "Population density"),
    ("income", "median_income_usd", "Greens", "Median income"),
    ("ethnicity", "hispanic_pct", "OrRd", "Hispanic population %"),
]

VECTOR_QUERY_FIELDS = [
    "GEOID",
    "acs_name",
    "population",
    "median_income_usd",
    "hispanic_pct",
    "black_pct",
    "population_density_per_km2",
]

def _summary_stats(geojson: dict, geocode: dict) -> dict:
    populations = []
    incomes = []
    densities = []

    for feature in geojson.get("features") or []:
        props = feature.get("properties") or {}
        if props.get("population") is not None:
            populations.append(props["population"])
        if props.get("median_income_usd") is not None:
            incomes.append(props["median_income_usd"])
        if props.get("population_density_per_km2") is not None:
            densities.append(props["population_density_per_km2"])

    return {
        "tract_count": len(geojson.get("features") or []),
        "county": geocode.get("county_name"),
        "state": geocode.get("state_name") or geocode.get("state_code"),
        "total_population": sum(populations) if populations else None,
        "median_income_usd": round(sorted(incomes)[len(incomes) // 2]) if incomes else None,
        "avg_density_per_km2": round(sum(densities) / len(densities), 1) if densities else None,
    }


def encode_preview_token(path: Path, cache_dir: Path) -> str:
    rel = path.resolve().relative_to(cache_dir.resolve())
    token = base64.urlsafe_b64encode(str(rel).encode("utf-8")).decode("utf-8")
    return token.rstrip("=")


def decode_preview_token(token: str, cache_dir: Path) -> Path:
    padding = "=" * (-len(token) % 4)
    rel = base64.urlsafe_b64decode((token + padding).encode("utf-8")).decode("utf-8")
    full = (cache_dir / rel).resolve()
    if not str(full).startswith(str(cache_dir.resolve())):
        raise ValueError("Invalid preview token.")
    return full


def city_cache_key(address: str) -> str:
    return hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()[:18]


def _map_cache_key(address: str, layer_id: str) -> str:
    return city_cache_key(f"{address.strip().lower()}|{layer_id}")


def _geojson_to_gdf(geojson: dict) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame.from_features(geojson.get("features") or [], crs="EPSG:4326")
    if gdf.empty:
        raise ValueError("No tract geometries to export.")
    return gdf


def _ensure_vector_layer(geojson: dict, address: str, cache_dir: Path) -> dict:
    """Write tract GeoPackage once per city; GeoJSON is derived on demand."""
    gpkg_dir = cache_dir / "gpkg"
    gpkg_dir.mkdir(parents=True, exist_ok=True)

    key = city_cache_key(address)
    gpkg_path = gpkg_dir / f"{key}.gpkg"

    if not gpkg_path.exists():
        gdf = _geojson_to_gdf(geojson)
        gdf.to_file(gpkg_path, driver="GPKG", layer=TRACT_LAYER)

    gdf = _geojson_to_gdf(geojson)
    west, south, east, north = gdf.total_bounds

    token = encode_preview_token(gpkg_path, cache_dir)
    return {
        "token": token,
        "geojson_url": f"/api/city-layers/vector/{token}/geojson",
        "gpkg_url": f"/api/city-layers/vector/{token}/download",
        "bounds_wgs84": [float(west), float(south), float(east), float(north)],
        "fields": VECTOR_QUERY_FIELDS,
        "layer": TRACT_LAYER,
    }


def load_vector_geojson(token: str, cache_dir: Path) -> dict:
    gpkg_path = decode_preview_token(token, cache_dir)
    geojson_path = cache_dir / "geojson" / f"{gpkg_path.stem}.geojson"
    if geojson_path.exists():
        return json.loads(geojson_path.read_text(encoding="utf-8"))
    gdf = gpd.read_file(gpkg_path, layer=TRACT_LAYER)
    return json.loads(gdf.to_json())


def _render_png_maps() -> bool:
    return os.environ.get("CITY_LAYERS_RENDER_PNG", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _build_map_previews(geojson: dict, address: str, cache_dir: Path) -> dict[str, dict]:
    previews: dict[str, dict] = {}
    if not _render_png_maps():
        for layer_id, field, _cmap, label in MAP_LAYER_SPECS:
            previews[layer_id] = {
                "id": layer_id,
                "label": label,
                "field": field,
                "preview_url": None,
            }
        return previews

    maps_dir = cache_dir / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    for layer_id, field, cmap, label in MAP_LAYER_SPECS:
        png_path = maps_dir / f"{_map_cache_key(address, layer_id)}.png"
        if not png_path.exists():
            render_tract_map(geojson, png_path, field=field, cmap=cmap, title=label)

        token = encode_preview_token(png_path, cache_dir)
        previews[layer_id] = {
            "id": layer_id,
            "label": label,
            "field": field,
            "preview_url": f"/api/city-layers/map/{token}/preview",
        }

    return previews


def _demo_snapshot_path(address: str, cache_dir: Path) -> Path:
    return cache_dir / "demo" / f"{city_cache_key(address)}.json"


def _save_demo_snapshot(address: str, payload: dict, cache_dir: Path) -> None:
    if address not in DEMO_CITY_ADDRESSES:
        return
    path = _demo_snapshot_path(address, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_json_safe(payload), indent=2), encoding="utf-8")


def _load_demo_snapshot(address: str, cache_dir: Path) -> dict | None:
    path = _demo_snapshot_path(address, cache_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_demo_portfolio(*, cache_dir: Path, warm: bool = False) -> dict:
    """Return cached city-layers payloads for all 11 demo cities."""
    cities_out: dict[str, dict | None] = {}
    errors: dict[str, str] = {}

    for address in DEMO_CITY_ADDRESSES:
        cached = _load_demo_snapshot(address, cache_dir)
        if cached:
            cities_out[address] = cached
            continue
        if warm:
            try:
                payload = load_city_layers(address, cache_dir=cache_dir)
                _save_demo_snapshot(address, payload, cache_dir)
                cities_out[address] = payload
            except Exception as exc:
                errors[address] = str(exc)
                cities_out[address] = None
        else:
            cities_out[address] = None

    hottest = max(DEMO_CITY_LST, key=lambda c: c["peak_lst_C"])
    loaded = sum(1 for v in cities_out.values() if v)

    return to_json_safe(
        {
            "demo_lst": DEMO_CITY_LST,
            "cities": cities_out,
            "loaded_count": loaded,
            "total_count": len(DEMO_CITY_ADDRESSES),
            "demo_overview": {
                "hottest_city": hottest["name"],
                "peak_lst_C": hottest["peak_lst_C"],
                "hottest_month": hottest["month"],
                "city_count": len(DEMO_CITY_LST),
            },
            "errors": errors,
        }
    )


def load_city_layers(address: str, *, cache_dir: Path) -> dict:
    """Full pipeline for one US city/county address string."""
    address = address.strip()
    if address in DEMO_CITY_ADDRESSES:
        cached = _load_demo_snapshot(address, cache_dir)
        if cached:
            return cached

    geocode = geocode_address(address)
    geojson = fetch_tract_geojson(
        geocode["state_fips"],
        geocode["county_fips"],
        cache_dir=cache_dir / "tiger",
    )
    acs = fetch_tract_acs(geocode["state_fips"], geocode["county_fips"])
    geojson = merge_acs_into_geojson(geojson, acs)

    map_previews = _build_map_previews(geojson, address, cache_dir)
    vector_layer = _ensure_vector_layer(geojson, address, cache_dir)

    summary = _summary_stats(geojson, geocode)
    tract_source = "Census TIGER shapefile (cached)" if (cache_dir / "tiger").exists() else "Census TIGER"

    result = {
        "address": address,
        "matched_address": geocode["matched_address"],
        "geocode": geocode,
        "summary": summary,
        "map_layers": map_previews,
        "vector_layer": vector_layer,
        "sources": {
            "geocoder": "Census Geocoder API",
            "tracts": tract_source,
            "demographics": f"Census ACS 5-year ({geocode['state_fips']}-{geocode['county_fips']})",
            "vector_layer": "Cached GeoPackage + GeoJSON (MapLibre)",
            "map_render": (
                "Server-side PNG choropleth (matplotlib)"
                if _render_png_maps()
                else "MapLibre vector choropleth (client)"
            ),
        },
    }
    _save_demo_snapshot(address, result, cache_dir)
    return result
