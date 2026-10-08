#!/usr/bin/env python3
"""Messages from collectors in The Legacy master app: badge, list, conversation, take-over, reply, hand-back, done,
   settings, live arrival, link from a notification, iPhone layout, and nothing visible before the SQL is run.
   Run: python3 tests/test_master_messages.py   (screenshots in /tmp/ls-desk-*.png)"""
import json, os, sys, threading, http.server, functools, re
from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = open(os.path.join(R, "tests", "master_mock.js"), encoding="utf-8").read()
CID = "c1111111-0000-4000-8000-000000000001"; CID2 = "c2222222-0000-4000-8000-000000000002"
def seed(chat=True):
    t = {"collections": [{"id": CID, "slug": "aurelia", "name": "Collection Aurelia"}, {"id": CID2, "slug": "w", "name": "Wahnich Collection"}],
         "collection_members": [], "profiles": [{"id": "u9", "email": "dylan@legacy-shaper.com", "role": "admin"}]}
    if chat:
        t.update(support_threads=[
            dict(id="t1", collection_id=CID, user_id="u1", client_email="client@example.com", lang="fr", status="open", mode="ai", human_last_at=None, category="bug", priority="high",
                 summary="Le client ne peut pas télécharger l’image de Test Work sur iPhone.", last_message_at="2026-10-08T09:10:00Z", last_author="ai", unread_admin=2, unread_client=0),
            dict(id="t2", collection_id=CID2, user_id="u2", client_email="jonathan@example.com", lang="en", status="open", mode="ai", human_last_at=None, category="document", priority="normal",
                 summary="Demande le certificat d’authenticité.", last_message_at="2026-10-08T08:00:00Z", last_author="ai", unread_admin=1, unread_client=0)],
          support_messages=[
            dict(id="m1", thread_id="t1", author="client", body="Bonjour, je n’arrive pas à télécharger l’image.", artwork_id="art1", created_at="2026-10-08T09:00:00Z"),
            dict(id="m2", thread_id="t1", author="client", body="Voici une capture.", attachment_path="u1/cap.png", attachment_name="cap.png", attachment_type="image/png", created_at="2026-10-08T09:05:00Z"),
            dict(id="m3", thread_id="t1", author="ai", body="Merci beaucoup, l’équipe s’en occupe.", created_at="2026-10-08T09:10:00Z"),
            dict(id="m4", thread_id="t2", author="client", body="Could I have the certificate?", created_at="2026-10-08T08:00:00Z")],
          support_settings=[dict(id=1, notify="all", quiet_start=None, quiet_end=None, tz="Europe/Paris", handoff_minutes=10)],
          push_subscriptions=[])
    return {"docs": [
        {"coll": "settings", "id": "company", "data": {"name": "Legacy Shaper Collection - FZCO"}, "updated_at": "2026-10-01T00:00:00Z"},
        {"coll": "artworks", "id": "art1", "data": {"id": "art1", "artist": "Test Artist", "title": "Test Work", "year": "2001"}, "updated_at": "2026-10-01T00:00:00Z"}],
        "tables": t, "files": {}}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8769), functools.partial(Quiet, directory=R))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8769/app/"
ok = 0
def check(c, label):
    global ok
    if not c: print("FAIL:", label); srv.shutdown(); sys.exit(1)
    ok += 1; print("ok  ", label)
errors = []
def start(b, sd, vp=None, mobile=False, hash=""):
    ctx = b.new_context(service_workers="block", viewport=vp or {"width": 1400, "height": 900}, is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
    ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
    ctx.route(re.compile(r"https://(cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com)/.*"), lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
    p = ctx.new_page()
    p.add_init_script(f"window.__MASTER_SEED={json.dumps(sd)};window.LEGACY_MSG_POLL_MS=500;")
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(URL + hash); p.wait_for_selector("#gEmail")
    p.fill("#gEmail", "dylan@legacy-shaper.com"); p.fill("#gPass", "good-pass"); p.click("#gForm button[type=submit]"); p.wait_for_selector("#gCode")
    p.fill("#gCode", "123456"); p.click("#gForm button[type=submit]")
    p.wait_for_function("typeof state!=='undefined' && state.artworks && state.artworks.art1", timeout=15000)
    p.wait_for_timeout(500)
    return ctx, p
DB = "__mockDB().tables"

with sync_playwright() as pw:
    b = pw.chromium.launch()
    # ---------- before the SQL: nothing new appears ----------
    ctx, p = start(b, seed(False))
    check(p.locator("#btnMsg").is_hidden() and p.locator("#homeMsg").is_hidden(), "tables not created yet: no Messages entry, app unchanged")
    ctx.close()

    # ---------- desk ----------
    ctx, p = start(b, seed(True))
    p.wait_for_selector("#btnMsg:not([hidden])")
    check(p.inner_text("#btnMsg .mbadge") == "3", "top bar: Messages with 3 unread")
    check(p.locator("#homeMsg").count() == 1 and p.inner_text("#homeMsg .hbadge") == "3", "home screen: 05 Messages with the same badge")
    p.click("#homeMsg"); p.wait_for_selector("#msgDesk .mrow")
    rows = p.locator("#msgDesk .mrow")
    check(rows.count() == 2 and "client@example.com" in rows.nth(0).inner_text() and "Collection Aurelia" in rows.nth(0).inner_text(), "conversations listed, most recent first, with the collection")
    check("Prioritaire" in rows.nth(0).inner_text() and "Souci technique" in rows.nth(0).inner_text() and "télécharger l’image" in rows.nth(0).inner_text(), "priority, category and the assistant's summary shown in the list")
    p.wait_for_selector("#msgDesk .bub")
    th = p.inner_text("#msgDesk .mthread")
    check("RÉSUMÉ DE L’ASSISTANT" in th.upper() and "Bonjour, je n’arrive pas" in th and "Merci beaucoup, l’équipe" in th, "conversation open: summary, the client's words and the assistant's reply")
    check("Œuvre : Test Artist, Test Work" in th, "the work concerned is named")
    p.wait_for_selector("#msgDesk .bub img[src^='data:image']")
    check(True, "the client's photo is shown")
    p.wait_for_function(f"{DB}.support_threads.find(t=>t.id==='t1').unread_admin===0")
    check(p.inner_text("#btnMsg .mbadge") == "1", "opened conversation marked read: badge goes to 1")
    p.screenshot(path="/tmp/ls-desk-1.png")

    # ---------- take over, reply, hand back ----------
    p.click("#mTake"); p.wait_for_selector("#mBack2")
    t1 = p.evaluate(f"{DB}.support_threads.find(t=>t.id==='t1')")
    check(t1["mode"] == "human" and t1["human_last_at"], "« Prendre le relais »: the assistant steps aside")
    check(p.evaluate(f"{DB}.support_messages.some(m=>m.thread_id==='t1'&&m.author==='system'&&m.body==='Dylan Lessel a rejoint la conversation.')"), "the client sees « Dylan Lessel a rejoint la conversation. » (in French for a French client)")
    check("Vous êtes en ligne" in p.inner_text("#msgDesk .hint2"), "Dylan is told the assistant stays quiet, and when it resumes")
    p.fill("#mIn", "Bonjour, c’est Dylan. Je vous envoie l’image dans un instant."); p.click("#mSend")
    p.wait_for_function(f"{DB}.support_messages.some(m=>m.author==='dylan')")
    check(p.input_value("#mIn") == "" and "c’est Dylan" in p.inner_text("#msgDesk .bub.dylan"), "Dylan's reply is sent and appears under « Vous »")
    check(p.evaluate(f"{DB}.support_messages.filter(m=>m.thread_id==='t1'&&m.author==='system').length") == 1, "no second joining notice while already in the conversation")
    p.click("#mBack2"); p.wait_for_selector("#mTake")
    check(p.evaluate(f"{DB}.support_threads.find(t=>t.id==='t1').mode") == "ai", "« Rendre la main »: the assistant resumes")
    p.click("#mDone"); p.wait_for_timeout(200)
    t1 = p.evaluate(f"{DB}.support_threads.find(t=>t.id==='t1')")
    check(t1["status"] == "resolved" and t1["priority"] == "normal" and "Traité" in p.inner_text("#msgDesk .mrow.on"), "« Marquer comme traité »")

    # ---------- writing directly takes over too (English client) ----------
    p.click("#msgDesk .mrow[data-t=t2]"); p.wait_for_selector("#msgDesk .bub.client")
    p.fill("#mIn", "Of course, I am sending it today."); p.wait_for_timeout(1300)
    check(p.input_value("#mIn") == "Of course, I am sending it today.", "what Dylan is typing survives the live refreshes")
    p.click("#mSend"); 
    p.wait_for_function(f"{DB}.support_messages.some(m=>m.thread_id==='t2'&&m.author==='dylan')")
    check(p.evaluate(f"{DB}.support_messages.some(m=>m.thread_id==='t2'&&m.author==='system'&&m.body==='Dylan Lessel has joined the conversation.')") and p.evaluate(f"{DB}.support_threads.find(t=>t.id==='t2').mode") == "human", "replying without « Prendre le relais » takes over as well (notice in English)")

    # ---------- settings ----------
    p.click("#mSet"); p.wait_for_selector("#sNotify")
    p.select_option("#sNotify", "important"); p.fill("#sQs", "22:00"); p.locator("#sQs").dispatch_event("change"); p.fill("#sQe", "08:00"); p.locator("#sQe").dispatch_event("change")
    p.select_option("#sHand", "15"); p.wait_for_timeout(200)
    st = p.evaluate(f"{DB}.support_settings[0]")
    check(st["notify"] == "important" and st["quiet_start"] == "22:00" and st["quiet_end"] == "08:00" and st["handoff_minutes"] == 15, "settings saved: important only, quiet hours 22:00–08:00, hand-back after 15 min")
    p.click("#pushTest"); p.wait_for_timeout(200)
    check("Aucun appareil activé" in p.inner_text("#pushState"), "test without any device: Dylan is told to activate this device first")
    check(any(i["name"] == "support-chat" and i["body"]["action"] == "test" for i in p.evaluate("window.__invokes")), "the test asks the function to notify Dylan's devices")
    p.click("#mClose"); p.wait_for_timeout(100)

    # ---------- a new message arrives while the app is open ----------
    p.evaluate(f"""(()=>{{ const D=__mockDB(); D.tables.support_messages.push({{id:'m9',thread_id:'t1',author:'client',body:'Une dernière chose',created_at:'2026-10-08T10:00:00Z'}});
        Object.assign(D.tables.support_threads.find(t=>t.id==='t1'),{{last_message_at:'2026-10-08T10:00:00Z',last_author:'client',unread_admin:1,status:'open',summary:'Une dernière chose'}}); localStorage.setItem('mock-db',JSON.stringify(D)); }})()""")
    p.wait_for_selector(".msgToast", timeout=4000)
    check("client@example.com" in p.inner_text(".msgToast") and p.inner_text("#btnMsg .mbadge") == "1", "live: a card announces the new message and the badge updates")
    p.click(".msgToast"); p.wait_for_selector("#msgDesk .bub")
    check("Une dernière chose" in p.inner_text("#msgDesk .mthread"), "touching the card opens that conversation")
    ctx.close()

    # ---------- link from a notification, iPhone layout ----------
    ctx, p = start(b, seed(True), vp={"width": 390, "height": 844}, mobile=True, hash="#messages/t2")
    p.wait_for_selector("#msgDesk.thread-open .bub")
    check("Could I have the certificate?" in p.inner_text("#msgDesk") and p.locator("#msgDesk .mlist").is_hidden(), "opening from a notification lands on that conversation (iPhone: full screen)")
    p.screenshot(path="/tmp/ls-desk-iphone-2.png")
    p.click("#mList"); p.wait_for_timeout(100)
    check(p.locator("#msgDesk .mlist").is_visible() and p.locator("#msgDesk .mthread").is_hidden(), "iPhone: ← returns to the list")
    p.screenshot(path="/tmp/ls-desk-iphone-1.png")
    ctx.close()
    check(not errors, "no script error" + (": " + "; ".join(errors[:3]) if errors else ""))
    b.close()
srv.shutdown()
print(f"\nALL {ok} CHECKS PASSED")
