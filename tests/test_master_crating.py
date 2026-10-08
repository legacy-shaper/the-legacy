#!/usr/bin/env python3
"""Emballage & caisse (crating) on the artwork record of The Legacy master app: status, types, features, several crates,
   measures and air-freight calculations, maker contact, client visibility, crate supplier bill, photos.
   Run: python3 tests/test_master_crating.py   (screenshots in /tmp/ls-crating-*.png)"""
import json, os, sys, threading, http.server, functools, re
from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = open(os.path.join(R, "tests", "master_mock.js"), encoding="utf-8").read()
CID = "c1111111-0000-4000-8000-000000000001"
SEED = {
  "docs": [
    {"coll": "settings", "id": "company", "data": {"name": "Legacy Shaper Collection - FZCO", "locations": [{"name": "Épinay Storage Dylan", "address": "Épinay-sur-Seine"}]}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "contacts", "id": "ct1", "data": {"id": "ct1", "name": "Jonathan Wahnich", "email": "old@example.com", "phone": "+33 1 00 00 00 00"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "contacts", "id": "ct2", "data": {"id": "ct2", "name": "Raphaël Wertheimer", "company": "RW Holdings"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "artworks", "id": "art1", "data": {"id": "art1", "artist": "Alexander Calder", "title": "Untitled", "year": "1962", "owner": "Collection DL", "location": "Épinay Storage Dylan", "price": "100000", "currency": "USD", "notes": "Internal note"}, "updated_at": "2026-10-01T00:00:00Z"},
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
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8771), functools.partial(Quiet, directory=R))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8771/app/"
ok = 0
def check(c, label):
    global ok
    if not c: print("FAIL:", label); srv.shutdown(); sys.exit(1)
    ok += 1; print("ok  ", label)

DOC = "__mockDB().docs.find(x=>x.coll==='artworks'&&x.id==='art1').data"
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
    p.fill("#gEmail", "dylan@legacy-shaper.com"); p.fill("#gPass", "good-pass"); p.click("#gForm button[type=submit]"); p.wait_for_selector("#gCode")
    p.fill("#gCode", "123456"); p.click("#gForm button[type=submit]")
    p.wait_for_function("typeof state!=='undefined' && state.artworks && state.artworks.art1 && state.contacts.ct2", timeout=15000)


    A = lambda: p.evaluate(DOC)
    def open_art():
        p.evaluate("state.curArt='art1'; leaveHome('artworks'); document.body.classList.add('alt-detail'); renderAlt();")
        p.wait_for_selector("#crCard")
    open_art()
    check(p.locator("#crStart").count() == 1 and "crating" not in A(), "empty section shows only « Renseigner l'emballage »")
    p.click("#crStart"); p.wait_for_selector("[data-crstatus=packed]")
    p.click("[data-crstatus=packed]"); p.click("[data-crtype=museum]")
    p.check("[data-crfeat=ispm15]"); p.check("[data-crfeat=foam]"); p.check("[data-crfeat=marks]")
    for k, v in [("h", "132"), ("w", "132"), ("d", "24"), ("kg", "68"), ("tare", "41")]: p.fill(f"#cr_crates_0_{k}", v)
    p.fill("#cr_crates_0_ref", "AUR-012-C1")
    check(p.inner_text("#crVol").strip() == "0,418 m³", "volume 132 × 132 × 24 cm = 0,418 m³")
    check(p.inner_text("#crAir").strip() == "69,7 kg" and p.inner_text("#crTax").strip() == "69,7 kg", "volumetric 69,7 kg wins over gross 68 kg")
    check("149,9 lb" in p.inner_text("#crCalc") and "14,8 ft³" in p.inner_text("#crCalc"), "pounds and cubic feet shown")
    check(p.inner_text("#crNet").strip() == "27,0 kg", "net = gross − tare")
    check(p.inner_text("#cr_crates_0_h_h").strip() == "52,0 in", "inch conversion under the field")
    p.wait_for_timeout(1500); c = A()["crating"]
    check(c["status"] == "packed" and c["crates"][0]["type"] == "museum", "status and type saved")
    check(c["crates"][0]["features"] == ["ispm15", "foam", "marks"], "features saved in list order")
    check(c["crates"][0]["h"] == "132" and c["crates"][0]["ref"] == "AUR-012-C1", "measures and marking saved")
    # toggling the same chip clears it
    p.click("[data-crtype=museum]"); p.click("[data-crtype=museum]"); p.wait_for_timeout(1200)
    check(A()["crating"]["crates"][0]["type"] == "museum", "type chip toggles back on")
    # second package (plinth), totals, then removal
    p.click("#crAdd"); p.wait_for_selector("#cr_crates_1_h")
    p.locator(".crate").nth(1).locator("[data-crtype=sculpture]").click()
    for k, v in [("h", "100"), ("w", "50"), ("d", "50"), ("kg", "30")]: p.fill(f"#cr_crates_1_{k}", v)
    check(p.inner_text("#crVol").strip() == "0,668 m³" and "Volume total (2 colis)" in p.inner_text("#crCalc"), "two packages: volumes add up")
    check(p.inner_text("#crKg").strip() == "98,0 kg", "two packages: gross weights add up")
    p.wait_for_timeout(1200)
    check(len(A()["crating"]["crates"]) == 2 and A()["crating"]["crates"][1]["type"] == "sculpture", "second package saved")
    d2 = p.locator(".crate").nth(1).locator("[data-crdel]"); d2.click(); d2 = p.locator(".crate").nth(1).locator("[data-crdel]"); d2.click()
    p.wait_for_timeout(1200)
    check(len(A()["crating"]["crates"]) == 1 and p.locator(".crate").count() == 1, "package removed after confirmation")
    # maker: contact, then free name
    p.select_option("#cr_maker_sel", "ct1"); p.wait_for_timeout(1200)
    check(A()["crating"]["makerContactId"] == "ct1" and A()["crating"]["maker"] == "Jonathan Wahnich", "maker linked to the contact")
    p.select_option("#cr_maker_sel", "__other"); p.wait_for_selector("#cr_maker"); p.fill("#cr_maker", "Atelier de caisserie, Dubaï"); p.wait_for_timeout(1200)
    check(A()["crating"]["maker"] == "Atelier de caisserie, Dubaï" and not A()["crating"]["makerContactId"], "free maker name")
    p.fill("#cr_date", "2026-09-14"); p.select_option("#cr_where", "with"); p.select_option("#cr_handling", "2p"); p.select_option("#cr_orientation", "upright")
    p.fill("#cr_quote", "2450"); p.select_option("#cr_quoteCurrency", "EUR")
    p.fill("#cr_notes", "Face vissée côté marquage"); p.fill("#cr_clientNote", "Caisse conservée avec l’œuvre.")
    p.wait_for_timeout(1500); c = A()["crating"]
    check(c["where"] == "with" and c["handling"] == "2p" and c["orientation"] == "upright" and c["date"] == "2026-09-14", "location, handling, orientation, date saved")
    check(c["quote"] == "2450" and c["quoteCurrency"] == "EUR" and c["notes"].startswith("Face") and c["clientNote"].startswith("Caisse"), "quote and notes saved")
    # visibility needs a client collection
    check(p.is_disabled("#crVis"), "client visibility locked while the work is not in a client collection")
    p.select_option("#k_collectionId", CID); p.wait_for_timeout(800); p.wait_for_selector("#crVis")
    check(not p.is_disabled("#crVis") and "Interne" in p.inner_text("#crCard h2"), "collection set: toggle available, still internal")
    p.check("#crVis"); p.wait_for_timeout(1200)
    check(A()["crating"]["visibleToClient"] is True and "Visible par le client" in p.inner_text("#crCard h2"), "visible to the client")
    # crate supplier bill linked to the work
    p.click("#crExp"); p.wait_for_timeout(1200)
    exps = [x["data"] for x in p.evaluate("__mockDB().docs") if x["coll"] == "expenses"]
    check(len(exps) == 1 and exps[0]["artworkId"] == "art1" and exps[0]["amount"] == "2450" and exps[0]["currency"] == "EUR" and exps[0]["supplier"] == "Atelier de caisserie, Dubaï", "crate bill created from the quote, linked to the work")
    check(A()["crating"]["expenseId"] == exps[0]["id"], "bill id kept on the crating")
    p.keyboard.press("Escape"); p.wait_for_timeout(300)
    p.evaluate("document.querySelectorAll('.ov').forEach(o=>o.remove())")
    open_art()
    check(p.locator("#crCost [data-expopen]").count() == 1 and p.locator("#crExp").count() == 0, "linked bill shown instead of the create button")
    # photos of the crate
    p.set_input_files("#crFile", files=[dict(name="caisse.pdf", mimeType="application/pdf", buffer=b"%PDF-1.4 fake")])
    p.wait_for_function("(state.artworks.art1.crating.files||[]).length===1", timeout=8000)
    check(p.locator("#crFiles .efile").count() == 1, "packing list listed")
    p.uncheck("[data-crfvis]"); p.wait_for_timeout(1200)
    check(A()["crating"]["files"][0].get("internal") is True, "file kept internal")
    p.check("[data-crfvis]"); p.wait_for_timeout(1200)
    check("internal" not in A()["crating"]["files"][0], "file shown to the client again")
    # reopening keeps everything
    open_art()
    check(p.locator("[data-crstatus=packed].on").count() == 1 and p.locator("[data-crtype=museum].on").count() == 1 and p.is_checked("[data-crfeat=foam]"), "chips and boxes restored")
    check(p.input_value("#cr_crates_0_kg") == "68" and p.input_value("#cr_maker") == "Atelier de caisserie, Dubaï", "values restored")
    p.screenshot(path="/tmp/ls-crating-desktop.png", full_page=True)
    # phone width: nothing wider than the screen
    p.set_viewport_size({"width": 390, "height": 844}); open_art(); p.wait_for_timeout(300)
    over = p.evaluate("(()=>{const W=document.documentElement.clientWidth;return [...document.querySelectorAll('#crCard *')].filter(e=>e.getBoundingClientRect().right>W+1).map(e=>e.className||e.tagName).slice(0,5)})()")
    check(over == [] and p.evaluate("document.documentElement.scrollWidth<=document.documentElement.clientWidth"), "phone width: no overflow")
    p.locator("#crCard").screenshot(path="/tmp/ls-crating-phone.png")
    # clearing the section (two taps)
    p.set_viewport_size({"width": 1400, "height": 900}); open_art()
    p.click("#crClear"); check("crating" in A(), "first tap only arms"); p.click("#crClear"); p.wait_for_timeout(1200)
    check("crating" not in A() and p.locator("#crStart").count() == 1, "section cleared after confirmation")
    check(not errors, "no page errors " + "; ".join(errors))
    b.close()
srv.shutdown()
print(f"\n{ok} checks passed")
