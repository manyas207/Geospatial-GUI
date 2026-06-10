/**
 * Geospatial dashboard UI: file upload → POST /api/query → map + stats + follow-up chat.
 * Map pan/zoom is vanilla CSS transform (no Leaflet); artifact previews come from the API.
 */
(function () {
  const PAGE_META = {
    ask: { eyebrow: "Step 1", title: "Ask a question" },
    dashboard: { eyebrow: "Step 2", title: "Dashboard & follow-up" },
    gfframe: { eyebrow: "GUI Frame", title: "Urban Heat & Equity" },
  };

  const workspaceEl = document.getElementById("workspace");

  const navButtons = document.querySelectorAll(".nav-btn");
  const pages = document.querySelectorAll(".page");
  const pageEyebrow = document.getElementById("pageEyebrow");
  const pageTitle = document.getElementById("pageTitle");
  const statusEl = document.getElementById("status");

  const rasterInput = document.getElementById("raster");
  const fileDrop = document.getElementById("fileDrop");
  const fileBrowseBtn = document.getElementById("fileBrowseBtn");
  const fileHint = document.getElementById("fileHint");
  const fileList = document.getElementById("fileList");
  const fileClearBtn = document.getElementById("fileClearBtn");

  const RASTER_RE = /\.(tif|tiff|geotiff|gtiff)$/i;
  const SHAPEFILE_RE = /\.(shp|shx|dbf|prj|cpg|sbn|sbx)$/i;
  // Hide file paths and internal keys from metric cards (mirrors backend INTERNAL_STAT_KEYS).
  const HIDDEN_STAT_KEY_RE = /(gpkg|tif|geotiff|upload_dir|primary_raster|file_count)$/i;

  function isHiddenStatKey(key) {
    return HIDDEN_STAT_KEY_RE.test(key);
  }
  let selectedFiles = [];
  const queryInput = document.getElementById("queryInput");
  const runQueryBtn = document.getElementById("runQuery");

  const dashboardEmpty = document.getElementById("dashboardEmpty");
  const dashboardContent = document.getElementById("dashboardContent");
  const dashModel = document.getElementById("dashModel");
  const dashSummary = document.getElementById("dashSummary");
  const dashRaster = document.getElementById("dashRaster");
  const dashStats = document.getElementById("dashStats");
  const dashLogs = document.getElementById("dashLogs");
  const mapViewport = document.getElementById("mapViewport");
  const mapImage = document.getElementById("mapImage");
  const mapEmpty = document.getElementById("mapEmpty");
  const mapCaption = document.getElementById("mapCaption");
  const mapLayerSelect = document.getElementById("mapLayerSelect");
  const mapDownloadBtn = document.getElementById("mapDownloadBtn");
  const mapZoomIn = document.getElementById("mapZoomIn");
  const mapZoomOut = document.getElementById("mapZoomOut");
  const mapZoomReset = document.getElementById("mapZoomReset");
  const downloadList = document.getElementById("downloadList");
  const chatThread = document.getElementById("chatThread");
  const followupForm = document.getElementById("followupForm");
  const followupInput = document.getElementById("followupInput");
  const followupBtn = document.getElementById("followupBtn");
  const referenceLayersHint = document.getElementById("referenceLayersHint");
  const referenceLayerList = document.getElementById("referenceLayerList");

  let dashboard = null;
  let chatMessages = [];
  let mapLayers = [];
  let activeMapLayer = 0;
  let allReferenceLayers = [];
  let extraMapLayerIds = new Set();

  // Pan/zoom state: transform origin is top-left of the viewport.
  const mapView = {
    scale: 1,
    x: 0,
    y: 0,
    dragging: false,
    pointerId: null,
    lastX: 0,
    lastY: 0,
  };

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function applyMapTransform() {
    mapImage.style.transform = `translate(${mapView.x}px, ${mapView.y}px) scale(${mapView.scale})`;
  }

  function fitMapToViewport() {
    if (!mapImage.naturalWidth || !mapImage.naturalHeight) return;

    const vw = mapViewport.clientWidth;
    const vh = mapViewport.clientHeight;
    const iw = mapImage.naturalWidth;
    const ih = mapImage.naturalHeight;
    const fitScale = Math.min(vw / iw, vh / ih) * 0.96;

    mapView.scale = clamp(fitScale, 0.05, 8);
    mapView.x = (vw - iw * mapView.scale) / 2;
    mapView.y = (vh - ih * mapView.scale) / 2;
    applyMapTransform();
  }

  // Zoom toward the pointer by adjusting translate so the point under the cursor stays fixed.
  function zoomMapAt(clientX, clientY, factor) {
    const rect = mapViewport.getBoundingClientRect();
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    const nextScale = clamp(mapView.scale * factor, 0.1, 10);

    mapView.x = px - ((px - mapView.x) * nextScale) / mapView.scale;
    mapView.y = py - ((py - mapView.y) * nextScale) / mapView.scale;
    mapView.scale = nextScale;
    applyMapTransform();
  }

  function setActiveMapLayer(index) {
    if (!mapLayers.length) {
      mapImage.classList.add("hidden");
      mapEmpty.classList.remove("hidden");
      mapCaption.textContent = "";
      mapDownloadBtn.classList.add("hidden");
      mapLayerSelect.hidden = true;
      return;
    }

    activeMapLayer = clamp(index, 0, mapLayers.length - 1);
    const layer = mapLayers[activeMapLayer];

    mapEmpty.classList.add("hidden");
    mapImage.classList.remove("hidden");
    mapImage.onload = () => fitMapToViewport();
    mapImage.src = layer.preview_url;
    if (mapImage.complete) fitMapToViewport();

    mapCaption.textContent = `${layer.label} · ${layer.filename}`;
    mapLayerSelect.hidden = mapLayers.length < 2;
    mapLayerSelect.value = String(activeMapLayer);

    if (layer.download_url) {
      mapDownloadBtn.href = layer.download_url;
      mapDownloadBtn.download = layer.filename;
      mapDownloadBtn.textContent = `Download ${layer.kind === "vector" ? "file" : "GeoTIFF"}`;
      mapDownloadBtn.classList.remove("hidden");
    } else {
      mapDownloadBtn.classList.add("hidden");
    }
  }

  function layerMapKey(layer) {
    return layer.id || `${layer.label}|${layer.filename}`;
  }

  function collectMapLayers() {
    const layers = [];
    const seen = new Set();

    function push(layer) {
      if (!layer || !layer.preview_url) return;
      const key = layerMapKey(layer);
      if (seen.has(key)) return;
      seen.add(key);
      layers.push(layer);
    }

    if (dashboard) {
      (dashboard.artifacts || []).forEach(push);
      (dashboard.reference_layers || []).forEach(push);
    }

    allReferenceLayers.forEach((layer) => {
      if (extraMapLayerIds.has(layer.id)) push(layer);
    });

    return layers;
  }

  function renderMapViewer() {
    mapLayers = collectMapLayers();
    mapLayerSelect.innerHTML = "";

    mapLayers.forEach((layer, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = layer.label;
      mapLayerSelect.appendChild(option);
    });

    if (!dashboardContent.classList.contains("hidden") && mapLayers.length) {
      setActiveMapLayer(0);
    } else if (!mapLayers.length) {
      setActiveMapLayer(0);
    }
  }

  function formatReferenceStats(stats) {
    if (!stats || typeof stats !== "object") return "";
    const parts = [];
    if (stats.mean !== undefined) parts.push(`mean ${stats.mean}`);
    if (stats.min !== undefined && stats.max !== undefined) {
      parts.push(`range ${stats.min}–${stats.max}`);
    }
    if (stats.valid_pixels !== undefined) {
      parts.push(`${stats.valid_pixels.toLocaleString()} px`);
    }
    return parts.join(" · ");
  }

  function showLayerOnMap(layerId) {
    extraMapLayerIds.add(layerId);
    if (dashboardContent.classList.contains("hidden")) {
      dashboardEmpty.classList.add("hidden");
      dashboardContent.classList.remove("hidden");
      if (!dashboard) {
        dashboard = {
          model: "reference",
          summary: "Browsing reference layers from your data folder.",
          stats: {},
          logs: "",
          raster: "",
          artifacts: [],
          reference_layers: [],
        };
        dashModel.textContent = "REF";
        dashModel.className = "model-badge model-badge-reference";
        dashSummary.textContent = dashboard.summary;
        dashRaster.textContent = "";
        dashStats.innerHTML = "";
        dashLogs.textContent = "";
        chatThread.innerHTML = "";
      }
    }
    renderMapViewer();
    const index = mapLayers.findIndex((layer) => layer.id === layerId);
    if (index >= 0) setActiveMapLayer(index);
    showPage("dashboard");
  }

  function renderReferenceLayers() {
    referenceLayerList.innerHTML = "";

    if (!allReferenceLayers.length) {
      referenceLayersHint.textContent =
        "No reference layers found. Set REFERENCE_DATA_DIR to your gridded population folder.";
      return;
    }

    referenceLayersHint.textContent = `${allReferenceLayers.length} layer${
      allReferenceLayers.length === 1 ? "" : "s"
    } available — view on the map or download the GeoTIFF.`;

    allReferenceLayers.forEach((layer) => {
      const li = document.createElement("li");
      li.className = "reference-layer-item";

      const icon = document.createElement("span");
      icon.className = "download-icon";
      icon.textContent = layer.category === "population" ? "POP" : "REF";

      const info = document.createElement("div");
      info.className = "download-info";

      const name = document.createElement("strong");
      name.textContent = layer.label;

      const file = document.createElement("span");
      file.className = "muted";
      file.textContent = layer.filename;

      const stats = document.createElement("span");
      stats.className = "muted reference-stats";
      stats.textContent = formatReferenceStats(layer.stats);

      info.appendChild(name);
      info.appendChild(file);
      if (stats.textContent) info.appendChild(stats);

      const actions = document.createElement("div");
      actions.className = "reference-actions";

      const viewBtn = document.createElement("button");
      viewBtn.type = "button";
      viewBtn.className = "download-btn";
      viewBtn.textContent = "View on map";
      viewBtn.addEventListener("click", () => showLayerOnMap(layer.id));

      actions.appendChild(viewBtn);

      if (layer.download_url) {
        const link = document.createElement("a");
        link.className = "download-btn";
        link.href = layer.download_url;
        link.download = layer.filename;
        link.textContent = "Download";
        actions.appendChild(link);
      }

      li.appendChild(icon);
      li.appendChild(info);
      li.appendChild(actions);
      referenceLayerList.appendChild(li);
    });
  }

  async function loadReferenceLayers() {
    try {
      const response = await fetch("/api/reference-layers");
      const payload = await response.json().catch(() => []);
      if (!response.ok) {
        referenceLayersHint.textContent = "Could not load reference layers.";
        return;
      }
      allReferenceLayers = Array.isArray(payload) ? payload : [];
      renderReferenceLayers();
    } catch {
      referenceLayersHint.textContent = "Could not load reference layers.";
    }
  }

  function renderDownloads() {
    const artifacts = dashboard.artifacts || [];
    const withDownload = artifacts.filter((item) => item.download_url);

    downloadList.innerHTML = "";
    if (!withDownload.length) {
      const empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "No output files generated.";
      downloadList.appendChild(empty);
      return;
    }

    withDownload.forEach((item) => {
      const li = document.createElement("li");
      li.className = "download-item";

      const icon = document.createElement("span");
      icon.className = "download-icon";
      icon.textContent = item.kind === "vector" ? "VEC" : "TIF";

      const info = document.createElement("div");
      info.className = "download-info";

      const name = document.createElement("strong");
      name.textContent = item.label;

      const file = document.createElement("span");
      file.className = "muted";
      file.textContent = item.filename;

      const link = document.createElement("a");
      link.className = "download-btn";
      link.href = item.download_url;
      link.download = item.filename;
      link.textContent = "Download";

      info.appendChild(name);
      info.appendChild(file);
      li.appendChild(icon);
      li.appendChild(info);
      li.appendChild(link);
      downloadList.appendChild(li);
    });
  }

  function setStatus(message, type) {
    statusEl.textContent = message || "";
    statusEl.classList.remove("is-ok", "is-error");
    if (type) statusEl.classList.add(type);
  }

  function showPage(name) {
    const meta = PAGE_META[name] || PAGE_META.ask;

    navButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.page === name);
    });
    pages.forEach((page) => {
      page.classList.toggle("active", page.id === `page-${name}`);
    });

    pageEyebrow.textContent = meta.eyebrow;
    pageTitle.textContent = meta.title;

    if (workspaceEl) {
      workspaceEl.classList.toggle("is-gfframe", name === "gfframe");
    }
    if (name === "gfframe" && window.GfFrame) {
      window.GfFrame.activate();
    }
  }

  function formatStatLabel(key) {
    return key.replace(/_/g, " ");
  }

  function formatStatValue(value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function formatDashboardSummary(data) {
    const lines = [`Analysis complete (${data.model.toUpperCase()}).`, data.summary];
    const stats = data.stats || {};
    const metricParts = Object.entries(stats)
      .filter(([key]) => !isHiddenStatKey(key))
      .slice(0, 6)
      .map(([key, value]) => `${formatStatLabel(key)}: ${formatStatValue(value)}`);
    if (metricParts.length) {
      lines.push(metricParts.join(" · "));
    }
    return lines.join("\n");
  }

  function renderDashboard() {
    if (!dashboard) {
      dashboardEmpty.classList.remove("hidden");
      dashboardContent.classList.add("hidden");
      return;
    }

    dashboardEmpty.classList.add("hidden");
    dashboardContent.classList.remove("hidden");

    dashModel.textContent = dashboard.model.toUpperCase();
    dashModel.className = `model-badge model-badge-${dashboard.model}`;
    dashSummary.textContent = dashboard.summary;
    dashRaster.textContent = dashboard.raster ? `Raster: ${dashboard.raster}` : "";

    renderMapViewer();
    renderDownloads();

    dashStats.innerHTML = "";
    Object.entries(dashboard.stats || {}).forEach(([key, value]) => {
      if (isHiddenStatKey(key)) return;
      const dt = document.createElement("dt");
      dt.textContent = formatStatLabel(key);
      const dd = document.createElement("dd");
      dd.textContent = formatStatValue(value);
      dashStats.appendChild(dt);
      dashStats.appendChild(dd);
    });

    dashLogs.textContent = dashboard.logs || "";
    renderChat();
  }

  function renderChat() {
    chatThread.innerHTML = "";
    chatMessages.forEach((msg) => {
      const bubble = document.createElement("div");
      bubble.className = `chat-bubble chat-bubble-${msg.role}`;
      const label = document.createElement("span");
      label.className = "chat-role";
      label.textContent = msg.role === "user" ? "You" : "Assistant";
      const text = document.createElement("p");
      text.textContent = msg.text;
      bubble.appendChild(label);
      bubble.appendChild(text);
      chatThread.appendChild(bubble);
    });
    chatThread.scrollTop = chatThread.scrollHeight;
  }

  function addMessage(role, text) {
    chatMessages.push({ role, text });
    renderChat();
  }

  function parseError(payload) {
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || item).join("; ");
    }
    return "Request failed";
  }

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.page));
  });

  document.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.goto));
  });

  // Dedupe incremental "Add files" picks (same name/size/mtime = same file).
  function fileKey(file) {
    return `${file.name}|${file.size}|${file.lastModified}`;
  }

  function isRaster(file) {
    return RASTER_RE.test(file.name);
  }

  function isShapefilePart(file) {
    return SHAPEFILE_RE.test(file.name);
  }

  function isAllowedUpload(file) {
    return isRaster(file) || isShapefilePart(file);
  }

  function getSelectedFiles() {
    return selectedFiles.slice();
  }

  function openFilePicker() {
    rasterInput.click();
  }

  function updateFileUI() {
    const count = selectedFiles.length;

    fileDrop.classList.toggle("has-file", count > 0);
    fileList.hidden = count === 0;
    fileClearBtn.classList.toggle("hidden", count === 0);

    if (count === 0) {
      fileHint.textContent = "or use Add files — you can add more anytime";
      fileList.innerHTML = "";
      setStatus("");
      return;
    }

    fileHint.textContent = `${count} file${count === 1 ? "" : "s"} ready — click Add files to attach more`;
    setStatus(`${count} file${count === 1 ? "" : "s"} ready`, "is-ok");

    fileList.innerHTML = "";
    selectedFiles.forEach((file) => {
      const item = document.createElement("li");
      item.className = "file-list-item";

      const name = document.createElement("span");
      name.className = "file-list-name";
      name.textContent = file.name;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "file-remove";
      removeBtn.setAttribute("aria-label", `Remove ${file.name}`);
      removeBtn.textContent = "×";
      removeBtn.addEventListener("click", () => {
        const key = fileKey(file);
        selectedFiles = selectedFiles.filter((entry) => fileKey(entry) !== key);
        updateFileUI();
      });

      item.appendChild(name);
      item.appendChild(removeBtn);
      fileList.appendChild(item);
    });
  }

  function addFiles(incoming) {
    const valid = incoming.filter(isAllowedUpload);
    if (!valid.length) {
      setStatus("Use GeoTIFF (.tif) and/or shapefile parts (.shp, .shx, .dbf)", "is-error");
      return;
    }

    const existing = new Set(selectedFiles.map(fileKey));
    let added = 0;

    valid.forEach((file) => {
      const key = fileKey(file);
      if (!existing.has(key)) {
        selectedFiles.push(file);
        existing.add(key);
        added += 1;
      }
    });

    rasterInput.value = "";
    updateFileUI();

    if (added === 0 && valid.length > 0) {
      setStatus("Those files are already added", "is-error");
    }
  }

  fileBrowseBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    openFilePicker();
  });

  rasterInput.addEventListener("change", () => {
    const picked = rasterInput.files ? Array.from(rasterInput.files) : [];
    if (picked.length) addFiles(picked);
  });

  fileClearBtn.addEventListener("click", () => {
    selectedFiles = [];
    rasterInput.value = "";
    updateFileUI();
  });

  fileDrop.addEventListener("dragover", (event) => {
    event.preventDefault();
    fileDrop.classList.add("is-dragover");
  });

  fileDrop.addEventListener("dragleave", () => {
    fileDrop.classList.remove("is-dragover");
  });

  fileDrop.addEventListener("drop", (event) => {
    event.preventDefault();
    fileDrop.classList.remove("is-dragover");
    const dropped = event.dataTransfer.files
      ? Array.from(event.dataTransfer.files)
      : [];
    if (dropped.length) addFiles(dropped);
  });

  // --- Main analysis: multipart upload + NL question → dashboard ---
  runQueryBtn.addEventListener("click", async () => {
    const files = getSelectedFiles();
    const question = (queryInput.value || "").trim();

    if (!files.length) {
      setStatus("Select at least one file", "is-error");
      return;
    }
    if (!files.some(isRaster)) {
      setStatus("Include at least one GeoTIFF (.tif)", "is-error");
      return;
    }
    if (!question) {
      setStatus("Enter a question", "is-error");
      return;
    }

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    formData.append("question", question);

    runQueryBtn.disabled = true;
    setStatus("Running analysis…", "");

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        body: formData,
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        setStatus(parseError(payload), "is-error");
        return;
      }

      dashboard = {
        model: payload.model,
        summary: payload.summary,
        stats: payload.stats || {},
        logs: payload.logs || "",
        raster: files.map((f) => f.name).join(", "),
        artifacts: payload.artifacts || [],
        reference_layers: payload.reference_layers || [],
      };

      (payload.reference_layers || []).forEach((layer) => {
        if (layer.id) extraMapLayerIds.add(layer.id);
      });

      chatMessages = [
        { role: "user", text: question },
        { role: "assistant", text: formatDashboardSummary(payload) },
      ];

      renderDashboard();
      setStatus("Dashboard ready — ask follow-up questions", "is-ok");
      showPage("dashboard");
      followupInput.focus();
    } catch (error) {
      setStatus(error.message || "Network error", "is-error");
    } finally {
      runQueryBtn.disabled = false;
    }
  });

  // --- Follow-up chat: sends full dashboard context to POST /api/followup ---
  followupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!dashboard) {
      setStatus("Run an analysis first", "is-error");
      showPage("ask");
      return;
    }

    const question = (followupInput.value || "").trim();
    if (!question) return;

    addMessage("user", question);
    followupInput.value = "";
    followupBtn.disabled = true;
    setStatus("Thinking…", "");

    try {
      const response = await fetch("/api/followup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, context: dashboard }),
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        addMessage("assistant", parseError(payload));
        setStatus("Follow-up failed", "is-error");
        return;
      }

      addMessage("assistant", payload.answer || "No answer returned.");
      setStatus("", "is-ok");
    } catch (error) {
      addMessage("assistant", error.message || "Network error");
      setStatus("Network error", "is-error");
    } finally {
      followupBtn.disabled = false;
      followupInput.focus();
    }
  });

  mapLayerSelect.addEventListener("change", () => {
    setActiveMapLayer(Number(mapLayerSelect.value) || 0);
  });

  mapZoomIn.addEventListener("click", () => {
    const rect = mapViewport.getBoundingClientRect();
    zoomMapAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1.2);
  });

  mapZoomOut.addEventListener("click", () => {
    const rect = mapViewport.getBoundingClientRect();
    zoomMapAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1 / 1.2);
  });

  mapZoomReset.addEventListener("click", () => fitMapToViewport());

  // --- Map interactions: wheel zoom, pointer drag pan ---
  mapViewport.addEventListener(
    "wheel",
    (event) => {
      if (mapImage.classList.contains("hidden")) return;
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      zoomMapAt(event.clientX, event.clientY, factor);
    },
    { passive: false }
  );

  mapViewport.addEventListener("pointerdown", (event) => {
    if (mapImage.classList.contains("hidden")) return;
    mapView.dragging = true;
    mapView.pointerId = event.pointerId;
    mapView.lastX = event.clientX;
    mapView.lastY = event.clientY;
    mapViewport.classList.add("is-dragging");
    mapViewport.setPointerCapture(event.pointerId);
  });

  mapViewport.addEventListener("pointermove", (event) => {
    if (!mapView.dragging || event.pointerId !== mapView.pointerId) return;
    mapView.x += event.clientX - mapView.lastX;
    mapView.y += event.clientY - mapView.lastY;
    mapView.lastX = event.clientX;
    mapView.lastY = event.clientY;
    applyMapTransform();
  });

  function endMapDrag(event) {
    if (!mapView.dragging || event.pointerId !== mapView.pointerId) return;
    mapView.dragging = false;
    mapView.pointerId = null;
    mapViewport.classList.remove("is-dragging");
    if (mapViewport.hasPointerCapture(event.pointerId)) {
      mapViewport.releasePointerCapture(event.pointerId);
    }
  }

  mapViewport.addEventListener("pointerup", endMapDrag);
  mapViewport.addEventListener("pointercancel", endMapDrag);

  window.addEventListener("resize", () => {
    if (!mapImage.classList.contains("hidden")) fitMapToViewport();
  });

  loadReferenceLayers();
  renderDashboard();
  showPage("ask");
})();
