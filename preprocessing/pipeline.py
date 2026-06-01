"""Run preprocessing steps in order."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from preprocessing import clip, cloud_mask, mosaic, spectral_indices, stack_bands


@dataclass
class PreprocessingConfig:
    input_dir: Path
    output_dir: Path
    stack_bands: bool = True
    clip_to_aoi: bool = True
    cloud_mask: bool = True
    mosaic: bool = True
    spectral_indices: list[str] = field(default_factory=lambda: ["ndvi"])


def run_preprocessing(config: PreprocessingConfig, context: dict[str, Any]) -> dict[str, Any]:
    result = dict(context)
    if config.stack_bands:
        result = stack_bands.run(result, config)
    if config.clip_to_aoi:
        result = clip.run(result, config)
    if config.cloud_mask:
        result = cloud_mask.run(result, config)
    if config.mosaic:
        result = mosaic.run(result, config)
    if config.spectral_indices:
        result = spectral_indices.run(result, config)
    return result
