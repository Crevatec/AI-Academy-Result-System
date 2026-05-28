/**
 * frontend/static/js/dashboard.js
 * --------------------------------
 * Global JavaScript for AcadResult dashboards.
 * Loaded on every page via base.html.
 *
 * Responsibilities:
 * - Auto-dismiss flash messages after 5 seconds
 * - Active nav link highlighting
 * - Any shared UI helpers
 *
 * Chart.js rendering is done inline per-page in {% block extra_js %}
 * because each page has different data variables from Jinja2.
 */

document.addEventListener("DOMContentLoaded", function () {

  // ── Auto-dismiss flash messages after 5 seconds ─────────────────────
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach(function (flash) {
    setTimeout(function () {
      flash.style.transition = "opacity 0.5s";
      flash.style.opacity = "0";
      setTimeout(function () {
        flash.remove();
      }, 500);
    }, 5000);
  });

  // ── Highlight active nav link based on current URL ──────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll(".nav-link").forEach(function (link) {
    if (link.getAttribute("href") === currentPath) {
      link.classList.add("active");
    }
  });

  // ── File input label update ─────────────────────────────────────────
  const fileInput = document.getElementById("excelFile");
  if (fileInput) {
    fileInput.addEventListener("change", function () {
      const label = document.querySelector(".file-label");
      if (label && this.files.length > 0) {
        label.textContent = this.files[0].name;
      }
    });
  }

});
