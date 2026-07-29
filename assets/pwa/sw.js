/* IRconnect service worker.
 * Deliberately conservative: it NEVER caches the live NiceGUI app (its websocket + versioned assets
 * must always be fresh, or an install would serve a stale UI). It only precaches our own /pwa/ art +
 * an offline fallback, serves navigations network-first, and falls back to /pwa/offline.html when the
 * network is unreachable. That's enough to make the app installable without risking staleness.
 */
const CACHE = 'irconnect-shell-v2';
const OFFLINE = '/pwa/offline.html';
const PRECACHE = [OFFLINE, '/pwa/icon-192.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Our own static art: cache-first (safe — it's versioned by content and rarely changes).
  if (url.pathname.startsWith('/pwa/')) {
    event.respondWith(caches.match(req).then((r) => r || fetch(req)));
    return;
  }

  // App navigations: network-first, offline fallback. Everything else passes straight through.
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
  }
});

// Web Push: render the incoming payload as a notification.
self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data && event.data.text() }; }
  const title = data.title || 'IRconnect';
  event.waitUntil(self.registration.showNotification(title, {
    body: data.body || '',
    icon: '/pwa/icon-192.png',
    badge: '/pwa/icon-192.png',
    tag: data.tag || 'lighthouse',
    renotify: true,
    data: { url: data.url || '/' },
  }));
});

// Tapping a notification focuses an open IRconnect tab or opens one.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil((async () => {
    const wins = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const w of wins) { if (w.url.startsWith(self.location.origin) && 'focus' in w) return w.focus(); }
    if (clients.openWindow) return clients.openWindow(target);
  })());
});
