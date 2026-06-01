"""Register and dispatch analysis implementations."""

from enum import Enum
from typing import Any, Callable

from analysis.deep_learning import run as run_dl
from analysis.object_based import run as run_object
from analysis.pixel_based import run as run_pixel

Runner = Callable[[dict[str, Any]], dict[str, Any]]


class AnalysisMethod(str, Enum):
    PIXEL = "pixel_based"
    OBJECT = "object_based"
    DEEP_LEARNING = "deep_learning"


_REGISTRY: dict[AnalysisMethod, Runner] = {
    AnalysisMethod.PIXEL: run_pixel,
    AnalysisMethod.OBJECT: run_object,
    AnalysisMethod.DEEP_LEARNING: run_dl,
}


def list_methods() -> list[str]:
    return [m.value for m in AnalysisMethod]


def get_runner(method: str | AnalysisMethod) -> Runner:
    key = AnalysisMethod(method) if isinstance(method, str) else method
    return _REGISTRY[key]
