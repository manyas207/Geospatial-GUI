"""Narrative / tabular summary for the report panel."""

from typing import Any


def build(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Geospatial Analysis Summary",
        "sensor": context.get("sensor"),
        "years": context.get("years"),
        "accuracy": context.get("accuracy_report"),
        "notes": [],
    }
