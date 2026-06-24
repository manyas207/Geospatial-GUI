"""Pearson correlations between tract-level map layers for dashboard chat."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
from scipy import stats

from backend.core.json_util import to_json_safe
from backend.layers.tract_query import load_tract_gdf

CORRELATION_KEYWORDS = (
    "correlat",
    "relationship",
    "associated",
    "association",
    "between layer",
    "between the layer",
    "layers of the map",
    "map layer",
    "how does",
    "how do",
    "related to",
    "link between",
    "connection between",
)

LAYER_FIELDS: dict[str, str] = {
    "lst_mean_C": "LST (°C)",
    "median_income_usd": "Median income ($)",
    "population_density_per_km2": "Population density (per km²)",
    "hispanic_pct": "Hispanic population share (%)",
    "black_pct": "Black population share (%)",
}

MIN_TRACTS = 5
MIN_PAIRS = 5


def is_correlation_question(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in CORRELATION_KEYWORDS)


def _strength_label(r: float) -> str:
    magnitude = abs(r)
    if magnitude >= 0.7:
        qualifier = "strong"
    elif magnitude >= 0.4:
        qualifier = "moderate"
    elif magnitude >= 0.2:
        qualifier = "weak"
    else:
        qualifier = "very weak"
    direction = "positive" if r >= 0 else "negative"
    return f"{qualifier} {direction}"


def _plain_strength(r: float) -> str:
    magnitude = abs(r)
    if magnitude >= 0.7:
        return "a clear pattern"
    if magnitude >= 0.4:
        return "a noticeable tendency"
    if magnitude >= 0.2:
        return "a modest tendency"
    return "little consistent connection"


def _pair_interpretation(field_a: str, field_b: str, r: float) -> str:
    """Plain-language reading of one tract-level correlation pair."""
    pair = frozenset({field_a, field_b})
    strength = _plain_strength(r)
    direction = "higher" if r > 0 else "lower"

    if pair == frozenset({"lst_mean_C", "population_density_per_km2"}):
        if r > 0.2:
            return (
                f"Denser tracts tend to run hotter — {strength} consistent with an "
                "urban heat-island effect at the neighborhood scale."
            )
        if r < -0.2:
            return (
                f"Surprisingly, denser tracts are somewhat cooler here ({strength}), "
                "which may reflect tree cover, land use mix, or how density is distributed."
            )
        return "Heat and population density show little linear alignment across tracts."

    if pair == frozenset({"lst_mean_C", "median_income_usd"}):
        if r < -0.2:
            return (
                f"Wealthier tracts tend to be cooler on average ({strength}), "
                "suggesting income and thermal exposure may diverge across the city."
            )
        if r > 0.2:
            return (
                f"Higher-income tracts are somewhat warmer here ({strength}) — "
                "worth checking whether that reflects suburban development patterns or sparse tree cover."
            )
        return "Income and land-surface temperature are largely unrelated in a straight-line sense."

    if pair == frozenset({"lst_mean_C", "hispanic_pct"}):
        if abs(r) < 0.2:
            return "Hispanic population share and heat exposure are only weakly linked tract-to-tract."
        return (
            f"Tracts with {direction} Hispanic share tend to have {direction} LST ({strength}), "
            "which may overlap with density, housing age, or impervious surface — not causation by itself."
        )

    if pair == frozenset({"lst_mean_C", "black_pct"}):
        if abs(r) < 0.2:
            return "Black population share and heat show little linear association across tracts."
        return (
            f"Tracts with {direction} Black population share tend toward {direction} temperatures ({strength}); "
            "interpret alongside income and density rather than in isolation."
        )

    if pair == frozenset({"median_income_usd", "population_density_per_km2"}):
        if r > 0.2:
            return f"Higher-density tracts also tend to have higher incomes ({strength})."
        if r < -0.2:
            return f"Denser tracts tend to have lower incomes ({strength}), a common urban pattern."
        return "Income and density are not strongly aligned across tracts."

    if pair == frozenset({"median_income_usd", "hispanic_pct"}):
        if r < -0.2:
            return (
                f"Tracts with larger Hispanic communities tend to have lower median incomes ({strength}), "
                "a socioeconomic pattern that can intersect with heat exposure."
            )
        if r > 0.2:
            return f"Hispanic share and income move together positively here ({strength})."
        return "Hispanic population share and income are only weakly associated."

    if pair == frozenset({"median_income_usd", "black_pct"}):
        if abs(r) < 0.2:
            return "Black population share and median income show little linear relationship."
        return (
            f"Income is {direction} in tracts with {direction} Black population share ({strength})."
        )

    if pair == frozenset({"population_density_per_km2", "hispanic_pct"}):
        return (
            f"Hispanic share and density {('rise together' if r > 0.2 else 'fall together' if r < -0.2 else 'show little alignment')} "
            f"across tracts ({strength})."
        )

    if pair == frozenset({"population_density_per_km2", "black_pct"}):
        return (
            f"Black population share and density {('rise together' if r > 0.2 else 'fall together' if r < -0.2 else 'show little alignment')} "
            f"across tracts ({strength})."
        )

    if pair == frozenset({"hispanic_pct", "black_pct"}):
        return (
            "Hispanic and Black population shares "
            + ("tend to move together" if r > 0.2 else "tend to diverge" if r < -0.2 else "are largely independent")
            + f" across tracts ({strength})."
        )

    label_a = LAYER_FIELDS.get(field_a, field_a)
    label_b = LAYER_FIELDS.get(field_b, field_b)
    if r > 0.2:
        return f"Higher {label_a} tends to coincide with higher {label_b} ({strength})."
    if r < -0.2:
        return f"Higher {label_a} tends to coincide with lower {label_b} ({strength})."
    return f"{label_a} and {label_b} show little linear relationship across tracts."


def _build_narrative_lead(
    correlations: list[dict[str, Any]],
    *,
    city_name: str | None,
    tract_count: int,
) -> str:
    if not correlations:
        return ""
    city = _short_city(city_name)
    top = correlations[0]
    return (
        f"Looking across {tract_count} census tracts in {city}, "
        f"the standout pattern links {top['label_a'].replace(' (°C)', '')} and "
        f"{top['label_b'].lower()}: {top['interpretation']}"
    )


def _short_city(city_name: str | None) -> str:
    if not city_name:
        return "this city"
    return city_name.split(",")[0].strip()


def _pair_correlation(series_a: Any, series_b: Any) -> tuple[float | None, int]:
    aligned = np.column_stack(
        [
            series_a.astype(float).to_numpy(),
            series_b.astype(float).to_numpy(),
        ]
    )
    mask = np.isfinite(aligned).all(axis=1)
    pairs = aligned[mask]
    if len(pairs) < MIN_PAIRS:
        return None, int(len(pairs))
    r, _ = stats.pearsonr(pairs[:, 0], pairs[:, 1])
    if not np.isfinite(r):
        return None, int(len(pairs))
    return float(r), int(len(pairs))


def analyze_layer_correlations_gdf(
    gdf: gpd.GeoDataFrame,
    *,
    city_name: str | None = None,
) -> dict[str, Any]:
    """Compute pairwise Pearson r across tract-level dashboard layers."""
    available = [field for field in LAYER_FIELDS if field in gdf.columns]
    working = gdf[available].copy()
    working = working.dropna(how="all")
    tract_count = len(working)

    if tract_count < MIN_TRACTS:
        return to_json_safe(
            {
                "city": city_name,
                "tract_count": tract_count,
                "correlations": [],
                "summary": (
                    f"Not enough census tracts with data ({tract_count}) to estimate "
                    "correlations reliably (need at least 5)."
                ),
            }
        )

    correlations: list[dict[str, Any]] = []
    for i, field_a in enumerate(available):
        for field_b in available[i + 1 :]:
            r, n_pairs = _pair_correlation(working[field_a], working[field_b])
            if r is None:
                continue
            correlations.append(
                {
                    "field_a": field_a,
                    "field_b": field_b,
                    "label_a": LAYER_FIELDS[field_a],
                    "label_b": LAYER_FIELDS[field_b],
                    "pearson_r": round(r, 3),
                    "tract_pairs": n_pairs,
                    "strength": _strength_label(r),
                    "interpretation": _pair_interpretation(field_a, field_b, r),
                }
            )

    correlations.sort(key=lambda item: abs(item["pearson_r"]), reverse=True)

    if not correlations:
        missing_lst = "lst_mean_C" not in available
        summary = (
            "Tract-level land surface temperature is not available, so heat–demographic "
            "correlations cannot be computed. Run LST analysis first."
            if missing_lst
            else "No overlapping tract data for the selected layers."
        )
    else:
        narrative_lead = _build_narrative_lead(
            correlations, city_name=city_name, tract_count=tract_count
        )
        top = correlations[0]
        summary = narrative_lead or (
            f"Across {tract_count} tracts in {_short_city(city_name)}, "
            f"the strongest association is between {top['label_a']} and {top['label_b']} "
            f"(r = {top['pearson_r']:+.2f})."
        )

    payload: dict[str, Any] = {
        "city": city_name,
        "tract_count": tract_count,
        "layers_analyzed": [LAYER_FIELDS[f] for f in available],
        "correlations": correlations,
        "summary": summary,
        "note": (
            "Pearson r measures linear association across census tracts, not causation. "
            "Values near 0 mean little linear relationship."
        ),
    }
    if correlations:
        payload["narrative_lead"] = summary
        payload["writing_guidance"] = (
            "Expand the narrative_lead and interpretation fields into 2–4 short paragraphs "
            "for a policy-minded reader. Do not list every r value; emphasize what patterns "
            "mean for heat exposure and equity in this city."
        )

    return to_json_safe(payload)


def analyze_layer_correlations(
    gpkg_path: Path,
    *,
    city_name: str | None = None,
) -> dict[str, Any]:
    gdf = load_tract_gdf(gpkg_path)
    return analyze_layer_correlations_gdf(gdf, city_name=city_name)


def format_correlation_answer(data: dict[str, Any]) -> str:
    if not data:
        return ""
    correlations = data.get("correlations") or []
    if not correlations:
        return data.get("summary") or "Correlation data is not available for this city."

    city = _short_city(data.get("city"))
    tract_count = data.get("tract_count", 0)
    paragraphs = [data.get("narrative_lead") or data.get("summary") or ""]

    top_key = None
    if correlations:
        top = correlations[0]
        top_key = frozenset({top["field_a"], top["field_b"]})

    secondary = [
        c
        for c in correlations
        if abs(c["pearson_r"]) >= 0.25
        and frozenset({c["field_a"], c["field_b"]}) != top_key
    ][:3]

    if secondary:
        also = " ".join(c["interpretation"] for c in secondary)
        paragraphs.append(f"Beyond that, {also}")

    paragraphs.append(
        f"These patterns are estimated across {tract_count} tracts in {city} and describe "
        "how variables move together — not what causes what. Local land use, tree cover, "
        "and building materials can all shape heat beyond what tract averages show."
    )

    return "\n\n".join(p for p in paragraphs if p.strip())
