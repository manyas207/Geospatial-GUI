"""Discover and serve reference GeoTIFFs (e.g. gridded population) for the dashboard.

Set REFERENCE_DATA_DIR to a folder of GeoTIFFs on disk. Layers appear in the map
viewer and are auto-attached to LST/OBIA results when extents overlap.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
from pathlib import Path

import numpy as np
import rasterio
from fastapi import HTTPException
from rasterio.warp import transform_bounds

from backend.constants import RASTER_SUFFIXES
from backend.preview import render_geotiff_preview

# Human-readable labels from common filename tokens.
_LABEL_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"pop(ulation)?", re.I), "Population"),
    (re.compile(r"density", re.I), "Population density"),
    (re.compile(r"income", re.I), "Income"),
    (re.compile(r"census|tract", re.I), "Census tract"),
    (re.compile(r"grid(ded)?", re.I), "Gridded data"),
    (re.compile(r"_B01\b|band.?1", re.I), "VNIR band 1"),
    (re.compile(r"_B02\b|band.?2", re.I), "VNIR band 2"),
    (re.compile(r"_B03N?\b|band.?3", re.I), "VNIR band 3"),
    (re.compile(r"QA_DataPlane2?", re.I), "QA data plane"),
]


def reference_data_dir() -> Path | None:
    raw = os.environ.get("REFERENCE_DATA_DIR", "").strip()
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw).expanduser())
    candidates.append(Path.home() / "Desktop" / "Gridded Population Data")

    for candidate in candidates:
        path = candidate.resolve()
        if path.is_dir():
            return path
    return None


def _label_for(path: Path) -> str:
    name = path.stem
    if "QA_DataPlane" in name:
        return "QA data plane 2" if name.endswith("2") else "QA data plane"
    for pattern, label in _LABEL_RULES:
        if pattern.search(name):
            return label
    return name.replace("_", " ")


def _is_population_like(path: Path) -> bool:
    name = path.name.lower()
    return any(token in name for token in ("pop", "density", "census", "grid", "demog"))


def encode_layer_id(path: Path, root: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    token = base64.urlsafe_b64encode(str(rel).encode("utf-8")).decode("utf-8")
    return token.rstrip("=")


def decode_layer_path(token: str, root: Path) -> Path:
    padding = "=" * (-len(token) % 4)
    try:
        rel = base64.urlsafe_b64decode((token + padding).encode("utf-8")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid layer id.") from exc

    full = (root / rel).resolve()
    if not str(full).startswith(str(root.resolve())):
        raise HTTPException(status_code=403, detail="Layer path not allowed.")
    if not full.exists():
        raise HTTPException(status_code=404, detail="Layer not found.")
    if full.suffix.lower() not in RASTER_SUFFIXES:
        raise HTTPException(status_code=400, detail="Not a raster layer.")
    return full


def _preview_cache_path(tif_path: Path, cache_dir: Path) -> Path:
    digest = hashlib.sha256(str(tif_path.resolve()).encode("utf-8")).hexdigest()[:20]
    return cache_dir / f"{digest}.png"


def _raster_stats(path: Path) -> dict:
    with rasterio.open(path) as src:
        band = src.read(1, masked=True)
        valid = band.compressed()
        stats: dict = {
            "crs": str(src.crs) if src.crs else None,
            "width": src.width,
            "height": src.height,
            "bands": src.count,
        }
        if valid.size:
            stats["min"] = round(float(valid.min()), 4)
            stats["max"] = round(float(valid.max()), 4)
            stats["mean"] = round(float(valid.mean()), 4)
            stats["valid_pixels"] = int(valid.size)
        return stats


def _bounds_wgs84(path: Path) -> tuple[float, float, float, float] | None:
    with rasterio.open(path) as src:
        if not src.crs:
            return None
        west, south, east, north = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        return west, south, east, north


def bounds_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    aw, as_, ae, an = a
    bw, bs, be, bn = b
    return not (ae < bw or be < aw or an < bs or bn < as_)


def list_layers(*, cache_dir: Path) -> list[dict]:
    root = reference_data_dir()
    if root is None:
        return []

    cache_dir.mkdir(parents=True, exist_ok=True)
    layers: list[dict] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in RASTER_SUFFIXES:
            continue

        layer_id = encode_layer_id(path, root)
        preview_path = _preview_cache_path(path, cache_dir)
        if not preview_path.exists():
            try:
                model = "population" if _is_population_like(path) else "reference"
                render_geotiff_preview(path, preview_path, model=model)
            except Exception:
                preview_path = None

        layers.append(
            {
                "id": layer_id,
                "label": _label_for(path),
                "filename": path.name,
                "kind": "reference",
                "category": "population" if _is_population_like(path) else "reference",
                "stats": _raster_stats(path),
                "bounds_wgs84": _bounds_wgs84(path),
                "preview_url": f"/api/reference-layers/{layer_id}/preview"
                if preview_path and preview_path.exists()
                else None,
                "download_url": f"/api/reference-layers/{layer_id}/download",
            }
        )

    return layers


def layers_overlapping_raster(raster_path: Path, *, cache_dir: Path) -> list[dict]:
    with rasterio.open(raster_path) as src:
        if not src.crs:
            return []
        target = transform_bounds(src.crs, "EPSG:4326", *src.bounds)

    return [
        layer
        for layer in list_layers(cache_dir=cache_dir)
        if layer.get("bounds_wgs84") and bounds_overlap(tuple(layer["bounds_wgs84"]), target)
    ]


def resolve_preview(layer_id: str, *, cache_dir: Path) -> Path:
    root = reference_data_dir()
    if root is None:
        raise HTTPException(status_code=404, detail="Reference data not configured.")

    path = decode_layer_path(layer_id, root)
    preview_path = _preview_cache_path(path, cache_dir)
    if not preview_path.exists():
        model = "population" if _is_population_like(path) else "reference"
        render_geotiff_preview(path, preview_path, model=model)
    return preview_path


def resolve_download(layer_id: str) -> Path:
    root = reference_data_dir()
    if root is None:
        raise HTTPException(status_code=404, detail="Reference data not configured.")
    return decode_layer_path(layer_id, root)
