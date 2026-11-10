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
        elif path in {"/static/InterVariable.woff2", "/static/SourceSerif4-Regular.ttf.woff2", "/static/JetBrainsMono-Regular.woff2"}:
            route.fulfill(body=(ROOT / "web" / path.rsplit("/", 1)[-1]).read_bytes(), content_type="font/woff2")
        elif path.startswith("/static/") and path.rsplit("/", 1)[-1] in {"auth.js", "ramp_ui.js", "workspace_ui.js", "template_builder_ui.js", "app.js", "style.css", "v4_style.css", "v4_ui.js", "favicon.svg"}:
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
        page.goto("http://127.0.0.1:8765/#recovery")
        expect(page.get_by_role("heading", name="Northwind Cloud", exact=True)).to_be_visible()
        expect(page.get_by_text("$9,600.00", exact=True)).to_be_visible()
        expect(page.get_by_text("$1,000.00", exact=True)).to_be_visible()
        expect(page.get_by_text("$0.00", exact=True)).to_be_visible()
        # Cited clauses sit in a collapsed inspector on each month row; opening it shows the exact reference.
        expect(page.get_by_text("NW-CSA-2026#4", exact=True)).to_be_hidden()
        page.locator("#finance-months").get_by_text("Cited clauses (1)", exact=True).click()
        expect(page.get_by_text("NW-CSA-2026#4", exact=True)).to_be_visible()
        page.get_by_text("Agreement & review record", exact=True).click()
        expect(page.get_by_text("scripted-test-reviewer", exact=True)).to_be_visible()
        assert "SYNTHETIC_CUSTOMER" not in page.locator("body").inner_text()
        assert "replay" not in page.locator("#content").inner_text().lower()
        # Four primary destinations; the other tools stay one click away under More tools.
        for label in ["Overview", "Cases", "Agreements", "Activity"]:
            expect(page.locator("nav.rail-primary").get_by_role("link", name=label, exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Ramp records", exact=True)).to_be_hidden()
        page.get_by_text("More tools", exact=True).click()
        for label in ["Ramp records", "Case ledger", "Integrations"]:
            expect(page.get_by_role("link", name=label, exact=True)).to_be_visible()
        page.set_viewport_size({"width": 1000, "height": 500})
        integrations = page.get_by_role("link", name="Integrations", exact=True)
        integrations.scroll_into_view_if_needed()
        assert integrations.evaluate("e => { const r=e.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; }")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_role("link", name="Ramp records", exact=True).click()
        expect(page.get_by_role("heading", name="Ramp worklist", exact=True)).to_be_visible()
        assert not unexpected
        assert not errors
        browser.close()


def test_workflow_action_uses_real_dom_collection_and_refreshes_server_state():
    """Exercise the actual browser HTMLCollection, which the Node stub models as an array."""
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome" if Path("/Applications/Google Chrome.app").exists() else None)
        page = browser.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content('<main id="workflow"></main>')
        page.add_script_tag(path=str(ROOT / "web/workspace_ui.js"))
        page.evaluate("""async () => {
            window.workflowCalls = [];
            let accepted = false;
            const api = async (path, body) => {
                window.workflowCalls.push({path, body});
                if (body !== undefined) accepted = true;
                return {workflow: {
                    vendor: 'Action verification',
                    claim: {id: 'claim-1', state: accepted ? 'CLAIMED' : 'DRAFT'},
                    ledger: {destination: 'Local ledger', claimed: accepted ? '2400.00' : '0.00'},
                    finance: {stages: [{stage: 'claimed', label: 'Claimed', amount: accepted ? '2400.00' : '0.00',
                                        status: accepted ? 'recorded' : 'not yet'}]},
                    next_actions: accepted ? [] : [{id: 'approve/claim-1', label: 'Approve claim'}]
                }};
            };
            await window.UptimeWorkspace.create({api}).render(document.getElementById('workflow'));
        }""")
        page.get_by_role("button", name="Approve claim", exact=True).click()
        expect(page.get_by_role("button", name="Approve claim", exact=True)).to_have_count(0)
        expect(page.locator(".lifecycle-step", has_text="Claimed")).to_contain_text("$2,400.00")
        expect(page.get_by_text("No actions available in the current state.", exact=True)).to_be_visible()
        assert page.evaluate("window.workflowCalls") == [
            {"path": "/api/workspace/workflow", "body": None},
            {"path": "/api/workspace/workflow/actions/approve%2Fclaim-1", "body": {}},
            {"path": "/api/workspace/workflow", "body": None},
        ]
        assert not errors
        browser.close()


def test_result_quotes_and_decimal_equations_render_as_server_text_without_html_execution():
    quote='Credit clause: each completed 0.1 percentage point earns 10%. <img src=x onerror="window.quoteExecuted=true">'
    calculation='USD 9007199254740993.01 × 20% = USD 1801439850948198.60 after final-cent rounding.'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome' if Path('/Applications/Google Chrome.app').exists() else None)
        page=browser.new_page()
        page.set_content('<main id="workflow"></main>')
        page.add_script_tag(path=str(ROOT/'web/workspace_ui.js'))
        page.evaluate('''async ({quote,calculation}) => {
            const workflow={vendor:'Contract review',months:[
                {month:'January',outcome:'ELIGIBLE',amount:'1801439850948198.60',calculation:[calculation],
                 citations:[{label:'Credit clause 6',ref:'urn:agreement:clause:6',quote}]},
                {month:'March',outcome:'INSUFFICIENT_EVIDENCE',amount:null,calculation:[]}],next_actions:[]};
            await UptimeWorkspace.create({api:async()=>({workflow})}).render(document.getElementById('workflow'));
        }''',dict(quote=quote,calculation=calculation))
        expect(page.get_by_text(calculation,exact=True)).to_be_visible()
        page.get_by_text('Cited clauses (1)',exact=True).click()
        page.get_by_text('Read clause',exact=True).click()
        expect(page.locator('blockquote')).to_have_text(quote)
        expect(page.locator('blockquote')).to_be_visible()
        assert page.locator('#workflow img').count()==0
        assert page.evaluate('window.quoteExecuted === undefined')
        expect(page.locator('tbody tr').nth(1).locator('td').nth(2)).to_have_text('Not determined')
        browser.close()
