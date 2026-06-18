"""Multipart upload helpers."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

from backend.core.constants import ALLOWED_UPLOAD_SUFFIXES


async def save_upload_files(files: list[UploadFile], dest_dir: Path) -> list[Path]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    dest_dir.mkdir(parents=True, exist_ok=True)
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
                    "Use GeoTIFF (.tif) and/or shapefile sidecars (.shp, .shx, .dbf)."
                ),
            )
        safe_name = re.sub(r"[^\w.\-]", "_", Path(upload.filename).name)
        dest_path = dest_dir / safe_name
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Uploaded file is empty: {upload.filename}")
        dest_path.write_bytes(content)
        saved_paths.append(dest_path)

    if not saved_paths:
        raise HTTPException(status_code=400, detail="At least one file is required.")
    return saved_paths
