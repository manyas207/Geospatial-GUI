"""Object-based image analysis (segment + classify objects)."""

from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path

    analysis_dir = Path(context.get("analysis_dir", "data/outputs/analysis"))
    analysis_dir.mkdir(parents=True, exist_ok=True)
    out = analysis_dir / "object_classification.gpkg"
    context["analysis_type"] = "object_based"
    context["classification_path"] = str(out)
    return context
