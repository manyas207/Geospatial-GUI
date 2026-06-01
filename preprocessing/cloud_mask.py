"""Cloud and shadow masking."""

from typing import Any

from preprocessing.config import PreprocessingConfig


def run(context: dict[str, Any], config: PreprocessingConfig) -> dict[str, Any]:
    context["masked_path"] = str(config.output_dir / "masked.tif")
    return context
