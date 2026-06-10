"""Pydantic models for /api/query and /api/followup request/response bodies."""

from typing import Literal

from pydantic import BaseModel, Field


class Artifact(BaseModel):
    """One downloadable or previewable pipeline output."""

    id: str
    label: str
    filename: str
    kind: Literal["geotiff", "vector", "reference"]
    download_url: str | None = None
    preview_url: str | None = None


class ReferenceLayer(BaseModel):
    """Gridded population or other reference raster served from REFERENCE_DATA_DIR."""

    id: str
    label: str
    filename: str
    kind: Literal["reference"] = "reference"
    category: Literal["population", "reference"] = "reference"
    stats: dict = Field(default_factory=dict)
    bounds_wgs84: list[float] | None = None
    download_url: str | None = None
    preview_url: str | None = None


class QueryResponse(BaseModel):
    model: Literal["lst", "obia"]
    summary: str
    stats: dict
    logs: str
    artifacts: list[Artifact] = Field(default_factory=list)
    reference_layers: list[ReferenceLayer] = Field(default_factory=list)


class DashboardContext(BaseModel):
    """Snapshot of the dashboard the client sends back for follow-up questions."""

    model: Literal["lst", "obia"]
    summary: str
    stats: dict = Field(default_factory=dict)
    logs: str = ""
    raster: str = ""
    artifacts: list[Artifact] = Field(default_factory=list)
    reference_layers: list[ReferenceLayer] = Field(default_factory=list)


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
    worldpop: dict = Field(default_factory=dict)
    sources: dict = Field(default_factory=dict)
