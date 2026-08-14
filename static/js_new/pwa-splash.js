(function () {
  var STORAGE_KEY = 'topteen_pwa_launch_shown';

  function isStandalonePwa() {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      window.matchMedia('(display-mode: fullscreen)').matches ||
      window.navigator.standalone === true
    );
  }

  function shouldShowLaunchScreen() {
    if (!isStandalonePwa()) {
      return false;
    }
    try {
      return window.sessionStorage.getItem(STORAGE_KEY) !== '1';
    } catch (err) {
      return true;
    }
  }

  function markLaunchScreenShown() {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, '1');
    } catch (err) {
      /* ignore */
    }
  }

  function forceCleanup() {
    document.documentElement.classList.remove('pwa-launch-active');
    try {
      document.documentElement.style.removeProperty('overflow');
      if (document.body) {
        document.body.style.removeProperty('overflow');
      }
    } catch (err) {
      /* ignore */
    }
    var splash = document.getElementById('pwa-launch-screen');
    if (!splash) {
      return;
    }
    splash.hidden = true;
    splash.classList.remove('is-hiding');
    splash.setAttribute('aria-hidden', 'true');
  }

  function showSplash() {
    var splash = document.getElementById('pwa-launch-screen');
    if (!splash) {
      return null;
    }
    document.documentElement.classList.add('pwa-launch-active');
    splash.hidden = false;
    splash.classList.remove('is-hiding');
    splash.setAttribute('aria-hidden', 'false');
    return splash;
  }

  if (!shouldShowLaunchScreen()) {
    forceCleanup();
    return;
  }

  var splash = showSplash();
  if (!splash) {
    forceCleanup();
    return;
  }

  var progressBar = document.getElementById('pwa-launch-progress');
  var progressRoot = splash.querySelector('.pwa-launch-screen__loader');
  var minVisibleMs = 1400;
  var maxVisibleMs = 4000;
  var startedAt = Date.now();
  var hidden = false;
  var progress = 0;
  var progressTimer = null;

  function setProgress(value) {
    progress = Math.max(0, Math.min(100, value));
    if (progressBar) {
      progressBar.style.width = progress + '%';
    }
    if (progressRoot) {
      progressRoot.setAttribute('aria-valuenow', String(Math.round(progress)));
    }
  }

  function tickProgress() {
    if (hidden) {
      return;
    }
    var elapsed = Date.now() - startedAt;
    var target = Math.min(94, 12 + (elapsed / maxVisibleMs) * 82);
    if (target > progress) {
      setProgress(target);
    }
    progressTimer = window.setTimeout(tickProgress, 100);
  }

  tickProgress();

  function hideSplash() {
    if (hidden) {
      return;
    }
    hidden = true;
    if (progressTimer) {
      window.clearTimeout(progressTimer);
    }
    setProgress(100);
    markLaunchScreenShown();
    splash.classList.add('is-hiding');
    window.setTimeout(function () {
      forceCleanup();
    }, 420);
  }

  function scheduleHide() {
    var elapsed = Date.now() - startedAt;
    window.setTimeout(hideSplash, Math.max(0, minVisibleMs - elapsed));
  }

  if (document.readyState === 'complete') {
    scheduleHide();
  } else {
    window.addEventListener('load', scheduleHide, { once: true });
  }

  window.setTimeout(hideSplash, maxVisibleMs);

  window.addEventListener('pageshow', function () {
    if (!shouldShowLaunchScreen()) {
      forceCleanup();
    }
  });

  window.addEventListener('pagehide', forceCleanup);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden' && hidden) {
      forceCleanup();
    }
  });
})();
