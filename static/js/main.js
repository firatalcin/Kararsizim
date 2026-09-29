// Kararsizim front-end helpers.
// Phase 3 adds voting via fetch, Phase 4 adds copy-link; toasts are wired in Phase 1.
(function () {
  "use strict";

  // CSRF token for fetch requests (sent as the X-CSRFToken header).
  window.kz = window.kz || {};
  window.kz.csrfToken = function () {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  };
})();
