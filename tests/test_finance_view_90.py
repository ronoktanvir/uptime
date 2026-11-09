"""Finance summary over the real authored workflow: next actions come from case state, money is copied, never derived."""
from copy import deepcopy
import json
import re

import pytest
from fastapi.testclient import TestClient

from scripts import setup_northwind as setup
from uptime.auth import SCRIPT, DEFAULT_ORIGIN
from uptime.contracts import Principal
from uptime.finance_view import attention, decimal, money, summarize


@pytest.fixture(scope='module')
def walk(tmp_path_factory):
    """Every projection of one complete authored run, read through the real HTTP routes."""
    app, private, events = setup.prepare(tmp_path_factory.mktemp('finance') / 'owned', DEFAULT_ORIGIN)
    client = TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 1234), raise_server_exceptions=False)
    actor, _ = setup.seed(client, app, private, events)
    read = lambda: setup.checked(client.get('/api/workspace/workflow', headers=actor.headers))['workflow']
    states, cases = [read()], [app.state.bench.case(Principal('bears', SCRIPT, 'reviewer'), 'inbox-northwind-2026-01')]
    while states[-1]['next_actions']:
        setup.checked(actor.post('/api/workspace/workflow/actions/' + states[-1]['next_actions'][0]['id'], {}))
        states.append(read())
        cases.append(app.state.bench.case(Principal('bears', SCRIPT, 'reviewer'), 'inbox-northwind-2026-01'))
    yield states, cases
    client.close()


def kinds(projection):
    return [item['kind'] for item in projection['finance']['attention']]


def test_walk_has_the_expected_eleven_actions(walk):
    states, _ = walk
    assert len(states) == 12 and states[-1]['next_actions'] == []
    assert states[-1]['ledger']['bill']['outstanding_amount'] == '8600.00'


def test_initial_state_lists_deadline_approval_price_review_missing_usage_then_next_step(walk):
    first = walk[0][0]
    assert kinds(first) == ['CLAIM_DEADLINE', 'REVIEW_REQUIRED', 'REVIEW_REQUIRED', 'MISSING_USAGE', 'NEXT_STEP']
    deadline, approval, price, usage, step = first['finance']['attention']
    assert '2026-03-03T00:00:00+00:00' in deadline['detail'] and '1 day 12 hours' in deadline['detail']
    assert deadline['title'] == 'File the January 2026 claim before the deadline'
    assert approval['title'] == 'Approve the claim packet before it is filed' and approval['owner'] == 'reviewer'
    assert price['title'] == 'Review invoice NW-2026-03 before payment'
    assert all(s in price['detail'] for s in ('$12,000.00', '$11,000.00', 'amendment-v2', '$1,000.00', 'not an awarded credit'))
    assert usage['title'] == 'Complete March 2026 usage evidence' and usage['refs'] == ['northwind-monthly-coverage-2026-03']
    assert 'not ineligible' in usage['detail'] and 'undetermined' in usage['detail']
    assert step['title'] == 'Next step: Approve January claim'


def test_ineligible_february_is_never_reported_as_missing_evidence(walk):
    for state in walk[0]:
        months = {m['month']: m['outcome'] for m in state['months']}
        assert months['2026-02'] == 'INELIGIBLE'
        assert not any('February' in item['title'] for item in state['finance']['attention'])


def test_each_state_derives_its_items_from_the_case(walk):
    states, cases = walk
    for state, case in zip(states, cases):
        offered = {a['id'] for a in case['actions']}
        approvals = [i for i in state['finance']['attention'] if i['title'].startswith('Approve the')]
        assert bool(approvals) == bool(offered & {'approve-claim', 'approve-response'})
        filed = bool(state['claim']['receipt_id'])
        assert ('CLAIM_DEADLINE' in kinds(state)) == (not filed)
        assert ('MISSING_EVIDENCE' in kinds(state)) == (case['stage'] == 'NEEDS_EVIDENCE' and case['requested_artifact'] is not None)
        steps = [i for i in state['finance']['attention'] if i['kind'] == 'NEXT_STEP']
        if state['next_actions']:
            assert steps[-1]['title'] == 'Next step: ' + state['next_actions'][0]['label']
        assert 'RECONCILIATION_CONFLICT' not in kinds(state) and 'MISSING_AGREEMENT' not in kinds(state)


def test_requested_vendor_artifact_is_named_from_the_claim(walk):
    needs = [s for s in walk[0] if s['claim']['state'] == 'NEEDS_EVIDENCE']
    assert needs
    item = next(i for i in needs[0]['finance']['attention'] if i['kind'] == 'MISSING_EVIDENCE')
    artifact = needs[0]['claim']['requested_artifact']
    assert artifact['type'] in item['detail'] and artifact['ref'] in item['detail'] and item['refs'] == [artifact['ref']]


def test_final_stages_bill_and_destination_are_server_values(walk):
    final = walk[0][-1]
    summary = final['finance']
    assert [(r['stage'], r['amount']) for r in summary['stages']] == [
        ('estimated', '2400.00'), ('claimed', '2400.00'), ('awarded', '2400.00'), ('posted', '2400.00'), ('applied', '2400.00')]
    assert summary['stages'][3]['label'] == 'Posted to Local ledger'
    assert summary['bill'] == dict(id='NW-2026-04', original='11000.00', applied='2400.00', outstanding='8600.00',
                                   application_ref=final['ledger']['record_ids']['application'])
    assert summary['ramp']['destination'] == 'Local ledger' and summary['ramp']['linked_record'] is None
    assert 'No Ramp bill is linked' in summary['ramp']['note']
    assert kinds(final) == ['REVIEW_REQUIRED', 'MISSING_USAGE']
    assert final['price_finding']['amount'] == '1000.00' and final['price_finding']['credit_applied'] == '0.00'


def test_projection_additions_copy_the_domain_values(walk):
    states, cases = walk
    for state, case in zip(states, cases):
        assert state['claim']['filing_cutoff'] == case['filing_cutoff'] == '2026-03-03T00:00:00+00:00'
        assert state['claim']['month'] == '2026-01'
        assert state['claim']['pending_approvals'] == sorted(a['id'] for a in case['actions'] if a['id'].startswith('approve-'))
        assert state['claim']['requested_artifact'] == case['requested_artifact']
        assert state['price_finding']['lines'] == [dict(line_id='cloud-hosting-monthly', product='Cloud Hosting',
            version='amendment-v2', billed='12000.00', expected='11000.00', delta='1000.00', direction='OVERCHARGE')]
        january, february, march = state['months']
        assert january['inputs'] == dict(governing_fee='12000.00', currency='USD', fee_version=january['inputs']['fee_version'],
            eligible_downtime_minutes='135', completed_steps='2', credit_percent='20', claim_cutoff='2026-03-03T00:00:00+00:00',
            monitor_ref='northwind-monthly-coverage-2026-01')
        assert february['inputs']['completed_steps'] == '0' and february['inputs']['credit_percent'] == '0'
        assert march['inputs'] == {} and march['amount'] is None
        assert all(h['actor'] == SCRIPT for h in state['onboarding']['history'])
        without = {k: v for k, v in state.items() if k != 'finance'}
        assert state['finance'] == summarize(without)


def test_every_amount_in_the_summary_is_copied_from_the_projection(walk):
    for state in walk[0]:
        source = {k: v for k, v in state.items() if k != 'finance'}
        exact = {v for v in re.findall(r'"(-?\d+(?:\.\d+)?)"', json.dumps(source))}
        shown = set(re.findall(r'\$([\d,]+\.\d\d)', json.dumps(state['finance'])))
        assert shown, 'summary should show at least the price review amounts'
        assert all(value.replace(',', '') in exact for value in shown), shown - exact


def test_summarize_does_not_mutate_its_input(walk):
    state = deepcopy(walk[0][0])
    before = deepcopy(state)
    summarize(state)
    attention(state)
    assert state == before


def base(walk):
    projection = deepcopy(walk[0][-1])
    projection.pop('finance')
    return projection


@pytest.mark.parametrize('change,expected', [
    (lambda p: p['ledger'].update(posted='2500.00'), 'posted credit exceeds the awarded amount'),
    (lambda p: p['ledger'].update(applied='2500.00'), 'applied credit exceeds the posted credit'),
    (lambda p: p['ledger']['record_ids'].update(credit=None), 'no single matching credit record'),
    (lambda p: p['connection'].update(receipt_status='NOT_POSTED'), 'no verified destination read-back'),
    (lambda p: p['ledger']['record_ids'].update(application=None), 'no single matching application record'),
    (lambda p: p['ledger']['bill'].update(outstanding_amount='11000.01'), 'bill balance is outside its original amount'),
])
def test_reconciliation_conflicts_come_first_and_name_the_disagreement(walk, change, expected):
    projection = base(walk)
    change(projection)
    items = attention(projection)
    assert items[0]['kind'] == 'RECONCILIATION_CONFLICT' and expected in items[0]['detail']
    assert items[0]['owner'] == 'finance'


def test_unparseable_amounts_stay_unknown_without_inventing_a_conflict(walk):
    projection = base(walk)
    projection['ledger'].update(posted='2,400.00', awarded=None)
    assert decimal('2,400.00') is None and decimal(None) is None and decimal(' 1.00') is None and decimal('NaN') is None
    assert 'RECONCILIATION_CONFLICT' not in [i['kind'] for i in attention(projection)]
    assert money(None) == 'not determined' and money('12000.00') == '$12,000.00' and money('-5.10') == '-$5.10'


@pytest.mark.parametrize('field', ['version', 'documents'])
def test_missing_agreement_is_reported_without_guessing(walk, field):
    projection = base(walk)
    projection['contract'][field] = None if field == 'version' else []
    item = next(i for i in attention(projection) if i['kind'] == 'MISSING_AGREEMENT')
    assert item['section'] == 'finance-agreement' and 'undetermined' in item['detail']


def test_a_closed_filing_window_is_not_offered_as_fileable(walk):
    projection = deepcopy(walk[0][0])
    projection.pop('finance')
    projection['as_of'] = '2026-03-03T00:00:00+00:00'
    item = next(i for i in attention(projection) if i['kind'] == 'CLAIM_DEADLINE')
    assert item['title'] == 'The January 2026 filing window has closed' and 'No claim can be filed' in item['detail']
    projection['claim']['filing_cutoff'] = None
    assert 'CLAIM_DEADLINE' not in [i['kind'] for i in attention(projection)]


def test_only_a_server_supplied_ramp_record_is_linked(walk):
    projection = base(walk)
    assert summarize(projection)['ramp']['linked_record'] is None
    projection['ramp_record'] = {'id': 'f74ba12c-95d0-582d-9f62-26d8057d1d37'}
    assert summarize(projection)['ramp'] == dict(destination='Local ledger', linked_record=projection['ramp_record'], note=None)


def test_nothing_waiting_when_no_item_and_no_action(walk):
    projection = base(walk)
    projection['price_finding'].update(state='CLOSED')
    projection['months'] = [m for m in projection['months'] if m['outcome'] != 'INSUFFICIENT_EVIDENCE']
    assert [(i['kind'], i['title']) for i in attention(projection)] == [('NEXT_STEP', 'No step is waiting')]
    assert 'recorded in Local ledger' in attention(projection)[0]['detail']
