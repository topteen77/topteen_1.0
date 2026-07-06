(function () {
  function isStandalonePwa() {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      window.matchMedia('(display-mode: fullscreen)').matches ||
      window.navigator.standalone === true
    );
  }

  if (!isStandalonePwa()) {
    return;
  }

  var splash = document.getElementById('pwa-launch-screen');
  if (!splash) {
    return;
  }

  var minVisibleMs = 1600;
  var maxVisibleMs = 4000;
  var startedAt = Date.now();
  var hidden = false;

  document.documentElement.classList.add('pwa-launch-active');
  splash.hidden = false;

  function hideSplash() {
    if (hidden) {
      return;
    }
    hidden = true;
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
