"""Dispatch registered analysis models for project city uploads."""

from __future__ import annotations

from pathlib import Path

from models.contract import ModelResult, RunContext
from models.registry import get_model


def run_model(model_id: str, paths: list[Path], ctx: RunContext) -> ModelResult:
    """Run a registered model on uploaded files."""
    spec = get_model(model_id)
    return spec.execute(paths, ctx)


def run_lst_pipeline(raster_path: Path) -> dict:
    """Backward-compatible LST entry point (single raster, no tract enrichment)."""
    from models.lst_pipeline import run_lst

    return run_lst(str(raster_path))
