/**
 * Ask page: multi-city LST project uploads → Heat & Equity dashboard.
 */
(function () {
  const PAGE_META = {
    ask: { eyebrow: "Step 1", title: "Upload & build project" },
    gfframe: { eyebrow: "Heat & Equity", title: "Urban Heat & Equity" },
  };

  const RASTER_RE = /\.(tif|tiff|geotiff|gtiff)$/i;

  const workspaceEl = document.getElementById("workspace");
  const navButtons = document.querySelectorAll(".nav-btn");
  const pages = document.querySelectorAll(".page");
  const pageEyebrow = document.getElementById("pageEyebrow");
  const pageTitle = document.getElementById("pageTitle");
  const statusEl = document.getElementById("status");
  const navGfframe = document.getElementById("navGfframe");

  const askCityCustom = document.getElementById("askCityCustom");
  const askProjectFilesInput = document.getElementById("askProjectFiles");
  const askProjectFileDrop = document.getElementById("askProjectFileDrop");
  const askProjectFileBrowse = document.getElementById("askProjectFileBrowse");
  const askProjectFileList = document.getElementById("askProjectFileList");
  const askProjectFileClear = document.getElementById("askProjectFileClear");
  const askProjectFileHint = document.getElementById("askProjectFileHint");
  const askAddCityBtn = document.getElementById("askAddCity");
  const askRunCityLstBtn = document.getElementById("askRunCityLst");
  const askProjectStatus = document.getElementById("askProjectStatus");
  const askProjectCityList = document.getElementById("askProjectCityList");
  const askNewProjectBtn = document.getElementById("askNewProject");

  let projectId = localStorage.getItem("gf_project_id") || null;
  let projectData = null;
  let projectCityFiles = [];

  function isRaster(file) {
    return RASTER_RE.test(file.name);
  }

  function fileKey(file) {
    return `${file.name}|${file.size}|${file.lastModified}`;
  }

  function parseError(payload) {
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || item).join("; ");
    }
    return "Request failed";
  }

  function setStatus(message, type) {
    statusEl.textContent = message || "";
    statusEl.classList.remove("is-ok", "is-error");
    if (type) statusEl.classList.add(type);
  }

  function hasReadyProject() {
    return Boolean(projectId && projectData && (projectData.ready_count || 0) > 0);
  }

  function updateNavVisibility() {
    if (!navGfframe) return;
    navGfframe.hidden = !hasReadyProject();
  }

  function showPage(name, gfMode) {
    if (name === "gfframe") {
      const mode = gfMode || localStorage.getItem("gf_mode") || "demo";
      if (mode === "project" && !hasReadyProject()) {
        setStatus("Upload LST for at least one city on Ask first", "is-error");
        name = "ask";
      } else {
        localStorage.setItem("gf_mode", mode);
      }
    }

    if (name !== "gfframe") {
      const meta = PAGE_META[name] || PAGE_META.ask;
      pageEyebrow.textContent = meta.eyebrow;
      pageTitle.textContent = meta.title;
    } else {
      const isDemo = (localStorage.getItem("gf_mode") || "demo") === "demo";
      pageEyebrow.textContent = isDemo ? "Preview" : "Your project";
      pageTitle.textContent = isDemo ? "11-city demo" : "Urban Heat & Equity";
    }

    navButtons.forEach((btn) => {
      const active =
        btn.dataset.page === name &&
        (name !== "gfframe" || btn.dataset.gfMode === localStorage.getItem("gf_mode"));
      btn.classList.toggle("active", active);
    });
    pages.forEach((page) => {
      page.classList.toggle("active", page.id === `page-${name}`);
    });

    if (workspaceEl) {
      workspaceEl.classList.toggle("is-gfframe", name === "gfframe");
    }

    if (name === "gfframe") {
      localStorage.setItem("gf_last_page", "gfframe");
      if (window.GfFrame) window.GfFrame.activate();
    } else {
      localStorage.setItem("gf_last_page", "ask");
    }
  }

  window.AppShell = { showPage, hasReadyProject };

  function resolveCityAddress() {
    const custom = (askCityCustom?.value || "").trim();
    if (custom) return custom;
    return "";
  }

  function updateProjectFileUI() {
    if (!askProjectFileList) return;
    if (!projectCityFiles.length) {
      askProjectFileList.hidden = true;
      askProjectFileList.innerHTML = "";
      askProjectFileClear?.classList.add("hidden");
      if (askProjectFileHint) askProjectFileHint.textContent = "ST_B10, SR_B4, SR_B5";
      return;
    }
    askProjectFileList.hidden = false;
    askProjectFileClear?.classList.remove("hidden");
    askProjectFileList.innerHTML = "";
    projectCityFiles.forEach((file, index) => {
      const item = document.createElement("li");
      item.className = "file-list-item";
      item.textContent = file.name;
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "file-remove-btn";
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", () => {
        projectCityFiles.splice(index, 1);
        updateProjectFileUI();
      });
      item.appendChild(removeBtn);
      askProjectFileList.appendChild(item);
    });
    if (askProjectFileHint) {
      askProjectFileHint.textContent = `${projectCityFiles.length} file(s) selected`;
    }
  }

  function addProjectFiles(incoming) {
    const valid = incoming.filter(isRaster);
    if (!valid.length) {
      setStatus("Include at least one GeoTIFF (.tif)", "is-error");
      return;
    }
    const existing = new Set(projectCityFiles.map((f) => fileKey(f)));
    valid.forEach((file) => {
      const key = fileKey(file);
      if (!existing.has(key)) {
        projectCityFiles.push(file);
        existing.add(key);
      }
    });
    if (askProjectFilesInput) askProjectFilesInput.value = "";
    updateProjectFileUI();
  }

  async function ensureAskProject() {
    if (projectId) {
      const response = await fetch(`/api/projects/${projectId}`);
      if (response.ok) {
        projectData = await response.json();
        return projectData;
      }
      projectId = null;
      localStorage.removeItem("gf_project_id");
    }
    const response = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "LST City Project" }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(payload) || "Could not create project.");
    projectData = payload;
    projectId = payload.id;
    localStorage.setItem("gf_project_id", projectId);
    return projectData;
  }

  function renderAskPortfolio() {
    if (!askProjectCityList) return;
    askProjectCityList.innerHTML = "";
    const cities = projectData?.cities ? Object.entries(projectData.cities) : [];

    if (!cities.length) {
      if (askProjectStatus) {
        askProjectStatus.textContent = "No cities yet. Pick a city, upload bands, and run LST.";
      }
      updateNavVisibility();
      return;
    }

    const readyCount = projectData.ready_count || 0;
    if (askProjectStatus) {
      askProjectStatus.textContent =
        readyCount > 0
          ? `${readyCount} of ${cities.length} cities ready — dashboard unlocked. Add more cities anytime via Back to Ask.`
          : `${cities.length} city(ies) registered — run LST to open the dashboard.`;
    }

    cities.forEach(([key, entry]) => {
      const li = document.createElement("li");
      li.className = "ask-project-city-item";
      const name = document.createElement("strong");
      name.textContent = entry.name || entry.address || key;
      const meta = document.createElement("div");
      meta.className = "ask-project-city-meta";
      const status = document.createElement("span");
      status.className = `ask-project-status ask-project-status-${entry.status || "pending"}`;
      status.textContent = entry.status || "pending";
      meta.appendChild(status);
      if (entry.lst_stats?.mean_C != null) {
        const lst = document.createElement("span");
        lst.className = "ask-project-lst";
        lst.textContent = `${entry.lst_stats.mean_C}°C mean`;
        meta.appendChild(lst);
      }
      li.appendChild(name);
      li.appendChild(meta);
      askProjectCityList.appendChild(li);
    });

    updateNavVisibility();
  }

  async function loadAskProjectState() {
    if (!projectId) {
      projectData = null;
      renderAskPortfolio();
      return;
    }
    try {
      const response = await fetch(`/api/projects/${projectId}`);
      if (!response.ok) throw new Error("Project not found");
      projectData = await response.json();
      renderAskPortfolio();
    } catch {
      projectId = null;
      localStorage.removeItem("gf_project_id");
      projectData = null;
      renderAskPortfolio();
    }
  }

  async function registerAskCity(address) {
    await ensureAskProject();
    const response = await fetch(`/api/projects/${projectId}/cities`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(payload) || "Could not register city.");
    projectData = payload;
    return payload;
  }

  function cityKeyForAddress(address) {
    if (!projectData?.cities) return null;
    for (const [key, entry] of Object.entries(projectData.cities)) {
      if ((entry.address || "").toLowerCase() === address.toLowerCase()) return key;
      if ((entry.name || "").toLowerCase() === address.toLowerCase()) return key;
    }
    return null;
  }

  function openGfDashboard() {
    if (!hasReadyProject()) {
      setStatus("Upload LST for at least one city first", "is-error");
      return;
    }
    localStorage.setItem("gf_project_id", projectId);
    localStorage.setItem("gf_mode", "project");
    showPage("gfframe");
  }

  async function addCityToProject() {
    const address = resolveCityAddress();
    if (!address) {
      setStatus("Enter a city address", "is-error");
      return;
    }

    askAddCityBtn.disabled = true;
    setStatus(`Adding ${address} to project…`, "");

    try {
      await registerAskCity(address);
      renderAskPortfolio();
      setStatus(`${address} added. Upload Landsat bands, then run LST.`, "is-ok");
    } catch (error) {
      setStatus(error.message || "Could not add city", "is-error");
    } finally {
      askAddCityBtn.disabled = false;
    }
  }

  async function runAskCityLst() {
    const address = resolveCityAddress();
    if (!address) {
      setStatus("Enter a city address", "is-error");
      return;
    }
    if (!projectCityFiles.length) {
      setStatus("Add Landsat GeoTIFFs for this city", "is-error");
      return;
    }

    let cityKey = cityKeyForAddress(address);
    if (!cityKey) {
      setStatus("Add the city to your project first", "is-error");
      return;
    }

    askRunCityLstBtn.disabled = true;
    setStatus(`Running LST for ${address}…`, "");

    try {
      const form = new FormData();
      projectCityFiles.forEach((file) => form.append("files", file));
      const response = await fetch(`/api/projects/${projectId}/cities/${cityKey}/lst`, {
        method: "POST",
        body: form,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(parseError(payload) || "LST upload failed.");

      projectData = payload;
      projectCityFiles = [];
      updateProjectFileUI();
      if (askCityCustom) askCityCustom.value = "";
      renderAskPortfolio();

      setStatus(`${address} LST complete — opening dashboard…`, "is-ok");
      openGfDashboard();
    } catch (error) {
      setStatus(error.message || "LST failed", "is-error");
      await loadAskProjectState();
    } finally {
      askRunCityLstBtn.disabled = false;
    }
  }

  async function resetAskProject() {
    projectId = null;
    projectData = null;
    projectCityFiles = [];
    localStorage.removeItem("gf_project_id");
    localStorage.removeItem("gf_mode");
    updateProjectFileUI();
    renderAskPortfolio();
    setStatus("New project started — add a city and upload LST bands.", "is-ok");
    showPage("ask");
  }

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.page, btn.dataset.gfMode));
  });

  document.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.goto));
  });

  askProjectFileBrowse?.addEventListener("click", (event) => {
    event.stopPropagation();
    askProjectFilesInput?.click();
  });

  askProjectFilesInput?.addEventListener("change", () => {
    const picked = askProjectFilesInput.files ? Array.from(askProjectFilesInput.files) : [];
    if (picked.length) addProjectFiles(picked);
  });

  askProjectFileClear?.addEventListener("click", () => {
    projectCityFiles = [];
    if (askProjectFilesInput) askProjectFilesInput.value = "";
    updateProjectFileUI();
  });

  askProjectFileDrop?.addEventListener("dragover", (event) => {
    event.preventDefault();
    askProjectFileDrop.classList.add("is-dragover");
  });

  askProjectFileDrop?.addEventListener("dragleave", () => {
    askProjectFileDrop.classList.remove("is-dragover");
  });

  askProjectFileDrop?.addEventListener("drop", (event) => {
    event.preventDefault();
    askProjectFileDrop.classList.remove("is-dragover");
    const dropped = event.dataTransfer.files ? Array.from(event.dataTransfer.files) : [];
    if (dropped.length) addProjectFiles(dropped);
  });

  askAddCityBtn?.addEventListener("click", () => addCityToProject());
  askRunCityLstBtn?.addEventListener("click", () => runAskCityLst());
  askNewProjectBtn?.addEventListener("click", () => resetAskProject());

  loadAskProjectState().then(() => {
    const lastPage = localStorage.getItem("gf_last_page");
    const lastMode = localStorage.getItem("gf_mode") || "demo";
    if (lastPage === "gfframe" && (lastMode === "demo" || hasReadyProject())) {
      showPage("gfframe", lastMode);
    } else {
      showPage("ask");
    }
  });
})();
