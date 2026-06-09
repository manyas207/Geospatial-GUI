"""FastAPI entry point: uploads, NL routing, pipeline dispatch, and static web UI.

Request flow:
  POST /api/query  → save files → parse_intent (Ollama) → run LST/OBIA → dashboard JSON
  POST /api/followup → Ollama answers from prior dashboard context
  GET  /api/artifacts/{id}/download|preview → serve pipeline outputs via encoded paths
"""

import re
import uuid
from pathlib import Path

import rasterio
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.artifacts import build_artifacts, decode_artifact_path
from backend.constants import ALLOWED_UPLOAD_SUFFIXES, RASTER_SUFFIXES
from backend.dashboard_chat import answer_about_dashboard
from backend.nlu import parse_intent
from backend.router import run as run_model
from backend.schemas import Artifact, FollowupRequest, FollowupResponse, QueryResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Geospatial Dashboard API")


def _band_count(path: Path) -> int:
    try:
        with rasterio.open(path) as src:
            return src.count
    except Exception:
        return 0


def _is_raster(path: Path) -> bool:
    return path.suffix.lower() in RASTER_SUFFIXES


def _raster_paths(paths: list[Path]) -> list[Path]:
    return [path for path in paths if _is_raster(path)]


def _pick_primary_raster(paths: list[Path], intent: str) -> Path:
    """Choose which GeoTIFF to pass into the pipeline when several were uploaded."""
    rasters = _raster_paths(paths)
    if not rasters:
        raise HTTPException(
            status_code=400,
            detail="At least one GeoTIFF is required. Shapefiles alone are not enough.",
        )

    if intent == "lst":
        # Prefer Landsat thermal band; lst_pipeline finds SR_B4/B5 siblings in the folder.
        for path in rasters:
            upper = path.name.upper()
            if "ST_B10" in upper or "ST_B11" in upper:
                return path
        # Else use the richest multi-band stack (3-band or HLS-style 10+ band).
        multi_band = [path for path in rasters if _band_count(path) >= 3]
        if multi_band:
            return max(multi_band, key=_band_count)
        return rasters[0]

    if intent == "obia":
        # More bands → better segmentation features; shapefile is found separately.
        return max(rasters, key=_band_count)

    return rasters[0]


async def _save_uploads(files: list[UploadFile]) -> tuple[Path, list[Path]]:
    """Persist multipart uploads under data/{uuid}/; shapefile parts must share this folder."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    upload_id = uuid.uuid4().hex
    upload_dir = DATA_DIR / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []

    for upload in files:
        if not upload.filename:
            continue

        suffix = Path(upload.filename).suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type: {upload.filename}. "
                    "Use GeoTIFF (.tif) and/or shapefile components (.shp, .shx, .dbf, .prj)."
                ),
            )

        # Sanitize filenames so path traversal and odd characters cannot reach disk paths.
        safe_name = re.sub(r"[^\w.\-]", "_", Path(upload.filename).name)
        dest_path = upload_dir / safe_name

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Uploaded file is empty: {upload.filename}")

        dest_path.write_bytes(content)
        saved_paths.append(dest_path)

    if not saved_paths:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    if not _raster_paths(saved_paths):
        raise HTTPException(
            status_code=400,
            detail="Upload at least one GeoTIFF. For OBIA, add training shapefile components (.shp, .shx, .dbf).",
        )

    return upload_dir, saved_paths


@app.post("/api/query", response_model=QueryResponse)
async def query(
    question: str = Form(...),
    files: list[UploadFile] = File(...),
) -> QueryResponse:
    upload_dir, saved_paths = await _save_uploads(files)

    try:
        intent = parse_intent(question)
        raster_path = _pick_primary_raster(saved_paths, intent)
        result = run_model(intent, raster_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    model_label = "LST" if intent == "lst" else "OBIA"
    file_names = ", ".join(path.name for path in saved_paths)
    summary = (
        f"Routed to {model_label} based on: {question.strip()[:120]}. "
        f"Files ({len(saved_paths)}): {file_names}"
    )

    pipeline_stats = result.get("stats", {})
    # Pipelines write to data/{upload_id}/results/{raster_stem}/ alongside the upload.
    results_dir = raster_path.parent / "results" / raster_path.stem
    artifact_rows = build_artifacts(
        pipeline_stats,
        model=intent,
        results_dir=results_dir,
        data_dir=DATA_DIR,
    )

    return QueryResponse(
        model=intent,
        summary=summary,
        stats={
            **pipeline_stats,
            # Internal keys (hidden in the UI) for debugging and artifact resolution.
            "upload_dir": str(upload_dir),
            "primary_raster": raster_path.name,
            "file_count": len(saved_paths),
        },
        logs=result.get("logs", ""),
        artifacts=[Artifact(**row) for row in artifact_rows],
    )


@app.get("/api/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str) -> FileResponse:
    path = decode_artifact_path(artifact_id, DATA_DIR)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@app.get("/api/artifacts/{artifact_id}/preview")
async def preview_artifact(artifact_id: str) -> FileResponse:
    path = decode_artifact_path(artifact_id, DATA_DIR)
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Preview not available for this file type.")
    return FileResponse(path, media_type="image/png")


@app.post("/api/followup", response_model=FollowupResponse)
async def followup(body: FollowupRequest) -> FollowupResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    try:
        answer = answer_about_dashboard(question, body.context.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FollowupResponse(answer=answer)


# html=True serves index.html for / and other SPA-style paths.
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
