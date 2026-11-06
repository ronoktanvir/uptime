from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import sqlite3
from threading import Event, Lock
from time import monotonic

import pytest

from uptime.public_proposal_jobs import PublicProposalJobs, canonical, load_approvals

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


class Provider:
    def __init__(self, *, release=None, error=None):
        self.calls = []
        self.release = release
        self.started = Event()
        self.error = error
        self.lock = Lock()
        self.last_receipt = {'model': 'reported-test-model', 'raw_stdout_stored': False}

    def __call__(self, request):
        with self.lock:
            self.calls.append(request)
        self.started.set()
        if self.release is not None:
            assert self.release.wait(4)
        if self.error:
            raise self.error
        return {'text': 'an inert source-grounded proposal'}


def setup(tmp_path, *, requests=None, limits=None, provider=None, clock=None, **options):
    folder = tmp_path / 'operator'
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / 'approvals.json'
    request = canonical({'model': 'test', 'tools': [], 'input': 'Public text\n', 'attempt_nonce': 'initial', 'max_budget_usd': '1.00'})
    pins = dict(tenant='tenant-a', subject='reviewer-a', kind='vendor', target='vendor-a', context_sha256='a' * 64, request=request)
    entries = []
    for current in requests or [pins]:
        entries.append(dict(**{k: v for k, v in current.items() if k != 'request'}, request=json.loads(current['request']),
                            approved_by='engineering-operator', approved_at=(NOW-timedelta(minutes=1)).isoformat(),
                            expires_at=(NOW+timedelta(hours=1)).isoformat(),
                            source_references=[dict(reference='authored public fixture', sha256=sha256(b'Public text\n').hexdigest())]))
    path.write_text(json.dumps(dict(version=1, limits=limits or dict(daily_jobs=20, daily_budget_usd='20.00'), approvals=entries)))
    path.chmod(0o600)
    provider = provider or Provider()
    jobs = PublicProposalJobs(tmp_path / 'app.sqlite', path, {'vendor': provider}, clock=clock or (lambda: NOW), **options)
    return jobs, provider, pins, path


def done(jobs, pins, job):
    end = monotonic() + 5
    while monotonic() < end:
        result = jobs.get(pins['tenant'], pins['subject'], job['job_id'])
        if result['status'] not in {'QUEUED', 'RUNNING'}:
            return result
        Event().wait(.005)
    pytest.fail('Bounded job failed to terminate.')


def test_concurrent_duplicate_signed_intent_dispatches_once_and_survives_restart(tmp_path):
    release = Event()
    jobs, provider, pins, path = setup(tmp_path, provider=Provider(release=release))
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            submitted = list(pool.map(lambda _: jobs.submit(**pins, validate=lambda r: {'proposal': r['text']}), range(20)))
        assert len({job['job_id'] for job in submitted}) == 1
        assert provider.started.wait(1)
        assert len(provider.calls) == 1
        for _ in range(10):
            assert jobs.inspect(**pins)['existing_job']['job_id'] == submitted[0]['job_id']
            jobs.get(pins['tenant'], pins['subject'], submitted[0]['job_id'])
        assert len(provider.calls) == 1
        release.set()
        result = done(jobs, pins, submitted[0])
        assert result['status'] == 'SUCCEEDED'
        assert result['result'] == {'proposal': 'an inert source-grounded proposal'}
    finally:
        release.set()
        jobs.close()
    fresh = Provider()
    resumed = PublicProposalJobs(tmp_path/'app.sqlite', path, {'vendor': fresh}, clock=lambda: NOW)
    try:
        assert resumed.submit(**pins, validate=lambda _: pytest.fail('terminal result revalidated')) == result
        assert fresh.calls == []
    finally:
        resumed.close()


@pytest.mark.parametrize('changed', [dict(tenant='other'), dict(subject='other'), dict(kind='correspondence'),
                                    dict(target='other'), dict(context_sha256='b'*64),
                                    dict(request=canonical({'model': 'test', 'tools': [], 'input': 'Public text', 'attempt_nonce': 'initial', 'max_budget_usd': '1.00'}))])
def test_whole_request_and_every_identity_binding_require_exact_approval(tmp_path, changed):
    jobs, provider, pins, _ = setup(tmp_path)
    try:
        altered = {**pins, **changed}
        assert jobs.inspect(**altered)['enabled'] is False
        with pytest.raises(PermissionError):
            jobs.submit(**altered, validate=dict)
        assert provider.calls == []
    finally:
        jobs.close()


def test_other_subject_cannot_see_or_consume_existing_request(tmp_path):
    jobs, provider, pins, _ = setup(tmp_path)
    try:
        job = jobs.submit(**pins, validate=dict)
        done(jobs, pins, job)
        with pytest.raises(KeyError):
            jobs.get('tenant-a', 'reviewer-b', job['job_id'])
        with pytest.raises(KeyError):
            jobs.get('tenant-b', 'reviewer-a', job['job_id'])
        for method in (jobs.inspect, lambda **kw: jobs.submit(**kw, validate=dict)):
            with pytest.raises(PermissionError):
                method(**{**pins, 'subject': 'reviewer-b'})
        assert len(provider.calls) == 1
    finally:
        jobs.close()


@pytest.mark.parametrize('error,status,reason', [(TimeoutError('PRIVATE secret stderr'), 'UNCERTAIN', 'provider_timeout'),
                                              (RuntimeError('PRIVATE secret stderr'), 'UNCERTAIN', 'provider_outcome_unknown'),
                                              (ValueError('PRIVATE secret stderr'), 'REFUSED', 'proposal_validation_failed')])
def test_provider_failures_are_terminal_redacted_and_never_retried(tmp_path, error, status, reason):
    jobs, provider, pins, _ = setup(tmp_path, provider=Provider(error=error))
    try:
        job = jobs.submit(**pins, validate=dict)
        result = done(jobs, pins, job)
        assert (result['status'], result['reason'], result['result']) == (status, reason, None)
        assert 'PRIVATE' not in json.dumps(result)
        assert jobs.submit(**pins, validate=dict) == result
        assert len(provider.calls) == 1
    finally:
        jobs.close()


@pytest.mark.parametrize('result', [None, ['untyped'], {'value': float('nan')}, {'value': 'x'*300001}])
def test_validator_must_return_bounded_finite_object(tmp_path, result):
    jobs, _, pins, _ = setup(tmp_path)
    try:
        job = jobs.submit(**pins, validate=lambda _: result)
        assert done(jobs, pins, job)['status'] == 'REFUSED'
    finally:
        jobs.close()


def test_stale_context_validation_refuses_without_a_success_receipt(tmp_path):
    jobs, _, pins, _ = setup(tmp_path)
    def changed(_):
        raise PermissionError('Source context changed while the model ran.')
    try:
        result = done(jobs, pins, jobs.submit(**pins, validate=changed))
        assert result['status'] == 'REFUSED'
        assert result['result'] is None
        with sqlite3.connect(tmp_path/'app.sqlite') as db:
            evidence = json.loads(db.execute('SELECT response_json FROM public_proposal_jobs WHERE id=?', (result['job_id'],)).fetchone()[0])
        assert evidence == {'text': 'an inert source-grounded proposal'}
        assert 'response_json' not in result
    finally:
        jobs.close()


def test_second_owner_is_rejected_without_disturbing_first_owner(tmp_path):
    jobs, _, pins, path = setup(tmp_path)
    try:
        with pytest.raises(BlockingIOError):
            PublicProposalJobs(tmp_path/'app.sqlite', path, {'vendor': Provider()})
        assert done(jobs, pins, jobs.submit(**pins, validate=dict))['status'] == 'SUCCEEDED'
    finally:
        jobs.close()


def test_recovery_distinguishes_reserved_and_dispatched_work_without_running_either(tmp_path):
    jobs, _, pins, path = setup(tmp_path)
    result = done(jobs, pins, jobs.submit(**pins, validate=dict))
    jobs.close()
    for previous, expected in [('RUNNING', 'UNCERTAIN'), ('QUEUED', 'CANCELLED')]:
        with sqlite3.connect(tmp_path/'app.sqlite') as db:
            db.execute('UPDATE public_proposal_jobs SET status=?,result_json=NULL WHERE id=?', (previous, result['job_id']))
        provider = Provider()
        resumed = PublicProposalJobs(tmp_path/'app.sqlite', path, {'vendor': provider}, clock=lambda: NOW)
        try:
            assert resumed.get('tenant-a', 'reviewer-a', result['job_id'])['status'] == expected
            assert resumed.submit(**pins, validate=dict)['status'] == expected
            assert provider.calls == []
        finally:
            resumed.close()


def test_expiry_is_checked_before_dispatch_and_completed_late_is_recorded(tmp_path):
    at = [NOW]
    release = Event()
    jobs, provider, pins, _ = setup(tmp_path, clock=lambda: at[0], provider=Provider(release=release))
    try:
        job = jobs.submit(**pins, validate=dict)
        assert provider.started.wait(1)
        at[0] += timedelta(hours=2)
        release.set()
        result = done(jobs, pins, job)
        assert result['status'] == 'SUCCEEDED'
        assert result['completed_after_expiry'] is True
        assert jobs.inspect(**pins)['enabled'] is False
    finally:
        release.set()
        jobs.close()


def test_revocation_while_waiting_for_provider_prevents_second_dispatch(tmp_path):
    release = Event()
    jobs, provider, pins, path = setup(tmp_path, provider=Provider(release=release), max_workers=1)
    second = {**pins, 'target': 'vendor-b'}
    artifact = json.loads(path.read_text())
    artifact['approvals'].append({**artifact['approvals'][0], 'target': 'vendor-b'})
    path.write_text(json.dumps(artifact))
    try:
        first = jobs.submit(**pins, validate=dict)
        assert provider.started.wait(1)
        waiting = jobs.submit(**second, validate=dict)
        artifact['approvals'] = []
        path.write_text(json.dumps(artifact))
        release.set()
        assert done(jobs, pins, first)['status'] == 'SUCCEEDED'
        assert done(jobs, second, waiting)['status'] == 'REFUSED'
        assert len(provider.calls) == 1
    finally:
        release.set()
        jobs.close()


@pytest.mark.parametrize('limits', [dict(daily_jobs=1, daily_budget_usd='20.00'), dict(daily_jobs=20, daily_budget_usd='1.00')])
def test_daily_reservations_bound_separately_approved_attempts(tmp_path, limits):
    jobs, provider, pins, path = setup(tmp_path, limits=limits)
    artifact = json.loads(path.read_text())
    new_request = {**json.loads(pins['request']), 'attempt_nonce': 'operator-second-attempt'}
    artifact['approvals'].append({**artifact['approvals'][0], 'request': new_request})
    path.write_text(json.dumps(artifact))
    try:
        done(jobs, pins, jobs.submit(**pins, validate=dict))
        with pytest.raises(PermissionError, match='daily'):
            jobs.submit(**{**pins, 'request': canonical(new_request)}, validate=dict)
        assert len(provider.calls) == 1
    finally:
        jobs.close()


def test_explicit_approved_new_attempt_can_follow_a_refusal(tmp_path):
    jobs, provider, pins, path = setup(tmp_path)
    try:
        first = done(jobs, pins, jobs.submit(**pins, validate=lambda _: None))
        assert first['status'] == 'REFUSED'
        new_request = {**json.loads(pins['request']), 'attempt_nonce': 'operator-second-attempt'}
        altered = {**pins, 'request': canonical(new_request)}
        with pytest.raises(PermissionError):
            jobs.submit(**altered, validate=dict)
        artifact = json.loads(path.read_text())
        artifact['approvals'].append({**artifact['approvals'][0], 'request': new_request})
        path.write_text(json.dumps(artifact))
        second = done(jobs, altered, jobs.submit(**altered, validate=dict))
        assert second['status'] == 'SUCCEEDED'
        assert second['job_id'] != first['job_id']
        assert len(provider.calls) == 2
        assert jobs.get('tenant-a', 'reviewer-a', first['job_id']) == first
    finally:
        jobs.close()


@pytest.mark.parametrize('mutation', ['public_file', 'public_directory', 'symlink', 'hash_only', 'duplicate_json', 'duplicate_entry'])
def test_insecure_or_ambiguous_operator_artifacts_cannot_authorize(tmp_path, mutation):
    jobs, _, _, path = setup(tmp_path)
    jobs.close()
    value = json.loads(path.read_text())
    if mutation == 'public_file':
        path.chmod(0o644)
    elif mutation == 'public_directory':
        path.parent.chmod(0o755)
    elif mutation == 'symlink':
        actual = path.with_name('actual.json')
        path.rename(actual)
        path.symlink_to(actual)
    elif mutation == 'hash_only':
        value['approvals'][0]['request_sha256'] = 'a'*64
        del value['approvals'][0]['request']
        path.write_text(json.dumps(value))
    elif mutation == 'duplicate_json':
        path.write_text('{"version":1,"version":1,"limits":{},"approvals":[]}')
    else:
        value['approvals'].append(value['approvals'][0])
        path.write_text(json.dumps(value))
    with pytest.raises((ValueError, PermissionError, OSError)):
        load_approvals(path)


@pytest.mark.parametrize('encoded', [b'{"a":1,"a":2}', b'{"a": NaN}', b'{ "a": 1 }', b'[]', b'\xff', b'x'*80001])
def test_noncanonical_or_oversized_requests_never_invoke_provider(tmp_path, encoded):
    jobs, provider, pins, _ = setup(tmp_path)
    try:
        with pytest.raises(ValueError):
            jobs.submit(**{**pins, 'request': encoded}, validate=dict)
        assert provider.calls == []
    finally:
        jobs.close()
