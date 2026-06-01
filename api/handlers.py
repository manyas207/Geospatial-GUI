"""Dispatch UI actions to workflow modules."""

import json
from pathlib import Path
from typing import Any

from accuracy.assessment import run_accuracy_assessment
from analysis.registry import AnalysisMethod, get_runner
from app.jobs.store import JobStatus, get_job_store
from dashboard.builder import build_dashboard
from preprocessing.config import PreprocessingConfig
from preprocessing.pipeline import run_preprocessing
from user_inputs.dataset import DatasetSelection, SensorFamily
from user_inputs.years import parse_years


def handle_request(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    """JSON-style RPC from the iframe UI (wire to HTTP later)."""
    if action == "create_job":
        return _create_job(payload)
    if action == "get_job":
        return _get_job(payload)
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


def _require_job_id(payload: dict[str, Any]) -> str:
    job_id = payload.get("job_id")
    if not job_id:
        raise ValueError("job_id is required")
    return str(job_id)


def _create_job(payload: dict[str, Any]) -> dict[str, Any]:
    store = get_job_store()
    job_id, context = store.create_job(payload.get("request"))
    return {"ok": True, "job_id": job_id, "context": context}


def _get_job(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = _require_job_id(payload)
    store = get_job_store()
    metadata = store.get_metadata(job_id)
    context = store.load_context(job_id)
    return {"ok": True, "job_id": job_id, "metadata": metadata, "context": context}


def _save_user_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = _require_job_id(payload)
    store = get_job_store()
    context = store.load_context(job_id)

    selection = DatasetSelection(
        sensor=SensorFamily(payload["sensor"]),
        years=parse_years(payload["years"]),
        aoi_path=payload.get("aoi_path"),
    )
    context["sensor"] = selection.sensor.value
    context["years"] = selection.years
    if selection.aoi_path:
        context["aoi_path"] = selection.aoi_path

    store.merge_metadata(
        job_id,
        {"request": {**store.get_metadata(job_id).get("request", {}), **payload}},
    )
    store.save_context(job_id, context)
    return {
        "ok": True,
        "job_id": job_id,
        "selection": {
            "sensor": selection.sensor.value,
            "years": selection.years,
            "aoi_path": selection.aoi_path,
        },
        "context": context,
    }


def _run_preprocessing(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = _require_job_id(payload)
    store = get_job_store()
    store.update_status(job_id, JobStatus.PREPROCESSING)
    context = store.load_context(job_id)
    paths = store.paths(job_id)

    config = PreprocessingConfig(
        input_dir=Path(payload.get("input_dir", paths.inputs)),
        output_dir=Path(payload.get("output_dir", paths.processed)),
        stack_bands=payload.get("stack_bands", True),
        clip_to_aoi=payload.get("clip_to_aoi", True),
        cloud_mask=payload.get("cloud_mask", True),
        mosaic=payload.get("mosaic", True),
        spectral_indices=payload.get("spectral_indices", ["ndvi"]),
    )
    merged = {**context, **payload.get("context", {})}
    result = run_preprocessing(config, merged)
    store.save_context(job_id, result)
    store.update_status(job_id, JobStatus.PENDING)
    return {"ok": True, "job_id": job_id, "context": result}


def _run_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = _require_job_id(payload)
    store = get_job_store()
    store.update_status(job_id, JobStatus.ANALYZING)
    context = store.load_context(job_id)
    methods = payload.get("methods", [])

    for name in methods:
        runner = get_runner(AnalysisMethod(name))
        context = runner(context)

    store.save_context(job_id, context)
    store.update_status(job_id, JobStatus.PENDING)
    return {"ok": True, "job_id": job_id, "context": context}


def _run_accuracy(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = _require_job_id(payload)
    store = get_job_store()
    store.update_status(job_id, JobStatus.ACCURACY)
    context = store.load_context(job_id)

    report = run_accuracy_assessment(
        payload.get("predictions"),
        payload.get("reference"),
    )
    context["accuracy_report"] = report.__dict__
    paths = store.paths(job_id)
    accuracy_file = paths.accuracy / "report.json"
    accuracy_file.write_text(json.dumps(report.__dict__, indent=2), encoding="utf-8")
    store.save_context(job_id, context)
    return {"ok": True, "job_id": job_id, "report": report.__dict__, "context": context}


def _build_dashboard(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = _require_job_id(payload)
    store = get_job_store()
    context = store.load_context(job_id)
    paths = store.paths(job_id)

    dash = build_dashboard(context, str(paths.exports))
    dashboard_json = paths.dashboard / "dashboard.json"
    dashboard_json.write_text(json.dumps(dash.__dict__, indent=2), encoding="utf-8")
    store.save_context(job_id, context)
    store.update_status(job_id, JobStatus.COMPLETED)
    return {
        "ok": True,
        "job_id": job_id,
        "dashboard": dash.__dict__,
        "dashboard_path": str(dashboard_json),
        "context": context,
    }
