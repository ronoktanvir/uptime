"""Browser layout checks with authored local API projections; no provider transport."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def test_configured_workflow_keeps_evidence_money_and_original_navigation_reachable():
    projection = {
        "vendor": "Northwind Cloud", "company": "Finance operations",
        "contract": {"title": "Cloud Services Agreement", "version": "2026-01", "ref": "NW-CSA-2026",
                     "documents": [{"title": "Amendment 1", "ref": "NW-AM1#2", "version": "1", "effective_at": "2026-03-01"}]},
        "reviewer": {"name": "Dana Reyes", "principal": "scripted-test-reviewer", "authority_kind": "SCRIPTED_REVIEWER"},
        "connection": {"destination": "Local ledger", "status": "CONNECTED", "receipt_status": "VERIFIED_LOCAL_READBACK"},
        "claim": {"state": "APPLIED", "id": "claim-jan", "receipt_id": "local-receipt-1"},
        "ledger": {"destination": "Local ledger", "claimed": "2400.00", "awarded": "2400.00", "posted": "2400.00", "applied": "2400.00", "bill": {"id": "NW-MAR-2026", "original_amount": "12000.00", "outstanding_amount": "9600.00"}},
        "months": [{"month": "January 2026", "outcome": "ELIGIBLE", "amount": "2400.00", "citations": [{"label": "Credit schedule §4", "ref": "NW-CSA-2026#4"}]}, {"month": "February 2026", "outcome": "INELIGIBLE", "amount": "0.00"}, {"month": "March 2026", "outcome": "INSUFFICIENT_EVIDENCE", "amount": None}],
        "price_finding": {"amount": "1000.00", "state": "REVIEW_REQUIRED", "citations": [{"label": "Amended cap", "ref": "NW-AM1#2"}]},
        "onboarding": {"vendor": "CalyxQuay", "state": "ACTIVE", "version": "cq-v2", "history": [{"event": "Shadow evaluation passed", "ref": "cq-shadow"}, {"event": "Version approved", "ref": "cq-approval"}, {"event": "Version activated", "ref": "cq-active"}, {"event": "Version rolled back", "ref": "cq-rollback"}]},
        "next_actions": [], "sources": ["SYNTHETIC_CUSTOMER"], "mode": "replay",
    }
    unexpected, errors = [], []

    def serve(route):
        path = urlsplit(route.request.url).path
        if path == "/":
            route.fulfill(body=(ROOT / "web/index.html").read_text(), content_type="text/html")
        elif path.startswith("/static/") and path.rsplit("/", 1)[-1] in {"auth.js", "ramp_ui.js", "workspace_ui.js", "app.js", "style.css", "v4_style.css", "v4_ui.js", "favicon.svg"}:
            file = ROOT / "web" / path.rsplit("/", 1)[-1]
            route.fulfill(body=file.read_text(), content_type="text/javascript" if file.suffix == ".js" else "text/css" if file.suffix == ".css" else "image/svg+xml")
        elif path == "/api/workspace/workflow":
            route.fulfill(json={"workflow": projection})
        elif path == "/api/ramp/workspace":
            route.fulfill(json={"records": [], "resources": []})
        else:
            unexpected.append(path)
            route.abort()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome" if Path("/Applications/Google Chrome.app").exists() else None)
        page = browser.new_page(viewport={"width": 1360, "height": 900})
        page.route("**/*", serve)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.add_init_script("sessionStorage.setItem('uptime-v4-session', " + json.dumps(json.dumps({"token": "browser-projection-token", "subject": "browser-reviewer"})) + ")")
        page.goto("http://127.0.0.1:8765/")
        expect(page.get_by_role("heading", name="Northwind Cloud", exact=True)).to_be_visible()
        expect(page.get_by_text("$9,600.00", exact=True)).to_be_visible()
        expect(page.get_by_text("$1,000.00", exact=True)).to_be_visible()
        expect(page.get_by_text("$0.00", exact=True)).to_be_visible()
        expect(page.get_by_text("NW-CSA-2026#4", exact=True)).to_be_visible()
        page.get_by_text("Agreement & review record", exact=True).click()
        expect(page.get_by_text("scripted-test-reviewer", exact=True)).to_be_visible()
        assert "SYNTHETIC_CUSTOMER" not in page.locator("body").inner_text()
        assert "replay" not in page.locator("#content").inner_text().lower()
        for label in ["Vendor contracts", "Correspondence", "Ramp records"]:
            expect(page.get_by_role("link", name=label, exact=True)).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_role("link", name="Ramp records", exact=True).click()
        expect(page.get_by_role("heading", name="Ramp worklist", exact=True)).to_be_visible()
        assert not unexpected
        assert not errors
        browser.close()
