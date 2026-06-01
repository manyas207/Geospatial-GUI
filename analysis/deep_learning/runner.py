"""Deep learning segmentation / classification."""

from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path

    analysis_dir = Path(context.get("analysis_dir", "data/outputs/analysis"))
    analysis_dir.mkdir(parents=True, exist_ok=True)
    out = analysis_dir / "dl_classification.tif"
    context["analysis_type"] = "deep_learning"
    context["model_metrics"] = {}
    context["classification_path"] = str(out)
    return context
