"""Cross-city comparison for multi-city LST projects."""

from __future__ import annotations

import re
from typing import Any

from backend.geocode import CITY_CENTROIDS
from backend.json_util import to_json_safe
from backend.presets import PRESET_CITIES
from backend.project import get_project, list_ready_cities

METRIC_ALIASES: dict[str, list[str]] = {
    "mean_lst_C": ["lst", "temperature", "heat", "surface temperature"],
    "avg_density_per_km2": ["density", "population density"],
    "median_income_usd": ["income", "earnings"],
    "hispanic_pct": ["hispanic", "ethnic", "latino"],
    "tract_count": ["tract", "tracts"],
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


def _detect_metric(question: str) -> str | None:
    q = question.lower()
    for metric, aliases in METRIC_ALIASES.items():
        if metric.replace("_", " ") in q:
            return metric
        for alias in aliases:
            if alias in q:
                return metric
    if "difference" in q or "compare" in q or "versus" in q or " vs " in q:
        return "mean_lst_C"
    return None


def _city_run_stats(city_entry: dict) -> dict:
    return city_entry.get("run_stats") or city_entry.get("lst_stats") or {}


def _city_metric_value(city_entry: dict, metric: str) -> Any:
    run_stats = _city_run_stats(city_entry)
    summary = city_entry.get("summary") or {}

    if metric == "mean_lst_C":
        return run_stats.get("mean_C") or run_stats.get("tract_mean_lst_C")
    if metric in summary:
        return summary.get(metric)
    if metric.startswith("avg_") and metric[4:] in summary:
        return summary.get(metric[4:])
    return summary.get(metric) or run_stats.get(metric)


def compare_cities(project_id: str, question: str, *, projects_dir) -> dict[str, Any]:
    """Build a comparison block for chat from project manifest data."""
    from pathlib import Path

    project = get_project(project_id, projects_dir=Path(projects_dir))
    cities = project.get("cities") or {}
    ready = list_ready_cities(cities)

    if len(ready) < 1:
        return {
            "summary": "No cities with LST results in this project yet.",
            "cities": [],
        }

    mentioned = detect_cities_in_question(question, cities)
    if len(mentioned) >= 2:
        target_keys = mentioned[:10]
    elif len(mentioned) == 1:
        target_keys = mentioned
    else:
        target_keys = [c["key"] for c in ready]

    metric = _detect_metric(question) or "mean_lst_C"
    rows: list[dict[str, Any]] = []

    for key in target_keys:
        entry = cities.get(key)
        if not entry or entry.get("status") != "ready":
            continue
        value = _city_metric_value(entry, metric)
        rows.append(
            {
                "key": key,
                "name": entry.get("name") or entry.get("address"),
                "metric": metric,
                "value": value,
                "lst_stats": entry.get("lst_stats"),
                "summary": entry.get("summary"),
            }
        )

    result: dict[str, Any] = {
        "metric": metric,
        "cities": rows,
        "project_id": project_id,
    }

    numeric = [r for r in rows if isinstance(r.get("value"), (int, float))]
    if len(numeric) >= 2:
        sorted_rows = sorted(numeric, key=lambda r: r["value"])
        low = sorted_rows[0]
        high = sorted_rows[-1]
        diff = round(high["value"] - low["value"], 2)
        result["summary"] = (
            f"{high['name']} has higher {metric.replace('_', ' ')} "
            f"({high['value']}) than {low['name']} ({low['value']}); difference ≈ {diff}."
        )
        result["difference"] = diff
        result["highest"] = high
        result["lowest"] = low
    elif len(numeric) == 1:
        r = numeric[0]
        result["summary"] = f"{r['name']}: {metric.replace('_', ' ')} = {r['value']}."
    else:
        result["summary"] = "Could not compare numeric values for the mentioned cities."

    return to_json_safe(result)


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
            "lst_stats": {"mean_C": entry.get("peak_lst_C") or entry.get("temp")},
            "summary": entry.get("summary") or {},
        }

    metric = _detect_metric(question) or "mean_lst_C"
    mentioned = detect_cities_in_question(question, cities)
    if len(mentioned) >= 2:
        target_keys = mentioned[:10]
    elif len(mentioned) == 1:
        target_keys = mentioned
    else:
        target_keys = list(cities.keys())

    rows: list[dict[str, Any]] = []
    for key in target_keys:
        entry = cities.get(key)
        if not entry:
            continue
        value = _city_metric_value(entry, metric)
        rows.append(
            {
                "key": key,
                "name": entry.get("name"),
                "metric": metric,
                "value": value,
                "lst_stats": entry.get("lst_stats"),
                "summary": entry.get("summary"),
            }
        )

    result: dict[str, Any] = {
        "metric": metric,
        "cities": rows,
        "mode": "demo",
    }

    numeric = [r for r in rows if isinstance(r.get("value"), (int, float))]
    if metric == "mean_lst_C" and len(numeric) >= 1:
        hottest = max(numeric, key=lambda r: r["value"])
        result["hottest"] = hottest
        result["summary"] = (
            f"{hottest['name']} has the highest demo LST ({hottest['value']}°C) "
            f"across the {len(demo_cities)}-city portfolio."
        )
    elif len(numeric) >= 2:
        sorted_rows = sorted(numeric, key=lambda r: r["value"])
        low = sorted_rows[0]
        high = sorted_rows[-1]
        diff = round(high["value"] - low["value"], 2)
        result["summary"] = (
            f"{high['name']} has higher {metric.replace('_', ' ')} "
            f"({high['value']}) than {low['name']} ({low['value']}); difference ≈ {diff}."
        )
        result["difference"] = diff
        result["highest"] = high
        result["lowest"] = low
    elif len(numeric) == 1:
        r = numeric[0]
        result["summary"] = f"{r['name']}: {metric.replace('_', ' ')} = {r['value']}."
    else:
        result["summary"] = "Could not compare numeric values for the mentioned cities."

    return to_json_safe(result)
