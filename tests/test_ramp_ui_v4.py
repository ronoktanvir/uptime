"""Browser contract for Ramp UI; all requests are fulfilled with synthetic local data.

No server, credentials, provider transport, or customer fixtures are used.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_ramp_browser_navigation_and_read_only_plan():
    from playwright.sync_api import sync_playwright, expect, Error

    row = dict(id="opaque/key?#", provider_id="native-test-id", provider_object_type="bills",
               vendor="Browser test vendor", title="Synthetic browser contract", native_status="OPEN",
               native_approval_status="PENDING", sources=["SYNTHETIC_CUSTOMER"], amount="12.01", currency="USD")
    records = [dict(row, id=f"record-{i}") for i in range(60)]
    records[0] = row
    records.append(dict(row, id="transaction-1", provider_object_type="transactions", native_status="CLEARED"))
    workspace = dict(source_mode="TEST_ONLY", as_of="2026-01-01T00:00:00Z",
                     snapshot_status={"freshness": "STALE"}, records=records,
                     resources=[dict(name="bills", status="TRUNCATED", complete=False, count=60, issues=[])],
                     writeback={"comment": "NOT_GRANTED", "actual_writes": []}, credit_sync={})
    requests, unexpected, console_errors = [], [], []
    csp = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

    def serve(route):
        req = route.request
        path = urlsplit(req.url).path
        requests.append((path, req.method, req.is_navigation_request()))
        if path == "/":
            route.fulfill(body=(ROOT / "web/index.html").read_text(), content_type="text/html",
                          headers={"Content-Security-Policy": csp})
        elif path.startswith("/static/") and path.rsplit("/", 1)[-1] in {"auth.js", "ramp_ui.js", "app.js", "style.css", "favicon.svg"}:
            file = ROOT / "web" / path.rsplit("/", 1)[-1]
            content_type = "text/javascript" if file.suffix == ".js" else "text/css" if file.suffix == ".css" else "image/svg+xml"
            route.fulfill(body=file.read_text(), content_type=content_type)
        elif path == "/api/ramp/workspace":
            route.fulfill(json=workspace)
        elif path.endswith("/workflow"):
            route.fulfill(json={"status": "REVIEW_REQUIRED", "delivery": "NOT_SENT", "note": "No current grant"})
        elif path.startswith("/api/ramp/records/"):
            route.fulfill(json={**row, "provider_uri": "https://demo.ramp.com/bills/native-test-id", "trace": ["Synthetic test only"]})
        elif path == "/api/dashboard":
            route.fulfill(json={"workspace": "Synthetic rehearsal", "cases": [], "metrics": [], "audit": []})
        else:
            unexpected.append(path)
            route.abort()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome" if Path("/Applications/Google Chrome.app").exists() else None)
        except Error:
            if os.environ.get("UPTIME_REQUIRE_BROWSER") == "1":
                raise
            pytest.skip("Browser launch unavailable; set UPTIME_REQUIRE_BROWSER=1 at the integration gate")
        page = browser.new_page(viewport={"width": 1360, "height": 900})
        page.route("**/*", serve)
        # A synthetic local session exercises the real auth transport, never a real credential.
        page.add_init_script("sessionStorage.setItem('uptime-v4-session', " + json.dumps(json.dumps({"token": "synthetic-browser-test", "subject": "synthetic-reviewer"})) + ")")
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.goto("http://127.0.0.1:8765/")
        expect(page.get_by_role("heading", name="Ramp worklist", exact=True)).to_be_visible()
        expect(page.locator("tbody tr")).to_have_count(25)
        expect(page.get_by_role("button", name="Sign out · synthetic-reviewer")).to_be_visible()
        page.get_by_label("Record filter").select_option("transactions")
        expect(page.locator("tbody tr")).to_have_count(1)
        page.get_by_label("Record filter").select_option("all")
        page.get_by_role("button", name="Next page").click()
        expect(page.get_by_text("Page 2 of 3", exact=False)).to_be_visible()
        page.get_by_role("button", name="Previous page").click()
        # Returning to the filter must keep it focused, with no fragment or document navigation.
        search = page.get_by_label("Search Ramp records")
        search.fill("Browser test")
        before = page.evaluate("window.scrollY")
        search.press("End")
        search.type(" vendor")
        expect(search).to_be_focused()
        assert page.evaluate("window.scrollY") == before
        page.get_by_role("button", name="Browser test vendor", exact=True).first.click()
        expect(page.get_by_role("heading", name="Synthetic browser contract")).to_be_visible()
        assert page.url.endswith("#ramp/opaque%2Fkey%3F%23")
        page.get_by_role("button", name="Inspect finding plan").click()
        expect(page.get_by_text("NOT_SENT", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Open record in Ramp sandbox")).to_have_attribute("href", "https://demo.ramp.com/bills/native-test-id")
        page.get_by_role("button", name="Back to Ramp worklist").click()
        expect(page.get_by_role("heading", name="Ramp worklist", exact=True)).to_be_visible()
        expect(page.get_by_label("Search Ramp records")).to_have_value("Browser test vendor")
        page.get_by_role("link", name="Case ledger", exact=False).click()
        expect(page.get_by_role("heading", name="Evidence ledger", exact=True)).to_be_visible()
        page.go_back()
        expect(page.get_by_role("heading", name="Ramp worklist", exact=True)).to_be_visible()
        page.goto("http://127.0.0.1:8765/#rehearsal")
        expect(page.get_by_role("heading", name="Evidence ledger", exact=True)).to_be_visible()
        assert not unexpected
        assert not console_errors
        assert all(method == "GET" for _, method, _ in requests)
        assert sum(nav for _, _, nav in requests) == 2, "only initial load and explicit rehearsal load navigate the document"
        assert any(path == "/api/ramp/records/opaque%2Fkey%3F%23/workflow" for path, _, _ in requests)
        browser.close()
