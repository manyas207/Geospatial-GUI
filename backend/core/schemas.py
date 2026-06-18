"""Pydantic models for API request/response bodies."""

from typing import Literal

from pydantic import BaseModel, Field


class DashboardContext(BaseModel):
    """Snapshot of the dashboard the client sends back for follow-up questions."""

    model: Literal["equity"] = "equity"
    analysis_model: str | None = None
    summary: str
    stats: dict = Field(default_factory=dict)
    logs: str = ""
    raster: str = ""
    tract_layer_token: str | None = None
    project_id: str | None = None
    demo_cities: list[dict] | None = None
    demo_overview: dict | None = None
    project_cities: list[dict] | None = None


class ModelInputFieldSchema(BaseModel):
    name: str
    label: str
    required: bool = True
    accept: str = ""
    hint: str = ""


class ModelInfoSchema(BaseModel):
    id: str
    label: str
    description: str
    dashboard: str
    vector_join: str
    primary_metric: str
    input_schema: list[ModelInputFieldSchema]


class ModelsListResponse(BaseModel):
    models: list[ModelInfoSchema]


class ProjectCreateRequest(BaseModel):
    name: str | None = None
    model_id: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = None


class ProjectCityRequest(BaseModel):
    address: str
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=1984, le=2100)


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


class ReportChatPair(BaseModel):
    question: str = ""
    answer: str = ""


class ReportRequest(BaseModel):
    """Client sends active city + optional chat when user clicks Export."""

    city_key: str | None = None
    chat: list[ReportChatPair] = Field(default_factory=list)
    max_chat_pairs: int = Field(default=5, ge=0, le=20)

