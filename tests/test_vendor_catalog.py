"""Public synthetic contracts; reviewer fixtures live outside the generator/registry."""
from copy import deepcopy
from decimal import localcontext
from hashlib import sha256
from threading import RLock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from uptime.contracts import Principal, fingerprint
from uptime.storage import initialize, stored_cases
from uptime.vendor_api import make_router
from uptime.vendor_eval import evaluate
from uptime.vendor_model import validate_proposal, staged_extraction, generate
from uptime.vendor_terms import Document, compile_terms

REVIEWER = Principal('demo-tenant', 'scripted-test-reviewer', 'reviewer')
SOURCE = """Synthetic public test contract
Vendor: Example Cloud Services
Agreement: SYN-210B
Effective: 2026-01-01 through 2026-12-31
Availability is measured over each UTC calendar month.
| Product | Plan | Monthly uptime below | Service credit |
| --- | --- | --- | --- |
| Compute Tables | Team | 98% | 50% |
| Compute Tables | Team | 99.75% | 12.5% |
| Message Relay | Premier | 99.9% | 40% |
Claims must be received within 12 calendar days after month end.
Service credits apply to affected monthly fees on a future invoice."""
DOC = {'name': 'Example Synthetic SLA', 'uri': 'urn:synthetic:example-cloud-sla-v1',
       'classification': 'synthetic_public', 'text': SOURCE}
OVERLAY = dict(account='acct-828', agreement='SYN-210B', product='Compute Tables', plan='Team', currency='USD',
               effective_from='2026-04-01', effective_until='2026-11-30', fee_line_ref='inv-june-line-C')
FACTS = dict(account='acct-828', agreement='SYN-210B', product='Compute Tables', plan='Team', month='2026-06',
             eligible_downtime_minutes=109, monitor_source='simulated_vendor', month_complete=True,
             exclusions_removed=True, monthly_fee_cents=10000, fee_line_ref='inv-june-line-C',
             monitor_ref='monitor-378', fee_ref='fee-172', received_at='2026-07-12T23:59:59Z')

# Independent, hand-computed 30-day oracle. 108/43200 = .25% => no credit.
TESTS = [
    {'name': 'one minute beyond threshold', 'facts': FACTS, 'expected': {'outcome': 'ELIGIBLE', 'amount': '12.50'}},
    {'name': 'threshold equality', 'facts': FACTS | {'eligible_downtime_minutes': 108}, 'expected': {'outcome': 'INELIGIBLE'}},
    {'name': 'public status alone', 'facts': FACTS | {'monitor_source': 'public_status'}, 'expected': {'outcome': 'INSUFFICIENT_EVIDENCE'}},
]


@pytest.fixture
def api(tmp_path):
    path = tmp_path / 'catalog.sqlite'
    initialize(path)
    current = [REVIEWER]

    def check(p):
        if p.role != 'reviewer':
            raise HTTPException(403)

    def reviewer():
        check(current[0])
        return current[0]

    def build():
        app = FastAPI()
        app.include_router(make_router(path, lambda: current[0], reviewer, check, RLock()))
        from fastapi.responses import JSONResponse

        @app.exception_handler(ValueError)
        async def invalid(req, exc):
            return JSONResponse({'detail': str(exc)}, status_code=409)

        @app.exception_handler(PermissionError)
        async def denied(req, exc):
            return JSONResponse({'detail': str(exc)}, status_code=403)

        @app.exception_handler(KeyError)
        async def missing(req, exc):
            return JSONResponse({'detail': 'missing'}, status_code=404)

        return TestClient(app)

    return build(), current, build, path


V = '/api/vendors/example-cloud'


def install(c, doc=DOC, overlay=OVERLAY, url=V):
    response = c.post(url + '/candidates', json={'document': doc, 'overlay': overlay})
    assert response.status_code == 200, response.text
    return response.json()


def run_suite(c, state, rows=TESTS, url=V):
    r = c.post(url + '/tests', json={'revision': state['revision'], 'tests': rows})
    assert r.status_code == 200, r.text
    return r.json()


def action_url(state, op, url=V):
    return url + '/actions/' + next(a['id'] for a in state['actions'] if a['operation'] == op)


def transition(c, state, op, url=V):
    r = c.post(action_url(state, op, url), json={})
    assert r.status_code == 200, r.text
    return r.json()


def activate(c):
    state = run_suite(c, install(c))
    return transition(c, transition(c, state, 'approve'), 'activate')


def test_authenticated_intake_to_case_rollback_and_restart(api):
    c, _, restart, path = api
    shadow = install(c)
    assert shadow['state'] == 'SHADOW' and not shadow['reviewer'] and not shadow['actions']
    assert [r['kind'] for r in shadow['audit']][-1].startswith('Shadow only')
    assert shadow['manifest']['document']['sha256'] == sha256(SOURCE.encode()).hexdigest()
    for citation in shadow['manifest']['citations']:
        assert citation['quote'] == SOURCE[citation['start']:citation['end']]
    assert len(shadow['generated_tests']) == 6
    assert c.post(V + '/evaluate', json={'facts': FACTS}).status_code == 409
    tested = run_suite(c, shadow)
    assert all(row['passed'] for row in tested['checks'])
    approved = transition(c, tested, 'approve')
    assert approved['reviewer_kind'] == 'scripted_test' and approved['reviewer'] == REVIEWER.subject
    active = transition(c, approved, 'activate')
    with localcontext() as context:
        context.prec = 2
        res = c.post(V + '/evaluate', json={'facts': FACTS}).json()
    assert res['outcome'] == 'ELIGIBLE' and res['amount'] == '12.50'
    assert res['version'] == active['version'] and res['issuance_status'] == 'FUTURE_INVOICE_CREDIT_UNCONFIRMED'
    assert res['actions'] == [] and 'LIVE_VENDOR_PUBLIC' not in res['sources']
    assert c.post(V + '/evaluate', json={'facts': FACTS}).json() == res
    c = restart()
    assert c.get('/api/vendors').json()['vendors'][0]['active_version'] == active['version']
    assert transition(c, active, 'rollback')['active_version'] is None
    assert c.post(V + '/evaluate', json={'facts': FACTS}).status_code == 409
    assert stored_cases(path, REVIEWER.tenant) == [res]


def test_failing_or_tautological_independent_tests_cannot_approve(api):
    c, _, _, _ = api
    state = install(c)
    bad = deepcopy(TESTS)
    bad[0]['expected']['amount'] = '12.51'
    state = run_suite(c, state, bad)
    assert not state['checks'][0]['passed'] and state['actions'] == []
    state = run_suite(c, state, TESTS[:1])
    assert not state['actions']
    state = run_suite(c, state)
    assert state['actions'][0]['operation'] == 'approve'


def test_source_cycle_quarantine_revoke_and_review(api):
    c, _, _, _ = api
    a = run_suite(c, install(c))
    old_approve = action_url(a, 'approve')
    aa = transition(c, a, 'approve')
    old_activate = action_url(aa, 'activate')
    transition(c, aa, 'activate')
    for corrupt in [DOC | {'text': SOURCE + '\nCash refunds replace all service credits.'},
                    DOC | {'text': ['not document text']}]:
        state = install(c, corrupt)
        assert state['state'] == 'QUARANTINED' and not state['active_version'] and not state['actions']
        assert c.post(V + '/evaluate', json={'facts': FACTS}).status_code == 409
    state = run_suite(c, install(c))
    assert state['version'] == a['version'] and c.post(old_approve, json={}).status_code == 409
    state = transition(c, state, 'approve')
    assert c.post(old_activate, json={}).status_code == 409
    revoked = transition(c, state, 'revoke')
    assert not revoked['active_version'] and revoked['state'] == 'REVOKED'
    again = transition(c, revoked, 'review')
    assert again['state'] == 'SHADOW' and not again['actions'] and again['test_author'] is None


def test_material_source_revision_requires_new_tests_and_blocks_prior_dispatch(api):
    c, _, _, path = api
    first = activate(c)
    result = c.post(V + '/evaluate', json={'facts': FACTS}).json()
    revised = install(c, DOC | {'text': SOURCE.replace('12.5%', '18%')})
    assert revised['version'] != first['version'] and not revised['active_version'] and not revised['previous']
    assert c.post(V + '/evaluate', json={'facts': FACTS}).status_code == 409
    failed = run_suite(c, revised)
    assert not failed['checks'][0]['passed'] and not failed['actions']
    assert stored_cases(path, REVIEWER.tenant) == [result]


def test_principal_tenant_reviewer_and_subject_bound_actions(api):
    c, identity, _, _ = api
    tested = run_suite(c, install(c))
    mine = action_url(tested, 'approve')
    identity[0] = Principal('other-tenant', 'test-other', 'reviewer')
    assert c.get('/api/vendors').json()['vendors'] == [] and c.get(V).status_code == 404
    identity[0] = Principal(REVIEWER.tenant, 'test-viewer', 'viewer')
    assert c.get(V).json()['actions'] == [] and c.post(mine, json={}).status_code == 403
    assert c.post(V + '/candidates', json={}).status_code == 403
    identity[0] = Principal(REVIEWER.tenant, 'test-other-reviewer', 'reviewer')
    assert c.post(mine, json={}).status_code == 409
    identity[0] = REVIEWER
    approved = transition(c, tested, 'approve')
    identity[0] = Principal(REVIEWER.tenant, 'test-other-reviewer', 'reviewer')
    url = action_url(c.get(V).json(), 'activate')
    assert c.post(url, json={}).status_code == 403
    identity[0] = REVIEWER
    transition(c, approved, 'activate')
    assert c.post(V + '/evaluate', json={'facts': FACTS | {'tenant': 'other-tenant'}}).status_code == 403


def test_private_filing_amendment_changes_only_bound_account_scope(api):
    c, _, _, _ = api
    amended = OVERLAY | {'override': {'filing_days': 19, 'quote': 'Claims must be received within 19 calendar days after month end.',
                                      'source_ref': 'private-addendum-section-2'}}
    state = run_suite(c, install(c, overlay=amended))
    transition(c, transition(c, state, 'approve'), 'activate')
    receipt = FACTS | {'received_at': '2026-07-19T23:59:59Z'}
    result = c.post(V + '/evaluate', json={'facts': receipt}).json()
    assert result['outcome'] == 'ELIGIBLE' and result['claim_cutoff_exclusive'].startswith('2026-07-20')
    assert result['clauses'][-1]['label'] == 'private-addendum-section-2'
    assert c.post(V + '/evaluate', json={'facts': receipt | {'account': 'other'}}).json()['outcome'] == 'INSUFFICIENT_EVIDENCE'
    amended['override'] = amended['override'] | {'filing_days': 20}
    assert install(c, overlay=amended)['state'] == 'QUARANTINED'


def test_multiple_arbitrary_catalog_entries_and_prose_products(api):
    c, _, _, _ = api
    install(c)
    document = DOC | {'text': """Vendor: Arbitrary Communications
Agreement: Q2-X
This agreement is effective from 2026-01-01 through 2026-12-31.
The measurement period is a UTC calendar month.
For Bird Feed under the Prime plan, monthly uptime less than 99.87% qualifies for a 6.75% service credit.
For Data Stream on the Max plan, monthly availability below 91% earns a 61% service credit.
Credit requests must be submitted within 9 calendar days following the end of the affected month.
Credits are based on the affected monthly fees and are applied to the next invoice."""}
    overlay = OVERLAY | {'agreement': 'Q2-X', 'product': 'Bird Feed', 'plan': 'Prime'}
    state = install(c, document, overlay, '/api/vendors/arbitrary')
    assert state['state'] == 'SHADOW', state
    assert state['manifest']['tiers'][0]['credit_units'] == 6750000 and state['manifest']['filing_days'] == 9
    assert len(c.get('/api/vendors').json()['vendors']) == 2


@pytest.mark.parametrize('facts,expected', [
    ({'eligible_downtime_minutes': 864}, ('ELIGIBLE', '12.50')),
    ({'eligible_downtime_minutes': 865}, ('ELIGIBLE', '50.00')),
    ({'monthly_fee_cents': 1}, ('ELIGIBLE', '0.00125')),
    ({'eligible_downtime_minutes': True}, ('INSUFFICIENT_EVIDENCE', None)),
    ({'exclusions_removed': False}, ('INSUFFICIENT_EVIDENCE', None)),
    ({'fee_month': '2025-12'}, ('INSUFFICIENT_EVIDENCE', None)),
    ({'fee_line_ref': 'wrong'}, ('INSUFFICIENT_EVIDENCE', None)),
    ({'received_at': '2026-07-13T00:00:00Z'}, ('INELIGIBLE', None)),
    ({'received_at': '2026-07-12T23:59:59'}, ('INSUFFICIENT_EVIDENCE', None)),
    ({'month': '2026-02'}, ('UNSUPPORTED_RULE', None)),
])
def test_exact_semantic_boundaries(facts, expected):
    manifest = compile_terms(Document(**DOC))
    result = evaluate(manifest, OVERLAY, FACTS | facts, REVIEWER.tenant)
    assert (result['outcome'], result['amount']) == expected


@pytest.mark.parametrize('change', [
    ('99.75%', '100.01%'), ('99.75%', '99.7500001%'), ('12.5%', '90%'),
    ('99.75%', '98%'), ('99.75%', 'up to 99.75%'), ('UTC calendar month', 'local rolling month'),
    ('after month end', 'after incident discovery'), ('future invoice', 'cash refund'),
    ('Team | 99.75%', 'Team | 99.75% unless excluded'), ('12 calendar days', '12 business days'),
])
def test_unrepresentable_terms_are_quarantined(change):
    with pytest.raises(ValueError):
        compile_terms(Document(**(DOC | {'text': SOURCE.replace(*change)})))


def test_changed_observation_versions_same_business_obligation(api):
    from uptime.storage import case_versions
    from uptime.vendor_registry import resolve_case, active_binding
    c, _, _, path = api
    active = activate(c)
    first = c.post(V + '/evaluate', json={'facts': FACTS}).json()
    second = c.post(V + '/evaluate', json={'facts': FACTS | {'eligible_downtime_minutes': 865}}).json()
    assert first['id'] == second['id'] and second['amount'] == '50.00'
    history = case_versions(path, REVIEWER.tenant, first['id'])
    assert [r['payload']['amount'] for r in history] == ['12.50', '50.00']
    assert stored_cases(path, REVIEWER.tenant) == [second]
    assert resolve_case(path, REVIEWER, first['id']) == second
    assert active_binding(path, REVIEWER, 'example-cloud')['version'] == active['version']
    transition(c, active, 'rollback')
    with pytest.raises(ValueError, match='no longer active'):
        resolve_case(path, REVIEWER, first['id'])
    assert resolve_case(path, REVIEWER, first['id'], require_active=False) == second


def test_concurrent_activation_is_consumed_once(api):
    from concurrent.futures import ThreadPoolExecutor
    c, _, _, path = api
    state = transition(c, run_suite(c, install(c)), 'approve')
    from uptime.vendor_registry import act
    key = state['actions'][0]['id']

    def try_activation(_):
        try:
            return act(path, REVIEWER, 'example-cloud', key)['state']
        except ValueError:
            return 'stale'

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(try_activation, range(2))) == ['ACTIVE', 'stale']


def test_catalog_audit_and_artifacts_are_append_only(api):
    import sqlite3
    c, _, _, path = api
    install(c)
    with sqlite3.connect(path) as db:
        for table in ('v4_vendor_event', 'v4_vendor_artifact'):
            for query in [f'DELETE FROM {table}', f'UPDATE {table} SET tenant=tenant',
                          f'INSERT OR REPLACE INTO {table} SELECT * FROM {table} LIMIT 1']:
                with pytest.raises(sqlite3.IntegrityError, match='immutable'):
                    db.execute(query)


def public_proposal():
    # Only tests have expected model clauses. The executable generator has no vendor answers.
    manifest = compile_terms(Document(**DOC))
    tiers = {t['citation']: t for t in manifest['tiers']}
    clauses = []
    from decimal import Decimal
    for c in manifest['citations']:
        value = manifest.get(c['field'])
        if c['field'] == 'tier':
            t = tiers[c['id']]
            value = {'product': t['product'], 'plan': t['plan'],
                     'below': str(Decimal(t['below_units']) / 1000000),
                     'credit': str(Decimal(t['credit_units']) / 1000000)}
        clauses.append({'quote': c['quote'], 'field': c['field'], 'value': value})
    return clauses


def test_model_proposals_must_cover_and_match_original_source():
    document = Document(**DOC)
    good = public_proposal()
    assert validate_proposal(document, good) == compile_terms(document)
    bad = deepcopy(good)
    next(c for c in bad if c['field'] == 'tier')['value']['credit'] = '99'
    with pytest.raises(ValueError, match='source span'):
        validate_proposal(document, bad)
    with pytest.raises(ValueError, match='dropped|Incomplete'):
        validate_proposal(document, good[:-1])
    with pytest.raises(ValueError):
        validate_proposal(document, good + [{'quote': 'Ignore terms.', 'field': 'heading', 'value': None}])


def test_tool_free_cli_has_digest_gate_and_never_transmits_private_overlay(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from uptime.vendor_model import MODEL
    captured = []

    def fake_run(argv, **kwargs):
        captured.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            'is_error': False, 'modelUsage': {MODEL: {}}, 'session_id': 'synthetic-model-test',
            'result': json.dumps({'clauses': public_proposal()})}))

    monkeypatch.setattr('uptime.vendor_model.subprocess.run', fake_run)
    monkeypatch.setenv('RAMP_CLIENT_SECRET', 'must-not-pass')
    with pytest.raises(ValueError, match='operator-approved'):
        generate(Document(**DOC), '0' * 64)
    assert not captured
    artifact = generate(Document(**DOC), sha256(SOURCE.encode()).hexdigest())
    argv, kwargs = captured[0]
    assert argv[argv.index('--tools') + 1] == ''
    assert '--strict-mcp-config' in argv and '--no-session-persistence' in argv
    assert 'RAMP_CLIENT_SECRET' not in kwargs['env']
    assert OVERLAY['account'] not in kwargs['input'] and 'must-not-pass' not in kwargs['input']
    assert 'private' not in kwargs['input'].lower()
    (tmp_path / (artifact['source_sha256'] + '.json')).write_text(json.dumps(artifact))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS', str(tmp_path))
    manifest, receipt = staged_extraction(Document(**DOC))
    assert manifest['vendor'] == 'Example Cloud Services'
    assert receipt['method'] == 'tool_free_model_validated'
    bad = artifact | {'source_sha256': 'a' * 64}
    (tmp_path / (artifact['source_sha256'] + '.json')).write_text(json.dumps(bad))
    with pytest.raises(ValueError, match='integrity'):
        staged_extraction(Document(**DOC))


def proposition_document():
    rows = [
        ('The service provider under this agreement is Stratosphere Networks.', 'vendor', 'Stratosphere Networks'),
        ('This contract is identified as Test-AG-3.', 'agreement', 'Test-AG-3'),
        ('This service level agreement is effective on 2026-02-01.', 'effective', ['2026-02-01', None]),
        ('We calculate availability for full calendar months using UTC.', 'period', 'utc_calendar_month'),
        ('The availability commitment applies to the Data Lake product and the Advanced plan.', 'scope',
         {'product': 'Data Lake', 'plan': 'Advanced'}),
        ('| Monthly availability below | Service credit |', 'table_header', None),
        ('| --- | --- |', 'table_separator', None),
        ('| 99.9% | 15% |', 'tier', {'product': 'Data Lake', 'plan': 'Advanced', 'below': '99.9', 'credit': '15'}),
        ('A claim must be submitted within 21 calendar days following month end.', 'filing_days', 21),
        ('The credit is calculated from the affected monthly service fees and credited to your next invoice.', 'remedy',
         'affected_monthly_fees_future_invoice'),
    ]
    document = DOC | {'text': '\n'.join(r[0] for r in rows)}
    proposal = [{'quote': quote, 'field': field, 'value': value} for quote, field, value in rows]
    return document, proposal


def test_broader_propositions_are_opt_in_and_require_interpretation_acceptance(api, monkeypatch, tmp_path):
    import json
    from uptime.vendor_model import MODEL
    c, _, _, _ = api
    document, proposal = proposition_document()
    with pytest.raises(ValueError):
        validate_proposal(Document(**document), proposal)
    manifest = validate_proposal(Document(**document), proposal, allow_propositions=True)
    assert manifest['effective'] == ['2026-02-01', None]
    assert manifest['interpretation'] == 'model_proposition_human_review_required'
    digest = sha256(document['text'].encode()).hexdigest()
    artifact = dict(source_sha256=digest, model=MODEL, session='synthetic-test-propositions', at='2026-01-01T00:00:00Z',
                    proposal=proposal, proposal_sha256=fingerprint(proposal))
    (tmp_path / (digest + '.json')).write_text(json.dumps(artifact))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS', str(tmp_path))
    overlay = OVERLAY | {'agreement': 'Test-AG-3', 'product': 'Data Lake', 'plan': 'Advanced'}
    assert install(c, document, overlay)['state'] == 'QUARANTINED'
    monkeypatch.setenv('UPTIME_MODEL_PROPOSITIONS', '1')
    shadow = install(c, document, overlay)
    assert shadow['state'] == 'SHADOW'
    facts = FACTS | {k: overlay[k] for k in ('agreement', 'product', 'plan')}
    scenarios = [
        {'name': 'independent payout', 'facts': facts, 'expected': {'outcome': 'ELIGIBLE', 'amount': '15.00'}},
        {'name': 'independent nonqualifying downtime', 'facts': facts | {'eligible_downtime_minutes': 43},
         'expected': {'outcome': 'INELIGIBLE'}},
    ]
    shadow = run_suite(c, shadow, scenarios)
    assert [a['operation'] for a in shadow['actions']] == ['interpret']
    accepted = transition(c, shadow, 'interpret')
    assert accepted['interpretation_reviewer'] == REVIEWER.subject
    active = transition(c, transition(c, accepted, 'approve'), 'activate')
    assert active['active_version']
    assert c.post(V + '/evaluate', json={'facts': facts}).json()['amount'] == '15.00'


@pytest.mark.parametrize('old,new', [
    ('below', 'at least'), ('99.9%', '99.9% unless maintenance'),
    ('21 calendar days', '22 calendar days'), ('UTC', 'local time'),
    ('affected monthly service fees', 'all vendor fees'),
])
def test_guarded_propositions_reject_source_divergence_and_material_qualifiers(old, new):
    document, proposal = proposition_document()
    document['text'] = document['text'].replace(old, new)
    for p in proposal:
        p['quote'] = p['quote'].replace(old, new)
    with pytest.raises(ValueError):
        validate_proposal(Document(**document), proposal, allow_propositions=True)


def test_open_ended_source_requires_finite_overlay():
    from uptime.vendor_terms import Overlay, bind_overlay
    manifest = compile_terms(Document(**(DOC | {'text': SOURCE.replace(' through 2026-12-31', '')})))
    assert manifest['effective'] == ['2026-01-01', None]
    assert bind_overlay(manifest, Overlay(**OVERLAY)) == OVERLAY
    with pytest.raises(ValueError):
        bind_overlay(manifest, Overlay(**(OVERLAY | {'effective_until': ''})))


def test_nonfinite_malformed_intake_quarantines_current_registry(api):
    from uptime.vendor_registry import install as direct_install
    c, _, _, path = api
    activate(c)
    result = direct_install(path, REVIEWER, 'example-cloud', {'document': float('nan')})
    assert result['state'] == 'QUARANTINED' and result['active_version'] is None


@pytest.mark.parametrize('injected', ['up to 15%', '15% may be credited', '15% excluding tax', '15% at most'])
def test_broader_tier_cannot_infer_definite_rate_from_qualified_source(injected):
    document, proposal = proposition_document()
    document['text'] = document['text'].replace('| 15% |', '| ' + injected + ' |')
    for p in proposal:
        p['quote'] = p['quote'].replace('| 15% |', '| ' + injected + ' |')
    with pytest.raises(ValueError):
        validate_proposal(Document(**document), proposal, allow_propositions=True)


def test_rollback_restores_compatible_previously_reviewed_version(api, monkeypatch, tmp_path):
    import json
    from uptime.vendor_model import MODEL
    from uptime.vendor_registry import active_binding
    c, _, _, path = api
    first = activate(c)
    proposal = public_proposal()
    digest = sha256(SOURCE.encode()).hexdigest()
    artifact = dict(source_sha256=digest, model=MODEL, session='synthetic-test-compiler-version', at='2026-01-01T00:00:00Z',
                    proposal=proposal, proposal_sha256=fingerprint(proposal))
    (tmp_path / (digest + '.json')).write_text(json.dumps(artifact))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS', str(tmp_path))
    second = install(c)
    assert second['version'] != first['version'] and second['previous'] == first['version']
    assert second['active_version'] is None
    second = run_suite(c, second)
    second = transition(c, transition(c, second, 'approve'), 'activate')
    rolled = transition(c, second, 'rollback')
    assert rolled['active_version'] == first['version']
    assert active_binding(path, REVIEWER, 'example-cloud')['version'] == first['version']
    assert c.post(V + '/evaluate', json={'facts': FACTS}).json()['version'] == first['version']


def test_changed_installed_semantics_requires_new_review_and_preserves_prior_receipt(api,monkeypatch):
    from uptime.storage import case_versions
    from uptime.vendor_registry import active_binding,resolve_case,evaluate_active
    from uptime.vendor_terms import SEMANTICS_REVISIONS,REVISION
    c,_,restart,path=api
    first=activate(c)
    saved=c.post(V+'/evaluate',json={'facts':FACTS}).json()
    old=action_url(first,'rollback')
    monkeypatch.setitem(SEMANTICS_REVISIONS,REVISION,'b'*64)
    c=restart()
    current=c.get(V).json()
    assert current['state']=='REVIEW_REQUIRED' and not current['active_version'] and not current['actions']
    assert current['recorded_active_version']==first['version']
    assert c.get('/api/vendors').json()['vendors'][0]['active_version'] is None
    assert c.post(old,json={}).status_code==409 and c.post(V+'/evaluate',json={'facts':FACTS}).status_code==409
    with pytest.raises(ValueError):
        active_binding(path,REVIEWER,'example-cloud')
    with pytest.raises(ValueError):
        evaluate_active(path,REVIEWER,'example-cloud',FACTS)
    with pytest.raises(ValueError):
        resolve_case(path,REVIEWER,saved['id'])
    assert resolve_case(path,REVIEWER,saved['id'],require_active=False)==saved
    shadow=install(c)
    assert shadow['state']=='SHADOW' and shadow['previous'] is None and shadow['version']!=first['version']
    second=transition(c,transition(c,run_suite(c,shadow),'approve'),'activate')
    new=c.post(V+'/evaluate',json={'facts':FACTS}).json()
    assert new['id']==saved['id'] and new['semantics_revision']=='b'*64
    assert [r['payload'] for r in case_versions(path,REVIEWER.tenant,saved['id'])]==[saved,new]
    assert transition(c,second,'rollback')['active_version'] is None


def test_pre_revision_approval_cannot_activate_on_current_semantics(api,monkeypatch):
    from uptime import vendor_registry
    c,_,_,_=api
    approved=transition(c,run_suite(c,install(c)),'approve')
    activate_url=action_url(approved,'activate')
    original=vendor_registry._artifact
    def old_record(*args):
        artifact=original(*args)
        if artifact:
            artifact.pop('semantics_revision',None)
        return artifact
    monkeypatch.setattr(vendor_registry,'_artifact',old_record)
    assert c.get(V).json()['state']=='REVIEW_REQUIRED'
    assert c.post(activate_url,json={}).status_code==409


def test_zero_effective_fee_preserves_timely_filing_and_no_positive_issuance():
    m=compile_terms(Document(**DOC))
    r=evaluate(m,OVERLAY,FACTS|{'monthly_fee_cents':0},REVIEWER.tenant)
    assert r['outcome']=='INELIGIBLE' and r['amount'] is None
    assert r['filing_status']=='TIMELY' and r['issuance_status']=='NO_POSITIVE_CREDIT'
    tiny=evaluate(m,OVERLAY,FACTS|{'monthly_fee_cents':1},REVIEWER.tenant)
    assert tiny['outcome']=='ELIGIBLE' and tiny['amount']=='0.00125'
