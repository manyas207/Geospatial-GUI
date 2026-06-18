"""Heat-equity burden ranking from tract GeoPackages (deterministic, pre-LLM)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np

from backend.core.constants import TRACT_LAYER
from backend.core.json_util import to_json_safe
from backend.layers.tract_query import DISPLAY_COLUMNS, load_tract_gdf

EQUITY_KEYWORDS = (
    "burden",
    "burdened",
    "vulnerability",
    "vulnerable",
    "equity",
    "low-income",
    "low income",
    "socioeconomic",
    "disadvantaged",
    "environmental justice",
    "inequity",
    "inequitable",
)

HEAT_KEYWORDS = ("heat", "lst", "temperature", "thermal", "hot")


def is_equity_burden_question(question: str) -> bool:
    """True when the user is asking about combined heat + social vulnerability."""
    q = question.lower()
    if any(kw in q for kw in EQUITY_KEYWORDS):
        return True
    has_heat = any(kw in q for kw in HEAT_KEYWORDS)
    has_vulnerability = any(
        word in q
        for word in (
            "low",
            "income",
            "poverty",
            "poor",
            "minority",
            "hispanic",
            "black",
            "latino",
            "disadvantaged",
            "overlap",
        )
    )
    return has_heat and has_vulnerability


def _parse_income_ceiling(question: str) -> float | None:
    match = re.search(
        r"(?:below|under|less than)\s*\$?\s*([\d,]+)\s*(?:k|thousand)?",
        question.lower(),
    )
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    value = float(raw)
    if "k" in match.group(0) or "thousand" in match.group(0):
        value *= 1000
    elif value < 1000:
        value *= 1000
    return value


def _zscore(series: Any) -> Any:
    numeric = series.astype(float)
    valid = numeric.dropna()
    if len(valid) < 2:
        return numeric * 0.0
    std = float(valid.std())
    if std == 0.0 or np.isnan(std):
        return numeric * 0.0
    return (numeric - float(valid.mean())) / std


def _row_dict(row: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for col in DISPLAY_COLUMNS:
        if col not in row.index:
            continue
        value = row[col]
        if value is None or (isinstance(value, float) and value != value):
            continue
        data[col] = to_json_safe(value)
    return data


def _lst_quartile_threshold(series: Any) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.quantile(0.75))


def _fmt_money(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _short_city_name(city: str | None) -> str:
    if not city:
        return "This city"
    return city.split(",")[0].strip()


def _short_tract_name(name: str | None, geoid: str | None = None) -> str:
    if name:
        if "Census Tract" in name:
            return name.split(";")[0].replace("Census Tract", "Tract").strip()
        if ";" in name:
            return name.split(";")[0].strip()
        return name.strip()
    if geoid:
        return f"Tract {geoid}"
    return "Unknown tract"


def analyze_equity_burden_gdf(
    gdf: gpd.GeoDataFrame,
    question: str,
    *,
    city_name: str | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Rank tracts by combined heat exposure and socioeconomic vulnerability."""
    income_ceiling = _parse_income_ceiling(question)
    working = gdf.copy()

    if "lst_mean_C" not in working.columns:
        return to_json_safe(
            {
                "city": city_name,
                "summary": (
                    "Tract-level land surface temperature is not available for this area. "
                    "Run the LST analysis on your uploads first, then ask again."
                ),
                "tract_count_analyzed": 0,
                "top_burdened_tracts": [],
            }
        )

    working = working[working["lst_mean_C"].notna()]
    if working.empty:
        return to_json_safe(
            {
                "city": city_name,
                "summary": "No tracts with LST values were found for this city.",
                "tract_count_analyzed": 0,
                "top_burdened_tracts": [],
            }
        )

    if income_ceiling is not None and "median_income_usd" in working.columns:
        working = working[working["median_income_usd"].notna()]
        working = working[working["median_income_usd"] < income_ceiling]

    scores = _zscore(working["lst_mean_C"]).fillna(0.0)
    if "median_income_usd" in working.columns:
        scores = scores - _zscore(working["median_income_usd"]).fillna(0.0)
    if "hispanic_pct" in working.columns:
        scores = scores + 0.5 * _zscore(working["hispanic_pct"]).fillna(0.0)
    if "black_pct" in working.columns:
        scores = scores + 0.5 * _zscore(working["black_pct"]).fillna(0.0)
    if "population_density_per_km2" in working.columns:
        scores = scores + 0.25 * _zscore(working["population_density_per_km2"]).fillna(0.0)

    working = working.assign(burden_score=scores)
    ranked = working.sort_values("burden_score", ascending=False)

    positive = ranked[ranked["burden_score"] > 0]
    top = positive.head(top_n) if not positive.empty else ranked.head(min(3, top_n))
    top_rows = []
    for _, row in top.iterrows():
        entry = _row_dict(row)
        entry["burden_score"] = round(float(row["burden_score"]), 3)
        top_rows.append(entry)

    highest_lst_idx = working["lst_mean_C"].idxmax()
    highest_lst_row = working.loc[highest_lst_idx]
    highest_lst = _row_dict(highest_lst_row)
    highest_lst["burden_score"] = round(float(highest_lst_row["burden_score"]), 3)

    lst_threshold = _lst_quartile_threshold(gdf["lst_mean_C"])
    high_lst_count = 0
    if lst_threshold is not None and "median_income_usd" in gdf.columns:
        mask = (
            gdf["lst_mean_C"].notna()
            & (gdf["lst_mean_C"] >= lst_threshold)
            & gdf["median_income_usd"].notna()
        )
        if income_ceiling is not None:
            mask &= gdf["median_income_usd"] < income_ceiling
        high_lst_count = int(mask.sum())

    city_label = city_name or "this city"
    filter_note = (
        f" (median income below ${income_ceiling:,.0f})" if income_ceiling is not None else ""
    )

    if not top_rows:
        summary = f"No tracts matched the equity burden criteria{filter_note} in {city_label}."
    else:
        lead = top_rows[0]
        lead_name = lead.get("acs_name") or lead.get("GEOID")
        summary = (
            f"In {city_label}, the highest heat-equity burden tract{filter_note} is "
            f"{_short_tract_name(lead.get('acs_name'), lead.get('GEOID'))} "
            f"({lead.get('lst_mean_C')}°C, {_fmt_money(lead.get('median_income_usd'))} income)."
        )
        if highest_lst.get("GEOID") != lead.get("GEOID"):
            hot_name = _short_tract_name(highest_lst.get("acs_name"), highest_lst.get("GEOID"))
            hot_income = highest_lst.get("median_income_usd")
            summary += (
                f" The hottest tract ({hot_name}, {highest_lst.get('lst_mean_C')}°C"
            )
            if hot_income is not None:
                summary += f", {_fmt_money(hot_income)} income) is not the most burdened."
            else:
                summary += ") is not the most burdened."

    return to_json_safe(
        {
            "city": city_name,
            "methodology": (
                "Burden score = z(LST) - z(median income) + 0.5*z(Hispanic %) "
                "+ 0.5*z(Black %) + 0.25*z(population density). "
                "Higher score = greater combined heat and socioeconomic vulnerability. "
                "High LST alone does not imply high burden if income is high."
            ),
            "income_filter_usd": income_ceiling,
            "lst_top_quartile_C": round(lst_threshold, 2) if lst_threshold is not None else None,
            "high_lst_tract_count": high_lst_count,
            "tract_count_analyzed": int(len(working)),
            "top_burdened_tracts": top_rows,
            "highest_lst_tract": highest_lst,
            "summary": summary,
        }
    )


def analyze_equity_burden(gpkg_path: Path, question: str, *, city_name: str | None = None) -> dict[str, Any]:
    gdf = load_tract_gdf(gpkg_path)
    return analyze_equity_burden_gdf(gdf, question, city_name=city_name)


def analyze_project_equity_burden(
    project_id: str,
    question: str,
    *,
    projects_dir: Path,
) -> dict[str, Any]:
    """Rank burden tracts for every ready city in a project."""
    from backend.projects.service import get_project, list_ready_cities

    project = get_project(project_id, projects_dir=projects_dir)
    ready = list_ready_cities(project.get("cities") or {})
    per_city: list[dict[str, Any]] = []

    for entry in ready:
        key = entry["key"]
        city_name = entry.get("name") or entry.get("address") or key
        gpkg = projects_dir / project_id / "cities" / key / "tracts.gpkg"
        if not gpkg.exists():
            continue
        gdf = load_tract_gdf(gpkg)
        city_result = analyze_equity_burden_gdf(gdf, question, city_name=city_name)
        city_result["city_key"] = key
        per_city.append(city_result)

    if not per_city:
        return to_json_safe(
            {
                "project_id": project_id,
                "summary": "No ready cities with tract GeoPackages found in this project.",
                "cities": [],
            }
        )

    with_tracts = [c for c in per_city if c.get("top_burdened_tracts")]
    if with_tracts:
        lead_city = max(
            with_tracts,
            key=lambda c: c["top_burdened_tracts"][0].get("burden_score", 0),
        )
        lead_tract = lead_city["top_burdened_tracts"][0]
        lead_name = _short_tract_name(lead_tract.get("acs_name"), lead_tract.get("GEOID"))
        city_short = _short_city_name(lead_city.get("city"))
        summary = (
            f"Across {len(with_tracts)} cities, the greatest combined heat-equity burden is "
            f"{lead_name} in {city_short} "
            f"({lead_tract.get('lst_mean_C')}°C, {_fmt_money(lead_tract.get('median_income_usd'))} income)."
        )
    else:
        summary = "No tract-level LST data available yet for project cities. Run LST analysis first."

    return to_json_safe(
        {
            "project_id": project_id,
            "project_name": project.get("name"),
            "city_count": len(per_city),
            "summary": summary,
            "cities": per_city,
            "top_burdened_tracts": _flatten_top_tracts(per_city, top_n=10),
        }
    )


def _flatten_top_tracts(per_city: list[dict[str, Any]], *, top_n: int) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for city_result in per_city:
        city_label = city_result.get("city") or city_result.get("city_key")
        for tract in city_result.get("top_burdened_tracts") or []:
            combined.append({**tract, "city": city_label, "city_key": city_result.get("city_key")})
    combined.sort(key=lambda row: row.get("burden_score", 0), reverse=True)
    return combined[:top_n]


def _fmt_tract_brief(tract: dict[str, Any]) -> str:
    return (
        f"{tract.get('lst_mean_C')}C, {_fmt_money(tract.get('median_income_usd'))} income, "
        f"{tract.get('hispanic_pct', '-')}pct Hispanic, {tract.get('black_pct', '-')}pct Black"
    )


def _fmt_tract_line(rank: int, tract: dict[str, Any], *, city: str | None = None) -> str:
    name = _short_tract_name(tract.get("acs_name"), tract.get("GEOID"))
    city_bit = f" ({_short_city_name(city)})" if city else ""
    return f"{rank}. {name}{city_bit} - {_fmt_tract_brief(tract)}"


def _hot_tract_contrasts(equity: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], str | None]]:
    contrasts: list[tuple[dict[str, Any], dict[str, Any], str | None]] = []
    if equity.get("cities"):
        for city_result in equity["cities"]:
            hot = city_result.get("highest_lst_tract")
            top = (city_result.get("top_burdened_tracts") or [None])[0]
            if hot and top and hot.get("GEOID") != top.get("GEOID"):
                contrasts.append((hot, top, city_result.get("city") or city_result.get("city_key")))
        return contrasts

    hot = equity.get("highest_lst_tract")
    lead = (equity.get("top_burdened_tracts") or [None])[0]
    if hot and lead and hot.get("GEOID") != lead.get("GEOID"):
        contrasts.append((hot, lead, equity.get("city")))
    return contrasts


def format_equity_burden_answer(equity: dict[str, Any]) -> str | None:
    """Build a direct, scannable answer from ranked burden data."""
    if not equity:
        return None

    top_tracts = equity.get("top_burdened_tracts") or []
    if not top_tracts and equity.get("cities"):
        top_tracts = _flatten_top_tracts(equity["cities"], top_n=10)

    if not top_tracts:
        summary = equity.get("summary")
        return summary if summary else None

    cities = equity.get("cities") or []
    lines: list[str] = []

    if len(cities) > 1:
        lines.append(f"HEAT-EQUITY BURDEN ({len(cities)} cities)")
        lines.append("")
        lines.append("Highest burden per city:")
        for city_result in cities:
            city_label = _short_city_name(city_result.get("city"))
            top = (city_result.get("top_burdened_tracts") or [None])[0]
            if not top:
                continue
            tract_name = _short_tract_name(top.get("acs_name"), top.get("GEOID"))
            lines.append(f"  {city_label}: {tract_name}")
            lines.append(f"    {_fmt_tract_brief(top)}")
        lines.append("")
        if len(top_tracts) > len(cities):
            lines.append("Project-wide ranking:")
            for index, tract in enumerate(top_tracts[:5], start=1):
                lines.append(_fmt_tract_line(index, tract, city=tract.get("city")))
    else:
        city_label = _short_city_name(equity.get("city") or (cities[0].get("city") if cities else None))
        lead = top_tracts[0]
        lead_name = _short_tract_name(lead.get("acs_name"), lead.get("GEOID"))
        lines.append(f"HEAT-EQUITY BURDEN — {city_label}")
        lines.append("")
        lines.append(f"Most burdened: {lead_name}")
        lines.append(f"  {_fmt_tract_brief(lead)}")
        if len(top_tracts) > 1:
            lines.append("")
            lines.append("Also high burden:")
            for index, tract in enumerate(top_tracts[1:5], start=2):
                tract_name = _short_tract_name(tract.get("acs_name"), tract.get("GEOID"))
                lines.append(f"  {index}. {tract_name} — {_fmt_tract_brief(tract)}")

    contrasts = _hot_tract_contrasts(equity)
    if contrasts:
        lines.append("")
        lines.append("Note — hottest is not the same as most burdened:")
        for hot, lead, city_label in contrasts[:3]:
            city = _short_city_name(city_label)
            hot_name = _short_tract_name(hot.get("acs_name"), hot.get("GEOID"))
            lead_name = _short_tract_name(lead.get("acs_name"), lead.get("GEOID"))
            lines.append(
                f"  {city}: {hot_name} is hottest ({hot.get('lst_mean_C')}C, "
                f"{_fmt_money(hot.get('median_income_usd'))}), but {lead_name} has "
                f"greater combined burden ({lead.get('lst_mean_C')}C, "
                f"{_fmt_money(lead.get('median_income_usd'))})."
            )

    return "\n".join(lines).strip()
