#!/usr/bin/env python3
"""Socket-level authority probes against a separately served authored Northwind workspace.

Existing coverage of proof replay, body/path rebinding, forged keys, cross-origin and missing action
headers is in-process (TestClient). This probe sends the same attacks over real loopback HTTP to a
separate server process and checks that each is refused AND that the authoritative workflow and
ledger are unchanged afterwards. One legitimate signed action is then accepted, and an exact replay
of that accepted request is refused. Scripted local reviewer only; no Ramp, model or credential.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.probe_restart_gent8 import _free_port, _kill, _serve  # noqa: E402


def run(workdir, receipt_path):
    import httpx
    from uptime.auth import SCRIPT
    from uptime.auth_client import ReviewerClient
    from uptime.source_config import _check_file, _protected_path
    workdir = Path(workdir).resolve()
    workdir.mkdir(mode=0o700)
    directory = workdir / 'workspace'
    port = _free_port()
    origin = f'http://127.0.0.1:{port}'
    prepared = subprocess.run([sys.executable, str(ROOT / 'scripts/setup_northwind.py'), '--directory', str(directory),
                               '--origin', origin], cwd=ROOT, capture_output=True, text=True, timeout=300)
    if prepared.returncode:
        raise RuntimeError('Workspace preparation failed: ' + prepared.stderr[-500:])
    path = _protected_path(directory / 'workspace.json')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'r') as handle:
        _check_file(handle.fileno())
        secret = json.load(handle)['rehearsal_secret']
    log = (workdir / 'server.log').open('ab')
    server = _serve(directory, origin, log)
    probes = []
    try:
        with httpx.Client(base_url=origin, timeout=30, trust_env=False) as client:
            actor = ReviewerClient(client, origin, SCRIPT, secret)

            def state():
                response = client.get('/api/workspace/workflow', headers=actor.headers)
                response.raise_for_status()
                return response.json()['workflow']

            before = state()
            route = '/api/workspace/workflow/actions/' + before['next_actions'][0]['id']
            other = '/api/workspace/workflow/actions/' + 'action-' + '0' * 64

            def attempt(name, send):
                response = send()
                probes.append(dict(name=name, http_status=response.status_code, refused=response.status_code >= 400,
                                   state_unchanged=state() == before))

            signed = actor.prepare(route, {})
            attempt('body_tampered_after_signing',
                    lambda: client.post(route, content=b'{"amount":"999999.00"}', headers=signed['headers']))
            signed = actor.prepare(route, {})
            attempt('proof_rebound_to_other_path', lambda: client.post(other, **signed))
            signed = actor.prepare(route, {})
            attempt('cross_origin_header',
                    lambda: client.post(route, content=signed['content'],
                                        headers={**signed['headers'], 'Origin': f'http://127.0.0.1:{port + 1}'}))
            signed = actor.prepare(route, {})
            attempt('missing_action_header',
                    lambda: client.post(route, content=signed['content'],
                                        headers={k: v for k, v in signed['headers'].items() if k != 'X-Uptime-Action'}))
            attempt('bearer_session_without_proof', lambda: client.post(route, content=b'{}', headers=actor.headers))
            attempt('forged_rehearsal_key_login', lambda: _forged_login(client, origin))

            accepted_request = actor.prepare(route, {})
            accepted = client.post(route, **accepted_request)
            after_accept = state()
            replay = client.post(route, **accepted_request)
            probes.append(dict(name='exact_replay_of_accepted_request', http_status=replay.status_code,
                               refused=replay.status_code >= 400, state_unchanged=state() == after_accept))
        result = dict(schema='socket-authority-probe-gent8/1', at=datetime.now(UTC).isoformat(), transport='REAL_LOOPBACK_HTTP',
                      process_model='separate OS server process', authority_kind='SCRIPTED_REVIEWER',
                      probe_sha256=sha256(Path(__file__).read_bytes()).hexdigest(), probes=probes,
                      legitimate_action=dict(http_status=accepted.status_code, state_changed=after_accept != before,
                                             ledger_before=before['ledger'], ledger_after=after_accept['ledger']))
    finally:
        _kill(server)
        log.close()
    Path(receipt_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    return result


def _forged_login(client, origin):
    """Log in as the scripted subject with a key derived from a different secret."""
    from uptime.auth import SCRIPT
    from uptime.auth_client import ReviewerClient
    import httpx
    try:
        ReviewerClient(client, origin, SCRIPT, 'forged-' + '0' * 40)
    except httpx.HTTPStatusError as error:
        return error.response
    raise AssertionError('A forged rehearsal key was accepted at login.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args(argv)
    result = run(args.workdir, args.receipt)
    for probe in result['probes']:
        print(probe)
    print('legitimate', result['legitimate_action']['http_status'], result['legitimate_action']['state_changed'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
