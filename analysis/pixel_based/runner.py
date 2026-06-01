"""Pixel-based classification (e.g. RF, SVM on raster pixels)."""

from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    context["analysis_type"] = "pixel_based"
    context["classification_path"] = "outputs/pixel_classification.tif"
    return context
