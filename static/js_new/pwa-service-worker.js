/* TopTeen PWA service worker — cache version injected by Django */
const CACHE_VERSION = '__PWA_CACHE_VERSION__';
const STATIC_CACHE = 'topteen-static-' + CACHE_VERSION;
const OFFLINE_URL = '/offline/';
const OFFLINE_ASSETS = [
  OFFLINE_URL,
  '/static/images_new/general/offline-mode.png',
  /* Resume Builder v2 — hero + CSS cached for mobile & desktop revisits */
  '/static/images_new/general/resume-hero-sm.webp?v=opt1',
  '/static/images_new/general/resume-hero-md.webp?v=opt1',
  '/static/images_new/general/resume-hero.webp?v=opt1',
  '/static/images_new/general/resume-hero.png?v=opt1',
  '/static/resume-builder-v2/styles.css?v=12',
];

const SKIP_PREFIXES = [
  '/admin',
  '/topteenadmin',
  '/api',
  '/user-analytics',
  '/oauth',
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
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys
          .filter(function (key) {
            return key.indexOf('topteen-static-') === 0 && key !== STATIC_CACHE;
          })
          .map(function (key) {
            return caches.delete(key);
          })
      );
    })
  );
  self.clients.claim();
});

function shouldSkip(pathname) {
  for (var i = 0; i < SKIP_PREFIXES.length; i += 1) {
    if (pathname.indexOf(SKIP_PREFIXES[i]) === 0) {
      return true;
    }
  }
  return false;
}

function isNavigationRequest(request) {
  if (request.mode === 'navigate') {
    return true;
  }
  var accept = request.headers.get('accept') || '';
  return accept.indexOf('text/html') !== -1;
}

self.addEventListener('message', function (event) {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') {
    return;
  }

  var url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }
  if (shouldSkip(url.pathname)) {
    return;
  }

  if (url.pathname.indexOf('/static/') === 0) {
    event.respondWith(
      caches.open(STATIC_CACHE).then(function (cache) {
        return cache.match(request).then(function (cached) {
          var networkFetch = fetch(request)
            .then(function (response) {
              if (response && response.ok) {
                cache.put(request, response.clone());
              }
              return response;
            })
            .catch(function () {
              return cached;
            });
          return cached || networkFetch;
        });
      })
    );
    return;
  }

  if (isNavigationRequest(request)) {
    event.respondWith(
      fetch(request).catch(function () {
        return caches.match(request).then(function (cached) {
          return cached || caches.match(OFFLINE_URL);
        });
      })
    );
  }
});
