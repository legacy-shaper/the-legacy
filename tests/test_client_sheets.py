#!/usr/bin/env python3
"""Client app: several works in one PDF. Œuvres → « Sélectionner » → tick works → « Fiches d'inventaire (PDF) »
   = one inventory sheet per page, in a single print/PDF. Also checks the real printed PDF has one page per work.
   Run: python3 tests/test_client_sheets.py   (screenshots and PDF in /tmp/ls-sheets-*)"""
import json, os, sys, threading, http.server, functools, re
from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(R, "client")
MOCK = open(os.path.join(R, "tests", "client_mock.js"), encoding="utf-8").read()
JSZIP = open("/opt/npm-tools/node_modules/jszip/dist/jszip.min.js", encoding="utf-8").read()
demo = json.load(open(os.path.join(R, "tests", "demo.json"), encoding="utf-8"))
CID = demo["coll"]["id"]
SEED = {"users": [dict(id="u1", email="client@example.com", role="client")],
        "members": [dict(user_id="u1", collection_id=CID)],
        "tables": {"profiles": [dict(id="u1", role="client")], "collections": [demo["coll"]], "artworks": demo["works"],
                   "artwork_views": demo["views"], "expenses": demo["expenses"], "documents": []}, "files": {}}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8776), functools.partial(Quiet, directory=CLIENT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
ok = 0
def check(c, label):
    global ok
    if not c: print("FAIL:", label); srv.shutdown(); sys.exit(1)
    ok += 1; print("ok  ", label)

errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for name, vp, loc in [("iphone", dict(width=390, height=844), "fr-FR"), ("mac", dict(width=1280, height=860), "en-GB")]:
        ctx = b.new_context(service_workers="block", viewport=vp, locale=loc, device_scale_factor=2 if name == "iphone" else 1)
        ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
        ctx.route("**/jszip.min.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=JSZIP))
        ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda r: r.fulfill(status=200, content_type="text/css", body=""))
        p = ctx.new_page()
        p.add_init_script(f"window.__SEED={json.dumps(SEED)};window.__NET=true;Object.defineProperty(Navigator.prototype,'onLine',{{configurable:true,get:()=>true}});window.LS_POLL_MS=600000;")
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto("http://127.0.0.1:8776/"); p.wait_for_selector("#gEmail")
        p.fill("#gEmail", "client@example.com"); p.click("#gForm .btn"); p.wait_for_selector("#gCode"); p.fill("#gCode", "42424242")
        p.wait_for_selector("#app:not([hidden])"); p.wait_for_timeout(1500); p.wait_for_selector("#app:not([hidden])")
        p.evaluate("window.print=()=>{window.__printed=(window.__printed||0)+1};0")
        p.click('#tabs [data-t="works"]:visible, #btabs [data-bt="works"]:visible'); p.wait_for_selector("#selStart")
        fr = loc.startswith("fr")
        check(p.inner_text("#selStart") == ("Sélectionner" if fr else "Select"), f"{name}: « Sélectionner » button on the works page")
        p.click("#selStart"); p.wait_for_selector("#selBar")
        check(p.locator("#selGo").is_disabled() and p.locator("#chatFab").is_hidden(), f"{name}: PDF button disabled until a pick; chat button out of the way")
        cards = p.locator("#grid [data-w]"); n = cards.count()
        ids = [cards.nth(i).get_attribute("data-w") for i in range(n)]
        for i in (2, 0, 4): cards.nth(i).click()
        check(p.locator("#detail").is_hidden() or not p.locator("#detail").is_visible(), f"{name}: ticking does not open the work")
        check(p.locator("#grid .card.picked").count() == 3 and "3" in p.inner_text("#selGo"), f"{name}: 3 works ticked")
        cards.nth(4).click(); cards.nth(4).click()
        check(p.locator("#grid .card.picked").count() == 3, f"{name}: untick / re-tick")
        p.screenshot(path=f"/tmp/ls-sheets-{name}-select.png")
        p.click("#selGo"); p.wait_for_function("window.__printed===1", timeout=15000)
        sheets = p.evaluate("[...document.querySelectorAll('#print .psheet')].map(s=>({t:s.querySelector('.pa').innerText,logo:!!s.querySelector('img.pl'),img:!!s.querySelector('img.pimg')}))")
        want = [w for w in ids if w in (ids[0], ids[2], ids[4])]
        order = p.evaluate(f"{json.dumps(want)}.map(id=>S.data.works.find(w=>w.id===id).artist)")
        check(len(sheets) == 3 and [s["t"] for s in sheets] == order, f"{name}: 3 sheets, in collection order: {[s['t'] for s in sheets]}")
        check(all(s["logo"] and s["img"] for s in sheets), f"{name}: every sheet has the logo and the work's photo")
        check(re.search(r" - 3 (œuvres|works) - \d{4}-\d\d-\d\d$", p.evaluate("window.__lastSheets.name")), f"{name}: file name = collection - 3 works - date")
        check(p.locator("#selBar").count() == 0 and p.locator("#selStart").count() == 1, f"{name}: back to the normal grid")
        # the real printed PDF: one A4 page per work
        p.emulate_media(media="print"); pdf = p.pdf(format="A4", print_background=True); p.emulate_media(media="screen")
        open(f"/tmp/ls-sheets-{name}.pdf", "wb").write(pdf)
        pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
        check(pages == 3, f"{name}: printed PDF has exactly 3 pages (got {pages})")
        # select all + search filter, cancel, tab change clears
        p.click("#selStart"); p.click("#selAll")
        check(p.locator("#grid .card.picked").count() == n, f"{name}: « Tout sélectionner » ticks all {n}")
        p.click("#selAll"); check(p.locator("#grid .card.picked").count() == 0, f"{name}: clear")
        p.click("#selCancel"); check(p.locator("#selBar").count() == 0 and p.evaluate("S.sel") is None, f"{name}: « Annuler » leaves selection")
        p.click("#selStart"); cards.nth(1).click(); p.click('#tabs [data-t="overview"]:visible, #btabs [data-bt="overview"]:visible')
        check(p.locator("#selBar").count() == 0 and p.evaluate("S.sel") is None and p.locator("#chatFab").count() == 1, f"{name}: changing tab ends the selection")
        # single sheet from the work page is unchanged
        p.click('#tabs [data-t="works"]:visible, #btabs [data-bt="works"]:visible'); p.locator("#grid [data-w]").first.click(); p.wait_for_selector("#dPdf")
        p.click("#dPdf"); p.wait_for_function("window.__printed===2", timeout=10000)
        check(p.locator("#print .psheet").count() == 1 and p.locator("#print .pa").count() == 1, f"{name}: single « Fiche d’inventaire » = one sheet")
        ctx.close()
    b.close()
srv.shutdown()
check(not errors, "no page errors: " + "; ".join(errors[:3]))
print(f"\n{ok} checks passed")
