"""Follow-up Q&A on the dashboard using Ollama and tract/city context."""

import json

from backend.json_util import to_json_safe
from backend.ollama_client import chat

SYSTEM_PROMPT = (
    "You are a geospatial analysis assistant. The user is viewing an urban heat and equity "
    "dashboard with census tract data and land surface temperature (LST). Answer follow-up "
    "questions using only the dashboard context provided, including tract_query and "
    "city_comparison blocks when present. "
    "For the 11-city demo, use demo_cities (all placeholder LST values) and demo_overview "
    "(hottest_city, peak_lst_C) for cross-city questions — not only the active city's census stats. "
    "Be concise, use plain language, and cite specific stats when relevant. "
    "If the answer is not in the context, say you do not have that information."
)


def _fallback_answer(question: str, context: dict) -> str:
    """Simple stat listing when Ollama is unreachable."""
    stats = context.get("stats") or {}
    parts = ["Based on the equity dashboard:"]

    if stats:
        for key, value in stats.items():
            parts.append(f"- {key.replace('_', ' ')}: {value}")
    else:
        parts.append("- No stats available.")

    comparison = context.get("city_comparison")
    if comparison and comparison.get("summary"):
        parts.append(f"\nCity comparison: {comparison['summary']}")

    tract = context.get("tract_query")
    if tract and tract.get("summary"):
        parts.append(f"\nTract query: {tract['summary']}")

    parts.append(f"\nRegarding your question ({question!r}): see the context above.")
    return "\n".join(parts)


def answer_about_dashboard(question: str, context: dict) -> str:
    question = question.strip()
    if not question:
        raise ValueError("Question is required.")

    context_block = json.dumps(
        to_json_safe(
            {
                "model": context.get("model"),
                "summary": context.get("summary"),
                "stats": context.get("stats"),
                "tract_query": context.get("tract_query"),
                "city_comparison": context.get("city_comparison"),
                "project_id": context.get("project_id"),
                "demo_cities": context.get("demo_cities"),
                "demo_overview": context.get("demo_overview"),
                "logs": (context.get("logs") or "")[:4000],
                "raster": context.get("raster"),
            }
        ),
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
