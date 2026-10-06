#!/usr/bin/env python3
"""Tests of the client-collection features added to The Legacy master app (app/index.html), with a Supabase mock.
   Run: python3 tests/test_master_collections.py"""
import json, os, sys, threading, http.server, functools, re
from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = open(os.path.join(R, "tests", "master_mock.js"), encoding="utf-8").read()
CID = "c1111111-0000-4000-8000-000000000001"
SEED = {
  "docs": [
    {"coll": "settings", "id": "company", "data": {"name": "Legacy Shaper Collection - FZCO", "locations": [{"name": "Épinay Storage Dylan", "address": "Épinay-sur-Seine"}]}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "artworks", "id": "art1", "data": {"id": "art1", "artist": "Test Artist", "title": "Test Work", "year": "2001", "owner": "Collection DL", "location": "Épinay Storage Dylan", "price": "100000", "currency": "USD", "notes": "Internal note"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "expenses", "id": "exp1", "data": {"id": "exp1", "supplier": "Shipper", "label": "Transport", "category": "transport", "amount": "1200", "currency": "USD", "status": "due", "artworkId": "art1", "date": "2026-09-30"}, "updated_at": "2026-10-01T00:00:00Z"},
  ],
  "tables": {"collections": [{"id": CID, "slug": "aurelia", "name": "Collection Aurelia", "subtitle": None, "display_currency": "USD"}],
             "collection_members": [], "profiles": [{"id": "u9", "email": "dylan@legacy-shaper.com", "role": "admin"}]},
  "files": {},
}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), functools.partial(Quiet, directory=R))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8766/app/"
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
    ctx.route("**/jszip.min.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=open("/opt/npm-tools/node_modules/jszip/dist/jszip.min.js").read()))
    ctx.route(re.compile(r"https://(cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com)/.*"), lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
    p = ctx.new_page()
    p.add_init_script(f"window.__MASTER_SEED={json.dumps(SEED)};")
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(URL); p.wait_for_selector("#gEmail")
    p.fill("#gEmail", "dylan@legacy-shaper.com"); p.fill("#gPass", "bad"); p.click("#gForm button[type=submit]"); p.wait_for_timeout(200)
    check("incorrect" in p.inner_text("#gErr"), "wrong password refused")
    p.fill("#gPass", "good-pass"); p.click("#gForm button[type=submit]"); p.wait_for_selector("#gCode")
    p.fill("#gCode", "123456"); p.click("#gForm button[type=submit]")
    p.wait_for_function("typeof state!=='undefined' && state.artworks && state.artworks.art1 && state.collections && state.collections.length===1", timeout=15000)
    check(True, "master signs in (password + authenticator) and loads its data and the collections")

    # --- artwork: attach to a client collection ---
    p.evaluate("state.curArt='art1'; leaveHome('artworks'); document.body.classList.add('alt-detail'); renderAlt();")
    p.wait_for_selector("#k_collectionId")
    check(p.locator("#k_acqPrice").count() == 0, "artwork not shared: client fields hidden")
    p.select_option("#k_collectionId", CID); p.wait_for_selector("#k_acqPrice")
    check(True, "choosing a collection reveals the client fields")
    p.fill("#k_clientLocation", "Private residence · Geneva"); p.fill("#k_acqPrice", "250000"); p.select_option("#k_acqCurrency", "EUR")
    p.fill("#k_insuredValue", "300000"); p.fill("#k_ownershipShare", "50"); p.fill("#k_clientNotes", "Shown to the collector")
    p.wait_for_function("(()=>{const d=__mockDB().docs.find(x=>x.coll==='artworks'&&x.id==='art1').data; return d.collectionId && d.acqPrice==='250000' && d.clientNotes==='Shown to the collector'})()", timeout=10000)
    d = p.evaluate("__mockDB().docs.find(x=>x.coll==='artworks'&&x.id==='art1').data")
    check(d["collectionId"] == CID and d["acqCurrency"] == "EUR" and d["insuredValue"] == "300000" and d["ownershipShare"] == "50" and d["clientLocation"].startswith("Private"), "client fields saved in the database")
    check(d["notes"] == "Internal note" and d["price"] == "100000", "internal description and sale price untouched")
    check("Visible par le collectionneur" in p.inner_text("#detail"), "card says the work is shared")

    # --- expense: visible to client ---
    p.evaluate("openExp('exp1')"); p.wait_for_selector("#e_visibleToClient")
    p.select_option("#e_visibleToClient", "true")
    p.wait_for_function("__mockDB().docs.find(x=>x.coll==='expenses'&&x.id==='exp1').data.visibleToClient==='true'", timeout=10000)
    check(True, "expense marked visible to the client")
    p.click("#expDone")

    # --- settings: collections, access ---
    p.evaluate("openSettings()"); p.wait_for_selector("#collBox")
    p.wait_for_function("document.querySelector('#collBox').innerText.includes('Aucun accès')", timeout=10000)
    check("Collection Aurelia" in p.input_value("[data-collf=name]") and "1 œuvre(s)" in p.inner_text("#collBox"), "settings list the collection and its works")
    p.fill(f"#inv_{CID}", "pas-une-adresse"); p.click(f"[data-collgrant='{CID}']")
    check("vérifier" in p.inner_text("#collMsg"), "invalid email refused")
    p.fill(f"#inv_{CID}", "Collector@Example.com"); p.click(f"[data-collgrant='{CID}']")
    p.wait_for_function("document.querySelector('#collBox').innerText.includes('collector@example.com')", timeout=10000)
    check("app.legacy-shaper.com" in p.inner_text("#collMsg"), "access granted, explanation shown")
    p.click("[data-collrevoke]"); check(p.inner_text("[data-collrevoke]") == "Confirmer", "removing access asks for confirmation")
    p.click("[data-collrevoke]"); p.wait_for_function("document.querySelector('#collBox').innerText.includes('Aucun accès')", timeout=10000)
    check(True, "access removed")
    p.fill("[data-collf=subtitle]", "Collection Office"); p.press("[data-collf=subtitle]", "Tab")
    p.wait_for_function("__mockDB().tables.collections[0].subtitle==='Collection Office'", timeout=5000)
    check(True, "collection subtitle saved")
    p.fill("#collNewName", "Collection Démo 2"); p.click("#collNew")
    p.wait_for_function("__mockDB().tables.collections.length===2 && document.querySelectorAll('#collBox [data-collf=name]').length===2", timeout=10000)
    check(re.match(r"collection-demo-2-[a-z0-9]{4}$", p.evaluate("__mockDB().tables.collections[1].slug")) is not None, "new collection created with a clean slug")
    check(p.evaluate("document.getElementById('setMsg').style.color") == "", "collection actions do not mark company settings as modified")
    p.click("#cancelSet")
    p.evaluate("switchView('invoices'); renderAll()")
    p.wait_for_timeout(300)
    b.close()

check(not errors, "no script error" + (": " + " | ".join(errors[:3]) if errors else ""))
srv.shutdown()
print(f"\nALL {ok} CHECKS PASSED")
