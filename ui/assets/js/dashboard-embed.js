/**
 * Dashboard embed: listen for payload from parent, wire downloads to API later.
 */
document.addEventListener("geospatial-gui", (event) => {
  const { action, payload } = event.detail;
  if (action === "setData" && payload) {
    renderDashboard(payload);
  }
});

function renderDashboard(data) {
  const maps = document.getElementById("maps-panel");
  const klass = document.getElementById("class-panel");
  const perf = document.getElementById("perf-panel");
  const summary = document.getElementById("summary-panel");
  if (maps && data.maps) maps.querySelector(".placeholder").textContent = JSON.stringify(data.maps);
  if (klass && data.classifications) klass.querySelector(".placeholder").textContent = "Classification loaded.";
  if (perf && data.model_performance) perf.querySelector(".placeholder").textContent = "Metrics loaded.";
  if (summary && data.summary) summary.querySelector(".placeholder").textContent = data.summary.title || "Report ready.";
}

document.querySelectorAll("[data-format]").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (window.GeospatialEmbed) {
      GeospatialEmbed.notifyParent("download", { format: btn.dataset.format });
    }
  });
});
