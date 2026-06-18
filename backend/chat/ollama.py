"""Thin HTTP client for the local Ollama /api/chat endpoint (no extra dependencies)."""

import json
import os
import urllib.error
import urllib.request


def chat(messages: list[dict], *, format_json: bool = False) -> str:
    # Env: OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT (see .env.example).
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    timeout = int(os.environ.get("OLLAMA_TIMEOUT", "60"))

    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if format_json:
        payload["format"] = "json"

    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Ollama unavailable at {base_url}: {exc}") from exc

    return (body.get("message") or {}).get("content") or ""
