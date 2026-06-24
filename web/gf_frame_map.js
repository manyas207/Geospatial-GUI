/**
 * Urban Heat & Equity GUI Frame — MapLibre map rendering and layer controls.
 */
(function () {
  const gf = window.GfFrame;
  const { ANALYSIS_LAYER_ID, LAYER_ORDER, CHOROPLETH_LAYER_IDS, LAYER_FIELDS } = gf;

  const DEFAULT_LEGEND_COLORS = ["#3d7ea6", "#74add1", "#abd9e9", "#f3c89b", "#e07b32", "#c45a1a", "#9b2226"];

  function activePlugin() {
    const { adapter, state } = gf;
    const city = gf.getCities()[state.activeCityIndex];
    const modelId = gf.activeProjectModelId(city);
    return adapter?.getPlugin(modelId) || adapter?.getPlugin("lst");
  }

  function configureMapLibreWorker() {
    const { state } = gf;
    if (state.workerConfigured || typeof maplibregl === "undefined") return;
    maplibregl.setWorkerUrl("/vendor/maplibre-gl/maplibre-gl-csp-worker.js");
    state.workerConfigured = true;
  }

  function cityShort(name) {
    return name.split(",")[0];
  }

  function cityPeriodLabel(city) {
    if (city?.month && city?.year) {
      const names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
      ];
      return `${names[city.month - 1] || city.month} ${city.year}`;
    }
    if (city?.year) return String(city.year);
    return "";
  }

  function cityListLabel(city) {
    const short = cityShort(city.name);
    const period = cityPeriodLabel(city);
    return period ? `${short} · ${period}` : short;
  }

  function formatNumber(value) {
    if (value === null || value === undefined) return "—";
    return Number(value).toLocaleString();
  }

  function numericFieldValues(geojson, field) {
    if (!geojson?.features?.length || !field) return [];
    return geojson.features
      .map((feature) => Number(feature.properties?.[field]))
      .filter((value) => Number.isFinite(value));
  }

  function fieldValueRange(geojson, field) {
    const values = numericFieldValues(geojson, field);
    if (!values.length) return null;
    values.sort((a, b) => a - b);
    const actualMin = values[0];
    const actualMax = values[values.length - 1];
    const spread = actualMax - actualMin;

    let scaleMin = actualMin;
    let scaleMax = actualMax;
    if (spread < 2 && values.length >= 5) {
      const p10 = values[Math.floor(values.length * 0.1)];
      const p90 = values[Math.floor(values.length * 0.9)];
      if (p90 > p10) {
        scaleMin = p10;
        scaleMax = p90;
      }
    }
    if (scaleMax - scaleMin < 0.25) {
      const pad = Math.max(0.5, spread * 0.5 || 0.5);
      scaleMin = actualMin - pad;
      scaleMax = actualMax + pad;
    }

    return {
      min: scaleMin,
      max: scaleMax,
      actualMin,
      actualMax,
    };
  }

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

  function updateLegendBar(colors) {
    const { legendBarEl } = gf.dom;
    if (!legendBarEl) return;
    const cells = legendBarEl.querySelectorAll(".gf-legend-cell");
    cells.forEach((cell, index) => {
      if (colors[index]) cell.style.background = colors[index];
    });
  }

  function resetLegendBar() {
    updateLegendBar(DEFAULT_LEGEND_COLORS);
  }

  function usesLocalValueScale(field) {
    const plugin = activePlugin();
    return plugin?.usesLocalValueScale(field) || false;
  }

  function isAnalysisLayer(layerId) {
    return layerId === ANALYSIS_LAYER_ID;
  }

  function isAnalysisLayerActive() {
    return isAnalysisLayer(activeMapLayerId());
  }

  function legendContext() {
    const { state } = gf;
    const city = gf.getCities()[state.activeCityIndex];
    const modelId = gf.activeProjectModelId(city);
    const pres = gf.modelPresentation(modelId);
    const field = activeChoroplethField();
    const layerId = activeMapLayerId();
    return {
      field,
      city,
      appMode: state.appMode,
      scaleMode: state.lstScaleMode,
      tractLegendRange: state.tractLegendRange,
      pres,
      isAnalysisLayer: isAnalysisLayerActive(),
      layerId,
      layerLabels: {
        density: "Density",
        income: "Income",
        ethnicity: "Hispanic %",
        tracts: "Tracts",
        [ANALYSIS_LAYER_ID]:
          state.appMode === "project" ? pres.legendLabel : `${pres.legendLabel} demo`,
      },
    };
  }

  function setChoroplethLayerEnabled(layerId, enabled) {
    const row = document.querySelector(`.gf-layer-toggle[data-gf-layer="${layerId}"]`);
    const toggle = row?.querySelector(".gf-toggle");
    if (!toggle) return;
    toggle.classList.toggle("on", enabled);
    toggle.setAttribute("aria-checked", enabled ? "true" : "false");
  }

  function anyChoroplethLayerEnabled() {
    return CHOROPLETH_LAYER_IDS.some((id) => layerEnabled(id));
  }

  function projectLstCacheKey(field) {
    const { state } = gf;
    const ready = state.projectCityList
      .filter((city) => city.status === "ready" && gf.activeProjectModelId(city) === "lst")
      .map((city) => `${city.key}:${city.vector_layer?.token || ""}`)
      .sort()
      .join("|");
    return `${state.projectId || ""}:${field}:${ready}`;
  }

  async function loadCityTractGeojson(city) {
    const { state } = gf;
    if (!city?.key) return null;

    const vector =
      city.vector_layer || state.projectData?.cities?.[city.key]?.vector_layer || null;
    if (!vector?.geojson_url) return null;

    if (state.tractGeojsonCache.token === vector.token && state.tractGeojsonCache.data) {
      return state.tractGeojsonCache.data;
    }

    if (state.projectGeojsonCache[city.key]?.token === vector.token) {
      return state.projectGeojsonCache[city.key].data;
    }

    const response = await fetch(vector.geojson_url);
    if (!response.ok) return null;
    const data = await response.json();
    state.projectGeojsonCache[city.key] = { token: vector.token, data };
    return data;
  }

  async function ensureProjectLstRange(field) {
    const { state } = gf;
    if (state.appMode !== "project" || !field) return null;

    const cacheKey = projectLstCacheKey(field);
    if (state.projectLstRangeCache?.key === cacheKey) {
      return state.projectLstRangeCache.range;
    }

    const cities = state.projectCityList.filter(
      (city) => city.status === "ready" && gf.activeProjectModelId(city) === "lst"
    );
    if (!cities.length) return null;

    const merged = { type: "FeatureCollection", features: [] };
    for (const city of cities) {
      const geojson = await loadCityTractGeojson(city);
      if (geojson?.features?.length) {
        merged.features.push(...geojson.features);
      }
    }
    if (!merged.features.length) return null;

    const range = fieldValueRange(merged, field);
    state.projectLstRangeCache = { key: cacheKey, range };
    return range;
  }

  async function resolveLegendRange(geojson, field) {
    const { state } = gf;
    if (!usesLocalValueScale(field)) return null;
    if (state.lstScaleMode === "project" && state.appMode === "project") {
      return ensureProjectLstRange(field);
    }
    return fieldValueRange(geojson, field);
  }

  function updateLstScaleUI() {
    const { state, dom } = gf;
    if (!dom.lstScaleWrapEl) return;
    const ctx = legendContext();
    const plugin = activePlugin();
    const show = plugin?.showsScaleControls(ctx) || false;
    dom.lstScaleWrapEl.hidden = !show;

    const readyLstCount = state.projectCityList.filter(
      (city) => city.status === "ready" && gf.activeProjectModelId(city) === "lst"
    ).length;
    const projectBtn = dom.lstScaleWrapEl.querySelector('[data-gf-lst-scale="project"]');
    if (projectBtn) {
      projectBtn.hidden = readyLstCount < 2;
      projectBtn.disabled = readyLstCount < 2;
    }
    if (readyLstCount < 2 && state.lstScaleMode === "project") {
      state.lstScaleMode = "local";
      localStorage.setItem("gf_lst_scale_mode", "local");
    }

    dom.lstScaleWrapEl.querySelectorAll("[data-gf-lst-scale]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-gf-lst-scale") === state.lstScaleMode);
    });
  }

  async function setLstScaleMode(mode) {
    const { state } = gf;
    state.lstScaleMode = mode === "project" ? "project" : "local";
    localStorage.setItem("gf_lst_scale_mode", state.lstScaleMode);
    updateLstScaleUI();
    await refreshTractChoropleth();
    updateLegend();
  }

  async function refreshTractChoropleth() {
    const { state } = gf;
    if (!state.map || !state.mapReady || !state.tractGeojsonCache.data) return;
    const field = activeChoroplethField();
    if (!field) return;
    await upsertTractLayers(state.tractGeojsonCache.data, field);
  }

  function layerEnabled(layerId) {
    const row = document.querySelector(`.gf-layer-toggle[data-gf-layer="${layerId}"] .gf-toggle`);
    return row ? row.classList.contains("on") : false;
  }

  function activeMapLayerId() {
    for (const layerId of LAYER_ORDER) {
      if (layerEnabled(layerId)) return layerId;
    }
    return ANALYSIS_LAYER_ID;
  }

  function activeLayerLabel() {
    const { state } = gf;
    const layerId = activeMapLayerId();
    const city = gf.getCities()[state.activeCityIndex];
    const modelId = gf.activeProjectModelId(city);
    const pres = gf.modelPresentation(modelId);
    if (isAnalysisLayer(layerId) || layerId === pres.analysisLayerId) {
      if (state.appMode === "project" && city?.status === "ready") return pres.analysisLayerLabel;
      return `${pres.legendLabel} (demo — density stand-in)`;
    }
    return state.cityLayersData?.map_layers?.[layerId]?.label || "Map layer";
  }

  function activeChoroplethField() {
    const { state, adapter } = gf;
    const layerId = activeMapLayerId();
    const city = gf.getCities()[state.activeCityIndex];
    const modelId = gf.activeProjectModelId(city);
    const pres = gf.modelPresentation(modelId);
    if (isAnalysisLayer(layerId) || layerId === pres.analysisLayerId) {
      if (state.appMode === "project" && city?.status === "ready") {
        return (
          adapter?.choroplethField(modelId, layerId, state.appMode, city) ||
          pres.choroplethField ||
          city?.vector_layer?.fields?.find((f) => f === pres.choroplethField) ||
          pres.choroplethField
        );
      }
      return LAYER_FIELDS.density;
    }
    return LAYER_FIELDS[layerId] ?? state.cityLayersData?.map_layers?.[layerId]?.field ?? null;
  }

  function updateLegend() {
    const { state, dom } = gf;
    const ctx = legendContext();
    const plugin = activePlugin();
    const legend = plugin?.renderLegend(ctx);

    if (legend) {
      if (dom.legendTitleEl) dom.legendTitleEl.textContent = legend.title || ctx.pres.legendLabel || "Map";
      if (dom.legendLowEl) dom.legendLowEl.textContent = legend.low ?? "Low";
      if (dom.legendHighEl) dom.legendHighEl.textContent = legend.high ?? "High";
      if (legend.colorStops?.length) updateLegendBar(legend.colorStops);
    } else {
      const labels = ctx.layerLabels;
      if (dom.legendTitleEl) {
        dom.legendTitleEl.textContent =
          labels[ctx.layerId] ||
          (ctx.layerId === ctx.pres.analysisLayerId ? ctx.pres.legendLabel : "Map");
      }
      if (dom.legendLowEl) dom.legendLowEl.textContent = "Low";
      if (dom.legendHighEl) dom.legendHighEl.textContent = "High";
      resetLegendBar();
    }
    updateLstScaleUI();
  }

  function choroplethFillPaint(field, valueRange) {
    const { state } = gf;
    if (!field) {
      return { "fill-color": "#5a9ab8", "fill-opacity": 0.78 };
    }

    const value = ["coalesce", ["to-number", ["get", field]], 0];
    const ctx = {
      ...legendContext(),
      scaleMode: state.lstScaleMode,
      isAnalysisLayer: isAnalysisLayerActive(),
    };
    const pluginPaint = activePlugin()?.choroplethFillPaint(field, valueRange, ctx);
    if (pluginPaint) return pluginPaint;

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
    const { state } = gf;
    if (!state.map) return;
    state.map.resize();
  }

  function afterLayout(callback) {
    requestAnimationFrame(() => {
      requestAnimationFrame(callback);
    });
  }

  function tractPopupHtml(props) {
    const { state } = gf;
    const name = props.acs_name || props.NAME || props.GEOID || "Census tract";
    const field = activeChoroplethField();
    const layerLabel = activeLayerLabel();
    const plugin = activePlugin();

    let metricHtml = "";
    if (field === "median_income_usd" && props.median_income_usd != null) {
      metricHtml = `<div class="gf-tract-popup-metric">$${formatNumber(props.median_income_usd)}</div><div class="gf-tract-popup-metric-label">${layerLabel}</div>`;
    } else if (field === "hispanic_pct" && props.hispanic_pct != null) {
      metricHtml = `<div class="gf-tract-popup-metric">${props.hispanic_pct}%</div><div class="gf-tract-popup-metric-label">${layerLabel}</div>`;
    } else if (field === "population_density_per_km2" && props.population_density_per_km2 != null) {
      metricHtml = `<div class="gf-tract-popup-metric">${formatNumber(props.population_density_per_km2)}/km²</div><div class="gf-tract-popup-metric-label">${layerLabel}</div>`;
    } else if (plugin) {
      metricHtml = plugin.tractPopupMetric(props, field, layerLabel);
    }

    const rows = [
      ["Population", formatNumber(props.population)],
      ["Median income", props.median_income_usd != null ? `$${formatNumber(props.median_income_usd)}` : "—"],
      ["Hispanic %", props.hispanic_pct != null ? `${props.hispanic_pct}%` : "—"],
      ["Black %", props.black_pct != null ? `${props.black_pct}%` : "—"],
      ["Density", props.population_density_per_km2 != null ? `${formatNumber(props.population_density_per_km2)}/km²` : "—"],
    ];
    const detailRow = plugin?.tractDetailRow(props);
    if (detailRow) rows.push(detailRow);
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
    const { state } = gf;
    if (!state.map || state.hoveredTractId == null) return;
    state.map.setFeatureState({ source: "tracts", id: state.hoveredTractId }, { hover: false });
    state.hoveredTractId = null;
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
    const { state } = gf;
    if (!state.map || state.tractInteractionsBound) return;
    state.tractInteractionsBound = true;

    state.map.on("mousemove", "tracts-fill", (event) => {
      const feature = event.features && event.features[0];
      if (!feature) return;

      state.map.getCanvas().style.cursor = "pointer";

      if (state.hoveredTractId !== null && state.hoveredTractId !== feature.id) {
        state.map.setFeatureState({ source: "tracts", id: state.hoveredTractId }, { hover: false });
      }
      state.hoveredTractId = feature.id;
      state.map.setFeatureState({ source: "tracts", id: state.hoveredTractId }, { hover: true });

      state.popup.setLngLat(event.lngLat).setHTML(tractPopupHtml(feature.properties)).addTo(state.map);
    });

    state.map.on("mouseleave", "tracts-fill", () => {
      clearTractHover();
      state.popup.remove();
      state.map.getCanvas().style.cursor = "";
    });

    state.map.on("click", "tracts-fill", (event) => {
      const feature = event.features && event.features[0];
      if (!feature) return;
      const bounds = boundsFromFeature(feature);
      state.map.fitBounds(bounds, { padding: 72, duration: 700, maxZoom: 14 });
    });
  }

  function ensureMap() {
    const { state, dom } = gf;
    if (!dom.mapContainerEl || typeof maplibregl === "undefined") return null;
    configureMapLibreWorker();
    if (state.map) return state.map;

    state.map = new maplibregl.Map({
      container: dom.mapContainerEl,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: "bg", type: "background", paint: { "background-color": "#e8edf2" } }],
      },
      center: [-98.5, 39.5],
      zoom: 3,
      attributionControl: true,
    });

    state.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    state.popup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      maxWidth: "300px",
      className: "gf-tract-hover-popup",
      offset: 14,
    });

    bindTractInteractions();

    state.map.on("load", () => {
      state.mapReady = true;
      refreshMapSize();
      if (state.cityLayersData) renderActiveMapLayer();
    });

    return state.map;
  }

  function fitMapBounds(bounds) {
    const { state } = gf;
    if (!state.map || !bounds || bounds.length !== 4) return;
    const [west, south, east, north] = bounds;
    state.map.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      { padding: 36, duration: 600 }
    );
  }

  function removeRasterOverlay() {
    const { state } = gf;
    if (!state.map) return;
    if (state.map.getLayer("raster-overlay")) state.map.removeLayer("raster-overlay");
    if (state.map.getSource("raster-overlay")) state.map.removeSource("raster-overlay");
  }

  function setRasterOverlay(url, bounds) {
    const { state } = gf;
    if (!state.map || !state.mapReady || !url || !bounds || bounds.length !== 4) return;
    const [west, south, east, north] = bounds;
    const absoluteUrl = url.startsWith("http") ? url : `${window.location.origin}${url}`;
    removeRasterOverlay();
    state.map.addSource("raster-overlay", {
      type: "image",
      url: `${absoluteUrl}${absoluteUrl.includes("?") ? "&" : "?"}t=${Date.now()}`,
      coordinates: [
        [west, north],
        [east, north],
        [east, south],
        [west, south],
      ],
    });
    state.map.addLayer({
      id: "raster-overlay",
      type: "raster",
      source: "raster-overlay",
      paint: { "raster-opacity": 0.88 },
    });
    if (state.map.getLayer("tracts-fill")) {
      state.map.setPaintProperty("tracts-fill", "fill-opacity", 0.15);
      state.map.setPaintProperty("tracts-line", "line-opacity", 0.35);
    }
  }

  function showVectorLayers() {
    const { state } = gf;
    if (!state.map || !state.map.getLayer("tracts-fill")) return;
    state.map.setLayoutProperty("tracts-fill", "visibility", "visible");
    state.map.setLayoutProperty("tracts-line", "visibility", "visible");
    state.map.setPaintProperty("tracts-fill", "fill-opacity", 0.78);
    state.map.setPaintProperty("tracts-line", "line-opacity", 1);
    removeRasterOverlay();
  }

  async function loadTractGeojson() {
    const { state } = gf;
    const vector = state.cityLayersData?.vector_layer;
    if (!vector?.geojson_url) return null;

    if (state.tractGeojsonCache.token === vector.token && state.tractGeojsonCache.data) {
      return state.tractGeojsonCache.data;
    }

    const response = await fetch(vector.geojson_url);
    if (!response.ok) throw new Error("Could not load tract GeoJSON.");
    const data = await response.json();
    state.tractGeojsonCache = { token: vector.token, data };
    if (state.appMode === "project") {
      const city = gf.getCities()[state.activeCityIndex];
      if (city?.key) {
        state.projectGeojsonCache[city.key] = { token: vector.token, data };
      }
    }
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

  async function upsertTractLayers(geojson, field) {
    const { state } = gf;
    if (!state.map || !state.mapReady) return;

    clearTractHover();
    state.popup.remove();

    state.tractLegendRange = await resolveLegendRange(geojson, field);
    const fillPaint = {
      ...choroplethFillPaint(field, state.tractLegendRange),
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

    if (state.map.getSource("tracts")) {
      state.map.getSource("tracts").setData(geojson);
    } else {
      state.map.addSource("tracts", { type: "geojson", data: geojson, promoteId: "GEOID" });
      state.map.addLayer({
        id: "tracts-fill",
        type: "fill",
        source: "tracts",
        paint: fillPaint,
      });
      state.map.addLayer({
        id: "tracts-line",
        type: "line",
        source: "tracts",
        paint: { ...outline, ...hoverOutline },
      });
    }

    Object.keys(fillPaint).forEach((key) => {
      state.map.setPaintProperty("tracts-fill", key, fillPaint[key]);
    });
    Object.keys(outline).forEach((key) => {
      state.map.setPaintProperty("tracts-line", key, outline[key]);
    });
    state.map.setPaintProperty("tracts-line", "line-width", hoverOutline["line-width"]);
    updateLegend();
  }

  async function renderActiveMapLayer() {
    const { state, dom } = gf;
    if (!state.cityLayersData) return;

    state.tractLegendRange = null;
    const layerId = activeMapLayerId();
    const city = gf.getCities()[state.activeCityIndex];
    const modelId = gf.activeProjectModelId(city);
    const summary = state.cityLayersData.summary || {};

    if (state.appMode === "project" && !gf.isEquityDashboard(modelId)) {
      gf.updateMapWarning(city);
      if (dom.mapOverlayEl) {
        dom.mapOverlayEl.innerHTML = `
          <div class="gf-map-overlay-title">${city.name} · ${gf.modelPresentation(modelId).legendLabel}</div>
          <div class="gf-map-overlay-sub">Raster dashboard shell — map view for this model is not implemented yet.</div>
        `;
      }
      if (dom.mapEmptyEl) {
        dom.mapEmptyEl.textContent =
          "This model uses a raster dashboard type. Full map view will be added when the model is integrated.";
        dom.mapEmptyEl.classList.remove("hidden");
      }
      dom.mapContainerEl?.classList.add("hidden");
      return;
    }

    if (dom.mapEmptyEl) dom.mapEmptyEl.classList.add("hidden");

    if (dom.mapOverlayEl) {
      const warning = state.appMode === "project" ? gf.cityRunWarning(city) : null;
      dom.mapOverlayEl.innerHTML = `
        <div class="gf-map-overlay-title">${city.name} · ${activeLayerLabel()}</div>
        <div class="gf-map-overlay-sub">${summary.county || ""} · ${formatNumber(summary.tract_count)} tracts · hover for details, click to zoom</div>
        ${warning ? `<div class="gf-map-overlay-warning">${warning}</div>` : ""}
      `;
    }
    gf.updateMapWarning(city);
    updateLegend();

    if (!dom.mapContainerEl || typeof maplibregl === "undefined") {
      if (dom.mapEmptyEl) {
        dom.mapEmptyEl.textContent = "MapLibre failed to load. Check your network connection.";
        dom.mapEmptyEl.classList.remove("hidden");
      }
      return;
    }

    ensureMap();
    dom.mapContainerEl.classList.remove("hidden");
    if (dom.mapEmptyEl) dom.mapEmptyEl.classList.add("hidden");

    const render = async () => {
      try {
        const geojson = await loadTractGeojson();
        if (!geojson) throw new Error("No vector layer for this city.");

        const field = activeChoroplethField();
        await upsertTractLayers(geojson, field);
        refreshMapSize();
        fitMapBounds(state.cityLayersData.vector_layer?.bounds_wgs84);
        showVectorLayers();
      } catch (error) {
        if (dom.mapEmptyEl) {
          dom.mapEmptyEl.textContent = error.message || "Could not render map.";
          dom.mapEmptyEl.classList.remove("hidden");
        }
      }
    };

    if (state.mapReady) {
      await render();
    } else {
      state.map.once("load", () => render());
    }
  }

  async function loadProjectCity(cityKey) {
    const { state, dom } = gf;
    const entry = state.projectData?.cities?.[cityKey];
    if (!entry) return null;
    if (dom.mapLoadingEl) {
      dom.mapLoadingEl.hidden = false;
      dom.mapLoadingEl.textContent = `Loading ${entry.name}…`;
    }
    state.cityLayersData = {
      address: entry.address,
      summary: entry.summary || {},
      vector_layer: entry.vector_layer,
      map_layers: entry.map_layers || {},
      sources: {
        analysis: gf.modelPresentation(gf.activeProjectModelId(entry)).sourcesAnalysis || "Model output",
        census: "Census ACS",
      },
    };
    state.tractGeojsonCache = { token: null, data: null };
    if (dom.mapLoadingEl) dom.mapLoadingEl.hidden = true;
    gf.updateStats?.();
    gf.updateMapWarning(state.projectCityList.find((c) => c.key === cityKey) || entry);
    await renderActiveMapLayer();
    return state.cityLayersData;
  }

  Object.assign(gf, {
    cityShort,
    cityListLabel,
    formatNumber,
    setChoroplethLayerEnabled,
    anyChoroplethLayerEnabled,
    updateLstScaleUI,
    setLstScaleMode,
    activeMapLayerId,
    refreshMapSize,
    afterLayout,
    fitMapBounds,
    renderActiveMapLayer,
    loadProjectCity,
  });
})();
