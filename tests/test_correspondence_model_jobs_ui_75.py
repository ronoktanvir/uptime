"""Workstream 75 browser behavior with a fake signed client. Synthetic interaction only;
no claim of actual human review accuracy or of any provider behavior."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
AWARD = 'A service credit of USD 17.20 is now on our approved list; USD 44.93 remains declined.'
MESSAGE = 'Permission required: an operator must approve this exact request before it can be sent.'


def context_for(text):
    return dict(digest='0' * 64, text=text, text_sha256='1' * 64, event_digest='2' * 64, contract_version='3' * 64,
                contract_source_sha256='4' * 64, scope=dict(month='2028-04', vendor='Public test vendor', service='Test service',
                                                            region='east', account='acct-public'),
                claim='inbox-public-review', requested='62.13', currency='USD', filing_fields=[])


def model_job(reason, can_request, job=None, message=None):
    return dict(kind='correspondence', target='inbox-public-review', context_digest='0' * 64,
                enabled=can_request or reason in {'independent_reading_required', 'existing_request'},
                can_request=can_request, reason=reason, message=message or MESSAGE, request_sha256='9' * 64,
                request_bytes=4321, profile='public-test-profile', job=job)


def job(state):
    terminal = state in {'SUCCEEDED', 'REFUSED', 'CANCELLED', 'UNCERTAIN'}
    return dict(id='job-1', state=state, terminal=terminal, kind='correspondence', target='inbox-public-review',
                context_digest='0' * 64, request_sha256='9' * 64, reason=None,
                result=dict(candidate_id='5' * 64, context_digest='0' * 64, request_sha256='9' * 64, external_actions=[],
                            ledger_unchanged=True) if state == 'SUCCEEDED' else None)


def award_annotation():
    from uptime.correspondence_blocks import hydrate_blocks
    from test_correspondence_blocks_71 import P, annotate
    return hydrate_blocks(AWARD, annotate(AWARD, ('substantive', [P('award', slots=[('award', 'USD 17.20', 0),
                                                                                    ('remainder', 'USD 44.93', 0)])])))


def payload(text, blind, info, candidates=()):
    from uptime.correspondence_blocks import source_blocks
    return dict(context=context_for(text), visible_text=text, blind_entry=blind, candidates=list(candidates),
                model_enabled=False, source_blocks=source_blocks(text), model_job=info)


JS = '''window.calls=[]; const F=FIXTURE; let polls=0, reads=0;
window.fakeApi=async(path,body)=>{
  window.calls.push({path,body:body===undefined?null:body});
  if(path.endsWith('/blind-entry'))return {id:'blind'};
  if(path.endsWith('/model-jobs'))return F.submitted;
  if(path.includes('/model-jobs/')){const s=F.states[Math.min(polls,F.states.length-1)];polls++;return s;}
  if(path.endsWith('/reviews'))return {id:'review'};
  if(path.endsWith('/preview'))return {disposition:'INFORMATIONAL_REVIEW',reported_award:'17.20',prepare_allowed:false};
  if(path.endsWith('/interpretation')){reads++;return reads>1&&F.later?F.later:F.data;}
  throw new Error('Unexpected request');
}; window.UptimeInterpretation.mount(document.getElementById('fixture'),window.fakeApi,'inbox-public-review',{pollMs:20});'''


@contextmanager
def page_for(fixture):
    from playwright.sync_api import sync_playwright, Error
    html = ('<html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/interpretation.css">'
            '<script defer src="/static/interpretation.js"></script><script defer src="/fixture.js"></script></head>'
            '<body><main id="fixture"></main></body></html>')
    js = JS.replace('FIXTURE', json.dumps(fixture))
    unexpected, errors = [], []

    def serve(route):
        path = urlsplit(route.request.url).path
        if path == '/':
            route.fulfill(body=html, content_type='text/html', headers={'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'none'"})
        elif path == '/fixture.js':
            route.fulfill(body=js, content_type='text/javascript')
        elif path in {'/static/interpretation.js', '/static/interpretation.css'}:
            file = ROOT / 'web' / path.rsplit('/', 1)[-1]
            route.fulfill(body=file.read_text(), content_type='text/javascript' if file.suffix == '.js' else 'text/css')
        else:
            unexpected.append(path); route.abort()
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel='chrome' if Path('/Applications/Google Chrome.app').exists() else None)
        except Error:
            if os.environ.get('UPTIME_REQUIRE_BROWSER') == '1':
                raise
            pytest.skip('Browser unavailable')
        page = browser.new_page(viewport={'width': 1200, 'height': 900}); page.route('**/*', serve)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://127.0.0.1:8765/')
        yield page
        assert not errors and not unexpected
        browser.close()


def kinds(page):
    return [row['path'].rsplit('/', 1)[-1] for row in page.evaluate('window.calls')]


def test_permission_required_keeps_request_disabled_and_shows_exact_reference():
    from playwright.sync_api import expect
    from test_correspondence_interpretation import TEXT
    fixture = dict(data=payload(TEXT, None, model_job('independent_reading_required', False,
                                                      message='Save your independent reading before requesting an interpretation.')),
                   later=payload(TEXT, None, model_job('approval_required', False)), submitted=None, states=[])
    with page_for(fixture) as page:
        request = page.get_by_role('button', name='Request interpretation')
        expect(request).to_be_hidden()  # independent reading first
        page.get_by_text('Interpretation request permission', exact=True).click()
        expect(page.get_by_text('Request reference ' + '9' * 64, exact=False)).to_be_visible()
        for label, value in [('Main assertion', 'time_bar'), ('Polarity', 'positive'), ('Status of the assertion', 'asserted'),
                             ('Which claim?', 'current_claim'), ('Additional objection or unresolved meaning?', 'no')]:
            page.get_by_label(label, exact=True).select_option(value)
        page.get_by_role('button', name='Save independent reading').click()
        expect(request).to_be_visible()
        expect(request).to_be_disabled()
        expect(page.locator('#interpretation-request-reason')).to_have_text(MESSAGE)
        assert kinds(page) == ['interpretation', 'blind-entry', 'interpretation']
        assert not any('model' in row['path'] for row in page.evaluate('window.calls'))


def test_complete_operator_request_is_readable_and_permission_refresh_never_submits():
    from playwright.sync_api import expect
    from test_correspondence_interpretation import TEXT, meaning
    pending = model_job('approval_required', False)
    pending['approval_request'] = dict(tenant='bears', subject='reviewer', kind='correspondence',
        target='inbox-public-review', context_sha256='0'*64,
        request={'input': {'source_blocks': [{'id': 'block-1', 'text': TEXT}]}, 'attempt_nonce': 'initial'},
        source_references=[{'reference': 'public-authored-reply', 'sha256': '1'*64}])
    fixture = dict(data=payload(TEXT, meaning(TEXT).model_dump(), pending),
                   later=payload(TEXT, meaning(TEXT).model_dump(), model_job('approved', True)),
                   submitted=None, states=[])
    with page_for(fixture) as page:
        request = page.get_by_role('button', name='Request interpretation')
        expect(request).to_be_disabled()
        page.get_by_text('Interpretation request permission', exact=True).click()
        page.get_by_text('Complete request for operator approval', exact=True).click()
        expect(page.locator('.interpretation-permission pre')).to_contain_text(TEXT)
        expect(page.locator('.interpretation-permission pre')).to_contain_text('source_references')
        page.get_by_role('button', name='Refresh request permission', exact=True).click()
        expect(request).to_be_enabled()
        assert kinds(page) == ['interpretation', 'interpretation']


def test_queued_running_success_shows_exact_source_and_requires_unprefilled_review():
    from playwright.sync_api import expect
    interpretation = award_annotation()
    candidate = dict(id='5' * 64, origin='model', interpretation=interpretation.model_dump(),
                     provenance=dict(request_sha256='9' * 64))
    blind = interpretation.model_dump()
    fixture = dict(data=payload(AWARD, blind, model_job('approved', True)),
                   later=payload(AWARD, blind, model_job('existing_request', False, job('SUCCEEDED')), [candidate]),
                   submitted=job('QUEUED'), states=[job('RUNNING'), job('SUCCEEDED')])
    with page_for(fixture) as page:
        request = page.get_by_role('button', name='Request interpretation')
        expect(request).to_be_enabled()
        request.click()
        expect(page.get_by_text('Request completed', exact=False)).to_be_visible()
        expect(request).to_be_disabled()  # never resubmitted
        expect(page.get_by_role('heading', name='Untrusted suggestions')).to_be_visible()
        page.get_by_text('Requested interpretation — requires your review', exact=True).click()
        expect(page.get_by_text('State: proposed; not reviewed', exact=True)).to_be_visible()
        expect(page.locator('blockquote').first).to_have_text(AWARD)
        start = AWARD.encode().index(b'USD 17.20')
        expect(page.get_by_text(f'award: “USD 17.20” — line 1, bytes {start}–{start + 9} of that line', exact=True)).to_be_visible()
        start = AWARD.encode().index(b'USD 44.93')
        expect(page.get_by_text(f'remainder: “USD 44.93” — line 1, bytes {start}–{start + 9} of that line', exact=True)).to_be_visible()
        page.get_by_role('button', name='Compare this suggestion').click()
        decision = page.get_by_label('Your decision', exact=True)
        expect(decision).to_have_value('')
        expect(page.get_by_role('checkbox').nth(0)).not_to_be_checked()
        expect(page.get_by_role('checkbox').nth(1)).not_to_be_checked()
        decision.select_option('accept')
        page.get_by_label('Explanation of source meaning and any difference', exact=True).fill('Synthetic browser interaction; not an actual human study.')
        page.get_by_role('checkbox').nth(0).check(); page.get_by_role('checkbox').nth(1).check()
        page.get_by_role('button', name='Save meaning review and inspect preview').click()
        expect(page.get_by_role('heading', name='Deterministic preview')).to_be_visible()
        expect(page.get_by_text('Interpreted reported award: USD 17.20; no ledger entry.', exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='Prepare evidence-backed response draft')).to_have_count(0)
        expect(page.get_by_text('State: reviewed by you; preview only', exact=True)).to_be_attached()
        calls = page.evaluate('window.calls')
        assert kinds(page) == ['interpretation', 'model-jobs', 'job-1', 'job-1', 'interpretation', 'reviews', 'preview']
        assert calls[1]['body'] == {'context_digest': '0' * 64}  # no text, classification or grant
        assert calls[5]['body']['candidate_id'] == '5' * 64
        assert not any(row['path'].endswith(('prepare-response', 'submit-response')) or '/actions/' in row['path'] for row in calls)


@pytest.mark.parametrize('state', ['REFUSED', 'UNCERTAIN', 'CANCELLED'])
def test_refused_or_uncertain_job_adds_nothing_and_is_not_retried(state):
    from playwright.sync_api import expect
    from test_correspondence_interpretation import TEXT, meaning
    blind = meaning(TEXT).model_dump()
    fixture = dict(data=payload(TEXT, blind, model_job('approved', True)), later=None,
                   submitted=job('QUEUED'), states=[job(state)])
    with page_for(fixture) as page:
        request = page.get_by_role('button', name='Request interpretation')
        request.click()
        expect(page.get_by_text('No proposal was added' if state == 'REFUSED' else 'not sent again automatically', exact=False).first).to_be_visible()
        expect(request).to_be_disabled()
        page.get_by_role('button', name='Refresh request status').click()
        expect(page.get_by_text('Untrusted suggestions', exact=True)).to_have_count(1)  # only the initially empty list
        assert kinds(page).count('model-jobs') == 1
        assert 'candidates' not in ''.join(kinds(page))
