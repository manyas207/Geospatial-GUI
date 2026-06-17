"""Multi-city LST project storage and orchestration."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.city_layers import (
    TRACT_LAYER,
    VECTOR_QUERY_FIELDS,
    city_cache_key,
    load_city_layers,
)
from backend.geocode import geocode_address
from backend.json_util import to_json_safe
from backend.lst_zonal import enrich_tracts_with_lst
from backend.presets import PRESET_CITIES
from backend.raster_util import pick_primary_lst_raster
from backend.router import run_lst_pipeline

import geopandas as gpd

LST_VECTOR_FIELDS = [*VECTOR_QUERY_FIELDS, "lst_mean_C", "lst_max_C"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def address_to_key(address: str) -> str:
    geocode = geocode_address(address)
    county = (geocode.get("county_name") or "").split()[0]
    state = geocode.get("state_code") or geocode.get("state_name") or ""
    base = f"{county}_{state}" if county else address
    slug = re.sub(r"[^\w]+", "_", base.strip().lower()).strip("_")
    return slug or uuid.uuid4().hex[:10]


def _manifest_path(project_id: str, projects_dir: Path) -> Path:
    return projects_dir / project_id / "manifest.json"


def _load_manifest_raw(project_id: str, projects_dir: Path) -> dict:
    path = _manifest_path(project_id, projects_dir)
    if not path.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(project_id: str, projects_dir: Path, manifest: dict) -> None:
    path = _manifest_path(project_id, projects_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_json_safe(manifest), indent=2), encoding="utf-8")


def create_project(name: str | None, *, projects_dir: Path) -> dict:
    project_id = uuid.uuid4().hex
    manifest = {
        "id": project_id,
        "name": (name or "LST City Project").strip(),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "cities": {},
    }
    _save_manifest(project_id, projects_dir, manifest)
    return manifest


def get_project(project_id: str, *, projects_dir: Path) -> dict:
    manifest = _load_manifest_raw(project_id, projects_dir)
    return _enrich_project_response(manifest, projects_dir)


def list_ready_cities(cities: dict[str, dict]) -> list[dict]:
    return [
        {"key": key, **entry}
        for key, entry in cities.items()
        if entry.get("status") == "ready"
    ]


def _city_dir(project_id: str, city_key: str, projects_dir: Path) -> Path:
    return projects_dir / project_id / "cities" / city_key


def _vector_urls(project_id: str, city_key: str) -> dict[str, str]:
    return {
        "geojson_url": f"/api/projects/{project_id}/cities/{city_key}/geojson",
        "gpkg_url": f"/api/projects/{project_id}/cities/{city_key}/gpkg",
    }


def _enrich_project_response(manifest: dict, projects_dir: Path) -> dict:
    project_id = manifest["id"]
    cities_out: dict[str, Any] = {}

    for key, entry in (manifest.get("cities") or {}).items():
        city = dict(entry)
        if city.get("status") == "ready":
            gpkg = _city_dir(project_id, key, projects_dir) / "tracts.gpkg"
            if gpkg.exists():
                gdf = gpd.read_file(gpkg, layer=TRACT_LAYER)
                west, south, east, north = gdf.total_bounds
                city["vector_layer"] = {
                    "token": f"{project_id}:{key}",
                    "bounds_wgs84": [float(west), float(south), float(east), float(north)],
                    "fields": LST_VECTOR_FIELDS,
                    "layer": TRACT_LAYER,
                    **_vector_urls(project_id, key),
                }
        cities_out[key] = city

    ready_count = sum(1 for c in cities_out.values() if c.get("status") == "ready")
    return to_json_safe(
        {
            **manifest,
            "cities": cities_out,
            "ready_count": ready_count,
            "preset_cities": PRESET_CITIES,
        }
    )


def register_city(project_id: str, address: str, *, projects_dir: Path, city_layers_cache: Path) -> dict:
    address = address.strip()
    if not address:
        raise ValueError("Address is required.")

    manifest = _load_manifest_raw(project_id, projects_dir)
    key = address_to_key(address)
    geocode = geocode_address(address)

    for existing_key, entry in manifest.get("cities", {}).items():
        if (entry.get("address") or "").lower() == address.lower():
            key = existing_key
            break

    city_dir = _city_dir(project_id, key, projects_dir)
    city_dir.mkdir(parents=True, exist_ok=True)

    manifest.setdefault("cities", {})[key] = {
        "key": key,
        "address": address,
        "name": address,
        "matched_address": geocode.get("matched_address"),
        "status": "pending",
        "color": _preset_color(address),
        "registered_at": _now_iso(),
    }
    manifest["updated_at"] = _now_iso()
    _save_manifest(project_id, projects_dir, manifest)
    return get_project(project_id, projects_dir=projects_dir)


def _preset_color(address: str) -> str:
    short = address.lower()
    for preset in PRESET_CITIES:
        if preset["name"].lower() == short or preset["name"].split(",")[0].lower() in short:
            return preset["color"]
    return "#3d7ea6"


def run_city_lst_upload(
    project_id: str,
    city_key: str,
    saved_paths: list[Path],
    *,
    projects_dir: Path,
    city_layers_cache: Path,
) -> dict:
    manifest = _load_manifest_raw(project_id, projects_dir)
    city = manifest.get("cities", {}).get(city_key)
    if not city:
        raise ValueError(f"City not registered in project: {city_key}")

    address = city["address"]
    city_dir = _city_dir(project_id, city_key, projects_dir)
    uploads_dir = city_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    city["status"] = "processing"
    city["error"] = None
    manifest["updated_at"] = _now_iso()
    _save_manifest(project_id, projects_dir, manifest)

    try:
        primary = pick_primary_lst_raster(saved_paths)

        result = run_lst_pipeline(primary)
        lst_stats = to_json_safe(result.get("stats") or {})
        geotiff = lst_stats.get("geotiff")
        if not geotiff:
            raise ValueError("LST pipeline did not produce a GeoTIFF.")

        layers = load_city_layers(address, cache_dir=city_layers_cache)
        cache_key = city_cache_key(address)
        geojson_path = city_layers_cache / "geojson" / f"{cache_key}.geojson"
        base_gpkg = city_layers_cache / "gpkg" / f"{cache_key}.gpkg"
        if geojson_path.exists():
            gdf = gpd.read_file(geojson_path)
        elif base_gpkg.exists():
            gdf = gpd.read_file(base_gpkg, layer=TRACT_LAYER)
        else:
            raise FileNotFoundError("Census tract layer not found after city-layers load.")

        out_gpkg = city_dir / "tracts.gpkg"
        out_geojson = city_dir / "tracts.geojson"
        enriched = enrich_tracts_with_lst(
            gdf,
            Path(geotiff),
            out_gpkg=out_gpkg,
            out_geojson=out_geojson,
        )

        west, south, east, north = enriched.total_bounds
        tract_lst = enriched["lst_mean_C"].dropna()
        if not tract_lst.empty:
            tract_mean = round(float(tract_lst.mean()), 2)
            lst_stats["tract_mean_lst_C"] = tract_mean
            lst_stats["mean_C"] = tract_mean
        else:
            lst_stats["tract_zonal_warning"] = (
                "No tract LST values — raster extent may not overlap census tracts "
                "(check that Landsat tiles match the registered city)."
            )

        city.update(
            {
                "status": "ready",
                "lst_stats": lst_stats,
                "summary": layers.get("summary") or {},
                "worldpop": layers.get("worldpop") or {},
                "map_layers": layers.get("map_layers") or {},
                "geocode": layers.get("geocode") or {},
                "bounds_wgs84": [float(west), float(south), float(east), float(north)],
                "processed_at": _now_iso(),
                "primary_raster": primary.name,
            }
        )
    except Exception as exc:
        city["status"] = "error"
        city["error"] = str(exc)
        manifest["updated_at"] = _now_iso()
        _save_manifest(project_id, projects_dir, manifest)
        raise

    manifest["updated_at"] = _now_iso()
    _save_manifest(project_id, projects_dir, manifest)
    return get_project(project_id, projects_dir=projects_dir)



def get_city_geojson(project_id: str, city_key: str, *, projects_dir: Path) -> dict:
    path = _city_dir(project_id, city_key, projects_dir) / "tracts.geojson"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    gpkg = _city_dir(project_id, city_key, projects_dir) / "tracts.gpkg"
    if not gpkg.exists():
        raise FileNotFoundError("Tract data not found for this city.")
    gdf = gpd.read_file(gpkg, layer=TRACT_LAYER)
    return json.loads(gdf.to_json())


def get_city_gpkg_path(project_id: str, city_key: str, *, projects_dir: Path) -> Path:
    path = _city_dir(project_id, city_key, projects_dir) / "tracts.gpkg"
    if not path.exists():
        raise FileNotFoundError("GeoPackage not found for this city.")
    return path


def compare_project(project_id: str, question: str, *, projects_dir: Path) -> dict:
    from backend.city_compare import compare_cities

    return compare_cities(project_id, question, projects_dir=projects_dir)
