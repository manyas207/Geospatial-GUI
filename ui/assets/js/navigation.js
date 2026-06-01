const STEP_PAGES = {
  user_inputs: "pages/user_inputs.html",
  preprocessing: "pages/preprocessing.html",
  analysis: "pages/analysis.html",
  accuracy: "pages/accuracy.html",
  dashboard: "pages/dashboard.html",
};

const frame = document.getElementById("step-frame");
const status = document.getElementById("status");
const navButtons = document.querySelectorAll(".step-nav button");

function showStep(step) {
  const src = STEP_PAGES[step];
  if (!src) return;
  frame.src = src;
  navButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.step === step);
  });
  status.textContent = `Step: ${step.replace("_", " ")}`;
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => showStep(btn.dataset.step));
});

window.addEventListener("message", (event) => {
  if (event.data?.type === "navigate") {
    showStep(event.data.step);
  }
});
