"""Multi-city project routes."""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from backend.config import CITY_LAYERS_CACHE, PROJECTS_DIR
from backend.core.presets import DEMO_CITY_LST, PRESET_CITIES
from backend.core.schemas import ProjectCityRequest, ProjectCreateRequest, ProjectUpdateRequest
from backend.core.uploads import save_upload_files
from backend.projects.service import (
    create_project,
    get_city_geojson,
    get_city_gpkg_path,
    get_project,
    mark_city_processing,
    register_city,
    run_city_lst_upload,
    run_city_model_upload,
    update_project,
)

router = APIRouter(tags=["projects"])


def _run_city_model_background(
    project_id: str,
    city_key: str,
    saved_paths: list[Path],
    model_id: str,
) -> None:
    try:
        run_city_model_upload(
            project_id,
            city_key,
            saved_paths,
            model_id=model_id,
            projects_dir=PROJECTS_DIR,
            city_layers_cache=CITY_LAYERS_CACHE,
            skip_processing_mark=True,
        )
    except Exception:
        pass


def _run_city_lst_background(
    project_id: str,
    city_key: str,
    saved_paths: list[Path],
) -> None:
    _run_city_model_background(project_id, city_key, saved_paths, "lst")


@router.post("/api/projects")
async def create_lst_project(body: ProjectCreateRequest) -> JSONResponse:
    try:
        manifest = create_project(
            body.name,
            projects_dir=PROJECTS_DIR,
            model_id=body.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(content=manifest)


@router.get("/api/projects/presets")
async def project_presets() -> JSONResponse:
    return JSONResponse(content={"cities": PRESET_CITIES, "demo_lst": DEMO_CITY_LST})


@router.get("/api/projects/{project_id}")
async def get_lst_project(project_id: str) -> JSONResponse:
    try:
        return JSONResponse(content=get_project(project_id, projects_dir=PROJECTS_DIR))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/api/projects/{project_id}")
async def patch_lst_project(project_id: str, body: ProjectUpdateRequest) -> JSONResponse:
    try:
        return JSONResponse(
            content=update_project(
                project_id,
                name=body.name,
                projects_dir=PROJECTS_DIR,
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/projects/{project_id}/cities")
async def add_project_city(project_id: str, body: ProjectCityRequest) -> JSONResponse:
    try:
        return JSONResponse(
            content=register_city(
                project_id,
                body.address,
                month=body.month,
                year=body.year,
                projects_dir=PROJECTS_DIR,
                city_layers_cache=CITY_LAYERS_CACHE,
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/projects/{project_id}/cities/{city_key}/run")
async def upload_project_city_run(
    project_id: str,
    city_key: str,
    background_tasks: BackgroundTasks,
    model: str = "lst",
    files: list[UploadFile] = File(...),
) -> JSONResponse:
    city_dir = PROJECTS_DIR / project_id / "cities" / city_key / "uploads"
    try:
        saved = await save_upload_files(files, city_dir)
        mark_city_processing(
            project_id,
            city_key,
            model_id=model,
            projects_dir=PROJECTS_DIR,
        )
        background_tasks.add_task(
            _run_city_model_background,
            project_id,
            city_key,
            saved,
            model,
        )
        return JSONResponse(content=get_project(project_id, projects_dir=PROJECTS_DIR))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/projects/{project_id}/cities/{city_key}/lst")
async def upload_project_city_lst(
    project_id: str,
    city_key: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> JSONResponse:
    city_dir = PROJECTS_DIR / project_id / "cities" / city_key / "uploads"
    try:
        saved = await save_upload_files(files, city_dir)
        mark_city_processing(
            project_id,
            city_key,
            model_id="lst",
            projects_dir=PROJECTS_DIR,
        )
        background_tasks.add_task(
            _run_city_lst_background,
            project_id,
            city_key,
            saved,
        )
        return JSONResponse(content=get_project(project_id, projects_dir=PROJECTS_DIR))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/projects/{project_id}/cities/{city_key}/geojson")
async def project_city_geojson(project_id: str, city_key: str) -> JSONResponse:
    try:
        return JSONResponse(content=get_city_geojson(project_id, city_key, projects_dir=PROJECTS_DIR))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/projects/{project_id}/cities/{city_key}/gpkg")
async def project_city_gpkg(project_id: str, city_key: str) -> FileResponse:
    try:
        path = get_city_gpkg_path(project_id, city_key, projects_dir=PROJECTS_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, filename=path.name, media_type="application/geopackage+sqlite3")
