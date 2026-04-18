/**
 * Student dashboard / resume shell: desktop sidebar collapse + localStorage.
 * Expects #studentDashboardShell and #studentSidebarToggleDesktop.
 */
(function () {
  var STORAGE_KEY = 'topteen_student_dash_sidebar_collapsed';
  var shell = document.getElementById('studentDashboardShell');
  var desktopToggle = document.getElementById('studentSidebarToggleDesktop');
  if (!shell || !desktopToggle) return;

  var mq = window.matchMedia('(min-width: 992px)');

  function updateToggleUi() {
    var collapsed = shell.classList.contains('sidebar-collapsed');
    var icon = desktopToggle.querySelector('i');
    if (icon) {
      icon.className = collapsed ? 'bx bx-menu' : 'bx bx-chevrons-left';
    }
    desktopToggle.setAttribute('aria-label', collapsed ? 'Open sidebar' : 'Close sidebar');
    desktopToggle.setAttribute('title', collapsed ? 'Open sidebar' : 'Close sidebar');
  }

  function syncFromStorage() {
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

  desktopToggle.addEventListener('click', function () {
    if (!mq.matches) return;
    shell.classList.toggle('sidebar-collapsed');
    try {
      localStorage.setItem(STORAGE_KEY, shell.classList.contains('sidebar-collapsed') ? '1' : '0');
    } catch (e) {}
    updateToggleUi();
  });

  mq.addEventListener('change', syncFromStorage);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncFromStorage);
  } else {
    syncFromStorage();
  }
})();
