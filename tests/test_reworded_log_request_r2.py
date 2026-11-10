"""The authored 'reworded-log-request' reply: unfamiliar wording, a reviewer's reading, the same walkthrough.

The reply is authored (fixtures/northwind/counterparty-variants.json) and the reviewer is scripted
(SCRIPTED_NOT_ACTUAL_HUMAN). No model is called here; the reviewer's own reading drives the bridge.
"""
from decimal import Decimal
import hashlib

from fastapi.testclient import TestClient
import pytest

from scripts import setup_northwind as setup
from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.correspondence_reason import propose

CLAIM = 'inbox-northwind-2026-01'
BASE = '/api/correspondence/claims/' + CLAIM
TEXT_SHA256 = 'a7dccd088968906b1045f0b16cb9de25245de2da3b856edc76f02b9fee674ac5'
UNCLEAR_TEXT_SHA256 = '9412f9036d3714197fae2fe5096ea8a02ff313ce9fb6d8be873ce32d41e2bb4c'  # recorded receipt context
OPENING = "We can't take this any further on the numbers alone."
DEFAULT_STEPS = [('approve-claim', 'PERSON'), ('submit-claim', 'APPROVED_OPERATION'), ('receive-denial', 'EVENT_INTAKE'),
                 ('receive-artifact', 'EVENT_INTAKE'), ('receive-verification', 'EVENT_INTAKE'), ('approve-response', 'PERSON'),
                 ('submit-response', 'APPROVED_OPERATION'), ('receive-award', 'EVENT_INTAKE'), ('record-credit', 'PERSON'),
                 ('receive-invoice', 'EVENT_INTAKE'), ('apply-balance', 'PERSON')]


def reworded_text():
    return setup.correspondence_for(setup.load_package(), 'reworded-log-request')['denial']['text']


def span(text, quote):
    start = text.index(quote)
    return dict(start=len(text[:start].encode()), end=len(text[:start + len(quote)].encode()), quote=quote)


def proposition(family, source, **changes):
    value = dict(family=family, source=source, polarity='positive', modality='asserted', referent='current_claim',
                 conditions=[], slots=[], artifact_type=None, scope_field=None, filing_fields=[])
    value.update(changes)
    return value


def log_request_reading(text):
    """The reviewer's own reading: one proposition, a request for the resource log NW-JAN-LOG-001."""
    whole = span(text, text)
    return dict(propositions=[proposition('artifact', whole, artifact_type='resource_log',
                                          slots=[dict(name='artifact_ref', source=span(text, 'NW-JAN-LOG-001'))])],
                segments=[dict(source=whole, role='substantive')])


def reading_with_unsupported_opening(text):
    rest = text[len(OPENING) + 1:]
    gap = dict(start=len(OPENING.encode()), end=len(OPENING.encode()) + 1, quote=' ')
    return dict(propositions=[proposition('artifact', span(text, rest), artifact_type='resource_log',
                                          slots=[dict(name='artifact_ref', source=span(text, 'NW-JAN-LOG-001'))]),
                              proposition('unsupported', span(text, OPENING))],
                segments=[dict(source=span(text, OPENING), role='unsupported'), dict(source=gap, role='courtesy'),
                          dict(source=span(text, rest), role='substantive')])


@pytest.fixture
def world(tmp_path):
    app, private, events = setup.prepare(tmp_path / 'ws', DEFAULT_ORIGIN, routine_automation=True,
                                         counterparty_reply='reworded-log-request')
    client = TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 1234), raise_server_exceptions=False)
    actor, _ = setup.seed(client, app, private, events)
    yield app, client, actor
    client.close()


def read(client, actor, path='/api/workspace/workflow'):
    return setup.checked(client.get(path, headers=actor.headers))


def post(actor, path, body):
    return setup.checked(actor.post(path, body))


def approve_and_reach_the_reply(client, actor):
    view = read(client, actor)['workflow']
    return post(actor, '/api/workspace/workflow/actions/' + view['next_actions'][0]['id'], {})['workflow']


def review(client, actor, reading, verdict='accept'):
    context = read(client, actor, BASE + '/interpretation')['context']
    body = dict(context_digest=context['digest'], interpretation=reading)
    post(actor, BASE + '/interpretation/blind-entry', body)
    rid = post(actor, BASE + '/interpretation/reviews', dict(**body, candidate_id=None, resolutions=[
        dict(proposition=i, verdict=verdict, explanation='Scripted review of the complete signed reply.')
        for i in range(len(reading['propositions']))], residuals_reviewed=True, complete_meaning_reviewed=True))['id']
    return rid, read(client, actor, BASE + '/interpretation/reviews/' + rid + '/preview')


def test_the_variant_is_recorded_unknown_to_the_fixed_rules_and_pauses_the_walkthrough(world):
    app, client, actor = world
    text = reworded_text()
    assert hashlib.sha256(text.encode()).hexdigest() == TEXT_SHA256
    assert propose(text, claimed=Decimal('2400.00'), scope_month='2026-01').reason == 'unknown'
    view = approve_and_reach_the_reply(client, actor)
    assert view['automation']['pause']['reason'] == 'UNEXPECTED_GROUND' and view['next_actions'] == []
    case = read(client, actor, BASE)
    assert case['stage'] == 'HUMAN_REVIEW' and case['replies'][-1]['reason'] == 'unknown'
    assert case['replies'][-1]['text'] == text


def test_the_reviewers_reading_carries_the_walkthrough_to_the_same_applied_credit(world):
    app, client, actor = world
    approve_and_reach_the_reply(client, actor)
    rid, preview = review(client, actor, log_request_reading(reworded_text()))
    assert preview['disposition'] == 'NEEDS_EVIDENCE' and preview['prepare_allowed'] and preview['ledger_unchanged']
    assert preview['external_actions'] == [] and preview['assertions']['category'] == 'MISSING_EVIDENCE'
    case = post(actor, BASE + '/interpretation/prepare-response', dict(review_id=rid, preview_digest=preview['digest']))
    assert case['stage'] == 'NEEDS_EVIDENCE'
    assert case['requested_artifact'] == {'type': 'resource_log', 'ref': 'NW-JAN-LOG-001'}
    clicked = []
    while (view := read(client, actor)['workflow'])['next_actions']:
        offer = view['next_actions'][0]
        clicked.append(offer['label'])
        post(actor, '/api/workspace/workflow/actions/' + offer['id'], {})
    assert clicked == ['Continue routine steps', 'Approve response', 'Post to Local ledger', 'Apply credit to eligible invoice']
    final = read(client, actor)['workflow']
    automation = final['automation']
    assert automation['state'] == 'COMPLETE' and automation['counts'] == dict(person_decisions=4, automatic_steps=7)
    assert [(s['operation'], s['authority']['kind']) for s in automation['steps']] == DEFAULT_STEPS
    assert all(s['authority'].get('actor') in (None, SCRIPT) for s in automation['steps'])
    ledger = final['ledger']
    assert ledger['claimed'] == ledger['awarded'] == ledger['posted'] == ledger['applied'] == '2400.00'
    assert (ledger['bill']['original_amount'], ledger['bill']['outstanding_amount']) == ('11000.00', '8600.00')
    first = read(client, actor, BASE)['replies'][0]
    assert first['reason'] == 'artifact' and first['reviewed_interpretation'] == rid


@pytest.mark.parametrize('variant', ['rejected', 'unsupported-segment'])
def test_a_rejected_or_unsupported_reading_keeps_the_case_in_review_without_money(world, variant):
    app, client, actor = world
    approve_and_reach_the_reply(client, actor)
    before = read(client, actor, BASE)
    text = reworded_text()
    reading = log_request_reading(text) if variant == 'rejected' else reading_with_unsupported_opening(text)
    rid, preview = review(client, actor, reading, verdict='reject' if variant == 'rejected' else 'accept')
    assert not preview['prepare_allowed'] and preview['ledger_unchanged']
    refused = actor.post(BASE + '/interpretation/prepare-response', dict(review_id=rid, preview_digest=preview['digest']))
    assert refused.status_code == 409
    after = read(client, actor, BASE)
    assert after['stage'] == 'HUMAN_REVIEW' and after['ledger'] == before['ledger'] and after['ledger']['awarded'] == '0.00'
    assert after['submissions'] == before['submissions'] and read(client, actor)['workflow']['next_actions'] == []


def test_the_default_and_unclear_replies_are_unchanged():
    package = setup.load_package()
    assert setup.correspondence_for(package, 'request-log') is package['correspondence']
    unclear = setup.correspondence_for(package, 'unclear')['denial']
    assert unclear['event_id'] == 'northwind-denial-jan-unclear'
    assert hashlib.sha256(unclear['text'].encode()).hexdigest() == UNCLEAR_TEXT_SHA256
