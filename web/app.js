/**
 * Ask page: model selection, multi-city uploads → dashboard.
 */
(function () {
  const adapter = window.DashboardAdapter;
  const PAGE_META = {
    ask: { eyebrow: "Step 1", title: "Upload & build project" },
    gfframe: { eyebrow: "Heat & Equity", title: "Urban Heat & Equity" },
  };

  const workspaceEl = document.getElementById("workspace");
  const navButtons = document.querySelectorAll(".nav-btn");
  const pages = document.querySelectorAll(".page");
  const pageEyebrow = document.getElementById("pageEyebrow");
  const pageTitle = document.getElementById("pageTitle");
  const statusEl = document.getElementById("status");
  const navGfframe = document.getElementById("navGfframe");

  const askModelSelect = document.getElementById("askModelSelect");
  const askModelLockHint = document.getElementById("askModelLockHint");
  const askModelHint = document.getElementById("askModelHint");
  const askCardTitle = document.getElementById("askCardTitle");
  const askCityCustom = document.getElementById("askCityCustom");
  const askCityMonth = document.getElementById("askCityMonth");
  const askCityYear = document.getElementById("askCityYear");
  const askProjectName = document.getElementById("askProjectName");
  const askProjectFilesInput = document.getElementById("askProjectFiles");
  const askProjectFileDrop = document.getElementById("askProjectFileDrop");
  const askProjectFileBrowse = document.getElementById("askProjectFileBrowse");
  const askProjectFileList = document.getElementById("askProjectFileList");
  const askProjectFileClear = document.getElementById("askProjectFileClear");
  const askProjectFileHint = document.getElementById("askProjectFileHint");
  const askProjectFileTitle = document.getElementById("askProjectFileTitle");
  const askAddCityBtn = document.getElementById("askAddCity");
  const askRunCityBtn = document.getElementById("askRunCity");
  const askRunCitySection = document.getElementById("askRunCitySection");
  const askRunCityHint = document.getElementById("askRunCityHint");
  const askRunProgress = document.getElementById("askRunProgress");
  const askRunProgressLabel = document.getElementById("askRunProgressLabel");
  const askRunProgressPct = document.getElementById("askRunProgressPct");
  const askRunProgressBar = document.getElementById("askRunProgressBar");
  const askRunProgressDetail = document.getElementById("askRunProgressDetail");
  const askRunProgressTrack = askRunProgress?.querySelector(".ask-run-progress-track");
  const askProjectStatus = document.getElementById("askProjectStatus");
  const askProjectCityList = document.getElementById("askProjectCityList");
  const askPortfolioEmpty = document.getElementById("askPortfolioEmpty");
  const askPortfolioStats = document.getElementById("askPortfolioStats");
  const askPortfolioCityCount = document.getElementById("askPortfolioCityCount");
  const askPortfolioReadyCount = document.getElementById("askPortfolioReadyCount");
  const askNewProjectBtn = document.getElementById("askNewProject");

  let projectId = localStorage.getItem("gf_project_id") || null;
  let projectData = null;
  let projectCityFiles = [];
  let selectedModelId = localStorage.getItem("gf_model_id") || "lst";
  let modelsLoaded = false;

  const MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];

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
    statusEl.classList.remove("is-ok", "is-error", "is-warn");
    if (type) statusEl.classList.add(type);
  }

  function cityWarning(entry) {
    return adapter?.cityRunWarning(entry) || null;
  }

  function selectedModel() {
    return adapter?.getModelSpec(selectedModelId) || { id: selectedModelId, label: selectedModelId };
  }

  function presentation() {
    return adapter?.getPresentation(selectedModelId) || { runVerb: "analysis", metricUnit: "°C" };
  }

  function projectHasCities() {
    return Boolean(projectData?.cities && Object.keys(projectData.cities).length);
  }

  function syncModelSelectLock() {
    if (!askModelSelect) return;
    const locked = projectHasCities();
    askModelSelect.disabled = locked;
    if (askModelLockHint) askModelLockHint.hidden = !locked;
    if (locked && projectData?.model_id) {
      selectedModelId = projectData.model_id;
      askModelSelect.value = selectedModelId;
    }
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  const MODEL_RUN_STEPS = {
    lst: [
      "Uploading files…",
      "Running LST pipeline…",
      "Loading census tracts…",
      "Joining temperature to tracts…",
      "Finalizing dashboard…",
    ],
    obia: [
      "Uploading files…",
      "Loading raster…",
      "Segmenting image (SLIC)…",
      "Extracting features…",
      "Training classifier…",
      "Joining results to census tracts…",
      "Finalizing dashboard…",
    ],
    default: [
      "Uploading files…",
      "Running analysis…",
      "Preparing dashboard…",
    ],
  };

  function modelRunSteps(modelId) {
    return MODEL_RUN_STEPS[modelId] || MODEL_RUN_STEPS.default;
  }

  function runProgressWorkingDetail(modelId) {
    const pres = adapter?.getPresentation(modelId) || presentation();
    if (pres.runProgressWorking) return pres.runProgressWorking;
    const verb = pres.runVerb || "analysis";
    return `Still working — ${verb} runs can take several minutes for large inputs.`;
  }

  function runProgressStartDetail(modelId) {
    const pres = adapter?.getPresentation(modelId) || presentation();
    if (pres.runProgressStart) return pres.runProgressStart;
    const verb = pres.runVerb || "analysis";
    return `Starting ${verb} analysis on the server…`;
  }

  function showRunProgress(label, percent, detail) {
    if (!askRunProgress) return;
    askRunProgress.hidden = false;
    if (askRunProgressLabel) askRunProgressLabel.textContent = label || "Running analysis…";
    if (askRunProgressPct) {
      askRunProgressPct.textContent = percent != null ? `${Math.round(percent)}%` : "";
    }
    if (askRunProgressBar) {
      askRunProgressBar.classList.toggle("is-indeterminate", percent == null);
      if (percent != null) {
        askRunProgressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
      } else {
        askRunProgressBar.style.width = "";
      }
    }
    if (askRunProgressTrack) {
      askRunProgressTrack.setAttribute(
        "aria-valuenow",
        String(percent != null ? Math.round(percent) : 0)
      );
    }
    if (askRunProgressDetail && detail != null) askRunProgressDetail.textContent = detail;
  }

  function hideRunProgress() {
    if (!askRunProgress) return;
    askRunProgress.hidden = true;
    if (askRunProgressBar) {
      askRunProgressBar.classList.remove("is-indeterminate");
      askRunProgressBar.style.width = "";
    }
    if (askRunProgressDetail) askRunProgressDetail.textContent = "";
  }

  async function pollCityRun(cityKey, modelId) {
    const steps = modelRunSteps(modelId);
    const maxWaitMs = 45 * 60 * 1000;
    const pollMs = 1500;
    const started = Date.now();
    let tick = 0;

    while (Date.now() - started < maxWaitMs) {
      const elapsed = Date.now() - started;
      const response = await fetch(`/api/projects/${projectId}`);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(parseError(payload) || "Could not check project status.");
      }
      projectData = payload;
      renderAskPortfolio();

      const city = projectData?.cities?.[cityKey];
      const status = city?.status;
      const stepIndex = Math.min(steps.length - 1, Math.floor(elapsed / 12000));
      const stepLabel = steps[stepIndex];
      const pseudoPct = Math.min(92, 8 + (elapsed / maxWaitMs) * 84);

      showRunProgress(
        stepLabel,
        status === "processing" ? pseudoPct : status === "ready" ? 100 : pseudoPct,
        status === "processing" ? runProgressWorkingDetail(modelId) : ""
      );
      setStatus(`${stepLabel} (${city?.name || "city"})`, "");

      if (status === "ready" || status === "error") {
        showRunProgress(status === "ready" ? "Complete" : "Failed", status === "ready" ? 100 : 0);
        return city;
      }

      tick += 1;
      await sleep(pollMs);
    }

    throw new Error("Analysis timed out. Check server logs and try again.");
  }

  function syncAskFormActions() {
    const address = resolveCityAddress();
    const period = resolveCityPeriod();
    const cityKey =
      address && validateCityPeriodSilent(period)
        ? cityKeyForEntry(address, period.month, period.year)
        : null;
    const cityInProject = Boolean(cityKey);
    const pres = presentation();

    if (askRunCitySection) askRunCitySection.hidden = !cityInProject;
    if (askRunCityBtn) {
      askRunCityBtn.disabled = !cityInProject || !projectCityFiles.length;
    }
    if (askRunCityHint) {
      if (!cityInProject) {
        askRunCityHint.textContent = "";
      } else if (!projectCityFiles.length) {
        askRunCityHint.textContent = `Upload input files above, then run ${pres.runVerb || "analysis"} for this city.`;
      } else {
        askRunCityHint.textContent = `Ready — click to run ${pres.runVerb || "analysis"} for this city.`;
      }
    }
  }

  function validateCityPeriodSilent(period) {
    const { month, year } = period;
    if (month != null && !year) return false;
    if (month != null && (month < 1 || month > 12)) return false;
    if (year != null && (year < 1984 || year > 2100)) return false;
    return true;
  }

  function updateAskModelUI() {
    const pres = presentation();
    const spec = selectedModel();
    if (askCardTitle) askCardTitle.textContent = pres.cardTitle || `Run ${spec.label}`;
    if (askModelHint) {
      askModelHint.textContent = pres.portfolioHint || spec.description || "";
    }
    if (askRunCityBtn) {
      askRunCityBtn.textContent = `Run ${pres.runVerb || spec.label} for city`;
    }
    if (askProjectFileTitle) {
      askProjectFileTitle.textContent = adapter?.fileDropTitle(selectedModelId) || "Input files";
    }
    const accept = adapter?.inputAccept(selectedModelId) || ".tif,.tiff";
    if (askProjectFilesInput) askProjectFilesInput.accept = accept;
    updateProjectFileUI();
    syncModelSelectLock();
    syncAskFormActions();
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
        setStatus("Run analysis for at least one city on Ask first", "is-error");
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
    return (askCityCustom?.value || "").trim();
  }

  function resolveProjectName() {
    return (askProjectName?.value || "").trim();
  }

  function defaultProjectName() {
    return `${selectedModel().label} City Project`;
  }

  function resolveCityPeriod() {
    const month = Number.parseInt(askCityMonth?.value || "", 10);
    const year = Number.parseInt(askCityYear?.value || "", 10);
    return {
      month: Number.isFinite(month) ? month : null,
      year: Number.isFinite(year) ? year : null,
    };
  }

  function formatPeriod(month, year) {
    if (year && month) {
      const label = MONTH_NAMES[month - 1] || `Month ${month}`;
      return `${label} ${year}`;
    }
    if (year) return String(year);
    return "";
  }

  function periodPhrase(month, year) {
    const label = formatPeriod(month, year);
    return label ? ` (${label})` : "";
  }

  function validateCityPeriod() {
    const { month, year } = resolveCityPeriod();
    if (month != null && !year) {
      setStatus("Enter a year when selecting a month", "is-error");
      return null;
    }
    if (month != null && (month < 1 || month > 12)) {
      setStatus("Month must be between 1 and 12", "is-error");
      return null;
    }
    if (year != null && (year < 1984 || year > 2100)) {
      setStatus("Year must be between 1984 and 2100", "is-error");
      return null;
    }
    return { month, year };
  }

  function initCityPeriodFields() {
    if (askCityMonth && !askCityMonth.options.length) {
      const optional = document.createElement("option");
      optional.value = "";
      optional.textContent = "Optional";
      askCityMonth.appendChild(optional);
      MONTH_NAMES.forEach((label, index) => {
        const option = document.createElement("option");
        option.value = String(index + 1);
        option.textContent = label;
        askCityMonth.appendChild(option);
      });
      askCityMonth.value = "";
    }
  }

  function syncProjectNameInput() {
    if (!askProjectName) return;
    askProjectName.value = projectData?.name || "";
  }

  async function saveProjectName() {
    const name = resolveProjectName();
    if (!name) {
      setStatus("Enter a project name", "is-error");
      return false;
    }
    if (!projectId) return true;

    if (projectData?.name === name) return true;

    const response = await fetch(`/api/projects/${projectId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(payload) || "Could not update project name.");
    projectData = payload;
    return true;
  }

  function formatFileSize(bytes) {
    if (!Number.isFinite(bytes) || bytes < 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function isAcceptedFile(file) {
    const accept = adapter?.inputAccept(selectedModelId) || "";
    return adapter?.extensionMatchesAccept(file.name, accept) ?? true;
  }

  function updateProjectFileUI() {
    if (!askProjectFileList) return;
    const defaultHint = adapter?.inputHint(selectedModelId) || "Upload required input files";
    const hasFiles = projectCityFiles.length > 0;
    askProjectFileDrop?.classList.toggle("has-file", hasFiles);

    if (!hasFiles) {
      askProjectFileList.hidden = true;
      askProjectFileList.innerHTML = "";
      askProjectFileClear?.classList.add("hidden");
      if (askProjectFileHint) askProjectFileHint.textContent = defaultHint;
      syncAskFormActions();
      return;
    }

    askProjectFileList.hidden = false;
    askProjectFileClear?.classList.remove("hidden");
    askProjectFileList.innerHTML = "";
    projectCityFiles.forEach((file, index) => {
      const item = document.createElement("li");
      item.className = "file-list-item";

      const left = document.createElement("div");
      left.className = "file-list-left";

      const info = document.createElement("span");
      info.className = "file-list-name";
      info.textContent = file.name;
      info.title = file.name;

      const meta = document.createElement("span");
      meta.className = "file-list-meta";
      meta.textContent = formatFileSize(file.size);

      left.appendChild(info);
      left.appendChild(meta);

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "file-remove-btn";
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        projectCityFiles.splice(index, 1);
        updateProjectFileUI();
      });

      item.appendChild(left);
      item.appendChild(removeBtn);
      askProjectFileList.appendChild(item);
    });
    if (askProjectFileHint) {
      askProjectFileHint.textContent = `${projectCityFiles.length} file${projectCityFiles.length === 1 ? "" : "s"} ready to upload`;
    }
    syncAskFormActions();
  }

  function addProjectFiles(incoming) {
    const valid = incoming.filter(isAcceptedFile);
    if (!valid.length) {
      setStatus(`Include at least one accepted file (${adapter?.inputAccept(selectedModelId)})`, "is-error");
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
        if (projectData.model_id) selectedModelId = projectData.model_id;
        localStorage.setItem("gf_model_id", selectedModelId);
        syncModelSelectLock();
        return projectData;
      }
      projectId = null;
      localStorage.removeItem("gf_project_id");
    }
    const response = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: resolveProjectName() || defaultProjectName(),
        model_id: selectedModelId,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(payload) || "Could not create project.");
    projectData = payload;
    projectId = payload.id;
    localStorage.setItem("gf_project_id", projectId);
    localStorage.setItem("gf_model_id", selectedModelId);
    syncProjectNameInput();
    syncModelSelectLock();
    return projectData;
  }

  function updatePortfolioChrome(cityCount, readyCount) {
    const hasCities = cityCount > 0;
    askPortfolioEmpty?.toggleAttribute("hidden", hasCities);
    if (askProjectCityList) askProjectCityList.hidden = !hasCities;
    if (askPortfolioStats) askPortfolioStats.hidden = !hasCities;
    if (askPortfolioCityCount) {
      askPortfolioCityCount.textContent = `${cityCount} cit${cityCount === 1 ? "y" : "ies"}`;
    }
    if (askPortfolioReadyCount) {
      askPortfolioReadyCount.hidden = readyCount <= 0;
      askPortfolioReadyCount.textContent = `${readyCount} ready`;
    }
  }

  function renderAskPortfolio() {
    if (!askProjectCityList) return;
    askProjectCityList.innerHTML = "";
    const cities = projectData?.cities ? Object.entries(projectData.cities) : [];
    const pres = presentation();
    const modelId = projectData?.model_id || selectedModelId;
    const readyCount = projectData?.ready_count || 0;
    const warningCount = cities.filter(([, entry]) => cityWarning(entry)).length;

    if (!cities.length) {
      if (askProjectStatus) {
        askProjectStatus.textContent =
          "Your portfolio is empty. Add cities on the left to get started.";
      }
      updatePortfolioChrome(0, 0);
      updateNavVisibility();
      syncAskFormActions();
      return;
    }

    if (askProjectStatus) {
      let statusText =
        readyCount > 0
          ? `${readyCount} of ${cities.length} ready — dashboard unlocked. Add more cities anytime.`
          : `${cities.length} registered — run analysis to open the dashboard.`;
      if (warningCount > 0) {
        statusText += ` ${warningCount} cit${warningCount === 1 ? "y has" : "ies have"} raster/city overlap warnings.`;
      }
      askProjectStatus.textContent = statusText;
    }
    updatePortfolioChrome(cities.length, readyCount);

    cities.forEach(([key, entry]) => {
      const li = document.createElement("li");
      li.className = "ask-project-city-item";
      const name = document.createElement("strong");
      const period = formatPeriod(entry.month, entry.year);
      name.textContent = period
        ? `${entry.name || entry.address || key} · ${period}`
        : entry.name || entry.address || key;
      const meta = document.createElement("div");
      meta.className = "ask-project-city-meta";
      const status = document.createElement("span");
      const warning = cityWarning(entry);
      const statusKey =
        entry.status === "ready" && warning ? "warn" : entry.status || "pending";
      status.className = `ask-project-status ask-project-status-${statusKey}`;
      status.textContent = warning ? "needs review" : entry.status || "pending";
      meta.appendChild(status);
      const metric = adapter?.cityPrimaryValue(entry, entry.model_id || modelId);
      if (metric != null) {
        const metricEl = document.createElement("span");
        metricEl.className = "ask-project-lst";
        metricEl.textContent = adapter?.formatPrimaryValue(metric, entry.model_id || modelId);
        meta.appendChild(metricEl);
      }
      if (entry.model_id && entry.model_id !== modelId) {
        const modelTag = document.createElement("span");
        modelTag.className = "ask-project-lst";
        modelTag.textContent = entry.model_id;
        meta.appendChild(modelTag);
      }
      li.appendChild(name);
      li.appendChild(meta);
      if (entry.status === "error" && entry.error) {
        const errEl = document.createElement("div");
        errEl.className = "ask-project-error";
        errEl.textContent = entry.error;
        errEl.title = entry.error;
        li.appendChild(errEl);
      } else if (warning) {
        const warnEl = document.createElement("div");
        warnEl.className = "ask-project-warning";
        warnEl.textContent = warning;
        warnEl.title = warning;
        li.appendChild(warnEl);
      }
      askProjectCityList.appendChild(li);
    });

    updateNavVisibility();
    syncAskFormActions();
  }

  async function loadAskProjectState() {
    if (!projectId) {
      projectData = null;
      renderAskPortfolio();
      syncAskFormActions();
      return;
    }
    try {
      const response = await fetch(`/api/projects/${projectId}`);
      if (!response.ok) throw new Error("Project not found");
      projectData = await response.json();
      if (projectData.model_id) {
        selectedModelId = projectData.model_id;
        if (askModelSelect) askModelSelect.value = selectedModelId;
        localStorage.setItem("gf_model_id", selectedModelId);
      }
      syncProjectNameInput();
      updateAskModelUI();
      renderAskPortfolio();
      syncAskFormActions();
    } catch {
      projectId = null;
      localStorage.removeItem("gf_project_id");
      projectData = null;
      renderAskPortfolio();
      syncAskFormActions();
    }
  }

  async function registerAskCity(address, period) {
    await ensureAskProject();
    const response = await fetch(`/api/projects/${projectId}/cities`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        address,
        month: period.month,
        year: period.year,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(payload) || "Could not register city.");
    projectData = payload;
    return payload;
  }

  function cityKeyForEntry(address, month, year) {
    if (!projectData?.cities) return null;
    for (const [key, entry] of Object.entries(projectData.cities)) {
      const sameAddress =
        (entry.address || "").toLowerCase() === address.toLowerCase() ||
        (entry.name || "").toLowerCase() === address.toLowerCase();
      if (!sameAddress) continue;
      if ((entry.month ?? null) === month && (entry.year ?? null) === year) return key;
    }
    return null;
  }

  function openGfDashboard() {
    if (!hasReadyProject()) {
      setStatus("Run analysis for at least one city first", "is-error");
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
    const period = validateCityPeriod();
    if (!period) return;

    askAddCityBtn.disabled = true;
    setStatus(`Adding ${address}${periodPhrase(period.month, period.year)} to project…`, "");

    try {
      await saveProjectName();
      await registerAskCity(address, period);
      renderAskPortfolio();
      syncAskFormActions();
      const pres = presentation();
      setStatus(
        `${address}${periodPhrase(period.month, period.year)} added. Upload files, then run ${pres.runVerb || "analysis"}.`,
        "is-ok"
      );
    } catch (error) {
      setStatus(error.message || "Could not add city", "is-error");
    } finally {
      askAddCityBtn.disabled = false;
    }
  }

  async function runAskCityModel() {
    const address = resolveCityAddress();
    if (!address) {
      setStatus("Enter a city address", "is-error");
      return;
    }
    const period = validateCityPeriod();
    if (!period) return;
    if (!projectCityFiles.length) {
      setStatus(`Add input files for ${selectedModel().label}`, "is-error");
      return;
    }

    let cityKey = cityKeyForEntry(address, period.month, period.year);
    if (!cityKey) {
      setStatus("Add this city to the project first, then upload files and run analysis.", "is-error");
      return;
    }

    const pres = presentation();
    const modelId = selectedModelId;
    askRunCityBtn.disabled = true;
    askAddCityBtn.disabled = true;
    showRunProgress("Uploading files…", 5, runProgressStartDetail(modelId));
    setStatus(
      `Running ${pres.runVerb || selectedModel().label} for ${address}${periodPhrase(period.month, period.year)}…`,
      ""
    );

    try {
      await saveProjectName();
      const form = new FormData();
      projectCityFiles.forEach((file) => form.append("files", file));
      const response = await fetch(
        `/api/projects/${projectId}/cities/${cityKey}/run?model=${encodeURIComponent(selectedModelId)}`,
        { method: "POST", body: form }
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(parseError(payload) || "Model run failed.");

      projectData = payload;
      renderAskPortfolio();
      const steps = modelRunSteps(modelId);
      showRunProgress(steps[1] || "Running analysis…", 12, runProgressWorkingDetail(modelId));

      const finishedCity = await pollCityRun(cityKey, modelId);
      if (finishedCity?.status === "error") {
        throw new Error(finishedCity.error || "Model run failed.");
      }

      projectCityFiles = [];
      updateProjectFileUI();
      if (askCityCustom) askCityCustom.value = "";
      renderAskPortfolio();

      const runWarning = cityWarning(finishedCity);
      if (runWarning) {
        setStatus(
          `Analysis finished with a warning${periodPhrase(period.month, period.year)}: ${runWarning}`,
          "is-warn"
        );
      } else {
        setStatus(`${address}${periodPhrase(period.month, period.year)} complete — opening dashboard…`, "is-ok");
      }
      openGfDashboard();
    } catch (error) {
      await loadAskProjectState();
      const failedCity = projectData?.cities?.[cityKey];
      const detail = failedCity?.error || error.message;
      setStatus(detail || "Analysis failed", "is-error");
    } finally {
      hideRunProgress();
      askRunCityBtn.disabled = false;
      askAddCityBtn.disabled = false;
      syncAskFormActions();
    }
  }

  async function resetAskProject() {
    projectId = null;
    projectData = null;
    projectCityFiles = [];
    localStorage.removeItem("gf_project_id");
    localStorage.removeItem("gf_mode");
    if (askModelSelect) askModelSelect.disabled = false;
    if (askProjectName) askProjectName.value = "";
    if (askCityYear) askCityYear.value = "";
    if (askCityMonth) askCityMonth.value = "";
    initCityPeriodFields();
    updateProjectFileUI();
    renderAskPortfolio();
    await initModels();
    setStatus("New project started — pick a model, add a city, and upload files.", "is-ok");
    showPage("ask");
  }

  function onModelChange() {
    if (!askModelSelect) return;
    const next = askModelSelect.value || "lst";
    if (projectHasCities() && projectData?.model_id && next !== projectData.model_id) {
      askModelSelect.value = projectData.model_id;
      setStatus("Start a new project to switch analysis models.", "is-error");
      return;
    }
    selectedModelId = next;
    localStorage.setItem("gf_model_id", selectedModelId);
    projectCityFiles = [];
    if (askProjectFilesInput) askProjectFilesInput.value = "";
    updateAskModelUI();
  }

  function renderModelSelect() {
    if (!askModelSelect || !adapter) return;
    const models = adapter.listModels();
    askModelSelect.innerHTML = "";
    models.forEach((spec) => {
      const option = document.createElement("option");
      option.value = spec.id;
      option.textContent = spec.label;
      askModelSelect.appendChild(option);
    });
    if (!adapter.getModelSpec(selectedModelId)) {
      selectedModelId = models[0]?.id || "lst";
    }
    askModelSelect.value = selectedModelId;
    syncModelSelectLock();
    updateAskModelUI();
  }

  async function initModels() {
    if (!adapter) {
      setStatus("Dashboard adapter failed to load.", "is-error");
      return;
    }
    try {
      adapter.invalidateModelsCache?.();
      await adapter.fetchModels({ force: true });
      modelsLoaded = true;
      renderModelSelect();
      const models = adapter.listModels();
      if (models.length === 1 && models[0]?.id === "lst") {
        setStatus(
          "Only LST is available from the server. Stop the old server (port 8765) and run python serve.py again to load OBIA.",
          "is-error"
        );
      }
    } catch (error) {
      setStatus(error.message || "Could not load models", "is-error");
    }
  }

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.page, btn.dataset.gfMode));
  });

  document.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.goto));
  });

  askModelSelect?.addEventListener("change", onModelChange);

  askProjectFileBrowse?.addEventListener("click", (event) => {
    event.stopPropagation();
    askProjectFilesInput?.click();
  });

  askProjectFileDrop?.addEventListener("click", (event) => {
    if (event.target.closest("button")) return;
    askProjectFilesInput?.click();
  });

  askProjectFileDrop?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      askProjectFilesInput?.click();
    }
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

  askProjectName?.addEventListener("change", () => {
    saveProjectName().catch((error) => {
      setStatus(error.message || "Could not update project name", "is-error");
    });
  });

  askAddCityBtn?.addEventListener("click", () => addCityToProject());

  askCityCustom?.addEventListener("input", syncAskFormActions);
  askCityMonth?.addEventListener("change", syncAskFormActions);
  askCityYear?.addEventListener("input", syncAskFormActions);

  askRunCityBtn?.addEventListener("click", () => runAskCityModel());
  askNewProjectBtn?.addEventListener("click", () => resetAskProject());

  initCityPeriodFields();
  initModels().then(() =>
    loadAskProjectState().then(() => {
      const lastPage = localStorage.getItem("gf_last_page");
      const lastMode = localStorage.getItem("gf_mode") || "demo";
      if (lastPage === "gfframe" && (lastMode === "demo" || hasReadyProject())) {
        showPage("gfframe", lastMode);
      } else {
        showPage("ask");
      }
    })
  );
})();
