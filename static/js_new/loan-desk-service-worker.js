/* Loan Desk PWA service worker — scoped to /loan-desk/ */
const CACHE_VERSION = '__PWA_CACHE_VERSION__';
const STATIC_CACHE = 'loan-desk-static-' + CACHE_VERSION;
const OFFLINE_ASSETS = [
  '/loan-desk/',
  '/loan-desk/login/',
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function (cache) {
      return Promise.all(
        OFFLINE_ASSETS.map(function (url) {
          return cache.add(url).catch(function () {});
        })
      );
    })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys
          .filter(function (key) {
            return key.indexOf('loan-desk-static-') === 0 && key !== STATIC_CACHE;
          })
          .map(function (key) {
            return caches.delete(key);
          })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') {
    return;
  }
  var url;
  try {
    url = new URL(request.url);
  } catch (e) {
    return;
  }
  if (url.origin !== self.location.origin) {
    return;
  }
  if (url.pathname.indexOf('/loan-desk/') !== 0) {
    return;
  }
  // Network-first for HTML/API; cache shell on failure
  event.respondWith(
    fetch(request)
      .then(function (response) {
        return response;
      })
      .catch(function () {
        return caches.match(request).then(function (cached) {
          return cached || caches.match('/loan-desk/login/');
        });
      })
  );
});
