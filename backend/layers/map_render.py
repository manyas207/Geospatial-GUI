"""Render tract choropleth maps as PNG previews (no client-side map library needed)."""

from __future__ import annotations

from pathlib import Path


def render_tract_map(
    geojson: dict,
    png_path: Path,
    *,
    field: str | None = None,
    cmap: str = "YlOrRd",
    title: str = "",
) -> Path:
    """Draw census tracts to a PNG; optionally color by an attribute column."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import geopandas as gpd

    png_path.parent.mkdir(parents=True, exist_ok=True)

    gdf = gpd.GeoDataFrame.from_features(geojson.get("features") or [], crs="EPSG:4326")
    if gdf.empty:
        raise ValueError("No tract geometries to render.")

    fig, ax = plt.subplots(figsize=(9, 7), dpi=110)
    fig.patch.set_facecolor("#f4f7fa")

    plot_field = field if field and field in gdf.columns else None
    if plot_field:
        gdf.plot(
            column=plot_field,
            cmap=cmap,
            linewidth=0.25,
            edgecolor="#ffffff",
            ax=ax,
            legend=True,
            legend_kwds={"shrink": 0.55, "pad": 0.02},
            missing_kwds={"color": "#e8edf2", "edgecolor": "#ffffff", "linewidth": 0.2},
        )
    else:
        gdf.plot(
            color="#5a9ab8",
            linewidth=0.35,
            edgecolor="#ffffff",
            ax=ax,
            alpha=0.65,
        )

    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=10, color="#1a3348", pad=8)
    fig.tight_layout()
    fig.savefig(png_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return png_path
