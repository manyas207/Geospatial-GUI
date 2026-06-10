"""Follow-up Q&A on the dashboard using Ollama and the last query's context.

The frontend sends the full DashboardContext (stats, logs, artifacts) so answers
stay grounded in pipeline output rather than general world knowledge.
"""

import json

from backend.constants import INTERNAL_STAT_KEYS
from backend.ollama_client import chat

SYSTEM_PROMPT = (
    "You are a geospatial analysis assistant. The user is viewing a dashboard with "
    "results from an LST (land surface temperature) or OBIA (segmentation) pipeline. "
    "Answer follow-up questions using only the dashboard context provided. "
    "Be concise, use plain language, and cite specific stats when relevant. "
    "If the answer is not in the context, say you do not have that information."
)


def _fallback_answer(question: str, context: dict) -> str:
    """Simple stat listing when Ollama is unreachable."""
    stats = context.get("stats") or {}
    model = (context.get("model") or "unknown").upper()
    parts = [f"Based on the {model} dashboard:"]

    if stats:
        for key, value in stats.items():
            if key in INTERNAL_STAT_KEYS or key.endswith(("_gpkg", "_tif", "geotiff")):
                continue
            parts.append(f"- {key.replace('_', ' ')}: {value}")
    else:
        parts.append("- No stats available.")

    parts.append(f"\nRegarding your question ({question!r}): see the stats and logs above.")
    return "\n".join(parts)


def answer_about_dashboard(question: str, context: dict) -> str:
    question = question.strip()
    if not question:
        raise ValueError("Question is required.")

    context_block = json.dumps(
        {
            "model": context.get("model"),
            "summary": context.get("summary"),
            "stats": context.get("stats"),
            "logs": (context.get("logs") or "")[:4000],  # cap prompt size for the LLM
            "raster": context.get("raster"),
            "reference_layers": context.get("reference_layers") or [],
        },
        indent=2,
    )

    try:
        return chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Dashboard context:\n{context_block}\n\nQuestion: {question}",
                },
            ]
        ).strip()
    except ConnectionError:
        return _fallback_answer(question, context)
