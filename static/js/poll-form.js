// Poll form: add/remove option rows (2–5) and keep the formset management form in sync.
// Without JS the form still works with the rows the server rendered.
(function () {
  "use strict";

  const fieldset = document.querySelector("[data-option-formset]");
  if (!fieldset) {
    return;
  }

  const rows = fieldset.querySelector("[data-option-rows]");
  const template = fieldset.querySelector("[data-option-template]");
  const addButton = fieldset.querySelector("[data-add-option]");
  const totalForms = fieldset.querySelector('input[name$="-TOTAL_FORMS"]');
  const min = Number(fieldset.dataset.min);
  const max = Number(fieldset.dataset.max);

  function rowElements() {
    return rows.querySelectorAll("[data-option-row]");
  }

  // Renumber names/ids (options-<i>-text) and placeholders after any change.
  function refresh() {
    const all = rowElements();
    all.forEach(function (row, index) {
      const input = row.querySelector("input");
      input.name = input.name.replace(/-(\d+|__prefix__)-/, "-" + index + "-");
      input.id = input.id.replace(/-(\d+|__prefix__)-/, "-" + index + "-");
      input.placeholder = index + 1 + ". seçenek";
      row.querySelector("[data-remove-option]").hidden = all.length <= min;
    });
    totalForms.value = all.length;
    addButton.hidden = all.length >= max;
  }

  addButton.addEventListener("click", function () {
    if (rowElements().length >= max) {
      return;
    }
    rows.appendChild(template.content.cloneNode(true));
    refresh();
    const all = rowElements();
    all[all.length - 1].querySelector("input").focus();
  });

  rows.addEventListener("click", function (event) {
    const button = event.target.closest("[data-remove-option]");
    if (!button || rowElements().length <= min) {
      return;
    }
    const row = button.closest("[data-option-row]");
    const next = row.nextElementSibling || row.previousElementSibling;
    row.remove();
    refresh();
    if (next) {
      next.querySelector("input").focus();
    }
  });

  refresh();
})();
