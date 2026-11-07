// QuickQueue service worker.
// Only shows a friendly offline page when there is no internet.
// Pages are NOT cached, so users always see live queue data and no personal data is stored on the phone.
const CACHE = 'quickqueue-v1';
const OFFLINE_URL = '/offline/';
const PRECACHE = [OFFLINE_URL, '/static/pwa/icon-192.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE_URL)));
  }
});
