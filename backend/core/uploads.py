"""Multipart upload helpers."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

from backend.core.constants import ALLOWED_UPLOAD_SUFFIXES
from backend.core.limits import upload_max_file_bytes, upload_max_total_bytes


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


async def _read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    chunk_size = 1024 * 1024
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File too large: {upload.filename} "
                    f"(max {_format_size(max_bytes)} per file)."
                ),
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def save_upload_files(files: list[UploadFile], dest_dir: Path) -> list[Path]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    per_file_limit = upload_max_file_bytes()
    total_limit = upload_max_total_bytes()
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    total_bytes = 0

    for upload in files:
        if not upload.filename:
            continue
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type: {upload.filename}. "
                    "Use GeoTIFF (.tif) and/or shapefile sidecars (.shp, .shx, .dbf)."
                ),
            )
        safe_name = re.sub(r"[^\w.\-]", "_", Path(upload.filename).name)
        dest_path = dest_dir / safe_name
        content = await _read_upload_limited(upload, per_file_limit)
        if not content:
            raise HTTPException(status_code=400, detail=f"Uploaded file is empty: {upload.filename}")
        total_bytes += len(content)
        if total_bytes > total_limit:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Upload batch too large ({_format_size(total_bytes)}; "
                    f"max {_format_size(total_limit)} total per request)."
                ),
            )
        dest_path.write_bytes(content)
        saved_paths.append(dest_path)

    if not saved_paths:
        raise HTTPException(status_code=400, detail="At least one file is required.")
    return saved_paths
