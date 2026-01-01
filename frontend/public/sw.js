const CACHE_NAME = 'borslabbet-v1';
const API_CACHE = 'borslabbet-api-v1';

const STATIC_ASSETS = [
  '/',
  '/index.html',
];

const API_ROUTES = [
  '/strategies',
  '/strategies/sammansatt_momentum',
  '/strategies/trendande_varde',
  '/strategies/trendande_utdelning',
  '/strategies/trendande_kvalitet',
  '/portfolio/sverige',
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
      Promise.all(keys.filter(k => k !== CACHE_NAME && k !== API_CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // API requests: network first, cache fallback
  if (url.pathname.startsWith('/api') || API_ROUTES.some(r => url.pathname.includes(r))) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(API_CACHE).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  
  // Static assets: cache first
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
