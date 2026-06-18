"""On-demand PDF reports for multi-city projects (generated only at export time)."""

from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from backend.core.constants import TRACT_LAYER
from backend.layers.orchestrator import VECTOR_QUERY_FIELDS
from backend.layers.map_render import render_tract_map
from backend.projects.service import get_city_gpkg_path, get_project
from models.registry import get_model

MONTH_NAMES = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

ANALYSIS_LAYER_CMAPS = {
    "lst_mean_C": ("inferno", "Land surface temperature (mean °C)"),
    "lst_max_C": ("inferno", "Land surface temperature (max °C)"),
    "obia_mode_class": ("viridis", "Dominant OBIA land-cover class"),
    "obia_mode_pct": ("YlGn", "Dominant class coverage (%)"),
}


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\-.]+", "_", name.strip()).strip("._")
    return (cleaned[:80] or "report").lower()


def _choropleth_field(spec, columns: set[str]) -> tuple[str | None, str, str]:
    """Return (field, cmap, title) for the map choropleth."""
    for field, (cmap, title) in ANALYSIS_LAYER_CMAPS.items():
        if field in spec.vector_fields and field in columns:
            return field, cmap, title

    census = set(VECTOR_QUERY_FIELDS)
    for field in spec.vector_fields:
        if field in columns and field not in census:
            label = field.replace("_", " ").title()
            return field, "viridis", label

    if spec.primary_metric and spec.primary_metric in columns:
        label = spec.primary_metric.replace("_", " ").title()
        return spec.primary_metric, "viridis", label

    return None, "viridis", "Census tracts"


def _render_city_map(
    project_id: str,
    city_key: str,
    *,
    model_id: str,
    projects_dir: Path,
    tmp_dir: Path,
) -> Path | None:
    try:
        gpkg = get_city_gpkg_path(project_id, city_key, projects_dir=projects_dir)
    except FileNotFoundError:
        return None

    gdf = gpd.read_file(gpkg, layer=TRACT_LAYER)
    if gdf.empty:
        return None

    spec = get_model(model_id)
    field, cmap, title = _choropleth_field(spec, set(gdf.columns))
    geojson = json.loads(gdf.to_json())
    png_path = tmp_dir / f"{city_key}_map.png"
    render_tract_map(geojson, png_path, field=field, cmap=cmap, title=title)
    return png_path


def _fmt_num(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _observation_label(city: dict) -> str:
    month = city.get("month")
    year = city.get("year")
    if month and year:
        return f"{MONTH_NAMES[int(month)]} {year}"
    if year:
        return str(year)
    return "Not specified"


def _ready_cities(project: dict, city_key: str | None) -> list[tuple[str, dict]]:
    cities: dict[str, dict] = project.get("cities") or {}
    if city_key:
        entry = cities.get(city_key)
        if not entry:
            raise ValueError(f"City not found in project: {city_key}")
        if entry.get("status") != "ready":
            raise ValueError(f"City {city_key!r} is not ready for export.")
        return [(city_key, entry)]

    ready = [(key, entry) for key, entry in cities.items() if entry.get("status") == "ready"]
    if not ready:
        raise ValueError("No ready cities to include in the report.")
    return ready


class _ReportPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Page {self.page_no()}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _reset_x(pdf: FPDF) -> None:
    pdf.set_x(pdf.l_margin)


def _pdf_text(text: Any) -> str:
    """Helvetica is Latin-1 only; normalize common Unicode punctuation."""
    cleaned = str(text)
    return (
        cleaned.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _pdf_line(pdf: FPDF, text: str, *, bold: bool = False, size: int = 11) -> None:
    _reset_x(pdf)
    style = "B" if bold else ""
    pdf.set_font("Helvetica", style, size)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(pdf.epw, 5.5, _pdf_text(text))
    pdf.ln(1)
    _reset_x(pdf)


def _pdf_bullet(pdf: FPDF, label: str, value: str) -> None:
    label_width = 52
    _reset_x(pdf)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(label_width, 5.5, _pdf_text(f"{label}:"), new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(pdf.epw - label_width, 5.5, _pdf_text(value))
    _reset_x(pdf)


def build_project_report_pdf(
    project_id: str,
    *,
    city_key: str | None = None,
    chat_pairs: list[dict[str, str]] | None = None,
    base_url: str = "",
    projects_dir: Path,
) -> tuple[bytes, str]:
    """Build a PDF report in memory. Map PNGs are rendered on demand (not cached)."""
    project = get_project(project_id, projects_dir=projects_dir)
    model_id = project.get("model_id") or "lst"
    spec = get_model(model_id)
    cities = _ready_cities(project, city_key)
    chat_pairs = chat_pairs or []

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _pdf_text(project.get("name") or "Geospatial Project Report"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, _pdf_text(f"Analysis model: {spec.label}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, _pdf_text(f"Generated: {generated}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, _pdf_text(f"Ready cities: {project.get('ready_count', len(cities))}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    _reset_x(pdf)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for key, city in cities:
            _reset_x(pdf)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(26, 51, 72)
            city_name = city.get("name") or city.get("address") or key
            pdf.cell(0, 8, _pdf_text(city_name), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 5, _pdf_text(f"Address: {city.get('address', '-')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.cell(
                0,
                5,
                _pdf_text(f"Observation period: {_observation_label(city)}"),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.ln(2)
            _reset_x(pdf)

            summary = city.get("summary") or {}
            run_stats = city.get("run_stats") or city.get("lst_stats") or {}

            _pdf_line(pdf, "Census & demographics", bold=True, size=11)
            _pdf_bullet(pdf, "County", str(summary.get("county") or "-"))
            _pdf_bullet(pdf, "State", str(summary.get("state") or "-"))
            _pdf_bullet(pdf, "Tracts", _fmt_num(summary.get("tract_count")))
            _pdf_bullet(pdf, "Population", _fmt_num(summary.get("total_population")))
            _pdf_bullet(pdf, "Median income", (
                f"${_fmt_num(summary.get('median_income_usd'))}"
                if summary.get("median_income_usd") is not None
                else "-"
            ))
            _pdf_bullet(
                pdf,
                "Avg density",
                (
                    f"{_fmt_num(summary.get('avg_density_per_km2'))}/km2"
                    if summary.get("avg_density_per_km2") is not None
                    else "-"
                ),
            )
            pdf.ln(2)

            if run_stats:
                _pdf_line(pdf, "Analysis results", bold=True, size=11)
                shown: set[str] = set()
                for stat_key in (
                    "mean_C",
                    "tract_mean_lst_C",
                    "max_C",
                    "min_C",
                    "lst_max_C",
                    spec.primary_metric,
                ):
                    if not stat_key or stat_key in shown or run_stats.get(stat_key) is None:
                        continue
                    shown.add(stat_key)
                    label = stat_key.replace("_", " ").title()
                    unit = " °C" if stat_key.endswith("_C") or stat_key in ("mean_C", "max_C", "min_C") else ""
                    _pdf_bullet(pdf, label, f"{_fmt_num(run_stats[stat_key])}{unit}")
                warning = run_stats.get("tract_zonal_warning")
                if warning:
                    pdf.ln(1)
                    _pdf_line(pdf, f"Note: {warning}", size=9)
                pdf.ln(2)

            city_model_id = city.get("model_id") or model_id
            map_path = _render_city_map(
                project_id,
                key,
                model_id=city_model_id,
                projects_dir=projects_dir,
                tmp_dir=tmp_dir,
            )
            if map_path and map_path.exists():
                _pdf_line(pdf, "Map", bold=True, size=11)
                usable_width = pdf.epw
                pdf.image(str(map_path), w=usable_width)
                pdf.ln(3)
                _reset_x(pdf)

            gpkg_url = f"{base_url}/api/projects/{project_id}/cities/{key}/gpkg"
            _pdf_line(pdf, "GeoPackage download", bold=True, size=11)
            _reset_x(pdf)
            pdf.set_font("Helvetica", "U", 10)
            pdf.set_text_color(0, 51, 153)
            link_text = _pdf_text(f"Download tracts.gpkg for {city_name}")
            pdf.write(5, link_text, link=gpkg_url)
            pdf.ln(6)
            _reset_x(pdf)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(pdf.epw, 4.5, _pdf_text(f"Link (requires server): {gpkg_url}"))
            pdf.ln(4)
            _reset_x(pdf)

            if len(cities) > 1:
                pdf.add_page()

    if chat_pairs:
        if len(cities) > 1:
            pdf.add_page()
        _pdf_line(pdf, "Recent Q&A", bold=True, size=13)
        pdf.ln(1)
        for index, pair in enumerate(chat_pairs, start=1):
            question = (pair.get("question") or "").strip()
            answer = (pair.get("answer") or "").strip()
            if not question and not answer:
                continue
            _pdf_line(pdf, f"Q{index}: {question}", bold=True, size=10)
            _pdf_line(pdf, answer or "(no answer)", size=10)
            pdf.ln(2)

    pdf_bytes = bytes(pdf.output())
    slug = _safe_filename(project.get("name") or "report")
    city_suffix = f"-{city_key}" if city_key else ""
    filename = f"{slug}{city_suffix}-report.pdf"
    return pdf_bytes, filename
