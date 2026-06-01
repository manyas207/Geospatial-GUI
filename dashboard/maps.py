"""Map layers and legends for the dashboard."""

from typing import Any


def build(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "basemap": "osm",
        "layers": [
            {"id": "aoi", "type": "vector", "visible": True},
            {"id": "classification", "type": "raster", "visible": True},
        ],
        "extent": context.get("aoi_bounds"),
    }
