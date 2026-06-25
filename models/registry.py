"""Registry of analysis models available to the API."""

from __future__ import annotations

from models.contract import ModelSpec
from models.lst_model import LST_MODEL
from models.obia_model import OBIA_MODEL

# New model: copy templates/model/ into project paths, rename your_model → your id.
# Register YOUR_MODEL below. See docs/ADDING_A_MODEL.md § Quick checklist.
# from models.your_model import YOUR_MODEL

_MODELS: dict[str, ModelSpec] = {
    LST_MODEL.id: LST_MODEL,
    OBIA_MODEL.id: OBIA_MODEL,
    # YOUR_MODEL.id: YOUR_MODEL,
}

DEFAULT_MODEL_ID = LST_MODEL.id


def resolve_model_id(model_id: str | None) -> str:
    """Return a normalized model id, defaulting when omitted."""
    return (model_id or DEFAULT_MODEL_ID).strip().lower()


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
