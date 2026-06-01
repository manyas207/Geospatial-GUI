"""Per-request job workspaces under data/jobs/{job_id}/."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from app.config.settings import Settings, get_settings


class JobStatus(str, Enum):
    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    ANALYZING = "analyzing"
    ACCURACY = "accuracy"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class JobPaths:
    root: Path
    inputs: Path
    processed: Path
    analysis: Path
    accuracy: Path
    dashboard: Path
    exports: Path

    def ensure(self) -> None:
        for path in (
            self.root,
            self.inputs,
            self.processed,
            self.analysis,
            self.accuracy,
            self.dashboard,
            self.exports,
        ):
            path.mkdir(parents=True, exist_ok=True)


class JobStore:
    """Create and manage isolated folders for each analysis request."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._jobs_root = self._settings.jobs_dir
        self._jobs_root.mkdir(parents=True, exist_ok=True)

    def paths(self, job_id: str) -> JobPaths:
        root = self._jobs_root / job_id
        return JobPaths(
            root=root,
            inputs=root / "inputs",
            processed=root / "processed",
            analysis=root / "analysis",
            accuracy=root / "accuracy",
            dashboard=root / "dashboard",
            exports=root / "exports",
        )

    def create_job(self, payload: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
        """Create a new job folder and return job_id plus initial context."""
        job_id = _new_job_id()
        paths = self.paths(job_id)
        paths.ensure()

        now = _utc_now()
        metadata: dict[str, Any] = {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "created_at": now,
            "updated_at": now,
            "request": payload or {},
        }
        self._write_metadata(job_id, metadata)

        context = self.build_context(job_id)
        self.save_context(job_id, context)
        return job_id, context

    def build_context(self, job_id: str) -> dict[str, Any]:
        paths = self.paths(job_id)
        return {
            "job_id": job_id,
            "job_dir": str(paths.root),
            "inputs_dir": str(paths.inputs),
            "processed_dir": str(paths.processed),
            "analysis_dir": str(paths.analysis),
            "accuracy_dir": str(paths.accuracy),
            "dashboard_dir": str(paths.dashboard),
            "exports_dir": str(paths.exports),
        }

    def get_metadata(self, job_id: str) -> dict[str, Any]:
        path = self._metadata_path(job_id)
        if not path.is_file():
            raise FileNotFoundError(f"Job not found: {job_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def update_status(self, job_id: str, status: JobStatus) -> dict[str, Any]:
        metadata = self.get_metadata(job_id)
        metadata["status"] = status.value
        metadata["updated_at"] = _utc_now()
        self._write_metadata(job_id, metadata)
        return metadata

    def merge_metadata(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        metadata = self.get_metadata(job_id)
        metadata.update(updates)
        metadata["updated_at"] = _utc_now()
        self._write_metadata(job_id, metadata)
        return metadata

    def load_context(self, job_id: str) -> dict[str, Any]:
        path = self._context_path(job_id)
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            base = self.build_context(job_id)
            base.update(data)
            return base
        return self.build_context(job_id)

    def save_context(self, job_id: str, context: dict[str, Any]) -> None:
        paths = self.paths(job_id)
        if not paths.root.is_dir():
            raise FileNotFoundError(f"Job not found: {job_id}")
        serializable = {k: v for k, v in context.items() if _is_json_serializable(v)}
        metadata = self.get_metadata(job_id)
        metadata["updated_at"] = _utc_now()
        self._write_metadata(job_id, metadata)
        self._context_path(job_id).write_text(
            json.dumps(serializable, indent=2),
            encoding="utf-8",
        )

    def _write_metadata(self, job_id: str, metadata: dict[str, Any]) -> None:
        self._metadata_path(job_id).write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

    def list_jobs(self) -> list[str]:
        if not self._jobs_root.is_dir():
            return []
        return sorted(
            p.name
            for p in self._jobs_root.iterdir()
            if p.is_dir() and (p / "job.json").is_file()
        )

    def _metadata_path(self, job_id: str) -> Path:
        return self.paths(job_id).root / "job.json"

    def _context_path(self, job_id: str) -> Path:
        return self.paths(job_id).root / "context.json"


def get_job_store() -> JobStore:
    return JobStore()


def _new_job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False
