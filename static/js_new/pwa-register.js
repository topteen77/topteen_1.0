(function () {
  if (!('serviceWorker' in navigator)) {
    return;
  }

  var version = document.documentElement.getAttribute('data-pwa-version') || '1';

  function showUpdateBanner(registration) {
    var banner = document.getElementById('pwa-update-banner');
    if (!banner) {
      return;
    }
    banner.hidden = false;
    var refreshBtn = banner.querySelector('[data-pwa-refresh]');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function () {
        if (registration.waiting) {
          registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
        window.location.reload();
      });
    }
  }

  window.addEventListener('load', function () {
    navigator.serviceWorker
      .register('/service-worker.js?v=' + encodeURIComponent(version), { scope: '/' })
      .then(function (registration) {
        if (registration.waiting && navigator.serviceWorker.controller) {
          showUpdateBanner(registration);
        }

        registration.addEventListener('updatefound', function () {
          var installing = registration.installing;
          if (!installing) {
            return;
          }
          installing.addEventListener('statechange', function () {
            if (
              installing.state === 'installed' &&
              navigator.serviceWorker.controller
            ) {
              showUpdateBanner(registration);
            }
          });
        });
      })
      .catch(function (err) {
        console.warn('[PWA] Service worker registration failed:', err);
      });
  });

  navigator.serviceWorker.addEventListener('controllerchange', function () {
    if (document.getElementById('pwa-update-banner')) {
      window.location.reload();
    }
  });
})();
