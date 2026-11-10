"""The contract proposal job card leads with state, model, times and the cited clauses; digests sit in one closed disclosure."""
import json
from pathlib import Path
import re
import socket
import threading
import time

from playwright.sync_api import expect, sync_playwright
import uvicorn

from uptime.auth import enroll
from uptime.auth_keys import generate_reviewer_key
from uptime.server import create_app
from test_vendor_model_jobs_runtime import P
from test_vendor_family_selection_89 import selecting  # noqa: F401 (fixture)
from test_vendor_model_jobs_browser import ADD_AGREEMENT, await_selected_proposal, open_section

CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
HEX64 = re.compile(r'\b[0-9a-f]{64}\b')


def test_job_card_keeps_digests_one_click_away_and_clauses_in_view(selecting, tmp_path):
    from test_vendor_family_selection_89 import PROSE, PROSE_AS_RESOURCE, PROSE_PROPOSAL, VENDOR as AUTO, approve, blocks_text
    db, _, provider, jobs, _ = selecting
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}),
                        'resource-month': blocks_text(PROSE, PROSE_AS_RESOURCE)}
    approve(selecting, PROSE)
    key = generate_reviewer_key()
    enroll(db, P.subject, key, tenant=P.tenant, mode='replay')
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); sock.listen(25)
    origin = 'http://127.0.0.1:' + str(sock.getsockname()[1])
    app = create_app(db, tenant=P.tenant, origin=origin, proposal_jobs=jobs, approvals_enabled=False)
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False))
    runner = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True); runner.start()
    try:
        for _ in range(200):
            if server.started: break
            time.sleep(.01)
        assert server.started
        with sync_playwright() as api:
            browser = api.chromium.launch(headless=True, **({'executable_path': str(CHROME)} if CHROME.exists() else {}))
            context = browser.new_context(viewport={'width': 1440, 'height': 900})
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
            page = context.new_page(); errors = []
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.goto(origin + '/#vendors')
            page.get_by_label('Account name', exact=True).fill(P.subject)
            page.get_by_label('Credential file', exact=True).set_input_files({
                'name': 'scripted-runtime-account.json', 'mimeType': 'application/json', 'buffer': json.dumps(key).encode()})
            page.get_by_role('button', name='Sign in', exact=True).click()
            open_section(page, ADD_AGREEMENT)
            page.get_by_role('button', name='Check generation access', exact=True).wait_for()
            for label, value in [('Proposal vendor identifier', AUTO), ('Public document name', PROSE['name']),
                                 ('Public document URI', PROSE['uri']),
                                 ('Exact public source text (sent exactly as entered)', PROSE['text'])]:
                page.get_by_label(label, exact=True).fill(value)
            page.get_by_label('Public document origin', exact=True).select_option(PROSE['classification'])
            page.get_by_role('button', name='Check generation access', exact=True).click()
            page.get_by_text('Generation is permitted for this exact request.', exact=False).wait_for()
            page.get_by_role('button', name='Generate proposals', exact=True).click()
            await_selected_proposal(page)
            card = page.locator('.v4-job').first
            disclosure = card.locator('details', has=page.locator('summary', has_text='Request details'))
            expect(disclosure).to_have_count(1)
            assert disclosure.evaluate('d => d.open') is False
            # In view: job id, state, model and times, the validation sentence, the document and every quote.
            visible = card.inner_text()
            for text in ('Status', 'SUCCEEDED', 'Model', 'Validated against the exact public source. The proposal is unreviewed and not approved.',
                         PROSE['name'], PROSE['uri']):
                assert text in visible, text
            assert not HEX64.search(visible), HEX64.search(visible)
            assert page.locator('.v4-proposal blockquote').count() == len(PROSE_PROPOSAL)
            for clause in PROSE_PROPOSAL:
                assert clause['quote'] in visible
            # One click shows every digest exactly.
            disclosure.locator('summary').click()
            opened = disclosure.inner_text()
            for name in ('request sha256', 'context sha256', 'source sha256', 'proposal sha256', 'session'):
                assert name in opened, name
            assert len(HEX64.findall(opened)) == 4
            assert errors == []
            browser.close()
    finally:
        server.should_exit = True; runner.join(timeout=5); sock.close()
