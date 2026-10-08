/* Legacy Shaper — client app service worker.
   The app opens instantly and offline; collection data never passes through this cache (Supabase is always live). */
const VERSION = "ls-client-0b47d5dd";
const APP = ["./", "./index.html", "./manifest.webmanifest", "./apple-touch-icon.png", "./icon-192.png", "./icon-512.png", "./room-chair.webp", "./room-parquet.jpg"];
const EXTERNAL = [
  "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js",
  "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Hanken+Grotesk:wght@300;400;500;600&display=swap"
];
const within = (p, ms) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms))]);
self.addEventListener("install", e => { e.waitUntil((async () => {
  const c = await caches.open(VERSION);
  await Promise.all(APP.map(async u => { try { const r = await fetch(new Request(u, { cache: "reload" })); if (r.ok) await c.put(u, r); } catch (err) {} }));
  await Promise.all(EXTERNAL.map(async u => { try { const r = await fetch(u, { mode: "cors" }); if (r.ok) await c.put(u, r); } catch (err) {} }));
  self.skipWaiting();
})()); });
self.addEventListener("activate", e => { e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k.startsWith("ls-client-") && k !== VERSION) await caches.delete(k);
  await self.clients.claim();
})()); });
self.addEventListener("fetch", e => {
  const req = e.request; if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.hostname.endsWith("supabase.co")) return;
  if (req.mode === "navigate") { e.respondWith((async () => {
    // fresh page when the network answers quickly; otherwise (airplane mode, Wi-Fi without internet) the copy kept here
    try { const r = await within(fetch(req, { cache: "no-store" }), 3500); if (r.ok) { const c = await caches.open(VERSION); c.put("./index.html", r.clone()); } return r; }
    catch (err) { return (await caches.match("./index.html", { ignoreSearch: true })) || (await caches.match("./", { ignoreSearch: true })) || Response.error(); }
  })()); return; }
  e.respondWith((async () => { const hit = await caches.match(req); if (hit) return hit;
    try { const r = await within(fetch(req), 15000); const ok = r.ok || r.type === "opaque";
      if (ok && (url.origin === self.location.origin || EXTERNAL.includes(req.url) || url.hostname === "fonts.gstatic.com")) { const c = await caches.open(VERSION); c.put(req, r.clone()); }
      return r; }
    catch (err) { return Response.error(); } })());
});
