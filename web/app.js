(function () {
  const navButtons = document.querySelectorAll(".nav-btn");
  const pages = document.querySelectorAll(".page");

  function showPage(name) {
    navButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.page === name);
    });
    pages.forEach((page) => {
      page.classList.toggle("active", page.id === `page-${name}`);
    });
  }

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.page));
  });

  const rasterInput = document.getElementById("raster");
  const results = document.getElementById("results");

  rasterInput.addEventListener("change", () => {
    const file = rasterInput.files && rasterInput.files[0];
    if (file) {
      results.value = `Selected raster: ${file.name}\n`;
    }
  });
})();
