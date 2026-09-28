/* The Legacy — offline service worker (read-only app)
   Rule: the screen never waits for the network.
   - App page: the saved copy is shown at once; a fresh copy is fetched in the
     background for the next opening. A new app version (new VERSION below)
     installs itself and reloads the page once when online.
   - Fonts and PDF libraries: saved copy, else network with a short limit, else skipped. */
const VERSION = "the-legacy-e7c3b33b";
const APP = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./icon-maskable-512.png", "./apple-touch-icon.png"];
const EXTERNAL = [
  "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
  "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Hanken+Grotesk:wght@300;400;500;600&display=swap"
];

function timedFetch(input, init, ms) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  return fetch(input, Object.assign({}, init || {}, { signal: ctl.signal })).finally(() => clearTimeout(t));
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    await Promise.all(APP.map(async u => { const r = await fetch(new Request(u, { cache: "reload" })); if (!r.ok) throw new Error(u); await cache.put(u, r); }));
    // carry over fonts and libraries already saved by the previous version
    for (const key of await caches.keys()) {
      if (key === VERSION) continue;
      const old = await caches.open(key);
      for (const req of await old.keys()) if (!req.url.startsWith(self.location.origin)) { const r = await old.match(req); if (r) await cache.put(req, r); }
    }
    await Promise.all(EXTERNAL.map(async url => {
      if (await cache.match(url)) return;
      try { const res = await timedFetch(url, { mode: "cors" }, 15000); if (res.ok) await cache.put(url, res); } catch (e) {}
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

async function savedPage() {
  const c = await caches.open(VERSION);
  return (await c.match("./index.html")) || (await c.match("./")) || (await caches.match("./index.html")) || (await caches.match("./"));
}
async function refreshPage() {
  try {
    const res = await timedFetch(new Request("./index.html", { cache: "no-store" }), {}, 20000);
    if (res && res.ok) { const c = await caches.open(VERSION); await c.put("./index.html", res.clone()); await c.put("./", res); }
  } catch (e) {}
}

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  if (sameOrigin && /\/(data|key)\.enc$/.test(url.pathname)) return; // the page fetches these itself, with a time limit
  const cacheable = sameOrigin || /(^|\.)fonts\.(googleapis|gstatic)\.com$/.test(url.hostname) || url.hostname === "cdnjs.cloudflare.com";
  if (!cacheable) return;

  if (req.mode === "navigate") {
    event.respondWith((async () => {
      const saved = await savedPage();
      if (saved) { event.waitUntil(refreshPage()); return saved; }
      try { return await timedFetch(req.url.split("#")[0], { cache: "no-store" }, 20000); }
      catch (e) { return new Response("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><body style='background:#1B3924;color:#F3EEDF;font:16px -apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center;padding:24px'>Connexion nécessaire pour la toute première ouverture de The Legacy.</body>", { headers: { "Content-Type": "text/html; charset=utf-8" } }); }
    })());
    return;
  }
  event.respondWith((async () => {
    const hit = await caches.match(req, { ignoreVary: true });
    if (hit) return hit;
    try {
      const res = await timedFetch(req, {}, sameOrigin ? 15000 : 4000);
      if (res && (res.ok || res.type === "opaque")) { const c = await caches.open(VERSION); c.put(req, res.clone()); }
      return res;
    } catch (e) {
      if (sameOrigin) return Response.error();
      const type = /\.js(\?|$)/.test(url.pathname) ? "text/javascript" : url.hostname.startsWith("fonts.googleapis") ? "text/css" : "application/octet-stream";
      return new Response("", { status: 200, headers: { "Content-Type": type } });
    }
  })());
});
