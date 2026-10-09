#!/usr/bin/env python3
"""Several works in one PDF (master app): works list → « Sélectionner pour un PDF » → tick works → « Créer le PDF »
   = one full-page fiche per work (same template as « Fiche PDF »), in list order, in a single file.
   Run: python3 tests/test_master_fiche_set.py   (screenshots in /tmp/ls-ficheset-*.png)"""
import json, os, sys, threading, http.server, functools, re
from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = open(os.path.join(R, "tests", "master_mock.js"), encoding="utf-8").read()
PX = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
HD = PX.replace("data:image/png", "data:image/png")  # stand-in for the HD primary view
SEED = {"docs": [
    {"coll": "settings", "id": "company", "data": {"name": "Legacy Shaper Collection - FZCO"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "artworks", "id": "a1", "data": {"id": "a1", "artist": "Pierre Soulages", "title": "Peinture", "year": "1959", "medium": "Huile sur toile", "dimensions": "130 x 100 cm", "photo": PX, "primaryViewId": "v1", "provenance": "Galerie de France, Paris"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "artworks/a1/views", "id": "v1", "data": {"id": "v1", "photo": HD + "#hd1", "createdAt": "2026-10-01"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "artworks", "id": "a2", "data": {"id": "a2", "artist": "Alexander Calder", "title": "Mobile", "year": "1962", "photo": PX + "#th2"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "artworks", "id": "a3", "data": {"id": "a3", "artist": "Andy Warhol", "title": "Flowers", "year": "1964", "photo": PX + "#th3"}, "updated_at": "2026-10-01T00:00:00Z"},
    {"coll": "artworks", "id": "a4", "data": {"id": "a4", "artist": "Georg Baselitz", "title": "Ohne Titel", "photo": ""}, "updated_at": "2026-10-01T00:00:00Z"},
], "tables": {"collections": [], "collection_members": [], "profiles": [{"id": "u9", "email": "dylan@legacy-shaper.com", "role": "admin"}]}, "files": {}}

# jsPDF / html2canvas come from a CDN the sandbox cannot reach: stand-ins that record every page and the fiche staged for it
FAKE_PDF = """window.jspdf={jsPDF:function(){const log=window.__pdfLog=[];return {internal:{pageSize:{getWidth:()=>595.28,getHeight:()=>841.89}},
  addImage:(u,t,x,y,w,h)=>log.push(['img',Math.round(w),Math.round(h)]),addPage:()=>log.push(['page']),setFont(){},setFontSize(){},setTextColor(){},
  text:(s)=>log.push(['text',s]),setProperties:(p)=>{window.__pdfProps=p;},getNumberOfPages:()=>1+log.filter(x=>x[0]==='page').length,output:()=>new Blob(['%PDF'],{type:'application/pdf'})};}};
window.__staged=[];
window.html2canvas=async(el)=>{window.__staged.push({cls:el.className,text:el.innerText,img:(el.querySelector('.fbox img')||{}).src||'',logo:!!el.querySelector('img.fl')});
  const c=document.createElement('canvas');c.width=20;c.height=28;return c;};0;"""

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8774), functools.partial(Quiet, directory=R))
threading.Thread(target=srv.serve_forever, daemon=True).start()
ok = 0
def check(c, label):
    global ok
    if not c: print("FAIL:", label); srv.shutdown(); sys.exit(1)
    ok += 1; print("ok  ", label)

errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for name, vp in [("mac", dict(width=1400, height=900)), ("iphone", dict(width=390, height=844))]:
        ctx = b.new_context(service_workers="block", viewport=vp, device_scale_factor=2 if name == "iphone" else 1, accept_downloads=True)
        ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
        ctx.route("**/jszip.min.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=open("/opt/npm-tools/node_modules/jszip/dist/jszip.min.js").read()))
        ctx.route(re.compile(r"https://(cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com)/.*"), lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
        p = ctx.new_page(); p.add_init_script(f"window.__MASTER_SEED={json.dumps(SEED)};")
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto("http://127.0.0.1:8774/app/"); p.wait_for_selector("#gEmail")
        p.fill("#gEmail", "dylan@legacy-shaper.com"); p.fill("#gPass", "good-pass"); p.click("#gForm button[type=submit]"); p.wait_for_selector("#gCode")
        p.fill("#gCode", "123456"); p.click("#gForm button[type=submit]")
        p.wait_for_function("typeof state!=='undefined' && state.artworks && state.artworks.a4", timeout=15000)
        p.evaluate(FAKE_PDF)
        p.evaluate("leaveHome('artworks'); document.body.classList.remove('alt-detail'); renderAlt(); window.scrollTo(0,0);")
        p.wait_for_selector("#selStart")
        check(p.locator("#selBar").count() == 0, f"{name}: normal list, no selection bar")
        p.click("#selStart"); p.wait_for_selector("#selBar")
        check(p.locator("#selGo").is_disabled(), f"{name}: « Créer le PDF » disabled until a work is ticked")
        # ticking does not open the work
        p.click("[data-art=a3]"); p.click("[data-art=a1]")
        check(not p.evaluate("document.body.classList.contains('alt-detail')"), f"{name}: ticking a work does not open it")
        check(p.locator(".art.picked").count() == 2 and "2 fiches" in p.inner_text("#selGo"), f"{name}: 2 works ticked, button says « 2 fiches »")
        p.click("[data-art=a3]"); p.click("[data-art=a2]"); p.click("[data-art=a3]")
        check(p.locator(".art.picked").count() == 3, f"{name}: untick / re-tick works")
        p.screenshot(path=f"/tmp/ls-ficheset-{name}-select.png")
        # provenance option of the fiche applies to every page
        p.evaluate("state.ficheProv=true")
        p.click("#selGo")
        p.wait_for_function("window.__lastFicheSet", timeout=15000)
        st = p.evaluate("window.__staged"); log = p.evaluate("window.__pdfLog")
        check(p.evaluate("window.__lastFicheSet.pages") == 3 and len([x for x in log if x[0] == 'img']) == 3, f"{name}: one PDF, 3 pages, one full-page image each")
        check(all(x[1] == 595 and x[2] == 842 for x in log if x[0] == 'img'), f"{name}: every page is a full A4 page")
        order = [s["text"].split("\n")[0] for s in st]
        check(order == ["Alexander Calder", "Andy Warhol", "Pierre Soulages"], f"{name}: pages in list order (by artist): {order}")
        check(all(s["cls"] == "fiche" and s["logo"] for s in st), f"{name}: each page uses the fiche template with the logo")
        check(st[2]["img"].endswith("#hd1"), f"{name}: Soulages page uses the HD primary view, not the thumbnail")
        check(st[0]["img"].endswith("#th2") and st[1]["img"].endswith("#th3"), f"{name}: each work gets its own photo")
        check("Galerie de France, Paris" in st[2]["text"] and "Copyright The Artist" in st[2]["text"], f"{name}: caption, provenance and copyright lines present")
        check(re.match(r"Legacy_Shaper_-_3_works_-_\d{4}-\d\d-\d\d\.pdf$", p.evaluate("window.__lastFicheSet.name")), f"{name}: file name « Legacy_Shaper_-_3_works_-_date.pdf »")
        check(p.locator("#selBar").count() == 0 and p.locator("#selStart").count() == 1, f"{name}: back to the normal list after the PDF")
        check(p.evaluate("document.getElementById('pdfstage').innerHTML") == "", f"{name}: staging area emptied")
        # select all / cancel, and the filters are respected by « Tout sélectionner »
        p.click("#selStart"); p.click("#selAll")
        check(p.locator(".art.picked").count() == 4 and "Tout désélectionner" in p.inner_text("#selAll"), f"{name}: « Tout sélectionner » ticks every visible work")
        p.click("#selAll"); check(p.locator(".art.picked").count() == 0, f"{name}: « Tout désélectionner » clears")
        p.fill("#q2", "warhol"); p.wait_for_timeout(100); p.click("#selAll")
        check(p.evaluate("artSel.size") == 1 and p.evaluate("[...artSel][0]") == "a3", f"{name}: « Tout sélectionner » follows the search filter")
        p.fill("#q2", ""); p.click("#selCancel")
        check(p.locator("#selBar").count() == 0 and p.evaluate("artSel") is None, f"{name}: « Annuler » leaves selection mode")
        # a single work: same file name as its own fiche
        p.evaluate("window.__lastFicheSet=null; window.__staged=[]; exportFicheSet(['a4'])")
        p.wait_for_function("window.__lastFicheSet", timeout=10000)
        check(p.evaluate("window.__lastFicheSet.name") == "Georg_Baselitz_-_Ohne_Titel_-_Legacy_Shaper.pdf" and p.evaluate("window.__lastFicheSet.pages") == 1, f"{name}: one work = its usual fiche file name, 1 page")
        # the usual single-work fiche still works
        p.evaluate("window.__staged=[]; state.curArt='a2'; document.body.classList.add('alt-detail'); renderAlt();")
        p.wait_for_selector("#artFiche"); p.click("#artFiche"); p.wait_for_function("window.__staged.length===1", timeout=10000)
        check(p.evaluate("window.__staged[0].text").startswith("Alexander Calder"), f"{name}: single « Fiche PDF » unchanged")
        ctx.close()
    b.close()
srv.shutdown()
check(not errors, "no page errors: " + "; ".join(errors[:3]))
print(f"\n{ok} checks passed")
