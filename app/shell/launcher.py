"""Start UI server, API hooks, and embedded HTML window."""

from app.config.settings import ensure_data_dirs, get_settings
from app.shell.iframe_host import open_embedded_ui
from app.shell.ui_server import start_ui_server


def run_app() -> None:
    settings = get_settings()
    ensure_data_dirs(settings)
    server = start_ui_server(settings)
    try:
        open_embedded_ui(settings)
    finally:
        server.shutdown()
