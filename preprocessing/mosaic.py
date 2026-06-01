"""Mosaic tiles or dates into a seamless composite."""

from typing import Any

from preprocessing.config import PreprocessingConfig


def run(context: dict[str, Any], config: PreprocessingConfig) -> dict[str, Any]:
    context["mosaic_path"] = str(config.output_dir / "mosaic.tif")
    return context
