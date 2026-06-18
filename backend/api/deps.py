"""Shared FastAPI dependencies and helpers."""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

from backend.config import CITY_LAYERS_CACHE
from backend.core.rate_limit import chat_rate_limiter
from backend.layers.orchestrator import decode_preview_token

_chat_limiter = chat_rate_limiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client:
        return request.client.host
    return "unknown"


def chat_limiter():
    return _chat_limiter


def city_png_preview(token: str) -> FileResponse:
    try:
        path = decode_preview_token(token, CITY_LAYERS_CACHE)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preview not found.")
    return FileResponse(path, media_type="image/png")
