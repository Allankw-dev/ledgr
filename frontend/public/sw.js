// Ledgr service worker — deliberately minimal and hand-written rather than
// build-tool-generated: it exists to satisfy PWA installability criteria
// (a fetch handler is required) and to make repeat visits feel instant by
// caching the static app shell, not to provide full offline data access.
// API requests (anything under /api/) are always network-only — showing
// stale fee balances or invoice data from a cache would be actively
// misleading in a finance app, so that's a deliberate exclusion, not an
// oversight.

const CACHE_NAME = 'ledgr-shell-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Only ever cache same-origin GET requests. Never intercept the API —
  // financial data must always come from the network, never a cache.
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) {
    return;
  }

  // Navigations (loading a page/route): try the network first so a user
  // with connectivity always gets the current app, falling back to the
  // cached shell only when offline.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request).then((cached) => cached || caches.match('/')))
    );
    return;
  }

  // Static assets (JS/CSS/images/fonts): cache-first for speed, with a
  // network fallback that also refreshes the cache for next time.
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      });
    })
  );
});
