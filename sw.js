// Drum Highway offline cache. Bump VERSION whenever index.html changes so installed copies update.
const VERSION = 'dh-v1';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  // The app itself: network first (so updates arrive), cache when offline.
  if (u.origin === location.origin) {
    e.respondWith(fetch(e.request).then((r) => { const c = r.clone(); caches.open(VERSION).then((ca) => ca.put(e.request, c)); return r; })
      .catch(() => caches.match(e.request).then((r) => r || caches.match('./index.html'))));
    return;
  }
  // Fonts: cache after first use so the app looks right offline.
  if (/fonts\.(googleapis|gstatic)\.com$/.test(u.hostname)) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => { const c = r.clone(); caches.open(VERSION).then((ca) => ca.put(e.request, c)); return r; })));
  }
});
