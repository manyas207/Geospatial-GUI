/**
 * Urban Heat & Equity GUI Frame — UI builders, controls, and activation.
 */
(function () {
  const gf = window.GfFrame;
  const { ANALYSIS_LAYER_ID, CHOROPLETH_LAYER_IDS } = gf;

  function updateStats() {
    const { state } = gf;
    const summary = state.cityLayersData?.summary || {};
    const set = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    };
    set("gfStatCounty", summary.county || "—");
    set("gfStatTracts", gf.formatNumber(summary.tract_count));
    set("gfStatPopulation", gf.formatNumber(summary.total_population));
    set("gfStatIncome", summary.median_income_usd ? `$${gf.formatNumber(summary.median_income_usd)}` : "—");
    set(
      "gfStatDensity",
      summary.avg_density_per_km2 != null ? `${gf.formatNumber(summary.avg_density_per_km2)}/km²` : "—"
    );
  }

  async function fetchCityLayers(address) {
    const { state, dom } = gf;
    if (state.appMode === "demo" && state.demoPortfolioCache[address]) {
      state.cityLayersData = state.demoPortfolioCache[address];
      state.tractGeojsonCache = { token: null, data: null };
      updateStats();
      await gf.renderActiveMapLayer();
      return state.cityLayersData;
    }

    if (dom.mapLoadingEl) {
      dom.mapLoadingEl.hidden = false;
      dom.mapLoadingEl.textContent = `Loading census & population data for ${address}… (first load may download tract boundaries)`;
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
      state.cityLayersData = payload;
      state.tractGeojsonCache = { token: null, data: null };
      if (state.appMode === "demo") {
        state.demoPortfolioCache[address] = payload;
      }
      if (dom.mapLoadingEl) dom.mapLoadingEl.hidden = true;
      updateStats();
      await gf.renderActiveMapLayer();
      return payload;
    } catch (error) {
      if (dom.mapLoadingEl) {
        dom.mapLoadingEl.hidden = false;
        dom.mapLoadingEl.textContent = error.message || "Could not load city data.";
      }
      return null;
    }
  }

  async function selectCity(index) {
    const { state } = gf;
    state.activeCityIndex = index;
    const cities = gf.getCities();
    const city = cities[index];
    if (!city) return;

    document.querySelectorAll(".gf-city-btn").forEach((btn, i) => {
      btn.classList.toggle("active", i === index);
    });
    document.querySelectorAll(".gf-mini-city").forEach((cell, i) => {
      cell.classList.toggle("active", i === index);
    });

    if (state.appMode === "project" && city.status === "ready" && city.key) {
      await gf.loadProjectCity(city.key);
    } else {
      await fetchCityLayers(city.name || city.address);
    }
  }

  function buildCityList() {
    const { state, dom } = gf;
    if (!dom.cityListEl) return;
    dom.cityListEl.innerHTML = "";
    const cities = gf.getCities();
    if (state.appMode === "project" && cities.length === 0) {
      const hint =
        gf.modelPresentation(state.projectModelId).emptyProjectHint ||
        "No cities in this project. Use <strong>Back to Ask</strong> to upload input files.";
      dom.cityListEl.innerHTML = `<p class="muted gf-project-hint">${hint}</p>`;
      return;
    }
    cities.forEach((city, index) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "gf-city-btn" + (index === state.activeCityIndex ? " active" : "");
      const warning = state.appMode === "project" ? gf.cityRunWarning(city) : null;
      const statusKey =
        state.appMode === "project" && city.status
          ? warning
            ? "warn"
            : city.status
          : null;
      const status =
        statusKey
          ? `<span class="gf-city-status gf-city-status-${statusKey}">${warning ? "needs review" : city.status}</span>`
          : "";
      btn.innerHTML = `
        <span class="gf-city-btn-left">
          <span class="gf-city-dot" style="background:${city.color}"></span>
          ${gf.cityListLabel(city)}${status}
        </span>
        <span class="gf-temp-pill" style="background:${city.color}22;color:${city.color}">${gf.cityLstDisplay(city)}</span>
      `;
      btn.addEventListener("click", () => selectCity(index));
      dom.cityListEl.appendChild(btn);
    });
  }

  function buildBarChart() {
    const { state, dom, adapter } = gf;
    if (!dom.barChartEl) return;
    dom.barChartEl.innerHTML = "";
    const cities = gf.getCities();
    const maxVal = gf.barChartMax();
    const modelId = state.appMode === "project" ? state.projectModelId : "lst";
    const pres = gf.modelPresentation(modelId);
    const label =
      state.appMode === "project"
        ? pres.barChartHeadingProject || pres.barChartLabelProject
        : pres.barChartHeadingDemo || pres.barChartLabelDemo;
    cities.forEach((city) => {
      const val = state.appMode === "project" ? gf.projectPrimaryMetric(city) : city.temp;
      const pct = val != null ? Math.round((val / maxVal) * 100) : 0;
      const valLabel =
        val != null
          ? state.appMode === "project"
            ? adapter?.formatPrimaryValueShort(val, gf.activeProjectModelId(city))
            : `${val}°`
          : "—";
      const row = document.createElement("div");
      row.className = "gf-chart-row";
      row.innerHTML = `
        <span>${gf.cityShort(city.name)}</span>
        <div class="gf-bar-track"><div class="gf-bar-fill" style="width:${pct}%;background:${city.color}"></div></div>
        <span class="gf-bar-val">${valLabel}</span>
      `;
      dom.barChartEl.appendChild(row);
    });
    const heading = document.querySelector("#gfPanelCharts .gf-panel-heading");
    if (heading) heading.textContent = label;
  }

  function buildCityGrid() {
    const { state, dom } = gf;
    if (!dom.cityGridEl) return;
    dom.cityGridEl.innerHTML = "";
    gf.getCities().forEach((city, index) => {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "gf-mini-city" + (index === state.activeCityIndex ? " active" : "");
      const temp = state.appMode === "project" ? gf.projectPrimaryMetric(city) : city.temp;
      const unit = state.appMode === "project" ? gf.modelPresentation(gf.activeProjectModelId(city)).metricUnit : "°C";
      cell.innerHTML = `
        <div class="gf-mini-city-name">${gf.cityListLabel(city)}</div>
        <div class="gf-mini-city-temp" style="color:${city.color}">${temp != null ? `${temp}${unit}` : "—"}</div>
        <div class="gf-mini-city-state muted">${city.name.split(", ")[1] || ""}</div>
      `;
      cell.addEventListener("click", () => selectCity(index));
      dom.cityGridEl.appendChild(cell);
    });
  }

  function wirePanelResize() {
    const panel = document.getElementById("gfRightPanel");
    const handle = document.getElementById("gfPanelResizeHandle");
    if (!panel || !handle || handle.dataset.gfResizeWired === "1") return;
    handle.dataset.gfResizeWired = "1";

    const PANEL_WIDTH_KEY = "gf_panel_width";
    const PANEL_MIN = 250;
    const PANEL_MAX = 560;

    function clampWidth(value) {
      const max = Math.min(PANEL_MAX, Math.floor(window.innerWidth * 0.55));
      return Math.min(max, Math.max(PANEL_MIN, value));
    }

    function applyPanelWidth(px) {
      const width = clampWidth(px);
      panel.style.width = `${width}px`;
      document.documentElement.style.setProperty("--gf-panel-width", `${width}px`);
      localStorage.setItem(PANEL_WIDTH_KEY, String(width));
      if (document.getElementById("page-gfframe")?.classList.contains("active")) {
        gf.refreshMapSize();
      }
    }

    const saved = Number.parseInt(localStorage.getItem(PANEL_WIDTH_KEY) || "", 10);
    if (!Number.isNaN(saved)) applyPanelWidth(saved);

    let dragging = false;
    let startX = 0;
    let startWidth = 0;

    function stopDrag(event) {
      if (!dragging) return;
      dragging = false;
      handle.classList.remove("is-dragging");
      document.body.classList.remove("gf-panel-resizing");
      if (event?.pointerId != null && handle.releasePointerCapture) {
        try {
          handle.releasePointerCapture(event.pointerId);
        } catch {
          /* pointer already released */
        }
      }
    }

    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      dragging = true;
      startX = event.clientX;
      startWidth = panel.getBoundingClientRect().width;
      handle.classList.add("is-dragging");
      document.body.classList.add("gf-panel-resizing");
      handle.setPointerCapture(event.pointerId);
      event.preventDefault();
    });

    handle.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      applyPanelWidth(startWidth + (startX - event.clientX));
    });

    handle.addEventListener("pointerup", stopDrag);
    handle.addEventListener("pointercancel", stopDrag);

    handle.addEventListener("dblclick", () => {
      applyPanelWidth(PANEL_MIN);
    });
  }

  function wireControls() {
    const { dom, state } = gf;
    if (dom.keyQueriesEl) {
      dom.keyQueriesEl.addEventListener("click", (event) => {
        const btn = event.target.closest("button[data-gf-prompt]");
        if (!btn) return;
        gf.askQuestion(btn.dataset.gfPrompt || "");
      });
    }

    document.querySelectorAll(".gf-panel-tab").forEach((tab) => {
      tab.addEventListener("click", () => gf.switchPanelTab(tab.dataset.gfTab || "chat"));
    });

    document.querySelectorAll(".gf-layer-toggle").forEach((row) => {
      const toggle = row.querySelector(".gf-toggle");
      const layerId = row.dataset.gfLayer;
      if (!toggle || !CHOROPLETH_LAYER_IDS.includes(layerId)) return;
      toggle.addEventListener("click", () => {
        const enabling = !toggle.classList.contains("on");
        if (enabling) {
          CHOROPLETH_LAYER_IDS.forEach((id) => gf.setChoroplethLayerEnabled(id, id === layerId));
        } else {
          gf.setChoroplethLayerEnabled(layerId, false);
          if (!gf.anyChoroplethLayerEnabled()) {
            gf.setChoroplethLayerEnabled(ANALYSIS_LAYER_ID, true);
          }
        }
        gf.updateLstScaleUI();
        gf.renderActiveMapLayer();
      });
    });

    if (dom.lstScaleWrapEl) {
      dom.lstScaleWrapEl.addEventListener("click", (event) => {
        const btn = event.target.closest("[data-gf-lst-scale]");
        if (!btn) return;
        event.preventDefault();
        const mode = btn.getAttribute("data-gf-lst-scale") || "local";
        gf.setLstScaleMode(mode);
      });
    }

    if (dom.sendBtnEl) {
      dom.sendBtnEl.addEventListener("click", () => {
        gf.askQuestion(dom.queryInputEl?.value || "");
        if (dom.queryInputEl) dom.queryInputEl.value = "";
      });
    }

    if (dom.queryInputEl) {
      dom.queryInputEl.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          gf.askQuestion(dom.queryInputEl.value);
          dom.queryInputEl.value = "";
        }
      });
    }

    document.getElementById("gfExportBtn")?.addEventListener("click", () => {
      gf.exportReport();
    });

    document.getElementById("gfZoomIn")?.addEventListener("click", () => state.map?.zoomIn({ duration: 200 }));
    document.getElementById("gfZoomOut")?.addEventListener("click", () => state.map?.zoomOut({ duration: 200 }));
    document.getElementById("gfZoomReset")?.addEventListener("click", () => {
      gf.fitMapBounds(state.cityLayersData?.vector_layer?.bounds_wgs84);
    });
    document.getElementById("gfAllCitiesBtn")?.addEventListener("click", () => gf.switchPanelTab("layers"));

    window.addEventListener("resize", () => {
      if (document.getElementById("page-gfframe")?.classList.contains("active")) {
        gf.refreshMapSize();
      }
    });

    wirePanelResize();
  }

  function activate() {
    const { state } = gf;
    gf.resolveAppMode();

    if (state.appMode === "project" && (!state.projectId || !window.AppShell?.hasReadyProject?.())) {
      window.AppShell?.showPage("ask");
      return;
    }

    gf.updateModeChrome();
    state.dataLoaded = false;
    state.tractGeojsonCache = { token: null, data: null };
    state.cityLayersData = null;
    state.activeCityIndex = 0;

    gf.renderChat();
    if (!state.uiWired) {
      wireControls();
      state.uiWired = true;
    }

    gf.afterLayout(async () => {
      await gf.ensureAdapterModels();

      if (state.appMode === "demo") {
        try {
          await gf.ensureDemoCities();
        } catch {
          window.AppShell?.showPage("ask");
          return;
        }
      }

      gf.refreshDemoCityUI();

      if (state.appMode === "project") {
        try {
          await gf.loadProject();
        } catch {
          window.AppShell?.showPage("ask");
          return;
        }
        gf.refreshDemoCityUI();
      } else {
        gf.startDemoPortfolioWarm();
      }

      if (!state.dataLoaded) {
        state.dataLoaded = true;
        const cities = gf.getCities();
        if (cities.length) await selectCity(state.activeCityIndex);
        return;
      }
      gf.refreshMapSize();
      await gf.renderActiveMapLayer();
    });
  }

  Object.assign(gf, {
    updateStats,
    fetchCityLayers,
    selectCity,
    buildCityList,
    buildBarChart,
    buildCityGrid,
    wirePanelResize,
    wireControls,
    activate,
  });

  gf.init = activate;
  window.GfFrame = gf;
})();
