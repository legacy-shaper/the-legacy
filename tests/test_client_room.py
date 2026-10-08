#!/usr/bin/env python3
""""View at scale" in the client app: button only for wall works, exact scale, dragging, wall colours, saved image.
   Run: python3 tests/test_client_room.py   (screenshots in /tmp/ls-room-*.png)"""
import json, os, sys, threading, http.server, functools, re
from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(R, "client")
MOCK = open(os.path.join(R, "tests", "client_mock.js"), encoding="utf-8").read()
demo = json.load(open(os.path.join(R, "tests", "demo.json"), encoding="utf-8"))
CID = demo["coll"]["id"]
for w in demo["works"]:
    if w["id"] == "aur-10": w["dimensions"] = "200 x 360 cm"                       # a very large canvas
    if w["id"] == "aur-07": w["dimensions"] = "47 1/4 x 35 3/8 in."                 # given in inches
    if w["id"] == "aur-04": w["category"] = "sculpture"
SEED = {"users": [dict(id="u1", email="client@example.com", role="client")],
        "members": [dict(user_id="u1", collection_id=CID)],
        "tables": {"profiles": [dict(id="u1", role="client")], "collections": [demo["coll"]], "artworks": demo["works"],
                   "artwork_views": demo["views"], "expenses": demo["expenses"], "documents": []}, "files": {}}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8767), functools.partial(Quiet, directory=CLIENT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8767/"
ok = 0
def check(cond, label):
    global ok
    if not cond: print("FAIL:", label); srv.shutdown(); sys.exit(1)
    ok += 1; print("ok  ", label)
errors = []
def page(ctx):
    p = ctx.new_page()
    p.add_init_script(f"window.__SEED={json.dumps(SEED)};window.__NET=true;window.LS_POLL_MS=600000;")
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.on("console", lambda m: m.type == "error" and errors.append(m.text))
    return p
def route(ctx):
    ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
    ctx.route("**/jszip.min.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
    ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda r: r.fulfill(status=200, content_type="text/css", body=""))
def login(p):
    p.goto(URL); p.wait_for_selector("#gEmail"); p.fill("#gEmail", "client@example.com"); p.click("#gForm .btn")
    p.wait_for_selector("#gCode"); p.fill("#gCode", "42424242"); p.wait_for_selector("#app:not([hidden])")
    p.wait_for_timeout(700); p.wait_for_selector("#app:not([hidden])")
def open_room(p, wid):
    p.evaluate(f"openWork('{wid}')"); p.wait_for_selector("#detail:not([hidden]) .dh")
    p.click("#dRoom"); p.wait_for_selector("#room:not([hidden]) canvas")
    p.wait_for_function("R.W && R.floor && R.art && R.chair")

with sync_playwright() as pw:
    b = pw.chromium.launch()
    for name, vp, mobile in [("desktop", dict(width=1366, height=860), False), ("iphone", dict(width=390, height=844), True)]:
        ctx = b.new_context(viewport=vp, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile,
                            service_workers="block", accept_downloads=True, locale="fr-FR"); route(ctx)
        p = page(ctx); login(p)
        p.evaluate("openWork('aur-11')"); p.wait_for_selector("#detail:not([hidden]) .dh")
        check(p.locator("#dRoom").count() == 0, f"{name}: no scale view for a volume (78 x 42 x 38 cm)")
        p.evaluate("openWork('aur-04')"); p.wait_for_selector("#detail:not([hidden]) .dh")
        check(p.locator("#dRoom").count() == 0, f"{name}: no scale view for a sculpture")
        open_room(p, "aur-01")
        check("Crimson Threshold" in p.inner_text("#room .rtop") and p.locator("#rReset").inner_text() == "Recentrer", f"{name}: scale view opens, in French")
        check("130 × 100 cm" in p.inner_text("#room .rbar"), f"{name}: dimensions shown")
        r = p.evaluate("(()=>{const a=artRect(),c=chairRect();return {aw:a.w,ah:a.h,s:R.scale,cw:c.w,ch:c.h,cs:c.s,base:R.baseY,H:R.H,W:R.W,ax:a.x,cx:c.x}})()")
        check(abs(r["ah"] / r["s"] - 130) < 0.01 and abs(r["aw"] / r["s"] - 100) < 0.01, f"{name}: the work is drawn at exactly 130 x 100 cm")
        check(abs(r["ch"] / r["cs"] - 80) < 0.01, f"{name}: the chair is 80 cm high at its own depth")
        check(r["ax"] >= 0 and r["ax"] + r["aw"] <= r["W"] and r["cx"] >= 0, f"{name}: work and chair fully in view")
        mid = p.evaluate("(()=>{const a=artRect();return R.baseY-(a.y+a.h/2)})()") / r["s"]
        check(abs(mid - 150) < 0.5, f"{name}: work hung with its centre at 150 cm")
        p.screenshot(path=f"/tmp/ls-room-{name}-1.png")
        # drag the work up and left, the chair right (chair cannot move vertically)
        box = p.locator("#rCv").bounding_box()
        a0 = p.evaluate("({x:R.artX,y:R.artY,c:R.chairX})")
        ax, ay = box["x"] + r["ax"] + r["aw"] / 2, box["y"] + r["base"] - (150 * r["s"])
        p.mouse.move(ax, ay); p.mouse.down(); p.mouse.move(ax - 40, ay - 30, steps=5); p.mouse.up()
        a1 = p.evaluate("({x:R.artX,y:R.artY,c:R.chairX})")
        check(a1["x"] < a0["x"] and a1["y"] > a0["y"] and a1["c"] == a0["c"], f"{name}: the work moves left/right and up/down")
        c = p.evaluate("(()=>{const c=chairRect();return {x:c.x+c.w/2,y:c.y+c.h*0.6,top:c.y}})()")
        p.mouse.move(box["x"] + c["x"], box["y"] + c["y"]); p.mouse.down(); p.mouse.move(box["x"] + c["x"] + 30, box["y"] + c["y"] - 50, steps=5); p.mouse.up()
        a2 = p.evaluate("({x:R.artX,y:R.artY,c:R.chairX,top:chairRect().y})")
        check(a2["c"] > a1["c"] and abs(a2["top"] - c["top"]) < 0.001 and a2["x"] == a1["x"], f"{name}: the chair moves left/right only")
        p.click("[data-wall=green]"); p.wait_for_timeout(100)
        px = p.evaluate("(()=>{const x=$('#rCv').getContext('2d');const d=x.getImageData(Math.round(4*R.dpr),Math.round(R.baseY*R.dpr*0.5),1,1).data;return [d[0],d[1],d[2]]})()")
        check(px[1] > px[0] and px[1] < 110, f"{name}: wall colour changes (Vert Legacy)")
        check(p.evaluate("localStorage.getItem('ls-wall')") == "green", f"{name}: wall colour remembered")
        p.screenshot(path=f"/tmp/ls-room-{name}-2.png")
        p.click("#rReset"); p.wait_for_timeout(50)
        check(p.evaluate("Math.abs(R.artX-%f)<1e-6" % a0["x"]), f"{name}: Recentrer puts everything back")
        p.click("[data-wall=pearl]")
        if not mobile:
            with p.expect_download() as dl: p.click("#rSave")
            f = dl.value; check(f.suggested_filename.endswith("Voir à l’échelle.jpg"), f"{name}: image saved ({f.suggested_filename})")
            path = f.path(); check(os.path.getsize(path) > 50000, f"{name}: saved image has content")
        p.click("#rBack"); p.wait_for_timeout(50)
        check(p.locator("#room").is_hidden() and p.locator("#detail").is_visible(), f"{name}: back returns to the work")
        # large canvas: 200 x 360 cm stays in view and at scale
        open_room(p, "aur-10")
        r = p.evaluate("(()=>{const a=artRect();return {aw:a.w,ah:a.h,s:R.scale,x:a.x,W:R.W,y:a.y,base:R.baseY}})()")
        check(abs(r["aw"] / r["s"] - 360) < 0.01 and r["x"] >= 0 and r["x"] + r["aw"] <= r["W"] and r["y"] >= 0, f"{name}: 200 x 360 cm canvas fits, at scale")
        p.screenshot(path=f"/tmp/ls-room-{name}-3.png"); p.click("#rBack")
        open_room(p, "aur-07")
        r = p.evaluate("(()=>{const a=artRect();return {h:a.h/R.scale,w:a.w/R.scale}})()")
        check(abs(r["h"] - 120.015) < 0.01 and abs(r["w"] - 89.8525) < 0.01, f"{name}: dimensions in inches converted (47 1/4 x 35 3/8 in = 120 x 89.9 cm)")
        p.keyboard.press("Escape"); p.wait_for_timeout(50)
        check(p.locator("#room").is_hidden(), f"{name}: Escape closes the view")
        ctx.close()
    check(not errors, "no script error" + (": " + "; ".join(errors[:3]) if errors else ""))
    b.close()
srv.shutdown()
print(f"\nALL {ok} CHECKS PASSED")
