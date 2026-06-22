"""Cross-city comparison for multi-model projects."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.core.json_util import to_json_safe
from backend.core.presets import PRESET_CITIES
from backend.layers.geocode import CITY_CENTROIDS
from backend.projects.service import city_run_stats, get_project, list_ready_cities
from models.registry import get_model, resolve_model_id

METRIC_ALIASES: dict[str, list[str]] = {
    "mean_lst_C": ["lst", "temperature", "heat", "surface temperature"],
    "avg_density_per_km2": ["density", "population density"],
    "median_income_usd": ["income", "earnings"],
    "hispanic_pct": ["hispanic", "ethnic", "latino"],
    "tract_count": ["tract", "tracts"],
    "primary_value": ["segments", "labeled", "obia", "land cover", "classification"],
    "labeled_segments": ["labeled segments", "training segments"],
    "total_segments": ["total segments", "segment count"],
}


def _city_display_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for city in PRESET_CITIES:
        key = str(city["key"])
        name = str(city["name"])
        names[key] = name
        names[name.split(",")[0].lower()] = name
    for centroid_key in CITY_CENTROIDS:
        display = centroid_key.title()
        names[centroid_key.split(",")[0].lower()] = display
        names[centroid_key] = display
    return names


def detect_cities_in_question(question: str, project_cities: dict[str, dict]) -> list[str]:
    """Return city keys mentioned in the question (project keys)."""
    q = question.lower()
    found: list[str] = []

    for key, entry in project_cities.items():
        address = (entry.get("address") or entry.get("name") or "").lower()
        short = address.split(",")[0].strip()
        if short and short in q:
            found.append(key)
            continue
        if key.replace("_", " ") in q or key.replace("_", ", ") in q:
            found.append(key)

    for alias, display in _city_display_names().items():
        if alias in q:
            for key, entry in project_cities.items():
                name = (entry.get("name") or entry.get("address") or "").lower()
                if alias in name or display.lower() in name:
                    if key not in found:
                        found.append(key)

    return found


def _default_metric(project: dict | None = None) -> str:
    model_id = resolve_model_id((project or {}).get("model_id"))
    try:
        return get_model(model_id).primary_metric
    except ValueError:
        return "mean_C"


def _city_model_id(city_entry: dict, project: dict | None = None) -> str:
    return resolve_model_id(city_entry.get("model_id") or (project or {}).get("model_id"))


def _city_metric_value(
    city_entry: dict,
    metric: str,
    *,
    project: dict | None = None,
) -> Any:
    run_stats = city_run_stats(city_entry)
    summary = city_entry.get("summary") or {}
    model_id = _city_model_id(city_entry, project)
    try:
        primary = get_model(model_id).primary_metric
    except ValueError:
        primary = ""

    if metric == "mean_lst_C" and primary == "mean_C":
        return run_stats.get("mean_C") or run_stats.get("tract_mean_lst_C")
    if metric in (primary, "primary_value"):
        return run_stats.get(metric) or run_stats.get(primary)
    if metric in summary:
        return summary.get(metric)
    if metric.startswith("avg_") and metric[4:] in summary:
        return summary.get(metric[4:])
    return summary.get(metric) or run_stats.get(metric)


def _detect_metric(question: str, *, project: dict | None = None) -> str | None:
    q = question.lower()
    for metric, aliases in METRIC_ALIASES.items():
        if metric.replace("_", " ") in q:
            return metric
        for alias in aliases:
            if alias in q:
                return metric
    if "difference" in q or "compare" in q or "versus" in q or " vs " in q:
        return _default_metric(project)
    return None


def _target_city_keys(question: str, cities: dict[str, dict], ready: list[dict]) -> list[str]:
    mentioned = detect_cities_in_question(question, cities)
    if len(mentioned) >= 2:
        return mentioned[:10]
    if len(mentioned) == 1:
        return mentioned
    return [c["key"] for c in ready]


def _comparison_rows(
    target_keys: list[str],
    cities: dict[str, dict],
    metric: str,
    *,
    project: dict | None = None,
    require_ready: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in target_keys:
        entry = cities.get(key)
        if not entry:
            continue
        if require_ready and entry.get("status") != "ready":
            continue
        rows.append(
            {
                "key": key,
                "name": entry.get("name") or entry.get("address"),
                "metric": metric,
                "value": _city_metric_value(entry, metric, project=project),
                "run_stats": city_run_stats(entry),
                "summary": entry.get("summary"),
            }
        )
    return rows


def _is_temperature_metric(metric: str) -> bool:
    return metric in ("mean_lst_C", "mean_C")


def _summarize_comparison(
    rows: list[dict[str, Any]],
    metric: str,
    *,
    demo_hottest: dict[str, Any] | None = None,
) -> str:
    numeric = [r for r in rows if isinstance(r.get("value"), (int, float))]
    if demo_hottest and _is_temperature_metric(metric) and len(numeric) >= 1:
        hottest = max(numeric, key=lambda r: r["value"])
        count = demo_hottest["city_count"]
        return (
            f"{hottest['name']} has the highest demo LST ({hottest['value']}°C) "
            f"across the {count}-city portfolio."
        )
    if len(numeric) >= 2:
        sorted_rows = sorted(numeric, key=lambda r: r["value"])
        low = sorted_rows[0]
        high = sorted_rows[-1]
        diff = round(high["value"] - low["value"], 2)
        return (
            f"{high['name']} has higher {metric.replace('_', ' ')} "
            f"({high['value']}) than {low['name']} ({low['value']}); difference ≈ {diff}."
        )
    if len(numeric) == 1:
        row = numeric[0]
        return f"{row['name']}: {metric.replace('_', ' ')} = {row['value']}."
    return "Could not compare numeric values for the mentioned cities."


def _build_comparison_result(
    rows: list[dict[str, Any]],
    metric: str,
    *,
    extra: dict[str, Any] | None = None,
    demo_hottest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"metric": metric, "cities": rows, **(extra or {})}
    numeric = [r for r in rows if isinstance(r.get("value"), (int, float))]

    if demo_hottest and _is_temperature_metric(metric) and len(numeric) >= 1:
        hottest = max(numeric, key=lambda r: r["value"])
        result["hottest"] = hottest

    result["summary"] = _summarize_comparison(rows, metric, demo_hottest=demo_hottest)

    if len(numeric) >= 2 and not (demo_hottest and _is_temperature_metric(metric)):
        sorted_rows = sorted(numeric, key=lambda r: r["value"])
        result["difference"] = round(sorted_rows[-1]["value"] - sorted_rows[0]["value"], 2)
        result["highest"] = sorted_rows[-1]
        result["lowest"] = sorted_rows[0]

    return to_json_safe(result)


def compare_cities(project_id: str, question: str, *, projects_dir) -> dict[str, Any]:
    """Build a comparison block for chat from project manifest data."""
    project = get_project(project_id, projects_dir=Path(projects_dir))
    cities = project.get("cities") or {}
    ready = list_ready_cities(cities)

    if len(ready) < 1:
        return {
            "summary": "No cities with analysis results in this project yet.",
            "cities": [],
        }

    metric = _detect_metric(question, project=project) or _default_metric(project)
    rows = _comparison_rows(
        _target_city_keys(question, cities, ready),
        cities,
        metric,
        project=project,
        require_ready=True,
    )
    return _build_comparison_result(
        rows,
        metric,
        extra={"project_id": project_id},
    )


def compare_demo_cities(question: str, demo_cities: list[dict]) -> dict[str, Any]:
    """Cross-city comparison for the 11-city demo using placeholder LST temps."""
    cities: dict[str, dict] = {}
    for entry in demo_cities:
        name = entry.get("name") or ""
        if not name:
            continue
        key = re.sub(r"[^\w]+", "_", name.lower()).strip("_")
        cities[key] = {
            "name": name,
            "address": name,
            "status": "ready",
            "run_stats": {"mean_C": entry.get("peak_lst_C") or entry.get("temp")},
            "summary": entry.get("summary") or {},
        }

    metric = _detect_metric(question) or _default_metric()
    ready = [{"key": key} for key in cities]
    rows = _comparison_rows(
        _target_city_keys(question, cities, ready),
        cities,
        metric,
        require_ready=False,
    )
    return _build_comparison_result(
        rows,
        metric,
        extra={"mode": "demo"},
        demo_hottest={"city_count": len(demo_cities)} if _is_temperature_metric(metric) else None,
    )
