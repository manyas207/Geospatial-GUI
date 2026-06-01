"""Export summary report as PDF."""

from typing import Any


def export(context: dict[str, Any], output_dir: str) -> str:
    _ = context
    return f"{output_dir}/report.pdf"
