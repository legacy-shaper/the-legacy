/* The Legacy — offline service worker (read-only app)
   Rule: never let the screen wait on a bad network. Every network attempt has a
   short time limit; past it, the saved copy is used. */
const VERSION = "the-legacy-v4";
const APP = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./icon-maskable-512.png", "./apple-touch-icon.png"];
const EXTERNAL = [
  "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
  "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Hanken+Grotesk:wght@300;400;500;600&display=swap"
];
const PAGE_WAIT = 2500;   // ms before the app page falls back to the saved copy
const ASSET_WAIT = 4000;  // ms before a missing font/library is skipped

function timedFetch(input, init, ms) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  return fetch(input, Object.assign({}, init, { signal: ctl.signal })).finally(() => clearTimeout(t));
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    await cache.addAll(APP);
    await Promise.all(EXTERNAL.map(async url => {
      try { const res = await timedFetch(url, { mode: "cors" }, 15000); if (res.ok) await cache.put(url, res); } catch (e) { /* retried at runtime */ }
    }));
    // keep the fonts already downloaded by the previous version
    for (const key of await caches.keys()) {
      if (key === VERSION) continue;
      const old = await caches.open(key);
      for (const req of await old.keys()) if (/fonts\.gstatic\.com|fonts\.googleapis\.com|cdnjs\.cloudflare\.com/.test(req.url) && !(await cache.match(req))) {
        const r = await old.match(req); if (r) await cache.put(req, r);
      }
    }
    self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key !== VERSION) await caches.delete(key);
    await self.clients.claim();
  })());
});

async function savedPage() {
  return (await caches.match("./index.html")) || (await caches.match("./"));
}

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  if (sameOrigin && /\/(data|key)\.enc$/.test(url.pathname)) return; // handled (with its own time limit) by the page
  const cacheable = sameOrigin || /(^|\.)fonts\.(googleapis|gstatic)\.com$/.test(url.hostname) || url.hostname === "cdnjs.cloudflare.com";
  if (!cacheable) return;

  // App page: fresh copy if the network answers quickly, otherwise the saved copy at once.
  if (req.mode === "navigate") {
    event.respondWith((async () => {
      const saved = await savedPage();
      const net = timedFetch(new Request(req.url.split("#")[0], { cache: "no-store", credentials: "same-origin" }), {}, saved ? PAGE_WAIT : 20000)
        .then(async res => { if (res && res.ok) { const c = await caches.open(VERSION); await c.put("./index.html", res.clone()); } return res; });
      try { const res = await net; if (res && res.ok) return res; return saved || res; }
      catch (e) { return saved || new Response("<!doctype html><meta charset=utf-8><body style='background:#1B3924;color:#F3EEDF;font:16px sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;padding:24px'>Connexion nécessaire pour la toute première ouverture de The Legacy.</body>", { headers: { "Content-Type": "text/html; charset=utf-8" } }); }
    })());
    return;
  }
  // Everything else: saved copy first; otherwise network with a time limit; never block the page.
  event.respondWith((async () => {
    const hit = await caches.match(req);
    if (hit) return hit;
    try {
      const res = await timedFetch(req, {}, sameOrigin ? 15000 : ASSET_WAIT);
      if (res && (res.ok || res.type === "opaque")) { const c = await caches.open(VERSION); c.put(req, res.clone()); }
      return res;
    } catch (e) {
      if (sameOrigin) return Response.error();
      const type = /\.js(\?|$)/.test(url.pathname) ? "text/javascript" : url.hostname.startsWith("fonts.googleapis") ? "text/css" : "application/octet-stream";
      return new Response("", { status: 200, headers: { "Content-Type": type } }); // skip the font/library, show the app anyway
    }
  })());
});
