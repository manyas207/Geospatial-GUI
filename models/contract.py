"""Model plugin contract for analysis pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import geopandas as gpd

DashboardType = Literal["equity"]
VectorJoinKind = Literal["tract_zonal", "none"]


@dataclass(frozen=True)
class InputField:
    """Describes one expected upload group for a model."""

    name: str
    label: str
    required: bool = True
    accept: str = ""
    hint: str = ""


@dataclass
class RunContext:
    """Per-city context passed into model run and post-process hooks."""

    address: str
    city_dir: Path
    uploads_dir: Path
    city_layers_cache: Path


@dataclass
class ModelResult:
    """Normalized output from a model pipeline run."""

    stats: dict[str, Any] = field(default_factory=dict)
    logs: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)
    primary_raster: str | None = None


@dataclass
class PostProcessResult:
    """Optional tract enrichment and manifest fields after a model run."""

    enriched_gdf: gpd.GeoDataFrame | None = None
    stats_updates: dict[str, Any] = field(default_factory=dict)
    city_fields: dict[str, Any] = field(default_factory=dict)
    vector_fields: list[str] = field(default_factory=list)


PickPrimaryFn = Callable[[list[Path]], Path]
RunFn = Callable[[list[Path], RunContext], ModelResult]
PostProcessFn = Callable[[ModelResult, RunContext], PostProcessResult]


@dataclass(frozen=True)
class ModelSpec:
    """Registered analysis model."""

    id: str
    label: str
    description: str
    input_schema: tuple[InputField, ...]
    dashboard: DashboardType = "equity"
    vector_join: VectorJoinKind = "none"
    vector_fields: tuple[str, ...] = ()
    primary_metric: str = ""
    pick_primary: PickPrimaryFn | None = None
    run: RunFn | None = None
    post_process: PostProcessFn | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "dashboard": self.dashboard,
            "vector_join": self.vector_join,
            "primary_metric": self.primary_metric,
            "input_schema": [
                {
                    "name": field.name,
                    "label": field.label,
                    "required": field.required,
                    "accept": field.accept,
                    "hint": field.hint,
                }
                for field in self.input_schema
            ],
        }

    def pick_primary_file(self, paths: list[Path]) -> Path:
        if self.pick_primary is None:
            raise ValueError(f"Model {self.id!r} does not define pick_primary.")
        return self.pick_primary(paths)

    def execute(self, paths: list[Path], ctx: RunContext) -> ModelResult:
        if self.run is None:
            raise ValueError(f"Model {self.id!r} does not define run.")
        return self.run(paths, ctx)

    def enrich(self, result: ModelResult, ctx: RunContext) -> PostProcessResult:
        if self.post_process is None:
            return PostProcessResult(vector_fields=list(self.vector_fields))
        return self.post_process(result, ctx)
