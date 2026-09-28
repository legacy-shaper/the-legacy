/* The Legacy — offline service worker (read-only app) */
const VERSION = "the-legacy-v3";
const APP = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./icon-maskable-512.png", "./apple-touch-icon.png"];
const EXTERNAL = [
  "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
  "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Hanken+Grotesk:wght@300;400;500;600&display=swap"
];

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    await cache.addAll(APP);
    await Promise.all(EXTERNAL.map(async url => {
      try { const res = await fetch(url, { mode: "cors" }); if (res.ok) await cache.put(url, res); } catch (e) { /* retried at runtime */ }
    }));
    self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key !== VERSION) await caches.delete(key);
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  if (sameOrigin && /\/(data|key)\.enc$/.test(url.pathname)) return; // always live, never cached here
  const cacheable = sameOrigin || /(^|\.)fonts\.(googleapis|gstatic)\.com$/.test(url.hostname) || url.hostname === "cdnjs.cloudflare.com";
  if (!cacheable) return;

  // App page: network first (to get updates), cache when offline.
  if (req.mode === "navigate") {
    event.respondWith((async () => {
      try { const res = await fetch(new Request(req.url.split("#")[0], { cache: "no-store", credentials: "same-origin" })); if (res.ok) { const c = await caches.open(VERSION); c.put("./index.html", res.clone()); } return res; }
      catch (e) { return (await caches.match("./index.html")) || (await caches.match("./")); }
    })());
    return;
  }
  // Everything else: cache first, then network (and remember it).
  event.respondWith((async () => {
    const hit = await caches.match(req);
    if (hit) return hit;
    try {
      const res = await fetch(req);
      if (res && (res.ok || res.type === "opaque")) { const c = await caches.open(VERSION); c.put(req, res.clone()); }
      return res;
    } catch (e) { return hit || Response.error(); }
  })());
});
