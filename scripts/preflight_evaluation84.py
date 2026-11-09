#!/usr/bin/env python3
"""Offline pre-inference validation of the frozen evaluation84 corpus against the current source.

No model, CLI, network, application server or database is used. Sealed gold is never opened:
only `os.lstat` metadata (existence, owner, mode) is recorded. Public inputs are checked against
the manifest pins and the frozen commit's Git blobs, then against the current runner input
contracts (onboarding) and the current claim `Scope` schema (disputes).

The dispute check reports which pending team decision blocks normal claim intake. It never fills a
missing scope field, slugs a name or invents an invoice/incident/region to make a case fit.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MANIFEST = 'docs/v4/evaluation84/manifest.json'
CORPUS_COMMIT = '042d701da9c6c05f44c523939241b18ee1d579ed'
SCHEMA = 'evaluation84-preflight/1'
# Scope fields whose value domain is the D03 identity question.
IDENTITY_FIELDS = frozenset({'account', 'contract'})
# Scope fields whose universal requirement is the D04 scope-variant question.
SCOPE_FIELDS = frozenset({'component', 'invoice', 'incident', 'region'})


def _hash(data):
    return sha256(data).hexdigest()


def _git_blob(path):
    """Frozen-commit bytes, or None when that commit is absent (for example a shallow clone)."""
    result = subprocess.run(['git', 'show', f'{CORPUS_COMMIT}:{path}'], cwd=ROOT, capture_output=True, timeout=30)
    return result.stdout if result.returncode == 0 else None


def _gold_metadata(root, relative):
    """lstat only: the sealed file is never opened, read or hashed here."""
    path = Path(root) / relative
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return {'present': False}
    return {'present': True, 'regular': stat.S_ISREG(info.st_mode), 'owner_only': stat.S_IMODE(info.st_mode) & 0o077 == 0,
            'owned_by_operator': info.st_uid == os.getuid()}


def _pins(manifest):
    files = []
    for entry in manifest['files']:
        raw = (ROOT / entry['path']).read_bytes()
        blob = _git_blob(entry['path'])
        files.append({'path': entry['path'], 'manifest_match': _hash(raw) == entry['sha256'] and len(raw) == entry['bytes'],
                      'frozen_commit_match': None if blob is None else blob == raw})
    return files


def onboarding_case(entry):
    from scripts import evaluate_onboarding_85 as runner
    from scripts.public_proposals import _read_document
    from uptime.vendor_model import proposal_input
    from uptime.vendor_model_jobs import ProposalRequest
    result = {'id': entry['id'], 'profile': entry['profile'], 'checks': {}}
    document_path, customer_path = ROOT / entry['public_document'], ROOT / entry['local_customer']
    pins = {item['path']: item['sha256'] for item in json.loads((ROOT / MANIFEST).read_bytes())['files']}
    checks = result['checks']
    try:
        runner._input(document_path, 'document.json', pins[entry['public_document']])
        customer = runner._customer(runner._input(customer_path, 'customer.json', pins[entry['local_customer']]))
        document = _read_document(document_path)
        checks['runner_inputs'] = 'ACCEPTED'
    except (ValueError, OSError) as error:
        checks['runner_inputs'] = f'REFUSED:{type(error).__name__}'
        return result
    checks['runner_family_route'] = runner.PROFILES.get(entry['id']) == entry['profile']
    try:
        request = ProposalRequest(document=document, profile=entry['profile'], attempt_nonce='initial')
        proposal_input(request.document, entry['profile'])
        checks['profile_input'] = 'ACCEPTED'
    except (ValueError, TypeError) as error:
        checks['profile_input'] = f'REFUSED:{type(error).__name__}'
    checks['scenarios'] = [scenario['name'] for scenario in customer['scenarios']]
    # The runner signs as a DraftReviewer. vendor_api only resolves governing-fee contexts for
    # non-draft principals, so an authored fee source cannot become fee authority on this path.
    checks['governing_fee_source_supplied'] = 'governing_fee_source' in customer
    checks['fee_authority_reachable_on_draft_path'] = False
    return result


def _derived_scope(source):
    """Only values literally present in the frozen reply context; nothing is invented."""
    context = source['context']
    scope = {'account': context.get('account'), 'vendor': source.get('vendor'), 'contract': context.get('agreement'),
             'service': context.get('product'), 'currency': context.get('currency'), 'month': context.get('month')}
    return {key: value for key, value in scope.items() if value is not None}


def dispute_case(entry):
    from pydantic import ValidationError
    from uptime.correspondence_types import Claim
    source = json.loads((ROOT / entry['public_source']).read_bytes())
    context = source['context']
    claim = {'claim_id': 'inbox-' + context['claim_ref'], 'scope': _derived_scope(source)}
    blockers = {'D03': [], 'D04': [], 'other': []}
    try:
        Claim.model_validate(claim)
        outcome = 'SCOPE_ACCEPTED'
    except ValidationError as error:
        outcome = 'SCOPE_REFUSED'
        for item in error.errors():
            field = item['loc'][-1] if item['loc'] else None
            bucket = 'D03' if field in IDENTITY_FIELDS else 'D04' if field in SCOPE_FIELDS else 'other'
            blockers[bucket].append({'field': field, 'type': item['type']})
    basis = context.get('claim_basis') or {}
    return {'id': entry['id'], 'route': '/api/correspondence/claims', 'outcome': outcome,
            'claim_basis_contract': Path(basis.get('document_path', '')).parent.name or None,
            'blockers': {key: sorted(value, key=lambda item: item['field'] or '') for key, value in blockers.items()},
            'model_calls': 0}


def claim_basis_activation(disputes):
    """Can each dispute claim-basis contract enter the deterministic (no-model) candidate route?

    In-process app on a temporary database with the scripted local reviewer; no network, model or
    gold. Claims resolve terms only through an ACTIVE adapter (uptime/v4_routes.resolve_active), so a
    contract that cannot reach SHADOW here cannot back a submitted claim without another path.
    """
    import secrets
    import tempfile
    from fastapi.testclient import TestClient
    from uptime.auth import DEFAULT_ORIGIN, SCRIPT
    from uptime.auth_client import ReviewerClient
    from uptime.server import create_app
    results = {}
    for name in sorted({case['claim_basis_contract'] for case in disputes if case['claim_basis_contract']}):
        folder = ROOT / 'fixtures/evaluation84_public/onboarding' / name
        document = json.loads((folder / 'document.json').read_bytes())
        overlay = json.loads((folder / 'customer.json').read_bytes())['overlay']
        from unittest.mock import patch
        clean = {k: v for k, v in os.environ.items() if k not in ('UPTIME_PUBLIC_EXTRACTIONS', 'UPTIME_MODEL_PROPOSITIONS')}
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, clean, clear=True):
            key = secrets.token_urlsafe(32)
            app = create_app(Path(temporary) / 'setup.db', rehearsal=True, rehearsal_secret=key, approvals_enabled=True)
            with TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 4510)) as client:
                response = ReviewerClient(client, DEFAULT_ORIGIN, SCRIPT, key).post(
                    '/api/vendors/v-claim-basis/candidates', dict(document=document, overlay=overlay))
                body = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
        results[name] = {'route': 'deterministic candidate (no model)', 'http_status': response.status_code,
                         'state': body.get('state'), 'reason': body.get('reason'),
                         'dispute_cases': sum(1 for case in disputes if case['claim_basis_contract'] == name)}
    return results


def build(gold_root=None):
    manifest = json.loads((ROOT / MANIFEST).read_bytes())
    gold_root = gold_root or manifest['sealed_gold_root']
    entries = manifest['entries']
    onboarding = [onboarding_case(entry) for entry in entries if entry['kind'] == 'onboarding']
    disputes = [dispute_case(entry) for entry in entries if entry['kind'] == 'dispute']
    gold = {entry['id']: _gold_metadata(gold_root, entry['gold_relative_path']) for entry in entries}
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    blocked = [case['id'] for case in disputes if case['outcome'] != 'SCOPE_ACCEPTED']
    pins = _pins(manifest)
    activation = claim_basis_activation(disputes)
    return {
        'schema': SCHEMA, 'at': datetime.now(UTC).isoformat(), 'source_head': head, 'corpus_commit': CORPUS_COMMIT,
        'manifest_sha256': _hash((ROOT / MANIFEST).read_bytes()),
        'model_calls': 0, 'gold_opened': False, 'network': False,
        'pins': pins, 'gold_metadata': gold, 'onboarding': onboarding, 'disputes': disputes,
        'claim_basis_activation': activation,
        'summary': {
            'inputs_pinned': all(item['manifest_match'] for item in pins),
            'frozen_commit_verified': all(item['frozen_commit_match'] is True for item in pins),
            'frozen_commit_mismatch': sum(1 for item in pins if item['frozen_commit_match'] is False),
            'sealed_gold_present': sum(1 for value in gold.values() if value.get('present')),
            'onboarding_runner_inputs_accepted': sum(1 for case in onboarding if case['checks'].get('runner_inputs') == 'ACCEPTED'),
            'onboarding_profile_inputs_accepted': sum(1 for case in onboarding if case['checks'].get('profile_input') == 'ACCEPTED'),
            'dispute_scope_blocked': len(blocked),
            'dispute_blocked_by_D03': sum(1 for case in disputes if case['blockers']['D03']),
            'dispute_blocked_by_D04': sum(1 for case in disputes if case['blockers']['D04']),
            'dispute_blocked_other': sum(1 for case in disputes if case['blockers']['other']),
            'claim_basis_contracts_reaching_shadow': sum(1 for value in activation.values() if value['state'] in ('SHADOW', 'ACTIVE')),
            'dispute_cases_without_activatable_claim_basis': sum(value['dispute_cases'] for value in activation.values()
                                                                 if value['state'] not in ('SHADOW', 'ACTIVE')),
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', help='Create-only output path; prints to stdout when omitted.')
    args = parser.parse_args(argv)
    data = (json.dumps(build(), indent=2, ensure_ascii=False) + '\n').encode()
    if args.receipt:
        fd = os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o644)
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
    else:
        sys.stdout.write(data.decode())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
