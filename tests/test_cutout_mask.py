#!/usr/bin/env python3
"""Cut-out mask prepared by Claude (scaleView.cutout, tools/cutout.py) used by the view at scale (tools/room.js).

A white figure on a white backdrop whose outline is invisible on one side: the edge detection alone leaves holes,
with the mask the figure is solid, a real opening (between the legs) still shows the wall, the base is whole.
Also: a mask made for another photo is never applied, a photo on a floor (not a plain backdrop) works with a mask,
and the composition settings never lose the mask. No network; Chromium from /opt/pw-browsers."""
import functools, http.server, os, sys, threading
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = 0
def check(c, msg):
    global ok
    if not c:
        print("FAIL", msg); sys.exit(1)
    ok += 1; print("ok  ", msg)

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8781), functools.partial(Q, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()

PAGE = """<!doctype html><meta charset=utf-8><body><script>window.ROOM_HOST={lang:'fr',base:'/app/'};</script>
<script src="/tools/room.js"></script><script>
// synthetic packshot: 600x700, white backdrop; a white figure (torso + legs) whose LEFT outline is invisible,
// a pink head (well visible), a white base. Same figure drawn as a black/white silhouette = Claude's mask.
function figure(x,body,legs,head,base,floor){
  if(floor){ x.fillStyle='#8a8a86'; x.fillRect(0,520,600,180); }
  x.fillStyle=base; x.beginPath(); x.ellipse(300,600,170,24,0,0,7); x.fill(); x.fillRect(130,600,340,26); x.beginPath(); x.ellipse(300,626,170,24,0,0,7); x.fill();
  x.fillStyle=legs; x.fillRect(240,440,48,160); x.fillRect(312,440,48,160);           // two legs, a real gap between them
  x.fillStyle=body; x.beginPath(); x.ellipse(300,360,95,110,0,0,7); x.fill();         // torso
  x.fillStyle=head; x.beginPath(); x.arc(300,180,90,0,7); x.fill(); }
function make(floor){ const c=document.createElement('canvas'); c.width=600; c.height=700; const x=c.getContext('2d');
  x.fillStyle='#e6e6e4'; x.fillRect(0,0,600,700);
  figure(x,'#e8e8e7','#e7e7e6','#e8a0b8','#ebebea',floor);
  // a faint outline on the right side only (the left side has none, like the real photo)
  x.strokeStyle='#cfcfcd'; x.lineWidth=2; x.beginPath(); x.ellipse(300,360,95,110,0,-1.4,1.4); x.stroke();
  return c.toDataURL('image/jpeg',0.92); }
function maskOf(withBase){ const c=document.createElement('canvas'); c.width=600; c.height=700; const x=c.getContext('2d');
  // the model leaves a pale base out; tools/cutout.py --base adds the base measured on the photo
  x.fillStyle='#000'; x.fillRect(0,0,600,700); figure(x,'#fff','#fff','#fff',withBase?'#fff':'#000',false);
  return c.toDataURL('image/png'); }
window.SRC=make(false); window.FLOOR=make(true); window.MASK=maskOf(true); window.MASK_NOBASE=maskOf(false);
</script>"""
open(os.path.join(ROOT, "tests", "_cutout_page.html"), "w").write(PAGE)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=None)
    pg = b.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8781/tests/_cutout_page.html"); pg.wait_for_function("window.MASK")
    # alpha of the cut-out at photo points: the cut-out's box starts at the piece's top-left (head top, base left)
    A = """async([src,useMask,pts,sig])=>{ roomAllowRetry(); localStorage.clear(); const im=await roomImg(window[src]);
      const cut=useMask?Object.assign({w:600,h:700,mask:window[useMask===2?'MASK_NOBASE':'MASK']},sig||{}):null; const w={scaleView:cut?{cutout:cut}:{}};
      const mk=await roomMaskFor(w,im); const o=roomObj(im,mk); if(!o) return {none:true,mk:!!mk};
      const c=o.canvas, d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
      // photo -> cut-out: the box's left/top are the piece's extreme pixels (W = 600 here, no downscale)
      const al=[]; for(const [px,py] of pts){ const X=px-o.x0+o.pad, Y=py-o.y0+o.pad; al.push(X<0||Y<0||X>=c.width||Y>=c.height?0:d[(Y*c.width+X)*4+3]); }
      return {mk:!!mk, al, bw:o.bw, bh:o.bh}; }"""
    # expose the box origin from roomObjFinish for the test
    has = pg.evaluate("typeof roomObjFinish==='function'")
    check(has, "engine has the finishing step" + (": "+"; ".join(errs) if errs else ""))
    inside = [[300, 300], [230, 360], [215, 330], [260, 420], [255, 520], [330, 520], [300, 180]]     # torso (left side too), legs, head
    gap = [[300, 520]]                                                                                    # between the legs
    base = [[160, 610], [440, 610], [300, 640]]
    r0 = pg.evaluate(A, ["SRC", False, inside + gap + base, None])
    check(r0.get("none") or min(r0["al"][:6]) < 128, f"without the mask the white figure is not solid (alpha {r0.get('al')})")
    r1 = pg.evaluate(A, ["SRC", True, inside + gap + base, None])
    check(r1["mk"] and all(v == 255 for v in r1["al"][:len(inside)]), f"with the mask the figure is solid everywhere ({r1['al'][:len(inside)]})")
    check(r1["al"][len(inside)] == 0, f"the real opening between the legs still shows the wall ({r1['al'][len(inside)]})")
    check(all(v == 255 for v in r1["al"][len(inside) + 1:]), f"the base measured on the photo (cutout.py --base) is whole ({r1['al'][len(inside)+1:]})")
    rn = pg.evaluate(A, ["SRC", 2, inside + base, None])
    check(all(v == 255 for v in rn["al"][:len(inside)]) and all(v == 0 for v in rn["al"][len(inside):]), "a base nobody measured is never invented")
    r2 = pg.evaluate(A, ["SRC", True, inside, {"srcLen": 12345, "srcTail": "zz"}])
    check(not r2.get("mk"), "a mask made for another photo is never applied")
    L = pg.evaluate("window.SRC.length"); T = pg.evaluate("window.SRC.slice(-24)")
    r3 = pg.evaluate(A, ["SRC", True, inside, {"srcLen": L, "srcTail": T}])
    check(r3["mk"] and all(v == 255 for v in r3["al"]), "a mask tied to this exact photo is applied")
    r4 = pg.evaluate(A, ["FLOOR", False, inside, None])
    check(r4.get("none"), "photo on a floor without a mask: no cut-out (as before)")
    r5 = pg.evaluate(A, ["FLOOR", True, inside + gap, None])
    check(r5["mk"] and all(v == 255 for v in r5["al"][:len(inside)]) and r5["al"][len(inside)] == 0, "photo on a floor with a mask: cut out cleanly, the floor left out")
    wrong = pg.evaluate("""async()=>{ const im=await roomImg(window.SRC); return !!(await roomMaskFor({scaleView:{cutout:{w:700,h:600,mask:window.MASK}}},im)); }""")
    check(not wrong, "a mask of other proportions is ignored")
    st = pg.evaluate("""(()=>{ const s={wall:'pearl',artX:1,artY:2,chairX:3,stand:true}; return roomSettings(s); })()""")
    check("cutout" not in st, "composition settings never carry the mask (it stays on the work)")
    check(not errs, "no script error" + (": " + "; ".join(errs[:3]) if errs else ""))
    b.close()
srv.shutdown()
os.remove(os.path.join(ROOT, "tests", "_cutout_page.html"))
print(f"\nALL {ok} CHECKS PASSED")
