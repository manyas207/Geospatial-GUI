/**
 * Urban Heat & Equity GUI Frame — chat context, queries, and report export.
 */
(function () {
  const gf = window.GfFrame;

  function chatContext() {
    const { state, adapter } = gf;
    const city = gf.getCities()[state.activeCityIndex];
    const modelId = state.appMode === "project" ? gf.activeProjectModelId(city) : "lst";
    const pres = gf.modelPresentation(modelId);
    const summary = state.cityLayersData?.summary || {};
    const demoCities = state.appMode === "demo" ? gf.buildDemoCitiesForChat() : null;
    const overview =
      state.appMode === "demo"
        ? state.demoOverview || {
            hottest_city: state.demoHottest?.name,
            peak_lst_C: state.demoHottest?.temp,
            hottest_month: state.demoHottest?.month,
            city_count: demoCities.length,
          }
        : null;

    const ctx = {
      model: "equity",
      analysis_model: state.appMode === "project" ? modelId : null,
      project_id: state.appMode === "project" ? state.projectId : null,
      demo_cities: demoCities,
      demo_overview: overview,
      tract_layer_token:
        state.appMode === "project" && city?.status === "ready" && city?.key
          ? `${state.projectId}:${city.key}`
          : state.cityLayersData?.vector_layer?.token || null,
      summary:
        state.appMode === "demo"
          ? `11-city urban heat and equity demo. Placeholder LST for all cities; live Census for the active city (${city?.name}). Use demo_cities and city_comparison for cross-city questions.`
          : adapter?.getPlugin(modelId)?.chatContextSummary(city) ||
            (pres.chatContextSummary
              ? pres.chatContextSummary.replace("{city}", city?.name || "this city")
              : state.cityLayersData
                ? `Census tract data for ${city.name} (${summary.county || ""}, ${summary.state || ""}).`
                : `Multi-city ${pres.chatAnalysisLabel || "analysis"} project.`),
      stats: {
        active_city: city?.name,
        observation_month: city?.month ?? null,
        observation_year: city?.year ?? null,
        ...summary,
      },
      logs: state.cityLayersData ? JSON.stringify(state.cityLayersData.sources || {}) : "",
      raster:
        state.appMode === "project" ? (adapter?.cityRunStats(city).geotiff || "") : "",
    };
    if (state.appMode === "demo") {
      if (city?.temp != null) ctx.stats.demo_lst_C = city.temp;
      if (overview?.peak_lst_C != null) ctx.stats.peak_lst_C = overview.peak_lst_C;
      if (overview?.hottest_city) ctx.stats.hottest_city = overview.hottest_city;
    } else if (state.appMode === "project") {
      Object.assign(ctx.stats, adapter?.cityRunStats(city) || {});
      const warning = gf.cityRunWarning(city);
      if (warning) ctx.stats.tract_zonal_warning = warning;
      ctx.project_cities = state.projectCityList
        .filter((entry) => entry.status === "ready")
        .map((entry) => ({
          key: entry.key,
          name: entry.name || entry.address,
          address: entry.address,
          month: entry.month ?? null,
          year: entry.year ?? null,
          run_stats: entry.run_stats || {},
          summary: entry.summary || {},
        }));
    }
    return ctx;
  }

  function renderChat() {
    const { state, dom } = gf;
    if (!dom.chatPanelEl) return;
    dom.chatPanelEl.innerHTML = "";
    state.chatMessages.forEach((msg) => {
      const bubble = document.createElement("div");
      bubble.className = `gf-msg gf-msg-${msg.role}`;
      bubble.textContent = msg.text;
      dom.chatPanelEl.appendChild(bubble);
    });
    dom.chatPanelEl.scrollTop = dom.chatPanelEl.scrollHeight;
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
    const { state, dom } = gf;
    const q = (question || "").trim();
    if (!q) return;

    state.chatMessages.push({ role: "user", text: q });
    renderChat();
    switchPanelTab("chat");
    if (dom.sendBtnEl) dom.sendBtnEl.disabled = true;

    try {
      const response = await fetch("/api/followup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, context: chatContext() }),
      });
      const payload = await response.json().catch(() => ({}));
      if (response.ok) {
        state.chatMessages.push({
          role: "assistant",
          text: payload.answer || "No answer returned.",
        });
      } else {
        state.chatMessages.push({
          role: "assistant",
          text: followupErrorText(response, payload) || "Could not get an answer.",
        });
      }
    } catch {
      state.chatMessages.push({ role: "assistant", text: "Network error. Check that the server is running." });
    } finally {
      if (dom.sendBtnEl) dom.sendBtnEl.disabled = false;
      renderChat();
    }
  }

  function reportChatPairs(maxPairs) {
    const { state } = gf;
    const limit = maxPairs ?? 5;
    const pairs = [];
    for (let i = 0; i < state.chatMessages.length; i += 1) {
      if (state.chatMessages[i].role !== "user") continue;
      const answer = state.chatMessages[i + 1]?.role === "assistant" ? state.chatMessages[i + 1].text : "";
      pairs.push({ question: state.chatMessages[i].text, answer });
    }
    return pairs.slice(-limit);
  }

  function parseReportError(response, payload) {
    if (response?.status === 405) {
      return "Report export is not available on the running server. Stop python serve.py, start it again, then retry.";
    }
    if (typeof payload.detail === "string") return payload.detail;
    return "Could not generate report.";
  }

  async function exportReport() {
    const { state } = gf;
    if (state.appMode !== "project" || !state.projectId) {
      state.chatMessages.push({
        role: "assistant",
        text: "PDF reports are available for your own project runs. Upload and process cities on Step 1, then return here to export.",
      });
      renderChat();
      switchPanelTab("chat");
      return;
    }

    const city = gf.getCities()[state.activeCityIndex];
    if (!city?.key || city.status !== "ready") {
      state.chatMessages.push({
        role: "assistant",
        text: "Select a ready city with completed analysis before exporting a report.",
      });
      renderChat();
      switchPanelTab("chat");
      return;
    }

    const exportBtn = document.getElementById("gfExportBtn");
    const priorLabel = exportBtn?.textContent;
    if (exportBtn) {
      exportBtn.disabled = true;
      exportBtn.textContent = "Generating PDF…";
    }

    try {
      const response = await fetch(`/api/projects/${state.projectId}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city_key: city.key,
          chat: reportChatPairs(5),
          max_chat_pairs: 5,
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        state.chatMessages.push({
          role: "assistant",
          text: parseReportError(response, payload),
        });
        renderChat();
        switchPanelTab("chat");
        return;
      }

      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || `${state.projectData?.name || "report"}.pdf`;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      state.chatMessages.push({
        role: "assistant",
        text: "Network error while generating the report. Check that the server is running.",
      });
      renderChat();
      switchPanelTab("chat");
    } finally {
      if (exportBtn) {
        exportBtn.disabled = false;
        exportBtn.textContent = priorLabel || "Export PDF report";
      }
    }
  }

  Object.assign(gf, {
    chatContext,
    renderChat,
    switchPanelTab,
    followupErrorText,
    askQuestion,
    exportReport,
  });
})();
