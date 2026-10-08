#!/usr/bin/env python3
"""View at scale as an automatic fixed image, master app + client app (shared engine tools/room.js):
   image among the photos, wall colour, position adjusted in the full-screen view, enlarged view, PDF page on demand.
   Run: python3 tests/test_scale_view.py   (screenshots in /tmp/ls-scale-*.png)"""
import base64, io, json, os, re, struct, sys, threading, http.server, functools, zlib
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = 0
def check(c, label):
    global ok
    if not c: print("FAIL:", label); sys.exit(1)
    ok += 1; print("ok  ", label)

def png(w, h, rgb=(180, 60, 40)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b"")
durl = lambda b: "data:image/png;base64," + base64.b64encode(b).decode()
THUMB, HD = durl(png(60, 60)), durl(png(1000, 1300))

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8771), functools.partial(Quiet, directory=R))
threading.Thread(target=srv.serve_forever, daemon=True).start()
DIM = "u=>new Promise(r=>{const i=new Image();i.onload=()=>r([i.width,i.height]);i.onerror=()=>r(null);i.src=u;})"
errors = []

# fake jsPDF that records what the fiche export puts in the PDF (the real library is a CDN download)
FAKE_PDF = """window.jspdf={jsPDF:function(){const log=window.__pdfLog=[];return {internal:{pageSize:{getWidth:()=>595.28,getHeight:()=>841.89}},
  addImage:(u,t,x,y,w,h)=>log.push(['img',u.slice(0,30),u.length,Math.round(w),Math.round(h)]),addPage:()=>log.push(['page']),setFont(){},setFontSize(){},setTextColor(){},
  text:(s)=>log.push(['text',s]),setProperties(){},output:()=>new Blob(['%PDF'],{type:'application/pdf'})};}};
window.html2canvas=async()=>{const c=document.createElement('canvas');c.width=20;c.height=28;return c;};"""

with sync_playwright() as pw:
    b = pw.chromium.launch()
    # ======================= MASTER =======================
    MOCK = open(os.path.join(R, "tests", "master_mock.js"), encoding="utf-8").read()
    SEED = {"docs": [
        {"coll": "settings", "id": "company", "data": {"name": "Legacy Shaper Collection - FZCO"}, "updated_at": "2026-10-01T00:00:00Z"},
        {"coll": "artworks", "id": "art1", "data": {"id": "art1", "artist": "Pierre Soulages", "title": "Peinture", "year": "1959", "category": "painting", "dimensions": "130 x 100 cm", "owner": "Collection DL", "photo": THUMB, "primaryViewId": "v1"}, "updated_at": "2026-10-01T00:00:00Z"},
        {"coll": "artworks/art1/views", "id": "v1", "data": {"id": "v1", "photo": HD, "createdAt": "2026-10-01"}, "updated_at": "2026-10-01T00:00:00Z"},
        {"coll": "artworks", "id": "art2", "data": {"id": "art2", "artist": "Alexander Calder", "title": "Mobile", "category": "sculpture", "dimensions": "80 x 120 x 60 cm", "photo": THUMB}, "updated_at": "2026-10-01T00:00:00Z"},
        {"coll": "artworks", "id": "art3", "data": {"id": "art3", "artist": "Jean Dubuffet", "title": "Sans titre", "category": "painting", "dimensions": "", "photo": THUMB}, "updated_at": "2026-10-01T00:00:00Z"},
    ], "tables": {"collections": [], "collection_members": [], "profiles": [{"id": "u9", "email": "dylan@legacy-shaper.com", "role": "admin"}]}, "files": {}}
    for name, vp in [("mac", dict(width=1400, height=900)), ("iphone", dict(width=390, height=844))]:
        ctx = b.new_context(service_workers="block", viewport=vp, device_scale_factor=2 if name == "iphone" else 1, accept_downloads=True)
        ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
        ctx.route(re.compile(r"https://(cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com)/.*"), lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
        p = ctx.new_page(); p.add_init_script(f"window.__MASTER_SEED={json.dumps(SEED)};")
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto("http://127.0.0.1:8771/app/"); p.wait_for_selector("#gEmail")
        p.fill("#gEmail", "dylan@legacy-shaper.com"); p.fill("#gPass", "good-pass"); p.click("#gForm button[type=submit]"); p.wait_for_selector("#gCode")
        p.fill("#gCode", "123456"); p.click("#gForm button[type=submit]")
        p.wait_for_function("typeof state!=='undefined' && state.artworks && state.artworks.art1", timeout=15000)
        DOC = lambda i: p.evaluate(f"__mockDB().docs.find(x=>x.coll==='artworks'&&x.id==='{i}').data")
        def open_art(i):
            p.evaluate(f"state.curArt='{i}'; leaveHome('artworks'); document.body.classList.add('alt-detail'); renderAlt(); window.scrollTo(0,0);")
            p.wait_for_selector("#viewsBox")
        open_art("art1")
        p.wait_for_selector("#scaleOpen img", timeout=20000)
        src = p.get_attribute("#scaleOpen img", "src")
        check(src.startswith("data:image/jpeg") and p.evaluate(DIM, src) == [1600, 1200], f"{name}: master — at-scale image made automatically (1600 x 1200)")
        check(p.evaluate("canViewAtScale(state.artworks.art1) && Math.abs(artRect((()=>{const s={dims:parseDims('130 x 100 cm'),chair:null};roomDefaults(s,false);roomFit(s,1600,1200,1,true);return s;})()).h/ (()=>{const s={dims:parseDims('130 x 100 cm'),chair:null};roomDefaults(s,false);roomFit(s,1600,1200,1,true);return s.scale;})() - 130) < 0.01"), f"{name}: master — work drawn at exactly 130 cm high")
        check(p.locator("#ficheScale").count() == 1 and not p.is_checked("#ficheScale"), f"{name}: master — 'Vue à l’échelle dans le PDF' box, unticked by default")
        # wall colour
        p.click("[data-scwall=green]"); p.wait_for_timeout(1500)
        check(DOC("art1").get("scaleView", {}).get("wall") == "green", f"{name}: master — wall colour saved on the work")
        p.wait_for_function("(()=>{const i=document.querySelector('#scaleOpen img'); if(!i||!i.complete) return false; const c=document.createElement('canvas'); c.width=i.naturalWidth; c.height=i.naturalHeight; const x=c.getContext('2d'); x.drawImage(i,0,0); const d=x.getImageData(40,300,1,1).data; return d[1]>d[0]&&d[1]<110; })()", timeout=10000)
        check(True, f"{name}: master — image redrawn with the green wall")
        if name == "mac": p.screenshot(path="/tmp/ls-scale-master-card.png", full_page=False)
        # adjust the position in the full-screen view, same frame as the image
        p.click("#scaleAdjust"); p.wait_for_selector("#room:not([hidden]) canvas"); p.wait_for_function("R.W && R.floor && R.art && R.chair")
        check(p.inner_text("#rSave") == "Enregistrer" and abs(p.evaluate("R.W/R.H") - 4 / 3) < 0.01, f"{name}: master — editor opens in the image's 4:3 frame, with 'Enregistrer'")
        check(p.evaluate("R.wall") == "green", f"{name}: master — editor starts from the saved wall")
        a0 = p.evaluate("R.artX"); box = p.locator("#rCv").bounding_box(); ar = p.evaluate("artRect()")
        x0, y0 = box["x"] + ar["x"] + ar["w"] / 2, box["y"] + ar["y"] + ar["h"] / 2
        p.mouse.move(x0, y0); p.mouse.down(); p.mouse.move(x0 + 40, y0 - 20, steps=5); p.mouse.up()
        moved = p.evaluate("({x:R.artX,y:R.artY})")
        check(moved["x"] > a0, f"{name}: master — the work moves in the editor")
        if name == "iphone": p.screenshot(path="/tmp/ls-scale-master-editor-iphone.png")
        p.click("#rSave"); p.wait_for_timeout(1500)
        sv = DOC("art1").get("scaleView", {})
        check(abs(sv.get("artX", 0) - moved["x"]) < 0.01 and abs(sv.get("artY", 0) - moved["y"]) < 0.01 and sv.get("wall") == "green", f"{name}: master — position saved on the work")
        check(p.locator("#room").is_hidden(), f"{name}: master — editor closed after saving")
        p.wait_for_function("(()=>{const i=document.querySelector('#scaleOpen img'); return i && i.complete && i.naturalWidth===1600})()")
        # enlarged view
        p.click("#scaleOpen"); p.wait_for_selector("#scBigImg")
        p.wait_for_function("document.querySelector('#scBigImg').naturalWidth===2400")
        check(True, f"{name}: master — tap enlarges the image (2400 px)")
        if name == "mac": p.screenshot(path="/tmp/ls-scale-master-big.png")
        p.keyboard.press("Escape"); p.wait_for_timeout(150)
        check(p.locator("#ovsc").count() == 0, f"{name}: master — Escape closes it")
        # PDF: without the box no at-scale page, with the box one page
        p.add_script_tag(content=FAKE_PDF)
        p.evaluate("exportFiche()"); p.wait_for_function("window.__pdfLog && window.__pdfLog.length>0"); p.wait_for_timeout(400)
        log = p.evaluate("window.__pdfLog")
        check(not any(e[0] == "text" and "at scale" in e[1] for e in log), f"{name}: master — PDF without the at-scale page when unticked")
        p.check("#ficheScale"); p.wait_for_timeout(1500)
        check(DOC("art1").get("scalePdf") == "1", f"{name}: master — PDF choice saved on the work")
        check(p.is_checked("#scalePdfBar"), f"{name}: master — the box under the image follows")
        p.uncheck("#scalePdfBar"); p.wait_for_timeout(1500)
        check(DOC("art1").get("scalePdf") == "" and not p.is_checked("#ficheScale"), f"{name}: master — unticked under the image, both boxes agree")
        p.check("#scalePdfBar"); p.wait_for_timeout(1500)
        p.evaluate("window.__pdfLog=null; exportFiche()"); p.wait_for_function("window.__pdfLog && window.__pdfLog.some(e=>e[0]==='text')", timeout=20000)
        log = p.evaluate("window.__pdfLog")
        imgs = [e for e in log if e[0] == "img"]
        check(log.count(["page"]) == 1 and any("at scale" in e[1] for e in log if e[0] == "text"), f"{name}: master — PDF: fiche + one at-scale page")
        check(imgs[-1][1].startswith("data:image/jpeg") and abs(imgs[-1][3] / imgs[-1][4] - 4 / 3) < 0.01, f"{name}: master — at-scale page is the 4:3 image, undistorted")
        # works that are not hung on a wall / without dimensions
        open_art("art2"); p.wait_for_timeout(300)
        check(p.locator("#scaleBox").count() == 0 and p.locator("#ficheScale").count() == 0, f"{name}: master — no at-scale image for a sculpture")
        open_art("art3"); p.wait_for_timeout(300)
        check("Indiquez les dimensions" in p.inner_text("#scaleWrap"), f"{name}: master — missing dimensions: hint instead of the image")
        p.fill("#k_dimensions", "65 x 54 cm"); p.wait_for_selector("#scaleOpen img", timeout=20000)
        check(True, f"{name}: master — image appears as soon as dimensions are typed")
        check(p.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f"{name}: master — no horizontal scroll")
        ctx.close()

    # ======================= CLIENT =======================
    CMOCK = open(os.path.join(R, "tests", "client_mock.js"), encoding="utf-8").read()
    demo = json.load(open(os.path.join(R, "tests", "demo.json"), encoding="utf-8"))
    for w in demo["works"]:
        if w["id"] == "aur-07": w["scale_view"] = {"wall": "green", "artX": 40, "artY": 160, "chairX": -70}
    CSEED = {"users": [dict(id="u1", email="client@example.com", role="client")], "members": [dict(user_id="u1", collection_id=demo["coll"]["id"])],
             "tables": {"profiles": [dict(id="u1", role="client")], "collections": [demo["coll"]], "artworks": demo["works"],
                        "artwork_views": demo["views"], "expenses": demo["expenses"], "documents": []}, "files": {}}
    csrv = http.server.ThreadingHTTPServer(("127.0.0.1", 8772), functools.partial(Quiet, directory=os.path.join(R, "client")))
    threading.Thread(target=csrv.serve_forever, daemon=True).start()
    for name, vp, mobile in [("mac", dict(width=1366, height=860), False), ("iphone", dict(width=390, height=844), True)]:
        ctx = b.new_context(viewport=vp, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile, service_workers="block", locale="fr-FR")
        ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=CMOCK))
        ctx.route("**/jszip.min.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
        ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda r: r.fulfill(status=200, content_type="text/css", body=""))
        p = ctx.new_page(); p.add_init_script(f"window.__SEED={json.dumps(CSEED)};window.__NET=true;window.LS_POLL_MS=600000;")
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto("http://127.0.0.1:8772/"); p.wait_for_selector("#gEmail"); p.fill("#gEmail", "client@example.com"); p.click("#gForm .btn")
        p.wait_for_selector("#gCode"); p.fill("#gCode", "42424242"); p.wait_for_selector("#app:not([hidden])"); p.wait_for_timeout(700)
        p.evaluate("openWork('aur-01')"); p.wait_for_selector("#detail:not([hidden]) .dh")
        p.wait_for_function("(()=>{const i=document.querySelector('#dScThumb'); return i && i.src && i.complete && i.naturalWidth===1600})()", timeout=20000)
        check("à l’échelle" in p.inner_text("#dScTile").lower(), f"{name}: client — 'À l’échelle' image among the views, made automatically")
        check(p.locator("#dScBar").is_hidden(), f"{name}: client — controls hidden until the image is chosen")
        p.click("#dScTile"); p.wait_for_function("(()=>{const i=document.querySelector('#dImg'); return i && i.naturalWidth===1600})()")
        check(p.locator("#dScBar").is_visible(), f"{name}: client — chosen: shown large, controls underneath")
        p.click("[data-scwall=linen]"); p.wait_for_timeout(600)
        check(json.loads(p.evaluate("localStorage.getItem('ls-scale:aur-01')"))["wall"] == "linen", f"{name}: client — wall colour kept on this device")
        p.click("#dScAdj"); p.wait_for_selector("#room:not([hidden]) canvas"); p.wait_for_function("R.W && R.floor && R.art && R.chair")
        check(p.inner_text("#rSave") == "Enregistrer" and abs(p.evaluate("R.W/R.H") - 4 / 3) < 0.01 and p.evaluate("R.wall") == "linen", f"{name}: client — 'Ajuster l’emplacement' opens the editor in the same frame")
        box = p.locator("#rCv").bounding_box(); c = p.evaluate("(()=>{const c=chairRect();return {x:c.x+c.w/2,y:c.y+c.h*0.6}})()"); c0 = p.evaluate("R.chairX")
        p.mouse.move(box["x"] + c["x"], box["y"] + c["y"]); p.mouse.down(); p.mouse.move(box["x"] + c["x"] + 25, box["y"] + c["y"], steps=5); p.mouse.up()
        c1 = p.evaluate("R.chairX"); check(c1 > c0, f"{name}: client — chair moved")
        p.click("#rSave"); p.wait_for_timeout(500)
        check(abs(json.loads(p.evaluate("localStorage.getItem('ls-scale:aur-01')"))["chairX"] - c1) < 0.01, f"{name}: client — position saved")
        if mobile: p.screenshot(path="/tmp/ls-scale-client-iphone.png")
        else: p.screenshot(path="/tmp/ls-scale-client-mac.png")
        # the existing "Voir à l’échelle" button keeps working
        check(p.locator("#dRoom").count() == 1, f"{name}: client — 'Voir à l’échelle' button still there")
        # PDF sheet: real print to PDF, page count
        if not mobile:
            def print_pdf():
                p.evaluate("window.print=()=>{window.__printed=(window.__printed||0)+1}")
                p.evaluate("window.__printed=0"); p.click("#dPdf"); p.wait_for_function("window.__printed>0", timeout=20000)
                p.emulate_media(media="print"); data = p.pdf(format="A4"); p.emulate_media(media="screen")
                return PdfReader(io.BytesIO(data))
            r1 = print_pdf()
            check(p.locator("#print .pscale").count() == 0 and "chelle" not in r1.pages[-1].extract_text(), f"{name}: client — no at-scale page when unticked ({len(r1.pages)} pages)")
            p.check("#dScPdf")
            r2 = print_pdf()
            last = r2.pages[-1]
            check(len(r2.pages) == len(r1.pages) + 1 and p.locator("#print .pscale img").count() == 1 and "chelle" in last.extract_text() and len(last.images) == 1, f"{name}: client — ticked: one more page, with the at-scale image ({len(r2.pages)} pages)")
            check(p.evaluate("localStorage.getItem('ls-scalepdf:aur-01')") == "1", f"{name}: client — PDF choice kept")
        # a work whose composition was set in The Legacy: the client starts from it
        p.evaluate("openWork('aur-07')"); p.wait_for_selector("#detail:not([hidden]) .dh")
        p.wait_for_function("(()=>{const i=document.querySelector('#dScThumb'); return i && i.complete && i.naturalWidth===1600})()", timeout=20000)
        check(p.locator("[data-scwall=green].on").count() == 1, f"{name}: client — starts from the wall chosen in The Legacy")
        p.click("#dScTile"); p.click("#dScAdj"); p.wait_for_selector("#room:not([hidden]) canvas"); p.wait_for_function("R.W && R.art")
        check(p.evaluate("Math.abs(R.artX-40)<1e-6 && Math.abs(R.artY-160)<1e-6 && Math.abs(R.chairX+70)<1e-6"), f"{name}: client — starts from the position set in The Legacy")
        p.click("#rBack"); p.wait_for_timeout(100)
        # sculpture: no tile
        p.evaluate("openWork('aur-11')"); p.wait_for_selector("#detail:not([hidden]) .dh")
        check(p.locator("#dScTile").count() == 0, f"{name}: client — no at-scale image for a volume")
        ctx.close()
    # database without the scale_view column (before SQL 005): the collection still opens
    OLDMOCK = CMOCK.replace("select() { return q; },", "select(c) { if (table === 'artworks' && String(c || '').includes('scale_view')) ins = '__nocol'; return q; },")
    OLDMOCK = OLDMOCK.replace("if (ins) {", "if (ins === '__nocol') return Promise.resolve({ data: null, error: { code: '42703', message: 'column artworks.scale_view does not exist' } }).then(res, rej);\n          if (ins) {", 1)
    assert OLDMOCK != CMOCK
    ctx = b.new_context(viewport=dict(width=1366, height=860), service_workers="block", locale="fr-FR")
    ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=OLDMOCK))
    ctx.route("**/jszip.min.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
    ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda r: r.fulfill(status=200, content_type="text/css", body=""))
    p = ctx.new_page(); p.add_init_script(f"window.__SEED={json.dumps(CSEED)};window.__NET=true;window.LS_POLL_MS=600000;")
    p.goto("http://127.0.0.1:8772/"); p.wait_for_selector("#gEmail"); p.fill("#gEmail", "client@example.com"); p.click("#gForm .btn")
    p.wait_for_selector("#gCode"); p.fill("#gCode", "42424242"); p.wait_for_selector("#app:not([hidden])"); p.wait_for_timeout(900)
    check(p.evaluate("S.data && S.data.works && S.data.works.length") == len(demo["works"]), "client — collection opens even without the scale_view column")
    ctx.close()
    csrv.shutdown()
    check(not errors, "no script error" + (": " + "; ".join(errors[:3]) if errors else ""))
    b.close()
srv.shutdown()
print(f"\nALL {ok} CHECKS PASSED")
