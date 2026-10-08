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
from PIL import Image, ImageDraw, ImageFilter
def jpg_url(im):
    b = io.BytesIO(); im.save(b, "JPEG", quality=92); return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
def backdrop(n=900):
    bg = Image.new("RGB", (n, n)); px = bg.load()
    for y in range(n):
        for x in range(n): v = 240 - int(y * 0.02) - int(x * 0.01); px[x, y] = (v, v, v - 2)
    return bg
def openwork():          # grid of dark bars, square 600 px, hung at 9°, with soft photo shadows (like a Morellet grid)
    g = Image.new("L", (600, 600), 0); d = ImageDraw.Draw(g)
    for i in range(0, 601, 50): d.line([(i, 0), (i, 600)], fill=255, width=6); d.line([(0, i), (600, i)], fill=255, width=6)
    g = g.rotate(-9, expand=True, resample=Image.BICUBIC)
    bg = backdrop(); off = ((900 - g.width) // 2, (900 - g.height) // 2)
    sh = g.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.25))
    bg.paste((150, 150, 150), (off[0] + 8, off[1] + 10), sh); bg.paste((25, 25, 28), off, g)
    return bg
def solid():             # painting with white areas, hung at 6°
    art = Image.new("RGB", (600, 450), (250, 250, 248)); d = ImageDraw.Draw(art)
    d.rectangle((40, 40, 300, 410), fill=(30, 60, 140)); d.rectangle((330, 60, 560, 200), fill=(200, 40, 40))
    art = art.convert("RGBA").rotate(6, expand=True, resample=Image.BICUBIC); bg = backdrop(); bg.paste(art, (150, 170), art); return bg
def fullframe():         # a painting photographed edge to edge: no background to remove
    im = Image.new("RGB", (800, 600), (120, 40, 30)); d = ImageDraw.Draw(im); d.rectangle((0, 300, 800, 600), fill=(30, 30, 90)); return im
def shapes_cut():        # coloured shaped panels on a white wall, the photo cutting the work at the top and bottom (like the Sperling photo)
    bg = backdrop(); d = ImageDraw.Draw(bg); import random; rnd = random.Random(3)
    for i in range(60):
        x = rnd.randint(150, 700); y = rnd.randint(-60, 900); c = rnd.choice([(120, 60, 160), (220, 60, 90), (240, 120, 70), (200, 80, 160)])
        d.ellipse((x, y, x + rnd.randint(40, 120), y + rnd.randint(20, 70)), fill=c)
    return bg
def tight():             # whole painting, framed with only a thin strip of wall around it
    bg = backdrop(700); d = ImageDraw.Draw(bg); d.rectangle((14, 160, 686, 540), fill=(40, 70, 130)); d.rectangle((300, 200, 600, 400), fill=(245, 245, 240)); return bg
def pair():              # two figures (one white like the backdrop) on a studio backdrop with floor shadows
    W_, H_ = 1164, 936; bg = Image.new("RGB", (W_, H_)); px = bg.load()
    for y in range(H_):
        for x in range(W_): v = 236 - int(y * 0.03); px[x, y] = (v, v, v - 1)
    sh = Image.new("L", (W_, H_), 0); d = ImageDraw.Draw(sh); d.ellipse((250, 790, 560, 840), fill=120); d.ellipse((640, 800, 920, 845), fill=120)
    bg.paste((150, 150, 150), (0, 0), sh.filter(ImageFilter.GaussianBlur(14))); d = ImageDraw.Draw(bg)
    def fig(x0, top, bottom, w, col, out):
        d.rounded_rectangle((x0, top + 120, x0 + w, bottom), 40, fill=col, outline=out, width=3); d.ellipse((x0 - 20, top + 20, x0 + w + 20, top + 200), fill=col, outline=out, width=3)
        d.ellipse((x0 + 10, top - 60, x0 + 60, top + 60), fill=col, outline=out, width=3); d.ellipse((x0 + w - 60, top - 60, x0 + w - 10, top + 60), fill=col, outline=out, width=3)
    fig(300, 140, 820, 210, (250, 250, 250), (150, 150, 150)); fig(680, 250, 825, 200, (240, 140, 170), (160, 80, 100))
    return bg
PAIR_URL = jpg_url(pair())
def ghost():             # a white figure with no outline on a white backdrop: only its face shows — must not be cut into pieces
    bg = backdrop(900); d = ImageDraw.Draw(bg)
    d.ellipse((330, 120, 380, 260), fill=(238, 238, 236)); d.ellipse((420, 120, 470, 260), fill=(238, 238, 236))   # ears, same as the wall
    d.ellipse((300, 240, 500, 420), fill=(239, 239, 237)); d.rectangle((330, 400, 470, 760), fill=(238, 238, 236))
    d.ellipse((370, 300, 390, 320), fill=(40, 160, 60)); d.ellipse((410, 300, 430, 320), fill=(40, 160, 60)); d.ellipse((360, 350, 440, 385), fill=(220, 30, 40))
    d.text((340, 170), "ka", fill=(200, 60, 120)); d.text((430, 170), "i", fill=(200, 60, 120))
    return bg
GHOST_URL = jpg_url(ghost())
OPEN_URL, SOLID_URL, FULL_URL, CUT_URL, TIGHT_URL = jpg_url(openwork()), jpg_url(solid()), jpg_url(fullframe()), jpg_url(shapes_cut()), jpg_url(tight())

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
        {"coll": "artworks", "id": "art4", "data": {"id": "art4", "artist": "Takashi Murakami", "title": "Kaikai & Kiki", "category": "sculpture", "dimensions": "Kaikai: 96.5 x 55.3 x 40 cm | 38 x 21 3/4 x 15 3/4 inches · Kiki: 81.1 x 57.6 x 41 cm | 31 15/16 x 22 11/16 x 16 1/8 inches (including pedestal)", "photo": THUMB, "primaryViewId": "v4"}, "updated_at": "2026-10-01T00:00:00Z"},
        {"coll": "artworks/art4/views", "id": "v4", "data": {"id": "v4", "photo": "__PAIR__", "createdAt": "2026-10-01"}, "updated_at": "2026-10-01T00:00:00Z"},
        {"coll": "artworks", "id": "art3", "data": {"id": "art3", "artist": "Jean Dubuffet", "title": "Sans titre", "category": "painting", "dimensions": "", "photo": THUMB}, "updated_at": "2026-10-01T00:00:00Z"},
    ], "tables": {"collections": [], "collection_members": [], "profiles": [{"id": "u9", "email": "dylan@legacy-shaper.com", "role": "admin"}]}, "files": {}}
    for name, vp in [("mac", dict(width=1400, height=900)), ("iphone", dict(width=390, height=844))]:
        ctx = b.new_context(service_workers="block", viewport=vp, device_scale_factor=2 if name == "iphone" else 1, accept_downloads=True)
        ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
        ctx.route(re.compile(r"https://(cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com)/.*"), lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
        p = ctx.new_page(); p.add_init_script(f"window.__MASTER_SEED={json.dumps(SEED).replace('__PAIR__', PAIR_URL)};")
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto("http://127.0.0.1:8771/app/"); p.wait_for_selector("#gEmail")
        p.fill("#gEmail", "dylan@legacy-shaper.com"); p.fill("#gPass", "good-pass"); p.click("#gForm button[type=submit]"); p.wait_for_selector("#gCode")
        p.fill("#gCode", "123456"); p.click("#gForm button[type=submit]")
        p.wait_for_function("typeof state!=='undefined' && state.artworks && state.artworks.art1", timeout=15000)
        DOC = lambda i: p.evaluate(f"__mockDB().docs.find(x=>x.coll==='artworks'&&x.id==='{i}').data")
        def open_art(i):
            p.evaluate(f"state.curArt='{i}'; leaveHome('artworks'); document.body.classList.add('alt-detail'); renderAlt(); window.scrollTo(0,0);")
            p.wait_for_selector("#viewsBox"); p.wait_for_timeout(100)
            p.evaluate("(()=>{ const e=document.querySelector('#scaleOpen')||document.querySelector('#scaleWrap'); if(e) e.scrollIntoView({block:'center'}); })()")
        # nothing heavy while the app opens: the view is prepared only once it is on screen
        p.evaluate("state.curArt='art1'; leaveHome('artworks'); document.body.classList.add('alt-detail'); renderAlt(); window.scrollTo(0,0);")
        p.wait_for_timeout(1200)
        if name == "iphone": check(p.locator("#scaleOpen img").count() == 0, f"{name}: master — off-screen view not prepared")
        open_art("art1")
        p.wait_for_selector("#scaleOpen img", timeout=20000)
        src = p.get_attribute("#scaleOpen img", "src")
        check(src.startswith("data:image/jpeg") and p.evaluate(DIM, src) == [1600, 1200], f"{name}: master — at-scale image made automatically (1600 x 1200)")
        check(p.evaluate("canViewAtScale(state.artworks.art1) && Math.abs(artRect((()=>{const s={dims:parseDims('130 x 100 cm'),chair:null};roomDefaults(s,false);roomFit(s,1600,1200,1,true);return s;})()).h/ (()=>{const s={dims:parseDims('130 x 100 cm'),chair:null};roomDefaults(s,false);roomFit(s,1600,1200,1,true);return s.scale;})() - 130) < 0.01"), f"{name}: master — work drawn at exactly 130 cm high")
        check(p.locator("#ficheScale").count() == 1 and not p.is_checked("#ficheScale"), f"{name}: master — 'Vue à l’échelle dans le PDF' box, unticked by default")
        p.evaluate("window.__HD0=state.views.art1.v1.photo")
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
        if name == "mac":
            r = p.evaluate("""async([o,s,f])=>{ const out={};
              const im=await roomImg(o), k=roomCut(im,parseDims('140 x 140 cm')); out.open=k&&{ang:k.angle*180/Math.PI,rw:k.rw,rh:k.rh,open:k.open};
              if(k){ const x=k.canvas.getContext('2d'); const sc=k.canvas.width/900; // a hole between bars, a bar, a corner outside the work
                const at=(px,py)=>x.getImageData(Math.round(px*sc),Math.round(py*sc),1,1).data[3]; out.hole=at(450-25*Math.cos(0.157)+0,450+25); out.outside=at(30,30); }
              const k2=roomCut(await roomImg(s),parseDims('100 x 133 cm')); out.solid=k2&&{ang:k2.angle*180/Math.PI,open:k2.open,rw:k2.rw,rh:k2.rh};
              if(k2){ const x=k2.canvas.getContext('2d'), sc=k2.canvas.width/900; out.white=x.getImageData(Math.round(560*sc),Math.round(520*sc),1,1).data; }
              out.full=roomCut(await roomImg(f),parseDims('60 x 80 cm')); out.fullInfo=roomCutInfo(await roomImg(f),parseDims('60 x 80 cm'));
              out.mismatch=roomCut(await roomImg(o),parseDims('50 x 140 cm'));
              const c=await roomRender({dimensions:'140 x 140 cm'},o,{wall:'green'}); const g=c.getContext('2d');
              const s2={dims:parseDims('140 x 140 cm'),chair:await roomImg('room-chair.webp'),cut:roomCut(im,parseDims('140 x 140 cm'))}; roomDefaults(s2,false); roomFit(s2,1600,1200,1,true);
              const a=artRect(s2); out.scaleOK=Math.abs(a.w/s2.scale-140)<0.01 && Math.abs(a.h/s2.scale-140)<0.01;
              // the wall shows through the work: centre of a cell is green
              const cx=a.x+a.w/2+a.w/12/2, cy=a.y+a.h/2+a.h/12/2; out.through=[...g.getImageData(Math.round(cx),Math.round(cy),1,1).data];
              const box=artBox(s2); out.box=[box.w,box.h];
              return out; }""", [OPEN_URL, SOLID_URL, FULL_URL])
            o = r["open"]
            check(o and abs(o["ang"] - 9) < 0.8 and o["open"], f"{name}: cut-out — openwork found at its angle ({o and round(o['ang'],2)}°)")
            check(o and abs(o["rw"] / o["rh"] - 1) < 0.06, f"{name}: cut-out — the square outline of the work is found")
            check(r["outside"] == 0, f"{name}: cut-out — background around the work removed")
            check(r["through"][1] > r["through"][0] + 10 and r["through"][1] < 120, f"{name}: cut-out — the wall shows through the open work ({r['through'][:3]})")
            check(r["scaleOK"] and r["box"][0] > 140 and abs(r["box"][0] - 140 * (abs(__import__('math').cos(0.157)) + abs(__import__('math').sin(0.157)))) < 3, f"{name}: cut-out — 140 x 140 cm kept, tilted bounding box {r['box'][0]:.0f} cm")
            s_ = r["solid"]
            check(s_ and abs(s_["ang"] + 6) < 0.8 and not s_["open"], f"{name}: cut-out — solid painting found at its angle, kept whole")
            check(r["white"][3] == 255 and r["white"][0] > 240, f"{name}: cut-out — the painting's white areas are kept")
            check(r["full"] is None, f"{name}: cut-out — photo without background: left as it was")
            check(r["fullInfo"] is None, f"{name}: cut-out — and no warning for an ordinary photo")
            e = p.evaluate("""async([c,tt])=>{ const d=parseDims('200 x 360 cm'); const ic=await roomImg(c);
                const t2=await roomImg(tt), k=roomCut(t2,parseDims('38 x 67 cm'));
                return {cut:roomCut(ic,d), info:roomCutInfo(ic,d), tight:k&&{ang:k.angle,open:k.open,ratio:k.rw/k.rh}}; }""", [CUT_URL, TIGHT_URL])
            check(e["cut"] is None and e["info"] and e["info"]["fail"] == "edge" and sorted(e["info"]["sides"]) == ["bottom", "top"], f"{name}: cut-out — work cut by the photo at the top and bottom: detected ({e['info']})")
            gh = p.evaluate("async(u)=>{ const im=await roomImg(u); return {obj:!!roomObj(im), info:roomObjInfo(im)}; }", GHOST_URL)
            check(not gh["obj"] and gh["info"] and gh["info"]["fail"] in ("unsure", "plain"), f"{name}: cut-out — white piece lost in a white backdrop: refused rather than shown in pieces ({gh['info']})")
            check(e["tight"] and e["tight"]["ang"] == 0 and not e["tight"]["open"] and abs(e["tight"]["ratio"] - 672 / 380) < 0.05, f"{name}: cut-out — tightly framed whole work: still cut out")
            check(r["mismatch"] is None, f"{name}: cut-out — outline far from the dimensions: left as it was")
            # hints in the work's card
            p.evaluate("(u)=>{ state.views.art1.v1.photo=u; const a=state.artworks.art1; a.dimensions='200 x 360 cm'; for(const k in scaleCache) delete scaleCache[k]; scaleRedraw(a); }", CUT_URL)
            p.wait_for_selector("#scaleNote:not([hidden])", timeout=20000)
            check("coupe l’œuvre (en haut et en bas)" in p.inner_text("#scaleNote"), f"{name}: master — hint: the photo cuts the work at the top and bottom")
            p.evaluate("(u)=>{ state.views.art1.v1.photo=u; const a=state.artworks.art1; a.dimensions='50 x 140 cm'; for(const k in scaleCache) delete scaleCache[k]; scaleRedraw(a); }", OPEN_URL)
            p.wait_for_function("(()=>{const n=document.querySelector('#scaleNote'); return n && !n.hidden && n.textContent.includes('Vérifiez l’ordre des dimensions')})()", timeout=20000)
            check(True, f"{name}: master — hint: proportions differ from the dimensions")
            p.evaluate("(u)=>{ state.views.art1.v1.photo=u; const a=state.artworks.art1; a.dimensions='140 x 140 cm'; for(const k in scaleCache) delete scaleCache[k]; scaleRedraw(a); }", OPEN_URL)
            p.wait_for_function("(()=>{const n=document.querySelector('#scaleNote'); return n && n.hidden})()", timeout=20000)
            check(True, f"{name}: master — no hint when the work is cut out")
            p.evaluate("(()=>{ const a=state.artworks.art1; a.dimensions='130 x 100 cm'; state.views.art1.v1.photo=window.__HD0; for(const k in scaleCache) delete scaleCache[k]; scaleRedraw(a); })()")
            # the work's switch
            p.click("#scaleCut"); p.wait_for_timeout(1500)
            check(DOC("art1").get("scaleView", {}).get("cut") == "off", f"{name}: master — 'Détourage automatique' can be switched off")
            p.click("#scaleCut"); p.wait_for_timeout(1500)
            check("cut" not in DOC("art1").get("scaleView", {}), f"{name}: master — and back on")
            # real flow: an openwork photo as the main photo, rendered in the card
            p.evaluate("(u)=>{ state.views.art1.v1.photo=u; const a=state.artworks.art1; a.dimensions='140 x 140 cm'; for(const k in scaleCache) delete scaleCache[k]; scaleRedraw(a); }", OPEN_URL)
            p.wait_for_function("(()=>{const i=document.querySelector('#scaleOpen img'); return i&&i.complete&&i.naturalWidth===1600})()"); p.wait_for_timeout(300)
            p.screenshot(path="/tmp/ls-scale-cut.png")
            # no white square any more: around the grid the wall is the wall
            px = p.evaluate("""(()=>{ const i=document.querySelector('#scaleOpen img'), c=document.createElement('canvas'); c.width=1600; c.height=1200; const x=c.getContext('2d'); x.drawImage(i,0,0);
              const s={dims:parseDims('140 x 140 cm'),chair:null}; roomDefaults(s,false); s.cut={angle:9*Math.PI/180}; roomApply(s,state.artworks.art1.scaleView); roomFit(s,1600,1200,1,true);
              const a=artRect(s); const d=x.getImageData(Math.round(a.x+a.w*0.02),Math.round(a.y+a.h*0.02),1,1).data; return [d[0],d[1],d[2]]; })()""")
            check(px[1] > px[0] + 10 and px[1] < 120, f"{name}: master — in the card, the photo's white square is gone ({px})")
            p.evaluate("(()=>{ state.artworks.art1.dimensions='130 x 100 cm'; state.views.art1.v1.photo=window.__HD0; })()")
        if name == "mac":
            p.evaluate("(async()=>{ const a=state.artworks.art4; await loadViews(a.id); const im=await roomImg(scaleSrc(a)); roomAllowRetry(); localStorage.setItem('ls-room-busy', roomSig(im,'obj')); for(const k in scaleCache) delete scaleCache[k]; })()")
            open_art("art4"); p.wait_for_selector("#scaleRetry", timeout=20000)
            check(p.locator("#scaleOpen img").count() == 0 and "interrompue" in p.inner_text("#scaleNote"), f"{name}: master — interrupted computation not restarted by itself, « Réessayer » offered")
            p.click("#scaleRetry"); p.wait_for_selector("#scaleOpen img", timeout=30000)
            check(p.evaluate("localStorage.getItem('ls-room-busy')") is None, f"{name}: master — « Réessayer » prepares the view and clears the mark")
        # works that are not hung on a wall / without dimensions
        open_art("art2"); p.wait_for_selector("#scaleNote:not([hidden])", timeout=20000)
        check("fond uni" in p.inner_text("#scaleNote") and p.locator("#scaleOpen img").count() == 0, f"{name}: master — sculpture without a usable photo: no image, the reason is given")
        # sculptures on a plinth beside the chair
        open_art("art4"); p.wait_for_selector("#scaleOpen img", timeout=30000)
        check("sur socle" in p.inner_text("#scaleBox").lower() and p.locator("#scaleCut").count() == 0, f"{name}: master — sculpture: view 'sur socle', no wall cut-out switch")
        g = p.evaluate("""(async()=>{ const a=state.artworks.art4, im=await roomImg(scaleSrc(a)), o=roomObj(im);
            const s={stand:true,dims:standDims(a),obj:o,chair:await roomImg('room-chair.webp')}; roomDefaults(s); roomFit(s,1600,1200,1);
            const gg=standGeom(s), top=roomP(s,s.artX,gg.ph+gg.h,gg.zc)[1], base=roomP(s,s.artX,gg.ph,gg.zc)[1], c=chairRect(s);
            return {h:standDims(a).h, ph:gg.ph, hcm:(base-top)/(s.f/gg.zc), chair:c.h/c.s, inview: top>0 && roomP(s,s.artX+gg.pw/2,0,gg.zf)[0]<1600 && c.x>0,
              white:(()=>{ const x=o.canvas.getContext('2d'); const k=o.bh/744; return x.getImageData(Math.round((405-300+o.pad)*k*0+ (405-300)*(o.bw/619)+o.pad), Math.round((520-80)*(o.bh/744)+o.pad),1,1).data[3]; })() }; })()""")
        check(abs(g["hcm"] - 96.5) < 0.01 and abs(g["chair"] - 80) < 0.01, f"{name}: master — tallest piece at exactly 96.5 cm, chair 80 cm")
        check(12 <= g["ph"] <= 30 and g["inview"], f"{name}: master — low white plinth ({g['ph']:.0f} cm), everything in view")
        check(g["white"] == 255, f"{name}: master — the white figure is kept although the backdrop is white")
        if name == "mac": p.screenshot(path="/tmp/ls-scale-sculpture-card.png")
        p.click("#scaleAdjust"); p.wait_for_selector("#room:not([hidden]) canvas"); p.wait_for_function("R.W && R.obj && R.chair")
        a0 = p.evaluate("R.artX"); hb = p.evaluate("standHit()"); box = p.locator("#rCv").bounding_box()
        x0, y0 = box["x"] + hb["x"] + hb["w"] / 2, box["y"] + hb["y"] + hb["h"] * 0.7
        p.mouse.move(x0, y0); p.mouse.down(); p.mouse.move(x0 - 40, y0 - 30, steps=5); p.mouse.up()
        check(p.evaluate("R.artX") < a0, f"{name}: master — sculptures and plinth slide left/right in the editor")
        if name == "iphone": p.screenshot(path="/tmp/ls-scale-sculpture-editor-iphone.png")
        p.click("#rSave"); p.wait_for_timeout(1500)
        check(abs(DOC("art4").get("scaleView", {}).get("artX", 0) - p.evaluate("state.artworks.art4.scaleView.artX")) < 1e-6, f"{name}: master — position saved")
        p.click("#scaleOpen"); p.wait_for_selector("#scBigImg"); p.wait_for_function("document.querySelector('#scBigImg').naturalWidth===2400")
        if name == "mac": p.screenshot(path="/tmp/ls-scale-sculpture-big.png")
        p.keyboard.press("Escape"); p.wait_for_timeout(150)
        # two plinths: low (default) or 90 cm
        check(p.locator("[data-plinth=low].on").count() == 1, f"{name}: master — low plinth by default")
        p.click("[data-plinth=high]"); p.wait_for_timeout(1500)
        check(DOC("art4").get("scaleView", {}).get("plinth") == "high" and p.locator("[data-plinth=high].on").count() == 1, f"{name}: master — 90 cm plinth chosen and saved")
        hg = p.evaluate("""(async()=>{ const a=state.artworks.art4, im=await roomImg(scaleSrc(a)); const s={stand:true,plinth:a.scaleView.plinth,dims:standDims(a),obj:roomObj(im),chair:await roomImg('room-chair.webp')};
            roomDefaults(s); roomApply(s,a.scaleView); roomFit(s,1600,1200,1); const g=standGeom(s), top=roomP(s,s.artX,g.ph+g.h,g.zc)[1], foot=roomP(s,s.artX,0,g.zf)[1];
            return {ph:g.ph, top, foot, H:s.H}; })()""")
        check(hg["ph"] == 90 and hg["top"] > 0 and hg["foot"] <= hg["H"], f"{name}: master — plinth 90 cm high, piece at 1.865 m, all in view")
        p.wait_for_function("(()=>{const i=document.querySelector('#scaleOpen img'); return i&&i.complete&&i.naturalWidth===1600})()"); p.wait_for_timeout(500)
        if name == "mac":
            p.click("#scaleOpen"); p.wait_for_selector("#scBigImg"); p.wait_for_function("document.querySelector('#scBigImg').naturalWidth===2400"); p.wait_for_timeout(200)
            p.screenshot(path="/tmp/ls-scale-sculpture-high.png"); p.keyboard.press("Escape"); p.wait_for_timeout(150)
        check(p.evaluate("canHighPlinth({category:'sculpture',dimensions:'150 x 60 x 50 cm'})") is False and p.evaluate("canHighPlinth({category:'sculpture',dimensions:'Kaikai: 96.5 x 55.3 x 40 cm'})") is True, f"{name}: master — no 90 cm plinth for a piece over 1.20 m")
        tall = p.evaluate("(()=>{ const s={stand:true,plinth:'high',dims:{h:150,w:60,d:50},obj:null}; return standGeom(s).ph; })()")
        check(tall < 90, f"{name}: master — a 1.50 m piece keeps the low plinth ({tall:.0f} cm)")
        p.click("[data-plinth=low]"); p.wait_for_timeout(1500)
        check("plinth" not in DOC("art4").get("scaleView", {}), f"{name}: master — back to the low plinth")
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
        # volume whose demo photo is not on a plain backdrop: the tile goes away (or shows a real image)
        p.evaluate("openWork('aur-11')"); p.wait_for_selector("#detail:not([hidden]) .dh"); p.wait_for_timeout(2500)
        check(p.locator("#dScTile").count() == 0 or p.evaluate("(()=>{const i=document.querySelector('#dScThumb'); return i&&i.naturalWidth===1600})()"), f"{name}: client — volume: tile only with a usable photo")
        # a sculpture with a packshot: standing on the plinth in the client app too
        p.evaluate("(u)=>{ const w=S.data.works.find(x=>x.id==='aur-04'); S.viewPhotos={}; const v=(S.data.views||[]).filter(v=>v.artwork_id==='aur-04'); v.forEach(x=>S.viewPhotos[x.id]=u); w.thumb=u; openWork('aur-04'); }", PAIR_URL)
        p.wait_for_function("(()=>{const i=document.querySelector('#dScThumb'); return i&&i.complete&&i.naturalWidth===1600})()", timeout=30000)
        check(True, f"{name}: client — sculpture on its plinth among the views")
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
