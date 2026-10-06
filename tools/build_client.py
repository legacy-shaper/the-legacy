#!/usr/bin/env python3
"""Build the Legacy Shaper client app (read-only collection viewer) into client/.
   client/ is self-contained: it is published as the site app.legacy-shaper.com."""
import hashlib, json, os, re, shutil
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = lambda f: open(os.path.join(R, "tools", f), encoding="utf-8").read()
OUT = os.path.join(R, "client")

master = T("master.html")
logos = {k: re.search(r'const ' + k + r' = "(data:image/png;base64,[^"]+)"', master).group(1) for k in ("LOGO_GOLD", "LOGO_GREEN", "LOGO_H")}
import base64, io
from PIL import Image
def recolor(data_url, rgb):
    im = Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGBA")
    a = im.getchannel("A")
    if a.getextrema() == (255, 255):  # no transparency: derive it from darkness
        a = im.convert("L").point(lambda v: 255 - v)
    out = Image.new("RGBA", im.size, rgb + (0,)); out.putalpha(a)
    buf = io.BytesIO(); out.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
logos["LOGO_H"] = recolor(logos["LOGO_H"], (196, 160, 82))
page = T("client.html")
for k, v in logos.items():
    page = page.replace(f'"__{k}__"', json.dumps(v))
assert "__LOGO_" not in page

SW = r'''/* Legacy Shaper — client app service worker.
   The app opens instantly and offline; collection data never passes through this cache (Supabase is always live). */
const VERSION = "ls-client-__BUILD__";
const APP = ["./", "./index.html", "./manifest.webmanifest", "./apple-touch-icon.png", "./icon-192.png", "./icon-512.png"];
const EXTERNAL = [
  "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js",
  "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Hanken+Grotesk:wght@300;400;500;600&display=swap"
];
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
    try { const r = await fetch(req, { cache: "no-store" }); if (r.ok) { const c = await caches.open(VERSION); c.put("./index.html", r.clone()); } return r; }
    catch (err) { return (await caches.match("./index.html", { ignoreSearch: true })) || Response.error(); }
  })()); return; }
  e.respondWith((async () => { const hit = await caches.match(req); if (hit) return hit;
    try { const r = await fetch(req); const ok = r.ok || r.type === "opaque";
      if (ok && (url.origin === self.location.origin || EXTERNAL.includes(req.url) || url.hostname === "fonts.gstatic.com")) { const c = await caches.open(VERSION); c.put(req, r.clone()); }
      return r; }
    catch (err) { return Response.error(); } })());
});
'''
build = hashlib.sha1((page + SW).encode()).hexdigest()[:8]
page = page.replace("</body></html>", f'<div id="buildTag" style="position:fixed;right:10px;bottom:calc(6px + env(safe-area-inset-bottom,0px));font:9px/1 -apple-system,sans-serif;color:rgba(22,36,26,.18);pointer-events:none">v{build}</div>\n</body></html>')

os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)
open(os.path.join(OUT, "sw.js"), "w", encoding="utf-8").write(SW.replace("__BUILD__", build))
for f in ("apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png"):
    shutil.copy(os.path.join(R, f), os.path.join(OUT, f))
manifest = {"name": "Legacy Shaper", "short_name": "Legacy Shaper", "description": "Legacy Shaper — Collection Office",
            "lang": "en", "start_url": "./", "scope": "./", "display": "standalone", "orientation": "any",
            "background_color": "#1B3924", "theme_color": "#1B3924",
            "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                      {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
                      {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
json.dump(manifest, open(os.path.join(OUT, "manifest.webmanifest"), "w"), ensure_ascii=False, indent=2)
open(os.path.join(OUT, "CNAME"), "w").write("app.legacy-shaper.com\n")
open(os.path.join(OUT, "robots.txt"), "w").write("User-agent: *\nDisallow: /\n")
print("build", build)
