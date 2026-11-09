#!/usr/bin/env python3
"""Cross-component probe: hard process kill and restart in the middle of the authored Northwind flow.

Existing restart tests reopen SQLite inside one interpreter. This probe runs the served application as
separate OS processes over real loopback HTTP: it takes some signed actions, SIGKILLs the server (no
graceful shutdown), starts a new process on the same database, replays the last action, and finishes
the flow. It checks persisted state, duplicate-action idempotency across the kill, and the final ledger
amounts the authored walkthrough documents. Authored local workspace only: no Ramp, model or
credential is used; the reviewer is the scripted local account, never ACTUAL_HUMAN.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _serve(directory, origin, log):
    process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/setup_northwind.py'), '--directory', str(directory),
                                '--resume', '--serve'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True)
    import httpx
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Server process exited during startup.')
        try:
            if httpx.get(origin + '/api/auth/context', timeout=1, trust_env=False).status_code == 200:
                return process
        except httpx.HTTPError:
            time.sleep(.2)
    process.kill()
    raise TimeoutError('Server did not start.')


def _kill(process):
    os.killpg(process.pid, signal.SIGKILL)
    process.wait(10)
    return process.returncode


def _money(value):
    return None if value is None else str(Decimal(str(value)))


def run(workdir, receipt_path, actions_before_kill=4):
    import httpx
    from scripts.rehearse_northwind import run as rehearse
    from uptime.auth_client import ReviewerClient
    from uptime.auth import SCRIPT
    from uptime.source_config import _protected_path, _check_file
    workdir = Path(workdir).resolve()
    workdir.mkdir(mode=0o700)
    directory = workdir / 'workspace'
    origin = f'http://127.0.0.1:{_free_port()}'
    log = (workdir / 'server.log').open('ab')
    prepared = subprocess.run([sys.executable, str(ROOT / 'scripts/setup_northwind.py'), '--directory', str(directory),
                               '--origin', origin], cwd=ROOT, capture_output=True, text=True, timeout=300)
    if prepared.returncode:
        raise RuntimeError('Workspace preparation failed: ' + prepared.stderr[-500:])
    result = dict(schema='restart-probe-gent8/1', started_at=datetime.now(UTC).isoformat(), transport='REAL_LOOPBACK_HTTP',
                  process_model='separate OS processes; SIGKILL between them', authority_kind='SCRIPTED_REVIEWER',
                  probe_sha256=sha256(Path(__file__).read_bytes()).hexdigest(), origin=origin)
    first = _serve(directory, origin, log)
    try:
        before = rehearse(directory, workdir / 'before-kill.json', actions_before_kill)
    except BaseException:
        _kill(first)
        raise
    result['before_kill'] = dict(actions=len(before['steps']), ledger=before['final']['ledger'],
                                 last_action=before['steps'][-1]['action'] if before['steps'] else None)
    result['first_process_returncode'] = _kill(first)
    second = _serve(directory, origin, log)
    try:
        path = _protected_path(directory / 'workspace.json')
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'r') as handle:
            _check_file(handle.fileno())
            private = json.load(handle)
        with httpx.Client(base_url=origin, timeout=30, trust_env=False) as client:
            actor = ReviewerClient(client, origin, SCRIPT, private['rehearsal_secret'])
            restored = client.get('/api/workspace/workflow', headers=actor.headers).json()['workflow']
            replay = None
            if result['before_kill']['last_action']:
                route = '/api/workspace/workflow/actions/' + result['before_kill']['last_action']['id']
                response = actor.post(route, {})
                replay = dict(http_status=response.status_code,
                              unchanged=response.status_code == 200 and response.json()['workflow'] == restored)
        result['after_restart'] = dict(state_equal_to_pre_kill=restored == before['final'], duplicate_replay=replay)
        after = rehearse(directory, workdir / 'after-restart.json', 20)
    finally:
        result['second_process_returncode'] = _kill(second)
        log.close()
    final = after['final']
    result['completion'] = dict(actions_after_restart=len(after['steps']), remaining_actions=after['available_actions_remaining'],
                                ledger=final['ledger'], every_duplicate_unchanged=all(s['duplicate_unchanged'] for s in after['steps']),
                                every_readback_equal=all(s['readback_equal'] for s in after['steps']))
    result['finished_at'] = datetime.now(UTC).isoformat()
    Path(receipt_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True, help='New directory for the disposable workspace')
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--actions-before-kill', type=int, default=4)
    args = parser.parse_args(argv)
    result = run(args.workdir, args.receipt, args.actions_before_kill)
    print(json.dumps(dict(before_kill=result['before_kill']['actions'], after_restart=result['after_restart'],
                          completion={k: v for k, v in result['completion'].items() if k != 'ledger'}), indent=1))
    print(json.dumps(result['completion']['ledger'], indent=1)[:1500])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
