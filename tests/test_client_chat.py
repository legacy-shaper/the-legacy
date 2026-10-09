#!/usr/bin/env python3
"""Messages with Legacy Shaper in the client app: opening, sending, the assistant's reply, a question about a work,
   an attached photo, Dylan taking over, unread badge, strict separation between collectors, and the app without the tables yet.
   Run: python3 tests/test_client_chat.py   (screenshots in /tmp/ls-chat-*.png)"""
import json, os, sys, threading, http.server, functools, re
from playwright.sync_api import sync_playwright

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(R, "client")
MOCK = open(os.path.join(R, "tests", "client_mock.js"), encoding="utf-8").read()
demo = json.load(open(os.path.join(R, "tests", "demo.json"), encoding="utf-8"))
CID = demo["coll"]["id"]; OTHER = "b0000000-0000-4000-8000-0000000000bb"
def seed(with_chat=True):
    t = {"profiles": [dict(id="u1", role="client"), dict(id="u2", role="client")],
         "collections": [demo["coll"], dict(id=OTHER, slug="other", name="Collection B", subtitle=None, display_currency="USD", cover_artwork_id=None)],
         "artworks": demo["works"], "artwork_views": demo["views"], "expenses": demo["expenses"], "documents": []}
    if with_chat: t.update(support_threads=[], support_messages=[])
    return {"users": [dict(id="u1", email="client@example.com", role="client"), dict(id="u2", email="other@example.com", role="client")],
            "members": [dict(user_id="u1", collection_id=CID), dict(user_id="u2", collection_id=OTHER)], "tables": t, "files": {}}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8768), functools.partial(Quiet, directory=CLIENT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8768/"
ok = 0
def check(cond, label):
    global ok
    if not cond: print("FAIL:", label); srv.shutdown(); sys.exit(1)
    ok += 1; print("ok  ", label)
errors = []
def page(ctx, sd):
    p = ctx.new_page()
    p.add_init_script(f"window.__SEED={json.dumps(sd)};window.__NET=true;window.LS_POLL_MS=600000;window.LS_CHAT_POLL_MS=400;Object.defineProperty(Navigator.prototype,'onLine',{{configurable:true,get:()=>window.__NET!==false}});")
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.on("console", lambda m: m.type == "error" and errors.append(m.text))
    return p
def route(ctx):
    ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
    ctx.route("**/jszip.min.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
    ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda r: r.fulfill(status=200, content_type="text/css", body=""))
def login(p, email):
    p.goto(URL); p.wait_for_selector("#gEmail"); p.fill("#gEmail", email); p.click("#gForm .btn")
    p.wait_for_selector("#gCode"); p.fill("#gCode", "42424242"); p.wait_for_selector("#app:not([hidden])")
    p.wait_for_timeout(700); p.wait_for_selector("#app:not([hidden])")

with sync_playwright() as pw:
    b = pw.chromium.launch()
    # ---------- before the SQL is run: nothing changes for the collector ----------
    ctx = b.new_context(service_workers="block", locale="fr-FR"); route(ctx)
    p = page(ctx, seed(False)); login(p, "client@example.com"); p.wait_for_timeout(300)
    check(p.locator("#chatFab").is_hidden(), "tables not created yet: no messaging button, app unchanged")
    p.evaluate("openWork('aur-01')"); p.wait_for_selector("#detail:not([hidden]) .dh")
    check(p.locator("#dAsk").count() == 0, "tables not created yet: no question button on the work")
    ctx.close()

    # ---------- with messaging ----------
    ctx = b.new_context(service_workers="block", locale="fr-FR", viewport=dict(width=390, height=844), device_scale_factor=2, is_mobile=True, has_touch=True); route(ctx)
    p = page(ctx, seed(True)); login(p, "client@example.com")
    p.wait_for_selector("#chatFab:not([hidden])")
    check(p.inner_text("#chatFab").strip() == "Nous écrire", "button « Nous écrire » shown to the collector")
    p.click("#chatFab"); p.wait_for_selector("#chat:not([hidden]) #cIn")
    check("Votre message parvient aussitôt" in p.inner_text("#chat") and "À votre écoute" in p.inner_text("#cState"), "messaging opens with a welcome line, in French")
    check(p.evaluate("SEED_T=window.__SEED.tables.support_threads, SEED_T.length===1 && SEED_T[0].user_id==='u1' && SEED_T[0].lang==='fr'"), "conversation created for this collector and collection, in French")
    p.evaluate("window.__aiDelay=900")
    p.fill("#cIn", "Bonjour, je n’arrive pas à télécharger l’image de Blue Field I.")
    p.click("#cSend")
    p.wait_for_selector("#cList .m.me")
    check("télécharger l’image" in p.inner_text("#cList .m.me"), "the collector's message appears at once")
    check(p.locator("#cList .typing").count() == 1, "a discreet « … » shows while the answer is written")
    p.wait_for_selector("#cList .m.them", timeout=5000)
    check("nous nous en occupons" in p.inner_text("#cList .m.them") and "LEGACY SHAPER" in p.inner_text("#cList .m.them").upper(), "the assistant's reply arrives, signed Legacy Shaper")
    p.wait_for_timeout(500)
    check(p.locator("#cList .typing").count() == 0, "the « … » goes away")
    inv = p.evaluate("window.__invokes")
    check(any(i["name"] == "support-chat" and i["body"]["action"] == "reply" and i["body"]["threadId"] == "t-u1" for i in inv), "the assistant is asked to reply to this conversation")
    p.screenshot(path="/tmp/ls-chat-iphone-1.png")
    # a forged message is refused by the rules
    forged = p.evaluate("""(async()=>{ const a=await sb.from('support_messages').insert({thread_id:'t-u1',author:'ai',body:'x'});
       const b=await sb.from('support_messages').insert({thread_id:'t-u1',author:'client',body:'x',attachment_path:'u2/x.png'}); return [!!a.error,!!b.error]; })()""")
    check(forged == [True, True], "a collector cannot write as the assistant, nor point to another person's file")
    p.click("#cClose"); p.wait_for_timeout(100)
    check(p.locator("#chat").is_hidden() and p.locator("#chatFab").is_visible(), "closing returns to the collection")

    # ---------- a question about a work, with a photo ----------
    p.evaluate("openWork('aur-04')"); p.wait_for_selector("#detail:not([hidden]) #dAsk")
    p.click("#dAsk"); p.wait_for_selector("#chat:not([hidden]) #cCtx:not([hidden])")
    check("Blue Field I" in p.inner_text("#cCtx"), "« Une question sur cette œuvre » opens with the work attached")
    p.set_input_files("#cFile", files=[dict(name="capture.png", mimeType="image/png", buffer=b"\x89PNG fake")])
    check("capture.png" in p.inner_text("#cCtx"), "photo ready to send")
    p.fill("#cIn", "Le titre devrait être « Blue Field (I) ».")
    p.click("#cSend"); p.wait_for_function("window.__SEED.tables.support_messages.filter(m=>m.author==='client').length===2")
    last = p.evaluate("window.__SEED.tables.support_messages.filter(m=>m.author==='client').pop()")
    check(last["artwork_id"] == "aur-04" and last["attachment_path"].startswith("u1/") and last["attachment_name"] == "capture.png", "message saved with the work and the photo (in the collector's own folder)")
    p.wait_for_selector("#cList img.ai[src^='blob:']", timeout=4000)
    check("À propos de" in p.inner_text("#cList") and p.locator("#cCtx").is_hidden(), "the work is named under the message; the composer is cleared")
    p.wait_for_function("window.__SEED.tables.support_messages.filter(m=>m.author==='ai').length===2", timeout=4000)

    # ---------- Dylan takes over ----------
    p.evaluate("""(()=>{ const th=window.__SEED.tables.support_threads[0]; th.mode='human';
        window.__supportReply(th.id,'Dylan Lessel a rejoint la conversation.','system'); window.__supportReply(th.id,'Bonjour, c’est Dylan, je m’en occupe personnellement.','dylan'); })()""")
    p.wait_for_function("document.querySelector('#cList .m.dylan')", timeout=4000)
    check("Dylan Lessel est avec vous" in p.inner_text("#cState"), "header shows that Dylan is with the collector")
    check("DYLAN LESSEL" in p.inner_text("#cList .m.dylan").upper() and "a rejoint la conversation" in p.inner_text("#cList .sys"), "Dylan's message is signed with his name, the joining notice is shown")
    n_ai = p.evaluate("window.__SEED.tables.support_messages.filter(m=>m.author==='ai').length")
    p.fill("#cIn", "Merci Dylan !"); p.click("#cSend"); p.wait_for_timeout(1500)
    check(p.evaluate("window.__SEED.tables.support_messages.filter(m=>m.author==='ai').length") == n_ai and p.locator("#cList .typing").count() == 0, "while Dylan is there, the assistant does not answer")
    p.screenshot(path="/tmp/ls-chat-iphone-2.png")

    # ---------- the app was in the background (iOS froze it) when Dylan answered ----------
    p.evaluate("""(()=>{ clearInterval(C.poll); C.poll=null; window.__vis='hidden';
        Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>window.__vis});
        window.__supportReply(window.__SEED.tables.support_threads[0].id,'Réponse pendant que l’app dormait.','dylan'); })()""")
    p.wait_for_timeout(600)
    check("pendant que l’app dormait" not in p.inner_text("#cList"), "(setup) app in the background, timers frozen: the reply has not been read yet")
    p.evaluate("window.__vis='visible'; document.dispatchEvent(new Event('visibilitychange'))")
    p.wait_for_function("document.querySelector('#cList').innerText.includes('pendant que l’app dormait')", timeout=1500)
    check(p.evaluate("!!C.poll"), "back in the app with the conversation open: Dylan's reply appears at once, live link and polling restarted")
    p.click("#cClose")

    # ---------- unread badge ----------
    p.evaluate("closeWork(); window.__supportReply(window.__SEED.tables.support_threads[0].id,'Votre titre est corrigé.','dylan')")
    p.evaluate("refresh(true)");     p.wait_for_selector("#chatFab .n:not([hidden])", timeout=3000)
    check(p.inner_text("#chatFab .n") == "1", "a new reply shows a badge on « Nous écrire »")
    p.click("#chatFab"); p.wait_for_timeout(500); p.click("#cClose"); p.wait_for_timeout(100)
    check(p.locator("#chatFab .n").is_hidden(), "badge cleared once the conversation is read")
    ctx.close()

    # ---------- another collector: separate conversation ----------
    ctx = b.new_context(service_workers="block", locale="en-GB"); route(ctx)
    sd = seed(True); sd["tables"]["support_threads"] = [dict(id="t-u1", collection_id=CID, user_id="u1", lang="fr", status="open", mode="ai", unread_client=0, unread_admin=0)]
    sd["tables"]["support_messages"] = [dict(id="x1", thread_id="t-u1", author="client", body="Secret question", created_at="2026-10-08T08:00:00Z")]
    p = page(ctx, sd); login(p, "other@example.com"); p.wait_for_selector("#chatFab:not([hidden])")
    check(p.inner_text("#chatFab").strip() == "Write to us", "English label for an English-speaking collector")
    p.click("#chatFab"); p.wait_for_selector("#cIn"); p.wait_for_timeout(300)
    check("Secret question" not in p.inner_text("#chat"), "another collector never sees someone else's conversation")
    check(p.evaluate("window.__SEED.tables.support_threads.some(t=>t.user_id==='u2' && t.collection_id==='%s')" % OTHER), "their own conversation is opened, on their own collection")
    seen = p.evaluate("(async()=>{ const r=await sb.from('support_messages').select('*').eq('thread_id','t-u1'); return r.data.length; })()")
    check(seen == 0, "reading another conversation directly returns nothing")
    p.evaluate("window.__NET=false")
    p.click("#cClose"); p.click("#chatFab"); p.wait_for_timeout(200)
    check(p.locator("#chat").is_hidden() and "connection is back" in p.inner_text("body"), "offline: a courteous note instead of the messaging")
    ctx.close()
    check(not errors, "no script error" + (": " + "; ".join(errors[:3]) if errors else ""))
    b.close()
srv.shutdown()
print(f"\nALL {ok} CHECKS PASSED")
