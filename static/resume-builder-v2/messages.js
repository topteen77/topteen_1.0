(function (global) {
  "use strict";

  var ICONS = {
    success: "bx-check-circle",
    error: "bx-error-circle",
    info: "bx-info-circle",
    warning: "bx-error",
  };

  var TITLES = {
    success: "Success",
    error: "Something went wrong",
    info: "Notice",
    warning: "Please check",
  };

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function ensureShell() {
    if (document.getElementById("rb2MsgRoot")) return;
    var root = document.createElement("div");
    root.id = "rb2MsgRoot";
    root.innerHTML =
      '<div class="rb2-toast-stack" id="rb2ToastStack" aria-live="polite"></div>' +
      '<div class="rb2-modal-backdrop" id="rb2ModalBackdrop" hidden>' +
      '  <div class="rb2-modal" id="rb2Modal" role="dialog" aria-modal="true" aria-labelledby="rb2ModalTitle">' +
      '    <div class="rb2-modal__head">' +
      '      <div class="rb2-modal__icon" id="rb2ModalIcon"><i class="bx bx-help-circle"></i></div>' +
      '      <h2 class="rb2-modal__title" id="rb2ModalTitle"></h2>' +
      '      <p class="rb2-modal__message" id="rb2ModalMessage"></p>' +
      "    </div>" +
      '    <div class="rb2-modal__foot">' +
      '      <button type="button" class="rb2-modal__btn rb2-modal__btn--ghost" id="rb2ModalCancel">Cancel</button>' +
      '      <button type="button" class="rb2-modal__btn rb2-modal__btn--primary" id="rb2ModalConfirm">Confirm</button>' +
      "    </div>" +
      "  </div>" +
      "</div>" +
      '<div class="rb2-success-panel" id="rb2SuccessPanel" hidden>' +
      '  <div class="rb2-success-panel__card">' +
      '    <div class="rb2-success-panel__icon"><i class="bx bx-check"></i></div>' +
      '    <h2 class="rb2-success-panel__title" id="rb2SuccessTitle">Done</h2>' +
      '    <p class="rb2-success-panel__text" id="rb2SuccessText"></p>' +
      "  </div>" +
      "</div>";
    document.body.appendChild(root);
  }

  function toast(message, opts) {
    ensureShell();
    opts = opts || {};
    var type = opts.type || "info";
    var stack = document.getElementById("rb2ToastStack");
    if (!stack) return;

    var el = document.createElement("div");
    el.className = "rb2-toast rb2-toast--" + type;
    var title = opts.title || TITLES[type] || TITLES.info;
    var icon = ICONS[type] || ICONS.info;
    var actionHtml = "";
    if (opts.actionLabel && opts.actionHref) {
      actionHtml =
        '<a class="rb2-toast__action" href="' +
        esc(opts.actionHref) +
        '" target="_blank" rel="noopener">' +
        esc(opts.actionLabel) +
        "</a>";
    } else if (opts.actionLabel && typeof opts.onAction === "function") {
      actionHtml =
        '<button type="button" class="rb2-toast__action">' + esc(opts.actionLabel) + "</button>";
    }
    el.innerHTML =
      '<div class="rb2-toast__icon"><i class="bx ' +
      icon +
      '"></i></div>' +
      '<div class="rb2-toast__body">' +
      "<p class=\"rb2-toast__title\">" +
      esc(title) +
      "</p>" +
      "<p class=\"rb2-toast__text\">" +
      esc(message) +
      "</p>" +
      actionHtml +
      "</div>" +
      '<button type="button" class="rb2-toast__close" aria-label="Dismiss">&times;</button>';

    var closeBtn = el.querySelector(".rb2-toast__close");
    function dismiss() {
      el.classList.add("is-out");
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 220);
    }
    if (closeBtn) closeBtn.addEventListener("click", dismiss);

    var actionBtn = el.querySelector(".rb2-toast__action");
    if (actionBtn && actionBtn.tagName === "BUTTON" && typeof opts.onAction === "function") {
      actionBtn.addEventListener("click", function () {
        opts.onAction();
        dismiss();
      });
    }

    stack.appendChild(el);
    var duration = opts.duration !== undefined ? opts.duration : 5200;
    if (duration > 0) {
      setTimeout(dismiss, duration);
    }
    return { dismiss: dismiss };
  }

  var confirmResolver = null;

  function confirm(opts) {
    ensureShell();
    opts = opts || {};
    var backdrop = document.getElementById("rb2ModalBackdrop");
    var modal = document.getElementById("rb2Modal");
    var titleEl = document.getElementById("rb2ModalTitle");
    var msgEl = document.getElementById("rb2ModalMessage");
    var iconEl = document.getElementById("rb2ModalIcon");
    var cancelBtn = document.getElementById("rb2ModalCancel");
    var confirmBtn = document.getElementById("rb2ModalConfirm");
    if (!backdrop || !modal) return Promise.resolve(false);

    var isDanger = opts.variant === "danger";
    modal.classList.toggle("rb2-modal--danger", isDanger);
    if (titleEl) titleEl.textContent = opts.title || "Confirm action";
    if (msgEl) msgEl.textContent = opts.message || "";
    if (iconEl) {
      iconEl.innerHTML = isDanger
        ? '<i class="bx bx-trash"></i>'
        : '<i class="bx bx-check-shield"></i>';
    }
    if (cancelBtn) cancelBtn.textContent = opts.cancelLabel || "Cancel";
    if (confirmBtn) {
      confirmBtn.textContent = opts.confirmLabel || "Confirm";
      confirmBtn.className =
        "rb2-modal__btn " + (isDanger ? "rb2-modal__btn--danger" : "rb2-modal__btn--primary");
    }

    backdrop.removeAttribute("hidden");

    return new Promise(function (resolve) {
      confirmResolver = resolve;
      function finish(val) {
        backdrop.setAttribute("hidden", "");
        confirmResolver = null;
        resolve(val);
      }
      function onKey(e) {
        if (e.key === "Escape") finish(false);
      }
      document.addEventListener("keydown", onKey);
      if (cancelBtn) {
        cancelBtn.onclick = function () {
          document.removeEventListener("keydown", onKey);
          finish(false);
        };
      }
      if (confirmBtn) {
        confirmBtn.onclick = function () {
          document.removeEventListener("keydown", onKey);
          finish(true);
        };
      }
      backdrop.onclick = function (e) {
        if (e.target === backdrop) {
          document.removeEventListener("keydown", onKey);
          finish(false);
        }
      };
    });
  }

  function showSuccess(opts) {
    ensureShell();
    opts = opts || {};
    var panel = document.getElementById("rb2SuccessPanel");
    var titleEl = document.getElementById("rb2SuccessTitle");
    var textEl = document.getElementById("rb2SuccessText");
    if (!panel) return;
    if (titleEl) titleEl.textContent = opts.title || "Success";
    if (textEl) textEl.textContent = opts.message || "";
    panel.removeAttribute("hidden");
    return function hide() {
      panel.setAttribute("hidden", "");
    };
  }

  global.RB2Messages = {
    toast: toast,
    confirm: confirm,
    showSuccess: showSuccess,
  };
})(typeof window !== "undefined" ? window : this);
