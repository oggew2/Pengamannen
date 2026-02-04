const CACHE_NAME = 'borslabbet-v4';
const API_CACHE = 'borslabbet-api-v4';

// Only cache truly static assets that never change
const STATIC_ASSETS = [
  '/icon.svg',
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
      Promise.all(
        keys
          .filter(k => k !== CACHE_NAME && k !== API_CACHE)
          .map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Skip non-GET requests entirely
  if (event.request.method !== 'GET') return;
  
  const url = new URL(event.request.url);
  
  // NEVER cache HTML, JS, or CSS - these change on every deploy
  // This is the main fix for blank screen issues
  if (
    url.pathname === '/' ||
    url.pathname.endsWith('.html') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.css') ||
    url.pathname.startsWith('/src/') ||
    url.pathname.startsWith('/assets/')
  ) {
    // Network only - no caching
    return;
  }
  
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
  
  // Static assets like icons: cache first
  if (STATIC_ASSETS.some(a => url.pathname === a)) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
  // Everything else: network only
});

// Push notification handler
self.addEventListener('push', (event) => {
  let data = { title: 'Börslabbet', body: 'Ny notifikation', url: '/' };
  
  try {
    if (event.data) {
      data = event.data.json();
    }
  } catch (e) {
    console.error('Failed to parse push data:', e);
  }
  
  const options = {
    body: data.body,
    icon: data.icon || '/icon.svg',
    badge: data.badge || '/icon.svg',
    tag: data.tag || 'borslabbet',
    data: { url: data.url || '/' },
    vibrate: [100, 50, 100],
    requireInteraction: false,
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  const url = event.notification.data?.url || '/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // Focus existing window if open
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      // Open new window
      return clients.openWindow(url);
    })
  );
});
