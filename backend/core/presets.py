"""Canonical list of 11 demo/preset US cities (single source of truth)."""

from __future__ import annotations

PRESET_CITIES: list[dict[str, str | float]] = [
    {"key": "phoenix_az", "name": "Phoenix, AZ", "color": "#c45a1a", "peak_lst_C": 42.3, "month": "July"},
    {"key": "houston_tx", "name": "Houston, TX", "color": "#d4652a", "peak_lst_C": 39.1, "month": "August"},
    {"key": "dallas_tx", "name": "Dallas, TX", "color": "#d4652a", "peak_lst_C": 38.4, "month": "July"},
    {"key": "miami_fl", "name": "Miami, FL", "color": "#e07b32", "peak_lst_C": 37.8, "month": "August"},
    {"key": "los_angeles_ca", "name": "Los Angeles, CA", "color": "#e07b32", "peak_lst_C": 36.5, "month": "September"},
    {"key": "atlanta_ga", "name": "Atlanta, GA", "color": "#e07b32", "peak_lst_C": 36.1, "month": "July"},
    {"key": "memphis_tn", "name": "Memphis, TN", "color": "#e07b32", "peak_lst_C": 37.2, "month": "July"},
    {"key": "chicago_il", "name": "Chicago, IL", "color": "#3d7ea6", "peak_lst_C": 34.2, "month": "July"},
    {"key": "detroit_mi", "name": "Detroit, MI", "color": "#3d7ea6", "peak_lst_C": 33.8, "month": "July"},
    {"key": "baltimore_md", "name": "Baltimore, MD", "color": "#5a9ab8", "peak_lst_C": 33.4, "month": "July"},
    {"key": "cleveland_oh", "name": "Cleveland, OH", "color": "#5a9ab8", "peak_lst_C": 32.9, "month": "July"},
]

DEMO_CITY_ADDRESSES = [str(c["name"]) for c in PRESET_CITIES]

DEMO_CITY_LST = [
    {
        "name": c["name"],
        "peak_lst_C": c["peak_lst_C"],
        "month": c["month"],
        "color": c["color"],
    }
    for c in PRESET_CITIES
]
