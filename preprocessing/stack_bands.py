"""Stack multispectral bands into a single raster stack."""

from typing import Any

from preprocessing.config import PreprocessingConfig


def run(context: dict[str, Any], config: PreprocessingConfig) -> dict[str, Any]:
    # TODO: implement band stacking (rasterio / xarray)
    context["stacked_path"] = str(config.output_dir / "stacked.tif")
    return context
