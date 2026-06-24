/**
 * Urban Heat & Equity GUI Frame — shared state, DOM refs, and bootstrap helpers.
 */
(function () {
  const gf = (window.GfFrame = window.GfFrame || {});
  gf.adapter = window.DashboardAdapter;

  const ANALYSIS_LAYER_ID = "analysis";
  const LAYER_ORDER = [ANALYSIS_LAYER_ID, "density", "income", "ethnicity", "tracts"];
  const CHOROPLETH_LAYER_IDS = LAYER_ORDER;

  const LAYER_FIELDS = {
    density: "population_density_per_km2",
    income: "median_income_usd",
    ethnicity: "hispanic_pct",
    tracts: null,
  };

  gf.ANALYSIS_LAYER_ID = ANALYSIS_LAYER_ID;
  gf.LAYER_ORDER = LAYER_ORDER;
  gf.CHOROPLETH_LAYER_IDS = CHOROPLETH_LAYER_IDS;
  gf.LAYER_FIELDS = LAYER_FIELDS;

  gf.state = {
    demoCities: [],
    demoMaxTemp: 1,
    demoHottest: null,
    params: new URLSearchParams(window.location.search),
    appMode: "demo",
    projectId: null,
    projectData: null,
    projectModelId: "lst",
    adapterModelsPromise: null,
    projectCityList: [],
    demoPortfolioCache: {},
    demoOverview: null,
    demoPortfolioLoading: null,
    activeCityIndex: 0,
    cityLayersData: null,
    tractGeojsonCache: { token: null, data: null },
    chatMessages: [
      {
        role: "assistant",
        text: "Welcome! Select a city, hover tracts for details, or click a tract to zoom in.",
      },
    ],
    chatProjectId: null,
    chatLoading: false,
    projectGeojsonCache: {},
    projectLstRangeCache: null,
    tractLegendRange: null,
    lstScaleMode: (() => {
      const stored = localStorage.getItem("gf_lst_scale_mode");
      if (stored === "project" || stored === "fixed") return "project";
      return "local";
    })(),
    map: null,
    mapReady: false,
    popup: null,
    workerConfigured: false,
    hoveredTractId: null,
    tractInteractionsBound: false,
    uiWired: false,
    dataLoaded: false,
  };

  gf.dom = {
    cityListEl: document.getElementById("gfCityList"),
    barChartEl: document.getElementById("gfBarChart"),
    cityGridEl: document.getElementById("gfCityGrid"),
    mapOverlayEl: document.getElementById("gfMapOverlay"),
    mapLoadingEl: document.getElementById("gfMapLoading"),
    mapViewportEl: document.getElementById("gfMapViewport"),
    mapContainerEl: document.getElementById("gfMapLibre"),
    mapEmptyEl: document.getElementById("gfMapEmpty"),
    mapWarningEl: document.getElementById("gfMapWarning"),
    chatPanelEl: document.getElementById("gfPanelChat"),
    keyQueriesEl: document.getElementById("gfKeyQueries"),
    queryInputEl: document.getElementById("gfQueryInput"),
    queryInputLabelEl: document.querySelector('label[for="gfQueryInput"]'),
    sendBtnEl: document.getElementById("gfSendBtn"),
    legendTitleEl: document.getElementById("gfLegendTitle"),
    legendLowEl: document.getElementById("gfLegendLow"),
    legendHighEl: document.getElementById("gfLegendHigh"),
    legendBarEl: document.querySelector(".gf-legend-bar"),
    lstScaleWrapEl: document.getElementById("gfLstScaleWrap"),
    demoBadgeEl: document.getElementById("gfDemoBadge"),
    projectBadgeEl: document.getElementById("gfProjectBadge"),
    cityCountBadgeEl: document.getElementById("gfCityCountBadge"),
    layerAnalysisLabelEl: document.getElementById("gfLayerAnalysisLabel"),
    topbarTitleEl: document.getElementById("gfTopbarTitle"),
    topbarSubtitleEl: document.getElementById("gfTopbarSubtitle"),
  };

  function ensureAdapterModels() {
    const { adapter } = gf;
    const { state } = gf;
    if (!adapter) return Promise.resolve();
    if (!state.adapterModelsPromise) state.adapterModelsPromise = adapter.fetchModels().catch(() => null);
    return state.adapterModelsPromise;
  }

  function activeProjectModelId(city) {
    const { adapter, state } = gf;
    return adapter?.resolveProjectModelId(state.projectData, city) || state.projectModelId || "lst";
  }

  function modelPresentation(modelId) {
    const { adapter } = gf;
    return adapter?.getPresentation(modelId) || {
      dashboard: "equity",
      analysisLayerId: ANALYSIS_LAYER_ID,
      choroplethField: "lst_mean_C",
      legendLabel: "LST",
      barChartLabelProject: "Mean LST (°C)",
      barChartLabelDemo: "Peak LST (°C)",
    };
  }

  function isEquityDashboard(modelId) {
    return modelPresentation(modelId).dashboard === "equity";
  }

  function keyQueriesForState(modelId) {
    const { state, adapter } = gf;
    return (
      adapter?.keyQueries(modelId, {
        appMode: state.appMode,
        modelId,
      }) || []
    );
  }

  function renderKeyQueries(modelId) {
    const { keyQueriesEl } = gf.dom;
    if (!keyQueriesEl) return;
    const queries = keyQueriesForState(modelId);
    keyQueriesEl.innerHTML = "";
    queries.forEach((item) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `gf-action-btn${item.style ? ` ${item.style}` : ""}`;
      btn.dataset.gfPrompt = item.prompt;
      btn.textContent = item.label;
      keyQueriesEl.appendChild(btn);
    });
  }

  function projectPrimaryMetric(city) {
    if (!city) return null;
    return gf.adapter?.cityPrimaryValue(city, activeProjectModelId(city)) ?? null;
  }

  function applyDashboardShell(modelId) {
    const { adapter, state, dom } = gf;
    const pres = modelPresentation(modelId);
    const spec = adapter?.getModelSpec(modelId);
    const equity = pres.dashboard === "equity";
    const gfApp = document.querySelector(".gf-app");
    gfApp?.classList.toggle("gf-dashboard-equity", equity);
    gfApp?.classList.toggle("gf-dashboard-raster", !equity);

    if (dom.layerAnalysisLabelEl) {
      dom.layerAnalysisLabelEl.textContent =
        pres.heatmapLayerLabel || `${pres.legendLabel || "Analysis"} heatmap`;
    }

    if (state.appMode === "project") {
      if (dom.topbarTitleEl) {
        dom.topbarTitleEl.textContent =
          state.projectData?.name || pres.dashboardTitle || `${spec?.label || "Analysis"} Dashboard`;
      }
      if (dom.topbarSubtitleEl) {
        dom.topbarSubtitleEl.textContent =
          pres.dashboardSubtitle || `${spec?.label || "Analysis"} + Population + Census`;
      }
    }

    if (dom.queryInputEl && pres.queryPlaceholder) {
      dom.queryInputEl.placeholder = pres.queryPlaceholder;
    }
    if (dom.queryInputLabelEl && pres.queryAriaLabel) {
      dom.queryInputLabelEl.textContent = pres.queryAriaLabel;
    }

    document.querySelectorAll(".gf-action-equity").forEach((btn) => {
      btn.hidden = state.appMode === "project" && !equity;
    });
    document.getElementById("gfLayerAnalysis")?.classList.toggle("hidden", state.appMode === "project" && !equity);
    renderKeyQueries(modelId);
    gf.updateLstScaleUI?.();
  }

  function getCities() {
    const { state } = gf;
    return state.appMode === "project" ? state.projectCityList : state.demoCities;
  }

  function cityRunWarning(city) {
    return gf.adapter?.cityRunWarning(city) || null;
  }

  function updateMapWarning(city) {
    const { state, dom } = gf;
    if (!dom.mapWarningEl) return;
    const warning = state.appMode === "project" ? cityRunWarning(city) : null;
    if (warning) {
      dom.mapWarningEl.hidden = false;
      dom.mapWarningEl.textContent = warning;
    } else {
      dom.mapWarningEl.hidden = true;
      dom.mapWarningEl.textContent = "";
    }
  }

  function cityLstDisplay(city) {
    const { adapter, state } = gf;
    if (state.appMode === "project" && cityRunWarning(city)) return "⚠";
    if (state.appMode === "project") {
      const v = projectPrimaryMetric(city);
      return adapter?.formatPrimaryValueShort(v, activeProjectModelId(city)) ?? "—";
    }
    return city?.temp != null ? `${city.temp}°` : "—";
  }

  function barChartMax() {
    const { state } = gf;
    if (state.appMode === "project") {
      const vals = state.projectCityList
        .map((c) => projectPrimaryMetric(c))
        .filter((v) => v != null);
      return vals.length ? Math.max(...vals) : 1;
    }
    return state.demoMaxTemp;
  }

  async function fillDemoTempsFromPortfolio(cities) {
    if (!cities.some((c) => c.temp == null)) return cities;
    try {
      const res = await fetch("/api/city-layers/demo-portfolio?warm=false");
      if (!res.ok) return cities;
      const port = await res.json();
      const byName = Object.fromEntries((port.demo_lst || []).map((d) => [d.name, d]));
      return cities.map((c) => {
        const demo = byName[c.name];
        if (!demo) return c;
        return {
          ...c,
          temp: c.temp ?? demo.peak_lst_C,
          month: c.month ?? demo.month,
          color: c.color ?? demo.color,
        };
      });
    } catch {
      return cities;
    }
  }

  async function ensureDemoCities() {
    const { state } = gf;
    if (state.demoCities.length) return state.demoCities;
    const response = await fetch("/api/projects/presets");
    if (!response.ok) throw new Error("Could not load demo cities.");
    const payload = await response.json();
    let rows = (payload.cities || []).map((c) => ({
      name: c.name,
      temp: c.peak_lst_C ?? c.temp ?? null,
      month: c.month,
      color: c.color,
    }));
    if (rows.some((c) => c.temp == null) && Array.isArray(payload.demo_lst)) {
      const byName = Object.fromEntries(payload.demo_lst.map((d) => [d.name, d]));
      rows = rows.map((c) => {
        const demo = byName[c.name];
        if (!demo) return c;
        return {
          ...c,
          temp: c.temp ?? demo.peak_lst_C,
          month: c.month ?? demo.month,
          color: c.color ?? demo.color,
        };
      });
    }
    rows = await fillDemoTempsFromPortfolio(rows);
    state.demoCities = rows;
    if (!state.demoCities.length) throw new Error("No demo cities configured.");
    const temps = state.demoCities.map((c) => c.temp).filter((v) => v != null);
    state.demoMaxTemp = temps.length ? Math.max(...temps) : 1;
    state.demoHottest = temps.length
      ? state.demoCities.reduce((a, b) => ((a.temp ?? -Infinity) >= (b.temp ?? -Infinity) ? a : b))
      : null;
    return state.demoCities;
  }

  function updateModeChrome() {
    const { state } = gf;
    const cities = getCities();
    const { demoBadgeEl, projectBadgeEl, cityCountBadgeEl } = gf.dom;
    if (demoBadgeEl) demoBadgeEl.hidden = state.appMode !== "demo";
    if (projectBadgeEl) projectBadgeEl.hidden = state.appMode !== "project";
    if (cityCountBadgeEl) {
      cityCountBadgeEl.textContent =
        state.appMode === "project"
          ? `${cities.length} cit${cities.length === 1 ? "y" : "ies"}`
          : "11 cities";
    }
    const cityLabel = document.getElementById("gfCityListLabel");
    if (cityLabel) {
      cityLabel.textContent = state.appMode === "project" ? "Your cities" : "11 cities";
    }
    renderKeyQueries(state.appMode === "project" ? state.projectModelId : "lst");
  }

  function resolveAppMode() {
    const { state } = gf;
    const mode = localStorage.getItem("gf_mode") || "demo";
    if (mode === "project" && localStorage.getItem("gf_project_id")) {
      state.appMode = "project";
      state.projectId = localStorage.getItem("gf_project_id");
      return;
    }
    state.appMode = "demo";
    state.projectId = null;
  }

  function syncProjectCityList() {
    const { state } = gf;
    const { adapter } = gf;
    if (!state.projectData?.cities) {
      state.projectCityList = [];
      return;
    }
    state.projectCityList = Object.entries(state.projectData.cities).map(([key, entry]) => ({
      key,
      name: entry.name || entry.address,
      color: entry.color || "#3d7ea6",
      month: entry.month ?? null,
      year: entry.year ?? null,
      model_id: entry.model_id || state.projectData.model_id || state.projectModelId,
      temp: projectPrimaryMetric({
        ...entry,
        model_id: entry.model_id || state.projectData.model_id || state.projectModelId,
      }),
      run_stats: adapter?.cityRunStats(entry) || {},
      status: entry.status,
      address: entry.address,
      summary: entry.summary,
      vector_layer: entry.vector_layer,
      map_layers: entry.map_layers,
    }));
  }

  async function loadProject() {
    const { state } = gf;
    if (!state.projectId) return;
    const response = await fetch(`/api/projects/${state.projectId}`);
    if (!response.ok) throw new Error("Could not load project.");
    state.projectData = await response.json();
    state.projectModelId = state.projectData.model_id || "lst";
    if (state.projectId !== state.chatProjectId) {
      gf.resetChat?.(state.projectId);
    }
    state.projectLstRangeCache = null;
    state.projectGeojsonCache = {};
    await ensureAdapterModels();
    syncProjectCityList();
    applyDashboardShell(state.projectModelId);
    updateModeChrome();
  }

  async function loadDemoPortfolio(warm = true) {
    const { state } = gf;
    if (state.demoPortfolioLoading) return state.demoPortfolioLoading;
    state.demoPortfolioLoading = (async () => {
      try {
        const response = await fetch(`/api/city-layers/demo-portfolio?warm=${warm ? "true" : "false"}`);
        if (!response.ok) throw new Error("Could not load demo portfolio.");
        const payload = await response.json();
        state.demoOverview = payload.demo_overview || null;
        state.demoPortfolioCache = {};
        Object.entries(payload.cities || {}).forEach(([address, layers]) => {
          if (layers) state.demoPortfolioCache[address] = layers;
        });
        return state.demoPortfolioCache;
      } finally {
        state.demoPortfolioLoading = null;
      }
    })();
    return state.demoPortfolioLoading;
  }

  function refreshDemoCityUI() {
    gf.buildCityList?.();
    gf.buildBarChart?.();
    gf.buildCityGrid?.();
  }

  function startDemoPortfolioWarm() {
    const { mapLoadingEl } = gf.dom;
    if (mapLoadingEl) {
      mapLoadingEl.hidden = false;
      mapLoadingEl.textContent =
        "Caching demo city data in the background (maps work while this runs)…";
    }
    loadDemoPortfolio(true)
      .catch(() => {})
      .finally(() => {
        if (mapLoadingEl) mapLoadingEl.hidden = true;
        refreshDemoCityUI();
      });
  }

  function buildDemoCitiesForChat() {
    const { state } = gf;
    return state.demoCities.map((city) => {
      const cached = state.demoPortfolioCache[city.name];
      return {
        name: city.name,
        peak_lst_C: city.temp,
        month: city.month,
        summary: cached?.summary || null,
      };
    });
  }

  Object.assign(gf, {
    ensureAdapterModels,
    activeProjectModelId,
    modelPresentation,
    isEquityDashboard,
    keyQueriesForState,
    renderKeyQueries,
    projectPrimaryMetric,
    applyDashboardShell,
    getCities,
    cityRunWarning,
    updateMapWarning,
    cityLstDisplay,
    barChartMax,
    fillDemoTempsFromPortfolio,
    ensureDemoCities,
    updateModeChrome,
    resolveAppMode,
    syncProjectCityList,
    loadProject,
    loadDemoPortfolio,
    refreshDemoCityUI,
    startDemoPortfolioWarm,
    buildDemoCitiesForChat,
  });
})();
