"""Dispatch LST pipeline for project city uploads."""

from pathlib import Path

from models.lst_pipeline import run_lst


def run_lst_pipeline(raster_path: Path) -> dict:
    return run_lst(str(raster_path))
