/**
 * Urban Heat & Equity GUI Frame — live census maps as server-rendered PNGs (pan/zoom, no Leaflet).
 */
(function () {
  const CITIES = [
    { name: "Phoenix, AZ", temp: 42.3, month: "July", color: "#c45a1a" },
    { name: "Houston, TX", temp: 39.1, month: "August", color: "#d4652a" },
    { name: "Dallas, TX", temp: 38.4, month: "July", color: "#d4652a" },
    { name: "Miami, FL", temp: 37.8, month: "August", color: "#e07b32" },
    { name: "Los Angeles, CA", temp: 36.5, month: "September", color: "#e07b32" },
    { name: "Atlanta, GA", temp: 36.1, month: "July", color: "#e07b32" },
    { name: "Memphis, TN", temp: 37.2, month: "July", color: "#e07b32" },
    { name: "Chicago, IL", temp: 34.2, month: "July", color: "#3d7ea6" },
    { name: "Detroit, MI", temp: 33.8, month: "July", color: "#3d7ea6" },
    { name: "Baltimore, MD", temp: 33.4, month: "July", color: "#5a9ab8" },
    { name: "Cleveland, OH", temp: 32.9, month: "July", color: "#5a9ab8" },
  ];

  const MAX_TEMP = Math.max(...CITIES.map((c) => c.temp));
  const HOTTEST = CITIES.reduce((a, b) => (a.temp >= b.temp ? a : b));

  const LAYER_ORDER = ["density", "income", "ethnicity", "tracts", "worldpop", "lst"];

  let activeCityIndex = 0;
  let cityLayersData = null;

  let chatMessages = [
    {
      role: "assistant",
      text: "Welcome! Select a city to load census tract maps from live APIs. Maps are rendered on the server — drag to pan and scroll to zoom. Set CENSUS_API_KEY in .env for demographic data.",
    },
  ];

  const cityListEl = document.getElementById("gfCityList");
  const barChartEl = document.getElementById("gfBarChart");
  const cityGridEl = document.getElementById("gfCityGrid");
  const mapOverlayEl = document.getElementById("gfMapOverlay");
  const mapLoadingEl = document.getElementById("gfMapLoading");
  const mapViewportEl = document.getElementById("gfMapViewport");
  const mapImageEl = document.getElementById("gfMapImage");
  const mapEmptyEl = document.getElementById("gfMapEmpty");
  const chatPanelEl = document.getElementById("gfPanelChat");
  const queryInputEl = document.getElementById("gfQueryInput");
  const sendBtnEl = document.getElementById("gfSendBtn");
  const legendTitleEl = document.getElementById("gfLegendTitle");

  const mapView = { scale: 1, x: 0, y: 0, dragging: false, pointerId: null, lastX: 0, lastY: 0 };

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

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function applyMapTransform() {
    if (!mapImageEl) return;
    mapImageEl.style.transform = `translate(${mapView.x}px, ${mapView.y}px) scale(${mapView.scale})`;
  }

  function fitMapToViewport() {
    if (!mapImageEl?.naturalWidth || !mapViewportEl) return;
    const vw = mapViewportEl.clientWidth;
    const vh = mapViewportEl.clientHeight;
    const iw = mapImageEl.naturalWidth;
    const ih = mapImageEl.naturalHeight;
    const fitScale = Math.min(vw / iw, vh / ih) * 0.96;
    mapView.scale = clamp(fitScale, 0.05, 8);
    mapView.x = (vw - iw * mapView.scale) / 2;
    mapView.y = (vh - ih * mapView.scale) / 2;
    applyMapTransform();
  }

  function zoomMapAt(clientX, clientY, factor) {
    if (!mapViewportEl) return;
    const rect = mapViewportEl.getBoundingClientRect();
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    const nextScale = clamp(mapView.scale * factor, 0.1, 10);
    mapView.x = px - ((px - mapView.x) * nextScale) / mapView.scale;
    mapView.y = py - ((py - mapView.y) * nextScale) / mapView.scale;
    mapView.scale = nextScale;
    applyMapTransform();
  }

  function activeMapLayerId() {
    for (const layerId of LAYER_ORDER) {
      if (layerEnabled(layerId)) return layerId;
    }
    return "density";
  }

  function activePreviewUrl() {
    if (!cityLayersData) return null;
    const layerId = activeMapLayerId();
    if (layerId === "worldpop") return cityLayersData.worldpop?.preview_url || null;
    if (layerId === "lst") return cityLayersData.map_layers?.density?.preview_url || null;
    return cityLayersData.map_layers?.[layerId]?.preview_url || null;
  }

  function activeLayerLabel() {
    const layerId = activeMapLayerId();
    if (layerId === "worldpop") return "WorldPop gridded population";
    if (layerId === "lst") return "LST (demo — use density map until LST rasters added)";
    return cityLayersData?.map_layers?.[layerId]?.label || "Map layer";
  }

  function updateLegend() {
    if (!legendTitleEl) return;
    const labels = {
      density: "Density",
      income: "Income",
      ethnicity: "Hispanic %",
      tracts: "Tracts",
      worldpop: "WorldPop",
      lst: "LST demo",
    };
    legendTitleEl.textContent = labels[activeMapLayerId()] || "Map";
  }

  function showMapImage(url) {
    if (!mapImageEl || !mapEmptyEl) return;
    if (!url) {
      mapImageEl.classList.add("hidden");
      mapEmptyEl.classList.remove("hidden");
      mapEmptyEl.textContent = "No preview for this layer.";
      return;
    }

    mapEmptyEl.classList.add("hidden");
    mapImageEl.classList.remove("hidden");
    mapImageEl.onload = () => fitMapToViewport();
    mapImageEl.src = `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;
    if (mapImageEl.complete) fitMapToViewport();
    updateLegend();
  }

  function renderActiveMapLayer() {
    showMapImage(activePreviewUrl());
    if (mapOverlayEl && cityLayersData) {
      const city = CITIES[activeCityIndex];
      const summary = cityLayersData.summary || {};
      mapOverlayEl.innerHTML = `
        <div class="gf-map-overlay-title">${city.name} · ${activeLayerLabel()}</div>
        <div class="gf-map-overlay-sub">${summary.county || ""} · ${formatNumber(summary.tract_count)} tracts</div>
      `;
    }
  }

  function demoContext() {
    const city = CITIES[activeCityIndex];
    const summary = cityLayersData?.summary || {};
    return {
      model: "lst",
      summary: cityLayersData
        ? `Live data for ${city.name} (${summary.county}, ${summary.state}).`
        : "11-city urban heat and equity GUI frame demo.",
      stats: {
        hottest_city: HOTTEST.name,
        peak_lst_C: HOTTEST.temp,
        active_city: city.name,
        demo_lst_C: city.temp,
        ...summary,
        cities: CITIES,
      },
      logs: cityLayersData ? JSON.stringify(cityLayersData.sources || {}) : "",
      raster: city.name,
      artifacts: [],
      reference_layers: [],
    };
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
        throw new Error(
          typeof payload.detail === "string" ? payload.detail : "Failed to load city layers."
        );
      }
      cityLayersData = payload;
      if (mapLoadingEl) mapLoadingEl.hidden = true;
      updateStats();
      renderActiveMapLayer();
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
    const city = CITIES[index];

    document.querySelectorAll(".gf-city-btn").forEach((btn, i) => {
      btn.classList.toggle("active", i === index);
    });
    document.querySelectorAll(".gf-mini-city").forEach((cell, i) => {
      cell.classList.toggle("active", i === index);
    });

    await fetchCityLayers(city.name);
  }

  function buildCityList() {
    if (!cityListEl) return;
    cityListEl.innerHTML = "";
    CITIES.forEach((city, index) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "gf-city-btn" + (index === 0 ? " active" : "");
      btn.innerHTML = `
        <span class="gf-city-btn-left">
          <span class="gf-city-dot" style="background:${city.color}"></span>
          ${cityShort(city.name)}
        </span>
        <span class="gf-temp-pill" style="background:${city.color}22;color:${city.color}">${city.temp}°</span>
      `;
      btn.addEventListener("click", () => selectCity(index));
      cityListEl.appendChild(btn);
    });
  }

  function buildBarChart() {
    if (!barChartEl) return;
    barChartEl.innerHTML = "";
    CITIES.forEach((city) => {
      const pct = Math.round((city.temp / MAX_TEMP) * 100);
      const row = document.createElement("div");
      row.className = "gf-chart-row";
      row.innerHTML = `
        <span>${cityShort(city.name)}</span>
        <div class="gf-bar-track"><div class="gf-bar-fill" style="width:${pct}%;background:${city.color}"></div></div>
        <span class="gf-bar-val">${city.temp}°</span>
      `;
      barChartEl.appendChild(row);
    });
  }

  function buildCityGrid() {
    if (!cityGridEl) return;
    cityGridEl.innerHTML = "";
    CITIES.forEach((city, index) => {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "gf-mini-city" + (index === 0 ? " active" : "");
      cell.innerHTML = `
        <div class="gf-mini-city-name">${cityShort(city.name)}</div>
        <div class="gf-mini-city-temp" style="color:${city.color}">${city.temp}°C</div>
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

  function mockAnswer(question) {
    const q = question.toLowerCase();
    const summary = cityLayersData?.summary || {};
    if (summary.tract_count && q.includes("income")) {
      return `In ${CITIES[activeCityIndex].name} (${summary.county}), median tract income is about $${formatNumber(summary.median_income_usd)} across ${summary.tract_count} tracts.`;
    }
    if (summary.avg_density_per_km2 && (q.includes("density") || q.includes("population"))) {
      return `Average tract population density in ${summary.county} is about ${formatNumber(summary.avg_density_per_km2)} people per km².`;
    }
    if (q.includes("ethnic") || q.includes("hispanic")) {
      return `Use the Ethnicity overlay on the map for Hispanic % by tract in ${summary.county}.`;
    }
    const city = CITIES[activeCityIndex];
    return `For ${city.name}: demo peak LST is ${city.temp}°C. Live census map layers are loaded for ${summary.county || "the county"}.`;
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
        body: JSON.stringify({ question: q, context: demoContext() }),
      });
      const payload = await response.json().catch(() => ({}));
      chatMessages.push({
        role: "assistant",
        text: response.ok ? payload.answer || mockAnswer(q) : mockAnswer(q),
      });
    } catch {
      chatMessages.push({ role: "assistant", text: mockAnswer(q) });
    } finally {
      if (sendBtnEl) sendBtnEl.disabled = false;
      renderChat();
    }
  }

  function wireMapInteractions() {
    if (!mapViewportEl) return;

    mapViewportEl.addEventListener(
      "wheel",
      (event) => {
        if (mapImageEl.classList.contains("hidden")) return;
        event.preventDefault();
        zoomMapAt(event.clientX, event.clientY, event.deltaY < 0 ? 1.12 : 1 / 1.12);
      },
      { passive: false }
    );

    mapViewportEl.addEventListener("pointerdown", (event) => {
      if (mapImageEl.classList.contains("hidden")) return;
      mapView.dragging = true;
      mapView.pointerId = event.pointerId;
      mapView.lastX = event.clientX;
      mapView.lastY = event.clientY;
      mapViewportEl.classList.add("is-dragging");
      mapViewportEl.setPointerCapture(event.pointerId);
    });

    mapViewportEl.addEventListener("pointermove", (event) => {
      if (!mapView.dragging || event.pointerId !== mapView.pointerId) return;
      mapView.x += event.clientX - mapView.lastX;
      mapView.y += event.clientY - mapView.lastY;
      mapView.lastX = event.clientX;
      mapView.lastY = event.clientY;
      applyMapTransform();
    });

    const endDrag = (event) => {
      if (!mapView.dragging || event.pointerId !== mapView.pointerId) return;
      mapView.dragging = false;
      mapView.pointerId = null;
      mapViewportEl.classList.remove("is-dragging");
      if (mapViewportEl.hasPointerCapture(event.pointerId)) {
        mapViewportEl.releasePointerCapture(event.pointerId);
      }
    };
    mapViewportEl.addEventListener("pointerup", endDrag);
    mapViewportEl.addEventListener("pointercancel", endDrag);

    window.addEventListener("resize", () => {
      if (!mapImageEl.classList.contains("hidden")) fitMapToViewport();
    });
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

    document.getElementById("gfZoomIn")?.addEventListener("click", () => {
      const rect = mapViewportEl?.getBoundingClientRect();
      if (rect) zoomMapAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1.2);
    });
    document.getElementById("gfZoomOut")?.addEventListener("click", () => {
      const rect = mapViewportEl?.getBoundingClientRect();
      if (rect) zoomMapAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1 / 1.2);
    });
    document.getElementById("gfZoomReset")?.addEventListener("click", () => fitMapToViewport());
    document.getElementById("gfAllCitiesBtn")?.addEventListener("click", () => switchPanelTab("layers"));
  }

  let initialized = false;

  function init() {
    buildCityList();
    buildBarChart();
    buildCityGrid();
    renderChat();
    wireControls();
    wireMapInteractions();

    if (!initialized) {
      initialized = true;
      selectCity(0);
    } else if (!mapImageEl.classList.contains("hidden")) {
      fitMapToViewport();
    }
  }

  window.GfFrame = { init, activate: init };

  if (document.getElementById("page-gfframe")) init();
})();
