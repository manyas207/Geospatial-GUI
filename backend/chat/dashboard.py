"""Follow-up Q&A on the dashboard using Ollama and tract/city context."""

import json
import os

from backend.chat.equity_burden import format_equity_burden_answer, is_equity_burden_question
from backend.chat.layer_correlation import format_correlation_answer, is_correlation_question
from backend.core.json_util import to_json_safe
from backend.chat.ollama import chat

LST_SYSTEM_PROMPT = (
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
    "When layer_correlations is present, write as an urban heat and equity analyst—not a "
    "statistics report. Use narrative_lead and each pair's interpretation field as your "
    "evidence, then explain what the patterns mean for residents and planning in this city.\n"
    "- Write 2-4 short paragraphs in plain prose. Do NOT bullet-list every correlation.\n"
    "- Mention at most two r values, woven into sentences; prefer everyday phrases like "
    "'clear pattern' or 'modest tendency' over jargon.\n"
    "- Do NOT use LaTeX or escaped math (no \\(°C\\), \\$, or similar). Write °C and $ normally.\n"
    "- Skip pairs with |r| < 0.2 unless the user explicitly asks for a full table.\n"
    "- Close with one brief sentence on equity or heat-risk implications, and that "
    "correlation is not causation.\n\n"
    "When city_comparison is present, only discuss cities listed there. "
    "When project_cities is present, do not invent cities outside that list.\n\n"
    "Do not tell the user to inspect JSON fields or blocks. Answer directly in plain "
    "language. Be concise. If data is missing, say what is missing."
)

OBIA_SYSTEM_PROMPT = (
    "You are a geospatial analysis assistant for an OBIA land-cover dashboard. "
    "Answer using ONLY the dashboard context JSON provided.\n\n"
    "This project uses object-based image analysis (OBIA) for land-cover classification. "
    "Do NOT describe results as land surface temperature, LST, heat, or thermal imagery.\n\n"
    "Key tract fields: obia_mode_class (1=urban, 2=vegetation, 3=water, 4=bare soil), "
    "obia_mode_pct (share of tract area in the dominant class), obia_segment_count.\n\n"
    "Key run_stats fields: labeled_segments, total_segments, class_counts, "
    "tract_mean_mode_pct. The city badge value is labeled segment count, not a "
    "temperature or land-cover class id.\n\n"
    "When city_comparison is present, only discuss cities listed there. "
    "When project_cities is present, do not invent cities outside that list.\n\n"
    "Do not tell the user to inspect JSON fields or blocks. Answer directly in plain "
    "language. Be concise. If data is missing, say what is missing."
)


def _system_prompt(context: dict) -> str:
    model = (context.get("analysis_model") or "").strip().lower()
    if model == "obia":
        return OBIA_SYSTEM_PROMPT
    return LST_SYSTEM_PROMPT


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

    correlation_answer = format_correlation_answer(context.get("layer_correlations") or {})
    if correlation_answer and is_correlation_question(question):
        return correlation_answer

    model = (context.get("analysis_model") or "").strip().lower()
    dashboard_label = (
        "OBIA land-cover dashboard" if model == "obia" else "equity dashboard"
    )
    parts = [f"Based on the {dashboard_label}:"]
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
        "layer_correlations": context.get("layer_correlations"),
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
    if not context.get("equity_burden") and not context.get("layer_correlations"):
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
    user_content = f"Dashboard context:\n{context_block}\n\nQuestion: {question}"
    if is_correlation_question(question) and context.get("layer_correlations"):
        user_content += (
            "\n\nWrite an interpretive answer in prose (no bullet lists of statistics). "
            "Lead with what the patterns mean for this city; use the narrative_lead "
            "and interpretation fields in layer_correlations."
        )

    try:
        llm_answer = chat(
            [
                {"role": "system", "content": _system_prompt(context)},
                {"role": "user", "content": user_content},
            ]
        ).strip()
        if (
            is_equity_burden_question(question)
            and equity
            and not _use_llm_for_equity()
        ):
            equity_answer = format_equity_burden_answer(equity)
            if equity_answer:
                return equity_answer
        return llm_answer
    except ConnectionError:
        return _fallback_answer(question, context)
