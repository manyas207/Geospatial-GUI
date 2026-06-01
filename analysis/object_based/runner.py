"""Object-based image analysis (segment + classify objects)."""

from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    context["analysis_type"] = "object_based"
    context["classification_path"] = "outputs/object_classification.gpkg"
    return context
