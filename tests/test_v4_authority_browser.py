"""Real Chromium cross-port exfiltration/replay regression, entirely on owned loopback listeners."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import shutil
import socket
from threading import Thread
import time

import httpx
from playwright.sync_api import sync_playwright
import uvicorn

from uptime.auth import enroll
from uptime.auth_keys import generate_reviewer_key
from uptime.auth_client import ReviewerClient
from uptime.server import create_app


@contextmanager
def running(factory):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        origin = "http://127.0.0.1:" + str(listener.getsockname()[1])
        app = factory(origin)
        server = uvicorn.Server(uvicorn.Config(app, proxy_headers=False, access_log=False,
                                              log_level="critical", log_config=None))
        worker = Thread(target=server.run, kwargs={"sockets":[listener]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic()+10
            while not server.started:
                assert worker.is_alive() and time.monotonic() < deadline
                time.sleep(.02)
            yield origin, app
        finally:
            server.should_exit = True
            worker.join(10)
            assert not worker.is_alive()


@contextmanager
def sibling():
    received = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(dict(self.headers))
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<title>Sibling localhost service</title>")
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1",0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield "http://127.0.0.1:"+str(server.server_port), received
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)


def test_real_browser_sibling_cannot_exfiltrate_or_replay_authority(tmp_path):
    path, credential, subject = tmp_path/"browser.db", generate_reviewer_key(), "browser.reviewer"
    enroll(path, subject, credential)
    with running(lambda origin:create_app(path, approvals_enabled=True, origin=origin)) as (origin, app), sibling() as (evil, captured), sync_playwright() as pw:
        chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        executable = str(chrome) if chrome.is_file() else shutil.which("google-chrome") or pw.chromium.executable_path
        browser = pw.chromium.launch(headless=True, executable_path=executable,
                                     args=["--disable-background-networking", "--disable-sync"])
        try:
            context = browser.new_context(service_workers="block")
            context.route("**/*", lambda route: route.continue_() if
                          route.request.url.startswith((origin+"/", evil+"/")) else route.abort())
            context.route_web_socket("**/*", lambda ws: ws.close())
            context.add_init_script("""(() => {
              const original = crypto.subtle.importKey.bind(crypto.subtle);
              crypto.subtle.importKey = async (...args) => {
                const key = await original(...args);
                window.importedReviewerKey = {extractable:key.extractable, algorithm:key.algorithm.name};
                return key;
              };
            })();""")
            page = context.new_page()
            requests = []
            page.on("request", lambda req: requests.append((req.url, req.headers, req.post_data)))
            page.goto(origin+"/#dashboard")
            page.get_by_label("Account name").fill(subject)
            page.get_by_label("Credential file", exact=True).set_input_files({
                "name":"reviewer.json", "mimeType":"application/json", "buffer":json.dumps(credential).encode()})
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_role("heading", name="Evidence ledger", exact=True).wait_for()
            assert not context.cookies()
            assert page.evaluate("window.importedReviewerKey") == {"extractable":False,"algorithm":"ECDSA"}
            assert credential["d"] not in page.evaluate("JSON.stringify(sessionStorage)")
            assert page.url == origin+"/#dashboard"
            # Positive human control uses the same UI signer and persists the named audit identity.
            case = page.evaluate("window.uptimeAPI('/api/cases/dispute-cure/actions/approve-claim', {})")
            assert case["stage"] == "CLAIM_APPROVED" and subject in str(case["timeline"])
            # Keep a read bearer to model an attacker that obtains more than actual sibling cookies.
            stolen_read = page.evaluate("window.uptimeAuth.session().token")
            page.goto(evil)
            assert captured
            assert all(not any(k.lower() in {"cookie","authorization"} for k in entry) for entry in captured)
            assert page.evaluate("sessionStorage.getItem('uptime-v4-session')") is None
            assert page.evaluate("document.cookie") == ""
            assert page.evaluate("""async origin => {
                try { await fetch(origin+'/api/auth/challenge', {method:'POST',
                  headers:{'Content-Type':'application/json','X-Uptime-Action':'1'},
                  body:JSON.stringify({subject:'browser.reviewer'})}); return 'accessible'; }
                catch { return 'blocked'; }
              }""", origin) == "blocked"
            # Replay the actual captured cookie material natively, spoofing the claimed Origin.
            cookies = next((v for r in captured for k,v in r.items() if k.lower()=="cookie"), "")
            with httpx.Client(base_url=origin) as native:
                headers = {"Origin":origin, "X-Uptime-Action":"1", "Cookie":cookies}
                response = native.post("/api/cases/dispute-partial/actions/approve-claim", json={}, headers=headers)
                assert response.status_code == 401
                headers["Authorization"] = "Bearer "+stolen_read
                response = native.post("/api/cases/dispute-partial/actions/approve-claim", json={}, headers=headers)
                assert response.status_code == 403
                signer = ReviewerClient(native, origin, subject, credential)
                replay = signer.prepare("/api/cases/dispute-partial/actions/approve-claim", {})
                assert native.post("/api/cases/dispute-partial/actions/approve-claim", **replay).status_code == 200
                assert native.post("/api/cases/dispute-partial/actions/approve-claim", **replay).status_code == 403
            assert all(credential["d"] not in url and "/session/" not in url and
                       credential["d"] not in str(headers) and credential["d"] not in (body or "")
                       for url,headers,body in requests)
        finally:
            browser.close()
