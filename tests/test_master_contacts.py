#!/usr/bin/env python3
"""Tests of contact channels (email / phone pro + perso, primary, newsletters) and profile photo in The Legacy master app.
   Run: python3 tests/test_master_contacts.py"""
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
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8768), functools.partial(Quiet, directory=R))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8768/app/"
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

    D = lambda i: p.evaluate(f"__mockDB().docs.find(x=>x.coll==='contacts'&&x.id==='{i}').data")
    def open_ct(i):
        p.evaluate(f"state.curContact='{i}'; leaveHome('contacts'); document.body.classList.add('alt-detail'); renderAlt();")
        p.wait_for_selector("#k_emailPro")
    # legacy contact (single email/phone) -> shown in the pro slots, primary pro
    open_ct("ct1")
    check(p.input_value("#k_emailPro") == "old@example.com" and p.input_value("#k_emailPerso") == "", "legacy email shown as pro email")
    check(p.input_value("#k_phonePro") == "+33 1 00 00 00 00", "legacy phone shown as pro phone")
    check(p.input_value("#k_primaryEmail") == "pro" and p.input_value("#k_primaryPhone") == "pro", "legacy contact: primary = pro")
    check(p.locator("#k_email").count() == 0 and p.locator("#k_phone").count() == 0, "old single fields gone")

    # Pamela-like case: pro + perso, primary pro
    open_ct("ct2")
    p.fill("#k_emailPro", "pamela@plw.paris"); p.fill("#k_emailPerso", "pamela.wahnich@gmail.com")
    p.wait_for_timeout(1500)
    d = D("ct2")
    check(d["emailPro"] == "pamela@plw.paris" and d["emailPerso"] == "pamela.wahnich@gmail.com", "both emails saved in their own fields")
    check(d["email"] == "pamela@plw.paris" and d["primaryEmail"] == "pro", "primary email = pro, copied to email")
    # switch primary to perso
    p.select_option("#k_primaryEmail", "perso"); p.wait_for_timeout(1500)
    d = D("ct2")
    check(d["primaryEmail"] == "perso" and d["email"] == "pamela.wahnich@gmail.com", "primary switched to perso updates email")
    p.select_option("#k_primaryEmail", "pro"); p.wait_for_timeout(1500)
    check(D("ct2")["email"] == "pamela@plw.paris", "primary back to pro")
    # primary chosen but empty -> falls back on the other
    p.fill("#k_phonePerso", "+33 6 03 16 14 23"); p.select_option("#k_primaryPhone", "pro"); p.wait_for_timeout(1500)
    d = D("ct2")
    check(d["phone"] == "+33 6 03 16 14 23", "empty primary phone falls back on the filled one")
    p.select_option("#k_primaryPhone", "perso"); p.wait_for_timeout(1500)
    check(D("ct2")["primaryPhone"] == "perso" and D("ct2")["phone"] == "+33 6 03 16 14 23", "primary phone perso")
    p.select_option("#k_newsletter", "yes"); p.wait_for_timeout(1500)
    check(D("ct2")["newsletter"] == "yes", "newsletter opt-in saved")
    # search finds the non-primary email; list shows the primary
    p.fill("#q2", "wahnich@gmail")
    check(p.locator("[data-ct=ct2]").count() == 1 and p.locator("[data-ct=ct1]").count() == 0, "search matches the perso email")
    p.fill("#q2", "")
    check("pamela@plw.paris" in p.inner_text("[data-ct=ct2]"), "contact list shows the primary email")
    # re-render keeps values
    open_ct("ct2")
    check(p.input_value("#k_emailPerso") == "pamela.wahnich@gmail.com" and p.input_value("#k_primaryEmail") == "pro", "values kept after reopening")

    # profile photo: small round thumbnail, cropped square, shown in the list, removable
    import base64, struct, zlib
    def png(w, h):
        raw = b"".join(b"\x00" + bytes([200, 120, 60]) * w for _ in range(h))
        ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
        return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b"")
    open_ct("ct2")
    check("Photo" in p.inner_text("#ctPhoto") and p.locator("#ctPhotoDel").count() == 0, "empty avatar invites to add a photo")
    with p.expect_file_chooser() as fc: p.click("#ctPhoto")
    fc.value.set_files(files=[{"name": "face.png", "mimeType": "image/png", "buffer": png(1200, 800)}])
    p.wait_for_selector("#ctPhoto img"); p.wait_for_timeout(1500)
    ph = D("ct2").get("photo", "")
    dims = p.evaluate("u=>new Promise(r=>{const i=new Image();i.onload=()=>r([i.width,i.height]);i.src=u;})", ph)
    check(ph.startswith("data:image/jpeg") and dims == [200, 200], "photo saved as a 200x200 JPEG thumbnail")
    check(len(ph) < 40000, f"thumbnail stays small ({len(ph)} chars)")
    check(p.locator("[data-ct=ct2] img.av-s").count() == 1 and p.locator("[data-ct=ct1] img.av-s").count() == 0, "small avatar shown in the contact list")
    check(p.evaluate("getComputedStyle(document.querySelector('#ctPhoto')).borderRadius") == "50%", "avatar is round")
    check(D("ct2")["email"] == "pamela@plw.paris" and D("ct2")["emailPerso"] == "pamela.wahnich@gmail.com", "photo upload leaves the other fields intact")
    p.click("#ctPhotoDel"); p.wait_for_timeout(1500)
    check(D("ct2")["photo"] == "" and p.locator("#ctPhoto img").count() == 0, "photo removed")
    with p.expect_file_chooser() as fc: p.click("#ctPhoto")
    fc.value.set_files(files=[{"name": "face.png", "mimeType": "image/png", "buffer": png(600, 900)}])
    p.wait_for_selector("#ctPhoto img"); p.wait_for_timeout(1500)
    check(D("ct2")["photo"].startswith("data:image/jpeg"), "photo added again (portrait image)")

    # new contact has empty channels, primary pro
    p.evaluate("const c=newContact(); state.contacts[c.id]=c; state.curContact=c.id; renderAlt();"); p.wait_for_selector("#k_emailPro")
    check(p.input_value("#k_primaryEmail") == "pro" and p.input_value("#k_emailPro") == "", "new contact: empty, primary pro")

    # mobile layout: no horizontal scroll
    p.set_viewport_size({"width": 390, "height": 844}); open_ct("ct2")
    check(p.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "no horizontal scroll on iPhone width")
    check(not errors, "no page errors: " + "; ".join(errors))
    b.close()
srv.shutdown()
print(f"\nAll {ok} checks passed.")
