#!/usr/bin/env python3
"""Export, review and approve exact authored-public requests outside the web application.

Exporting writes a readable request for review and grants no permission. Approval
covers a bounded model invocation only. Neither creates an actual human review
record, source authority, adapter approval or financial permission.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.correspondence_model_transport import strict_json
from uptime.public_proposal_jobs import canonical, load_approvals
from uptime.public_proposal_config import PublicProposalConfig
from uptime.contracts import DraftReviewer
from uptime.source_config import _protected_path, load_private
from uptime.vendor_model_jobs import ProposalRequest, build_vendor_provider, public_approval_request

EXPORT_FIELDS = frozenset({'tenant', 'subject', 'kind', 'target', 'context_sha256', 'request', 'source_references'})
DOCUMENT_FIELDS = frozenset({'name', 'classification', 'uri', 'text'})
PROFILES = ('monthly', 'monthly-propositions', 'resource-month')
MAX_EXPORT_BYTES = 100000
MAX_REQUEST_BYTES = 80000
MAX_DOCUMENT_BYTES = 80000
EXPORT_NOTICE = ('This export grants no permission: nothing was approved or queued; no model was invoked. '
                 'Review it with show and approve it separately.')


def _request_digest(value):
    if not isinstance(value, dict) or set(value) != EXPORT_FIELDS:
        raise ValueError('Use the complete application request export with its source references.')
    encoded = canonical(value['request'])
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError('Request exceeds the invocation limit.')
    return sha256(encoded).hexdigest()


def read_export(path):
    path = Path(path)
    if path.stat().st_size > MAX_EXPORT_BYTES:
        raise ValueError('Request export exceeds its limit.')
    value = strict_json(path.read_bytes())
    return value, _request_digest(value)


def _opaque(value, name):
    """Bounded printable opaque identifier; the export binds it but never interprets it."""
    if not isinstance(value, str) or not 0 < len(value) <= 160 or not value.isprintable() or value != value.strip():
        raise ValueError(f'Use a bounded printable {name}.')
    return value


def _read_document(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Use a regular public document file.')
        raw = b''
        while len(raw) <= MAX_DOCUMENT_BYTES:
            chunk = os.read(fd, MAX_DOCUMENT_BYTES + 1 - len(raw))
            if not chunk:
                break
            raw += chunk
    finally:
        os.close(fd)
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError('Public document exceeds its limit.')
    # Strict UTF-8 and strict JSON; the decoded text, including any CRLF, is passed on unchanged.
    document = strict_json(raw.decode('utf-8'))
    if (not isinstance(document, dict) or set(document) != DOCUMENT_FIELDS
            or not all(isinstance(document[field], str) for field in DOCUMENT_FIELDS)
            or document['classification'] not in ('synthetic_public', 'public')):
        raise ValueError('Use one authored-public document with only name, classification, uri and text.')
    return document


def _private_directory(info):
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise PermissionError('Use an existing owner-only 0700 output directory.')


def _new_output(output_path):
    path = _protected_path(output_path)  # absolute, resolved, outside Git, operator-owned parent
    if Path(output_path) != path:
        raise ValueError('Use an absolute resolved output path without symlinks or traversal.')
    _private_directory(os.lstat(path.parent))
    if os.path.lexists(path):
        raise FileExistsError('The request export already exists; choose a new output path.')
    return path


def _write_new(path, data):
    """Create the export exclusively without following links; remove it again if anything fails."""
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        _private_directory(os.fstat(directory))
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
                     dir_fd=directory)
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError('Export write made no progress.')
                view = view[written:]
            os.fsync(fd)
            os.fsync(directory)
        except BaseException:
            os.unlink(path.name, dir_fd=directory)
            raise
        finally:
            os.close(fd)
    finally:
        os.close(directory)


def export_vendor(document_path, config_path, output_path, *, tenant, subject, target, profile,
                  attempt_nonce='initial'):
    """Write the exact readable vendor request for separate review.

    Only the pinned provider constructor runs (its --help/--version checks). The provider is
    never called, and nothing is approved, queued or written to the approval allowlist or DB.
    """
    tenant, subject = _opaque(tenant, 'tenant'), _opaque(subject, 'subject')
    attempt_nonce = _opaque(attempt_nonce, 'attempt nonce')
    if profile not in PROFILES:
        raise ValueError('Use a supported vendor profile.')
    if not isinstance(target, str):
        raise ValueError('Use a target string.')
    output = _new_output(output_path)
    document = _read_document(document_path)
    config = load_private(config_path, PublicProposalConfig)
    if list(config.kinds).count('vendor') != 1 or len(config.kinds) != len(set(config.kinds)):
        raise PermissionError('Enable the vendor proposal kind once in the protected server config.')
    executable = config.executable
    if not (os.path.isabs(executable) and os.path.isfile(executable) and os.access(executable, os.X_OK)):
        raise PermissionError('Configure an absolute executable file for the vendor provider.')
    approval_path = _protected_path(config.approvals_path)
    if output == approval_path:
        raise PermissionError('Never write a request export at the approval allowlist path.')
    body = ProposalRequest(document=document, profile=profile, attempt_nonce=attempt_nonce)
    provider = build_vendor_provider(executable)
    exported = public_approval_request(provider, DraftReviewer(tenant, subject, 'reviewer'), target, body)
    digest = _request_digest(exported)
    references = exported['source_references']
    if ((exported['tenant'], exported['subject'], exported['kind'], exported['target']) != (tenant, subject, 'vendor', target)
            or not isinstance(exported['request'], dict) or not isinstance(references, list) or not references
            or not all(isinstance(item, dict) and set(item) == {'reference', 'sha256'} for item in references)):
        raise ValueError('The vendor request export does not match the requested public binding.')
    try:
        data = (json.dumps(exported, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    except TypeError as error:
        raise ValueError('The vendor request export is not plain JSON.') from error
    if len(data) > MAX_EXPORT_BYTES or canonical(strict_json(data)) != canonical(exported):
        raise ValueError('Request export exceeds its limit or does not round-trip exactly.')
    _write_new(output, data)
    return dict(output_path=str(output), request_sha256=digest, permission=EXPORT_NOTICE)


def export_vendor_auto(document_path, config_path, output_path, *, tenant, subject, target, attempt_nonce='initial'):
    """Automatic family selection (D05): one exact export per supported family, written beside output_path.

    The application evaluates every supported family for one source, so the operator reviews and approves
    each family's exact request separately. Every output must be new before any is written. Nothing is
    approved, queued or sent to a model.
    """
    from uptime.vendor_family_selection import FAMILIES
    output_path = Path(output_path)
    if output_path.suffix != '.json':
        raise ValueError('Use a .json output path; one file per family is written beside it.')
    targets = [(profile, output_path.with_name(f'{output_path.stem}.{profile}.json')) for _, profile, _ in FAMILIES]
    if any(path.exists() or path.is_symlink() for _, path in targets):
        raise ValueError('Every family export path must be new.')
    return [dict(export_vendor(document_path, config_path, path, tenant=tenant, subject=subject, target=target,
                               profile=profile, attempt_nonce=attempt_nonce), profile=profile) for profile, path in targets]


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
    export = sub.add_parser('export-vendor', help='Write the exact authored-public vendor request for review; grants no permission')
    export.add_argument('--document', type=Path, required=True)
    export.add_argument('--config', type=Path, required=True)
    export.add_argument('--output', type=Path, required=True)
    export.add_argument('--tenant', required=True)
    export.add_argument('--subject', required=True)
    export.add_argument('--target', required=True)
    export.add_argument('--profile', required=True, choices=PROFILES + ('auto',),
                        help='"auto" writes one export per supported family for automatic family selection')
    export.add_argument('--attempt-nonce', default='initial')
    args = parser.parse_args()
    try:
        if args.command == 'show':
            value, digest = read_export(args.request_file)
            print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
            print('Complete request SHA256:', digest)
        elif args.command == 'export-vendor' and args.profile == 'auto':
            for result in export_vendor_auto(args.document, args.config, args.output, tenant=args.tenant,
                                             subject=args.subject, target=args.target, attempt_nonce=args.attempt_nonce):
                print('Family profile:', result['profile'])
                print('Request export:', result['output_path'])
                print('Complete request SHA256:', result['request_sha256'])
            print(EXPORT_NOTICE, 'Approve each family request separately; automatic selection needs all of them.')
        elif args.command == 'export-vendor':
            result = export_vendor(args.document, args.config, args.output, tenant=args.tenant, subject=args.subject,
                                   target=args.target, profile=args.profile, attempt_nonce=args.attempt_nonce)
            print('Request export:', result['output_path'])
            print('Complete request SHA256:', result['request_sha256'])
            print(result['permission'])
        else:
            result = approve(args.request_file, args.approvals, approved_by=args.approved_by,
                             expected_digest=args.expected_request_sha256, public_confirmed=args.confirm_authored_public,
                             hours=args.hours)
            print(json.dumps(result, indent=2))
    except (ValueError, PermissionError, OSError):
        if args.command == 'export-vendor':
            parser.exit(1, 'Request export was not written. Check the authored-public document, protected config, '
                           'enabled vendor executable and new owner-only output path.\n')
        parser.exit(1, 'Approval was not written. Check the complete export, reviewed digest, public authorization and protected paths.\n')


if __name__ == '__main__':
    main()
