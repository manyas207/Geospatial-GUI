import json
import tempfile
from pathlib import Path

from app.config.settings import Settings
from app.jobs.store import JobStatus, JobStore
from api.handlers import handle_request


def test_create_job_creates_subfolders():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings = Settings(jobs_dir=root / "jobs")
        store = JobStore(settings)
        job_id, context = store.create_job({"sensor": "hls"})

        paths = store.paths(job_id)
        assert paths.root.is_dir()
        assert paths.inputs.is_dir()
        assert paths.processed.is_dir()
        assert paths.analysis.is_dir()
        assert (paths.root / "job.json").is_file()
        assert context["job_id"] == job_id
        assert context["processed_dir"] == str(paths.processed)


def test_handler_workflow_scoped_to_job():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings = Settings(jobs_dir=root / "jobs")
        store = JobStore(settings)

        # Patch get_job_store for handlers - use direct store via create
        import api.handlers as handlers

        original = handlers.get_job_store
        handlers.get_job_store = lambda: store
        try:
            created = handle_request("create_job", {})
            job_id = created["job_id"]

            handle_request(
                "save_user_inputs",
                {"job_id": job_id, "sensor": "landsat", "years": "2020,2021"},
            )
            handle_request(
                "run_preprocessing",
                {"job_id": job_id, "stack_bands": True},
            )
            handle_request(
                "run_analysis",
                {"job_id": job_id, "methods": ["pixel_based"]},
            )
            dash = handle_request("build_dashboard", {"job_id": job_id})

            meta = json.loads((store.paths(job_id).root / "job.json").read_text())
            assert meta["status"] == JobStatus.COMPLETED.value
            assert (store.paths(job_id).dashboard / "dashboard.json").is_file()
            assert dash["job_id"] == job_id
        finally:
            handlers.get_job_store = original
