"""Demo line (November 10): setup_northwind.py --model-jobs prepares live Claude readings of the authored samples.

A simulated transport stands in for the Claude Code CLI: it returns the recorded Corvid Ledger reading for the
monthly family and an unusable answer for the resource family. No model is called and no credential is read.
"""
import json
from pathlib import Path
import stat
import time

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
RECORDED = json.loads((ROOT / 'docs/v4/evidence/submission-onboarding-20261109/corvid-ledger-initial.json').read_text())
CORVID = json.loads((ROOT / 'fixtures/submission_onboarding/corvid_ledger.json').read_text())


class SimulatedTransport:
    """The provider interface of SafePublicClaude, without a process or a network."""
    def __init__(self, executable):
        from uptime.vendor_model import MODEL, VENDOR_SYSTEM
        self.executable, self.model, self.system = executable, MODEL, VENDOR_SYSTEM
        self.profile = {'name': 'simulated-demo-transport', 'revision': 1}
        self.last_receipt, self.calls = None, []

    def __call__(self, request):
        profile = json.loads(request)['profile']
        self.calls.append(profile)
        clauses = RECORDED['jobs']['monthly-availability/1']['proposal']['clauses']
        if profile == 'monthly-propositions':
            text = json.dumps({'clauses': clauses})
        else:
            # A resource reading of the same blocks, as the recorded run attempted: refused by validation.
            from uptime.vendor_resource_terms import public_blocks
            by_quote = {c['quote']: c for c in clauses}
            values = []
            for block in public_blocks(CORVID['text']):
                clause = by_quote.get(block['text'])
                values.append({'nonmaterial': 'table row'} if clause is None or clause['value'] is None
                              else {clause['field']: clause['value']})
            text = json.dumps({'blocks': [{'id': b['id'], 'value': v} for b, v in zip(public_blocks(CORVID['text']), values)]})
        return {'model': self.model, 'session': 'simulated-session-not-a-model', 'text': text}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    import scripts.setup_northwind as setup
    from uptime import vendor_model_jobs
    transports = []

    def build(executable):
        transports.append(SimulatedTransport(executable))
        return transports[-1]
    monkeypatch.setattr(vendor_model_jobs, 'build_vendor_provider', build)
    directory = tmp_path.resolve() / 'ws'
    setup.prepare(directory, 'http://127.0.0.1:8797')
    return setup, directory, transports


def test_model_jobs_writes_private_config_and_exact_sample_approvals(workspace):
    setup, directory, _ = workspace
    prepared = setup.prepare_model_jobs(directory, '/usr/bin/true')
    folder = directory / 'model-jobs'
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    for name in ('config.json', 'approvals.json'):
        assert stat.S_IMODE((folder / name).stat().st_mode) == 0o600
    config = json.loads((folder / 'config.json').read_text())
    # The configuration records the resolved path; on some Linux images /usr/bin/true is a link to another file.
    assert config == {'version': 1, 'executable': str(Path('/usr/bin/true').resolve()),
                      'approvals_path': str(folder / 'approvals.json'), 'kinds': ['vendor']}
    approvals = json.loads((folder / 'approvals.json').read_text())
    assert prepared['approved_requests'] == len(approvals['approvals']) == 18
    assert {a['target'] for a in approvals['approvals']} == {'corvid-ledger', 'halden-relay', 'halden-relay-control'}
    assert {a['subject'] for a in approvals['approvals']} == {'scripted-test-reviewer'}
    assert {a['approved_by'] for a in approvals['approvals']} == {'workspace operator (setup_northwind.py --model-jobs)'}
    assert {a['request']['attempt_nonce'] for a in approvals['approvals']} == {'retry-take1', 'retry-take2', 'retry-take3'}
    # Running it again at the next start-up renews the same approvals rather than adding more.
    setup.prepare_model_jobs(directory, '/usr/bin/true')
    assert len(json.loads((folder / 'approvals.json').read_text())['approvals']) == 18


def test_a_missing_executable_is_refused_before_anything_is_written(workspace):
    setup, directory, _ = workspace
    with pytest.raises(setup.WorkspaceRefused, match='--claude-executable'):
        setup.prepare_model_jobs(directory, None)
    assert not (directory / 'model-jobs').exists()


def test_served_walkthrough_runs_a_sample_reading_through_the_real_job_service(workspace):
    from uptime.auth import SCRIPT
    from uptime.auth_client import ReviewerClient
    setup, directory, transports = workspace
    prepared = setup.prepare_model_jobs(directory, '/usr/bin/true')
    app, private, _ = setup.open_workspace(directory, proposal_config=Path(prepared['config']))
    base = '/api/vendors/corvid-ledger'
    body = {'document': CORVID, 'profile': 'auto', 'attempt_nonce': 'retry-take1'}
    with TestClient(app, base_url=private['origin'], client=('127.0.0.1', 4511)) as client:
        reviewer = ReviewerClient(client, private['origin'], SCRIPT, private['rehearsal_secret'])
        before = reviewer.post(base + '/proposal-access', body).json()
        assert before['outcome'] == 'NOT_SUBMITTED'
        submitted = reviewer.post(base + '/proposal-jobs', body).json()
        jobs = [f['job']['job_id'] for f in submitted['families']]
        assert len(jobs) == 2
        for _ in range(300):
            states = [client.get(base + '/proposal-jobs/' + j, headers=reviewer.headers).json()['status'] for j in jobs]
            if all(s not in ('QUEUED', 'RUNNING') for s in states):
                break
            time.sleep(.02)
        after = reviewer.post(base + '/proposal-access', body).json()
        assert after['outcome'] == 'SELECTED' and after['selected']['method'] == 'public_proposal_job', json.dumps(
            [(f['family'], f['state'], (f.get('job') or {}).get('status'), (f.get('job') or {}).get('reason'), f.get('refusal')) for f in after['families']])[:1500]
        job = client.get(base + '/proposal-jobs/' + after['selected']['job_id'], headers=reviewer.headers).json()
        assert job['status'] == 'SUCCEEDED' and job['proposal']['model'] == 'claude-opus-5-5'
        assert job['submitted_at'] and job['started_at'] and job['finished_at']
        clauses = job['proposal']['clauses']
        assert clauses and all(c['quote'] in CORVID['text'] for c in clauses)
        refused = next(f for f in after['families'] if f['job']['job_id'] != job['job_id'])
        assert refused['job']['status'] == 'REFUSED'
        # A used take is never resent; an unapproved take is refused before any call.
        assert reviewer.post(base + '/proposal-jobs', body).json()['outcome'] == 'SELECTED'
        unapproved = reviewer.post(base + '/proposal-access', {**body, 'attempt_nonce': 'retry-take4'}).json()
        assert unapproved['outcome'] == 'APPROVAL_REQUIRED'
        # Nothing was staged or approved: there is no Corvid Ledger agreement.
        assert client.get(base, headers=reviewer.headers).status_code == 404
    served = transports[-1]
    assert sorted(served.calls) == ['monthly-propositions', 'resource-month']


@pytest.mark.parametrize('argv,message', [
    (['--model-jobs'], '--model-jobs requires --serve'),
    (['--claude-executable', '/usr/bin/true'], '--claude-executable applies with --model-jobs'),
    (['--serve', '--model-jobs', '--public-proposal-config', '/tmp/x.json'], 'leave out --public-proposal-config'),
])
def test_model_jobs_option_rules(tmp_path, monkeypatch, capsys, argv, message):
    import scripts.setup_northwind as setup
    monkeypatch.setattr('sys.argv', ['setup_northwind.py', '--directory', str(tmp_path / 'ws'), *argv])
    with pytest.raises(SystemExit):
        setup.main()
    assert message in capsys.readouterr().err
    assert not (tmp_path / 'ws').exists()
