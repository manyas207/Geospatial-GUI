/**
 * Model registry client + per-model dashboard presentation (Phase 3–4).
 */
(function (global) {
  const PRESENTATION = {
    lst: {
      dashboard: "equity",
      analysisLayerId: "lst",
      choroplethField: "lst_mean_C",
      primaryMetricKeys: ["mean_C", "tract_mean_lst_C"],
      barChartLabelProject: "Mean LST (°C)",
      barChartLabelDemo: "Peak LST (°C)",
      metricUnit: "°C",
      runVerb: "LST",
      cardTitle: "Run analysis for a city",
      portfolioHint:
        "Add input files per city for the selected model. Repeat for each city in your portfolio.",
      fileDropTitle: "Input files",
      analysisLayerLabel: "Land surface temperature",
      legendLabel: "LST",
      tractPopupMetricLabel: "Land surface temperature",
      tractDetailLabel: "LST mean",
      chatAnalysisLabel: "land surface temperature (LST)",
    },
    obia: {
      dashboard: "equity",
      analysisLayerId: "lst",
      choroplethField: "obia_mode_class",
      primaryMetricKeys: ["primary_value", "labeled_segments", "total_segments", "tract_mean_mode_pct"],
      barChartLabelProject: "Labeled segments",
      barChartLabelDemo: "Segments",
      metricUnit: "",
      runVerb: "OBIA",
      cardTitle: "Run OBIA for a city",
      portfolioHint:
        "Upload a multispectral GeoTIFF and training shapefile (.shp, .shx, .dbf) per city.",
      fileDropTitle: "Raster + training files",
      analysisLayerLabel: "OBIA land cover",
      legendLabel: "Land cover class",
      tractPopupMetricLabel: "Dominant OBIA class",
      tractDetailLabel: "Dominant class",
      chatAnalysisLabel: "OBIA land-cover classification",
    },
  };

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

  function mergePresentation(modelId, apiSpec) {
    const preset = PRESENTATION[modelId] || {};
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
      id: modelId,
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
    const id = (modelId || "lst").toLowerCase();
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
    return city?.run_stats || city?.lst_stats || {};
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
    const unit = getPresentation(modelId).metricUnit;
    if (unit === "°C") return `${value}°`;
    return formatPrimaryValue(value, modelId);
  }

  function choroplethField(modelId, layerId, appMode, city) {
    const pres = getPresentation(modelId);
    if (layerId === pres.analysisLayerId) {
      if (appMode === "project" && city?.status === "ready") {
        const fromVector = city?.vector_layer?.fields?.find((f) => f === pres.choroplethField);
        if (fromVector) return pres.choroplethField;
        if (pres.choroplethField) return pres.choroplethField;
      }
      return null;
    }
    return null;
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

  global.DashboardAdapter = {
    fetchModels,
    invalidateModelsCache,
    listModels,
    getModelSpec,
    getPresentation,
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
  };
})(window);
