"""Signed HTTP and real browser controls with the durable queue and a declared public provider double."""
import json
from pathlib import Path
import socket
import threading
import time

from fastapi.testclient import TestClient
from httpx import HTTPStatusError
from playwright.sync_api import sync_playwright
import pytest
import uvicorn

from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key
from uptime.server import create_app
from test_vendor_model_jobs_runtime import (DOC, OVERLAY, P, VENDOR, approved, finished, runtime)
from test_vendor_family_selection_89 import selecting  # noqa: F401 (fixture)

BASE = '/api/vendors/' + VENDOR
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')


@pytest.fixture
def signed(runtime):
    db, _, _, service, _ = runtime
    key = generate_reviewer_key()
    enroll(db, P.subject, key, tenant=P.tenant, mode='replay')
    app = create_app(db, tenant=P.tenant, proposal_jobs=service, approvals_enabled=False)
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 12345)) as client:
        yield runtime, app, ReviewerClient(client, DEFAULT_ORIGIN, P.subject, key)


def test_signed_job_routes_require_approval_and_cannot_grant_financial_actions(signed):
    runtime, app, reviewer = signed
    db, _, provider, service, adapter = runtime
    body, _ = approved(runtime)
    assert reviewer.client.post(BASE+'/proposal-jobs', json=body.model_dump()).status_code == 403
    for extra in ({'provider': 'browser-provider'}, {'approved': True}, {'receipt': {}}, {'overlay': OVERLAY}):
        assert reviewer.post(BASE+'/proposal-jobs', body.model_dump() | extra).status_code == 422
    assert provider.calls == []
    checked = reviewer.post(BASE+'/proposal-access', body.model_dump())
    assert checked.status_code == 200 and checked.json()['enabled'] is True
    assert provider.calls == []
    response = reviewer.post(BASE+'/proposal-jobs', body.model_dump())
    assert response.status_code == 200, response.text
    completed = finished(service, response.json())
    assert completed['status'] == 'SUCCEEDED'
    job_path = BASE+'/proposal-jobs/'+completed['job_id']
    visible = reviewer.client.get(job_path, headers=reviewer.headers)
    assert visible.status_code == 200 and visible.json()['candidate_available'] is True
    assert len(provider.calls) == 1
    # D05: an operator-chosen extraction profile cannot stage a candidate; Uptime selects the family.
    refused = reviewer.post(job_path+'/candidate', {'overlay': OVERLAY})
    assert refused.status_code == 409 and 'operator-chosen extraction profile' in refused.json()['detail']
    auto = {'document': body.model_dump()['document'], 'profile': 'auto', 'attempt_nonce': 'initial'}
    selection = reviewer.post(BASE+'/proposal-access', auto).json()
    assert selection['outcome'] == 'SELECTED' and selection['selected']['method'] == 'deterministic_document_parser'
    staged = reviewer.post(BASE+'/candidates', {'document': auto['document'], 'overlay': OVERLAY})
    assert staged.status_code == 200, staged.text
    state = staged.json()
    assert state['state'] == 'SHADOW' and state['actions'] == [] and state['reviewer'] is None
    repeated = reviewer.post(BASE+'/candidates', {'document': auto['document'], 'overlay': OVERLAY}).json()
    assert (repeated['revision'], repeated['version']) == (state['revision'], state['version'])
    for path, payload in ((BASE+'/evaluate', {'facts': {}}), (BASE+'/actions/activate', {})):
        with pytest.raises(HTTPStatusError) as denied:
            reviewer.post(path, payload)
        assert denied.value.response.status_code == 403
        assert denied.value.response.request.url.path == '/api/auth/challenge'
    assert len(provider.calls) == 1
    other_key = generate_reviewer_key()
    enroll(db, 'runtime74-other-reviewer', other_key, tenant=P.tenant, mode='replay')
    other = ReviewerClient(reviewer.client, DEFAULT_ORIGIN, 'runtime74-other-reviewer', other_key)
    assert other.client.get(job_path, headers=other.headers).status_code == 404
    assert other.post(job_path+'/candidate', {'overlay': OVERLAY}).status_code == 404


def test_provider_work_does_not_hold_the_application_post_lock(signed, monkeypatch):
    runtime, app, reviewer = signed
    _, _, provider, service, _ = runtime
    body, _ = approved(runtime)
    entered, release = threading.Event(), threading.Event()
    original = type(provider).__call__
    def blocked(self, request):
        entered.set()
        assert release.wait(5), 'Provider double was not released.'
        return original(self, request)
    monkeypatch.setattr(type(provider), '__call__', blocked)
    try:
        response = reviewer.post(BASE+'/proposal-jobs', body.model_dump())
        assert response.status_code == 200 and entered.wait(1)
        assert response.json()['status'] in ('QUEUED', 'RUNNING')
        # This second signed POST completes while the provider remains blocked.
        inspected = reviewer.post(BASE+'/proposal-access', body.model_dump())
        assert inspected.status_code == 200 and inspected.json()['existing_job']['job_id'] == response.json()['job_id']
        assert not release.is_set()
    finally:
        release.set()
    assert finished(service, response.json())['status'] == 'SUCCEEDED'
    assert len(provider.calls) == 1


@pytest.mark.parametrize('entry', ['manual', 'utf8_file', 'offline'])
def test_browser_checks_permission_generates_and_stages_separate_overlay(selecting, tmp_path, entry):
    """D05: the browser never names a family. Uptime selects it; only the selected result can be staged."""
    from test_vendor_family_selection_89 import (CANONICAL, CANONICAL_OVERLAY, PROSE, PROSE_AS_RESOURCE, PROSE_OVERLAY,
                                                 PROSE_PROPOSAL, VENDOR as AUTO, approve, blocks_text)
    db, _, provider, jobs, _ = selecting
    if entry == 'offline':
        document, overlay = CANONICAL, CANONICAL_OVERLAY
    else:
        document = PROSE if entry == 'manual' else PROSE | {'text': PROSE['text'].replace('\n', '\r\n')}
        overlay = PROSE_OVERLAY
        provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}),
                            'resource-month': blocks_text(document, PROSE_AS_RESOURCE)}
        approve(selecting, document)
    key = generate_reviewer_key()
    enroll(db, P.subject, key, tenant=P.tenant, mode='replay')
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); sock.listen(25)
    origin = 'http://127.0.0.1:'+str(sock.getsockname()[1])
    app = create_app(db, tenant=P.tenant, origin=origin, proposal_jobs=jobs, approvals_enabled=False)
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False))
    runner = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    runner.start()
    try:
        for _ in range(200):
            if server.started: break
            time.sleep(.01)
        assert server.started
        with sync_playwright() as browser_api:
            browser = browser_api.chromium.launch(headless=True, **({'executable_path': str(CHROME)} if CHROME.exists() else {}))
            context = browser.new_context(viewport={'width': 390, 'height': 844})
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
            page = context.new_page(); errors = []
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.goto(origin+'/#vendors')
            page.get_by_label('Account name', exact=True).fill(P.subject)
            page.get_by_label('Credential file', exact=True).set_input_files({
                'name': 'scripted-runtime-account.json', 'mimeType': 'application/json', 'buffer': json.dumps(key).encode()})
            page.get_by_role('button', name='Sign in', exact=True).click()
            page.get_by_role('button', name='Check generation access', exact=True).wait_for()
            assert page.get_by_label('Extraction profile', exact=True).count() == 0
            for label, value in [('Proposal vendor identifier', AUTO), ('Public document name', document['name']),
                                 ('Public document URI', document['uri'])]:
                page.get_by_label(label, exact=True).fill(value)
            if entry != 'utf8_file':
                page.get_by_label('Exact public source text (sent exactly as entered)', exact=True).fill(document['text'])
            else:
                page.get_by_label('Import UTF-8 source file (optional)', exact=True).set_input_files({
                    'name': 'public-source.txt', 'mimeType': 'text/plain', 'buffer': document['text'].encode('utf-8')})
                page.get_by_text('Source file loaded.', exact=False).wait_for()
                assert '\r' not in page.get_by_label('Exact public source text (sent exactly as entered)', exact=True).input_value()
            page.get_by_label('Public document origin', exact=True).select_option(document['classification'])
            assert page.get_by_role('button', name='Generate proposals', exact=True).is_disabled()
            page.get_by_role('button', name='Check generation access', exact=True).click()
            if entry == 'offline':
                page.get_by_text('Uptime selected the Monthly availability family.', exact=False).wait_for()
                assert page.get_by_role('button', name='Generate proposals', exact=True).is_disabled()
            else:
                page.get_by_text('Generation is permitted for this exact request.', exact=False).wait_for()
                assert provider.calls == []
                if entry == 'utf8_file':
                    # Editing the normalized display creates a new LF source, not a silent reuse of file bytes.
                    page.get_by_label('Exact public source text (sent exactly as entered)', exact=True).fill(PROSE['text'])
                    page.get_by_text('Text edited. This is a new source request;', exact=False).wait_for()
                    assert page.get_by_role('button', name='Generate proposals', exact=True).is_disabled()
                    page.get_by_role('button', name='Check generation access', exact=True).click()
                    page.get_by_text('Generation is not available for this exact request:', exact=False).wait_for()
                    assert provider.calls == []
                    page.get_by_label('Import UTF-8 source file (optional)', exact=True).set_input_files({
                        'name': 'public-source.txt', 'mimeType': 'text/plain', 'buffer': document['text'].encode('utf-8')})
                    page.get_by_text('Source file loaded.', exact=False).wait_for()
                    page.get_by_role('button', name='Check generation access', exact=True).click()
                    page.get_by_text('Generation is permitted for this exact request.', exact=False).wait_for()
                page.get_by_role('button', name='Generate proposals', exact=True).click()
                page.get_by_text('Every family evaluation has finished.', exact=False).wait_for(timeout=15000)
                assert sorted(provider.calls) == ['monthly-propositions', 'resource-month']
                page.get_by_role('button', name='Refresh proposal status', exact=True).click()
                page.get_by_role('heading', name='Proposed public clauses', exact=True).wait_for(timeout=10000)
                assert page.get_by_text('Why this family was refused', exact=True).count() == 1
                monthly = next(json.loads(r) for r in provider.requests if json.loads(r)['profile'] == 'monthly-propositions')
                assert monthly['input']['text'] == document['text']
                assert page.locator('.v4-proposal blockquote').count() == len(PROSE_PROPOSAL)
            assert not page.get_by_role('button', name='Approve reviewed tests', exact=True).count()
            page.get_by_label('Private customer overlay for this proposal (JSON object; never sent for extraction)', exact=True).fill(json.dumps(overlay))
            page.get_by_role('button', name='Review shadow candidate request', exact=True).click()
            page.get_by_role('button', name='Confirm shadow candidate', exact=True).click()
            page.get_by_role('button', name='Submit independent tests', exact=True).wait_for()
            assert page.get_by_text('SHADOW', exact=True).count() > 0
            assert len(provider.calls) == (0 if entry == 'offline' else 2)
            assert all(overlay['account'].encode() not in request for request in provider.requests)
            assert not page.get_by_role('button', name='Approve reviewed tests', exact=True).count()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert errors == []
            page.screenshot(path=str(tmp_path/'vendor-shadow-mobile.png'), full_page=True)
            browser.close()
    finally:
        server.should_exit = True; runner.join(timeout=5); sock.close()
