"""Comparative model performance (pixel vs object vs DL)."""

from typing import Any


def build(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "methods": context.get("compared_methods", []),
        "metrics": context.get("model_metrics", {}),
        "charts": ["bar_accuracy", "bar_f1"],
    }
