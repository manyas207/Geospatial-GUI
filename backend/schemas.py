"""Pydantic models for /api/query and /api/followup request/response bodies."""

from typing import Literal

from pydantic import BaseModel, Field


class Artifact(BaseModel):
    """One downloadable or previewable pipeline output."""

    id: str
    label: str
    filename: str
    kind: Literal["geotiff", "vector"]
    download_url: str | None = None
    preview_url: str | None = None


class QueryResponse(BaseModel):
    model: Literal["lst", "obia"]
    summary: str
    stats: dict
    logs: str
    artifacts: list[Artifact] = Field(default_factory=list)


class DashboardContext(BaseModel):
    """Snapshot of the dashboard the client sends back for follow-up questions."""

    model: Literal["lst", "obia"]
    summary: str
    stats: dict = Field(default_factory=dict)
    logs: str = ""
    raster: str = ""
    artifacts: list[Artifact] = Field(default_factory=list)


class FollowupRequest(BaseModel):
    question: str
    context: DashboardContext


class FollowupResponse(BaseModel):
    answer: str
