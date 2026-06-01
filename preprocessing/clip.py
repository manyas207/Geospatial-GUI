"""Clip imagery to the user AOI."""

from typing import Any

from preprocessing.pipeline import PreprocessingConfig


def run(context: dict[str, Any], config: PreprocessingConfig) -> dict[str, Any]:
    context["clipped_path"] = str(config.output_dir / "clipped.tif")
    return context
