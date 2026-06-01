"""Embed the local HTML UI in a desktop window (iframe-style shell)."""

from app.config.settings import Settings


def open_embedded_ui(settings: Settings) -> None:
    """Load index.html in a native webview pointed at the local UI server."""
    import webview

    webview.create_window(
        "Geospatial GUI",
        settings.ui_url,
        width=1280,
        height=800,
        min_size=(960, 600),
    )
    webview.start(debug=False)
