"""Serve the HTML UI from the project ui/ directory."""

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.config.settings import Settings


class _UiHandler(SimpleHTTPRequestHandler):
    """Static file handler with UI root as document base."""

    def __init__(self, *args, ui_dir: Path, frame_ancestors: str = "*", **kwargs):
        self._ui_dir = ui_dir
        self._frame_ancestors = frame_ancestors
        super().__init__(*args, directory=str(ui_dir), **kwargs)

    def end_headers(self) -> None:
        # Permit embedding on parent sites (do not set X-Frame-Options: SAMEORIGIN)
        self.send_header(
            "Content-Security-Policy",
            f"frame-ancestors {self._frame_ancestors}",
        )
        super().end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Quiet default request logging in the desktop app
        pass


def start_ui_server(settings: Settings) -> ThreadingHTTPServer:
    handler = partial(
        _UiHandler,
        ui_dir=settings.ui_dir,
        frame_ancestors=settings.frame_ancestors,
    )
    server = ThreadingHTTPServer((settings.host, settings.port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
