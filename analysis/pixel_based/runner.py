"""Pixel-based classification (e.g. RF, SVM on raster pixels)."""

from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path

    analysis_dir = Path(context.get("analysis_dir", "data/outputs/analysis"))
    analysis_dir.mkdir(parents=True, exist_ok=True)
    out = analysis_dir / "pixel_classification.tif"
    context["analysis_type"] = "pixel_based"
    context["classification_path"] = str(out)
    return context
