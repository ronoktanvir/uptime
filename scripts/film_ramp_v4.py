#!/usr/bin/env python3
"""Film the normal Ramp-first application in a disposable, loopback-only replay."""
from __future__ import annotations

import argparse
import copy
from hashlib import sha256
import os
from unittest.mock import patch
from decimal import Decimal
import json
from pathlib import Path
import secrets
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.film_demo import Director, WIDTH, UI_HEIGHT, encode, serve
from scripts.browser_replay import local_connections_only, allowed_browser_url

# Explicit public designation, never choose a bill because its amount looks useful.
BINDING = ROOT / 'fixtures/ramp/native-cap-binding.json'
PUBLIC_DIGEST = '697b2b662246f6f08672cb23d59ca03cadfa506f117947ff12debd063e258cc1'
EXTRACTIONS = ROOT / 'docs/v4/evidence/public-extractions'
VENDOR = 'calyxquay-film-draft'
DURATIONS = (8, 12, 10, 7, 7, 10, 12, 12, 8, 10, 7, 7, 10)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def money(value):
    require(isinstance(value, dict), 'Required native amount missing')
    amount = Decimal(value['amount'])
    require(amount.is_finite() and amount == Decimal(value['amount_minor']) /
            Decimal(value['minor_unit_conversion_rate']), 'Native money units disagree')
    return amount


def boundaries(workspace, bill, cap, designation):
    require(workspace['source_mode'] == 'REPLAY_OF_RAMP_SANDBOX', 'Historical replay required')
    require(workspace['snapshot_status']['integrity'] == 'CHECKSUM_VERIFIED', 'Capture checksum missing')
    require(bill['provider_id'] == cap['provider_id'] == designation['bill_id'], 'Designated native ID mismatch')
    require(bill['data_provenance']['capture_digest'] == designation['capture_digest'], 'Capture binding mismatch')
    require(cap['evidence']['capture_digest'] == designation['capture_digest'], 'Cap capture mismatch')
    for row in (bill, cap):
        require(row['native_status'] == 'OPEN' and row['native_approval_status'] == 'PENDING', 'Native state changed')
        require(money(row['native_amount']) == Decimal('840') and row['native_amount']['currency'] == 'USD', 'Designated bill amount changed')
        require(row['actual_recovery'] is None and row.get('actual_money_prevented') is None, 'Unsupported recovery claim')
    require(bill['amount'] is None and bill['outcome'] == 'INSUFFICIENT_EVIDENCE', 'Unbound bill acquired entitlement')
    require(Decimal(cap['amount']) == Decimal('40') and Decimal(cap['cap_amount']) == Decimal('800'), 'Constructed cap changed')
    require(cap['publishable'] is False and 'SYNTHETIC_CUSTOMER' in cap['sources'], 'Cap must remain synthetic')
    resources = {r['name']: r for r in workspace['resources']}
    for name in ('bills', 'vendors', 'approvals', 'transactions', 'purchase_orders'):
        require(resources[name]['count'] > 0, 'Required provider context absent: ' + name)
    for name in ('agreements', 'credits'):
        require(resources[name]['status'] == 'EMPTY' and resources[name]['count'] == 0, 'Missing-evidence narration no longer matches capture')


def public_intake():
    """Only accepted public bytes; never load a private overlay or evaluation oracle."""
    from uptime.vendor_model import staged_extraction
    from uptime.vendor_terms import Document
    scope = json.loads((ROOT/'prospective/public-scope.json').read_text())
    text = (ROOT/'prospective/public/calyxquay-beacon-cache-sla.txt').read_text()
    require(sha256(text.encode()).hexdigest() == scope['approved_utf8_sha256'] == PUBLIC_DIGEST,
            'Approved public source binding changed')
    require((EXTRACTIONS/(PUBLIC_DIGEST+'.json')).is_file(), 'Accepted public extraction missing')
    document = dict(name='CalyxQuay synthetic public agreement',
                    uri='urn:synthetic:public:calyxquay:2031-04', classification='synthetic_public', text=text)
    manifest, extraction = staged_extraction(Document.model_validate(document))
    require(extraction.get('model') == 'claude-opus-5-5' and extraction.get('session') ==
            '609751b5-43c2-4ddf-947d-799f6e5431ec', 'Accepted extraction provenance changed')
    overlay = dict(agreement='Editor authored CalyxQuay demo', public_agreement=manifest['agreement'],
                   account='Editor authored synthetic account', product=manifest['scope']['product'],
                   plan=manifest['scope']['plan'], effective_from=manifest['effective'][0],
                   effective_until=manifest['effective'][1], fee_line_ref='editor-demo-subscription', currency='USD')
    return dict(document=document, overlay=overlay), manifest, extraction


def demo_controls(overlay, manifest):
    """Editorial controls from public schema, not an independent held-out test suite."""
    from uptime.contracts import fingerprint
    scope = {k: overlay[k] for k in ('agreement','account','product','plan')}
    scope['month'] = '2031-04'
    def record(ref, content):
        return dict(scope, ref=ref, verified=True, complete=True, recorded_at='2031-05-02T00:00:00Z',
                    content=content, content_sha256=fingerprint(content))
    facts = dict(scope, fee_line_ref=overlay['fee_line_ref'],
        service_monitor=record('editor-synthetic-status', dict(source='simulated_vendor', unavailable_minutes=60)),
        service_invoice=record('editor-synthetic-invoice', dict(paid=True, currency='USD', lines=[
            dict(ref=overlay['fee_line_ref'], category='subscription', kind='recurring_subscription', amount_cents=10000),
            dict(ref='editor-coaching', category='operator coaching fees', amount_cents=5000)])),
        filing_proof=dict(scope, verified=True, ref='editor-synthetic-receipt', received_at='2031-05-15T00:00:00Z',
            fields={key:'Editor-authored synthetic '+key for key in manifest.get('request_fields', [])}))
    missing = copy.deepcopy(facts)
    del missing['service_monitor']
    late = copy.deepcopy(facts)
    late['filing_proof']['received_at'] = '2031-05-15T00:00:01Z'
    return facts, [dict(name='Editor demo: '+name, facts=value, expected=expected) for name,value,expected in (
        ('60 minutes; 12 percent of USD 100, coaching excluded', facts, dict(outcome='ELIGIBLE', amount='12.00')),
        ('missing status remains unknown', missing, dict(outcome='INSUFFICIENT_EVIDENCE')),
        ('one second late refused', late, dict(outcome='INELIGIBLE')))]


def draft_boundaries(state, extraction):
    require(state['state'] == 'SHADOW' and state['active_version'] is None and state['reviewer'] is None
            and state.get('interpretation_reviewer') is None, 'Draft acquired approval or activation')
    require(state['extraction'] == extraction, 'Draft extraction provenance mismatch')
    require(state['checks'] and all(row['passed'] for row in state['checks']), 'Editorial controls failed')


class RampDirector(Director):
    def __init__(self, page, origin, work):
        super().__init__(page, origin, work)
        self.evidence = []
        self.current = None

    def native(self, record):
        self.view('ramp/' + record['id'])
        self.current = record
        self.page.get_by_text('Native ID: ' + record['provider_id'], exact=False).wait_for()
        link = self.page.locator('.ramp-native-link')
        require(link.count() == (1 if record.get('provider_uri') else 0), 'Provider link provenance mismatch')
        if link.count():
            require(link.get_attribute('href') == record['provider_uri'], 'Provider link changed')

    def expand(self, title):
        summary = self.page.locator('summary').filter(has_text=title)
        summary.click()
        self.focus(summary, 30)

    def capture(self, view, first, second, data=None):
        seconds = DURATIONS[len(self.shots)]
        self.shot(seconds, view, first, second)
        data = data or self.current or {}
        self.evidence.append({'view': view, 'duration_s': seconds,
            'native_id': data.get('provider_id'), 'source_kinds': data.get('sources', []),
            'native_amount': data.get('native_amount'), 'finding_amount': data.get('amount'),
            'ledger': data.get('ledger'), 'stage': data.get('stage')})

    def perform(self):
        designation = json.loads(BINDING.read_text())
        workspace = self.get('/api/ramp/workspace')
        ident = designation['bill_id']
        bill = self.get('/api/ramp/records/ramp-bills-' + ident)
        cap = self.get('/api/ramp/records/rehearsal-cap-' + ident)
        boundaries(workspace, bill, cap, designation)
        self.checked_id = ident
        self.capture_digest = designation['capture_digest']
        rows = workspace['records']
        self.view('ramp')
        self.capture('Ramp worklist', 'An approver starts with captured Ramp sandbox records.',
                     'Historical read-only replay. Incomplete lists cannot establish portfolio totals.', bill)
        self.native(bill)
        self.focus(self.page.get_by_role('heading', name='Native Ramp status'))
        self.page.get_by_text('840', exact=True).first.wait_for()
        self.capture('Designated bill', 'This exact native bill is USD 840, OPEN, with approval PENDING.',
                     'No governing agreement or real credit is present in this capture.')
        approval = [e for e in bill['evidence'] if e.get('label') == 'Native approval observation']
        require(any(e.get('status') == 'PENDING' for e in approval), 'Record-bound approval missing')
        self.expand('Evidence & governing agreements')
        self.capture('Record-bound approval evidence', 'The approval observation carries the capture reference and digest.',
                     'Contract checks need governing rights and service evidence; neither is inferred.')
        require(bill['native_projection'].get('vendor_id') == bill['vendor'], 'Exact payee ID missing')
        self.expand('Compact redacted provider projection')
        self.capture('Captured payee', 'The captured bill identifies its payee by native vendor ID.',
                     'The truncated vendor list may omit that payee; no name or agreement is inferred.')
        transaction = next(r for r in rows if r['provider_object_type'] == 'transactions' and r['native_amount'])
        self.native(self.get('/api/ramp/records/' + transaction['id']))
        money(self.current['native_amount'])
        self.focus(self.page.get_by_role('heading', name='Native Ramp status'))
        self.capture('Captured card transaction', 'Card activity has its own native amount and status.',
                     'This is separate captured spend, not a bill payment or recovered credit.')
        po = next(r for r in rows if r['provider_object_type'] == 'purchase-orders' and r['native_amount'])
        self.native(self.get('/api/ramp/records/' + po['id']))
        money(self.current['native_amount'])
        self.expand('Compact redacted provider projection')
        self.capture('Available purchase order', 'Available PO details provide procurement context, not signed rights.',
                     'This separately observed PO is not asserted to govern the designated bill.')
        self.native(cap)
        self.expand('Deterministic trace')
        self.capture('Constructed cap on the same ID', 'Same native bill: USD 840 minus a constructed USD 800 gross cap is USD 40.',
                     'Synthetic terms include taxes and fees. No saved money or real claim is established.')
        self.page.get_by_role('button', name='Inspect finding plan', exact=True).click()
        self.page.get_by_text('NOT_SENT', exact=True).first.wait_for()
        plan = self.get('/api/ramp/records/' + cap['id'] + '/workflow')
        require(plan['object_id'] == ident and plan['delivery'] == 'NOT_SENT' and plan['status'] == 'SIMULATION_ONLY', 'Workflow boundary changed')
        self.focus(self.page.get_by_role('heading', name='Native informational workflow'), 20)
        self.capture('Informational note plan', 'The native note plan is informational, simulation-only, and NOT SENT.',
                     'Blank Canvas delivery is not demonstrated. No live provider writes occur.')
        case = self.case('dispute-cure')
        self.current = None
        require(Decimal(case['amount']) == Decimal('100'), 'Synthetic claim amount changed')
        self.action('approve-claim')
        denied = self.action('submit-claim')
        require(denied['stage'] == 'NEEDS_EVIDENCE', 'Expected evidence request absent')
        self.capture('Synthetic Twilio dispute', 'Uptime handles deeper disputes in a separate synthetic Twilio replay.',
                     'A USD 100 claim needs evidence; disputed does not mean awarded.', denied)
        self.action('prepare-response')
        self.action('approve-response')
        self.action('advance-cooldown')
        award = self.action('submit-response')
        require(award['ledger']['awarded'] == '100.00' and award['ledger']['applied'] == '0.00', 'Award ledger changed')
        self.focus(self.page.locator('#inspector h3').get_by_text('Awarded', exact=True))
        self.capture('Simulated award', 'The scripted reviewer approves the supplement; the vendor simulator awards USD 100.',
                     'An award alone is neither a recorded credit nor applied cash.', award)
        posted = self.action('record-credit')
        require(posted['stage'] == 'POSTED' and posted['ledger']['applied'] == '0.00', 'Posting boundary changed')
        self.focus(self.page.locator('#inspector h3').get_by_text('Posted', exact=True))
        self.capture('Recorded simulated credit', 'Recording the simulated credit changes its ledger stage.',
                     'Applied remains USD 0. This is not a Ramp credit.', posted)
        applied = self.action('apply-partial')
        require(applied['stage'] == 'PARTIALLY_APPLIED' and applied['ledger']['applied'] == '50.00', 'Application boundary changed')
        self.focus(self.page.get_by_role('heading', name='Decision trace', exact=True))
        self.capture('Partial simulated application', 'Only USD 50 is applied in this synthetic replay.',
                     'Disputed, awarded, recorded, and applied remain separate measures.', applied)
        intake, manifest, extraction = public_intake()
        prefix = '/api/vendors/' + VENDOR
        def post(path, body):
            return self.page.evaluate('([path,body]) => window.uptimeAPI(path,body)', [path, body])
        state = post(prefix+'/candidates', intake)
        require(state['state'] == 'SHADOW', 'Public draft intake rejected')
        facts, tests = demo_controls(intake['overlay'], manifest)
        state = post(prefix+'/tests', dict(revision=state['revision'], tests=tests))
        draft_boundaries(state, extraction)
        preview = post(prefix+'/shadow-preview', dict(revision=state['revision'], facts=facts))
        require(preview['classification'] == 'LOCAL_DRAFT_PREVIEW' and preview['dispatch_authorized'] is False
                and preview['evaluation']['amount'] == '12.00', 'Draft preview boundary changed')
        self.view('vendors')
        self.expand('Rules, overlay, tests and reviewer versions')
        self.page.get_by_text(extraction['session'], exact=False).first.wait_for()
        self.focus(self.page.get_by_role('heading', name=state['vendor'], exact=True), 84)
        self.onboarding = dict(vendor_id=VENDOR, state=state['state'], version=state['version'],
            source_sha256=PUBLIC_DIGEST, extraction=extraction, human_approval='PENDING',
            controls='EDITOR_AUTHORED_SYNTHETIC_NOT_HELD_OUT', preview=preview,
            model_called_during_film=False)
        self.capture('GENERAL onboarding / human approval pending',
                     'CalyxQuay: recorded Opus extraction becomes a new declarative SHADOW draft.',
                     'Editor-authored synthetic controls. Human approval pending; no model call here.',
                     {'sources':state['sources'], 'stage':'SHADOW'})
        require(sum(s.seconds for s in self.shots) == 120, 'Timeline must total 120 seconds')


def record(args):
    from playwright.sync_api import sync_playwright
    from uptime.auth import SCRIPT
    from uptime.auth_keys import rehearsal_key, write_credential
    output = args.output.resolve()
    require(not output.exists() or not any(output.iterdir()), 'Output must be a new or empty directory')
    with tempfile.TemporaryDirectory(prefix='uptime-ramp-film-') as temp:
        work = Path(temp).resolve()
        media = work / 'complete'
        media.mkdir()
        secret = secrets.token_urlsafe(32)
        credential = write_credential(work/'reviewer.json', rehearsal_key(secret), ROOT)
        failures = []
        with patch.dict(os.environ, {'UPTIME_PUBLIC_EXTRACTIONS': str(EXTRACTIONS), 'UPTIME_MODEL_PROPOSITIONS': '1'}), local_connections_only(), serve(work/'replay.sqlite', secret) as origin, sync_playwright() as pw:
            options = {'headless': True, 'args': ['--disable-background-networking', '--disable-sync']}
            if args.browser:
                options['executable_path'] = str(args.browser.resolve())
            browser = pw.chromium.launch(**options)
            try:
                context = browser.new_context(viewport={'width':WIDTH, 'height':UI_HEIGHT}, device_scale_factor=1,
                                              service_workers='block', reduced_motion='reduce')
                def intercept(route):
                    if allowed_browser_url(route.request.url, origin):
                        route.continue_()
                    else:
                        failures.append('nonlocal request')
                        route.abort()
                context.route('**/*', intercept)
                context.route_web_socket('**/*', lambda ws: ws.close())
                page = context.new_page()
                page.on('pageerror', lambda _: failures.append('page error'))
                page.on('response', lambda r: failures.append('HTTP error') if r.status >= 400 else None)
                page.set_default_timeout(15000)
                page.goto(origin + '/#ramp')
                page.get_by_label('Account name').fill(SCRIPT)
                page.get_by_label('Credential file', exact=True).set_input_files(str(credential))
                page.get_by_role('button', name='Sign in', exact=True).click()
                page.get_by_role('heading', name='Ramp worklist', exact=True).wait_for()
                require(not context.cookies(), 'Unexpected ambient cookies')
                director = RampDirector(page, origin, work)
                director.perform()
                require(not failures, 'Browser or network boundary check failed')
            finally:
                browser.close()
        if not args.check:
            encode(director.shots, work, media)
        for shot in director.shots:
            shutil.copy2(shot.image, media/shot.image.name)
        evidence = {'status':'browser_checked' if args.check else 'rendered_and_probed',
                    'duration_s':120, 'checked_native_id':director.checked_id,
                    'capture_digest':director.capture_digest, 'scenes':director.evidence,
                    'onboarding':director.onboarding,
                    'reviewer_origin':'disposable scripted-test-reviewer',
                    'copy_origin':'editorial captions; UI text is literal application output',
                    'network':'loopback only; no provider API calls', 'external_writes':0,
                    'audio':'none; spoken script in docs/v4/DEMO.md'}
        (media/'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
        output.mkdir(parents=True, exist_ok=True)
        for item in media.iterdir():
            shutil.copy2(item, output/item.name)
        print(json.dumps(evidence))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New/empty artifact directory')
    parser.add_argument('--browser', type=Path, help='Optional Chromium/Chrome executable; default Playwright Chromium')
    parser.add_argument('--check', action='store_true', help='Run actual browser and data checks; save screenshots/JSON without encoding')
    args = parser.parse_args()
    try:
        record(args)
    except Exception as error:
        # Never print Playwright exceptions, request details, credentials or raw API payloads.
        print('CAPTURE_BLOCKED: ' + type(error).__name__ + '; no completed capture published.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
