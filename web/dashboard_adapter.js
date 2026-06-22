/**
 * Model registry client + plugin registry (per-model presentation & rendering).
 */
import lstPlugin from "./plugins/lst_plugin.js";
import obiaPlugin from "./plugins/obia_plugin.js";

const PLUGINS = {};
[lstPlugin, obiaPlugin].forEach((plugin) => {
  PLUGINS[plugin.id] = plugin;
});

const DEFAULT_PRESENTATION = {
  dashboard: "equity",
  analysisLayerId: "analysis",
  choroplethField: null,
  primaryMetricKeys: [],
  barChartLabelProject: "Primary metric",
  barChartLabelDemo: "Peak value",
  metricUnit: "",
  runVerb: "analysis",
  cardTitle: "Run analysis for a city",
  portfolioHint: "Add input files per city for the selected model.",
  fileDropTitle: "Input files",
  analysisLayerLabel: "Analysis result",
  legendLabel: "Analysis",
  tractPopupMetricLabel: "Analysis",
  tractDetailLabel: "Primary metric",
  chatAnalysisLabel: "analysis output",
};

let modelsCache = null;
let modelsPromise = null;

function normalizeModelId(modelId) {
  return (modelId || "lst").toLowerCase();
}

function getPlugin(modelId) {
  return PLUGINS[normalizeModelId(modelId)] || PLUGINS.lst;
}

function mergePresentation(modelId, apiSpec) {
  const plugin = getPlugin(modelId);
  const preset = plugin.presentation || {};
  const primaryMetric = apiSpec?.primary_metric || preset.primaryMetric || "";
  const primaryMetricKeys = preset.primaryMetricKeys?.length
    ? preset.primaryMetricKeys
    : primaryMetric
      ? [primaryMetric]
      : [];

  return {
    ...DEFAULT_PRESENTATION,
    ...apiSpec,
    ...preset,
    id: normalizeModelId(modelId),
    primaryMetric,
    primaryMetricKeys,
    dashboard: apiSpec?.dashboard || preset.dashboard || "equity",
  };
}

async function fetchModels(options = {}) {
  const force = Boolean(options.force);
  if (modelsCache && !force) return modelsCache;
  if (modelsPromise) return modelsPromise;

  modelsPromise = (async () => {
    const cacheBust = force ? `?t=${Date.now()}` : "";
    const response = await fetch(`/api/models${cacheBust}`, {
      cache: force ? "no-store" : "default",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(
        typeof payload.detail === "string" ? payload.detail : "Could not load analysis models."
      );
    }
    const models = (payload.models || []).map((spec) => ({
      ...spec,
      presentation: mergePresentation(spec.id, spec),
    }));
    if (!models.length) {
      throw new Error("No analysis models are registered on the server.");
    }
    modelsCache = models;
    return modelsCache;
  })();

  try {
    return await modelsPromise;
  } finally {
    modelsPromise = null;
  }
}

function invalidateModelsCache() {
  modelsCache = null;
  modelsPromise = null;
}

function listModels() {
  return modelsCache || [];
}

function getModelSpec(modelId) {
  const id = normalizeModelId(modelId);
  return listModels().find((m) => m.id === id) || null;
}

function getPresentation(modelId) {
  const spec = getModelSpec(modelId);
  if (spec?.presentation) return spec.presentation;
  return mergePresentation(modelId || "lst", spec || { id: modelId, primary_metric: "" });
}

function inputAccept(modelId) {
  const spec = getModelSpec(modelId);
  if (!spec?.input_schema?.length) return ".tif,.tiff,.geotiff,.gtiff";
  const accepts = spec.input_schema
    .map((field) => field.accept)
    .filter(Boolean)
    .join(",");
  return accepts || "*/*";
}

function inputHint(modelId) {
  const spec = getModelSpec(modelId);
  if (!spec?.input_schema?.length) return "Upload required input files";
  return spec.input_schema.map((field) => field.hint || field.label).join(" · ");
}

function fileDropTitle(modelId) {
  const spec = getModelSpec(modelId);
  const first = spec?.input_schema?.[0];
  return first?.label || getPresentation(modelId).fileDropTitle;
}

function cityRunStats(city) {
  return city?.run_stats || {};
}

function cityRunWarning(city) {
  const stats = cityRunStats(city);
  return stats.tract_zonal_warning || stats.run_warning || null;
}

function cityPrimaryValue(city, modelId) {
  if (cityRunWarning(city)) return null;
  const stats = cityRunStats(city);
  const pres = getPresentation(modelId);
  for (const key of pres.primaryMetricKeys) {
    if (stats[key] != null && stats[key] !== "") return stats[key];
  }
  if (pres.primaryMetric && stats[pres.primaryMetric] != null) {
    return stats[pres.primaryMetric];
  }
  return null;
}

function formatPrimaryValue(value, modelId) {
  if (value == null || value === "") return "—";
  const unit = getPresentation(modelId).metricUnit;
  return unit ? `${value}${unit}` : String(value);
}

function formatPrimaryValueShort(value, modelId) {
  if (value == null || value === "") return "—";
  const pres = getPresentation(modelId);
  const unit = pres.metricUnit;
  if (unit === "°C") return `${value}°`;
  if (pres.primaryMetricSuffix) return `${value}${pres.primaryMetricSuffix}`;
  return formatPrimaryValue(value, modelId);
}

function choroplethField(modelId, layerId, appMode, city) {
  const plugin = getPlugin(modelId);
  const pres = getPresentation(modelId);
  return plugin.choroplethField(city, layerId, appMode, pres.analysisLayerId);
}

function resolveProjectModelId(projectData, city) {
  return (
    city?.model_id ||
    projectData?.model_id ||
    (city && cityRunStats(city).model_id) ||
    "lst"
  );
}

function extensionMatchesAccept(filename, accept) {
  if (!accept || accept === "*/*") return true;
  const lower = filename.toLowerCase();
  return accept.split(",").some((part) => {
    const token = part.trim().toLowerCase();
    if (!token) return false;
    if (token.startsWith(".")) return lower.endsWith(token);
    return lower.endsWith(`.${token}`);
  });
}

function genericEquityKeyQueries(ctx) {
  const pres = getPresentation(ctx.modelId);
  const metric = pres.legendLabel || "analysis metric";
  const analysisName = pres.chatAnalysisLabel || "analysis output";
  const cityScope = ctx.appMode === "demo" ? "all 11 demo cities" : "my project cities";

  if (pres.dashboard === "equity") {
    return [
      {
        label: `${metric} hotspots`,
        prompt: `Which city in my project has the highest ${metric} and what are the top hotspot tracts?`,
        style: "gf-action-highlight",
      },
      {
        label: "City-by-city comparison",
        prompt: `Compare ${analysisName} across my project cities and rank them from highest to lowest.`,
        style: "gf-action-highlight",
      },
      {
        label: "Low-income exposure",
        prompt: `In my project cities, where do low-income tracts overlap most with high ${metric}?`,
        style: "gf-action-equity",
      },
      {
        label: "Equity burden summary",
        prompt:
          "Summarize which communities appear most burdened by heat exposure and socioeconomic vulnerability in my project data.",
        style: "gf-action-equity",
      },
      {
        label: "Population density relationship",
        prompt: `For ${cityScope}, explain the relationship between population density and ${metric}.`,
      },
    ];
  }

  return [
    {
      label: `${metric} overview`,
      prompt: `Summarize ${analysisName} across my project cities and highlight the highest and lowest results.`,
      style: "gf-action-highlight",
    },
    {
      label: "Top city and tract",
      prompt: `Which city and tract in my project have the strongest ${metric} signal?`,
      style: "gf-action-highlight",
    },
    {
      label: "Cross-city ranking",
      prompt: `Rank my project cities by ${analysisName} and explain key differences.`,
    },
    {
      label: "Outlier detection",
      prompt: `Identify outlier tracts in my project data and explain why they stand out for ${metric}.`,
    },
    {
      label: "Actionable summary",
      prompt: "Give a concise decision-oriented summary of the main findings for my current project.",
    },
  ];
}

function keyQueries(modelId, ctx) {
  const plugin = getPlugin(modelId);
  const pluginQueries = plugin.keyQueries({ ...ctx, modelId });
  if (pluginQueries) return pluginQueries;
  return genericEquityKeyQueries({ ...ctx, modelId });
}

const DashboardAdapter = {
  fetchModels,
  invalidateModelsCache,
  listModels,
  getModelSpec,
  getPresentation,
  getPlugin,
  keyQueries,
  inputAccept,
  inputHint,
  fileDropTitle,
  cityRunStats,
  cityRunWarning,
  cityPrimaryValue,
  formatPrimaryValue,
  formatPrimaryValueShort,
  choroplethField,
  resolveProjectModelId,
  extensionMatchesAccept,
  registerPlugin(plugin) {
    if (plugin?.id) PLUGINS[plugin.id] = plugin;
  },
};

window.DashboardAdapter = DashboardAdapter;

export default DashboardAdapter;
