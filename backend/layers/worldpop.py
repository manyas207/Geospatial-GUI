"""WorldPop constrained population raster — clip by bbox and render map preview.

Uses the public USA 2020 COG (no API key). NASA SEDAC GPW can be added later via
EARTHDATA_API_KEY for alternate sources.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.windows import from_bounds as window_from_bounds

WORLDPOP_USA_COG = (
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/"
    "2020/USA/usa_ppp_2020_constrained.tif"
)
PREVIEW_MAX_PX = 512


def _bounds_key(bounds: tuple[float, float, float, float]) -> str:
    raw = ",".join(f"{v:.4f}" for v in bounds)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def bounds_from_geojson(geojson: dict) -> tuple[float, float, float, float]:
    """Compute WGS84 bounds from a GeoJSON FeatureCollection."""
    minx = miny = float("inf")
    maxx = maxy = float("-inf")

    def walk_coords(obj):
        nonlocal minx, miny, maxx, maxy
        if isinstance(obj, (list, tuple)):
            if obj and isinstance(obj[0], (int, float)) and len(obj) >= 2:
                x, y = float(obj[0]), float(obj[1])
                minx, maxx = min(minx, x), max(maxx, x)
                miny, maxy = min(miny, y), max(maxy, y)
            else:
                for item in obj:
                    walk_coords(item)

    for feature in geojson.get("features") or []:
        walk_coords((feature.get("geometry") or {}).get("coordinates"))

    if minx == float("inf"):
        raise ValueError("Could not compute bounds from GeoJSON.")

    pad = 0.02
    return minx - pad, miny - pad, maxx + pad, maxy + pad


def render_worldpop_preview(
    bounds_wgs84: tuple[float, float, float, float],
    png_path: Path,
) -> dict:
    """Clip WorldPop USA raster to bounds and write a PNG preview for Leaflet."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    west, south, east, north = bounds_wgs84
    png_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(WORLDPOP_USA_COG) as src:
        window = window_from_bounds(west, south, east, north, src.transform)
        scale = max(window.width, window.height) / PREVIEW_MAX_PX
        out_h = max(1, int(window.height / scale))
        out_w = max(1, int(window.width / scale))

        data = src.read(
            1,
            window=window,
            out_shape=(out_h, out_w),
            resampling=Resampling.bilinear,
            masked=True,
        )
        transform = from_bounds(west, south, east, north, out_w, out_h)

    plot_data = data.filled(np.nan) if np.ma.isMaskedArray(data) else data
    valid = plot_data[np.isfinite(plot_data) & (plot_data > 0)]

    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    fig.patch.set_facecolor("#f4f7fa")
    im = ax.imshow(plot_data, cmap="YlOrRd", interpolation="nearest")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="Population")
    ax.set_axis_off()
    ax.set_title("WorldPop 2020 (gridded)", fontsize=10, color="#1a3348", pad=8)
    fig.tight_layout()
    fig.savefig(png_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return {
        "bounds": [west, south, east, north],
        "max_population": round(float(valid.max()), 1) if valid.size else None,
        "mean_population": round(float(valid.mean()), 1) if valid.size else None,
        "source": "WorldPop 2020 constrained (USA)",
        "cog_url": WORLDPOP_USA_COG,
    }


def get_or_create_worldpop_preview(
    bounds_wgs84: tuple[float, float, float, float],
    cache_dir: Path,
) -> tuple[Path | None, dict]:
    """Return cached PNG path and metadata, generating on first request."""
    key = _bounds_key(bounds_wgs84)
    png_path = cache_dir / f"worldpop_{key}.png"
    meta_path = cache_dir / f"worldpop_{key}.json"

    if png_path.exists():
        meta = {}
        if meta_path.exists():
            import json

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return png_path, meta

    try:
        meta = render_worldpop_preview(bounds_wgs84, png_path)
        import json

        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        return png_path, meta
    except Exception as exc:
        return None, {"error": str(exc), "source": "WorldPop"}
