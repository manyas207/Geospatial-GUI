"""Assemble dashboard sections for the UI."""

from dataclasses import dataclass, field
from typing import Any

from dashboard import classifications, maps, model_performance, summary_report
from dashboard.exports import csv_export, geopackage_export, pdf_export


@dataclass
class DashboardPayload:
    maps: dict[str, Any] = field(default_factory=dict)
    classifications: dict[str, Any] = field(default_factory=dict)
    model_performance: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    download_urls: dict[str, str] = field(default_factory=dict)


def build_dashboard(context: dict[str, Any], output_dir: str) -> DashboardPayload:
    payload = DashboardPayload(
        maps=maps.build(context),
        classifications=classifications.build(context),
        model_performance=model_performance.build(context),
        summary=summary_report.build(context),
    )
    payload.download_urls = {
        "pdf": pdf_export.export(context, output_dir),
        "csv": csv_export.export(context, output_dir),
        "geopackage": geopackage_export.export(context, output_dir),
    }
    return payload
