"""Natural-language intent routing: Ollama JSON classifier with keyword fallback.

Returns "lst" or "obia". Set OLLAMA_ENABLED=false to use regex-only routing.
On ConnectionError, falls back to keywords so the API works without a local LLM.
"""

import json
import os
import re

from fastapi import HTTPException

from backend.ollama_client import chat

LST_PATTERN = re.compile(r"\b(temperature|thermal|lst|heat|land\s+surface)\b", re.I)
OBIA_PATTERN = re.compile(r"\b(segment|object|obia|parcel|region|classify)\b", re.I)

SYSTEM_PROMPT = (
    "You route geospatial analysis questions to one of two models. "
    "Reply with JSON only: {\"model\": \"lst\"} for land surface temperature "
    "or {\"model\": \"obia\"} for object-based segmentation."
)


def _keyword_intent(question: str) -> str:
    lst_match = bool(LST_PATTERN.search(question))
    obia_match = bool(OBIA_PATTERN.search(question))

    if lst_match and not obia_match:
        return "lst"
    if obia_match and not lst_match:
        return "obia"
    if lst_match and obia_match:
        raise HTTPException(
            status_code=400,
            detail="Question matches both LST and OBIA. Ask about temperature or segmentation only.",
        )
    raise HTTPException(
        status_code=400,
        detail="Ask about temperature (LST) or segmentation (OBIA).",
    )


def _parse_model_json(content: str) -> str:
    """Accept raw JSON or markdown-fenced JSON from the model."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I).strip()

    try:
        payload = json.loads(content)
        intent = payload.get("model", "").lower()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="LLM returned invalid JSON.") from exc

    if intent not in ("lst", "obia"):
        raise HTTPException(status_code=502, detail=f"LLM returned unknown model: {intent!r}")

    return intent


def _ollama_intent(question: str) -> str:
    content = chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        format_json=True,
    )
    return _parse_model_json(content or "{}")


def parse_intent(question: str) -> str:
    question = question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    use_ollama = os.environ.get("OLLAMA_ENABLED", "true").lower() not in ("0", "false", "no")
    if not use_ollama:
        return _keyword_intent(question)

    try:
        return _ollama_intent(question)
    except ConnectionError:
        return _keyword_intent(question)
