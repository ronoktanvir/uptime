#!/usr/bin/env python3
"""Frozen public-input evaluation through signed runtime jobs; never reads gold.

Prepare is offline. Run requires a separately approved exact request. Each attempt
is create-only and may dispatch once. Local observations are previewed without
semantic review, fee attestation, promotion, or native actions.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import subprocess
import sys
from threading import Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.public_proposals import _read_document, _write_new, _private_directory
from uptime import vendor_model_jobs, vendor_terms
from uptime.auth import enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key
from uptime.contracts import DraftReviewer
from uptime.correspondence_model_transport import strict_json
from uptime.public_proposal_config import PublicProposalConfig
from uptime.public_proposal_jobs import canonical, load_approvals
from uptime.source_config import _protected_path, load_private

PROFILES = {
    'monthly_tier': 'monthly-propositions', 'completed_step': 'monthly-propositions',
    'unsupported_variable_fee': 'monthly-propositions', 'ambiguous_deadline': 'monthly-propositions',
    'resource_month': 'resource-month', 'aggregate_fixed_month': 'resource-month',
}
CORE_FILES = ('uptime/vendor_model_jobs.py', 'uptime/public_proposal_jobs.py',
              'uptime/public_proposal_config.py', 'uptime/correspondence_model_transport.py',
              'uptime/vendor_api.py', 'uptime/server.py', 'uptime/auth.py', 'uptime/auth_client.py',
              'uptime/source_config.py', 'scripts/evaluate_onboarding_85.py', 'scripts/public_proposals.py')
TERMINAL = {'SUCCEEDED', 'REFUSED', 'UNCERTAIN', 'CANCELLED'}
# SafePublicClaude (uptime/correspondence_model_transport.py) runs --help and --version (10 s each)
# when the job constructs its provider, then one 60 s call. The poll must outlast that bound, and
# shutdown must let the job pool finish so the queue snapshot holds the job's own terminal state.
PROVIDER_BOUND_SECONDS = 80
POLL_SECONDS = PROVIDER_BOUND_SECONDS + 40
SHUTDOWN_SECONDS = PROVIDER_BOUND_SECONDS + 20


def _hash(data):
    return sha256(data).hexdigest()


def _json_new(path, value):
    _write_new(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())


def _input(path, name, expected):
    path = Path(path)
    # Check filename and resolved identity before any open; never discover inputs by scanning.
    if path.name != name or not path.is_absolute() or path.resolve() != path:
        raise ValueError('Only the explicit frozen document.json/customer.json inputs are allowed.')
    if not re.fullmatch('[a-f0-9]{64}', expected):
        raise ValueError('A frozen raw file digest is required.')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('A regular frozen input is required.')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(500001)
    finally:
        os.close(fd)
    if len(raw) > 500000 or _hash(raw) != expected:
        raise ValueError('Frozen input hash differs.')
    return raw


def _customer(raw):
    value = strict_json(raw)
    if (not isinstance(value, dict) or not {'overlay', 'scenarios'} <= set(value)
            or set(value) - {'overlay', 'scenarios', 'classification', 'governing_fee_source'}
            or not isinstance(value['overlay'], dict) or not isinstance(value['scenarios'], list)):
        raise ValueError('Use local overlay and authored scenarios only.')
    if 'classification' in value and not isinstance(value['classification'], str):
        raise ValueError('Invalid local classification.')
    if 'governing_fee_source' in value and not isinstance(value['governing_fee_source'], dict):
        raise ValueError('Raw local fee source must be an object, never issued authority.')
    names = []
    for scenario in value['scenarios']:
        if (not isinstance(scenario, dict) or set(scenario) != {'name', 'facts'}
                or not isinstance(scenario['name'], str) or not scenario['name']
                or not isinstance(scenario['facts'], dict)):
            raise ValueError('Each local scenario needs only name and facts.')
        names.append(scenario['name'])
    if len(names) != len(set(names)):
        raise ValueError('Scenario names must be unique.')
    return value


def source_pins(profile):
    family = vendor_model_jobs.PROFILE_FAMILIES[profile]
    files = set(CORE_FILES) | {'uptime/' + name for name in vendor_terms._PROFILE_FILES[family]}
    return {name: _hash((ROOT / name).read_bytes()) for name in sorted(files)}


def core_tree():
    """Digest of every tracked uptime/ file as it exists on disk; refuses uncommitted core changes."""
    def git(*args):
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True, timeout=30).stdout
    if git('status', '--porcelain', '--untracked-files=all', '--', 'uptime').strip():
        raise ValueError('Tested core source must be committed before an attempt is frozen or run.')
    names = sorted(name for name in git('ls-files', '-z', '--', 'uptime').decode().split('\0') if name)
    return _hash(canonical({name: _hash((ROOT / name).read_bytes()) for name in names}))


def _configuration(config_path):
    config = load_private(config_path, PublicProposalConfig)
    if config.kinds != ['vendor']:
        raise ValueError('The evaluation uses a vendor-only protected configuration.')
    _protected_path(config.approvals_path)
    return config


def _body(document, profile):
    return vendor_model_jobs.ProposalRequest(document=document, profile=profile, attempt_nonce='initial')


def prepare_case(*, case_id, family, document_path, customer_path, document_sha256,
                 customer_sha256, config_path, attempt_dir, tenant, subject):
    """Freeze one exact request without approval, queue setup, or inference."""
    if family not in PROFILES or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', case_id):
        raise ValueError('Use a declared family and bounded local case identifier.')
    profile = PROFILES[family]
    path = _protected_path(Path(attempt_dir))
    _private_directory(os.lstat(path.parent))
    if path.exists():
        raise FileExistsError('An attempt directory must be new.')
    raw_document = _input(document_path, 'document.json', document_sha256)
    raw_customer = _input(customer_path, 'customer.json', customer_sha256)
    document = _read_document(document_path)
    _customer(raw_customer)
    config = _configuration(config_path)
    # No case/family label or local customer fact enters target or transmitted request.
    target = 'v-' + _hash(raw_document)[:24]
    provider = vendor_model_jobs.build_vendor_provider(config.executable)
    exported = vendor_model_jobs.public_approval_request(
        provider, DraftReviewer(tenant, subject, 'reviewer'), target, _body(document, profile))
    request = canonical(exported['request'])
    pins = source_pins(profile)
    frozen = dict(schema='onboarding-evaluation85/1', case_id=case_id, family=family, profile=profile,
                  target=target, tenant=tenant, subject=subject, attempt_nonce='initial',
                  document_path=str(document_path), customer_path=str(customer_path),
                  document_sha256=document_sha256, customer_sha256=customer_sha256,
                  source_text_sha256=_hash(document['text'].encode()), request_sha256=_hash(request),
                  context_sha256=exported['context_sha256'], provider_profile=provider.profile,
                  config_sha256=_hash(canonical(config.model_dump())), source_pins=pins,
                  core_tree_sha256=core_tree(),
                  semantic_family=vendor_model_jobs.PROFILE_FAMILIES[profile],
                  semantic_digest=vendor_terms.SEMANTICS_REVISIONS[vendor_model_jobs.PROFILE_FAMILIES[profile]],
                  git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  authority='Generated local draft key only; no human review, monetary authority or promotion.')
    path.mkdir(mode=0o700)
    _write_new(path / 'document.json', raw_document)
    _write_new(path / 'customer.json', raw_customer)
    _write_new(path / 'request.json', request)
    _json_new(path / 'request-export.json', exported)
    _json_new(path / 'frozen.json', frozen)
    return frozen


def _progress(path, stage, **values):
    data = canonical(dict(at=datetime.now(UTC).isoformat(), stage=stage, **values)) + b'\n'
    fd = os.open(path / 'progress.jsonl', os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'ab') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def _verify(path, frozen, config_path):
    if frozen['profile'] != PROFILES[frozen['family']] or source_pins(frozen['profile']) != frozen['source_pins']:
        raise ValueError('Frozen runner or consumed core changed.')
    if core_tree() != frozen.get('core_tree_sha256'):
        raise ValueError('Tracked core source changed after the attempt was frozen.')
    for name in ('document', 'customer'):
        digest = frozen[name + '_sha256']
        _input(Path(frozen[name + '_path']), name + '.json', digest)
        _input(path / (name + '.json'), name + '.json', digest)
    config = _configuration(config_path)
    if _hash(canonical(config.model_dump())) != frozen['config_sha256']:
        raise ValueError('Configuration changed.')
    provider = vendor_model_jobs.build_vendor_provider(config.executable)
    document = _read_document(path / 'document.json')
    exported = vendor_model_jobs.public_approval_request(
        provider, DraftReviewer(frozen['tenant'], frozen['subject'], 'reviewer'), frozen['target'],
        _body(document, frozen['profile']))
    request = canonical(exported['request'])
    if (provider.profile != frozen['provider_profile'] or _hash(request) != frozen['request_sha256']
            or (path / 'request.json').read_bytes() != request
            or strict_json((path / 'request-export.json').read_bytes()) != exported
            or exported['context_sha256'] != frozen['context_sha256']):
        raise ValueError('Request, context or transport profile changed.')
    return config, document, _customer((path / 'customer.json').read_bytes())


@contextmanager
def _loopback(db, config_path, frozen, lifecycle):
    import httpx
    import uvicorn
    from uptime.server import create_app
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    origin = 'http://127.0.0.1:' + str(sock.getsockname()[1])
    app = create_app(db, tenant=frozen['tenant'], origin=origin, approvals_enabled=False,
                     proposal_config=config_path)
    key = generate_reviewer_key()
    enroll(db, frozen['subject'], key, tenant=frozen['tenant'])
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='on'))
    thread = Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        if not server.started:
            raise RuntimeError('Loopback server startup failed.')
        with httpx.Client(base_url=origin, timeout=15, trust_env=False) as client:
            yield client, ReviewerClient(client, origin, frozen['subject'], key)
    finally:
        server.should_exit = True
        # Lifespan shutdown closes the job pool with wait=True; a running provider call finishes or
        # times out inside its own bound before the queue is snapshotted.
        thread.join(SHUTDOWN_SECONDS)
        lifecycle['server_stopped'] = not thread.is_alive()
        sock.close()


def _queue_evidence(path, db, frozen):
    if not db.exists():
        return []
    with sqlite3.connect(db) as connection:
        connection.row_factory = sqlite3.Row
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'public_proposal_jobs' not in tables:
            return []
        rows = [dict(r) for r in connection.execute(
            'SELECT * FROM public_proposal_jobs WHERE tenant=? AND subject=? AND target=?',
            (frozen['tenant'], frozen['subject'], frozen['target']))]
    # Owner-only immutable audit snapshot; response/transport metadata never sent to model.
    _json_new(path / 'queue-evidence.json', rows)
    return rows


def run_attempt(*, attempt_dir, config_path):
    """Consume an approved frozen attempt once through signed loopback HTTP."""
    path = _protected_path(Path(attempt_dir))
    _private_directory(os.lstat(path))
    frozen = strict_json((path / 'frozen.json').read_bytes())
    _json_new(path / 'run-started.json', dict(at=datetime.now(UTC).isoformat(), frozen_sha256=_hash((path / 'frozen.json').read_bytes())))
    report = dict(case_id=frozen['case_id'], profile=frozen['profile'], failure_stage=None,
                  extraction={'status': 'NOT_ATTEMPTED'}, shadow={'status': 'NOT_ATTEMPTED'},
                  deterministic=[], authority={'promotion_performed': False, 'actual_human_review': False,
                  'semantic_review_performed': False, 'fee_authority_created': False})
    stage = 'frozen_inputs'
    own_database = False
    lifecycle = {}
    db = path / 'workspace.sqlite'
    _progress(path, stage)
    try:
        if db.exists():
            raise ValueError('A supplied database cannot be used as runtime evidence.')
        config, document, customer = _verify(path, frozen, config_path)
        stage = 'permission'
        _progress(path, stage)
        load_approvals(Path(config.approvals_path))
        own_database = True
        with _loopback(db, config_path, frozen, lifecycle) as (client, signed):
            base = '/api/vendors/' + frozen['target']
            body = _body(document, frozen['profile']).model_dump()
            access = signed.post(base + '/proposal-access', body)
            _json_new(path / 'access.json', {'http_status': access.status_code, 'body': access.json()})
            access.raise_for_status()
            if (access.json().get('enabled') is not True or access.json().get('existing_job') is not None
                    or access.json().get('request_sha256') != frozen['request_sha256']
                    or access.json().get('context_sha256') != frozen['context_sha256']):
                raise PermissionError('The exact new request is not approved.')
            stage = 'extraction'
            _progress(path, stage, action='single_submission')
            report['extraction']['status'] = 'UNCERTAIN'
            response = signed.post(base + '/proposal-jobs', body)  # Never retry this POST.
            _json_new(path / 'submission.json', {'http_status': response.status_code, 'body': response.json()})
            response.raise_for_status()
            job = response.json()
            job_id = vendor_model_jobs.job_identifier(job)
            report['extraction']['job_id'] = job_id
            deadline = time.monotonic() + POLL_SECONDS
            last_status = None
            while True:
                if job.get('status') != last_status:
                    _progress(path, stage, job_id=job_id, status=job.get('status'))
                    last_status = job.get('status')
                if job.get('status') in TERMINAL:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('A pending attempt remains unresolved; it is never retried.')
                time.sleep(.1)
                response = client.get(base + '/proposal-jobs/' + job_id, headers=signed.headers)
                response.raise_for_status()
                job = response.json()
            _json_new(path / 'job.json', job)
            report['extraction'].update(status=job['status'], reason=job.get('reason'))
            if job['status'] != 'SUCCEEDED':
                report['failure_stage'] = stage
                return report
            stage = 'shadow'
            _progress(path, stage)
            response = signed.post(base + '/proposal-jobs/' + job_id + '/candidate', {'overlay': customer['overlay']})
            _json_new(path / 'candidate.json', {'http_status': response.status_code, 'body': response.json()})
            response.raise_for_status()
            candidate = response.json()
            report['shadow'] = {'status': candidate['state'], 'version': candidate.get('version')}
            if candidate['state'] != 'SHADOW' or candidate.get('active_version') or candidate.get('reviewer'):
                report['failure_stage'] = stage
                return report
            stage = 'evaluation'
            _progress(path, stage)
            for scenario in customer['scenarios']:
                # Authored received_at remains the financial observation clock. Security uses real wall time.
                response = signed.post(base + '/shadow-preview', {'revision': candidate['revision'], 'facts': scenario['facts']})
                report['deterministic'].append({'name': scenario['name'], 'http_status': response.status_code, 'result': response.json()})
                if response.status_code != 200:
                    report['failure_stage'] = stage
            return report
    except Exception as error:
        report['failure_stage'] = stage
        report['error_type'] = type(error).__name__  # no uncontrolled private exception text
        return report
    finally:
        if own_database:
            rows = _queue_evidence(path, db, frozen)
            # The server's own record after shutdown, separate from what the poll last observed.
            # A job still QUEUED/RUNNING here was not observed terminal; it is never retried.
            report['queue'] = {'server_stopped': lifecycle.get('server_stopped', False),
                               'jobs': [{'status': row.get('status'), 'reason': row.get('reason')} for row in rows],
                               'terminal_observed': bool(rows) and all(row.get('status') in TERMINAL for row in rows)}
        _progress(path, 'finished', failure_stage=report['failure_stage'])
        _json_new(path / 'report.json', report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    for name in ('case-id', 'family', 'document-path', 'customer-path', 'document-sha256', 'customer-sha256',
                 'config-path', 'attempt-dir', 'tenant', 'subject'):
        prepare.add_argument('--' + name, required=True)
    run = commands.add_parser('run')
    run.add_argument('--attempt-dir', required=True)
    run.add_argument('--config-path', required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    result = prepare_case(**args) if command == 'prepare' else run_attempt(**args)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
