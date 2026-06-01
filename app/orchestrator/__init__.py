"""Pipeline orchestration across user inputs → preprocessing → analysis → dashboard."""

from app.orchestrator.pipeline import Pipeline, PipelineStage

__all__ = ["Pipeline", "PipelineStage"]
