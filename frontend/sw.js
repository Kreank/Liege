/* Service Worker für Liege.
   Cache-first für static Assets (Icons, Phaser CDN), Netzwerk-first für alles andere.
   Versionierung über CACHE_NAME — bumpen wenn UI/JS gross umgebaut wird, damit alte Clients aktualisieren. */

const CACHE_NAME = 'liege-v2';
const STATIC_ASSETS = [
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/icon-512-maskable.png',
  '/static/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  // Nur GET cachen
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // WebSockets, API-Auth, Admin und auth/me niemals cachen
  if (url.pathname.startsWith('/ws') ||
      url.pathname.startsWith('/auth/') ||
      url.pathname.startsWith('/admin')) {
    return;
  }

  // Static assets (Icons): cache-first
  if (url.pathname.startsWith('/static/icon') ||
      url.pathname === '/static/apple-touch-icon.png' ||
      url.pathname.startsWith('/assets/')) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
        return resp;
      }).catch(() => caches.match(req)))
    );
    return;
  }

  // Phaser CDN: cache-first (Versions-stable in der URL)
  if (url.hostname === 'cdn.jsdelivr.net') {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
        return resp;
      }))
    );
    return;
  }

  // Alles andere: Network-first mit Cache-Fallback
  event.respondWith(
    fetch(req).catch(() => caches.match(req))
  );
});
