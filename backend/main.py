"""FastAPI entry point: mounts API routers and static web UI."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.routes import city_layers, followup, models, projects, reports
from backend.config import WEB_DIR

app = FastAPI(title="Geospatial Dashboard API")

app.include_router(models.router)
app.include_router(projects.router)
app.include_router(reports.router)
app.include_router(city_layers.router)
app.include_router(followup.router)

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
