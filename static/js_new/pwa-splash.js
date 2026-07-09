(function () {
  var STORAGE_KEY = 'topteen_pwa_launch_shown';

  function isStandalonePwa() {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      window.matchMedia('(display-mode: fullscreen)').matches ||
      window.navigator.standalone === true
    );
  }

  function isIOS() {
    return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
  }

  function shouldShowLaunchScreen() {
    if (!isStandalonePwa()) {
      return false;
    }
    /* iOS uses apple-touch-startup-image (logo + tagline) on cold start. */
    if (isIOS()) {
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

  if (!shouldShowLaunchScreen()) {
    return;
  }

  var splash = document.getElementById('pwa-launch-screen');
  if (!splash) {
    return;
  }

  var minVisibleMs = 1400;
  var maxVisibleMs = 3500;
  var startedAt = Date.now();
  var hidden = false;

  document.documentElement.classList.add('pwa-launch-active');
  splash.hidden = false;

  function hideSplash() {
    if (hidden) {
      return;
    }
    hidden = true;
    markLaunchScreenShown();
    splash.classList.add('is-hiding');
    window.setTimeout(function () {
      splash.hidden = true;
      document.documentElement.classList.remove('pwa-launch-active');
    }, 360);
  }

  function scheduleHide() {
    var elapsed = Date.now() - startedAt;
    window.setTimeout(hideSplash, Math.max(0, minVisibleMs - elapsed));
  }

  if (document.readyState === 'complete') {
    scheduleHide();
  } else {
    window.addEventListener('load', scheduleHide);
  }

  window.setTimeout(hideSplash, maxVisibleMs);
})();
