/**
 * Resume Studio light/dark theme. html[data-theme="light"|"dark"] + admitcv-resume-flow.css
 * Storage: localStorage topteen_resume_studio_theme — if unset, follows prefers-color-scheme.
 */
(function () {
  var KEY = 'topteen_resume_studio_theme';

  function readStored() {
    try {
      return localStorage.getItem(KEY);
    } catch (e) {
      return null;
    }
  }

  function systemDefault() {
    try {
      return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    } catch (e) {
      return 'dark';
    }
  }

  function initialMode() {
    var s = readStored();
    if (s === 'light' || s === 'dark') return s;
    return systemDefault();
  }

  function applyMode(m) {
    document.documentElement.setAttribute('data-theme', m);
  }

  function setMode(m) {
    if (m !== 'light' && m !== 'dark') return;
    applyMode(m);
    try {
      localStorage.setItem(KEY, m);
    } catch (e) {}
  }

  function getMode() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  }

  function flipMode() {
    setMode(getMode() === 'light' ? 'dark' : 'light');
  }

  if (!document.documentElement.hasAttribute('data-theme')) {
    applyMode(initialMode());
  }

  window.TopTeenResumeTheme = {
    get: getMode,
    set: setMode,
    flip: flipMode
  };

  function syncToggleButton(btn) {
    var i = btn.querySelector('i');
    var isLight = getMode() === 'light';
    if (i) {
      i.className = 'bx ' + (isLight ? 'bx-moon' : 'bx-sun') + ' fs-18';
    }
    btn.setAttribute('aria-label', isLight ? 'Switch to dark mode' : 'Switch to light mode');
    btn.setAttribute('title', isLight ? 'Dark mode' : 'Light mode');
  }

  function bindToggle() {
    var btn = document.getElementById('resumeThemeToggle');
    if (!btn) return;
    btn.addEventListener('click', function () {
      flipMode();
      syncToggleButton(btn);
    });
    syncToggleButton(btn);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindToggle);
  } else {
    bindToggle();
  }
})();
