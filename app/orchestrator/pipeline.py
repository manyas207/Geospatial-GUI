"""High-level workflow stages matching the UI wizard."""

from enum import Enum
from typing import Any


class PipelineStage(str, Enum):
    USER_INPUTS = "user_inputs"
    PREPROCESSING = "preprocessing"
    ANALYSIS = "analysis"
    ACCURACY = "accuracy"
    DASHBOARD = "dashboard"


class Pipeline:
    """Coordinates step modules; state is passed from the API layer."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}
        self.stage = PipelineStage.USER_INPUTS

    def advance(self, stage: PipelineStage) -> None:
        self.stage = stage
