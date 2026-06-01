"""Dispatch UI actions to workflow modules."""

from typing import Any

from accuracy.assessment import run_accuracy_assessment
from analysis.registry import AnalysisMethod, get_runner
from dashboard.builder import build_dashboard
from preprocessing.pipeline import PreprocessingConfig, run_preprocessing
from user_inputs.dataset import DatasetSelection, SensorFamily
from user_inputs.years import parse_years


def handle_request(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    """JSON-style RPC from the iframe UI (wire to pywebview js_api later)."""
    if action == "save_user_inputs":
        return _save_user_inputs(payload)
    if action == "run_preprocessing":
        return _run_preprocessing(payload)
    if action == "run_analysis":
        return _run_analysis(payload)
    if action == "run_accuracy":
        return _run_accuracy(payload)
    if action == "build_dashboard":
        return _build_dashboard(payload)
    return {"ok": False, "error": f"unknown action: {action}"}


def _save_user_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    selection = DatasetSelection(
        sensor=SensorFamily(payload["sensor"]),
        years=parse_years(payload["years"]),
        aoi_path=payload.get("aoi_path"),
    )
    return {"ok": True, "selection": selection.__dict__}


def _run_preprocessing(payload: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path

    config = PreprocessingConfig(
        input_dir=Path(payload["input_dir"]),
        output_dir=Path(payload["output_dir"]),
        stack_bands=payload.get("stack_bands", True),
        clip_to_aoi=payload.get("clip_to_aoi", True),
        cloud_mask=payload.get("cloud_mask", True),
        mosaic=payload.get("mosaic", True),
        spectral_indices=payload.get("spectral_indices", ["ndvi"]),
    )
    result = run_preprocessing(config, payload.get("context", {}))
    return {"ok": True, "context": result}


def _run_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    methods = payload.get("methods", [])
    context = payload.get("context", {})
    for name in methods:
        runner = get_runner(AnalysisMethod(name))
        context = runner(context)
    return {"ok": True, "context": context}


def _run_accuracy(payload: dict[str, Any]) -> dict[str, Any]:
    report = run_accuracy_assessment(
        payload.get("predictions"),
        payload.get("reference"),
    )
    return {"ok": True, "report": report.__dict__}


def _build_dashboard(payload: dict[str, Any]) -> dict[str, Any]:
    dash = build_dashboard(payload.get("context", {}), payload.get("output_dir", "data/outputs"))
    return {"ok": True, "dashboard": dash.__dict__}
