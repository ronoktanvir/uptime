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


@pytest.mark.parametrize('project,family,continue_local', [(False, 'unsupported', False), (True, 'unsupported', True), (True, 'time_bar', True), (True, 'time_bar_late', True)])
def test_real_queue_records_one_controlled_candidate_without_financial_changes(tmp_path, monkeypatch, project, family, continue_local):
    """Real signed app/queue, explicit provider double; this is not inference evidence."""
    from uptime import public_proposal_config
    from uptime.public_proposal_jobs import PublicProposalJobs
    from test_correspondence_blocks_71 import Provider, P, annotate
    paths, pins = inputs(tmp_path)
    if project:
        prepared = json.loads(paths[0].read_bytes())
        prepared['review_mode'] = 'scripted_source_projection'
        prepared['local_continuation'] = continue_local
        prepared['continuation_clock'] = '2026-11-04T00:00:00Z'
        if family in {'time_bar', 'time_bar_late'}:
            prepared['reply']['text'] = 'Our intake timestamp fell outside the permitted filing interval.'
            text = prepared['reply']['text']
            paths[1].write_text(json.dumps({'reply_sha256': sha256(text.encode()).hexdigest(),
                                          'interpretation': meaning(text, family='time_bar').model_dump()}))
            pins[str(paths[1])] = sha256(paths[1].read_bytes()).hexdigest()
            if family == 'time_bar_late':
                prepared['filing_clock'] = '2026-11-20T00:00:00Z'
                prepared['continuation_clock'] = '2026-11-21T00:00:00Z'
                prepared['original_filing'] = {'kind': 'original_filing_receipt', 'source_ref': 'control-observed-filing',
                    'observed_at': '2026-11-20T00:00:00Z', 'received_at': '2026-11-15T12:00:00Z',
                    'receipt_id': 'control-late-receipt', 'submitted_to': 'local-support', 'fields': []}
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
    if family == 'time_bar_late':
        # Current application accepts observed historical receipts only for the
        # reviewed resource-month family. Preserve that ordinary setup refusal.
        assert report['outcome'] == 'SETUP_REFUSAL' and report['error'] == 'authored_historical_receipt'
        assert report['model_dispatched'] is False and provider.calls == []
        assert 'resource-month' in report['steps'][-1]['body']['detail']
        assert not any(s['name'] == 'submit-claim' for s in report['steps'])
        return
    assert report['outcome'] == 'CANDIDATE_RECORDED', report
    assert len(provider.calls) == 1 and report['model_dispatched'] is True
    assert report['dispatch']['state_unchanged'] is True
    if project:
        assert report['review_action'] == 'SCRIPTED_SOURCE_PROJECTION_NOT_MODEL_ACCEPTANCE'
        if family == 'unsupported':
            assert report['source_projection']['prepare_allowed'] is False
            assert report['continuation'] == 'NO_PERMITTED_LOCAL_CONTINUATION'
        else:
            assert report['source_projection']['prepare_allowed'] is True
            if family == 'time_bar_late':
                assert report['continuation'] == 'SCRIPTED_LOCAL_DENIAL_CLOSURE'
                assert report['case']['stage'] == 'DENIAL_ACCEPTED'
                assert report['case']['submissions'] == []
            else:
                assert report['continuation'] == 'LOCAL_RESPONSE_RECEIPT_ONLY'
                assert len(report['case']['submissions']) == 2
        assert report['case']['ledger']['awarded'] == '0.00'
    else:
        assert report['review_action'] == 'NOT_PERFORMED'
    assert report['external_actions'] == [] and report['gold_read'] is False


def test_late_terminal_readback_after_drain_is_recorded_without_redispatch(tmp_path):
    from scripts.dispute_runtime_finish import dispatch_model_job, canonical, digest
    request = {'public': 'authored control'}
    request_hash = digest(canonical(request))
    context = 'c' * 64
    blind = {'reading': 'frozen'}
    state = {'drained': False, 'posts': 0}
    class Response:
        status_code = 200
        def __init__(self, body): self.body = body
        def json(self): return self.body
    class Client:
        def get(self, url):
            if '/model-jobs/' in url:
                return Response({'id': 'job', 'state': 'SUCCEEDED' if state['drained'] else 'RUNNING',
                                 'terminal': state['drained'], 'request_sha256': request_hash, 'context_digest': context})
            candidate = {'id': 'candidate', 'provenance': {'request_sha256': request_hash}}
            return Response({'context': {'digest': context}, 'blind_entry': blind,
                'candidates': [candidate] if state['drained'] else [],
                'model_job': {'can_request': True, 'request_sha256': request_hash,
                             'approval_request': {'context_sha256': context, 'request': request}}})
        def post(self, url, body):
            state['posts'] += 1
            return Response({'id': 'job'})
    result = dispatch_model_job(Client(), '/claim', expected_context_digest=context,
        frozen_request=request, expected_request_sha256=request_hash, pinned_blind=blind,
        read_state=lambda: {'money': '0.00'}, folder=tmp_path / 'dispatch', poll_seconds=0,
        drain=lambda: state.update(drained=True))
    assert state['posts'] == 1
    assert result['poll_deadline_reached'] is True and result['poll_job']['state'] == 'RUNNING'
    assert result['job']['state'] == 'SUCCEEDED' and result['outcome'] == 'CANDIDATE_RECORDED'
    assert result['verified_candidate']['id'] == 'candidate' and result['state_unchanged'] is True
