// Kararsizim front-end helpers.
// Toasts, voting via fetch, copy-link.
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

  // ---------- Voting ----------
  // Progressive enhancement: the vote form posts normally without JS; with JS we
  // post via fetch and turn the card into its results view in place.

  function el(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  // Mirrors the results state of partials/_poll_card.html + _option_body.html.
  function renderResults(form, data) {
    const colors = {};
    form.querySelectorAll("[data-option-id]").forEach(function (button) {
      colors[button.dataset.optionId] = button.dataset.color;
    });

    const list = el("ul", "options");
    list.setAttribute("aria-label", "Sonuçlar");
    const bars = [];
    data.options.forEach(function (option) {
      const chosen = option.id === data.voted_option_id;
      const item = el(
        "li",
        "option option--" + colors[option.id] + " option--result" + (chosen ? " option--chosen option--pop" : "")
      );
      const bar = el("span", "option__bar");
      bar.setAttribute("aria-hidden", "true");
      item.appendChild(bar);
      item.appendChild(el("span", "option__text", option.text));
      if (chosen) {
        const check = el("span", "option__check", "✓");
        check.setAttribute("aria-label", "Senin oyun");
        item.appendChild(check);
      }
      item.appendChild(el("span", "option__percent", "%" + option.percent));
      item.style.setProperty("--percent", "0%");
      bars.push([item, option.percent]);
      list.appendChild(item);
    });

    const card = form.closest(".poll-card");
    const hint = card.querySelector(".poll-card__hint");
    if (hint) {
      hint.remove();
    }
    form.replaceWith(list);
    card.querySelector("[data-total-votes]").textContent = data.total_votes + " oy";

    // Grow the bars from 0 on the next frame so the CSS transition runs.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        bars.forEach(function (pair) {
          pair[0].style.setProperty("--percent", pair[1] + "%");
        });
      });
    });
  }

  document.addEventListener("submit", async function (event) {
    const form = event.target.closest("[data-vote-form]");
    const button = event.submitter;
    if (!form || !button || !button.dataset.optionId) {
      return;
    }
    event.preventDefault();

    const buttons = form.querySelectorAll("button");
    buttons.forEach(function (b) { b.disabled = true; });

    const body = new FormData(form);
    body.set("option_id", button.value);

    let data = null;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { Accept: "application/json", "X-CSRFToken": window.kz.csrfToken() },
        body: body,
        credentials: "same-origin",
      });
      data = await response.json();
    } catch (error) {
      data = null;
    }

    if (data && data.options) {
      // 200 (vote saved) or 409 (already voted): both carry fresh results.
      renderResults(form, data);
      window.kz.toast(data.ok ? "Oyun kaydedildi! ✨" : data.error, data.ok ? "success" : "warning");
    } else {
      buttons.forEach(function (b) { b.disabled = false; });
      window.kz.toast((data && data.error) || "Bir şeyler ters gitti, tekrar dener misin?", "error");
    }
  });

  // ---------- Copy link ----------
  // The link points at the poll page, so without JS it still works as a shareable link.
  document.addEventListener("click", async function (event) {
    const link = event.target.closest("[data-copy-link]");
    if (!link) {
      return;
    }
    event.preventDefault();
    const url = new URL(link.getAttribute("href"), window.location.href).href;

    try {
      // Missing outside secure contexts (plain http on a non-localhost host) → throws.
      await navigator.clipboard.writeText(url);
      window.kz.toast("Link kopyalandı!", "success");
    } catch (error) {
      if (navigator.share) {
        try {
          await navigator.share({ url: url, title: document.title });
        } catch (shareError) {
          // The user closed the share sheet; nothing to do.
        }
      } else {
        window.prompt("Linki kopyala:", url);
      }
    }
  });
})();
