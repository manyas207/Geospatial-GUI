"""Orchestrate geocode → Census ACS + tract boundaries → map PNGs + WorldPop."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from backend.census_api import fetch_tract_acs, merge_acs_into_geojson
from backend.geocode import geocode_address
from backend.map_render import render_tract_map
from backend.tiger_tracts import fetch_tract_geojson
from backend.worldpop_raster import bounds_from_geojson, get_or_create_worldpop_preview

MAP_LAYER_SPECS = [
    ("tracts", None, "viridis", "Census tracts"),
    ("density", "population_density_per_km2", "YlOrRd", "Population density"),
    ("income", "median_income_usd", "Greens", "Median income"),
    ("ethnicity", "hispanic_pct", "OrRd", "Hispanic population %"),
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


def _map_cache_key(address: str, layer_id: str) -> str:
    digest = hashlib.sha256(f"{address.strip().lower()}|{layer_id}".encode("utf-8")).hexdigest()[:18]
    return digest


def _build_map_previews(geojson: dict, address: str, cache_dir: Path) -> dict[str, dict]:
    previews: dict[str, dict] = {}
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


def load_city_layers(address: str, *, cache_dir: Path) -> dict:
    """Full pipeline for one US city/county address string."""
    geocode = geocode_address(address)
    geojson = fetch_tract_geojson(
        geocode["state_fips"],
        geocode["county_fips"],
        cache_dir=cache_dir / "tiger",
    )
    acs = fetch_tract_acs(geocode["state_fips"], geocode["county_fips"])
    geojson = merge_acs_into_geojson(geojson, acs)

    map_previews = _build_map_previews(geojson, address, cache_dir)

    bounds = bounds_from_geojson(geojson)
    worldpop_path, worldpop_meta = get_or_create_worldpop_preview(bounds, cache_dir)

    worldpop_preview_url = None
    if worldpop_path and worldpop_path.exists():
        worldpop_token = encode_preview_token(worldpop_path, cache_dir)
        worldpop_preview_url = f"/api/city-layers/worldpop/{worldpop_token}/preview"
        worldpop_meta = {
            **worldpop_meta,
            "preview_url": worldpop_preview_url,
            "bounds_wgs84": list(bounds),
        }
    else:
        worldpop_meta = {**worldpop_meta, "preview_url": None, "bounds_wgs84": list(bounds)}

    summary = _summary_stats(geojson, geocode)
    tract_source = "Census TIGER shapefile (cached)" if (cache_dir / "tiger").exists() else "Census TIGER"

    return {
        "address": address,
        "matched_address": geocode["matched_address"],
        "geocode": geocode,
        "summary": summary,
        "map_layers": map_previews,
        "worldpop": worldpop_meta,
        "sources": {
            "geocoder": "Census Geocoder API",
            "tracts": tract_source,
            "demographics": f"Census ACS 5-year ({geocode['state_fips']}-{geocode['county_fips']})",
            "map_render": "Server-side PNG choropleth (matplotlib + geopandas)",
            "gridded_population": worldpop_meta.get("source", "WorldPop"),
        },
    }
