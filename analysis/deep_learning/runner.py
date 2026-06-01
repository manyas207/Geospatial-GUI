"""Deep learning segmentation / classification."""

from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    context["analysis_type"] = "deep_learning"
    context["model_metrics"] = {}
    context["classification_path"] = "outputs/dl_classification.tif"
    return context
