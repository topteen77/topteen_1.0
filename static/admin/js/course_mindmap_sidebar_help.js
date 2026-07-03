(function () {
  var modal = null;
  var lastFocus = null;

  function getModal() {
    if (!modal) modal = document.getElementById("cmm-sidebar-help-modal");
    return modal;
  }

  function openHelp() {
    var m = getModal();
    if (!m) return;
    lastFocus = document.activeElement;
    m.removeAttribute("hidden");
    document.body.classList.add("cmm-help-modal-open");
    var closeBtn = m.querySelector(".cmm-sidebar-help-close");
    if (closeBtn) closeBtn.focus();
  }

  function closeHelp() {
    var m = getModal();
    if (!m) return;
    m.setAttribute("hidden", "");
    document.body.classList.remove("cmm-help-modal-open");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function initSidebarHelp() {
    document.querySelectorAll(".cmm-sidebar-info-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        openHelp();
      });
    });

    document.querySelectorAll("[data-cmm-help-close]").forEach(function (el) {
      el.addEventListener("click", closeHelp);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && getModal() && !getModal().hasAttribute("hidden")) {
        closeHelp();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSidebarHelp);
  } else {
    initSidebarHelp();
  }
})();
