/**
 * Student dashboard / resume shell: desktop sidebar collapse.
 * Sidebar is open by default on desktop (≥992px); closed on mobile/tablet.
 */
(function () {
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

    var open = shell.classList.contains('sidebar-open');
    var icon = desktopToggle.querySelector('i');
    if (icon) {
      icon.className = open ? 'bx bx-chevrons-left' : 'bx bx-menu';
    }
    desktopToggle.classList.toggle('std-shell-sidebar-toggle--open', open);
    desktopToggle.setAttribute('aria-label', open ? 'Close sidebar' : 'Open sidebar');
    desktopToggle.setAttribute('title', open ? 'Close sidebar' : 'Open sidebar');
  }

  function setSidebarOpen(isOpen) {
    var shell = getShell();
    if (!shell) return;

    shell.classList.toggle('sidebar-open', !!isOpen);
    updateToggleUi();
  }

  function ensureSidebarDefaultState() {
    setSidebarOpen(mq.matches);
  }

  function toggleSidebar() {
    var shell = getShell();
    if (!shell) return;
    if (!mq.matches) return;

    shell.classList.toggle('sidebar-open');
    updateToggleUi();
  }

  document.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest ? e.target.closest('#studentSidebarToggleDesktop') : null;
    if (!btn) return;
    e.preventDefault();
    toggleSidebar();
  });

  // Global close handler for Bootstrap modals (e.g., "Refer/Invite friends")
  document.addEventListener('click', function (e) {
    if (!e.target || !e.target.closest) return;
    var closeBtn = e.target.closest('[data-bs-dismiss="modal"], .referPopupClose');
    if (!closeBtn) return;

    var modalEl = closeBtn.closest('.modal');
    if (!modalEl) return;

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

    window.setTimeout(function () {
      var backdrops = document.querySelectorAll('.modal-backdrop');
      backdrops.forEach(function (b) { try { b.remove(); } catch (e2) {} });
      document.body.classList.remove('modal-open');
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
    }, 150);
  }, true);

  mq.addEventListener('change', function () {
    ensureSidebarDefaultState();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureSidebarDefaultState);
  } else {
    ensureSidebarDefaultState();
  }
})();
