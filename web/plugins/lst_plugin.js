import { createPlugin } from "../model_plugin.js";

const LST_COLOR_STOPS = [
  "#ffffcc",
  "#ffeda0",
  "#fed976",
  "#feb24c",
  "#fd8d3c",
  "#fc4e2a",
  "#e31a1c",
  "#b10026",
];

function buildRangeInterpolate(valueExpr, range, colors) {
  const stops = colors.length;
  const expr = ["interpolate", ["linear"], valueExpr];
  for (let i = 0; i < stops; i += 1) {
    const t = stops === 1 ? 0 : i / (stops - 1);
    expr.push(range.min + t * (range.max - range.min));
    expr.push(colors[i]);
  }
  return expr;
}

export default createPlugin({
  id: "lst",
  presentation: {
    dashboard: "equity",
    analysisLayerId: "analysis",
    choroplethField: "lst_mean_C",
    primaryMetricKeys: ["mean_C", "tract_mean_lst_C"],
    barChartLabelProject: "Mean LST (°C)",
    barChartLabelDemo: "Peak LST (°C)",
    barChartHeadingProject: "Mean LST by city (°C)",
    barChartHeadingDemo: "Peak LST by city (°C)",
    metricUnit: "°C",
    runVerb: "LST",
    runProgressWorking: "Still working — LST processing can take several minutes for large scenes.",
    runProgressStart: "Starting LST analysis on the server…",
    cardTitle: "Run analysis for a city",
    portfolioHint:
      "Add input files per city for the selected model. Repeat for each city in your portfolio.",
    fileDropTitle: "Input files",
    analysisLayerLabel: "Land surface temperature",
    heatmapLayerLabel: "LST heatmap",
    legendLabel: "LST",
    dashboardTitle: "Urban Heat & Equity GUI Frame",
    dashboardSubtitle: "LST + Population + Census Analysis Platform",
    queryPlaceholder: "Ask about LST, census tracts, or equity…",
    queryAriaLabel: "Ask about LST or equity",
    emptyProjectHint:
      "No cities in this project. Use <strong>Back to Ask</strong> to upload Landsat bands.",
    sourcesAnalysis: "LST raster + zonal join",
    tractPopupMetricLabel: "Land surface temperature",
    tractDetailLabel: "LST mean",
    chatAnalysisLabel: "land surface temperature (LST)",
    chatContextSummary:
      "Land surface temperature (LST) results for {city}. Use lst_mean_C on tracts and run_stats mean_C for city summaries. Combine with Census income and population fields for equity questions.",
  },

  choroplethField(city, layerId, appMode, analysisLayerId) {
    if (layerId !== analysisLayerId) return null;
    if (appMode === "project" && city?.status === "ready") return "lst_mean_C";
    return null;
  },

  renderStats(city, stats) {
    if (!stats?.mean_C) return `<p class="muted">No results yet</p>`;
    return `
      <div class="gf-stat-card">
        <div class="gf-stat-label">Mean LST</div>
        <div class="gf-stat-val">${stats.mean_C}°C</div>
      </div>`;
  },

  usesLocalValueScale(field) {
    return field === "lst_mean_C" || field === "lst_max_C" || (field && field.endsWith("_C"));
  },

  showsScaleControls({ appMode, city, field, isAnalysisLayer }) {
    if (appMode !== "project" || !isAnalysisLayer || city?.status !== "ready") return false;
    return field === "lst_mean_C";
  },

  renderLegend({ field, scaleMode, tractLegendRange, pres, isAnalysisLayer, layerId, layerLabels }) {
    if (!isAnalysisLayer || field !== "lst_mean_C") return null;
    const titleBase = layerLabels?.[layerId] || pres.legendLabel || "LST";
    if ((scaleMode === "local" || scaleMode === "project") && tractLegendRange) {
      const scopeLabel = scaleMode === "project" ? "all cities" : "this city";
      return {
        title: `${titleBase} (${scopeLabel})`,
        low: `${tractLegendRange.actualMin.toFixed(1)}°`,
        high: `${tractLegendRange.actualMax.toFixed(1)}°`,
        colorStops: LST_COLOR_STOPS,
        showScaleControls: true,
      };
    }
    return {
      title: titleBase,
      low: "Low",
      high: "High",
      colorStops: LST_COLOR_STOPS,
      showScaleControls: true,
    };
  },

  choroplethFillPaint(field, valueRange, { scaleMode, isAnalysisLayer }) {
    if (!this.usesLocalValueScale(field) || !isAnalysisLayer) return null;
    const value = ["coalesce", ["to-number", ["get", field]], 0];
    if ((scaleMode === "local" || scaleMode === "project") && valueRange) {
      return {
        "fill-color": buildRangeInterpolate(value, valueRange, LST_COLOR_STOPS),
        "fill-opacity": 0.82,
      };
    }
    return {
      "fill-color": buildRangeInterpolate(
        value,
        valueRange || { min: 25, max: 45 },
        LST_COLOR_STOPS
      ),
      "fill-opacity": 0.82,
    };
  },

  formatChoroplethValue(value) {
    if (value == null || value === "") return "—";
    return `${value}°C`;
  },

  chatContext(city, stats) {
    const name = city?.name || city?.label || "this city";
    const mean = stats?.mean_C ?? stats?.tract_mean_lst_C ?? "—";
    const median = stats?.median_C ?? "—";
    return `LST results for ${name}. Mean: ${mean}°C, Median: ${median}°C. Use lst_mean_C on tracts for equity analysis.`;
  },

  keyQueries({ appMode }) {
    if (appMode !== "demo") return null;
    return [
      {
        label: "Hottest month, all cities",
        prompt:
          "Which city had the hottest month overall across all 11 demo cities, and what is the peak LST value?",
        style: "gf-action-highlight",
      },
      {
        label: "Hottest month per city",
        prompt: "Show the hottest month for each of the 11 demo cities with average LST values.",
        style: "gf-action-highlight",
      },
      {
        label: "Low-income + high LST",
        prompt:
          "Which low-income census tracts across all 11 demo cities have the highest LST exposure? Focus on income below $40k.",
        style: "gf-action-equity",
      },
      {
        label: "Ethnic community heat burden",
        prompt:
          "Which ethnic community has the highest heat exposure across all 11 demo cities? Rank by average LST in majority-minority tracts.",
        style: "gf-action-equity",
      },
      {
        label: "Population density vs LST",
        prompt:
          "Compare population density vs LST for all 11 demo cities. Which city shows the strongest urban heat island pattern?",
      },
      {
        label: "Monthly LST trends",
        prompt:
          "Generate a monthly LST trend summary for all 11 demo cities showing variation across 12 months.",
      },
    ];
  },

  tractPopupMetric(props, field) {
    if (field && props[field] != null) {
      return `<div class="gf-tract-popup-metric">${props[field]}°C</div><div class="gf-tract-popup-metric-label">Land surface temperature</div>`;
    }
    return "";
  },

  tractDetailRow(props) {
    if (props.lst_mean_C != null) return ["LST mean", `${props.lst_mean_C}°C`];
    return null;
  },
});
