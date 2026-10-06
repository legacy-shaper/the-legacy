#!/usr/bin/env python3
"""Client app with its real service worker: after one visit online, the app opens with no network at all
   (reload, then a cold start as when the home-screen app is reopened in airplane mode).
   Run: PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS=1 python3 tests/test_client_offline.py"""
import os, sys, json, re, time, threading, http.server, functools
os.environ.setdefault("PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS", "1")
from playwright.sync_api import sync_playwright
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(R, "tests", "test_client.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(R, "tests", "test_client.py")}; exec(src.split("class Quiet")[0], ns)
SEED, MOCK = ns["SEED"], ns["MOCK"]
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8799), functools.partial(Q, directory=os.path.join(R, "client")))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://localhost:8799/"
ok = 0
def check(c, label):
    global ok
    if not c: print("FAIL:", label); srv.shutdown(); sys.exit(1)
    ok += 1; print("ok  ", label)
errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(service_workers="allow")
    ctx.route("**/supabase-js@*/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=MOCK))
    ctx.route(re.compile(r"https://(cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com)/.*"), lambda r: r.fulfill(status=200, content_type="text/css", body=""))
    def page():
        p = ctx.new_page(); p.add_init_script(f"window.__SEED={json.dumps(SEED)};window.LS_POLL_MS=600000;")
        p.on("pageerror", lambda e: errors.append(str(e))); return p
    p = page(); p.goto(URL); p.wait_for_selector("#gEmail")
    p.fill("#gEmail", "client@example.com"); p.click("#gForm .btn"); p.wait_for_selector("#gCode"); p.fill("#gCode", "42424242")
    p.wait_for_selector("#app:not([hidden])"); time.sleep(3)
    check(p.evaluate("!!navigator.serviceWorker.controller"), "service worker in control after the first visit")
    imgs = "new Promise(res=>{const q=indexedDB.open('ls-client');q.onsuccess=()=>{const st=q.result.transaction('kv').objectStore('kv');const out=[];st.openCursor().onsuccess=e=>{const c=e.target.result;if(!c){res(out);return}if(String(c.key).startsWith('img:'))out.push(String(c.value).slice(0,5));c.continue()}}})"
    for _ in range(50):
        got = p.evaluate(imgs)
        if len(got) == 15 and all(x == "data:" for x in got): break
        time.sleep(0.2)
    check(len(got) == 15 and all(x == "data:" for x in got), f"the 15 photographs themselves are kept on the device ({len(got)})")
    cached = p.evaluate("caches.keys().then(async ks=>{let n=[];for(const k of ks){n=n.concat((await (await caches.open(k)).keys()).map(r=>r.url))}return n})")
    check(any(u.endswith("/index.html") for u in cached) and any("supabase-js" in u for u in cached), "page and libraries kept on the device")
    ctx.set_offline(True)
    p.reload(); p.wait_for_selector("#app:not([hidden])", timeout=8000)
    check("Offline" in p.inner_text("#status"), "no network: reload opens the device copy")
    p.close(); p = page(); p.goto(URL); p.wait_for_selector("#app:not([hidden])", timeout=8000)
    check(p.inner_text("#collName") == "The Aurelian Collection", "no network: cold start opens the collection")
    p.click("[data-t=works]"); p.wait_for_selector("#grid")
    check(p.locator("#grid .card").count() == 12, "no network: all 12 works listed")
    p.click("#grid .card[data-w=aur-05]"); p.wait_for_selector("#dImg"); time.sleep(0.8)
    check(p.evaluate("(()=>{const i=document.getElementById('dImg'); return i && i.complete && i.naturalWidth>200})()"), "no network: the work opens with its photograph")
    tn = p.evaluate("[...document.querySelectorAll('[data-vt]')].map(i=>i.complete&&i.naturalWidth>0)")
    check(len(tn) >= 2 and all(tn), f"no network: every view of the work is shown ({len(tn)})")
    th = p.evaluate("(()=>{document.getElementById('dBack').click(); return [...document.querySelectorAll('#grid .card img')].map(i=>i.complete&&i.naturalWidth>0)})()")
    check(len(th) == 12 and all(th), "no network: all 12 thumbnails shown")
    b.close()
check(not errors, "no script error" + (": " + " | ".join(errors[:3]) if errors else ""))
srv.shutdown(); print(f"\nALL {ok} CHECKS PASSED")
