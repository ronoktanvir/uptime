#!/usr/bin/env python3
"""Review and approve exact authored-public requests outside the web application.

This approves a bounded model invocation only. It does not create an actual human
review record, source authority, adapter approval or financial permission.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.correspondence_model_transport import strict_json
from uptime.public_proposal_jobs import canonical, load_approvals
from uptime.source_config import _protected_path


def read_export(path):
    path = Path(path)
    if path.stat().st_size > 100000:
        raise ValueError('Request export exceeds its limit.')
    value = strict_json(path.read_bytes())
    expected = {'tenant', 'subject', 'kind', 'target', 'context_sha256', 'request', 'source_references'}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError('Use the complete application request export with its source references.')
    encoded = canonical(value['request'])
    if len(encoded) > 80000:
        raise ValueError('Request exceeds the invocation limit.')
    return value, sha256(encoded).hexdigest()


def approve(export_path, approvals_path, *, approved_by, expected_digest, public_confirmed, hours=24):
    if not public_confirmed:
        raise PermissionError('Only deliberately authorized authored-public source requests may be approved.')
    if not 1 <= hours <= 168:
        raise ValueError('Approval must expire within one week.')
    exported, digest = read_export(export_path)
    if digest != expected_digest:
        raise ValueError('The reviewed complete request hash does not match.')
    path = _protected_path(approvals_path)
    if path.parent.stat().st_mode & 0o077:
        raise PermissionError('Use an owner-only approval directory.')
    old = load_approvals(path) if path.exists() else dict(version=1, limits=dict(daily_jobs=20, daily_budget_usd='20.00'), approvals=[])
    now = datetime.now(timezone.utc)
    entry = {**exported, 'approved_by': approved_by, 'approved_at': now.isoformat(), 'expires_at': (now+timedelta(hours=hours)).isoformat()}
    keys = ('tenant', 'subject', 'kind', 'target', 'context_sha256')
    # Renewal replaces the same exact grant; terminal job records remain intact.
    old['approvals'] = [item for item in old['approvals'] if not (
        all(item[k] == entry[k] for k in keys) and canonical(item['request']) == canonical(entry['request']))] + [entry]
    handle = tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.proposal-approval-', delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(old, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        load_approvals(temporary)
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(request_sha256=digest, expires_at=entry['expires_at'], scope='model invocation only')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    show = sub.add_parser('show', help='Display the complete request and its stable hash for review')
    show.add_argument('request_file', type=Path)
    grant = sub.add_parser('approve', help='Add the reviewed authored-public request to a protected allowlist')
    grant.add_argument('request_file', type=Path)
    grant.add_argument('--approvals', type=Path, required=True)
    grant.add_argument('--approved-by', required=True)
    grant.add_argument('--expected-request-sha256', required=True)
    grant.add_argument('--confirm-authored-public', action='store_true')
    grant.add_argument('--hours', type=int, default=24)
    args = parser.parse_args()
    try:
        if args.command == 'show':
            value, digest = read_export(args.request_file)
            print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
            print('Complete request SHA256:', digest)
        else:
            result = approve(args.request_file, args.approvals, approved_by=args.approved_by,
                             expected_digest=args.expected_request_sha256, public_confirmed=args.confirm_authored_public,
                             hours=args.hours)
            print(json.dumps(result, indent=2))
    except (ValueError, PermissionError, OSError):
        parser.exit(1, 'Approval was not written. Check the complete export, reviewed digest, public authorization and protected paths.\n')


if __name__ == '__main__':
    main()
