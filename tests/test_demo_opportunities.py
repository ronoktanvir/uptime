"""Demo line: Corvid Ledger's estimated credit comes from the installed agreement's own evaluator."""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from scripts import setup_northwind as setup
from uptime import demo_opportunities as demo
from uptime.auth import DEFAULT_ORIGIN
from uptime.contracts import fingerprint
from uptime.vendor_eval import evaluate
from uptime.vendor_model import verify_receipt
from uptime.vendor_terms import Document

RECORD = demo.ROOT / 'docs/v4/evidence/submission-onboarding-20261109/corvid-ledger-initial.json'


def recorded_manifest():
    package = demo.load()
    receipt = json.loads((demo.FIXTURES / 'extractions' / (fingerprint_source(package) + '.json')).read_text())
    return verify_receipt(Document.model_validate(package['document']), receipt, allow_propositions=True)


def fingerprint_source(package):
    from hashlib import sha256
    return sha256(package['document']['text'].encode()).hexdigest()


def test_receipt_is_the_recorded_model_reading_unchanged():
    record = json.loads(RECORD.read_text())
    job = record['jobs']['monthly-availability/1']
    package = demo.load()
    receipt = json.loads((demo.FIXTURES / 'extractions' / (fingerprint_source(package) + '.json')).read_text())
    assert job['status'] == 'SUCCEEDED' and job['provider']['model'] == 'claude-opus-5-5'
    assert receipt['proposal'] == job['proposal']['clauses']
    assert receipt['session'] == job['proposal']['session'] == job['provider']['session']
    assert receipt['proposal_sha256'] == job['proposal']['proposal_sha256'] == fingerprint(receipt['proposal'])
    manifest, extraction = recorded_manifest()
    assert extraction['method'] == 'tool_free_model_propositions' and manifest['agreement'] == 'CDC-SLA-07'


@pytest.fixture(scope='module')
def workspace(tmp_path_factory):
    app, private, events = setup.prepare(tmp_path_factory.mktemp('demo-company') / 'owned', DEFAULT_ORIGIN)
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 1234)) as client:
        actor, _ = setup.seed(client, app, private, events)
        yield app, client, actor


def view(client, actor):
    response = client.get('/api/workspace/workflow', headers=actor.headers)
    assert response.status_code == 200, response.text
    return response.json()['workflow']


def test_amount_is_the_engines_and_follows_the_usage(workspace, monkeypatch):
    app, client, actor = workspace
    manifest, _ = recorded_manifest()
    package = demo.load()
    engine = evaluate(manifest, package['overlay'], demo.facts(package), 'bears')
    assert engine['outcome'] == 'ELIGIBLE'
    workflow = view(client, actor)
    [row] = workflow['opportunities']
    assert row['amount'] == engine['amount'] and row['evaluation']['rate_units'] == engine['rate_units']
    assert (row['vendor'], row['period'], row['kind'], row['stage'], row['currency'], row['route']) == (
        'Corvid Data Cooperative', '2026-10', 'service_credit', 'ESTIMATED', 'USD', 'agreements')
    assert row['agreement']['read_by'] == 'claude-opus-5-5' and row['agreement']['id'] == 'CDC-SLA-07'
    assert row['agreement']['clause'] in package['document']['text']
    for cited in row['agreement']['citations']:
        assert package['document']['text'][cited['start']:cited['end']] == cited['quote']
    assert row['invoice'] == dict(id='CDC-2026-10-0117', vendor='Corvid Data Cooperative', total='10000.00', currency='USD',
                                  issued_on='2026-11-01', line=package['invoice']['lines'][0]['description'])

    # Different usage: a lower tier and a lower amount, both from the same evaluator.
    lighter = deepcopy(package); lighter['usage']['unavailable_minutes'] = 120
    monkeypatch.setattr(demo, 'load', lambda: deepcopy(lighter))
    [changed] = view(client, actor)['opportunities']
    expected = evaluate(manifest, lighter['overlay'], demo.facts(lighter), 'bears')
    assert changed['amount'] == expected['amount'] != row['amount']
    # No credit due: no opportunity row.
    clean = deepcopy(package); clean['usage']['unavailable_minutes'] = 0
    monkeypatch.setattr(demo, 'load', lambda: deepcopy(clean))
    assert view(client, actor)['opportunities'] == []


def test_estimate_opens_nothing_and_leaves_northwind_alone(workspace):
    app, client, actor = workspace
    workflow = view(client, actor)
    assert [m['amount'] for m in workflow['months']] == ['2400.00', None, None]
    assert workflow['vendor'] == 'Northwind Cloud' and workflow['claim']['month'] == '2026-01'
    assert '2000.00' not in json.dumps(workflow['finance']) and '4400.00' not in json.dumps(workflow)
    cases = client.get('/api/cases', headers=actor.headers)
    if cases.status_code == 200:
        assert 'corvid' not in cases.text.lower()
    vendor = client.get('/api/vendors/corvid-ledger', headers=actor.headers).json()
    assert vendor['state'] == 'ACTIVE' and vendor['extraction']['model'] == 'claude-opus-5-5'
