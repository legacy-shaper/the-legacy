#!/usr/bin/env python3
"""Build the read-only phone/Mac app (index.html + sw.js) from the master source.

  python3 tools/build.py

tools/master.html is the SAME page as the Claude artifact "The Legacy"
(https://claude.ai/artifact/MfqmNZvqdzzQCXTsEQcNG1). Edit it, publish it to the
artifact, then run this script and push. The viewer = viewer-head + master +
viewer-tail (read-only mode via window.LEGACY_VIEWER). sw.js gets a version stamp
so phones install the update and reload once when online.
"""
import hashlib, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = lambda f: open(os.path.join(R, "tools", f), encoding="utf-8").read()
head, body, tail = T("viewer-head.html"), T("master.html"), T("viewer-tail.html")
FONT = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Hanken+Grotesk:wght@300;400;500;600&display=swap">'
assert body.count(FONT) == 1, "font link changed in master.html"
body = body.replace(FONT, FONT.replace('rel="stylesheet"', 'rel="stylesheet" media="print" onload="this.media=\'all\'"'))
for lib in ("html2canvas/1.4.1/html2canvas.min.js", "jspdf/2.5.1/jspdf.umd.min.js"):
    t = f'<script src="https://cdnjs.cloudflare.com/ajax/libs/{lib}"></script>'
    assert body.count(t) == 1, lib
    body = body.replace(t, t.replace("<script ", "<script async "))
page = head + body + tail
sw = T("sw.template.js")
build = hashlib.sha1(page.encode() + sw.encode()).hexdigest()[:8]
page = page.replace("</body></html>", f'<div id="buildTag" style="position:fixed;right:10px;bottom:calc(6px + env(safe-area-inset-bottom,0px));font:9px/1 -apple-system,sans-serif;color:rgba(243,238,223,.22);z-index:61;pointer-events:none">v{build}</div>\n<style>body:not(.home-on) #buildTag{{display:none}}</style>\n</body></html>')
open(os.path.join(R, "index.html"), "w", encoding="utf-8").write(page)
open(os.path.join(R, "sw.js"), "w").write(sw.replace("__BUILD__", build))
print("build", build)
