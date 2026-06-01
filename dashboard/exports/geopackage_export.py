"""Export vector outputs as GeoPackage."""

from typing import Any


def export(context: dict[str, Any], output_dir: str) -> str:
    _ = context
    return f"{output_dir}/results.gpkg"
