(function () {
  const PAGE_META = {
    inputs: { eyebrow: "Workflow", title: "Inputs" },
    analysis: { eyebrow: "Analysis", title: "Analysis Options" },
    dashboard: { eyebrow: "Output", title: "Results Dashboard" },
  };

  const navButtons = document.querySelectorAll(".nav-btn");
  const pages = document.querySelectorAll(".page");
  const pageEyebrow = document.getElementById("pageEyebrow");
  const pageTitle = document.getElementById("pageTitle");
  const statusEl = document.getElementById("status");

  const rasterInput = document.getElementById("raster");
  const fileDrop = document.getElementById("fileDrop");
  const fileHint = document.getElementById("fileHint");
  const results = document.getElementById("results");
  const analysisCards = document.querySelectorAll(".analysis-card");

  function setStatus(message, type) {
    statusEl.textContent = message || "";
    statusEl.classList.remove("is-ok", "is-error");
    if (type) statusEl.classList.add(type);
  }

  function showPage(name) {
    const meta = PAGE_META[name] || PAGE_META.inputs;

    navButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.page === name);
    });
    pages.forEach((page) => {
      page.classList.toggle("active", page.id === `page-${name}`);
    });

    pageEyebrow.textContent = meta.eyebrow;
    pageTitle.textContent = meta.title;
  }

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.page));
  });

  fileDrop.addEventListener("click", () => rasterInput.click());

  fileDrop.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      rasterInput.click();
    }
  });

  fileDrop.setAttribute("tabindex", "0");
  fileDrop.setAttribute("role", "button");

  rasterInput.addEventListener("change", () => {
    const file = rasterInput.files && rasterInput.files[0];
    if (!file) {
      fileDrop.classList.remove("has-file");
      fileHint.textContent = ".tif · .tiff · .geotiff";
      setStatus("");
      return;
    }

    fileDrop.classList.add("has-file");
    fileHint.textContent = file.name;
    setStatus("Raster ready", "is-ok");
    results.value = `Selected raster: ${file.name}\n`;
  });

  analysisCards.forEach((card) => {
    card.addEventListener("click", () => {
      analysisCards.forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
      const label = card.querySelector("strong").textContent;
      setStatus(`${label} selected`, "is-ok");
      results.value = `Analysis method: ${label}\n`;
      showPage("dashboard");
    });
  });

  showPage("inputs");
})();
