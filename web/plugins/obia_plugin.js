import { createPlugin } from "../model_plugin.js";

const OBIA_CLASS_DEFAULTS = {
  labels: { 1: "Urban", 2: "Vegetation", 3: "Water", 4: "Bare soil" },
  colors: { 1: "#6e6e6e", 2: "#31a354", 3: "#2171b5", 4: "#d4b483" },
  noData: "#e8e8e8",
};

function classPresentation(pres) {
  return {
    labels: pres.classLabels || OBIA_CLASS_DEFAULTS.labels,
    colors: pres.classColors || OBIA_CLASS_DEFAULTS.colors,
    noData: OBIA_CLASS_DEFAULTS.noData,
  };
}

function formatClassLabel(classId, pres) {
  if (classId == null || classId === "") return "No data";
  const key = Number(classId);
  const labels = classPresentation(pres).labels;
  return labels[key] || `Class ${classId}`;
}

export default createPlugin({
  id: "obia",
  presentation: {
    dashboard: "equity",
    analysisLayerId: "analysis",
    choroplethField: "obia_mode_class",
    primaryMetricKeys: ["labeled_segments", "primary_value", "total_segments", "tract_mean_mode_pct"],
    barChartLabelProject: "Labeled segments",
    barChartLabelDemo: "Segments",
    barChartHeadingProject: "Labeled segments by city",
    barChartHeadingDemo: "Segments by city",
    metricUnit: "",
    primaryMetricSuffix: " seg",
    runVerb: "OBIA",
    runProgressWorking: "Still working — large OBIA runs can take several minutes.",
    runProgressStart: "Starting OBIA segmentation and classification on the server…",
    cardTitle: "Run OBIA for a city",
    portfolioHint:
      "Upload a multispectral GeoTIFF and training shapefile (.shp, .shx, .dbf) per city.",
    fileDropTitle: "Raster + training files",
    analysisLayerLabel: "OBIA land cover",
    heatmapLayerLabel: "Land cover class heatmap",
    legendLabel: "Land cover class",
    dashboardTitle: "OBIA Land Cover Dashboard",
    dashboardSubtitle: "Land cover + Population + Census",
    queryPlaceholder: "Ask about land cover, census tracts, or equity…",
    queryAriaLabel: "Ask about land cover or equity",
    emptyProjectHint:
      "No cities in this project. Use <strong>Back to Ask</strong> to upload raster and training files.",
    sourcesAnalysis: "OBIA segmentation + classification",
    tractPopupMetricLabel: "Dominant OBIA class",
    tractDetailLabel: "Dominant class",
    chatAnalysisLabel: "OBIA land-cover classification",
    chatContextSummary:
      "OBIA land-cover results for {city}. Dominant class per tract is obia_mode_class (1=urban, 2=vegetation, 3=water, 4=bare soil). Use obia_mode_pct and obia_segment_count on tracts; run_stats.labeled_segments and total_segments summarize the scene. This is land-cover classification, not temperature. Combine with Census fields for equity questions.",
    classLabels: OBIA_CLASS_DEFAULTS.labels,
    classColors: OBIA_CLASS_DEFAULTS.colors,
  },

  choroplethField(city, layerId, appMode, analysisLayerId) {
    if (layerId !== analysisLayerId) return null;
    if (appMode === "project" && city?.status === "ready") return "obia_mode_class";
    return null;
  },

  renderStats(city, stats) {
    const segments = stats?.labeled_segments ?? stats?.total_segments;
    if (segments == null) return `<p class="muted">No results yet</p>`;
    return `
      <div class="gf-stat-card">
        <div class="gf-stat-label">Labeled segments</div>
        <div class="gf-stat-val">${segments}</div>
      </div>`;
  },

  renderLegend({ field, pres, isAnalysisLayer, layerId, layerLabels }) {
    if (!isAnalysisLayer || field !== "obia_mode_class") return null;
    const { labels, colors, noData } = classPresentation(pres);
    return {
      title: layerLabels?.[layerId] || pres.legendLabel || "Land cover class",
      low: labels[1] || "Urban",
      high: labels[4] || "Bare soil",
      colorStops: [colors[1], colors[2], colors[3], colors[4], noData, noData, noData],
      showScaleControls: false,
    };
  },

  choroplethFillPaint(field, _valueRange, { pres, isAnalysisLayer }) {
    if (!isAnalysisLayer || field !== "obia_mode_class") return null;
    const { colors, noData } = classPresentation(pres);
    return {
      "fill-color": [
        "match",
        ["to-number", ["get", "obia_mode_class"]],
        1,
        colors[1] || OBIA_CLASS_DEFAULTS.colors[1],
        2,
        colors[2] || OBIA_CLASS_DEFAULTS.colors[2],
        3,
        colors[3] || OBIA_CLASS_DEFAULTS.colors[3],
        4,
        colors[4] || OBIA_CLASS_DEFAULTS.colors[4],
        noData,
      ],
      "fill-opacity": 0.82,
    };
  },

  formatChoroplethValue(value) {
    return formatClassLabel(value, this.presentation);
  },

  chatContext(city, stats) {
    const name = city?.name || city?.label || "this city";
    const labeled = stats?.labeled_segments ?? "—";
    const total = stats?.total_segments ?? "—";
    return `OBIA land-cover results for ${name}. Labeled segments: ${labeled}, total segments: ${total}. Use obia_mode_class on tracts (1=urban, 2=vegetation, 3=water, 4=bare soil).`;
  },

  keyQueries({ appMode }) {
    if (appMode !== "project") return null;
    return [
      {
        label: "Dominant land-cover classes",
        prompt:
          "Which dominant land-cover classes appear in my project cities and which tracts have the strongest class signal?",
        style: "gf-action-highlight",
      },
      {
        label: "City-by-city comparison",
        prompt:
          "Compare OBIA land-cover results across my project cities and rank them by labeled segment count.",
        style: "gf-action-highlight",
      },
      {
        label: "Low-income tracts + land cover",
        prompt:
          "In my project cities, where do low-income tracts overlap with urban or bare-soil dominant land cover?",
        style: "gf-action-equity",
      },
      {
        label: "Class coverage summary",
        prompt:
          "Summarize obia_mode_pct and obia_segment_count across tracts in my project and highlight areas with weak raster coverage.",
        style: "gf-action-equity",
      },
      {
        label: "Urban vs vegetation",
        prompt:
          "For my project cities, compare tracts dominated by urban (class 1) versus vegetation (class 2) land cover.",
      },
    ];
  },

  tractPopupMetric(props, field, layerLabel) {
    if (field && props[field] != null) {
      const display = formatClassLabel(props[field], this.presentation);
      return `<div class="gf-tract-popup-metric">${display}</div><div class="gf-tract-popup-metric-label">${layerLabel}</div>`;
    }
    return "";
  },

  tractDetailRow(props) {
    if (props.obia_mode_class != null) {
      return ["Dominant class", formatClassLabel(props.obia_mode_class, this.presentation)];
    }
    return null;
  },
});
