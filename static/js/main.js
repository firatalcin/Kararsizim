// Kararsizim front-end helpers.
// Phase 3 adds voting via fetch, Phase 4 adds copy-link.
(function () {
  "use strict";

  const TOAST_DURATION_MS = 3000;

  window.kz = window.kz || {};

  // CSRF token for fetch requests (sent as the X-CSRFToken header).
  window.kz.csrfToken = function () {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  };

  // Removes a toast once its CSS fade-out ends, or after the duration when
  // animations are off (prefers-reduced-motion).
  function scheduleRemoval(toast) {
    toast.addEventListener("animationend", function (event) {
      if (event.animationName === "toast-out") {
        toast.remove();
      }
    });
    window.setTimeout(function () {
      toast.remove();
    }, TOAST_DURATION_MS + 400);
  }

  // Shows a toast. Text is set via textContent, never innerHTML.
  window.kz.toast = function (text, kind) {
    const container = document.getElementById("toasts");
    if (!container) {
      return;
    }
    const toast = document.createElement("div");
    toast.className = "toast" + (kind ? " toast--" + kind : "");
    toast.textContent = text;
    container.appendChild(toast);
    scheduleRemoval(toast);
  };

  document.querySelectorAll("#toasts .toast").forEach(scheduleRemoval);
})();
