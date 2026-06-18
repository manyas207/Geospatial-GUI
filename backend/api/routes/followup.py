"""Dashboard follow-up chat routes."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.api.deps import chat_limiter, client_ip
from backend.chat.dashboard import answer_about_dashboard
from backend.chat.equity_burden import (
    analyze_equity_burden,
    analyze_project_equity_burden,
    is_equity_burden_question,
)
from backend.config import CITY_LAYERS_CACHE, PROJECTS_DIR
from backend.core.rate_limit import chat_max_question_length
from backend.core.schemas import FollowupRequest, FollowupResponse
from backend.layers.orchestrator import decode_preview_token
from backend.layers.tract_query import query_tract_gpkg, query_tract_layer
from backend.projects.compare import compare_demo_cities
from backend.projects.service import compare_project, get_city_gpkg_path, get_project

router = APIRouter(tags=["followup"])


@router.post("/api/followup", response_model=FollowupResponse)
async def followup(body: FollowupRequest, request: Request) -> FollowupResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    max_len = chat_max_question_length()
    if len(question) > max_len:
        raise HTTPException(
            status_code=400,
            detail=f"Question is too long (max {max_len} characters).",
        )

    allowed, retry_after = chat_limiter().check(client_ip(request))
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "detail": (
                    f"Too many chat requests. Try again in {retry_after} seconds."
                ),
            },
            headers={"Retry-After": str(retry_after)},
        )

    try:
        context = body.context.model_dump()
        project_id = body.context.project_id
        token = body.context.tract_layer_token
        equity_question = is_equity_burden_question(question)

        if project_id:
            try:
                context["city_comparison"] = compare_project(
                    project_id.strip(), question, projects_dir=PROJECTS_DIR
                )
            except FileNotFoundError:
                pass

        elif body.context.demo_cities:
            context["city_comparison"] = compare_demo_cities(
                question, body.context.demo_cities
            )

        if equity_question and project_id:
            try:
                context["equity_burden"] = analyze_project_equity_burden(
                    project_id.strip(),
                    question,
                    projects_dir=PROJECTS_DIR,
                )
            except FileNotFoundError:
                pass

        if token:
            try:
                if project_id and ":" in token:
                    _, city_key = token.split(":", 1)
                    gpkg = get_city_gpkg_path(project_id, city_key, projects_dir=PROJECTS_DIR)
                    if equity_question:
                        if not context.get("equity_burden"):
                            project = get_project(project_id.strip(), projects_dir=PROJECTS_DIR)
                            city_entry = (project.get("cities") or {}).get(city_key) or {}
                            city_name = city_entry.get("name") or city_entry.get("address")
                            context["equity_burden"] = analyze_equity_burden(
                                gpkg, question, city_name=city_name
                            )
                    else:
                        context["tract_query"] = query_tract_gpkg(gpkg, question)
                elif equity_question:
                    try:
                        gpkg_path = decode_preview_token(token.strip(), CITY_LAYERS_CACHE)
                        if gpkg_path.suffix.lower() == ".gpkg":
                            context["equity_burden"] = analyze_equity_burden(gpkg_path, question)
                    except (ValueError, FileNotFoundError):
                        pass
                else:
                    context["tract_query"] = query_tract_layer(
                        token.strip(), question, CITY_LAYERS_CACHE
                    )
            except (ValueError, FileNotFoundError):
                pass
        answer = answer_about_dashboard(question, context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FollowupResponse(answer=answer)
