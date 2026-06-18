"""Follow-up Q&A on the dashboard using Ollama and tract/city context."""

import json
import os

from backend.chat.equity_burden import format_equity_burden_answer, is_equity_burden_question
from backend.core.json_util import to_json_safe
from backend.chat.ollama import chat

SYSTEM_PROMPT = (
    "You are a geospatial analysis assistant for an urban heat and equity dashboard. "
    "Answer using ONLY the dashboard context JSON provided.\n\n"
    "Heat-equity burden means HIGH land surface temperature (LST) combined with "
    "socioeconomic vulnerability (LOW median income, higher Hispanic or Black share, "
    "higher population density). Do NOT treat the hottest tract alone as most burdened "
    "if income is high. Median income above $80,000 is NOT low income.\n\n"
    "When equity_burden is present, use top_burdened_tracts and the equity_burden "
    "summary as your primary evidence. Cite tract names, LST (°C), income ($), and "
    "burden_score. Contrast with highest_lst_tract when it differs from the top "
    "burdened tract.\n\n"
    "When city_comparison is present, only discuss cities listed there. "
    "When project_cities is present, do not invent cities outside that list.\n\n"
    "Do not tell the user to inspect JSON fields or blocks. Answer directly in plain "
    "language. Be concise. If data is missing, say what is missing."
)


def _use_llm_for_equity() -> bool:
    return os.environ.get("EQUITY_CHAT_USE_LLM", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _fallback_answer(question: str, context: dict) -> str:
    """Simple stat listing when Ollama is unreachable."""
    equity_answer = format_equity_burden_answer(context.get("equity_burden") or {})
    if equity_answer:
        return equity_answer

    parts = ["Based on the equity dashboard:"]
    stats = context.get("stats") or {}
    if stats:
        for key, value in stats.items():
            parts.append(f"- {key.replace('_', ' ')}: {value}")
    else:
        parts.append("- No stats available.")

    comparison = context.get("city_comparison")
    if comparison and comparison.get("summary"):
        parts.append(f"\nCity comparison: {comparison['summary']}")

    tract = context.get("tract_query")
    if tract and tract.get("summary") and not tract.get("skipped"):
        parts.append(f"\nTract query: {tract['summary']}")

    parts.append(f"\nRegarding your question ({question!r}): see the context above.")
    return "\n".join(parts)


def _llm_context(context: dict) -> dict:
    """Drop fields that cause the LLM to ignore equity_burden rankings."""
    payload = {
        "model": context.get("model"),
        "summary": context.get("summary"),
        "equity_burden": context.get("equity_burden"),
        "tract_query": context.get("tract_query"),
        "city_comparison": context.get("city_comparison"),
        "project_id": context.get("project_id"),
        "project_cities": context.get("project_cities"),
        "demo_cities": context.get("demo_cities"),
        "demo_overview": context.get("demo_overview"),
        "analysis_model": context.get("analysis_model"),
        "logs": (context.get("logs") or "")[:4000],
        "raster": context.get("raster"),
    }
    if not context.get("equity_burden"):
        payload["stats"] = context.get("stats")
    return payload


def answer_about_dashboard(question: str, context: dict) -> str:
    question = question.strip()
    if not question:
        raise ValueError("Question is required.")

    equity = context.get("equity_burden")
    if is_equity_burden_question(question) and equity:
        equity_answer = format_equity_burden_answer(equity)
        if equity_answer and not _use_llm_for_equity():
            return equity_answer

    context_block = json.dumps(to_json_safe(_llm_context(context)), indent=2)

    try:
        llm_answer = chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Dashboard context:\n{context_block}\n\nQuestion: {question}",
                },
            ]
        ).strip()
        if is_equity_burden_question(question) and equity:
            equity_answer = format_equity_burden_answer(equity)
            if equity_answer:
                return equity_answer
        return llm_answer
    except ConnectionError:
        return _fallback_answer(question, context)
