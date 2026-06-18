"""PDF report export routes."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from backend.config import PROJECTS_DIR
from backend.core.schemas import ReportRequest
from backend.report.pdf import build_project_report_pdf

router = APIRouter(tags=["reports"])


@router.post("/api/projects/{project_id}/report")
async def export_project_report(
    project_id: str, body: ReportRequest, request: Request
) -> Response:
    """Generate a PDF report on demand (map render + stats; not pre-built)."""
    base_url = str(request.base_url).rstrip("/")
    chat_pairs = [pair.model_dump() for pair in body.chat[: body.max_chat_pairs]]

    try:
        pdf_bytes, filename = build_project_report_pdf(
            project_id,
            city_key=body.city_key,
            chat_pairs=chat_pairs,
            base_url=base_url,
            projects_dir=PROJECTS_DIR,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
