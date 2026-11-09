#!/usr/bin/env python3
"""One-off dry run of the phase85 runner through the REAL SafePublicClaude transport and a fake CLI.

Uses only the authored harness control (docs/v4/evaluation85/test_control.json), never corpus84 or
gold. The fake executable answers --help/--version like the pinned CLI and then either hangs past
the transport's 60 s bound (`hang`) or returns a well-formed stream (`ok`). Every invocation is
counted in a file beside it, so a retry would be visible. No real model is called.

Usage: python scripts/dryrun_onboarding_85_transport.py --mode hang --workdir NEW_DIR --receipt NEW_FILE
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAKE = '''#!{python}
import json, sys, time
from pathlib import Path
here = Path(__file__).parent
with open(here / 'invocations.log', 'a') as log:
    log.write(' '.join(a for a in sys.argv[1:] if a.startswith('--')) + '\\n')
if '--help' in sys.argv:
    print('usage --safe-mode --tools'); sys.exit(0)
if '--version' in sys.argv:
    print('0.0-dryrun-fake'); sys.exit(0)
sys.stdin.buffer.read()
model = sys.argv[sys.argv.index('--model') + 1]
print(json.dumps(dict(type='system', subtype='init', tools=[], mcp_servers=[], model=model, session_id='dryrun')), flush=True)
if (here / 'mode').read_text().strip() == 'hang':
    time.sleep({hang})
print(json.dumps(dict(type='result', subtype='success', is_error=False, session_id='dryrun',
                      modelUsage={{model: {{}}}}, result={text})), flush=True)
'''


def _private(path):
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def _write(path, data, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as out:
        out.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('hang', 'ok'), required=True)
    parser.add_argument('--hang-seconds', type=int, default=75)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args(argv)
    from hashlib import sha256
    from scripts import evaluate_onboarding_85 as harness
    from scripts import public_proposals
    control = json.loads((ROOT / 'docs/v4/evaluation85/test_control.json').read_bytes())
    work = _private(args.workdir.resolve())
    cli = _private(work / 'cli')
    executable = cli / 'claude'
    _write(executable, FAKE.format(python=sys.executable, hang=args.hang_seconds,
                                   text=repr(json.dumps(control['proposal']))).encode(), 0o700)
    (cli / 'mode').write_text(args.mode)
    sources = _private(work / 'sources')
    document, customer = sources / 'document.json', sources / 'customer.json'
    _write(document, (json.dumps(control['document'], indent=2) + '\n').encode())
    _write(customer, (json.dumps(control['customer'], indent=2) + '\n').encode())
    protected = _private(work / 'protected')
    approvals = protected / 'approvals.json'
    config = protected / 'public-proposal-config.json'
    _write(config, json.dumps({'version': 1, 'executable': str(executable), 'approvals_path': str(approvals),
                               'kinds': ['vendor']}).encode())
    attempt = _private(work / 'attempts') / 'attempt-dryrun'
    prepared = harness.prepare_case(case_id='dryrun-control', family='monthly_tier', document_path=document,
                                    customer_path=customer, document_sha256=sha256(document.read_bytes()).hexdigest(),
                                    customer_sha256=sha256(customer.read_bytes()).hexdigest(), config_path=config,
                                    attempt_dir=attempt, tenant='dryrun-tenant', subject='dryrun-subject')
    public_proposals.approve(attempt / 'request-export.json', approvals, approved_by='dryrun-harness-operator',
                             expected_digest=prepared['request_sha256'], public_confirmed=True)
    started = time.monotonic()
    report = harness.run_attempt(attempt_dir=attempt, config_path=config)
    elapsed = round(time.monotonic() - started, 3)
    invocations = (cli / 'invocations.log').read_text().splitlines()
    second = None
    try:
        harness.run_attempt(attempt_dir=attempt, config_path=config)
    except FileExistsError:
        second = 'FileExistsError'
    receipt = {
        'schema': 'evaluation85-transport-dryrun/1', 'mode': args.mode, 'hang_seconds': args.hang_seconds,
        'classification': 'controlled fake CLI through real SafePublicClaude; not a model call; not corpus data',
        'runner_constants': {'provider_bound': harness.PROVIDER_BOUND_SECONDS, 'poll': harness.POLL_SECONDS,
                             'shutdown': harness.SHUTDOWN_SECONDS},
        'elapsed_seconds': elapsed, 'report': report,
        'fake_cli_invocations': {'help': sum('--help' in line for line in invocations),
                                 'version': sum('--version' in line for line in invocations),
                                 'model_calls': sum('--model' in line for line in invocations)},
        'second_run': second,
    }
    _write(args.receipt, (json.dumps(receipt, indent=2) + '\n').encode(), 0o644)
    print(json.dumps({k: receipt[k] for k in ('mode', 'elapsed_seconds', 'fake_cli_invocations', 'second_run')}))
    print(json.dumps({'failure_stage': report['failure_stage'], 'extraction': report['extraction'],
                      'queue': report.get('queue')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
