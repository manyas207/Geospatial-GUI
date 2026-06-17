"""Helpers for JSON serialization of numpy/pandas scalar types."""

from __future__ import annotations

from typing import Any


def to_json_safe(value: Any) -> Any:
    """Recursively convert numpy/pandas scalars to native Python types."""
    if value is None:
        return None
    if hasattr(value, "item") and callable(value.item):
        try:
            return to_json_safe(value.item())
        except (ValueError, TypeError):
            pass
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]
    return value
