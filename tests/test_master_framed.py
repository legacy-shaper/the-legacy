#!/usr/bin/env python3
"""Artwork sheet in The Legacy: « Dimensions de l’œuvre » + optional « Dimensions avec cadre » (paintings, works on paper,
   photographs; hidden for sculptures, installations, furniture), saved on the artwork and printed on the PDF sheet (cm + inches).
   Run: python3 tests/test_master_framed.py"""
import json, os, sys, threading, http.server, functools, re
from playwright.sync_api import sync_playwright
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = open(os.path.join(R, "tests", "master_mock.js"), encoding="utf-8").read()
SEED = {"docs": [
    {"coll": "settings", "id": "company", "data": {"name": "Legacy Shaper Collection - FZCO"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "artworks", "id": "p1", "data": {"id": "p1", "artist": "Pierre Soulages", "title": "Peinture", "year": "1959", "category": "painting", "dimensions": "130 × 97 cm"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "artworks", "id": "s1", "data": {"id": "s1", "artist": "Alexander Calder", "title": "Acrobats (II)", "year": "1944", "category": "sculpture", "dimensions": "40 × 30 × 20 cm"}, "updated_at": "2026-10-01T00:00:00Z"}],
    "tables": {"collections": [], "collection_members": [], "profiles": [{"id": "u9", "email": "dylan@legacy-shaper.com", "role": "admin"}]}, "files": {}}
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8771), functools.partial(Quiet, directory=R))
threading.Thread(target=srv.serve_forever, daemon=True).start()
ok = 0
def check(c, label):
    global ok
    if not c: print("FAIL:", label); srv.shutdown(); sys.exit(1)
    ok += 1; print("ok  ", label)
errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(service_workers="block", viewport={"width": 1400, "height": 900})
    ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
    ctx.route(re.compile(r"https://(cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com)/.*"), lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
    p = ctx.new_page(); p.add_init_script(f"window.__MASTER_SEED={json.dumps(SEED)};"); p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto("http://127.0.0.1:8771/app/"); p.wait_for_selector("#gEmail")
    p.fill("#gEmail", "dylan@legacy-shaper.com"); p.fill("#gPass", "good-pass"); p.click("#gForm button[type=submit]"); p.wait_for_selector("#gCode")
    p.fill("#gCode", "123456"); p.click("#gForm button[type=submit]")
    p.wait_for_function("typeof state!=='undefined' && state.artworks && state.artworks.p1", timeout=15000)
    p.evaluate("state.curArt='p1'; switchView('artworks'); document.body.classList.add('alt-detail'); renderAlt()"); p.wait_for_selector("#k_dimsFramed")
    check("Dimensions de l’œuvre" in p.inner_text("#detail") and p.locator("#k_dimsFramed").is_visible(), "painting: « Dimensions de l’œuvre » and « Dimensions avec cadre » side by side")
    check(p.get_attribute("#k_dimsFramed", "placeholder").startswith("Facultatif"), "the framed field is optional")
    p.fill("#k_dimsFramed", "152 × 119 cm"); p.wait_for_timeout(300)
    check(p.evaluate("state.artworks.p1.dimsFramed") == "152 × 119 cm", "framed dimensions saved on the artwork")
    html = p.evaluate("ficheHTML(state.artworks.p1,'',false)")
    check("130 × 97 cm" in html and "Framed: 152 × 119 cm" in html and "Framed: 59 7/8 x 46 7/8 in" in html, "PDF sheet: work dimensions, then framed dimensions in cm and inches")
    p.select_option("#k_category", "sculpture"); p.wait_for_timeout(200)
    check(p.locator("#k_dimsFramed").is_hidden(), "category changed to sculpture: the framed field disappears")
    check("Framed" not in p.evaluate("ficheHTML(state.artworks.p1,'',false)"), "…and is not printed for a sculpture")
    p.select_option("#k_category", "paper"); p.wait_for_timeout(200)
    check(p.locator("#k_dimsFramed").is_visible() and p.input_value("#k_dimsFramed") == "152 × 119 cm", "back to a work on paper: the field and its value come back")
    p.evaluate("state.curArt='s1'; renderAlt()"); p.wait_for_selector("#k_category")
    check(p.locator("#k_dimsFramed").is_hidden(), "a sculpture opens without the framed field")
    p.evaluate("state.curArt='p1'; renderAlt()"); p.wait_for_selector("#k_dimsFramed")
    p.fill("#k_dimsFramed", ""); p.wait_for_timeout(200)
    check("Framed" not in p.evaluate("ficheHTML(state.artworks.p1,'',false)"), "left empty: nothing printed")
    check(not errors, "no script error" + (": " + "; ".join(errors[:3]) if errors else ""))
    b.close()
srv.shutdown()
print(f"\nALL {ok} CHECKS PASSED")
