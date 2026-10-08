#!/usr/bin/env python3
"""Client app: the read-only « Packing & crate » block of a work (artworks.crating, SQL 006) and its crate photos.
   Run: python3 tests/test_client_crating.py"""
import json, os, sys, threading, http.server, functools, io, zipfile, re
from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(R, "client")
MOCK = open(os.path.join(R, "tests", "client_mock.js"), encoding="utf-8").read()
JSZIP = open("/opt/npm-tools/node_modules/jszip/dist/jszip.min.js", encoding="utf-8").read()
demo = json.load(open(os.path.join(R, "tests", "demo.json"), encoding="utf-8"))
CID = demo["coll"]["id"]; OTHER = "b0000000-0000-4000-8000-0000000000bb"

docs = [
  dict(id="d1", kind="purchase_invoice", name="Invoice - Corvani.pdf", mime="application/pdf", size=1200, storage_path="files/d1", artwork_id="aur-05", expense_id=None, collection_id=CID, visible_to_client=True, created_at="2025-02-21T10:00:00Z"),
  dict(id="d2", kind="invoice", name="Internal note.pdf", mime="application/pdf", size=900, storage_path="files/d2", artwork_id="aur-05", expense_id=None, collection_id=CID, visible_to_client=False, created_at="2025-02-22T10:00:00Z"),
  dict(id="d3", kind="invoice", name="Other collection.pdf", mime="application/pdf", size=900, storage_path="files/d3", artwork_id="b-1", expense_id=None, collection_id=OTHER, visible_to_client=True, created_at="2025-02-22T10:00:00Z"),
]
hidden_exp = dict(id="demo-exp-hidden", date="2025-03-01", label="Internal commission", category="commission", amount=99999, currency="USD", supplier="x", artwork_id="aur-03", collection_id=CID, visible_to_client=False, status="paid")
# co-owned work (names + % only reach the client) and a work whose split Dylan hid
for w in demo["works"]:
    if w["id"] == "aur-04": w.update(ownership_share=60, co_owners=[dict(name="Jonathan Wahnich", share=25), dict(name="Fondation X", share=15)], ownership_visible=True)
    if w["id"] == "aur-02": w.update(ownership_share=None, co_owners=[], ownership_visible=False)
other_work = dict(demo["works"][0], id="b-1", collection_id=OTHER, title="Secret Work", artist="Other Artist", ref="B-1")
SEED = {
  "users": [dict(id="u1", email="client@example.com", role="client"), dict(id="u2", email="other@example.com", role="client"),
            dict(id="u9", email="dylan@legacy-shaper.com", role="admin", totp=True)],
  "members": [dict(user_id="u1", collection_id=CID), dict(user_id="u2", collection_id=OTHER)],
  "tables": {
    "profiles": [dict(id="u1", role="client"), dict(id="u2", role="client"), dict(id="u9", role="admin")],
    "collections": [demo["coll"], dict(id=OTHER, slug="other", name="Collection B", subtitle=None, display_currency="USD", cover_artwork_id=None)],
    "artworks": demo["works"] + [other_work],
    "artwork_views": demo["views"] + [dict(id="vb1", artwork_id="b-1", sort=0, photo="demo/aur-02.jpg")],
    "expenses": demo["expenses"] + [hidden_exp],
    "documents": docs,
  },
  "files": {"files/d1": "%PDF-1.4 demo invoice", "files/cr1": "%PDF-1.4 packing list"},
}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8772), functools.partial(Quiet, directory=CLIENT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8772/"

ok = 0
def check(cond, label):
    global ok
    if not cond: print("FAIL:", label); srv.shutdown(); sys.exit(1)
    ok += 1; print("ok  ", label)

def new_page(ctx, net=True):
    p = ctx.new_page()
    p.add_init_script(f"window.__SEED={json.dumps(SEED)};window.__NET={'true' if net else 'false'};"
                      "Object.defineProperty(Navigator.prototype,'onLine',{configurable:true,get:()=>window.__NET!==false});window.LS_POLL_MS=600000;")
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.on("console", lambda m: m.type == "error" and errors.append(m.text))
    return p

def route(ctx):
    ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
    ctx.route("**/jszip.min.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=JSZIP))
    ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda r: r.fulfill(status=200, content_type="text/css", body=""))

def app_ready(p):
    """App visible and settled: the one-time reload that writes the collection's home-screen name has happened."""
    p.wait_for_selector("#app:not([hidden])")
    for _ in range(60):
        try:
            if p.evaluate("""(()=>{ const app=document.getElementById('app'); if(!app||app.hidden) return false;
                let sh=false; try{ sh=sessionStorage.getItem('ls-shared')==='1'; }catch(e){}
                const want=document.querySelector('meta[name=apple-mobile-web-app-title]').content;
                return sh || !navigator.onLine || window.__homeLabel===want; })()"""): return
        except Exception: pass
        p.wait_for_timeout(100)
    p.wait_for_selector("#app:not([hidden])")

def login(p, email, code="42424242", shared=False):
    p.goto(URL); p.wait_for_selector("#gEmail")
    p.fill("#gEmail", email)
    if shared: p.check("#gShared")
    p.click("#gForm .btn"); p.wait_for_selector("#gCode")
    p.fill("#gCode", code)


CR = {"status": "packed", "where": "with", "handling": "2p", "orientation": "upright", "clientNote": "Kept at the freeport, ready for the next loan.",
      "crates": [{"type": "museum", "features": ["ispm15", "marks"], "h": 132, "w": 132, "d": 24, "kg": 68, "ref": "AUR-012-C1"},
                 {"type": "sculpture", "h": 100, "w": 50, "d": 50, "kg": 30}]}
for w in SEED["tables"]["artworks"]:
    if w["id"] == "aur-01": w["crating"] = CR
SEED["tables"]["documents"] += [
  dict(id="cr1", kind="crating", name="Packing list.pdf", mime="application/pdf", size=800, storage_path="files/cr1", artwork_id="aur-01", expense_id=None, collection_id=CID, visible_to_client=True, created_at="2026-09-14T10:00:00Z"),
  dict(id="cr2", kind="crating", name="Crate invoice.pdf", mime="application/pdf", size=800, storage_path="files/cr2", artwork_id="aur-01", expense_id=None, collection_id=CID, visible_to_client=False, created_at="2026-09-14T10:00:00Z")]
errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for loc, lang in (("en-GB", "en"), ("fr-FR", "fr")):
        ctx = b.new_context(service_workers="block", accept_downloads=True, locale=loc, viewport={"width": 390, "height": 844}); route(ctx)
        p = new_page(ctx); login(p, "client@example.com"); app_ready(p)
        p.evaluate("openWork('aur-01')"); p.wait_for_selector("#detail:not([hidden]) .dh")
        lg = p.evaluate("LANG")
        txt = p.inner_text("#dCrating")
        if lg == "en":
            check("packing & crate" in txt.lower() and "Packed" in txt and "International museum crate" in txt, "en: status and type shown")
            check("132 × 132 × 24 cm" in txt and "52.0 × 52.0 × 9.4 in" in txt and "68.0 kg · 149.9 lb" in txt, "en: dimensions in cm and inches, weight in kg and lb")
            check("package 1 / 2" in txt.lower() and "Sculpture / plinth crate" in txt, "en: two packages listed")
            check("ISPM 15 treated wood" in txt and "Kept with the work" in txt and "2 people" in txt and "Upright" in txt and "freeport" in txt, "en: features, location, handling, orientation, note")
        else:
            check("emballage & caisse" in txt.lower() and "Emballée" in txt and "Caisse internationale (musée)" in txt, "fr: status and type shown")
            check("52,0 × 52,0 × 9,4 in" in txt and "68,0 kg · 149,9 lb" in txt, "fr: French number format")
        check("Packing list.pdf" in txt and "Crate invoice.pdf" not in p.content(), lg + ": shared packing list shown, internal file never sent")
        docs_sec = p.locator("#detail .sec h4", has_text="Documents")
        check(all("Packing list.pdf" not in s for s in [p.locator("#detail .sec").nth(i).inner_text() for i in range(p.locator("#detail .sec").count()) if "Documents" in p.locator("#detail .sec").nth(i).inner_text()[:12]]), lg + ": crate files not repeated under Documents")
        with p.expect_download() as dl: p.locator("#dCrating [data-doc=cr1]").click()
        check(dl.value.suggested_filename == "Packing list.pdf", lg + ": packing list downloads")
        check(p.evaluate("document.documentElement.scrollWidth<=document.documentElement.clientWidth"), lg + ": phone width without overflow")
        p.locator("#dCrating").screenshot(path=f"/tmp/ls-crating-client-{lg}.png")
        # a work without crating shows no block
        p.click("#dBack"); p.evaluate("openWork('aur-06')"); p.wait_for_selector("#detail .dh")
        check(p.locator("#dCrating").count() == 0, lg + ": no block when nothing is shared")
        ctx.close()
    check(not errors, "no page errors " + "; ".join(errors[:3]))
    b.close()
srv.shutdown()
print(f"\n{ok} checks passed")
