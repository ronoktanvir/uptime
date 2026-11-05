"""Real local API and browser proof; generated QA identity never leaves the temporary fixture."""
import json
from pathlib import Path
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from uptime.auth import enroll
from uptime.server import create_app
from test_v4_audit_protocol import generate_key
from test_v4_routes_integration import TEXT, SMALL

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')


@pytest.fixture
def portal(tmp_path, monkeypatch):
    monkeypatch.delenv('UPTIME_PUBLIC_EXTRACTIONS', raising=False)
    key = generate_key()
    db = tmp_path / 'companion.sqlite'
    enroll(db, 'companion-reviewer', key)
    viewer = generate_key()
    enroll(db, 'companion-viewer', viewer, role='viewer')
    sock = socket.socket()
    try:
        sock.bind(('127.0.0.1', 0))
    except PermissionError:
        sock.close()
        pytest.skip('Sandbox denies loopback listener; browser layout and signed browser flow remain unverified')
    sock.listen(25)
    origin = 'http://127.0.0.1:' + str(sock.getsockname()[1])
    app = create_app(db, origin=origin, approvals_enabled=True)
    service = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False))
    runner = threading.Thread(target=service.run, kwargs={'sockets': [sock]}, daemon=True)
    runner.start()
    try:
        for _ in range(200):
            if service.started:
                break
            time.sleep(.025)
        assert service.started
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, **({'executable_path': str(CHROME)} if CHROME.exists() else {}))
            context = browser.new_context(viewport={'width': 390, 'height': 844})
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
            page = context.new_page()
            yield page, origin, key, viewer, app
            browser.close()
    finally:
        service.should_exit = True
        runner.join(timeout=5)
        sock.close()


def login(page, origin, key, subject='companion-reviewer'):
    page.goto(origin + '/#vendors')
    page.get_by_label('Account name', exact=True).fill(subject)
    page.get_by_label('Credential file', exact=True).set_input_files({
        'name': 'generated-test-account.json', 'mimeType': 'application/json', 'buffer': json.dumps(key).encode()})
    page.get_by_role('button', name='Sign in', exact=True).click()
    page.get_by_role('button', name='Generate candidate', exact=True).wait_for()


def test_signed_wizard_refresh_routes_and_mobile(portal):
    page, origin, key, _, _ = portal
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    writes = []
    page.on('request', lambda request: writes.append(request.url) if request.method == 'POST' and '/candidates' in request.url else None)
    login(page, origin, key)
    overlay = {k: SMALL[k] for k in ('agreement', 'account', 'product', 'plan', 'fee_line_ref')}
    overlay.update(currency='USD', effective_from='2026-01-01', effective_until='2026-12-31')
    for label, value in [('Vendor identifier','qa-companion'), ('Document name','Synthetic test terms'),
                         ('Public source URI','https://example.invalid/synthetic-terms'),
                         ('Public contract excerpt or full text',TEXT), ('Private customer overlay (JSON object)',json.dumps(overlay))]:
        page.get_by_label(label, exact=True).fill(value)
    page.get_by_label('Public source classification', exact=True).select_option('synthetic_public')
    page.get_by_role('button', name='Generate candidate', exact=True).click()
    page.get_by_role('heading', name='Review exact local request').wait_for()
    assert not writes
    # Changing reviewed data invalidates that review without sending stale bytes.
    page.get_by_label('Document name', exact=True).fill('Revised synthetic test terms')
    page.get_by_role('button', name='Generate candidate', exact=True).click()
    assert not writes
    with page.expect_response(lambda r: '/candidates' in r.url and r.request.method == 'POST') as response:
        page.get_by_role('button', name='Confirm generate candidate', exact=True).click()
    assert response.value.status == 200
    page.get_by_role('button', name='Submit independent tests', exact=True).wait_for()
    assert len(writes) == 1
    assert page.get_by_text('SHADOW', exact=True).count() > 0
    for route, heading in [('advanced','Advanced companion workflows'), ('disputes','Correspondence & disputes'),
                           ('lab','Vendor onboarding'), ('regression','Portfolio comparison'),
                           ('dashboard','Evidence ledger'), ('ramp','Ramp worklist')]:
        page.evaluate('(route) => { location.hash = route; }', route)
        page.get_by_role('heading', name=heading, exact=True).first.wait_for()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), route
    assert not errors
    page.evaluate("location.hash = 'vendors'")
    page.get_by_role('button', name='Generate candidate', exact=True).wait_for()
    page.reload()
    page.get_by_role('button', name='Generate candidate', exact=True).wait_for()
    assert page.get_by_role('button', name='Generate candidate', exact=True).is_disabled()


def test_viewer_and_disabled_gate_are_read_only(portal):
    page, origin, key, viewer, app = portal
    login(page, origin, viewer, 'companion-viewer')
    assert page.get_by_role('button', name='Generate candidate', exact=True).is_disabled()
    page.evaluate('() => window.uptimeAuth.signOut()')
    app.state.auth.approvals_enabled = False
    login(page, origin, key)
    assert page.get_by_role('button', name='Generate candidate', exact=True).is_disabled()


def test_source_audit_preserves_boundaries():
    app = (ROOT / 'web/app.js').read_text()
    ui = (ROOT / 'web/v4_ui.js').read_text()
    assert "script.src = '/static/v4_ui.js'" in app
    assert "css.href = '/static/v4_style.css'" in app
    assert "'lab','regression','advanced','vendors','disputes'" in app
    assert 'UNSUPPORTED_ENTITY' in app and 'READ_ONLY_PROPOSAL' in app
    assert 'innerHTML' not in ui and 'fetch(' not in ui
    assert "'/events'" not in ui
    assert 'Missing verification or quarantine counts are unknown, not zero' in ui


def test_companion_dom_workflows():
    import subprocess
    result = subprocess.run(['node', '--test', 'web/browser-contract.test.cjs', 'web/v4_ui.test.cjs',
                             'tests/helpers/advanced_companion.test.cjs'], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
