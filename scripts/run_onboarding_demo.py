#!/usr/bin/env python3
"""Drive model-assisted onboarding of one public or authored source through the ordinary signed routes.

Each step is explicit and separate:
- `access`: read-only selection view;
- `submit`: queue the family proposals, only when every exact request is already approved by the operator CLI;
- `wait`: read-only GET polling;
- `stage`: stage a SHADOW candidate only from a SELECTED outcome;
- `record`: write inspectable evidence.

Nothing is approved, activated, retried or replaced here. The reviewer credential is read locally to sign requests
and is never written to the evidence.
"""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.auth_client import ReviewerClient  # noqa: E402

TERMINAL = {'SUCCEEDED', 'REFUSED', 'CANCELLED', 'UNCERTAIN'}


def connect(origin, account, credential):
    return ReviewerClient(httpx.Client(base_url=origin, timeout=60), origin, account, json.loads(Path(credential).read_text()))


def get(reviewer, path):
    response = reviewer.client.get(path, headers=reviewer.headers)
    response.raise_for_status()
    return response.json()


def post(reviewer, path, payload):
    response = reviewer.post(path, payload)
    if response.status_code >= 400:
        raise SystemExit(f'{path}: HTTP {response.status_code}: {response.text[:400]}')
    return response.json()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=['access', 'submit', 'wait', 'stage', 'record'])
    parser.add_argument('--origin', required=True)
    parser.add_argument('--account', required=True)
    parser.add_argument('--credential', type=Path, required=True, help='Private reviewer JWK, outside the repository')
    parser.add_argument('--vendor', required=True)
    parser.add_argument('--document', type=Path, required=True)
    parser.add_argument('--attempt-nonce', default='initial')
    parser.add_argument('--overlay', type=Path, help='Private customer overlay for stage')
    parser.add_argument('--evidence', type=Path, help='New JSON file for record')
    parser.add_argument('--timeout-minutes', type=float, default=15)
    args = parser.parse_args(argv)
    reviewer = connect(args.origin, args.account, args.credential)
    document = json.loads(args.document.read_text())
    body = {'document': document, 'profile': 'auto', 'attempt_nonce': args.attempt_nonce}
    base = '/api/vendors/' + args.vendor
    view = post(reviewer, base + '/proposal-access', body)
    if args.step == 'access':
        print(json.dumps({'outcome': view['outcome'], 'selected': view['selected'], 'offline': view['offline'],
                          'families': [{k: f.get(k) for k in ('family', 'state', 'enabled', 'approval_reason', 'request_sha256')}
                                       | {'job': (f.get('job') or {}).get('job_id')} for f in view['families']],
                          'review_requirements': view['review_requirements']}, indent=2))
    elif args.step == 'submit':
        if view['outcome'] != 'NOT_SUBMITTED':
            raise SystemExit(f"Not submitting: outcome is {view['outcome']}. {' '.join(view['review_requirements'])}")
        view = post(reviewer, base + '/proposal-jobs', body)
        print(json.dumps({'outcome': view['outcome'], 'jobs': [(f['family'], (f.get('job') or {}).get('job_id'),
                                                                 (f.get('job') or {}).get('status')) for f in view['families']]}, indent=2))
    elif args.step == 'wait':
        jobs = [(f['family'], f['job']['job_id']) for f in view['families'] if f.get('job')]
        deadline = time.monotonic() + args.timeout_minutes * 60
        while True:
            states = {family: get(reviewer, f'{base}/proposal-jobs/{job}')['status'] for family, job in jobs}
            print(datetime.now(UTC).isoformat(timespec='seconds'), states, flush=True)
            if all(state in TERMINAL for state in states.values()) or time.monotonic() > deadline:
                break
            time.sleep(10)
    elif args.step == 'stage':
        selected = view['selected']
        if view['outcome'] != 'SELECTED' or not selected:
            raise SystemExit(f"Nothing to stage: outcome is {view['outcome']}.")
        overlay = json.loads(args.overlay.read_text())
        if selected['method'] == 'deterministic_document_parser':
            staged = post(reviewer, base + '/candidates', {'document': document, 'overlay': overlay})
        else:
            staged = post(reviewer, f"{base}/proposal-jobs/{selected['job_id']}/candidate", {'overlay': overlay})
        print(json.dumps({k: staged.get(k) for k in ('state', 'version', 'revision', 'active_version', 'actions')}, indent=2))
    else:
        if args.evidence is None or args.evidence.exists():
            raise SystemExit('record needs a new --evidence path.')
        jobs = {f['family']: get(reviewer, f"{base}/proposal-jobs/{f['job']['job_id']}") for f in view['families'] if f.get('job')}
        try:
            vendor = get(reviewer, base)
            requirements = get(reviewer, base + '/requirements')
        except httpx.HTTPStatusError:
            vendor, requirements = None, None
        record = {'recorded_at': datetime.now(UTC).isoformat(), 'origin': args.origin, 'account': args.account,
                  'vendor_id': args.vendor, 'document': {k: document[k] for k in ('name', 'uri', 'classification')},
                  'source_text': document['text'], 'selection': view, 'jobs': jobs,
                  'adapter': None if vendor is None else {k: vendor.get(k) for k in (
                      'state', 'version', 'revision', 'active_version', 'reviewer', 'actions', 'extraction', 'manifest', 'overlay')},
                  'requirements': requirements}
        args.evidence.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
        print('Evidence written:', args.evidence)


if __name__ == '__main__':
    main()
