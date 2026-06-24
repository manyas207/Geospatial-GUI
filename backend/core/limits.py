"""Server-enforced limits for uploads and chat."""

from __future__ import annotations

import os

_MB = 1024 * 1024


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def upload_max_file_bytes() -> int:
    """Max bytes per uploaded file (default 500 MB)."""
    if raw := os.environ.get("UPLOAD_MAX_FILE_BYTES", "").strip():
        try:
            return max(_MB, int(raw))
        except ValueError:
            pass
    mb = max(1, _int_env("UPLOAD_MAX_FILE_MB", 500))
    return mb * _MB


def upload_max_total_bytes() -> int:
    """Max bytes across all files in one upload request (default 2 GB)."""
    if raw := os.environ.get("UPLOAD_MAX_TOTAL_BYTES", "").strip():
        try:
            return max(upload_max_file_bytes(), int(raw))
        except ValueError:
            pass
    mb = max(1, _int_env("UPLOAD_MAX_TOTAL_MB", 2048))
    return max(upload_max_file_bytes(), mb * _MB)


def chat_max_question_length() -> int:
    return max(100, _int_env("CHAT_MAX_QUESTION_LENGTH", 2000))


def chat_rate_limit_max() -> int:
    return max(1, _int_env("CHAT_RATE_LIMIT_MAX", 15))


def chat_rate_limit_window() -> int:
    return max(1, _int_env("CHAT_RATE_LIMIT_WINDOW", 60))
