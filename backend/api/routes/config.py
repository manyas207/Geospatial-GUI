"""Public app configuration (limits exposed to the web UI)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.core.limits import (
    chat_max_question_length,
    chat_rate_limit_max,
    chat_rate_limit_window,
    upload_max_file_bytes,
    upload_max_total_bytes,
)

router = APIRouter(tags=["config"])


@router.get("/api/config")
async def app_config() -> JSONResponse:
    return JSONResponse(
        content={
            "upload_max_file_bytes": upload_max_file_bytes(),
            "upload_max_total_bytes": upload_max_total_bytes(),
            "chat_max_question_length": chat_max_question_length(),
            "chat_rate_limit_max": chat_rate_limit_max(),
            "chat_rate_limit_window": chat_rate_limit_window(),
        },
        headers={"Cache-Control": "no-store"},
    )
