/**
 * Student dashboard / resume shell: desktop sidebar collapse + localStorage.
 * Works across all student pages after login.
 * Uses event delegation so it doesn't depend on per-page script timing.
 */
(function () {
  var STORAGE_KEY = 'topteen_student_dash_sidebar_collapsed';
  var mq = window.matchMedia('(min-width: 992px)');

  function getShell() {
    return document.getElementById('studentDashboardShell');
  }

  function getDesktopToggle() {
    return document.getElementById('studentSidebarToggleDesktop');
  }

  function updateToggleUi() {
    var shell = getShell();
    var desktopToggle = getDesktopToggle();
    if (!shell || !desktopToggle) return;

    var collapsed = shell.classList.contains('sidebar-collapsed');
    var icon = desktopToggle.querySelector('i');
    if (icon) {
      icon.className = collapsed ? 'bx bx-menu' : 'bx bx-chevrons-left';
    }
    desktopToggle.setAttribute('aria-label', collapsed ? 'Open sidebar' : 'Close sidebar');
    desktopToggle.setAttribute('title', collapsed ? 'Open sidebar' : 'Close sidebar');
  }

  function syncFromStorage() {
    var shell = getShell();
    if (!shell) return;

    if (mq.matches) {
      try {
        if (localStorage.getItem(STORAGE_KEY) === '1') {
          shell.classList.add('sidebar-collapsed');
        } else {
          shell.classList.remove('sidebar-collapsed');
        }
      } catch (e) {
        shell.classList.remove('sidebar-collapsed');
      }
    } else {
      shell.classList.remove('sidebar-collapsed');
    }
    updateToggleUi();
  }

  function toggleSidebarCollapsed() {
    var shell = getShell();
    if (!shell) return;
    if (!mq.matches) return;

    shell.classList.toggle('sidebar-collapsed');
    try {
      localStorage.setItem(STORAGE_KEY, shell.classList.contains('sidebar-collapsed') ? '1' : '0');
    } catch (e) {}
    updateToggleUi();
  }

  document.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest ? e.target.closest('#studentSidebarToggleDesktop') : null;
    if (!btn) return;
    e.preventDefault();
    toggleSidebarCollapsed();
  });

  // Global close handler for Bootstrap modals (e.g., "Refer/Invite friends")
  // Some pages attach modal JS locally; this ensures the X always works.
  document.addEventListener('click', function (e) {
    if (!e.target || !e.target.closest) return;
    var closeBtn = e.target.closest('[data-bs-dismiss="modal"], .referPopupClose');
    if (!closeBtn) return;

    var modalEl = closeBtn.closest('.modal');
    if (!modalEl) return;

    // Prefer Bootstrap's API when available
    try {
      if (window.bootstrap && window.bootstrap.Modal) {
        var inst = window.bootstrap.Modal.getInstance(modalEl);
        if (!inst) inst = new window.bootstrap.Modal(modalEl);
        inst.hide();
      } else {
        modalEl.classList.remove('show');
        modalEl.style.display = 'none';
      }
    } catch (err) {
      modalEl.classList.remove('show');
      modalEl.style.display = 'none';
    }

    // Cleanup any stuck backdrop/body state
    window.setTimeout(function () {
      var backdrops = document.querySelectorAll('.modal-backdrop');
      backdrops.forEach(function (b) { try { b.remove(); } catch (e2) {} });
      document.body.classList.remove('modal-open');
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
    }, 150);
  }, true);

  mq.addEventListener('change', syncFromStorage);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncFromStorage);
  } else {
    syncFromStorage();
  }
})();
