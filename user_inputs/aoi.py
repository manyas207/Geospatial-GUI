"""Area of interest: vector file or drawn geometry."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AreaOfInterest:
    source_path: Path | None = None
    geometry: Any = None  # shapely geometry once wired

    @property
    def is_valid(self) -> bool:
        return self.source_path is not None or self.geometry is not None


def load_aoi(path: str | Path) -> AreaOfInterest:
    return AreaOfInterest(source_path=Path(path))
