"""Registry of analysis models available to the API."""

from __future__ import annotations

import logging

from models.contract import ModelSpec
from models.lst_model import LST_MODEL

logger = logging.getLogger(__name__)

_MODELS: dict[str, ModelSpec] = {
    LST_MODEL.id: LST_MODEL,
}

try:
    from models.obia_model import OBIA_MODEL

    _MODELS[OBIA_MODEL.id] = OBIA_MODEL
except Exception as exc:  # noqa: BLE001 — optional model; keep LST available
    logger.warning("OBIA model could not be loaded: %s", exc)


def get_model(model_id: str) -> ModelSpec:
    key = model_id.strip().lower()
    spec = _MODELS.get(key)
    if spec is None:
        known = ", ".join(sorted(_MODELS)) or "(none)"
        raise ValueError(f"Unknown model {model_id!r}. Available: {known}")
    return spec


def list_models() -> list[ModelSpec]:
    return [spec for _, spec in sorted(_MODELS.items())]


def list_models_public() -> list[dict]:
    return [spec.to_public_dict() for spec in list_models()]
