"""Preprocessing configuration (shared by pipeline steps)."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PreprocessingConfig:
    input_dir: Path
    output_dir: Path
    stack_bands: bool = True
    clip_to_aoi: bool = True
    cloud_mask: bool = True
    mosaic: bool = True
    spectral_indices: list[str] = field(default_factory=lambda: ["ndvi"])
