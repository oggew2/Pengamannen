const CACHE_NAME = 'borslabbet-v2';
const API_CACHE = 'borslabbet-api-v2';

const STATIC_ASSETS = [
  '/',
  '/index.html',
];

// Only cache GET requests for these read-only endpoints
const CACHEABLE_API_ROUTES = [
  '/v1/strategies',
  '/v1/portfolio/rebalance-dates',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => 
      Promise.all(keys.filter(k => !k.startsWith('borslabbet-')).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Skip non-GET requests entirely - never cache POST/PUT/DELETE
  if (event.request.method !== 'GET') {
    return; // Let browser handle it normally
  }
  
  const url = new URL(event.request.url);
  
  // Only cache specific safe API routes
  if (CACHEABLE_API_ROUTES.some(r => url.pathname.startsWith(r))) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(API_CACHE).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  
  // Static assets: cache first
  if (!url.pathname.startsWith('/v1/')) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
  // All other /v1/ requests: let browser handle (no caching)
});
