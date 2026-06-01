"""Run preprocessing steps in order."""

from typing import Any

from preprocessing import clip, cloud_mask, mosaic, spectral_indices, stack_bands
from preprocessing.config import PreprocessingConfig


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
