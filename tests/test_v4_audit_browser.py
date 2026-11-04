"""Real sibling-origin regression. A TestClient result cannot replace this check."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request


def browser_sibling_origin():
    import uvicorn
    from playwright.sync_api import sync_playwright
    from uptime.server import create_app
    with tempfile.TemporaryDirectory() as tmp:
        secret = secrets.token_urlsafe(32)
        app = create_app(Path(tmp) / "browser.sqlite", session_secret=secret, mode="replay")
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", 0))
            sock.listen(25)
            base = "http://127.0.0.1:" + str(sock.getsockname()[1])
            service = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False, proxy_headers=False))
            runner = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
            runner.start()
            captured = []
            class Neighbor(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def do_GET(self):
                    captured.append(self.headers.get("Cookie", ""))
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"synthetic sibling origin")
            neighbor = ThreadingHTTPServer(("127.0.0.1", 0), Neighbor)
            neighbor_thread = threading.Thread(target=neighbor.serve_forever, daemon=True)
            neighbor_thread.start()
            try:
                for _ in range(200):
                    if service.started:
                        break
                    time.sleep(.025)
                if not service.started:
                    raise RuntimeError("Local server did not start")
                with sync_playwright() as playwright:
                    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
                    options = {"executable_path": str(chrome)} if chrome.exists() else {}
                    browser = playwright.chromium.launch(headless=True, args=["--disable-background-networking"], **options)
                    try:
                        context = browser.new_context()
                        context.route("**/*", lambda route: route.continue_() if route.request.url.startswith("http://127.0.0.1:") else route.abort())
                        page = context.new_page()
                        page.goto(base + "/session/" + secret)
                        page.wait_for_selector('h1:has-text("Contract ledger")')
                        # A working reviewer control prevents auth removal from passing the negative test.
                        page.locator("tr").filter(has=page.get_by_text("dispute-partial", exact=True)).get_by_role("button").click()
                        with page.expect_response(lambda r: r.request.method == "POST" and "/actions/" in r.url) as posted:
                            page.get_by_role("button", name="Approve simulated claim", exact=True).click()
                        positive = posted.value.status
                        for label in ("Submit to vendor simulator", "Record simulated credit", "Apply part to a simulated bill", "Apply the remaining simulated balance"):
                            if not page.locator("dialog").is_visible():
                                page.locator("tr").filter(has=page.get_by_text("dispute-partial", exact=True)).get_by_role("button").click()
                            with page.expect_response(lambda r: r.request.method == "POST" and "/actions/" in r.url) as changed:
                                page.get_by_role("button", name=label, exact=True).click()
                            if changed.value.status != 200:
                                raise RuntimeError("Positive reconciliation UI control failed")
                        page.locator("#case-content").get_by_text("No actions are available in the current server state.", exact=True).wait_for()
                        rendered = page.locator("#case-content").inner_text()
                        case = context.request.get(base + "/api/cases/dispute-partial").json()
                        rec = case["reconciliation"]
                        joins = {"receipt": case["submissions"][0]["id"] in rendered,
                                 "credit": rec["credit_ids"][0] in rendered,
                                 "bill": rec["bill_ids"][0] in rendered,
                                 "application": rec["application_ids"][0] in rendered}
                        page.goto("http://127.0.0.1:" + str(neighbor.server_port) + "/owned")
                    finally:
                        browser.close()
                if not captured:
                    raise RuntimeError("Sibling origin never received a browser request")
                request = urllib.request.Request(base + "/api/cases/dispute-cure/actions/approve-claim",
                    data=b"{}", headers={"Cookie": captured[-1], "Content-Type": "application/json", "X-Uptime-Action": "1"})
                try:
                    with urllib.request.urlopen(request, timeout=4) as response:
                        replay = response.status
                except urllib.error.HTTPError as exc:
                    replay = exc.code
                observed = {"positive_ui_status": positive, "sibling_request_observed": True,
                            "replay_denied": replay in (401, 403)}
                expected = {"positive_ui_status": 200, "sibling_request_observed": True, "replay_denied": True}
                return [dict(id="W-browser-sibling-origin", observed=observed, expected=expected,
                             matches=observed == expected, category="defect"),
                        dict(id="A-ui-financial-join-ids", observed=joins,
                             expected=dict.fromkeys(joins, True), category="defect")]
            finally:
                neighbor.shutdown()
                neighbor.server_close()
                service.should_exit = True
                runner.join(4)
        finally:
            sock.close()
