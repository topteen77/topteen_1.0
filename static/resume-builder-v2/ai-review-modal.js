(function (global) {
  "use strict";

  var state = {
    cfg: null,
    overlay: null,
    escapeBound: false,
  };

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function apiPost(cfg, body) {
    return fetch(cfg.aiUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": cfg.csrfToken,
      },
      body: JSON.stringify(body),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) {
          var err = new Error((data && data.error) || "Request failed");
          err.payload = data;
          throw err;
        }
        return data;
      });
    });
  }

  function buildSectionsHtml(comparison) {
    return (comparison || [])
      .map(function (row) {
        var changed = !!row.changed;
        return (
          '<section class="rb2-ai-review__card' +
          (changed ? " is-changed" : "") +
          '" data-section="' +
          esc(row.id) +
          '">' +
          '<header class="rb2-ai-review__card-head">' +
          '<label class="rb2-ai-review__card-check">' +
          '<input type="checkbox" class="rb2-ai-section-cb" value="' +
          esc(row.id) +
          '"' +
          (changed ? " checked" : "") +
          (changed ? "" : " disabled") +
          ">" +
          '<span class="rb2-ai-review__card-title">' +
          esc(row.label) +
          "</span></label>" +
          (changed
            ? '<span class="rb2-ai-review__badge">Changed</span>'
            : '<span class="rb2-ai-review__badge rb2-ai-review__badge--muted">Unchanged</span>') +
          "</header>" +
          '<div class="rb2-ai-review__cols">' +
          '<div class="rb2-ai-review__col rb2-ai-review__col--old">' +
          '<h3 class="rb2-ai-review__col-label">Current</h3>' +
          '<pre class="rb2-ai-review__text">' +
          esc(row.old) +
          "</pre></div>" +
          '<div class="rb2-ai-review__col rb2-ai-review__col--new">' +
          '<h3 class="rb2-ai-review__col-label">AI generated</h3>' +
          '<pre class="rb2-ai-review__text">' +
          esc(row.new) +
          "</pre></div></div></section>"
        );
      })
      .join("");
  }

  function ensureOverlay() {
    if (state.overlay) return state.overlay;
    var el = document.createElement("div");
    el.id = "rb2AiReviewOverlay";
    el.className = "rb2-ai-review-overlay";
    el.setAttribute("hidden", "");
    el.setAttribute("role", "presentation");
    el.innerHTML =
      '<div class="rb2-ai-review-dialog" role="dialog" aria-modal="true" aria-labelledby="rb2AiReviewTitle">' +
      '  <header class="rb2-ai-review__header rb2-ai-review-dialog__header">' +
      '    <div class="rb2-ai-review__header-main">' +
      '      <h2 class="rb2-ai-review__title" id="rb2AiReviewTitle">AI Resume Review</h2>' +
      '      <p class="rb2-ai-review__sub" id="rb2AiReviewSub"></p>' +
      "    </div>" +
      '    <button type="button" class="rb2-ai-review__close" id="rb2AiReviewClose" aria-label="Close">&times;</button>' +
      "  </header>" +
      '  <div class="rb2-ai-review__toolbar rb2-ai-review-dialog__toolbar">' +
      '    <p class="rb2-ai-review__hint">Compare your current resume with the AI draft section by section. Select what to keep, then apply.</p>' +
      '    <div class="rb2-ai-review__toolbar-actions">' +
      '      <label class="rb2-ai-review__select-all"><input type="checkbox" id="rb2AiSelectAll" checked> Select all changed</label>' +
      "    </div></div>" +
      '  <div class="rb2-ai-review-dialog__body">' +
      '    <div class="rb2-ai-review__main" id="rb2AiReviewMain">' +
      '      <div class="rb2-ai-review__sections" id="rb2AiSections"></div>' +
      "    </div></div>" +
      '  <footer class="rb2-ai-review__footer rb2-ai-review-dialog__footer">' +
      '    <button type="button" class="rb2-ai-review__btn rb2-ai-review__btn--ghost" id="rb2AiDiscard">Discard draft</button>' +
      '    <div class="rb2-ai-review__footer-right">' +
      '      <button type="button" class="rb2-ai-review__btn rb2-ai-review__btn--soft" id="rb2AiApplySelected">Apply selected</button>' +
      '      <button type="button" class="rb2-ai-review__btn rb2-ai-review__btn--primary" id="rb2AiApplyAll">Apply all</button>' +
      "    </div></footer></div>";
    document.body.appendChild(el);
    state.overlay = el;
    return el;
  }

  function isOpen() {
    return state.overlay && !state.overlay.hasAttribute("hidden");
  }

  function selectedSections(overlay) {
    var out = [];
    overlay.querySelectorAll(".rb2-ai-section-cb").forEach(function (cb) {
      if (cb.checked && !cb.disabled && cb.value) out.push(cb.value);
    });
    return out;
  }

  function setBusy(overlay, busy) {
    ["rb2AiApplySelected", "rb2AiApplyAll", "rb2AiDiscard", "rb2AiReviewClose"].forEach(function (id) {
      var btn = overlay.querySelector("#" + id);
      if (btn) btn.disabled = busy;
    });
  }

  function syncSelectAll(overlay) {
    var selectAll = overlay.querySelector("#rb2AiSelectAll");
    if (!selectAll) return;
    var enabled = Array.prototype.filter.call(overlay.querySelectorAll(".rb2-ai-section-cb"), function (cb) {
      return !cb.disabled;
    });
    if (!enabled.length) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
      return;
    }
    var checked = enabled.filter(function (cb) {
      return cb.checked;
    });
    selectAll.checked = checked.length === enabled.length;
    selectAll.indeterminate = checked.length > 0 && checked.length < enabled.length;
  }

  function closeModal() {
    var overlay = state.overlay;
    if (!overlay) return;
    overlay.setAttribute("hidden", "");
    document.body.classList.remove("rb2-ai-review-open");
    setBusy(overlay, false);
    var activeCfg = state.cfg;
    if (activeCfg && typeof activeCfg.onClose === "function") activeCfg.onClose();
  }

  function onApply(applyAll) {
    var overlay = state.overlay;
    var msgs = global.RB2Messages;
    if (!overlay || !msgs) return;
    var activeCfg = state.cfg;
    if (!activeCfg) return;

    var sections = applyAll ? null : selectedSections(overlay);
    if (!applyAll && !sections.length) {
      msgs.toast("Choose at least one changed section before applying.", { type: "warning", title: "Nothing selected" });
      return;
    }

    msgs
      .confirm({
        title: applyAll ? "Apply all sections?" : "Apply selected sections?",
        message: applyAll
          ? "All AI-generated sections will replace your current saved resume content."
          : "Only the sections you selected will be updated on your resume.",
        confirmLabel: applyAll ? "Apply all" : "Apply selected",
        cancelLabel: "Keep reviewing",
      })
      .then(function (ok) {
        if (!ok) return;
        setBusy(overlay, true);
        var payload = { action: "apply_ai_resume", apply_all: !!applyAll };
        if (!applyAll) payload.sections = sections;
        apiPost(activeCfg, payload)
          .then(function (data) {
            closeModal();
            if (typeof activeCfg.onApplied === "function") activeCfg.onApplied(data);
            if (msgs.showSuccess) {
              msgs.showSuccess({
                title: "Resume updated",
                message: "Your selected AI changes have been saved to your resume.",
              });
            } else if (msgs.toast) {
              msgs.toast("Your resume has been updated.", { type: "success", title: "Saved" });
            }
          })
          .catch(function (err) {
            setBusy(overlay, false);
            msgs.toast(
              (err.payload && err.payload.error) || err.message || "Could not apply the AI draft.",
              { type: "error" }
            );
          });
      });
  }

  function onDiscard() {
    var overlay = state.overlay;
    var msgs = global.RB2Messages;
    var activeCfg = state.cfg;
    if (!overlay || !msgs || !activeCfg) return;

    msgs
      .confirm({
        title: "Discard AI draft?",
        message: "Your current resume will stay unchanged. You can generate a new draft anytime.",
        confirmLabel: "Discard draft",
        cancelLabel: "Keep reviewing",
        variant: "danger",
      })
      .then(function (ok) {
        if (!ok) return;
        setBusy(overlay, true);
        apiPost(activeCfg, { action: "discard_ai_resume" })
            .then(function () {
              closeModal();
              if (typeof activeCfg.onDiscarded === "function") activeCfg.onDiscarded();
              msgs.toast("AI draft discarded. Your resume was not changed.", { type: "info", title: "Draft removed" });
            })
          .catch(function (err) {
            setBusy(overlay, false);
            msgs.toast((err.payload && err.payload.error) || "Could not discard draft.", { type: "error" });
          });
      });
  }

  function bindEvents(overlay) {
    if (overlay.dataset.bound === "1") return;
    overlay.dataset.bound = "1";

    overlay.addEventListener("change", function (e) {
      if (e.target && e.target.classList.contains("rb2-ai-section-cb")) {
        syncSelectAll(overlay);
      }
    });

    var selectAll = overlay.querySelector("#rb2AiSelectAll");
    if (selectAll) {
      selectAll.addEventListener("change", function () {
        overlay.querySelectorAll(".rb2-ai-section-cb").forEach(function (cb) {
          if (!cb.disabled) cb.checked = selectAll.checked;
        });
      });
    }

    var dialog = overlay.querySelector(".rb2-ai-review-dialog");
    if (dialog) {
      dialog.addEventListener("click", function (e) {
        e.stopPropagation();
      });
    }

    overlay.querySelector("#rb2AiApplySelected").addEventListener("click", function () {
      onApply(false);
    });
    overlay.querySelector("#rb2AiApplyAll").addEventListener("click", function () {
      onApply(true);
    });
    overlay.querySelector("#rb2AiDiscard").addEventListener("click", onDiscard);
    overlay.querySelector("#rb2AiReviewClose").addEventListener("click", closeModal);

    if (!state.escapeBound) {
      state.escapeBound = true;
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && isOpen()) closeModal();
      });
    }
  }

  function open(opts) {
    var cfg = opts || {};
    state.cfg = cfg;
    var overlay = ensureOverlay();
    var sub = overlay.querySelector("#rb2AiReviewSub");
    if (sub) {
      sub.textContent = (cfg.resumeTitle || "My Resume") + (cfg.goalLabel ? " · Goal: " + cfg.goalLabel : "");
    }
    var sectionsEl = overlay.querySelector("#rb2AiSections");
    if (sectionsEl) sectionsEl.innerHTML = buildSectionsHtml(cfg.comparison || []);
    bindEvents(overlay);
    syncSelectAll(overlay);
    setBusy(overlay, false);
    overlay.removeAttribute("hidden");
    document.body.classList.add("rb2-ai-review-open");
  }

  function close() {
    closeModal();
  }

  global.RB2AiReviewModal = { open: open, close: close };
})(typeof window !== "undefined" ? window : this);
