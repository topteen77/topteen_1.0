(function () {
  if (!('serviceWorker' in navigator)) {
    return;
  }

  var version = document.documentElement.getAttribute('data-pwa-version') || '1';
  var refreshing = false;

  function hideUpdateBanner() {
    var banner = document.getElementById('pwa-update-banner');
    if (banner) {
      banner.hidden = true;
    }
  }

  function showUpdateBanner(registration) {
    var banner = document.getElementById('pwa-update-banner');
    if (!banner) {
      return;
    }
    banner.hidden = false;
    var refreshBtn = banner.querySelector('[data-pwa-refresh]');
    if (!refreshBtn || refreshBtn.getAttribute('data-bound') === '1') {
      return;
    }
    refreshBtn.setAttribute('data-bound', '1');
    refreshBtn.addEventListener('click', function () {
      refreshBtn.disabled = true;
      refreshBtn.textContent = 'Updating…';
      if (registration.waiting) {
        // Activate waiting worker; controllerchange will reload once.
        registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        return;
      }
      // No waiting worker — just reload (already on latest or race).
      hideUpdateBanner();
      window.location.reload();
    });
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

  // Reload only after the new SW has taken control (avoids banner loop).
  navigator.serviceWorker.addEventListener('controllerchange', function () {
    if (refreshing) {
      return;
    }
    refreshing = true;
    hideUpdateBanner();
    window.location.reload();
  });
})();
