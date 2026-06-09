"""GeoTIFF → PNG previews for the dashboard map (matplotlib, non-interactive backend)."""

from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.plot import reshape_as_image

PREVIEW_MAX_PX = 720


def _choose_cmap(path: Path, model: str) -> str:
    name = path.name.lower()
    if model == "obia" or "classified" in name or "segment" in name:
        return "tab20"
    return "inferno"


def render_geotiff_preview(
    tif_path: Path,
    png_path: Path,
    *,
    model: str = "lst",
) -> Path:
    """Write a downsampled PNG preview for a GeoTIFF."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    png_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(tif_path) as src:
        scale = max(src.width, src.height) / PREVIEW_MAX_PX
        out_h = max(1, int(src.height / scale))
        out_w = max(1, int(src.width / scale))

        # 3+ bands: treat as RGB; single band: colormap (thermal or classification).
        if src.count >= 3:
            data = src.read(
                [1, 2, 3],
                out_shape=(3, out_h, out_w),
                resampling=Resampling.bilinear,
                masked=True,
            )
            rgb = reshape_as_image(data)
            valid = ~np.any(rgb.mask, axis=2) if np.ma.isMaskedArray(rgb) else np.ones(rgb.shape[:2], dtype=bool)
            display = np.clip(rgb.filled(0), 0, 1) if np.ma.isMaskedArray(rgb) else np.clip(rgb, 0, 1)
            cmap = None
        else:
            band = src.read(
                1,
                out_shape=(out_h, out_w),
                resampling=Resampling.bilinear,
                masked=True,
            )
            valid = ~band.mask if np.ma.isMaskedArray(band) else np.ones(band.shape, dtype=bool)
            display = band
            cmap = _choose_cmap(tif_path, model)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    fig.patch.set_facecolor("#f4f7fa")
    ax.set_facecolor("#e8edf2")

    if cmap:
        plot_data = display.filled(np.nan) if np.ma.isMaskedArray(display) else display
        im = ax.imshow(plot_data, cmap=cmap, interpolation="nearest")
        fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    else:
        ax.imshow(display)

    ax.set_axis_off()
    ax.set_title(tif_path.stem, fontsize=10, color="#1a3348", pad=8)
    fig.tight_layout()
    fig.savefig(png_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return png_path
