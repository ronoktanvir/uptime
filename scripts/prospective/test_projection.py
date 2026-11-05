"""Fresh synthetic protocol controls; no frozen original inputs or oracle reads."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.prospective.projection import fingerprint, overlay_for, project_case, public_join, sha
from scripts.prospective import witness


TEXT = '''Agreement: Synthetic Navigation Schedule
Version TEST-2030. Fictional material.
Provider supplies Wayfinding on the Coastal plan.
From 2030-06-01T00:00:00Z inclusive to 2030-07-01T00:00:00Z exclusive.
'''
PRIVATE = dict(public_sla_version='TEST-2030', account_id='synthetic-account', service='Wayfinding', plan='Coastal',
               period=dict(start='2030-06-01T00:00:00Z', end='2030-07-01T00:00:00Z', minutes='43200'))


def receipt():
    lines = TEXT.splitlines()
    proposal = [dict(quote=lines[0], value={'agreement': 'Synthetic Navigation Schedule'}),
                dict(quote=lines[2], value={'scope': {'product': 'Wayfinding', 'plan': 'Coastal'}}),
                dict(quote=lines[3], value={'fixed_period': {k: PRIVATE['period'][k] for k in ('start', 'end')}})]
    return dict(source_sha256=sha(TEXT.encode()), proposal=proposal, proposal_sha256=fingerprint(proposal))


def sample(tmp_path, *, complete=None, down='61', extra_lines=None):
    overlay = overlay_for(PRIVATE, public_join(PRIVATE, TEXT, receipt()))
    shared = dict(account_id=PRIVATE['account_id'], service=PRIVATE['service'], plan=PRIVATE['plan'],
                  period=PRIVATE['period'], recorded_at='2030-07-02T00:00:00Z', source_label='SYNTHETIC_CUSTOMER')
    if complete is not None:
        shared['complete'] = complete
    monitor = dict(shared, source_id='synthetic-monitor', unavailable_minutes=down)
    invoice = dict(shared, source_id='synthetic-invoice', paid=True, lines=[
        dict(service=PRIVATE['service'], description='Recurring subscription', amount_usd='125.01'),
        dict(service='Orientation', description='orientation charges', amount_usd='35.00'),
    ] + (extra_lines or []))
    case = dict(id='disposable', period=PRIVATE['period'], filing_at='2030-07-03T00:00:00Z',
                invoice_path='invoice.json', status_path='status.json')
    for name, value in [('invoice.json', invoice), ('status.json', monitor)]:
        (tmp_path / name).write_text(json.dumps(value))
    hashes = {p.name: sha(p.read_bytes()) for p in tmp_path.glob('*.json')}
    manifest = dict(fixed_period={k:PRIVATE['period'][k] for k in ('start', 'end')}, fee_exclusions=['orientation fees'])
    return case, overlay, manifest, hashes


def project(tmp_path, **kwargs):
    case, overlay, manifest, hashes = sample(tmp_path, **kwargs)
    return project_case(tmp_path, case, overlay, manifest, hashes)


def test_exact_public_title_version_join_preserves_original_agreement():
    joined = public_join(PRIVATE, TEXT, receipt())
    overlay = overlay_for(PRIVATE, joined)
    assert overlay['agreement'] == 'TEST-2030'
    assert overlay['public_agreement'] == 'Synthetic Navigation Schedule'
    assert joined['provider_confirmed_private_identity'] is False


@pytest.mark.parametrize('changed', [dict(public_sla_version='TEST-2029'), dict(plan='Other'), dict(service='Unknown'),
    dict(period=PRIVATE['period'] | {'minutes': '44640'})])
def test_substantive_version_plan_and_denominator_mismatch_cannot_be_repaired(changed):
    with pytest.raises(ValueError):
        public_join(PRIVATE | changed, TEXT, receipt())


def test_changed_public_receipt_or_multiple_versions_refuse():
    with pytest.raises(ValueError, match='digest'):
        public_join(PRIVATE, TEXT + 'revision', receipt())
    r = receipt()
    r['proposal'][0]['value']['agreement'] = 'Other'
    with pytest.raises(ValueError, match='digest'):
        public_join(PRIVATE, TEXT, r)
    text = TEXT + 'Version TEST-2031. Fictional material.\n'
    r = receipt() | {'source_sha256': sha(text.encode())}
    with pytest.raises(ValueError, match='one exact'):
        public_join(PRIVATE, text, r)


def test_missing_completeness_and_receipt_are_not_invented(tmp_path):
    projected = project(tmp_path)
    assert not projected['facts']['service_monitor']['complete']
    assert not projected['facts']['service_invoice']['complete']
    assert 'filing_proof' not in projected['facts']
    assert [i['code'] for i in projected['issues']].count('MISSING_COMPLETE_ATTESTATION') == 2
    assert all(p['provider_confirmed'] is False for p in projected['provenance'])


def test_exact_units_line_aliases_and_hashes_preserve_evidence(tmp_path):
    projected = project(tmp_path, complete=True, down='43.21')
    monitor = projected['facts']['service_monitor']
    invoice = projected['facts']['service_invoice']
    assert monitor['content']['unavailable_minutes'] == '43.21'
    assert invoice['content']['lines'][0]['amount_cents'] == 12501
    assert invoice['content']['lines'][1]['category'] == 'orientation fees'
    assert invoice['content']['lines'][1]['ref'] != invoice['content']['lines'][0]['ref']
    assert invoice['content_sha256'] == fingerprint(invoice['content'])
    assert 'FRACTIONAL_MINUTES_UNSUPPORTED' in {i['code'] for i in projected['issues']}


def test_missing_artifact_is_not_filled_from_reported_case_amount(tmp_path):
    case, overlay, manifest, hashes = sample(tmp_path)
    case.update(invoice_path=None, reported_subscription_usd='9999.99')
    projected = project_case(tmp_path, case, overlay, manifest, hashes)
    assert 'service_invoice' not in projected['facts']


def test_source_scope_conflict_survives_projection_and_hash_tamper_refuses(tmp_path):
    case, overlay, manifest, hashes = sample(tmp_path)
    path = tmp_path / 'status.json'
    original = json.loads(path.read_text()) | {'account_id': 'other-account'}
    path.write_text(json.dumps(original))
    with pytest.raises(ValueError, match='changed'):
        project_case(tmp_path, case, overlay, manifest, hashes)
    hashes['status.json'] = sha(path.read_bytes())
    projected = project_case(tmp_path, case, overlay, manifest, hashes)
    assert projected['facts']['service_monitor']['account'] == 'other-account'
    assert 'SOURCE_SCOPE_MISMATCH' in {i['code'] for i in projected['issues']}


def test_unclassified_fees_and_duplicate_subscription_lines_remain_gaps(tmp_path):
    projected = project(tmp_path, extra_lines=[dict(service='Other', description='unknown charge', amount_usd='4.999'),
                                              dict(service=PRIVATE['service'], description='Subscription', amount_usd='2.00')])
    assert {'UNCLASSIFIED_FEE', 'FRACTIONAL_CENT_UNSUPPORTED', 'AMBIGUOUS_SUBSCRIPTION_LINE'} <= {i['code'] for i in projected['issues']}
    assert projected['facts']['service_invoice']['content']['lines'][2]['amount_cents'] == '499.900'
    assert projected['facts']['service_invoice']['verified'] is False


@pytest.mark.parametrize('changes,code', [
    ({'monthly_subscription_usd': '999.00'}, 'SOURCE_FEE_SUMMARY_MISMATCH'),
    ({'recorded_at': '2030-06-30T23:59:59Z'}, 'SOURCE_CHRONOLOGY_GAP'),
    ({'recorded_at': '2030-07-04T00:00:00Z'}, 'SOURCE_CHRONOLOGY_GAP'),
])
def test_source_fee_and_chronology_conflicts_cannot_be_verified(tmp_path, changes, code):
    case, overlay, manifest, hashes = sample(tmp_path, complete=True)
    path = tmp_path / 'invoice.json'
    path.write_text(json.dumps(json.loads(path.read_text()) | changes))
    hashes['invoice.json'] = sha(path.read_bytes())
    projected = project_case(tmp_path, case, overlay, manifest, hashes)
    invoice = projected['facts']['service_invoice']
    assert invoice['verified'] is False
    assert invoice['content']['lines'][0]['amount_cents'] == 12501
    assert code in {i['code'] for i in projected['issues']}


def test_sealed_public_controls_signed_mounted_api_activation(tmp_path, monkeypatch):
    """A newly authored control uses the published protocol, never original gold."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests'))
    from test_vendor_service_month import ROWS, OVERLAY
    from uptime.vendor_model import MODEL
    from uptime.server import create_app
    from fastapi.testclient import TestClient
    rows = [('Agreement: Navigation subscription test', {'agreement': 'Navigation subscription test'}),
            ('Version Compass-7. Fictional test material.', {'nonmaterial': 'Source version.'})] + deepcopy(ROWS)
    proposal = [dict(quote=q, field='resource_terms', value=v) for q,v in rows]
    document = dict(name='Disposable public scenario', classification='synthetic_public', uri='urn:synthetic:control',
                    text='\n'.join(q for q,v in rows))
    capture = dict(model=MODEL, source_sha256=sha(document['text'].encode()), session='scripted-test-not-real-provider',
                   at='2027-03-01T00:00:00Z', proposal=proposal, proposal_sha256=fingerprint(proposal))
    (tmp_path / (capture['source_sha256'] + '.json')).write_text(json.dumps(capture))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS', str(tmp_path))
    monkeypatch.setenv('UPTIME_MODEL_PROPOSITIONS', '1')
    overlay = OVERLAY | {'public_agreement': 'Navigation subscription test'}
    database, origin = tmp_path/'app.sqlite', 'http://127.0.0.1:8765'
    app = create_app(database, rehearsal=False, approvals_enabled=True, tenant='test-tenant', origin=origin)
    with TestClient(app, base_url=origin, client=('127.0.0.1', 45100)) as client:
        reviewer = witness.enrolled_reviewer(client, origin, database, 'synthetic.projection.test', 'test-tenant')
        journal = witness.Journal(tmp_path)
        installed, state = witness.onboard(reviewer, journal, '/api/vendors/test-control', document,
                                           overlay, capture, tmp_path, 'control')
        assert installed['active'], installed
        # Normal named-key enrollment uses this product label. The harness separately
        # records SCRIPTED_TEST/human_approval=False and never claims a real human.
        assert state['reviewer_kind'] == 'authenticated_reviewer'
        assert all(a['human_approval'] is False for a in installed['actions_taken'])
        assert all(row['passed'] for row in installed['checks'])
        witness.check_seal(tmp_path, 'public-controls-control-seal.json')
        # Authentic private-schema incompleteness is still refused after activation.
        facts = witness.public_controls(state['manifest'], overlay)[0]['facts']
        facts['service_monitor']['complete'] = False
        response = reviewer.post('/api/vendors/test-control/evaluate', {'facts': facts})
        assert response.status_code == 200
        assert response.json()['outcome'] == 'INSUFFICIENT_EVIDENCE'
        assert 'Complete verified record required' in response.json()['trace'][0]
