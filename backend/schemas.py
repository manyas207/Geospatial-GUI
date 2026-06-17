"""Pydantic models for API request/response bodies."""

from typing import Literal

from pydantic import BaseModel, Field


class DashboardContext(BaseModel):
    """Snapshot of the dashboard the client sends back for follow-up questions."""

    model: Literal["equity"] = "equity"
    summary: str
    stats: dict = Field(default_factory=dict)
    logs: str = ""
    raster: str = ""
    tract_layer_token: str | None = None
    project_id: str | None = None
    demo_cities: list[dict] | None = None
    demo_overview: dict | None = None


class ProjectCreateRequest(BaseModel):
    name: str | None = None


class ProjectCityRequest(BaseModel):
    address: str


class FollowupRequest(BaseModel):
    question: str
    context: DashboardContext


class FollowupResponse(BaseModel):
    answer: str


class CityLayersRequest(BaseModel):
    address: str


class CityLayersResponse(BaseModel):
    address: str
    matched_address: str
    geocode: dict
    summary: dict = Field(default_factory=dict)
    map_layers: dict = Field(default_factory=dict)
    vector_layer: dict = Field(default_factory=dict)
    worldpop: dict = Field(default_factory=dict)
    sources: dict = Field(default_factory=dict)
