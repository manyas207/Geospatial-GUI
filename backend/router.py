"""Dispatch parsed intent to the LST or OBIA pipeline wrapper."""

from pathlib import Path

from models.lst_pipeline import run_lst
from models.obia_pipeline import run_obia


def run(intent: str, raster_path: Path) -> dict:
    path = str(raster_path)

    if intent == "lst":
        return run_lst(path)
    if intent == "obia":
        return run_obia(path)

    raise ValueError(f"Unknown model: {intent}")
