#!/usr/bin/env python3
"""Supplementary authored-cohort driver: ordinary automatic-selection draft-signed app path.

Draft mode only (approvals disabled by the unchanged release gate): inspect -> exact per-family request export
and digest check -> optional operator approval (model invocation only) -> one start -> poll until a terminal
selection outcome -> stage the SELECTED candidate (SHADOW) -> optional shadow previews. No promotion, activation,
rollback, signature or human action is performed; those belong to Ronok. Every artifact is create-only and the
run directory must be new, so an attempt can never be repeated silently.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from threading import Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TERMINAL = {'SELECTED', 'AMBIGUOUS', 'NO_SUPPORTED_FAMILY', 'INCOMPLETE'}
PROVIDER_BOUND_SECONDS = 80          # SafePublicClaude: --help 10 s + --version 10 s + one 60 s call
POLL_SECONDS = 2 * PROVIDER_BOUND_SECONDS + 60   # vendor jobs share one provider lock: families run sequentially
SHUTDOWN_SECONDS = 2 * PROVIDER_BOUND_SECONDS + 20
TENANT, SUBJECT = 'eval-finish-20261109', 'finish-selector'


def _new(path, value):
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(data)


def _log(run, stage, **values):
    line = json.dumps(dict(at=datetime.now(UTC).isoformat(), stage=stage, **values), sort_keys=True) + '\n'
    fd = os.open(run / 'progress.jsonl', os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'a') as out:
        out.write(line)


@contextmanager
def _served(db, config_path, lifecycle):
    import httpx
    import uvicorn
    from uptime.auth import enroll
    from uptime.auth_client import ReviewerClient
    from uptime.auth_keys import generate_reviewer_key
    from uptime.server import create_app
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    origin = 'http://127.0.0.1:' + str(sock.getsockname()[1])
    app = create_app(db, tenant=TENANT, origin=origin, approvals_enabled=False, proposal_config=config_path)
    key = generate_reviewer_key()
    enroll(db, SUBJECT, key, tenant=TENANT)
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='on'))
    thread = Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        if not server.started:
            raise RuntimeError('Loopback server startup failed.')
        with httpx.Client(base_url=origin, timeout=30, trust_env=False) as client:
            yield ReviewerClient(client, origin, SUBJECT, key)
    finally:
        server.should_exit = True
        thread.join(SHUTDOWN_SECONDS)
        lifecycle['server_stopped'] = not thread.is_alive()
        sock.close()


def _export(document, family, target, executable):
    from uptime.contracts import DraftReviewer
    from uptime.public_proposal_jobs import canonical
    from uptime import vendor_model_jobs
    provider = vendor_model_jobs.build_vendor_provider(executable)
    body = vendor_model_jobs.ProposalRequest(document=document, profile=family['profile'], attempt_nonce='initial')
    exported = vendor_model_jobs.public_approval_request(provider, DraftReviewer(TENANT, SUBJECT, 'reviewer'), target, body)
    return exported, canonical(exported['request'])


def _forbidden_strings(local):
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
    return sorted({s for s in strings(local) if isinstance(s, str) and len(s) >= 6})


def verify_freeze(*, source_commit, pinned_inputs):
    """Require committed core and the exact declared input bytes before an attempt."""
    changed = subprocess.check_output(['git', 'diff', '--name-only', source_commit, '--', 'uptime', 'web', 'scripts/evaluate_onboarding_finish.py'], cwd=ROOT)
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all', '--', 'uptime', 'web', 'scripts/evaluate_onboarding_finish.py'], cwd=ROOT)
    if changed.strip() or dirty.strip():
        raise ValueError('Frozen implementation or runner differs; do not start an attempt.')
    if not pinned_inputs:
        raise ValueError('Frozen inputs are required.')
    for filename, expected in pinned_inputs.items():
        path = Path(filename)
        if not path.is_absolute() or path.resolve() != path or path.is_symlink() or not path.is_file():
            raise ValueError('Frozen input must be an absolute regular non-symlink file.')
        if sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen input hash differs; do not start an attempt.')
    return True


def run(*, document_path, overlay_path, run_dir, config_path, approve, approved_by=None, scenarios_path=None):
    from scripts.public_proposals import _read_document, approve as grant
    from uptime.public_proposal_config import PublicProposalConfig
    from uptime.source_config import load_private
    from uptime.vendor_terms import Document
    run = Path(run_dir)
    run.mkdir(mode=0o700)  # must be new: one attempt per directory, never silently repeated
    raw = Path(document_path).read_bytes()
    document = Document.model_validate(_read_document(Path(document_path)))
    overlay = json.loads(Path(overlay_path).read_bytes())
    scenarios = json.loads(Path(scenarios_path).read_bytes()) if scenarios_path else []
    # Never open expected answers, even for a leak scan. Local overlay values suffice here.
    forbidden = [s for s in _forbidden_strings(overlay) if s not in document.text]
    config = load_private(Path(config_path), PublicProposalConfig)
    target = 'v-' + sha256(raw).hexdigest()[:24]
    body = {'document': document.model_dump(), 'profile': 'auto', 'attempt_nonce': 'initial'}
    report = dict(schema='supplementary-onboarding-finish/1', document_sha256=sha256(raw).hexdigest(), target=target,
                  head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), stage='inspect', outcome=None,
                  requests=[], approvals=[], started=False, candidate=None, previews=[],
                  authority={'approvals_enabled': False, 'promotion_performed': False, 'human_actions_performed': False})
    lifecycle = {}
    db = run / 'workspace.sqlite'
    _log(run, 'start')
    try:
        with _served(db, config_path, lifecycle) as signed:
            base = '/api/vendors/' + target
            view = signed.post(base + '/proposal-access', body)
            _new(run / 'view-inspect.json', {'http_status': view.status_code, 'body': view.json()})
            view.raise_for_status()
            view = view.json()
            report['outcome'] = view['outcome']
            _log(run, 'inspected', outcome=view['outcome'])
            if view['outcome'] == 'APPROVAL_REQUIRED':
                report['stage'] = 'approval'
                for family in view['families']:
                    exported, request = _export(document, family, target, config.executable)
                    digest = sha256(request).hexdigest()
                    leaks = [s for s in forbidden if s.encode() in request]
                    record = {'family': family['family'], 'profile': family['profile'], 'request_sha256': digest,
                              'matches_server': digest == family['request_sha256'], 'bytes': len(request),
                              'transmitted_fields': sorted(json.loads(request)), 'forbidden_strings_found': len(leaks)}
                    report['requests'].append(record)
                    _new(run / f"request-export-{family['family'].replace('/', '_')}.json", exported)
                    if not record['matches_server'] or leaks:
                        raise PermissionError('An exported request differs from the server pin or contains local material.')
                if not approve:
                    report['stage'] = 'awaiting_operator_approval'
                    return report
                for family, record in zip(view['families'], report['requests']):
                    granted = grant(run / f"request-export-{family['family'].replace('/', '_')}.json", Path(config.approvals_path),
                                    approved_by=approved_by, expected_digest=record['request_sha256'], public_confirmed=True, hours=6)
                    report['approvals'].append({'family': family['family'], 'scope': granted['scope'], 'expires_at': granted['expires_at']})
                report['stage'] = 'start'
                started = signed.post(base + '/proposal-jobs', body)  # one start; never retried
                _new(run / 'start.json', {'http_status': started.status_code, 'body': started.json()})
                started.raise_for_status()
                report['started'] = True
                _log(run, 'started')
                deadline, view = time.monotonic() + POLL_SECONDS, started.json()
                while view['outcome'] not in TERMINAL and time.monotonic() < deadline:
                    time.sleep(1)
                    view = signed.post(base + '/proposal-access', body).json()
                _new(run / 'view-final.json', view)
                report['outcome'] = view['outcome']
                report['stage'] = 'selection'
                _log(run, 'selection', outcome=view['outcome'])
            selected = view.get('selected')
            if view['outcome'] == 'SELECTED' and selected:
                report['stage'] = 'staging'
                if selected['method'] == 'public_proposal_job':
                    staged = signed.post(f"{base}/proposal-jobs/{selected['job_id']}/candidate", {'overlay': overlay})
                else:
                    staged = signed.post(base + '/candidates', {'document': document.model_dump(), 'overlay': overlay})
                _new(run / 'candidate.json', {'http_status': staged.status_code, 'body': staged.json()})
                report['candidate'] = {'http_status': staged.status_code,
                                       'state': staged.json().get('state') if staged.status_code == 200 else None,
                                       'family': selected['family'], 'method': selected['method']}
                if staged.status_code == 200 and staged.json().get('state') == 'SHADOW':
                    report['stage'] = 'shadow'
                    for scenario in scenarios:
                        preview = signed.post(base + '/shadow-preview', {'revision': staged.json()['revision'], 'facts': scenario['facts']})
                        report['previews'].append({'name': scenario['name'], 'http_status': preview.status_code, 'result': preview.json()})
            return report
    except Exception as error:
        report['error_type'] = type(error).__name__
        return report
    finally:
        report['server_stopped'] = lifecycle.get('server_stopped', False)
        if db.exists():
            with sqlite3.connect(f'file:{db}?mode=ro', uri=True) as connection:
                connection.row_factory = sqlite3.Row
                tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                rows = [dict(r) for r in connection.execute('SELECT * FROM public_proposal_jobs')] if 'public_proposal_jobs' in tables else []
            report['jobs'] = [{'status': r.get('status'), 'reason': r.get('reason')} for r in rows]
            _new(run / 'queue-evidence.json', rows)
        _log(run, 'finished', final_stage=report['stage'], outcome=report['outcome'])
        _new(run / 'report.json', report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('document-path', 'overlay-path', 'run-dir', 'config-path'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--scenarios-path', type=Path)
    parser.add_argument('--approve', action='store_true', help='Operator approval for model invocation only (needs a go-ahead)')
    parser.add_argument('--approved-by')
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--input-pins', required=True, type=Path, help='Frozen absolute input path to SHA-256 mapping; no expected answers')
    args = parser.parse_args(argv)
    if args.approve and not args.approved_by:
        parser.error('--approve requires --approved-by')
    pins = json.loads(args.input_pins.read_bytes())
    required = [args.document_path, args.overlay_path] + ([args.scenarios_path] if args.scenarios_path else [])
    if any(str(path) not in pins for path in required):
        parser.error('Every consumed source/overlay/scenario file must be pinned.')
    verify_freeze(source_commit=args.source_commit, pinned_inputs=pins)
    report = run(document_path=args.document_path, overlay_path=args.overlay_path, run_dir=args.run_dir,
                 config_path=args.config_path, approve=args.approve, approved_by=args.approved_by,
                 scenarios_path=args.scenarios_path)
    print(json.dumps({k: report.get(k) for k in ('stage', 'outcome', 'started', 'candidate', 'error_type', 'jobs')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
