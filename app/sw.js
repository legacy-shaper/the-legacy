/* The Legacy (Supabase edition) — service worker
   App shell and libraries are kept for instant, offline opening.
   Data never goes through this cache: every request to Supabase passes straight to the network. */
const VERSION = "the-legacy-app-5a81a967";
const APP = ["./", "./index.html", "./manifest.webmanifest", "./room-chair.webp", "./room-parquet.jpg"];
const EXTERNAL = [
  "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js"
];
self.addEventListener("install", e => { e.waitUntil((async () => {
  const c = await caches.open(VERSION);
  await Promise.all(APP.map(async u => { const r = await fetch(new Request(u, { cache: "reload" })); if (r.ok) await c.put(u, r); }));
  await Promise.all(EXTERNAL.map(async u => { try { const r = await fetch(u, { mode: "cors" }); if (r.ok) await c.put(u, r); } catch (err) {} }));
  self.skipWaiting();
})()); });
self.addEventListener("activate", e => { e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k.startsWith("the-legacy-app-") && k !== VERSION) await caches.delete(k);
  await self.clients.claim();
})()); });
self.addEventListener("fetch", e => {
  const req = e.request; if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.hostname.endsWith("supabase.co")) return;            // data: always live
  if (req.mode === "navigate") { e.respondWith((async () => {
    try { const r = await fetch(req, { cache: "no-store" }); if (r.ok) { const c = await caches.open(VERSION); c.put("./index.html", r.clone()); } return r; }
    catch (err) { return (await caches.match("./index.html", { ignoreSearch: true })) || Response.error(); }
  })()); return; }
  e.respondWith((async () => { const hit = await caches.match(req); if (hit) return hit;
    try { const r = await fetch(req); if (r.ok && (url.origin === self.location.origin || EXTERNAL.includes(req.url))) { const c = await caches.open(VERSION); c.put(req, r.clone()); } return r; }
    catch (err) { return Response.error(); } })());
});
// Notifications: messages from collectors (sent by the support-chat function). Touching one opens the conversation.
self.addEventListener("push", e => {
  let d = {}; try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "The Legacy", {
    body: d.body || "", tag: d.tag || "messages", renotify: true, icon: "../icon-192.png", badge: "../icon-192.png",
    data: { url: d.url || "./#messages" } }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "./#messages";
  const tid = (url.match(/#messages\/([\w-]+)/) || [])[1] || null;
  e.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of all) { if (new URL(c.url).pathname.startsWith(new URL(self.registration.scope).pathname)) { c.postMessage({ type: "open-messages", threadId: tid }); return c.focus(); } }
    return self.clients.openWindow(url);
  })());
});
