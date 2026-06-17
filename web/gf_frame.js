/**
 * Urban Heat & Equity GUI Frame — MapLibre vector maps from cached GeoPackages + tract chat queries.
 */
(function () {
  const adapter = window.DashboardAdapter;
  let demoCities = [];
  let demoMaxTemp = 1;
  let demoHottest = null;

  const LAYER_ORDER = ["density", "income", "ethnicity", "tracts", "worldpop", "lst"];

  const LAYER_FIELDS = {
    density: "population_density_per_km2",
    income: "median_income_usd",
    ethnicity: "hispanic_pct",
    tracts: null,
    lst: "lst_mean_C",
  };

  const params = new URLSearchParams(window.location.search);
  let appMode = "demo";
  let projectId = null;
  let projectData = null;
  let projectModelId = "lst";
  let adapterModelsPromise = null;
  let projectCityList = [];
  let demoPortfolioCache = {};
  let demoOverview = null;
  let demoPortfolioLoading = null;

  let activeCityIndex = 0;
  let cityLayersData = null;
  let tractGeojsonCache = { token: null, data: null };

  let chatMessages = [
    {
      role: "assistant",
      text: "Welcome! Select a city, hover tracts for details, or click a tract to zoom in.",
    },
  ];

  const cityListEl = document.getElementById("gfCityList");
  const barChartEl = document.getElementById("gfBarChart");
  const cityGridEl = document.getElementById("gfCityGrid");
  const mapOverlayEl = document.getElementById("gfMapOverlay");
  const mapLoadingEl = document.getElementById("gfMapLoading");
  const mapViewportEl = document.getElementById("gfMapViewport");
  const mapContainerEl = document.getElementById("gfMapLibre");
  const mapEmptyEl = document.getElementById("gfMapEmpty");
  const chatPanelEl = document.getElementById("gfPanelChat");
  const queryInputEl = document.getElementById("gfQueryInput");
  const sendBtnEl = document.getElementById("gfSendBtn");
  const legendTitleEl = document.getElementById("gfLegendTitle");
  const demoBadgeEl = document.getElementById("gfDemoBadge");
  const projectBadgeEl = document.getElementById("gfProjectBadge");
  const cityCountBadgeEl = document.getElementById("gfCityCountBadge");
  const layerAnalysisLabelEl = document.getElementById("gfLayerAnalysisLabel");
  const topbarTitleEl = document.getElementById("gfTopbarTitle");
  const topbarSubtitleEl = document.getElementById("gfTopbarSubtitle");

  function ensureAdapterModels() {
    if (!adapter) return Promise.resolve();
    if (!adapterModelsPromise) adapterModelsPromise = adapter.fetchModels().catch(() => null);
    return adapterModelsPromise;
  }

  function activeProjectModelId(city) {
    return adapter?.resolveProjectModelId(projectData, city) || projectModelId || "lst";
  }

  function modelPresentation(modelId) {
    return adapter?.getPresentation(modelId) || {
      dashboard: "equity",
      analysisLayerId: "lst",
      choroplethField: "lst_mean_C",
      legendLabel: "LST",
      barChartLabelProject: "Mean LST (°C)",
      barChartLabelDemo: "Peak LST (°C)",
    };
  }

  function isEquityDashboard(modelId) {
    return modelPresentation(modelId).dashboard === "equity";
  }

  function projectPrimaryMetric(city) {
    if (!city) return null;
    return adapter?.cityPrimaryValue(city, activeProjectModelId(city)) ?? null;
  }

  function applyDashboardShell(modelId) {
    const pres = modelPresentation(modelId);
    const spec = adapter?.getModelSpec(modelId);
    const equity = pres.dashboard === "equity";
    const gfApp = document.querySelector(".gf-app");
    gfApp?.classList.toggle("gf-dashboard-equity", equity);
    gfApp?.classList.toggle("gf-dashboard-raster", !equity);

    if (layerAnalysisLabelEl) {
      layerAnalysisLabelEl.textContent = `${pres.legendLabel || "Analysis"} heatmap`;
    }

    if (appMode === "project") {
      if (topbarTitleEl) {
        topbarTitleEl.textContent = equity
          ? "Urban Heat & Equity GUI Frame"
          : `${spec?.label || "Analysis"} Dashboard`;
      }
      if (topbarSubtitleEl) {
        topbarSubtitleEl.textContent = equity
          ? `${spec?.label || "Analysis"} + Population + Census`
          : "Model output view";
      }
    }

    document.querySelectorAll(".gf-action-equity").forEach((btn) => {
      btn.hidden = appMode === "project" && !equity;
    });
    document.getElementById("gfLayerAnalysis")?.classList.toggle("hidden", appMode === "project" && !equity);
  }

  function getCities() {
    return appMode === "project" ? projectCityList : demoCities;
  }

  function cityLstDisplay(city) {
    if (appMode === "project") {
      const v = projectPrimaryMetric(city);
      return adapter?.formatPrimaryValueShort(v, activeProjectModelId(city)) ?? "—";
    }
    return city?.temp != null ? `${city.temp}°` : "—";
  }

  function barChartMax() {
    if (appMode === "project") {
      const vals = projectCityList
        .map((c) => projectPrimaryMetric(c))
        .filter((v) => v != null);
      return vals.length ? Math.max(...vals) : 1;
    }
    return demoMaxTemp;
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
    if (demoCities.length) return demoCities;
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
    demoCities = rows;
    if (!demoCities.length) throw new Error("No demo cities configured.");
    const temps = demoCities.map((c) => c.temp).filter((v) => v != null);
    demoMaxTemp = temps.length ? Math.max(...temps) : 1;
    demoHottest = temps.length
      ? demoCities.reduce((a, b) => ((a.temp ?? -Infinity) >= (b.temp ?? -Infinity) ? a : b))
      : null;
    return demoCities;
  }

  function updateModeChrome() {
    const cities = getCities();
    if (demoBadgeEl) demoBadgeEl.hidden = appMode !== "demo";
    if (projectBadgeEl) projectBadgeEl.hidden = appMode !== "project";
    if (cityCountBadgeEl) {
      cityCountBadgeEl.textContent =
        appMode === "project"
          ? `${cities.length} cit${cities.length === 1 ? "y" : "ies"}`
          : "11 cities";
    }
    const cityLabel = document.getElementById("gfCityListLabel");
    if (cityLabel) {
      cityLabel.textContent = appMode === "project" ? "Your cities" : "11 cities";
    }
  }

  function resolveAppMode() {
    const mode = localStorage.getItem("gf_mode") || "demo";
    if (mode === "project" && localStorage.getItem("gf_project_id")) {
      appMode = "project";
      projectId = localStorage.getItem("gf_project_id");
      return;
    }
    appMode = "demo";
    projectId = null;
  }

  function syncProjectCityList() {
    if (!projectData?.cities) {
      projectCityList = [];
      return;
    }
    projectCityList = Object.entries(projectData.cities).map(([key, entry]) => ({
      key,
      name: entry.name || entry.address,
      color: entry.color || "#3d7ea6",
      model_id: entry.model_id || projectData.model_id || projectModelId,
      temp: projectPrimaryMetric({
        ...entry,
        model_id: entry.model_id || projectData.model_id || projectModelId,
      }),
      run_stats: adapter?.cityRunStats(entry) || {},
      lst_stats: entry.lst_stats || entry.run_stats || {},
      status: entry.status,
      address: entry.address,
      summary: entry.summary,
      vector_layer: entry.vector_layer,
      worldpop: entry.worldpop,
      map_layers: entry.map_layers,
    }));
  }

  async function loadProject() {
    if (!projectId) return;
    const response = await fetch(`/api/projects/${projectId}`);
    if (!response.ok) throw new Error("Could not load project.");
    projectData = await response.json();
    projectModelId = projectData.model_id || "lst";
    await ensureAdapterModels();
    syncProjectCityList();
    applyDashboardShell(projectModelId);
    updateModeChrome();
  }

  async function loadDemoPortfolio(warm = true) {
    if (demoPortfolioLoading) return demoPortfolioLoading;
    demoPortfolioLoading = (async () => {
      try {
        const response = await fetch(`/api/city-layers/demo-portfolio?warm=${warm ? "true" : "false"}`);
        if (!response.ok) throw new Error("Could not load demo portfolio.");
        const payload = await response.json();
        demoOverview = payload.demo_overview || null;
        demoPortfolioCache = {};
        Object.entries(payload.cities || {}).forEach(([address, layers]) => {
          if (layers) demoPortfolioCache[address] = layers;
        });
        return demoPortfolioCache;
      } finally {
        demoPortfolioLoading = null;
      }
    })();
    return demoPortfolioLoading;
  }

  function refreshDemoCityUI() {
    buildCityList();
    buildBarChart();
    buildCityGrid();
  }

  function startDemoPortfolioWarm() {
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
    return demoCities.map((city) => {
      const cached = demoPortfolioCache[city.name];
      return {
        name: city.name,
        peak_lst_C: city.temp,
        month: city.month,
        summary: cached?.summary || null,
      };
    });
  }

  let map = null;
  let mapReady = false;
  let popup = null;
  let workerConfigured = false;
  let hoveredTractId = null;
  let tractInteractionsBound = false;

  function configureMapLibreWorker() {
    if (workerConfigured || typeof maplibregl === "undefined") return;
    maplibregl.setWorkerUrl("/vendor/maplibre-gl/maplibre-gl-csp-worker.js");
    workerConfigured = true;
  }

  function cityShort(name) {
    return name.split(",")[0];
  }

  function formatNumber(value) {
    if (value === null || value === undefined) return "—";
    return Number(value).toLocaleString();
  }

  function layerEnabled(layerId) {
    const row = document.querySelector(`.gf-layer-toggle[data-gf-layer="${layerId}"] .gf-toggle`);
    return row ? row.classList.contains("on") : false;
  }

  function activeMapLayerId() {
    for (const layerId of LAYER_ORDER) {
      if (layerEnabled(layerId)) return layerId;
    }
    return "density";
  }

  function activeLayerLabel() {
    const layerId = activeMapLayerId();
    const city = getCities()[activeCityIndex];
    const modelId = activeProjectModelId(city);
    const pres = modelPresentation(modelId);
    if (layerId === "worldpop") return "WorldPop gridded population";
    if (layerId === pres.analysisLayerId || layerId === "lst") {
      if (appMode === "project" && city?.status === "ready") return pres.analysisLayerLabel;
      return `${pres.legendLabel} (demo — density stand-in)`;
    }
    return cityLayersData?.map_layers?.[layerId]?.label || "Map layer";
  }

  function activeChoroplethField() {
    const layerId = activeMapLayerId();
    const city = getCities()[activeCityIndex];
    const modelId = activeProjectModelId(city);
    const pres = modelPresentation(modelId);
    if (layerId === "worldpop") return null;
    if (layerId === pres.analysisLayerId || layerId === "lst") {
      if (appMode === "project" && city?.status === "ready") {
        return (
          adapter?.choroplethField(modelId, layerId, appMode, city) ||
          pres.choroplethField ||
          city?.vector_layer?.fields?.find((f) => f === pres.choroplethField) ||
          pres.choroplethField
        );
      }
      return LAYER_FIELDS.density;
    }
    return LAYER_FIELDS[layerId] ?? cityLayersData?.map_layers?.[layerId]?.field ?? null;
  }

  function updateLegend() {
    if (!legendTitleEl) return;
    const city = getCities()[activeCityIndex];
    const pres = modelPresentation(activeProjectModelId(city));
    const labels = {
      density: "Density",
      income: "Income",
      ethnicity: "Hispanic %",
      tracts: "Tracts",
      worldpop: "WorldPop",
      lst: appMode === "project" ? pres.legendLabel : `${pres.legendLabel} demo`,
    };
    const layerId = activeMapLayerId();
    legendTitleEl.textContent =
      labels[layerId] || (layerId === pres.analysisLayerId ? pres.legendLabel : "Map");
  }

  function choroplethFillPaint(field) {
    if (!field) {
      return { "fill-color": "#5a9ab8", "fill-opacity": 0.78 };
    }

    const value = ["coalesce", ["to-number", ["get", field]], 0];

    if (field === "median_income_usd") {
      return {
        "fill-color": [
          "interpolate",
          ["linear"],
          value,
          20000,
          "#edf8e9",
          45000,
          "#74c476",
          80000,
          "#238b45",
          120000,
          "#006d2c",
        ],
        "fill-opacity": 0.82,
      };
    }
    if (field === "hispanic_pct") {
      return {
        "fill-color": [
          "interpolate",
          ["linear"],
          value,
          5,
          "#fee5d9",
          25,
          "#fcae91",
          50,
          "#fb6a4a",
          80,
          "#a50f15",
        ],
        "fill-opacity": 0.82,
      };
    }
    if (field === "lst_mean_C") {
      return {
        "fill-color": [
          "interpolate",
          ["linear"],
          value,
          25,
          "#ffffb2",
          32,
          "#fd8d3c",
          38,
          "#e31a1c",
          45,
          "#800026",
        ],
        "fill-opacity": 0.82,
      };
    }
    return {
      "fill-color": [
        "interpolate",
        ["linear"],
        value,
        500,
        "#ffffcc",
        2500,
        "#fd8d3c",
        8000,
        "#e31a1c",
        15000,
        "#800026",
      ],
      "fill-opacity": 0.82,
    };
  }

  function linePaint() {
    return { "line-color": "#ffffff", "line-width": 0.6 };
  }

  function refreshMapSize() {
    if (!map) return;
    map.resize();
  }

  function afterLayout(callback) {
    requestAnimationFrame(() => {
      requestAnimationFrame(callback);
    });
  }

  function tractPopupHtml(props) {
    const name = props.acs_name || props.NAME || props.GEOID || "Census tract";
    const field = activeChoroplethField();
    const layerLabel = activeLayerLabel();
    const city = getCities()[activeCityIndex];
    const pres = modelPresentation(activeProjectModelId(city));

    let metricHtml = "";
    if (field === "median_income_usd" && props.median_income_usd != null) {
      metricHtml = `<div class="gf-tract-popup-metric">$${formatNumber(props.median_income_usd)}</div><div class="gf-tract-popup-metric-label">${layerLabel}</div>`;
    } else if (field === "hispanic_pct" && props.hispanic_pct != null) {
      metricHtml = `<div class="gf-tract-popup-metric">${props.hispanic_pct}%</div><div class="gf-tract-popup-metric-label">${layerLabel}</div>`;
    } else if (field === "population_density_per_km2" && props.population_density_per_km2 != null) {
      metricHtml = `<div class="gf-tract-popup-metric">${formatNumber(props.population_density_per_km2)}/km²</div><div class="gf-tract-popup-metric-label">${layerLabel}</div>`;
    } else if (field && props[field] != null) {
      const unit = field === "lst_mean_C" || pres.metricUnit === "°C" ? "°C" : "";
      metricHtml = `<div class="gf-tract-popup-metric">${props[field]}${unit}</div><div class="gf-tract-popup-metric-label">${layerLabel}</div>`;
    }

    const rows = [
      ["Population", formatNumber(props.population)],
      ["Median income", props.median_income_usd != null ? `$${formatNumber(props.median_income_usd)}` : "—"],
      ["Hispanic %", props.hispanic_pct != null ? `${props.hispanic_pct}%` : "—"],
      ["Black %", props.black_pct != null ? `${props.black_pct}%` : "—"],
      ["Density", props.population_density_per_km2 != null ? `${formatNumber(props.population_density_per_km2)}/km²` : "—"],
    ];
    if (pres.choroplethField && props[pres.choroplethField] != null) {
      rows.push([
        pres.tractDetailLabel || pres.legendLabel,
        pres.metricUnit === "°C"
          ? `${props[pres.choroplethField]}°C`
          : String(props[pres.choroplethField]),
      ]);
    } else if (props.lst_mean_C != null) {
      rows.push(["LST mean", `${props.lst_mean_C}°C`]);
    }
    const dl = rows.map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`).join("");
    return `
      <div class="gf-tract-popup-card">
        <div class="gf-tract-popup-title">${name}</div>
        ${metricHtml}
        <dl class="gf-tract-popup">${dl}</dl>
        <div class="gf-tract-popup-hint muted">Click tract to zoom</div>
      </div>
    `;
  }

  function clearTractHover() {
    if (!map || hoveredTractId == null) return;
    map.setFeatureState({ source: "tracts", id: hoveredTractId }, { hover: false });
    hoveredTractId = null;
  }

  function boundsFromFeature(feature) {
    const bounds = new maplibregl.LngLatBounds();
    const walk = (coords) => {
      if (typeof coords[0] === "number") {
        bounds.extend(coords);
        return;
      }
      coords.forEach(walk);
    };
    walk(feature.geometry.coordinates);
    return bounds;
  }

  function bindTractInteractions() {
    if (!map || tractInteractionsBound) return;
    tractInteractionsBound = true;

    map.on("mousemove", "tracts-fill", (event) => {
      const feature = event.features && event.features[0];
      if (!feature) return;

      map.getCanvas().style.cursor = "pointer";

      if (hoveredTractId !== null && hoveredTractId !== feature.id) {
        map.setFeatureState({ source: "tracts", id: hoveredTractId }, { hover: false });
      }
      hoveredTractId = feature.id;
      map.setFeatureState({ source: "tracts", id: hoveredTractId }, { hover: true });

      popup.setLngLat(event.lngLat).setHTML(tractPopupHtml(feature.properties)).addTo(map);
    });

    map.on("mouseleave", "tracts-fill", () => {
      clearTractHover();
      popup.remove();
      map.getCanvas().style.cursor = "";
    });

    map.on("click", "tracts-fill", (event) => {
      const feature = event.features && event.features[0];
      if (!feature) return;
      const bounds = boundsFromFeature(feature);
      map.fitBounds(bounds, { padding: 72, duration: 700, maxZoom: 14 });
    });
  }

  function ensureMap() {
    if (!mapContainerEl || typeof maplibregl === "undefined") return null;
    configureMapLibreWorker();
    if (map) return map;

    map = new maplibregl.Map({
      container: mapContainerEl,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: "bg", type: "background", paint: { "background-color": "#e8edf2" } }],
      },
      center: [-98.5, 39.5],
      zoom: 3,
      attributionControl: true,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    popup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      maxWidth: "300px",
      className: "gf-tract-hover-popup",
      offset: 14,
    });

    bindTractInteractions();

    map.on("load", () => {
      mapReady = true;
      refreshMapSize();
      if (cityLayersData) renderActiveMapLayer();
    });

    return map;
  }

  function fitMapBounds(bounds) {
    if (!map || !bounds || bounds.length !== 4) return;
    const [west, south, east, north] = bounds;
    map.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      { padding: 36, duration: 600 }
    );
  }

  function removeRasterOverlay() {
    if (!map) return;
    if (map.getLayer("raster-overlay")) map.removeLayer("raster-overlay");
    if (map.getSource("raster-overlay")) map.removeSource("raster-overlay");
  }

  function setRasterOverlay(url, bounds) {
    if (!map || !mapReady || !url || !bounds || bounds.length !== 4) return;
    const [west, south, east, north] = bounds;
    const absoluteUrl = url.startsWith("http") ? url : `${window.location.origin}${url}`;
    removeRasterOverlay();
    map.addSource("raster-overlay", {
      type: "image",
      url: `${absoluteUrl}${absoluteUrl.includes("?") ? "&" : "?"}t=${Date.now()}`,
      coordinates: [
        [west, north],
        [east, north],
        [east, south],
        [west, south],
      ],
    });
    map.addLayer({
      id: "raster-overlay",
      type: "raster",
      source: "raster-overlay",
      paint: { "raster-opacity": 0.88 },
    });
    if (map.getLayer("tracts-fill")) {
      map.setPaintProperty("tracts-fill", "fill-opacity", 0.15);
      map.setPaintProperty("tracts-line", "line-opacity", 0.35);
    }
  }

  function showVectorLayers() {
    if (!map || !map.getLayer("tracts-fill")) return;
    map.setLayoutProperty("tracts-fill", "visibility", "visible");
    map.setLayoutProperty("tracts-line", "visibility", "visible");
    map.setPaintProperty("tracts-fill", "fill-opacity", 0.78);
    map.setPaintProperty("tracts-line", "line-opacity", 1);
    removeRasterOverlay();
  }

  async function loadTractGeojson() {
    const vector = cityLayersData?.vector_layer;
    if (!vector?.geojson_url) return null;

    if (tractGeojsonCache.token === vector.token && tractGeojsonCache.data) {
      return tractGeojsonCache.data;
    }

    const response = await fetch(vector.geojson_url);
    if (!response.ok) throw new Error("Could not load tract GeoJSON.");
    const data = await response.json();
    tractGeojsonCache = { token: vector.token, data };
    return data;
  }

  function fillOpacityPaint() {
    return [
      "case",
      ["boolean", ["feature-state", "hover"], false],
      0.95,
      0.82,
    ];
  }

  function upsertTractLayers(geojson, field) {
    if (!map || !mapReady) return;

    clearTractHover();
    popup.remove();

    const fillPaint = {
      ...choroplethFillPaint(field),
      "fill-opacity": fillOpacityPaint(),
    };
    const outline = linePaint();
    const hoverOutline = {
      "line-color": "#1a3348",
      "line-width": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        2.4,
        0.6,
      ],
    };

    if (map.getSource("tracts")) {
      map.getSource("tracts").setData(geojson);
    } else {
      map.addSource("tracts", { type: "geojson", data: geojson, promoteId: "GEOID" });
      map.addLayer({
        id: "tracts-fill",
        type: "fill",
        source: "tracts",
        paint: fillPaint,
      });
      map.addLayer({
        id: "tracts-line",
        type: "line",
        source: "tracts",
        paint: { ...outline, ...hoverOutline },
      });
    }

    Object.keys(fillPaint).forEach((key) => {
      map.setPaintProperty("tracts-fill", key, fillPaint[key]);
    });
    Object.keys(outline).forEach((key) => {
      map.setPaintProperty("tracts-line", key, outline[key]);
    });
    map.setPaintProperty("tracts-line", "line-width", hoverOutline["line-width"]);
  }

  async function renderActiveMapLayer() {
    if (!cityLayersData) return;

    const layerId = activeMapLayerId();
    const city = getCities()[activeCityIndex];
    const modelId = activeProjectModelId(city);
    const summary = cityLayersData.summary || {};

    if (appMode === "project" && !isEquityDashboard(modelId)) {
      if (mapOverlayEl) {
        mapOverlayEl.innerHTML = `
          <div class="gf-map-overlay-title">${city.name} · ${modelPresentation(modelId).legendLabel}</div>
          <div class="gf-map-overlay-sub">Raster dashboard shell — map view for this model is not implemented yet.</div>
        `;
      }
      if (mapEmptyEl) {
        mapEmptyEl.textContent =
          "This model uses a raster dashboard type. Full map view will be added when the model is integrated.";
        mapEmptyEl.classList.remove("hidden");
      }
      mapContainerEl?.classList.add("hidden");
      return;
    }

    if (mapEmptyEl) mapEmptyEl.classList.add("hidden");

    if (mapOverlayEl) {
      mapOverlayEl.innerHTML = `
        <div class="gf-map-overlay-title">${city.name} · ${activeLayerLabel()}</div>
        <div class="gf-map-overlay-sub">${summary.county || ""} · ${formatNumber(summary.tract_count)} tracts · hover for details, click to zoom</div>
      `;
    }
    updateLegend();

    if (!mapContainerEl || typeof maplibregl === "undefined") {
      if (mapEmptyEl) {
        mapEmptyEl.textContent = "MapLibre failed to load. Check your network connection.";
        mapEmptyEl.classList.remove("hidden");
      }
      return;
    }

    ensureMap();
    mapContainerEl.classList.remove("hidden");
    if (mapEmptyEl) mapEmptyEl.classList.add("hidden");

    const render = async () => {
      try {
        const geojson = await loadTractGeojson();
        if (!geojson) throw new Error("No vector layer for this city.");

        const field = activeChoroplethField();
        upsertTractLayers(geojson, field);
        refreshMapSize();
        fitMapBounds(cityLayersData.vector_layer?.bounds_wgs84);

        if (layerId === "worldpop" && cityLayersData.worldpop?.preview_url) {
          setRasterOverlay(
            cityLayersData.worldpop.preview_url,
            cityLayersData.worldpop.bounds_wgs84 || cityLayersData.vector_layer.bounds_wgs84
          );
        } else {
          showVectorLayers();
        }
      } catch (error) {
        if (mapEmptyEl) {
          mapEmptyEl.textContent = error.message || "Could not render map.";
          mapEmptyEl.classList.remove("hidden");
        }
      }
    };

    if (mapReady) {
      await render();
    } else {
      map.once("load", () => render());
    }
  }

  function chatContext() {
    const city = getCities()[activeCityIndex];
    const summary = cityLayersData?.summary || {};
    const demoCities = appMode === "demo" ? buildDemoCitiesForChat() : null;
    const overview =
      appMode === "demo"
        ? demoOverview || {
            hottest_city: demoHottest?.name,
            peak_lst_C: demoHottest?.temp,
            hottest_month: demoHottest?.month,
            city_count: demoCities.length,
          }
        : null;

    const ctx = {
      model: "equity",
      analysis_model: appMode === "project" ? activeProjectModelId(city) : null,
      project_id: appMode === "project" ? projectId : null,
      demo_cities: demoCities,
      demo_overview: overview,
      tract_layer_token:
        appMode === "project" && city?.status === "ready" && city?.key
          ? `${projectId}:${city.key}`
          : cityLayersData?.vector_layer?.token || null,
      summary:
        appMode === "demo"
          ? `11-city urban heat and equity demo. Placeholder LST for all cities; live Census for the active city (${city?.name}). Use demo_cities and city_comparison for cross-city questions.`
          : cityLayersData
            ? `Census tract data for ${city.name} (${summary.county || ""}, ${summary.state || ""}).`
            : `Multi-city ${modelPresentation(activeProjectModelId(city)).chatAnalysisLabel || "analysis"} project.`,
      stats: {
        active_city: city?.name,
        ...summary,
      },
      logs: cityLayersData ? JSON.stringify(cityLayersData.sources || {}) : "",
      raster:
        appMode === "project" ? (adapter?.cityRunStats(city).geotiff || city?.lst_stats?.geotiff || "") : "",
    };
    if (appMode === "demo") {
      if (city?.temp != null) ctx.stats.demo_lst_C = city.temp;
      if (overview?.peak_lst_C != null) ctx.stats.peak_lst_C = overview.peak_lst_C;
      if (overview?.hottest_city) ctx.stats.hottest_city = overview.hottest_city;
    } else if (appMode === "project") {
      Object.assign(ctx.stats, adapter?.cityRunStats(city) || city?.lst_stats || {});
    }
    return ctx;
  }

  async function loadProjectCity(cityKey) {
    const entry = projectData?.cities?.[cityKey];
    if (!entry) return null;
    if (mapLoadingEl) {
      mapLoadingEl.hidden = false;
      mapLoadingEl.textContent = `Loading ${entry.name}…`;
    }
    cityLayersData = {
      address: entry.address,
      summary: entry.summary || {},
      vector_layer: entry.vector_layer,
      worldpop: entry.worldpop || {},
      map_layers: entry.map_layers || {},
      sources: { lst: "User upload + zonal join", census: "Census ACS" },
    };
    tractGeojsonCache = { token: null, data: null };
    if (mapLoadingEl) mapLoadingEl.hidden = true;
    updateStats();
    await renderActiveMapLayer();
    return cityLayersData;
  }

  function updateStats() {
    const summary = cityLayersData?.summary || {};
    const set = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    };
    set("gfStatCounty", summary.county || "—");
    set("gfStatTracts", formatNumber(summary.tract_count));
    set("gfStatPopulation", formatNumber(summary.total_population));
    set("gfStatIncome", summary.median_income_usd ? `$${formatNumber(summary.median_income_usd)}` : "—");
    set(
      "gfStatDensity",
      summary.avg_density_per_km2 != null ? `${formatNumber(summary.avg_density_per_km2)}/km²` : "—"
    );
  }

  async function fetchCityLayers(address) {
    if (appMode === "demo" && demoPortfolioCache[address]) {
      cityLayersData = demoPortfolioCache[address];
      tractGeojsonCache = { token: null, data: null };
      updateStats();
      await renderActiveMapLayer();
      return cityLayersData;
    }

    if (mapLoadingEl) {
      mapLoadingEl.hidden = false;
      mapLoadingEl.textContent = `Loading census & population data for ${address}… (first load may download tract boundaries)`;
    }

    try {
      const response = await fetch("/api/city-layers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof payload.detail === "string" ? payload.detail : "Failed to load city layers.");
      }
      cityLayersData = payload;
      tractGeojsonCache = { token: null, data: null };
      if (appMode === "demo") {
        demoPortfolioCache[address] = payload;
      }
      if (mapLoadingEl) mapLoadingEl.hidden = true;
      updateStats();
      await renderActiveMapLayer();
      return payload;
    } catch (error) {
      if (mapLoadingEl) {
        mapLoadingEl.hidden = false;
        mapLoadingEl.textContent = error.message || "Could not load city data.";
      }
      return null;
    }
  }

  async function selectCity(index) {
    activeCityIndex = index;
    const cities = getCities();
    const city = cities[index];
    if (!city) return;

    document.querySelectorAll(".gf-city-btn").forEach((btn, i) => {
      btn.classList.toggle("active", i === index);
    });
    document.querySelectorAll(".gf-mini-city").forEach((cell, i) => {
      cell.classList.toggle("active", i === index);
    });

    if (appMode === "project" && city.status === "ready" && city.key) {
      await loadProjectCity(city.key);
    } else {
      await fetchCityLayers(city.name || city.address);
    }
  }

  function buildCityList() {
    if (!cityListEl) return;
    cityListEl.innerHTML = "";
    const cities = getCities();
    if (appMode === "project" && cities.length === 0) {
      cityListEl.innerHTML =
        '<p class="muted gf-project-hint">No cities in this project. Use <strong>Back to Ask</strong> to upload Landsat bands.</p>';
      return;
    }
    cities.forEach((city, index) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "gf-city-btn" + (index === activeCityIndex ? " active" : "");
      const status =
        appMode === "project" && city.status
          ? `<span class="gf-city-status gf-city-status-${city.status}">${city.status}</span>`
          : "";
      btn.innerHTML = `
        <span class="gf-city-btn-left">
          <span class="gf-city-dot" style="background:${city.color}"></span>
          ${cityShort(city.name)}${status}
        </span>
        <span class="gf-temp-pill" style="background:${city.color}22;color:${city.color}">${cityLstDisplay(city)}</span>
      `;
      btn.addEventListener("click", () => selectCity(index));
      cityListEl.appendChild(btn);
    });
  }

  function buildBarChart() {
    if (!barChartEl) return;
    barChartEl.innerHTML = "";
    const cities = getCities();
    const maxVal = barChartMax();
    const modelId = appMode === "project" ? projectModelId : "lst";
    const pres = modelPresentation(modelId);
    const label = appMode === "project" ? pres.barChartLabelProject : pres.barChartLabelDemo;
    cities.forEach((city) => {
      const val = appMode === "project" ? projectPrimaryMetric(city) : city.temp;
      const pct = val != null ? Math.round((val / maxVal) * 100) : 0;
      const valLabel =
        val != null
          ? appMode === "project"
            ? adapter?.formatPrimaryValueShort(val, activeProjectModelId(city))
            : `${val}°`
          : "—";
      const row = document.createElement("div");
      row.className = "gf-chart-row";
      row.innerHTML = `
        <span>${cityShort(city.name)}</span>
        <div class="gf-bar-track"><div class="gf-bar-fill" style="width:${pct}%;background:${city.color}"></div></div>
        <span class="gf-bar-val">${valLabel}</span>
      `;
      barChartEl.appendChild(row);
    });
    const heading = document.querySelector("#gfPanelCharts .gf-panel-heading");
    if (heading) heading.textContent = label;
  }

  function buildCityGrid() {
    if (!cityGridEl) return;
    cityGridEl.innerHTML = "";
    getCities().forEach((city, index) => {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "gf-mini-city" + (index === activeCityIndex ? " active" : "");
      const temp = appMode === "project" ? projectPrimaryMetric(city) : city.temp;
      const unit = appMode === "project" ? modelPresentation(activeProjectModelId(city)).metricUnit : "°C";
      cell.innerHTML = `
        <div class="gf-mini-city-name">${cityShort(city.name)}</div>
        <div class="gf-mini-city-temp" style="color:${city.color}">${temp != null ? `${temp}${unit}` : "—"}</div>
        <div class="gf-mini-city-state muted">${city.name.split(", ")[1] || ""}</div>
      `;
      cell.addEventListener("click", () => selectCity(index));
      cityGridEl.appendChild(cell);
    });
  }

  function renderChat() {
    if (!chatPanelEl) return;
    chatPanelEl.innerHTML = "";
    chatMessages.forEach((msg) => {
      const bubble = document.createElement("div");
      bubble.className = `gf-msg gf-msg-${msg.role}`;
      bubble.textContent = msg.text;
      chatPanelEl.appendChild(bubble);
    });
    chatPanelEl.scrollTop = chatPanelEl.scrollHeight;
  }

  function switchPanelTab(tab) {
    ["chat", "charts", "layers"].forEach((name) => {
      const panel = document.getElementById(`gfPanel${name.charAt(0).toUpperCase() + name.slice(1)}`);
      const tabBtn = document.getElementById(`gfTab${name.charAt(0).toUpperCase() + name.slice(1)}`);
      if (panel) panel.hidden = name !== tab;
      if (tabBtn) tabBtn.classList.toggle("active", name === tab);
    });
  }

  function followupErrorText(response, payload) {
    if (response.status === 429) {
      return typeof payload.detail === "string"
        ? payload.detail
        : "Too many chat requests. Please wait before trying again.";
    }
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail) && payload.detail.length) {
      const first = payload.detail[0];
      if (first?.msg) {
        const field = Array.isArray(first.loc) ? first.loc.slice(-1)[0] : "";
        return field ? `${field}: ${first.msg}` : first.msg;
      }
    }
    return null;
  }

  async function askQuestion(question) {
    const q = (question || "").trim();
    if (!q) return;

    chatMessages.push({ role: "user", text: q });
    renderChat();
    switchPanelTab("chat");
    if (sendBtnEl) sendBtnEl.disabled = true;

    try {
      const response = await fetch("/api/followup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, context: chatContext() }),
      });
      const payload = await response.json().catch(() => ({}));
      if (response.ok) {
        chatMessages.push({
          role: "assistant",
          text: payload.answer || "No answer returned.",
        });
      } else {
        chatMessages.push({
          role: "assistant",
          text: followupErrorText(response, payload) || "Could not get an answer.",
        });
      }
    } catch {
      chatMessages.push({ role: "assistant", text: "Network error. Check that the server is running." });
    } finally {
      if (sendBtnEl) sendBtnEl.disabled = false;
      renderChat();
    }
  }

  function wireControls() {
    document.querySelectorAll("[data-gf-prompt]").forEach((btn) => {
      btn.addEventListener("click", () => askQuestion(btn.dataset.gfPrompt || ""));
    });

    document.querySelectorAll(".gf-panel-tab").forEach((tab) => {
      tab.addEventListener("click", () => switchPanelTab(tab.dataset.gfTab || "chat"));
    });

    document.querySelectorAll(".gf-layer-toggle").forEach((row) => {
      const toggle = row.querySelector(".gf-toggle");
      if (toggle) {
        toggle.addEventListener("click", () => {
          toggle.classList.toggle("on");
          renderActiveMapLayer();
        });
      }
    });

    if (sendBtnEl) {
      sendBtnEl.addEventListener("click", () => {
        askQuestion(queryInputEl?.value || "");
        if (queryInputEl) queryInputEl.value = "";
      });
    }

    if (queryInputEl) {
      queryInputEl.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          askQuestion(queryInputEl.value);
          queryInputEl.value = "";
        }
      });
    }

    document.getElementById("gfExportBtn")?.addEventListener("click", () => {
      askQuestion(
        "Generate a full PDF report for all 11 cities comparing LST, income, and ethnicity data"
      );
    });

    document.getElementById("gfZoomIn")?.addEventListener("click", () => map?.zoomIn({ duration: 200 }));
    document.getElementById("gfZoomOut")?.addEventListener("click", () => map?.zoomOut({ duration: 200 }));
    document.getElementById("gfZoomReset")?.addEventListener("click", () => {
      fitMapBounds(cityLayersData?.vector_layer?.bounds_wgs84);
    });
    document.getElementById("gfAllCitiesBtn")?.addEventListener("click", () => switchPanelTab("layers"));

    window.addEventListener("resize", () => {
      if (document.getElementById("page-gfframe")?.classList.contains("active")) {
        refreshMapSize();
      }
    });
  }

  let uiWired = false;
  let dataLoaded = false;

  function activate() {
    resolveAppMode();

    if (appMode === "project" && (!projectId || !window.AppShell?.hasReadyProject?.())) {
      window.AppShell?.showPage("ask");
      return;
    }

    updateModeChrome();
    dataLoaded = false;
    tractGeojsonCache = { token: null, data: null };
    cityLayersData = null;
    activeCityIndex = 0;

    renderChat();
    if (!uiWired) {
      wireControls();
      uiWired = true;
    }

    afterLayout(async () => {
      await ensureAdapterModels();

      if (appMode === "demo") {
        try {
          await ensureDemoCities();
        } catch {
          window.AppShell?.showPage("ask");
          return;
        }
      }

      refreshDemoCityUI();

      if (appMode === "project") {
        try {
          await loadProject();
        } catch {
          window.AppShell?.showPage("ask");
          return;
        }
        refreshDemoCityUI();
      } else {
        startDemoPortfolioWarm();
      }

      if (!dataLoaded) {
        dataLoaded = true;
        const cities = getCities();
        if (cities.length) await selectCity(activeCityIndex);
        return;
      }
      refreshMapSize();
      await renderActiveMapLayer();
    });
  }

  window.GfFrame = { init: activate, activate };
})();
