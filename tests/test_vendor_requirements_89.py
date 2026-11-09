"""Read-only adapter requirement cards and generated shadow drafts (workstream 89).

Expected figures below are hand-computed from the cited clauses, not read from the
generator. Every source here is authored synthetic text; none is a real vendor's terms.
"""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from uptime import vendor_requirements as req
from uptime.contracts import Principal
from uptime.vendor_terms import _PROFILE_FILES, SEMANTICS_REVISIONS, Document, compile_terms

from test_vendor_catalog import DOC, OVERLAY, SOURCE, V, api, install, run_suite, transition  # noqa: F401 (fixture)
import test_vendor_resource as resource


def _requirements(c, url=V):
    response = c.get(url + '/requirements')
    assert response.status_code == 200, response.text
    return response.json()


def _by_element(card):
    return {row['element']: row for row in card['elements']}


def _quotes(manifest, ids):
    by_id = {c['id']: c for c in manifest['citations']}
    return [by_id[i]['quote'] for i in ids]


def _preview(c, state, facts, url=V):
    response = c.post(url + '/shadow-preview', json={'revision': state['revision'], 'facts': facts})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['dispatch_authorized'] is False
    return body['evaluation']


def test_new_module_is_outside_reviewed_semantics_so_existing_reviews_do_not_churn():
    assert all('vendor_requirements.py' not in files for files in _PROFILE_FILES.values())
    assert all('vendor_api.py' not in files for files in _PROFILE_FILES.values())
    assert set(SEMANTICS_REVISIONS) == {'monthly-availability/1', 'resource-month/1'}


def test_monthly_card_cites_every_required_element(api):
    c, _, _, _ = api
    state = install(c)
    body = _requirements(c)
    card, manifest = body['card'], c.get(V).json()['manifest']
    assert body['state'] == 'SHADOW' and body['version'] == state['version']
    assert body['authority'] == {'approval_gate': False, 'dispatch_authorized': False}
    assert card['supported'] and card['no_open_requirements'] and card['family'] == 'monthly-availability/1'
    rows = _by_element(card)
    assert [r['element'] for r in card['elements']] == list(req.ELEMENTS)
    assert rows['source_clauses']['status'] == 'PRESENT'
    tier_quotes = _quotes(manifest, rows['source_clauses']['detail']['fields']['tier'])
    assert tier_quotes == ['| Compute Tables | Team | 98% | 50% |', '| Compute Tables | Team | 99.75% | 12.5% |',
                           '| Message Relay | Premier | 99.9% | 40% |']
    assert rows['eligible_fee']['status'] == 'PRESENT'
    assert _quotes(manifest, rows['eligible_fee']['citations']) == [
        'Service credits apply to affected monthly fees on a future invoice.']
    assert rows['eligible_fee']['detail'] == {'remedy': 'affected_monthly_fees_future_invoice',
                                              'fee_line_ref': 'inv-june-line-C', 'currency': 'USD'}
    assert rows['evidence']['status'] == 'FAMILY_DEFINED' and len(rows['evidence']['detail']['observation']) == 4
    assert rows['exclusions']['status'] == 'NONE_STATED' and rows['exclusions']['citations'] == []
    assert rows['deadline']['status'] == 'PRESENT' and rows['deadline']['detail']['filing_days'] == 12
    assert _quotes(manifest, rows['deadline']['citations']) == [
        'Claims must be received within 12 calendar days after month end.']
    for citation in manifest['citations']:
        assert SOURCE[citation['start']:citation['end']] == citation['quote']
    assert any('independent expectations' in r for r in card['review_requirements'])


def test_generated_drafts_match_hand_calculation_and_shadow_evaluator(api):
    c, _, _, _ = api
    state = install(c)
    drafts = _requirements(c)['drafts']
    assert drafts['generated'] and drafts['month'] == '2026-04' and drafts['draft_fee_cents'] == 100000
    derived = {s['name']: s['derived'] for s in drafts['scenarios']}
    # April 2026 = 30 days = 43,200 minutes. 0.25% of 43,200 = 108 minutes; 2% = 864 minutes. Fee USD 1,000.00.
    assert derived['Availability one minute past the 99.75% threshold (109 of 43200 minutes down)'] == {
        'outcome': 'ELIGIBLE', 'amount': '125.00'}
    assert derived['Availability exactly at or above the 99.75% threshold (108 of 43200 minutes down)'] == {
        'outcome': 'INELIGIBLE', 'amount': None}
    assert derived['Availability one minute past the 98% threshold (865 of 43200 minutes down)'] == {
        'outcome': 'ELIGIBLE', 'amount': '500.00'}
    assert derived['Availability exactly at or above the 98% threshold (864 of 43200 minutes down)'] == {
        'outcome': 'ELIGIBLE', 'amount': '125.00'}
    # 12 calendar days after April ends: window closes at 2026-05-13T00:00:00Z (exclusive).
    by_name = {s['name']: s for s in drafts['scenarios']}
    assert by_name['Received at the last timely second']['facts']['received_at'] == '2026-05-12T23:59:59Z'
    assert by_name['Received when the filing window closes']['facts']['received_at'] == '2026-05-13T00:00:00Z'
    assert by_name['Month outside the governed interval']['facts']['month'] == '2026-12'
    assert derived['Affected fee unknown'] == {'outcome': 'INSUFFICIENT_EVIDENCE', 'amount': None}
    assert 'monthly_fee_cents' not in by_name['Affected fee unknown']['facts']
    outcomes = {s['derived']['outcome'] for s in drafts['scenarios']}
    assert outcomes == {'ELIGIBLE', 'INELIGIBLE', 'INSUFFICIENT_EVIDENCE', 'UNSUPPORTED_RULE'}
    for scenario in drafts['scenarios']:
        result = _preview(c, state, scenario['facts'])
        assert {'outcome': result['outcome'], 'amount': result['amount']} == scenario['derived'], scenario['name']


def test_drafts_cannot_be_submitted_unchanged_as_the_independent_suite(api):
    c, _, _, _ = api
    state = install(c)
    drafts = _requirements(c)['drafts']['scenarios']
    response = c.post(V + '/tests', json={'revision': state['revision'], 'tests': drafts})
    assert response.status_code == 422
    after = c.get(V).json()
    assert after['revision'] == state['revision'] and after['checks'] == [] and after['actions'] == []


def test_requirements_route_is_read_only_and_tenant_scoped(api):
    c, identity, _, _ = api
    state = install(c)
    before = c.get(V).json()
    _requirements(c)
    _requirements(c)
    assert c.get(V).json()['audit'] == before['audit'] and c.get(V).json()['revision'] == state['revision']
    identity[0] = Principal('demo-tenant', 'test-viewer', 'viewer')
    assert _requirements(c)['card']['no_open_requirements']
    identity[0] = Principal('other-tenant', 'test-other', 'reviewer')
    assert c.get(V + '/requirements').status_code == 404


def test_quarantined_intake_reports_a_review_requirement_not_a_card(api):
    c, _, _, _ = api
    install(c, DOC | {'text': SOURCE + '\nCash refunds replace all service credits.'})
    body = _requirements(c)
    assert body['state'] == 'QUARANTINED'
    assert body['card']['supported'] is False and body['card']['elements'] == []
    assert body['card']['review_requirements'][0].startswith('Source or overlay validation failed.')
    assert body['drafts'] == {'generated': False, 'reason': 'No compiled adapter is installed.', 'scenarios': []}


def test_missing_cited_element_becomes_a_concrete_requirement():
    manifest = compile_terms(Document(**DOC))
    assert req.requirement_card(manifest, OVERLAY)['no_open_requirements']
    damaged = deepcopy(manifest)
    for citation in damaged['citations']:
        if citation['field'] == 'filing_days':
            citation['field'] = 'heading'
    card = req.requirement_card(damaged, OVERLAY)
    rows = _by_element(card)
    assert card['no_open_requirements'] is False and rows['deadline']['status'] == 'REVIEW_REQUIRED'
    assert 'claim filing deadline' in rows['deadline']['requirement']
    assert card['review_requirements'][0] == rows['deadline']['requirement']
    unknown = req.requirement_card({'family': 'quarterly-uptime/9'}, OVERLAY)
    assert unknown['supported'] is False and unknown['elements'] == [] and unknown['review_requirements']
    assert req.scenario_drafts({'family': 'quarterly-uptime/9'}, OVERLAY)['generated'] is False


def test_resource_month_card_grounds_fee_evidence_exclusions_and_deadline_in_cited_blocks():
    manifest = resource.compiled()
    card = req.requirement_card(manifest, resource.OVERLAY)
    rows = _by_element(card)
    assert card['supported'] and card['no_open_requirements'] and card['family'] == 'resource-month/1'
    by_id = {c['id']: c for c in manifest['citations']}
    for name, key in (('eligible_fee', 'fee_basis'), ('evidence', 'evidence'), ('exclusions', 'exclusions'),
                      ('deadline', 'filing')):
        assert rows[name]['status'] == 'PRESENT', name
        assert any(key in by_id[i]['propositions'] for i in rows[name]['citations']), name
    assert rows['exclusions']['detail']['exclusions'] == ['Customer cable damage', 'approved calibration windows']
    assert rows['deadline']['detail']['filing'] == {'kind': 'calendar_days', 'count': 10, 'utc_time': '18:00',
                                                    'endpoint': 'inclusive'}
    assert any('interpretation' in r for r in card['review_requirements'])
    drafts = req.scenario_drafts(manifest, resource.OVERLAY)
    assert drafts['generated'] is False and 'Resource-month' in drafts['reason']


NEW_SOURCE = """Synthetic public test agreement
Provider: Halcyon Queueing Ltd
Contract ID: HQL-SLA-2027
Effective period: 2027-02-01 through 2027-12-31
Availability is measured over each UTC calendar month.
| Product | Plan | Monthly uptime below | Service credit |
| --- | --- | --- | --- |
| Durable Queues | Scale | 97% | 100% |
| Durable Queues | Scale | 99.5% | 25% |
For Durable Queues on the Scale plan, monthly availability below 99.95% earns a 10% service credit.
Claims must be received within 30 calendar days after month end.
Service credits apply to affected monthly fees on a future invoice."""
NEW_DOC = {'name': 'Authored queueing SLA', 'uri': 'urn:synthetic:halcyon-queueing-sla', 'classification': 'synthetic_public',
           'text': NEW_SOURCE}
NEW_OVERLAY = dict(account='acct-hq-7', agreement='HQL-SLA-2027', product='Durable Queues', plan='Scale', currency='USD',
                   effective_from='2027-02-01', effective_until='2027-06-30', fee_line_ref='hq-line-queues')


def test_new_vendor_name_reaches_shadow_with_useful_drafts_and_no_vendor_code(api):
    """Authored control within an operator-supplied family: proves no vendor code path, not family discovery (D05)."""
    c, _, _, _ = api
    url = '/api/vendors/halcyon-queueing'
    state = install(c, NEW_DOC, NEW_OVERLAY, url)
    assert state['state'] == 'SHADOW' and state['vendor'] == 'Halcyon Queueing Ltd' and not state['active_version']
    body = _requirements(c, url)
    assert body['card']['no_open_requirements'] and body['drafts']['month'] == '2027-02'
    derived = {s['name']: s['derived'] for s in body['drafts']['scenarios']}
    # February 2027 = 28 days = 40,320 minutes. 0.05% = 20.16; 0.5% = 201.6; 3% = 1,209.6 minutes. Fee USD 1,000.00.
    assert derived['Availability one minute past the 99.95% threshold (21 of 40320 minutes down)'] == {
        'outcome': 'ELIGIBLE', 'amount': '100.00'}
    assert derived['Availability exactly at or above the 99.95% threshold (20 of 40320 minutes down)']['outcome'] == 'INELIGIBLE'
    assert derived['Availability one minute past the 99.5% threshold (202 of 40320 minutes down)']['amount'] == '250.00'
    assert derived['Availability exactly at or above the 99.5% threshold (201 of 40320 minutes down)']['amount'] == '100.00'
    assert derived['Availability one minute past the 97% threshold (1210 of 40320 minutes down)']['amount'] == '1000.00'
    assert derived['Availability exactly at or above the 97% threshold (1209 of 40320 minutes down)']['amount'] == '250.00'
    for scenario in body['drafts']['scenarios']:
        result = _preview(c, state, scenario['facts'], url)
        assert {'outcome': result['outcome'], 'amount': result['amount']} == scenario['derived'], scenario['name']
    package = Path(req.__file__).parent
    assert not [p.name for p in package.glob('*.py') if 'halcyon' in p.read_text(encoding='utf-8').casefold()]
    # Shadow is not approval: drafts expose no action, and approval still needs an independent suite.
    assert c.get(url).json()['actions'] == []
    tested = run_suite(c, state, [
        {'name': 'hand-computed 21 minutes', 'facts': body['drafts']['scenarios'][0]['facts'],
         'expected': {'outcome': 'ELIGIBLE', 'amount': '100.00'}},
        {'name': 'hand-computed 20 minutes', 'facts': body['drafts']['scenarios'][1]['facts'],
         'expected': {'outcome': 'INELIGIBLE'}}], url)
    assert [a['operation'] for a in tested['actions']] == ['approve']
    # Reusing draft facts (even with hand-computed expectations) is reported to the reviewer, never hidden.
    overlap = _requirements(c, url)['draft_overlap']
    assert overlap['tests_reusing_draft_facts'] == ['hand-computed 21 minutes', 'hand-computed 20 minutes']
    assert 'independently' in overlap['warning']
    assert transition(c, tested, 'approve', url)['reviewer_kind'] == 'scripted_test'


def test_independent_facts_raise_no_overlap_warning(api):
    c, _, _, _ = api
    run_suite(c, install(c))
    assert _requirements(c)['draft_overlap'] == {'tests_reusing_draft_facts': [], 'warning': None}


def test_requirements_expose_nothing_beyond_the_detail_view_for_the_same_principal(api):
    c, identity, _, _ = api
    install(c)
    identity[0] = Principal('demo-tenant', 'test-viewer', 'viewer')
    detail, body = c.get(V).json(), _requirements(c)
    assert detail['overlay'] == OVERLAY
    fee = next(e for e in body['card']['elements'] if e['element'] == 'eligible_fee')['detail']
    assert {fee['fee_line_ref'], fee['currency']} <= set(detail['overlay'].values())


def test_propositions_manifest_has_no_false_uncategorized_alarm_and_unknown_content_requires_review():
    from test_vendor_catalog import proposition_document
    from uptime.vendor_model import validate_proposal
    document, proposal = proposition_document()
    manifest = validate_proposal(Document(**document), proposal, allow_propositions=True)
    overlay = dict(account='acct-p', agreement='Test-AG-3', product='Data Lake', plan='Advanced', currency='USD',
                   effective_from='2026-03-01', effective_until='2026-08-31', fee_line_ref='line-p')
    card = req.requirement_card(manifest, overlay)
    rows = _by_element(card)
    assert card['no_open_requirements'] and rows['exclusions']['status'] == 'NONE_STATED'
    assert any('interpretation' in r for r in card['review_requirements'])
    widened = deepcopy(manifest) | {'maintenance_windows': ['Sunday 02:00-04:00 UTC']}
    rows = _by_element(req.requirement_card(widened, overlay))
    assert rows['exclusions']['status'] == 'REVIEW_REQUIRED'
    assert rows['exclusions']['detail'] == {'uncategorized': ['maintenance_windows']}


def test_both_monthly_compilers_refuse_a_standalone_exclusion_sentence():
    """Pins the compiler behavior that NONE_STATED summarizes (vendor_requirements is outside the semantics hash)."""
    import pytest
    from test_vendor_catalog import proposition_document
    from uptime.vendor_model import validate_proposal
    sentence = 'Downtime caused by scheduled maintenance is excluded.'
    with pytest.raises(ValueError):
        compile_terms(Document(**(DOC | {'text': SOURCE + '\n' + sentence})))
    document, proposal = proposition_document()
    document['text'] += '\n' + sentence
    for field in ('heading', 'unsupported', 'remedy'):
        with pytest.raises(ValueError):
            validate_proposal(Document(**document), proposal + [{'quote': sentence, 'field': field, 'value': None}],
                              allow_propositions=True)


def test_resource_element_present_without_a_cited_block_requires_review():
    manifest = deepcopy(resource.compiled())
    for citation in manifest['citations']:
        citation['propositions'].pop('filing', None)
    rows = _by_element(req.requirement_card(manifest, resource.OVERLAY))
    assert rows['deadline']['status'] == 'REVIEW_REQUIRED' and rows['deadline']['citations'] == []
    assert 'without a cited source block' in rows['deadline']['requirement']


def test_malformed_artifacts_summarize_as_refusals_not_errors():
    manifest = compile_terms(Document(**DOC))
    for overlay in ({}, OVERLAY | {'effective_until': None}, OVERLAY | {'override': {'filing_days': None}},
                    {k: v for k, v in OVERLAY.items() if k != 'product'}):
        drafts = req.scenario_drafts(manifest, overlay)
        assert drafts['generated'] is False and drafts['scenarios'] == []
        assert isinstance(req.requirement_card(manifest, overlay)['review_requirements'], list)
    empty = req.requirement_card({'family': 'monthly-availability/1'}, OVERLAY)
    assert empty['supported'] and empty['no_open_requirements'] is False
    assert _by_element(empty)['source_clauses']['status'] == 'REVIEW_REQUIRED'
    assert req.requirement_card({'family': 'monthly-availability/1', 'citations': 'x'}, OVERLAY)['supported'] is False


def _sweep_source(thresholds, credits):
    rows = '\n'.join(f'| Sweep Service | Core | {t}% | {c}% |' for t, c in zip(thresholds, credits))
    return ('Synthetic public test contract\nVendor: Sweep Vendor\nAgreement: SWEEP-1\n'
            'Effective: 2026-01-01 through 2031-12-31\nAvailability is measured over each UTC calendar month.\n'
            '| Product | Plan | Monthly uptime below | Service credit |\n| --- | --- | --- | --- |\n' + rows +
            '\nClaims must be received within {days} calendar days after month end.\n'
            'Service credits apply to affected monthly fees on a future invoice.')


def _percent(millionths):
    from decimal import Decimal
    return format(Decimal(millionths).scaleb(-6).normalize(), 'f')


def test_property_sweep_drafts_equal_the_evaluator_for_random_tiers_months_and_windows():
    from hypothesis import given, settings, strategies as st
    from uptime.vendor_eval import evaluate
    from uptime.vendor_terms import Overlay, bind_overlay

    @settings(max_examples=60, deadline=None, derandomize=True)
    @given(st.lists(st.integers(90_000_000, 99_999_999), min_size=1, max_size=3, unique=True),
           st.lists(st.integers(1_000_000, 100_000_000), min_size=3, max_size=3, unique=True),
           st.integers(2026, 2030), st.integers(1, 12), st.integers(0, 14), st.integers(1, 60))
    def check(thresholds, credits, year, month, span, days):
        thresholds = [_percent(t) for t in sorted(thresholds)]
        credits = [_percent(c) for c in sorted(credits, reverse=True)][:len(thresholds)]
        text = _sweep_source(thresholds, credits).replace('{days}', str(days))
        manifest = compile_terms(Document(name='Sweep', uri='urn:synthetic:sweep', classification='synthetic_public', text=text))
        end_year, end_month = divmod(month - 1 + span, 12)
        from calendar import monthrange
        last = monthrange(year + end_year, end_month + 1)[1]
        overlay = bind_overlay(manifest, Overlay(**dict(
            account='acct-s', agreement='SWEEP-1', product='Sweep Service', plan='Core', currency='USD',
            effective_from=f'{year}-{month:02d}-01', effective_until=f'{year + end_year}-{end_month + 1:02d}-{last:02d}',
            fee_line_ref='line-s')))
        drafts = req.scenario_drafts(manifest, overlay)
        assert drafts['generated'], drafts['reason']
        assert req.requirement_card(manifest, overlay)['no_open_requirements']
        for scenario in drafts['scenarios']:
            result = evaluate(manifest, overlay, scenario['facts'], 'demo-tenant')
            assert {'outcome': result['outcome'], 'amount': result['amount']} == scenario['derived'], scenario['name']
    check()
    # Six-decimal percents on the placeholder fee produce fractional cents, kept exact as the evaluator does.
    assert req._money(req.DRAFT_FEE_CENTS, 12_345_678) == '123.45678'
