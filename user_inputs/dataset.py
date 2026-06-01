"""Sensor / product family selection."""

from dataclasses import dataclass
from enum import Enum


class SensorFamily(str, Enum):
    HLS = "hls"
    LANDSAT = "landsat"
    SENTINEL = "sentinel"


@dataclass(frozen=True)
class DatasetSelection:
    sensor: SensorFamily
    years: list[int]
    aoi_path: str | None = None
