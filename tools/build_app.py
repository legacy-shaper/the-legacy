#!/usr/bin/env python3
"""Build the Supabase edition of The Legacy into app/ (index.html, sw.js, manifest).
   page = app-head + master + app-tail ; data lives in Supabase (project the-legacy)."""
import hashlib, os, json
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = lambda f: open(os.path.join(R, "tools", f), encoding="utf-8").read()
head, body, tail = T("app-head.html"), T("master.html"), T("app-tail.html")
page = head + body + tail
sw = T("app-sw.template.js")
build = hashlib.sha1(page.encode() + sw.encode()).hexdigest()[:8]
page = page.replace("</body></html>", f'<div id="buildTag" style="position:fixed;right:10px;bottom:calc(6px + env(safe-area-inset-bottom,0px));font:9px/1 -apple-system,sans-serif;color:rgba(243,238,223,.22);z-index:61;pointer-events:none">v{build}</div>\n<style>body:not(.home-on) #buildTag{{display:none}}</style>\n</body></html>')
os.makedirs(os.path.join(R, "app"), exist_ok=True)
open(os.path.join(R, "app", "index.html"), "w", encoding="utf-8").write(page)
open(os.path.join(R, "app", "sw.js"), "w").write(sw.replace("__BUILD__", build))
m = json.load(open(os.path.join(R, "manifest.webmanifest")))
m.update({"description": "The Legacy — Legacy Shaper Collection - FZCO", "start_url": "./", "scope": "./",
          "icons": [{**i, "src": "../" + i["src"]} for i in m["icons"]]})
json.dump(m, open(os.path.join(R, "app", "manifest.webmanifest"), "w"), ensure_ascii=False, indent=2)
print("build", build)
