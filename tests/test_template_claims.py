"""A claim for the contract an approved template read: the Northwind lifecycle, carried by the same workflow.

No network and no Claude CLI: a stand-in replaces the template service, as in tests/test_template_agreements.py.
"""
from copy import deepcopy
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from scripts import setup_northwind as setup
from uptime import template_claims as tc
from uptime.auth import DEFAULT_ORIGIN
from uptime.storage import database

EXPECTED = json.loads((tc.CONTRACTS / 'expected.json').read_text())['halcyon-a']
TEMPLATE = {'id': 'halcyon-availability-addendum/1', 'sha256': 'cd' * 32}


def entry(values=None, reading_id='rd_a1', read_at='2026-11-10T13:05:00Z'):
    return {'build_id': 'tb_7a01', 'reading_id': reading_id, 'template': dict(TEMPLATE), 'vendor': 'Halcyon Grid Services',
            'document': {'id': 'halcyon-a', 'title': 'Halcyon Grid: Platform Availability Addendum', 'customer': EXPECTED['customer']},
            'values': dict(EXPECTED['terms'] if values is None else values), 'read_at': read_at}


class StandIn:
    """The members of TemplateBuilds the money link and the claims read."""
    def __init__(self, entries):
        self.entries, self.on_reading = list(entries), None

    def approved_readings(self):
        return deepcopy(self.entries)

    def set_agreement(self, build_id, reading_id, agreement):
        pass

    def get(self, build_id):
        return {'id': build_id, 'template': dict(TEMPLATE, approved_by='scripted-test-reviewer', approved_at='2026-11-10T13:04:00Z')}


@pytest.fixture
def served(tmp_path):
    app, private, events = setup.prepare(tmp_path / 'owned', DEFAULT_ORIGIN, routine_automation=True)  # as served by default
    client = TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 1234), raise_server_exceptions=False)
    actor, _ = setup.seed(client, app, private, events)
    yield app, client, actor
    client.close()


def connect(app, entries):
    from uptime.template_agreements import connect as money_link
    app.state.template_builds = StandIn(entries)
    money_link(app)
    return tc.connect(app, **app.state.template_claim_inputs)


def read(client, actor):
    response = client.get('/api/template-claims/halcyon-a', headers=actor.headers)
    assert response.status_code == 200, response.text
    return response.json()['workflow']


def press(client, actor, identity):
    return actor.post('/api/template-claims/halcyon-a/actions/' + identity, {})


def decide(client, actor):
    """Press the one offered decision; return the new projection."""
    offered = read(client, actor)['next_actions']
    assert len(offered) == 1, offered
    response = press(client, actor, offered[0]['id'])
    assert response.status_code == 200, response.text
    return response.json()['workflow']


def stages(view):
    return {row['stage']: row['amount'] for row in view['finance']['stages']}


def ops(view):
    return [(s['operation'], s['authority']['kind']) for s in view['automation']['steps']]


def test_authored_inputs_are_consistent_and_the_estimate_is_the_engines():
    from uptime import template_agreements as ta
    inputs = tc.load_inputs('halcyon-a')
    assert inputs['input_sha256']['service-log.txt'] == inputs['lifecycle']['supplement']['artifact']['body_sha256']
    agreement = ta.evaluate(entry(), ta.load_evidence('halcyon-a'))
    # October 2026: 31 x 1,440 = 44,640 minutes; 263 unavailable -> 44,377 available = 99.4108...%, below the 99.5%
    # second-tier threshold, so 25% (the 30% cap is not reached). 25% x USD 8,000.00 = USD 2,000.00.
    assert (agreement['availability_percent'], agreement['credit_percent'], agreement['monthly_fee'], agreement['credit']) == (
        '99.410', '25', '8000.00', {'amount': '2000.00', 'currency': 'USD', 'stage': 'ESTIMATED'})
    package = tc.build_package(entry(), inputs)
    assert package['document']['text'].count('\n') == len(package['manifest']['citations'])
    assert Decimal('8000.00') * Decimal('0.25') == Decimal(agreement['credit']['amount'])


def test_nothing_is_possible_before_an_accepted_read(served):
    app, client, actor = served
    assert client.get('/api/template-claims/halcyon-a', headers=actor.headers).status_code == 404  # claims not connected
    connect(app, [])
    assert client.get('/api/template-claims/halcyon-a', headers=actor.headers).status_code == 404  # no read on file
    assert press(client, actor, 'action-anything').status_code == 404
    # A read that does not reach a credit (no second tier, no first tier) offers nothing either.
    app.state.template_builds.entries = [entry(dict(EXPECTED['terms'], measurement_period='calendar_quarter'))]
    assert client.get('/api/template-claims/halcyon-a', headers=actor.headers).status_code == 404
    assert not (app.state.template_claim_inputs['directory'] / 'template-claims').exists()


def test_whole_path_to_the_credit_applied_once_on_the_next_invoice(served):
    app, client, actor = served
    connect(app, [entry()])
    northwind_before = setup.checked(client.get('/api/workspace/workflow', headers=actor.headers))['workflow']
    view = read(client, actor)
    assert view['claim']['state'] == 'NOT_OPENED' and view['next_actions'][0]['label'] == 'Approve October claim'
    assert view['reading']['read_by'] == 'FIXED_RULES' and view['reading']['template_id'] == TEMPLATE['id']
    assert view['reading']['approved_by'] == 'scripted-test-reviewer' and view['reading']['model_calls'] == 0
    assert stages(view) == {'estimated': '2000.00', 'claimed': '0.00', 'awarded': '0.00', 'posted': '0.00', 'applied': '0.00'}
    row = next(o for o in northwind_before['opportunities'] if o.get('source') == 'template')
    assert row['claim'] == dict(row['claim'], stage='estimated', amount='2000.00', next='Reviewer', href='#template-claim/halcyon-a')

    # Decision 1: approve the October claim. Uptime installs the read terms, opens the claim, receives the month's
    # signed records, files, and the counterparty asks for the service log.
    view = decide(client, actor)
    assert view['claim']['state'] == 'RESPONSE_DRAFTED' and view['ledger']['claimed'] == '2000.00'
    assert view['claim']['requested_artifact']['ref'] == 'HGS-OCT-LOG-001'
    assert ops(view) == [('install-agreement', 'APPROVED_OPERATION'), ('receive-status', 'EVENT_INTAKE'), ('receive-impact', 'EVENT_INTAKE'),
                         ('receive-coverage', 'EVENT_INTAKE'), ('receive-month-invoice', 'EVENT_INTAKE'), ('approve-claim', 'PERSON'),
                         ('submit-claim', 'APPROVED_OPERATION'), ('receive-denial', 'EVENT_INTAKE'),
                         ('receive-artifact', 'EVENT_INTAKE'), ('receive-verification', 'EVENT_INTAKE')]
    assert view['next_actions'][0]['label'] == 'Approve response'
    assert view['contract']['version'] and view['claim']['sla_source_sha256'] != view['contract']['documents'][0]['source_sha256']
    assert stages(view)['claimed'] == '2000.00' and stages(view)['awarded'] == '0.00'

    # Decision 2: approve the response; it is sent after the cooldown and the vendor awards.
    view = decide(client, actor)
    assert view['claim']['state'] == 'AWARDED' and stages(view)['awarded'] == '2000.00'
    assert view['next_actions'][0]['label'] == 'Post to Local ledger'

    # Decision 3: post to the local ledger; the next invoice arrives through the signed billing source.
    view = decide(client, actor)
    assert stages(view)['posted'] == '2000.00' and view['connection']['receipt_status'] == 'VERIFIED_LOCAL_READBACK'
    assert view['ledger']['bill']['id'] == 'HGS-INV-2026-12-2391' and view['ledger']['bill']['original_amount'] == '8000.00'
    assert view['next_actions'][0]['label'] == 'Apply credit to eligible invoice'

    # Decision 4: apply it once to the next invoice.
    view = decide(client, actor)
    assert stages(view) == {'estimated': '2000.00', 'claimed': '2000.00', 'awarded': '2000.00', 'posted': '2000.00', 'applied': '2000.00'}
    assert view['ledger']['bill']['outstanding_amount'] == '6000.00' and view['finance']['bill']['applied'] == '2000.00'
    assert view['automation']['state'] == 'COMPLETE' and view['next_actions'] == []
    assert view['automation']['counts']['person_decisions'] == 4
    # The stages are one credit: nothing is summed (2,000 at each stage, 6,000 left of the 8,000 invoice).
    assert Decimal(view['ledger']['bill']['original_amount']) - Decimal(view['ledger']['applied']) == Decimal('6000.00')

    # The Northwind case is untouched: same clock, same stage, same next decision.
    northwind = setup.checked(client.get('/api/workspace/workflow', headers=actor.headers))['workflow']
    assert (northwind['as_of'], northwind['claim']['state'], northwind['next_actions'][0]['label']) == (
        northwind_before['as_of'], northwind_before['claim']['state'], 'Approve January claim')
    row = next(o for o in northwind['opportunities'] if o.get('source') == 'template')
    assert row['claim'] == dict(row['claim'], stage='applied', amount='2000.00', next=None)

    # A second application is refused: the ledger action is no longer offered, and a direct retry records nothing.
    case = app.state.template_claims.cases['halcyon-a']
    from uptime.contracts import Principal
    reviewer = Principal('bears', actor.subject, 'reviewer')
    before = case.bench.allocations.bill_balance('bears', case.bill_id)
    case.bench.act(reviewer, case.claim_id, 'apply-balance')  # an exact completed action may be retried, never repeated
    assert case.bench.allocations.bill_balance('bears', case.bill_id) == before
    with database(case.provider.path) as db:
        assert db.execute("SELECT count(*) FROM local_ledger_record WHERE kind='application'").fetchone()[0] == 1
    assert press(client, actor, 'action-' + '0' * 64).status_code == 409


def test_each_decision_is_refused_out_of_order(served):
    from uptime.contracts import Principal
    app, client, actor = served
    connect(app, [entry()])
    reviewer = Principal('bears', actor.subject, 'reviewer')
    decisions = ('approve-claim', 'approve-response', 'record-credit', 'apply-balance')

    def refused_except(allowed):
        # Every later decision is refused by the domain; an earlier one is refused or is an exact retry: nothing changes.
        case = app.state.template_claims.cases['halcyon-a']
        before = read(client, actor)
        for operation in decisions:
            if decisions.index(operation) > decisions.index(allowed):
                with pytest.raises((ValueError, PermissionError)):
                    case.bench.act(reviewer, case.claim_id, operation)
            elif operation != allowed:
                try:  # an earlier decision: refused, or an exact retry of the completed action
                    case.bench.act(reviewer, case.claim_id, operation)
                except (ValueError, PermissionError):
                    pass
            after = read(client, actor)
            assert (stages(after), after['claim']['state'], len(after['automation']['steps'])) == (
                stages(before), before['claim']['state'], len(before['automation']['steps']))

    first = read(client, actor)['next_actions'][0]
    assert press(client, actor, 'action-' + 'f' * 64).status_code == 409  # nothing but the offered opening
    view = None
    view = decide(client, actor)                      # 1 approve the claim
    refused_except('approve-response')
    second = view['next_actions'][0]
    view = decide(client, actor)                      # 2 approve the response
    refused_except('record-credit')
    view = decide(client, actor)                      # 3 post
    refused_except('apply-balance')
    # A decision already taken is an exact retry: it records nothing and moves nothing.
    steps = len(view['automation']['steps'])
    for stale in (first['id'], second['id']):
        assert press(client, actor, stale).status_code == 200
        assert len(read(client, actor)['automation']['steps']) == steps
    assert stages(read(client, actor))['applied'] == '0.00'
    view = decide(client, actor)                      # 4 apply
    assert stages(view)['applied'] == '2000.00'


def test_an_approval_is_refused_when_the_content_changed(served):
    app, client, actor = served
    connect(app, [entry()])
    shown = read(client, actor)['next_actions'][0]
    # A newer reading of the same contract arrives before the reviewer presses: the approval shown no longer matches.
    app.state.template_builds.entries.append(entry(reading_id='rd_a2', read_at='2026-11-10T13:09:00Z'))
    assert press(client, actor, shown['id']).status_code == 409
    assert not (app.state.template_claim_inputs['directory'] / 'template-claims' / 'halcyon-a').exists()
    view = decide(client, actor)  # the current reading's approval is accepted
    assert view['reading']['reading_id'] == 'rd_a2'
    # The response approval is bound to the exact claim state it was shown on: a later signed record voids it.
    shown = view['next_actions'][0]
    case = app.state.template_claims.cases['halcyon-a']
    status = case.month_events()[0][1]
    import asyncio
    asyncio.run(case.deliver(case.claim_id, status.model_copy(update={'event_id': 'halcyon-status-2026-10-resent'})))
    assert press(client, actor, shown['id']).status_code == 409
    again = read(client, actor)['next_actions'][0]
    assert again['id'] != shown['id'] and again['label'] == shown['label']
    assert stages(read(client, actor))['awarded'] == '0.00'


def test_a_misread_term_fails_the_controls_and_opens_nothing(served):
    app, client, actor = served
    # A template that read the second tier as 15% (the contract says 25%) still estimates a credit, but the controls
    # authored from the contract refuse those terms, so nothing is installed and no claim is opened.
    connect(app, [entry(dict(EXPECTED['terms'], tier_2_credit_percent='15'))])
    view = read(client, actor)
    assert stages(view)['estimated'] == '1200.00'
    response = press(client, actor, view['next_actions'][0]['id'])
    assert response.status_code == 409 and 'controls' in response.json()['detail']
    assert not (app.state.template_claim_inputs['directory'] / 'template-claims' / 'halcyon-a').exists()
    assert read(client, actor)['claim']['state'] == 'NOT_OPENED'


def test_the_reading_is_marked_only_when_a_claim_can_be_opened(served):
    app, client, actor = served
    connect(app, [])
    on_reading = app.state.template_builds.on_reading
    assert on_reading(entry())['claim'] == {'available': True, 'case': 'halcyon-a'}
    # halcyon-c has an estimate but no claim evidence: no marker, so the build page shows no claim link.
    other = entry()
    other['document'] = {'id': 'halcyon-c', 'title': 'Halcyon Grid: Platform Availability Addendum (Brightwater)', 'customer': 'Brightwater Freight Co.'}
    other['values'] = json.loads((tc.CONTRACTS / 'expected.json').read_text())['halcyon-c']['terms']
    marked = on_reading(other)
    assert marked['credit']['stage'] == 'ESTIMATED' and 'claim' not in marked
    # A read that reaches no credit is not marked either.
    assert 'claim' not in on_reading(entry(dict(EXPECTED['terms'], measurement_period='calendar_quarter')))
