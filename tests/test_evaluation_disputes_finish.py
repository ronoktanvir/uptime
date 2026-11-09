"""Actual signed-route setup for the additive runner, without provider calls or holdouts."""
from hashlib import sha256
import json

import pytest

from scripts import evaluate_disputes_finish as runner
from test_v4_routes_integration import TEXT, SMALL, INTERVAL, SCOPE
from test_correspondence_interpretation import meaning


def inputs(tmp_path):
    text = 'The submitted chronology needs a fresh technical explanation.'
    scope = {k: v for k, v in SCOPE.items() if k not in ('component', 'region')}
    overlay = {k: SMALL[k] for k in ('agreement', 'account', 'product', 'plan', 'fee_line_ref')}
    overlay.update(currency='USD', effective_from='2026-01-01', effective_until='2026-12-31')
    prepared = {
        'schema': 'supplementary-dispute-setup/1', 'authority': 'SCRIPTED_NOT_ACTUAL_HUMAN',
        'case_id': 'authored-runner-control', 'filing_clock': '2026-11-03T00:00:00Z',
        'vendor_slot': 'authored-runner-vendor',
        'candidate': {'document': {'name': 'Public runner control', 'uri': 'urn:synthetic:runner-control',
                                   'classification': 'synthetic_public', 'text': TEXT}, 'overlay': overlay},
        'setup_tests': [
            {'name': 'Qualified source setup', 'facts': SMALL, 'expected': {'outcome': 'ELIGIBLE', 'amount': '52.17'}},
            {'name': 'Threshold setup', 'facts': SMALL | {'eligible_downtime_minutes': 44}, 'expected': {'outcome': 'INELIGIBLE'}},
        ],
        'claim': {'claim_id': 'inbox-authored-runner', 'scope': scope},
        'evidence': [
            {'event_id': 'control-status', 'role': 'status', 'body': {'kind': 'status', **INTERVAL}},
            {'event_id': 'control-impact', 'role': 'customer', 'body': {'kind': 'impact', 'affected': True, 'exclusion': 'none', **INTERVAL}},
            {'event_id': 'control-invoice', 'role': 'billing', 'body': {'kind': 'invoice', 'lines': [{'id': 'monthly-store', 'kind': 'affected_api', 'amount': '417.36'}]}},
            {'event_id': 'control-coverage', 'role': 'status', 'body': {'kind': 'coverage', 'start': '2026-10-01T00:00:00Z', 'end': '2026-11-01T00:00:00Z', 'complete': True, 'exclusions_removed': True, 'incident_ids': [scope['incident']], 'total_eligible_minutes': 45}},
        ],
        'reply': {'text': text},
    }
    paths = tmp_path / 'prepared.json', tmp_path / 'blind.json'
    paths[0].write_text(json.dumps(prepared))
    paths[1].write_text(json.dumps({'reply_sha256': sha256(text.encode()).hexdigest(),
                                  'interpretation': meaning(text, family='unsupported').model_dump()}))
    pins = {str(p): sha256(p.read_bytes()).hexdigest() for p in paths}
    return paths, pins


def test_unconfigured_provider_is_separate_from_successful_signed_setup(tmp_path, monkeypatch):
    from uptime import public_proposal_config
    monkeypatch.setattr(public_proposal_config, 'open_public_jobs', lambda *a: None)
    paths, pins = inputs(tmp_path)
    report = runner.run_case(prepared_path=paths[0], blind_path=paths[1], attempt_dir=tmp_path / 'attempt',
                             config_path=tmp_path / 'unused-config', approved_by='scripted-evaluation-operator', expected_pins=pins)
    assert report['outcome'] == 'SETUP_REFUSAL'
    assert report['error'] == 'no_exact_public_request'
    assert report['model_dispatched'] is False
    names = [r['name'] for r in report['steps']]
    assert 'scripted_activate' in names and 'submit-claim' in names and 'vendor_reply' in names
    assert 'scripted_source_reading' in names
    assert all(r['http_status'] == 200 for r in report['steps'])
    assert report['external_actions'] == [] and report['gold_read'] is False
    with pytest.raises(FileExistsError):
        runner.run_case(prepared_path=paths[0], blind_path=paths[1], attempt_dir=tmp_path / 'attempt',
                        config_path=tmp_path / 'unused-config', approved_by='scripted-evaluation-operator', expected_pins=pins)


def test_tampered_source_reading_never_creates_an_attempt(tmp_path):
    paths, pins = inputs(tmp_path)
    paths[1].write_text('{}')
    with pytest.raises(ValueError, match='changed'):
        runner.run_case(prepared_path=paths[0], blind_path=paths[1], attempt_dir=tmp_path / 'attempt',
                        config_path=tmp_path / 'unused-config', approved_by='scripted-evaluation-operator', expected_pins=pins)
    assert not (tmp_path / 'attempt').exists()


@pytest.mark.parametrize('project', [False, True])
def test_real_queue_records_one_controlled_candidate_without_financial_changes(tmp_path, monkeypatch, project):
    """Real signed app/queue, explicit provider double; this is not inference evidence."""
    from uptime import public_proposal_config
    from uptime.public_proposal_jobs import PublicProposalJobs
    from test_correspondence_blocks_71 import Provider, P, annotate
    paths, pins = inputs(tmp_path)
    if project:
        prepared = json.loads(paths[0].read_bytes())
        prepared['review_mode'] = 'scripted_source_projection'
        paths[0].write_text(json.dumps(prepared))
        pins[str(paths[0])] = sha256(paths[0].read_bytes()).hexdigest()
    text = json.loads(paths[0].read_bytes())['reply']['text']
    provider = Provider(json.dumps(annotate(text, ('substantive', [P('time_bar')]))),
                        profile={'name': 'controlled-runner-test', 'retry_count': 0})
    protected = tmp_path / 'protected'
    protected.mkdir(mode=0o700)
    approvals = protected / 'approvals.json'
    approvals.write_text(json.dumps({'version': 1, 'limits': {'daily_jobs': 2, 'daily_budget_usd': '2.00'}, 'approvals': []}))
    approvals.chmod(0o600)
    config = protected / 'config.json'
    config.write_text(json.dumps({'version': 1, 'executable': '/unused-controlled-provider',
                                 'approvals_path': str(approvals), 'kinds': ['correspondence']}))
    config.chmod(0o600)
    monkeypatch.setattr(public_proposal_config, 'open_public_jobs',
                        lambda db, _: PublicProposalJobs(db, approvals, {'correspondence': provider}))
    report = runner.run_case(prepared_path=paths[0], blind_path=paths[1], attempt_dir=tmp_path / 'attempt',
                             config_path=config, approved_by='scripted-evaluation-operator', expected_pins=pins)
    assert report['outcome'] == 'CANDIDATE_RECORDED', report
    assert len(provider.calls) == 1 and report['model_dispatched'] is True
    assert report['dispatch']['state_unchanged'] is True
    if project:
        assert report['review_action'] == 'SCRIPTED_SOURCE_PROJECTION_NOT_MODEL_ACCEPTANCE'
        assert report['source_projection']['prepare_allowed'] is False
        assert report['case']['ledger']['awarded'] == '0.00'
    else:
        assert report['review_action'] == 'NOT_PERFORMED'
    assert report['external_actions'] == [] and report['gold_read'] is False
