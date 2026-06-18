"""Analysis model registry routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.core.schemas import ModelInfoSchema, ModelsListResponse
from models.registry import list_models_public

router = APIRouter(tags=["models"])


@router.get("/api/models")
async def list_analysis_models() -> JSONResponse:
    payload = ModelsListResponse(
        models=[ModelInfoSchema(**item) for item in list_models_public()]
    )
    return JSONResponse(
        content=payload.model_dump(),
        headers={"Cache-Control": "no-store"},
    )
