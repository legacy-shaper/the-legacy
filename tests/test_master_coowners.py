#!/usr/bin/env python3
"""Tests of the "Propriété" card (co-owners, % or amount, total value, client visibility) in The Legacy master app.
   Run: python3 tests/test_master_coowners.py"""
import json, os, sys, threading, http.server, functools, re
from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = open(os.path.join(R, "tests", "master_mock.js"), encoding="utf-8").read()
CID = "c1111111-0000-4000-8000-000000000001"
SEED = {
  "docs": [
    {"coll": "settings", "id": "company", "data": {"name": "Legacy Shaper Collection - FZCO", "locations": [{"name": "Épinay Storage Dylan", "address": "Épinay-sur-Seine"}]}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "contacts", "id": "ct1", "data": {"id": "ct1", "name": "Jonathan Wahnich"}, "updated_at": "2026-10-01T00:00:00Z"},
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
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8767), functools.partial(Quiet, directory=R))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8767/app/"
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

    def open_art():
        p.evaluate("state.curArt='art1'; leaveHome('artworks'); document.body.classList.add('alt-detail'); renderAlt();")
        p.wait_for_selector("#ownCard")
    open_art()
    card = lambda: p.inner_text("#ownCard")
    check("Propriété à 100 %" in card() and p.input_value("#ownSel") == "__dl", "single owner (Collection DL) shown at 100 %")
    check(p.locator("#ownShow").count() == 0, "client visibility switch hidden while the work is in Dylan's inventory")

    # total value + main share in % -> amount computed
    p.fill("#k_ownValue", "1 000 000"); p.fill("#k_ownershipShare", "60")
    check(p.input_value("#k_ownerAmount") == "600000", "my share 60 % of 1 000 000 gives 600000")

    # add a co-owner from the contacts
    p.click("#coAdd"); p.wait_for_selector("#coQ")
    p.type("#coQ", "jona")
    check(p.locator("[data-copick=ct1]").count() == 1 and p.locator("[data-copick=ct2]").count() == 0, "contact search filters as you type")
    check("Ajouter « jona »" in p.inner_text("#coRes"), "free-name option offered too")
    p.click("[data-copick=ct1]"); p.wait_for_selector("#co_a_0")
    check("Jonathan Wahnich" in card() and "Contact" in card(), "contact added as co-owner")
    check(p.evaluate("document.activeElement.id") == "co_p_0", "cursor goes to the new co-owner's share")
    check("reste 40 %" in card(), "remaining share shown (40 %)")

    # amount -> percentage
    p.fill("#co_a_0", "250000")
    check(p.input_value("#co_p_0") == "25", "amount 250000 of 1 000 000 gives 25 %")
    check("reste 15 %" in card(), "remaining share updated (15 %)")

    # free name with Enter, accents in search
    p.click("#coAdd"); p.wait_for_selector("#coQ")
    p.type("#coQ", "raphael")
    check(p.locator("[data-copick=ct2]").count() == 1, "search ignores accents (raphael finds Raphaël)")
    check(p.locator("[data-copick=ct1]").count() == 0, "a contact already listed is not offered again")
    p.fill("#coQ", "Fondation X"); p.press("#coQ", "Enter"); p.wait_for_selector("#co_n_1")
    check(p.input_value("#co_n_1") == "Fondation X", "free name added with Enter")
    p.fill("#co_p_1", "15,5")
    check(p.input_value("#co_a_1") == "155000", "15,5 % gives 155000 (comma decimal accepted)")
    check("dépasse 100 % de 0,5 %" in card(), "over 100 % flagged")
    p.fill("#co_p_1", "15"); check(p.input_value("#co_a_1") == "150000" and "Répartition complète : 100 %" in card(), "total exactly 100 % confirmed")

    # total value changes: amounts follow the percentages
    p.fill("#k_ownValue", "2000000")
    check([p.input_value(s) for s in ("#k_ownerAmount", "#co_a_0", "#co_a_1")] == ["1200000", "500000", "300000"], "new total value recomputes every amount")
    p.select_option("#k_ownCurrency", "EUR"); p.wait_for_selector("label[for=co_a_0]")
    check("Montant (EUR)" in p.inner_text("label[for=co_a_0]"), "currency shown on the amount fields")

    # saved
    p.wait_for_function(f"(()=>{{const d={DOC}; return d.coOwners&&d.coOwners.length===2&&d.coOwners[1].pct==='15'&&d.ownValue==='2000000'&&d.ownCurrency==='EUR'}})()", timeout=10000)
    d = p.evaluate(DOC)
    check(d["ownershipShare"] == "60" and d["ownerAmount"] == "1200000" and d["coOwners"][0]["contactId"] == "ct1" and d["coOwners"][0]["amount"] == "500000"
          and d["coOwners"][1]["contactId"] == "" and d["coOwners"][1]["name"] == "Fondation X", "everything saved in the database")
    check(d["owner"] == "Collection DL" and d["notes"] == "Internal note" and d["price"] == "100000", "owner, description and price untouched")

    # reload: still there
    p.reload(); p.wait_for_function("typeof state!=='undefined' && state.artworks && state.artworks.art1 && state.artworks.art1.coOwners", timeout=15000)
    open_art()
    check(p.input_value("#co_p_0") == "25" and p.input_value("#co_n_1") == "Fondation X" and "Répartition complète" in card(), "after reload the split is intact")

    # contact page lists the co-owned work with its share
    p.evaluate("state.curContact='ct1'; switchView('contacts'); document.body.classList.add('alt-detail'); renderAlt();")
    p.wait_for_function("document.querySelector('#detail').textContent.includes('Œuvres lui appartenant')")
    ct = p.evaluate("document.querySelector('#detail').textContent"); check("Copropriétaire · 25 %" in ct and "Calder" in ct, "contact page shows the co-owned work and the share")

    # client collection: visibility switch
    p.evaluate("switchView('artworks')"); open_art()
    p.select_option("#k_collectionId", CID); p.wait_for_selector("#ownShow")
    check(p.is_checked("#ownShow"), "attached to a client collection: split shown to the collector by default")
    p.click("#ownShow"); p.wait_for_function(f"{DOC}.ownHide===true", timeout=10000)
    check(True, "unticking hides the split from the collector (saved)")
    p.click("#ownShow"); p.wait_for_function(f"{DOC}.ownHide===false", timeout=10000)
    check(True, "ticking shows it again")

    # removal needs two clicks
    p.click("[data-codel='1']"); check(p.locator("#co_n_1").count() == 1, "first click on remove only arms it")
    p.click("[data-codel='1']"); p.wait_for_function(f"{DOC}.coOwners.length===1", timeout=10000)
    check("reste 15 %" in card(), "co-owner removed, remaining share back to 15 %")

    # making a co-owner the main owner removes the duplicate
    p.select_option("#ownSel", "ct1"); p.wait_for_function(f"{DOC}.ownerContactId==='ct1' && {DOC}.coOwners.length===0", timeout=10000)
    check(True, "choosing a co-owner as main owner removes the duplicate line")
    p.select_option("#ownSel", "__dl"); p.wait_for_function(f"{DOC}.owner==='Collection DL'", timeout=10000)

    # iPhone width
    p.set_viewport_size({"width": 390, "height": 844}); open_art()
    p.click("#coAdd"); p.wait_for_selector("#coQ"); p.fill("#coQ", "Fondation Y"); p.press("#coQ", "Enter"); p.wait_for_selector("#co_n_0")
    sw = p.evaluate("document.documentElement.scrollWidth"); cw = p.evaluate("document.documentElement.clientWidth")
    check(sw <= cw, f"iPhone: no horizontal scrolling ({sw} <= {cw})")
    box = p.evaluate("(()=>{const r=document.querySelector('#co_p_0').getBoundingClientRect(); return [r.left, r.right]})()")
    check(box[0] >= 0 and box[1] <= cw, "iPhone: share field fully on screen")
    p.wait_for_timeout(1000)
    b.close()

check(not errors, "no script error" + (": " + " | ".join(errors[:3]) if errors else ""))
srv.shutdown()
print(f"\nALL {ok} CHECKS PASSED")
