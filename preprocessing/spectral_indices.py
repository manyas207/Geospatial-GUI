"""Spectral index generation (NDVI, NDWI, custom formulas)."""

from typing import Any

from preprocessing.config import PreprocessingConfig

INDEX_REGISTRY: dict[str, str] = {
    "ndvi": "(nir - red) / (nir + red)",
    "ndwi": "(green - nir) / (green + nir)",
}


def run(context: dict[str, Any], config: PreprocessingConfig) -> dict[str, Any]:
    context["indices"] = {name: INDEX_REGISTRY.get(name, name) for name in config.spectral_indices}
    return context
