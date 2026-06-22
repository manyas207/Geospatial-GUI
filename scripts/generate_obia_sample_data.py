#!/usr/bin/env python3
"""
Generate fake multispectral raster + training shapefile for OBIA POC runs.

Default city: Dallas, TX (demo centroid + census tracts). Output is compatible with
models/obia_core.py and the web OBIA upload flow.

Usage:
    python scripts/generate_obia_sample_data.py
    python scripts/generate_obia_sample_data.py --city "Round Rock, TX" --out sample_data/obia_round_rock
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_bounds
from shapely.geometry import box

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.layers.geocode import geocode_address

# HLS L30 band order: coastal, blue, green, red, nir, swir1, swir2
BAND_NAMES = ("coastal", "blue", "green", "red", "nir", "swir1", "swir2")

# Spectral reflectance templates (0–1) per land-cover macroclass
CLASS_PROFILES: dict[str, dict[str, float]] = {
    "urban": {"coastal": 0.06, "blue": 0.07, "green": 0.09, "red": 0.12, "nir": 0.18, "swir1": 0.28, "swir2": 0.22},
    "vegetation": {"coastal": 0.04, "blue": 0.05, "green": 0.12, "red": 0.06, "nir": 0.42, "swir1": 0.18, "swir2": 0.10},
    "water": {"coastal": 0.03, "blue": 0.06, "green": 0.08, "red": 0.04, "nir": 0.03, "swir1": 0.02, "swir2": 0.02},
    "bare_soil": {"coastal": 0.10, "blue": 0.12, "green": 0.16, "red": 0.22, "nir": 0.28, "swir1": 0.30, "swir2": 0.26},
}

MACROCLASS_IDS = {name: idx + 1 for idx, name in enumerate(CLASS_PROFILES)}


def geocode_city(address: str) -> tuple[float, float]:
    """Resolve City, ST to WGS84 lat/lon."""
    result = geocode_address(address)
    return float(result["latitude"]), float(result["longitude"])


def _zone_bounds(
    west: float,
    south: float,
    east: float,
    north: float,
    *,
    col: int,
    row: int,
    n_cols: int = 2,
    n_rows: int = 2,
) -> tuple[float, float, float, float]:
    """Return WGS84 bounds for one cell in an n_cols × n_rows grid over the scene."""
    width = (east - west) / n_cols
    height = (north - south) / n_rows
    x0 = west + col * width
    y0 = south + (n_rows - 1 - row) * height
    return x0, y0, x0 + width, y0 + height


def build_multispectral_array(height: int, width: int, rng: np.random.Generator) -> np.ndarray:
    """7-band float32 stack with four distinct land-cover zones + noise."""
    zones = list(CLASS_PROFILES.keys())
    data = np.zeros((7, height, width), dtype=np.float32)

    for row in range(2):
        for col in range(2):
            class_name = zones[row * 2 + col]
            profile = CLASS_PROFILES[class_name]
            r0, r1 = row * (height // 2), (row + 1) * (height // 2)
            c0, c1 = col * (width // 2), (col + 1) * (width // 2)

            for band_idx, band_name in enumerate(BAND_NAMES):
                base = profile[band_name]
                noise = rng.normal(0, 0.015, size=(r1 - r0, c1 - c0))
                data[band_idx, r0:r1, c0:c1] = np.clip(base + noise, 0.0, 1.0)

    return data


def build_training_samples(
    west: float,
    south: float,
    east: float,
    north: float,
    crs: str,
) -> gpd.GeoDataFrame:
    """Small polygon training ROIs — several per macroclass, centered in each raster zone."""
    zones = list(CLASS_PROFILES.keys())
    rows: list[dict] = []
    roi_id = 1

    for idx, class_name in enumerate(zones):
        row, col = divmod(idx, 2)
        x0, y0, x1, y1 = _zone_bounds(west, south, east, north, col=col, row=row)
        zone_w = x1 - x0
        zone_h = y1 - y0
        # Three ~250 m squares per zone for more labeled segments
        offsets = [(-0.2, -0.2), (0.0, 0.0), (0.2, 0.2)]
        half_deg = min(zone_w, zone_h) * 0.08

        for dx, dy in offsets:
            cx = x0 + zone_w * (0.5 + dx)
            cy = y0 + zone_h * (0.5 + dy)
            rows.append(
                {
                    "roi_id": roi_id,
                    "macroclass": MACROCLASS_IDS[class_name],
                    "class_name": class_name,
                    "geometry": box(cx - half_deg, cy - half_deg, cx + half_deg, cy + half_deg),
                }
            )
            roi_id += 1

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    return gdf.to_crs(crs)


def generate(
    *,
    city: str,
    out_dir: Path,
    width: int,
    height: int,
    pixel_size_m: float,
    utm_epsg: int,
    seed: int,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lat, lon = geocode_city(city)
    rng = np.random.default_rng(seed)

    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{utm_epsg}", always_xy=True)
    from_utm = Transformer.from_crs(f"EPSG:{utm_epsg}", "EPSG:4326", always_xy=True)

    center_x, center_y = to_utm.transform(lon, lat)
    half_w = (width * pixel_size_m) / 2
    half_h = (height * pixel_size_m) / 2
    west_utm = center_x - half_w
    east_utm = center_x + half_w
    south_utm = center_y - half_h
    north_utm = center_y + half_h

    west, south = from_utm.transform(west_utm, south_utm)
    east, north = from_utm.transform(east_utm, north_utm)

    crs = f"EPSG:{utm_epsg}"
    transform = from_bounds(west_utm, south_utm, east_utm, north_utm, width, height)
    data = build_multispectral_array(height, width, rng)

    raster_path = out_dir / "obia_multispectral.tif"
    meta = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 7,
        "width": width,
        "height": height,
        "crs": crs,
        "transform": transform,
        "nodata": None,
    }
    with rasterio.open(raster_path, "w", **meta) as dst:
        dst.write(data)
        for i, name in enumerate(BAND_NAMES, start=1):
            dst.set_band_description(i, name)

    samples = build_training_samples(west, south, east, north, crs)
    shp_path = out_dir / "training_rois.shp"
    samples.to_file(shp_path)

    manifest = {
        "city": city,
        "center_wgs84": {"lat": lat, "lon": lon},
        "crs": crs,
        "bounds_wgs84": [west, south, east, north],
        "raster": raster_path.name,
        "training_shapefile": shp_path.name,
        "macroclasses": MACROCLASS_IDS,
        "width": width,
        "height": height,
        "pixel_size_m": pixel_size_m,
        "seed": seed,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "raster": raster_path,
        "shapefile": shp_path,
        "manifest": manifest_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate OBIA-compatible fake city data.")
    parser.add_argument("--city", default="Dallas, TX", help="US city for geocoding (City, ST)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("sample_data/obia_dallas_tx"),
        help="Output directory",
    )
    parser.add_argument("--width", type=int, default=320, help="Raster width in pixels")
    parser.add_argument("--height", type=int, default=320, help="Raster height in pixels")
    parser.add_argument("--pixel-size", type=float, default=30.0, help="Pixel size in meters")
    parser.add_argument("--utm-epsg", type=int, default=32614, help="UTM EPSG (32614 = Texas central)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    paths = generate(
        city=args.city,
        out_dir=args.out,
        width=args.width,
        height=args.height,
        pixel_size_m=args.pixel_size,
        utm_epsg=args.utm_epsg,
        seed=args.seed,
    )

    print(f"Generated OBIA sample data for {args.city!r}")
    print(f"  Raster:     {paths['raster']}")
    print(f"  Shapefile:  {paths['shapefile']} (+ .shx, .dbf, .prj)")
    print(f"  Manifest:   {paths['manifest']}")
    print()
    print("POC steps:")
    print(f"  1. Start server: python serve.py")
    print("  2. Ask -> model: OBIA Land Cover")
    print(f"  3. City address: {args.city}")
    print(f"  4. Upload: {paths['raster'].name} + training_rois.shp/.shx/.dbf/.prj")
    print("  5. Optional .env: OBIA_N_SEGMENTS=10000 for faster runs")


if __name__ == "__main__":
    main()
