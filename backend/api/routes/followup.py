"""Dashboard follow-up chat routes."""

import logging

from fastapi import APIRouter, HTTPException, Request

from backend.api.deps import chat_limiter, client_ip
from backend.chat.dashboard import answer_about_dashboard
from backend.chat.equity_burden import (
    analyze_equity_burden,
    analyze_project_equity_burden,
    is_equity_burden_question,
)
from backend.chat.layer_correlation import (
    analyze_layer_correlations,
    is_correlation_question,
)
from backend.config import CITY_LAYERS_CACHE, PROJECTS_DIR
from backend.core.limits import chat_max_question_length
from backend.core.schemas import FollowupRequest, FollowupResponse
from backend.layers.orchestrator import decode_preview_token
from backend.layers.tract_query import query_tract_gpkg, query_tract_layer
from backend.projects.compare import compare_cities, compare_demo_cities
from backend.projects.service import get_city_gpkg_path, get_project
from models.registry import resolve_model_id

router = APIRouter(tags=["followup"])
logger = logging.getLogger(__name__)


def _project_model_id(project: dict) -> str:
    return resolve_model_id(project.get("model_id"))


def _try_get_project(project_id: str) -> dict | None:
    try:
        return get_project(project_id.strip(), projects_dir=PROJECTS_DIR)
    except FileNotFoundError:
        logger.debug("Project not found: %s", project_id)
        return None


def _enrich_equity_burden(
    context: dict,
    question: str,
    project_id: str | None,
    token: str | None,
) -> None:
    if not is_equity_burden_question(question) or context.get("equity_burden"):
        return

    project = _try_get_project(project_id) if project_id else None

    if project_id and project and _project_model_id(project) != "obia":
        try:
            context["equity_burden"] = analyze_project_equity_burden(
                project_id.strip(),
                question,
                projects_dir=PROJECTS_DIR,
            )
        except FileNotFoundError:
            logger.debug("Equity burden data missing for project %s", project_id)

    if token and project_id and ":" in token and not context.get("equity_burden"):
        _, city_key = token.split(":", 1)
        project = project or _try_get_project(project_id)
        if project and _project_model_id(project) != "obia":
            try:
                gpkg = get_city_gpkg_path(project_id, city_key, projects_dir=PROJECTS_DIR)
                city_entry = (project.get("cities") or {}).get(city_key) or {}
                city_name = city_entry.get("name") or city_entry.get("address")
                context["equity_burden"] = analyze_equity_burden(
                    gpkg, question, city_name=city_name
                )
            except FileNotFoundError:
                logger.debug("GPKG missing for %s/%s", project_id, city_key)
        return

    if token and not (project_id and ":" in token):
        try:
            gpkg_path = decode_preview_token(token.strip(), CITY_LAYERS_CACHE)
            if gpkg_path.suffix.lower() == ".gpkg":
                context["equity_burden"] = analyze_equity_burden(gpkg_path, question)
        except (ValueError, FileNotFoundError) as exc:
            logger.debug("Preview-token equity burden failed: %s", exc)


def _enrich_tract_query(
    context: dict,
    question: str,
    project_id: str | None,
    token: str | None,
) -> None:
    if not token or is_equity_burden_question(question) or is_correlation_question(question):
        return

    try:
        if project_id and ":" in token:
            _, city_key = token.split(":", 1)
            gpkg = get_city_gpkg_path(project_id, city_key, projects_dir=PROJECTS_DIR)
            context["tract_query"] = query_tract_gpkg(gpkg, question)
        else:
            context["tract_query"] = query_tract_layer(
                token.strip(), question, CITY_LAYERS_CACHE
            )
    except (ValueError, FileNotFoundError) as exc:
        logger.debug("Tract query failed: %s", exc)


def _enrich_layer_correlations(
    context: dict,
    question: str,
    project_id: str | None,
    token: str | None,
) -> None:
    if not is_correlation_question(question) or context.get("layer_correlations"):
        return

    if token and project_id and ":" in token:
        _, city_key = token.split(":", 1)
        project = _try_get_project(project_id)
        if project and _project_model_id(project) == "obia":
            return
        try:
            gpkg = get_city_gpkg_path(project_id, city_key, projects_dir=PROJECTS_DIR)
            city_entry = (project.get("cities") or {}).get(city_key) or {} if project else {}
            city_name = city_entry.get("name") or city_entry.get("address")
            context["layer_correlations"] = analyze_layer_correlations(
                gpkg, city_name=city_name
            )
        except FileNotFoundError:
            logger.debug("Layer correlation GPKG missing for %s/%s", project_id, city_key)
        return

    if token and not (project_id and ":" in token):
        try:
            gpkg_path = decode_preview_token(token.strip(), CITY_LAYERS_CACHE)
            if gpkg_path.suffix.lower() == ".gpkg":
                context["layer_correlations"] = analyze_layer_correlations(gpkg_path)
        except (ValueError, FileNotFoundError) as exc:
            logger.debug("Preview-token layer correlation failed: %s", exc)


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
        raise HTTPException(
            status_code=429,
            detail=f"Too many chat requests. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        context = body.context.model_dump()
        project_id = body.context.project_id
        token = body.context.tract_layer_token

        if project_id:
            try:
                context["city_comparison"] = compare_cities(
                    project_id.strip(), question, projects_dir=PROJECTS_DIR
                )
            except FileNotFoundError:
                logger.debug("City comparison skipped; project not found: %s", project_id)
        elif body.context.demo_cities:
            context["city_comparison"] = compare_demo_cities(
                question, body.context.demo_cities
            )

        _enrich_equity_burden(context, question, project_id, token)
        _enrich_layer_correlations(context, question, project_id, token)
        _enrich_tract_query(context, question, project_id, token)

        answer = answer_about_dashboard(question, context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FollowupResponse(answer=answer)
