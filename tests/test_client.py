#!/usr/bin/env python3
"""End-to-end tests of the Legacy Shaper client app (client/index.html) against an in-browser Supabase mock.
   Run: python3 tests/test_client.py   (exits non-zero on the first failure)"""
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
  "files": {"files/d1": "%PDF-1.4 demo invoice"},
}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(Quiet, directory=CLIENT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8765/"

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

errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    # ---------- 1. unknown address, bad code, good code ----------
    ctx = b.new_context(service_workers="block", accept_downloads=True, locale="en-GB"); route(ctx)
    p = new_page(ctx)
    p.goto(URL); p.wait_for_selector("#gEmail")
    check(p.locator("#gate img.logo").count() == 1, "gate shows the Legacy Shaper logo")
    p.fill("#gEmail", "stranger@example.com"); p.click("#gForm .btn"); p.wait_for_timeout(300)
    check("registered with Legacy Shaper" in p.inner_text("#gMsg"), "unknown address gets a courteous message, no account created")
    p.fill("#gEmail", "client@example.com"); p.click("#gForm .btn"); p.wait_for_selector("#gCode")
    check("client@example.com" in p.inner_text("#gate"), "code screen names the address")
    p.fill("#gCode", "00000000"); p.wait_for_timeout(400)
    check("does not match" in p.inner_text("#gMsg"), "wrong code is refused")
    p.fill("#gCode", "42424242"); app_ready(p)
    check(p.inner_text("#collName") == "The Aurelian Collection", "client opens their collection after the code")
    check(p.get_attribute('meta[name="apple-mobile-web-app-title"]', "content") == "Aurelian", "home-screen label is the collection name (Aurelian)")
    check(p.title() == "Legacy Shaper · The Aurelian Collection", "page title carries Legacy Shaper and the collection")
    check(p.evaluate("window.__homeLabel") == "Aurelian" and p.locator("link[rel=manifest]").count() == 0, "page reloaded once and is parsed with the collection's name (no fixed-name manifest)")
    check(p.evaluate("sessionStorage.getItem('ls-home-reload')") == "Aurelian", "the reload happens only once")
    check("12" in p.inner_text(".kpis"), "overview counts 12 works")
    check("Secret Work" not in p.content(), "a work from another collection never appears")
    # ---------- 2. works, search, location filter ----------
    p.click("[data-t=works]"); p.wait_for_selector("#grid")
    check(p.locator("#grid .card").count() == 12, "works tab lists 12 works")
    p.fill("#q", "corvani"); p.wait_for_timeout(100)
    check(p.locator("#grid .card").count() == 2, "search narrows to the artist")
    p.fill("#q", ""); p.select_option("#loc", "Yacht · Mediterranean"); p.wait_for_timeout(100)
    check(p.locator("#grid .card").count() == 2, "location filter")
    p.select_option("#loc", "")
    # ---------- 3. artwork detail ----------
    p.click("[data-w=aur-01]"); p.wait_for_selector("#detail:not([hidden]) .dh")
    det = p.inner_text("#detail")
    check("Crimson Threshold" in det and "Élise Marchetti" in det, "detail shows artist and title")
    check("51.2 × 39.4 in" in det, "dimensions are also given in inches")
    check("$420,000" in det and "14 June 2019" in det, "acquisition date and price")
    check("$520,000" in det, "insured value")
    check(p.locator("#detail .thumbs button").count() == 2, "two views available")
    p.wait_for_function("document.querySelector('#dImg') && document.querySelector('#dImg').src.includes('demo/aur-01.jpg')")
    p.click("#detail .thumbs button >> nth=1"); p.wait_for_function("document.querySelector('#dImg').src.includes('aur-01-d.jpg')")
    check(True, "switching views shows the detail photograph")
    check("Condition report" in det, "expenses of the work are listed on its page")
    p.click("#dNext"); p.wait_for_function("document.querySelector('#detail .title').innerText.includes('Nocturne')")
    check(True, "next work navigation")
    p.click("#dBack"); check(p.is_hidden("#detail"), "back closes the detail")
    # ---------- 4. shared ownership ----------
    p.click("[data-w=aur-06]"); p.wait_for_selector("#detail .dh")
    check("50 % share" in p.inner_text("#detail") and "family foundation" in p.inner_text("#detail"), "shared ownership shown with its note")
    # print sheet
    p.evaluate("window.print=()=>{window.__printed=document.getElementById('print').innerText}")
    p.click("#dPdf"); p.wait_for_function("window.__printed")
    pr = p.evaluate("window.__printed")
    check("Senza titolo (Segno rosso)" in pr and "39.4 × 51.2 in" in pr and "Inventory sheet" in pr, "inventory sheet prepared for PDF")
    check(p.evaluate("document.querySelector('#print img.pl').src.startsWith('data:image/png')"), "inventory sheet carries the official logo")
    p.click("#dBack")
    # ---------- 5. expenses ----------
    p.click("[data-t=expenses]"); p.wait_for_selector(".chipline")
    txt = p.inner_text("#main")
    check("Internal commission" not in txt, "expenses not shared with the client stay hidden")
    p.click("[data-y='2025']"); p.wait_for_timeout(100); txt = p.inner_text("#main")
    check("Annual fine art insurance premium" in txt and "Collection Office, annual engagement" in txt, "2025 general expenses")
    check("Conservation treatment" in txt and "2026" not in p.inner_text(".block >> nth=1"), "2025 per-work expenses, year filter applied")
    check("$188,500" in txt, "2025 total in USD (68,500 + 120,000)")
    # ---------- 6. documents ----------
    p.click("[data-t=documents]"); p.wait_for_selector("#main")
    txt = p.inner_text("#main")
    check("Invoice - Corvani.pdf" in txt and "Internal note" not in txt and "Other collection" not in txt, "only documents shared with this client are listed")
    with p.expect_download() as dl: p.click("[data-doc=d1]")
    check(dl.value.suggested_filename == "Invoice - Corvani.pdf", "document downloads with its name")
    # ---------- 7. export ----------
    p.click("#btnMenu");
    with p.expect_download(timeout=20000) as dl: p.click("#mExport")
    zp = dl.value.path(); z = zipfile.ZipFile(zp); names = z.namelist()
    check("inventory.csv" in names and "expenses.csv" in names, "export contains the inventory and expenses spreadsheets")
    imgs=[n for n in names if n.startswith("images/") and not n.endswith("/")]
    check(len(imgs) == 15, "export contains every photograph (15)")
    inv = z.read("inventory.csv").decode("utf-8-sig")
    import csv as _csv; rows=list(_csv.reader(io.StringIO(inv)))
    check(len(rows) == 13 and "Secret Work" not in inv and "Internal commission" not in z.read("expenses.csv").decode("utf-8-sig"), "export holds only this collection")
    # ---------- 8. language ----------
    p.click("#btnMenu"); p.click("#mLang"); p.wait_for_timeout(100)
    check("ŒUVRES" in p.inner_text("#tabs").upper(), "switch to French")
    p.click("[data-t=works]"); p.click("[data-w=aur-03]"); p.wait_for_selector("#detail .dh")
    check("TECHNIQUE" in p.inner_text("#detail").upper() and "43,3 × 43,3 in" in p.inner_text("#detail") and "780 000" in p.inner_text("#detail").replace(" "," ").replace("\xa0"," "), "French labels and number format")
    p.click("#dBack"); p.click("#btnMenu"); p.click("#mLang")
    # ---------- 9. reload keeps the session, photos kept for offline ----------
    p.reload(); app_ready(p)
    check(p.is_hidden("#gate"), "reopening the app needs no new code")
    p.wait_for_function("(async()=>{const r=await new Promise(res=>{const q=indexedDB.open('ls-client');q.onsuccess=()=>res(q.result)});return await new Promise(res=>{const t=r.transaction('kv').objectStore('kv').getAllKeys();t.onsuccess=()=>res(t.result.filter(k=>String(k).startsWith('img:')).length)})})()", polling=300, timeout=15000) if False else None
    p.wait_for_timeout(1500)
    nimg = p.evaluate("new Promise(res=>{const q=indexedDB.open('ls-client');q.onsuccess=()=>{const t=q.result.transaction('kv').objectStore('kv').getAllKeys();t.onsuccess=()=>res(t.result.filter(k=>String(k).startsWith('img:')).length)}})")
    check(nimg == 15, f"all 15 photographs kept on the device for offline use ({nimg})")
    p.close()
    # ---------- 10. offline ----------
    p = new_page(ctx, net=False)
    p.goto(URL)  # page itself is served locally; data network is cut
    app_ready(p)
    check("Offline" in p.inner_text("#status"), "offline: collection opens from the device copy")
    p.click("[data-t=works]"); p.click("[data-w=aur-11]"); p.wait_for_selector("#detail .dh")
    check("Figura en reposo" in p.inner_text("#detail") and "3/6" in p.inner_text("#detail"), "offline: detail with edition")
    p.wait_for_function("document.querySelector('#dImg') && document.querySelector('#dImg').src.includes('aur-11.jpg')")
    check(True, "offline: photograph available")
    p.close()
    # ---------- 11. sign out wipes the device ----------
    p = new_page(ctx); p.goto(URL); app_ready(p)
    p.click("#btnMenu"); p.click("#mOut"); p.wait_for_selector("#gEmail")
    keys = p.evaluate("new Promise(res=>{const q=indexedDB.open('ls-client');q.onsuccess=()=>{const t=q.result.transaction('kv').objectStore('kv').getAllKeys();t.onsuccess=()=>res(t.result.length)}})")
    check(keys == 0, "sign out removes every copy from the device")
    check(p.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('ls-client-auth')).length") == 0, "sign out removes the session")
    ctx.close()
    # ---------- 12. shared computer ----------
    ctx = b.new_context(service_workers="block", locale="fr-FR"); route(ctx)
    p = new_page(ctx)
    p.goto(URL); p.wait_for_selector("#gEmail")
    check("Accès privé" in p.inner_text("#gate"), "French browser gets the French gate")
    login(p, "client@example.com", shared=True); app_ready(p)
    p.wait_for_timeout(600)
    keys = p.evaluate("new Promise(res=>{const q=indexedDB.open('ls-client');q.onsuccess=()=>{const t=q.result.transaction('kv').objectStore('kv').getAllKeys();t.onsuccess=()=>res(t.result.length)}})")
    check(keys == 0 and p.evaluate("!localStorage.getItem('ls-client-auth') && !localStorage.getItem('ls-home')"), "shared computer: nothing written on the device")
    check(p.locator(".install").count() == 0, "shared computer: no install suggestion")
    p2 = new_page(ctx); p2.goto(URL); p2.wait_for_selector("#gEmail")
    check(True, "shared computer: a new window asks to sign in again")
    ctx.close()
    # ---------- 13. another client sees only their own collection ----------
    ctx = b.new_context(service_workers="block", locale="en-GB"); route(ctx)
    p = new_page(ctx); login(p, "other@example.com"); app_ready(p)
    check(p.inner_text("#collName") == "Collection B" and "Aurelian" not in p.content(), "second client sees only Collection B")
    check(p.get_attribute('meta[name="apple-mobile-web-app-title"]', "content") == "B" and "Collection B" in p.title(), "second client: label follows their own collection")
    ctx.close()
    # ---------- 14. Dylan (admin): email code + authenticator, then collection choice ----------
    ctx = b.new_context(service_workers="block", locale="en-GB"); route(ctx)
    p = new_page(ctx); login(p, "dylan@legacy-shaper.com"); p.wait_for_selector("#gate h1:has-text('Security code')")
    p.fill("#gCode", "111111"); p.click("#gForm .btn"); p.wait_for_timeout(300)
    check("does not match" in p.inner_text("#gMsg"), "admin: wrong authenticator code refused")
    p.fill("#gCode", "123456"); p.click("#gForm .btn"); p.wait_for_selector("[data-c]")
    check(p.locator("[data-c]").count() == 2, "admin: chooses among all collections")
    p.click(f"[data-c='{CID}']"); app_ready(p)
    p.click("[data-t=expenses]")
    check("Internal commission" not in p.inner_text("#main"), "admin preview shows exactly what the client sees")
    p.click("#btnMenu"); check(p.locator("#mSwitch").count() == 1, "admin: change collection from the menu")
    ctx.close()
    # ---------- 15. phone layout ----------
    ctx = b.new_context(service_workers="block", locale="en-GB", viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"); route(ctx)
    p = new_page(ctx); login(p, "client@example.com"); app_ready(p)
    check("Share button" in p.inner_text(".install"), "iPhone: install steps for Safari shown")
    check(p.evaluate("document.documentElement.scrollWidth<=window.innerWidth"), "iPhone: no horizontal scrolling")
    p.screenshot(path=os.path.join(os.environ.get("SHOTS", "/tmp"), "client-phone.png"), full_page=False)
    p.click("[data-t=works]"); p.click("[data-w=aur-05]"); p.wait_for_selector("#detail .dh"); p.wait_for_timeout(400)
    check(p.evaluate("document.getElementById('detail').scrollWidth<=window.innerWidth"), "iPhone: detail fits the screen")
    p.screenshot(path=os.path.join(os.environ.get("SHOTS", "/tmp"), "client-phone-detail.png"))
    ctx.close()
    ctx = b.new_context(service_workers="block", locale="en-GB", viewport={"width": 1440, "height": 900}); route(ctx)
    p = new_page(ctx); login(p, "client@example.com"); app_ready(p); p.wait_for_timeout(300)
    p.screenshot(path=os.path.join(os.environ.get("SHOTS", "/tmp"), "client-desktop.png"))
    p.click("[data-t=works]"); p.wait_for_timeout(200); p.screenshot(path=os.path.join(os.environ.get("SHOTS", "/tmp"), "client-desktop-works.png"))
    p.click("[data-w=aur-05]"); p.wait_for_selector("#detail .dh"); p.wait_for_timeout(500); p.screenshot(path=os.path.join(os.environ.get("SHOTS", "/tmp"), "client-desktop-detail.png"))
    p.click("#dBack"); p.click("[data-t=expenses]"); p.wait_for_timeout(200); p.screenshot(path=os.path.join(os.environ.get("SHOTS", "/tmp"), "client-desktop-expenses.png"), full_page=True)
    ctx.close()
    ctx = b.new_context(service_workers="block", locale="en-GB", viewport={"width": 1440, "height": 900}); route(ctx)
    p = new_page(ctx); p.goto(URL); p.wait_for_selector("#gEmail"); p.wait_for_timeout(200); p.screenshot(path=os.path.join(os.environ.get("SHOTS", "/tmp"), "client-gate.png"))
    ctx.close()
    b.close()

real = [e for e in errors if "Failed to fetch" not in e and "net::ERR" not in e]
check(not real, "no script error in any scenario" + (": " + " | ".join(real[:3]) if real else ""))
srv.shutdown()
print(f"\nALL {ok} CHECKS PASSED")
