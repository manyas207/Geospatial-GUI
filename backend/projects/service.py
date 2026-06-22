"""Multi-city project storage and model-run orchestration."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.constants import TRACT_LAYER
from backend.layers.geocode import geocode_address
from backend.core.json_util import to_json_safe
from backend.core.presets import PRESET_CITIES
from backend.projects.dispatch import run_model
from models.contract import RunContext
from models.lst_model import LST_VECTOR_FIELDS
from models.registry import get_model

import geopandas as gpd

DEFAULT_MODEL_ID = "lst"


def city_run_stats(city: dict) -> dict:
    """Per-city pipeline stats (reads legacy lst_stats from old manifests)."""
    return dict(city.get("run_stats") or city.get("lst_stats") or {})


def _city_vector_fields(city: dict, project_model_id: str | None = None) -> list[str]:
    if city.get("vector_fields"):
        return list(city["vector_fields"])
    model_id = city.get("model_id") or project_model_id or DEFAULT_MODEL_ID
    try:
        return list(get_model(model_id).vector_fields)
    except ValueError:
        return list(LST_VECTOR_FIELDS)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def address_to_key(address: str) -> str:
    geocode = geocode_address(address)
    county = (geocode.get("county_name") or "").split()[0]
    state = geocode.get("state_code") or geocode.get("state_name") or ""
    base = f"{county}_{state}" if county else address
    slug = re.sub(r"[^\w]+", "_", base.strip().lower()).strip("_")
    return slug or uuid.uuid4().hex[:10]


def city_storage_key(address: str, *, month: int | None = None, year: int | None = None) -> str:
    base = address_to_key(address)
    if month is not None and year is not None:
        return f"{base}_{year}_{month:02d}"
    if year is not None:
        return f"{base}_{year}"
    return base


def _validate_period(month: int | None, year: int | None) -> None:
    if month is not None and year is None:
        raise ValueError("Year is required when month is provided.")
    if month is not None and not 1 <= month <= 12:
        raise ValueError("Month must be between 1 and 12.")
    if year is not None and not 1984 <= year <= 2100:
        raise ValueError("Year must be between 1984 and 2100.")


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


def create_project(
    name: str | None,
    *,
    projects_dir: Path,
    model_id: str | None = None,
) -> dict:
    resolved_model = (model_id or DEFAULT_MODEL_ID).strip().lower()
    get_model(resolved_model)

    project_id = uuid.uuid4().hex
    cleaned_name = (name or "").strip() or "Geospatial City Project"
    manifest = {
        "id": project_id,
        "name": cleaned_name,
        "model_id": resolved_model,
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
    project_model_id = manifest.get("model_id") or DEFAULT_MODEL_ID
    cities_out: dict[str, Any] = {}

    for key, entry in (manifest.get("cities") or {}).items():
        city = dict(entry)
        run_stats = city_run_stats(city)
        if run_stats and not city.get("run_stats"):
            city["run_stats"] = run_stats
        if run_stats and not city.get("lst_stats"):
            city["lst_stats"] = run_stats

        if city.get("status") == "ready":
            gpkg = _city_dir(project_id, key, projects_dir) / "tracts.gpkg"
            if gpkg.exists():
                gdf = gpd.read_file(gpkg, layer=TRACT_LAYER)
                west, south, east, north = gdf.total_bounds
                fields = _city_vector_fields(city, project_model_id)
                city["vector_layer"] = {
                    "token": f"{project_id}:{key}",
                    "bounds_wgs84": [float(west), float(south), float(east), float(north)],
                    "fields": fields,
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


def update_project(
    project_id: str,
    *,
    name: str | None = None,
    projects_dir: Path,
) -> dict:
    manifest = _load_manifest_raw(project_id, projects_dir)
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Project name cannot be empty.")
        manifest["name"] = cleaned
    manifest["updated_at"] = _now_iso()
    _save_manifest(project_id, projects_dir, manifest)
    return get_project(project_id, projects_dir=projects_dir)


def register_city(
    project_id: str,
    address: str,
    *,
    month: int | None = None,
    year: int | None = None,
    projects_dir: Path,
    city_layers_cache: Path,
) -> dict:
    address = address.strip()
    if not address:
        raise ValueError("Address is required.")
    _validate_period(month, year)

    manifest = _load_manifest_raw(project_id, projects_dir)
    geocode = geocode_address(address)
    key = city_storage_key(address, month=month, year=year)

    for existing_key, entry in manifest.get("cities", {}).items():
        same_address = (entry.get("address") or "").lower() == address.lower()
        same_period = entry.get("month") == month and entry.get("year") == year
        if same_address and same_period:
            key = existing_key
            break

    city_dir = _city_dir(project_id, key, projects_dir)
    city_dir.mkdir(parents=True, exist_ok=True)

    city_entry = {
        "key": key,
        "address": address,
        "name": address,
        "matched_address": geocode.get("matched_address"),
        "status": "pending",
        "color": _preset_color(address),
        "registered_at": _now_iso(),
    }
    if month is not None:
        city_entry["month"] = month
    if year is not None:
        city_entry["year"] = year

    manifest.setdefault("cities", {})[key] = city_entry
    manifest["updated_at"] = _now_iso()
    _save_manifest(project_id, projects_dir, manifest)
    return get_project(project_id, projects_dir=projects_dir)


def _preset_color(address: str) -> str:
    short = address.lower()
    for preset in PRESET_CITIES:
        if preset["name"].lower() == short or preset["name"].split(",")[0].lower() in short:
            return preset["color"]
    return "#3d7ea6"


def mark_city_processing(
    project_id: str,
    city_key: str,
    *,
    model_id: str,
    projects_dir: Path,
) -> None:
    """Set city status to processing before a background model run."""
    spec = get_model(model_id)
    manifest = _load_manifest_raw(project_id, projects_dir)
    city = manifest.get("cities", {}).get(city_key)
    if not city:
        raise ValueError(f"City not registered in project: {city_key}")

    city["status"] = "processing"
    city["error"] = None
    city["model_id"] = spec.id
    manifest["model_id"] = spec.id
    manifest["updated_at"] = _now_iso()
    _save_manifest(project_id, projects_dir, manifest)


def run_city_model_upload(
    project_id: str,
    city_key: str,
    saved_paths: list[Path],
    *,
    model_id: str,
    projects_dir: Path,
    city_layers_cache: Path,
    skip_processing_mark: bool = False,
) -> dict:
    spec = get_model(model_id)
    manifest = _load_manifest_raw(project_id, projects_dir)
    city = manifest.get("cities", {}).get(city_key)
    if not city:
        raise ValueError(f"City not registered in project: {city_key}")

    address = city["address"]
    city_dir = _city_dir(project_id, city_key, projects_dir)
    uploads_dir = city_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    if not skip_processing_mark:
        mark_city_processing(
            project_id,
            city_key,
            model_id=model_id,
            projects_dir=projects_dir,
        )
        manifest = _load_manifest_raw(project_id, projects_dir)
        city = manifest["cities"][city_key]

    ctx = RunContext(
        address=address,
        city_dir=city_dir,
        uploads_dir=uploads_dir,
        city_layers_cache=city_layers_cache,
    )

    try:
        result = run_model(spec.id, saved_paths, ctx)
        run_stats = to_json_safe(result.stats)

        post = spec.enrich(result, ctx)
        if post.stats_updates:
            run_stats = to_json_safe({**run_stats, **post.stats_updates})

        primary_name = result.primary_raster
        if primary_name is None and spec.pick_primary is not None:
            primary_name = spec.pick_primary_file(saved_paths).name

        city.update(
            {
                "status": "ready",
                "model_id": spec.id,
                "run_stats": run_stats,
                "lst_stats": run_stats,
                "vector_fields": post.vector_fields or list(spec.vector_fields),
                "processed_at": _now_iso(),
                "primary_raster": primary_name,
                **post.city_fields,
            }
        )
        if result.logs:
            city["run_logs"] = result.logs[:8000]
    except Exception as exc:
        city["status"] = "error"
        city["error"] = str(exc)
        manifest["updated_at"] = _now_iso()
        _save_manifest(project_id, projects_dir, manifest)
        raise

    manifest["updated_at"] = _now_iso()
    _save_manifest(project_id, projects_dir, manifest)
    return get_project(project_id, projects_dir=projects_dir)


def run_city_lst_upload(
    project_id: str,
    city_key: str,
    saved_paths: list[Path],
    *,
    projects_dir: Path,
    city_layers_cache: Path,
) -> dict:
    """Backward-compatible wrapper for LST uploads."""
    return run_city_model_upload(
        project_id,
        city_key,
        saved_paths,
        model_id=DEFAULT_MODEL_ID,
        projects_dir=projects_dir,
        city_layers_cache=city_layers_cache,
    )


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
    from backend.projects.compare import compare_cities

    return compare_cities(project_id, question, projects_dir=projects_dir)
