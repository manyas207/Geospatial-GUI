"""Dispatch registered analysis models for project city uploads."""

from __future__ import annotations

from pathlib import Path

from models.contract import ModelResult, RunContext
from models.registry import get_model


def run_model(model_id: str, paths: list[Path], ctx: RunContext) -> ModelResult:
    """Run a registered model on uploaded files."""
    spec = get_model(model_id)
    return spec.execute(paths, ctx)
