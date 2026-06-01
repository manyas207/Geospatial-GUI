"""Classification summaries and symbology."""

from typing import Any


def build(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": context.get("classification_path"),
        "legend": context.get("class_legend", []),
        "area_by_class": context.get("area_by_class", {}),
    }
