/** Single-page wizard tabs (no nested iframes). */
const panels = document.querySelectorAll(".wizard-panel");
const navButtons = document.querySelectorAll(".step-nav button");

function showPanel(name) {
  panels.forEach((panel) => {
    const active = panel.dataset.panel === name;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
  navButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.panel === name);
  });
  if (window.GeospatialEmbed) {
    GeospatialEmbed.notifyParent("step", { panel: name });
  }
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => showPanel(btn.dataset.panel));
});
