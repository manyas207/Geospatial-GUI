"""Paths and runtime configuration."""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_DIR = ROOT / "ui"
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    ui_dir: Path = UI_DIR
    data_inputs: Path = DATA_DIR / "inputs"
    data_processed: Path = DATA_DIR / "processed"
    data_outputs: Path = DATA_DIR / "outputs"
    # CSP frame-ancestors for pages embedded on other sites (space-separated origins or *)
    frame_ancestors: str = "*"

    @property
    def ui_url(self) -> str:
        return f"http://{self.host}:{self.port}/index.html"

    @property
    def embed_dashboard_url(self) -> str:
        return f"http://{self.host}:{self.port}/embed/dashboard.html"


def get_settings() -> Settings:
    return Settings()


def ensure_data_dirs(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    for path in (s.data_inputs, s.data_processed, s.data_outputs):
        path.mkdir(parents=True, exist_ok=True)
