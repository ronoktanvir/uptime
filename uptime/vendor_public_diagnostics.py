"""Explicit offline public attachments, independently checked before a detail view.

Intake reads one operator-selected attachment for the exact approved public source.
It never traverses rejection archives or executes a model, and never reads overlays.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from .contracts import fingerprint
from .vendor_model import _save_immutable_json, replay_rejection
from .vendor_resource_terms import public_blocks
from .vendor_terms import Document, _validate_document, semantics_revision

SCHEMA = 'public-source-diagnostics/1'
REASONS = {
    'UNSUPPORTED_BLOCK_PROPOSITION': 'This block contains an unsupported proposed effect. Review its public terms and supported operators before preparing a fresh extraction.',
    'ISSUER_AUTHORITY_UNESTABLISHED': 'This block does not establish the proposed issuer verification authority. Customer records and custodian statements establish their stated evidence roles.',
    'PUBLIC_PROPOSITION_UNESTABLISHED': 'The proposed effect could not be established from this public source. Review the cited block before preparing a fresh extraction.',
}
REPORT_FIELDS = {'schema','source_sha256','source_uri','receipt_sha256','validator_revision','protocol','historical_status','issues'}
ISSUE_FIELDS = {'code','block','start','end','quote','block_sha256'}
MAX_ATTACHMENT_BYTES = 160_000
MAX_QUOTE_BYTES = 4096


def _hex(value):
    return isinstance(value, str) and bool(re.fullmatch('[0-9a-f]{64}', value))


def _code(reason):
    if reason in {'Issuer verification is not established by this public source block.',
                  'Proposed evidence category lacks source wording: verification'}:
        return 'ISSUER_AUTHORITY_UNESTABLISHED'
    if re.fullmatch(r'Unsupported material in resource clause [0-9]+\.', reason):
        return 'UNSUPPORTED_BLOCK_PROPOSITION'
    return 'PUBLIC_PROPOSITION_UNESTABLISHED'


def _checked_report(document, attachment):
    _validate_document(document)
    if (not isinstance(attachment, dict) or set(attachment) != {'sha256','report'}
            or not _hex(attachment['sha256']) or fingerprint(attachment['report']) != attachment['sha256']):
        raise ValueError('Invalid public diagnostic content address.')
    report = attachment['report']
    if (not isinstance(report, dict) or set(report) != REPORT_FIELDS or report['schema'] != SCHEMA
            or report['source_sha256'] != sha256(document.text.encode()).hexdigest()
            or report['source_uri'] != document.uri or not _hex(report['receipt_sha256'])
            or report['historical_status'] != 'REJECTED'
            or report['validator_revision'] != semantics_revision({'family':'resource-month/1'})
            or report['protocol'] not in ('public_block_ids/1','public_block_ids/2')
            or not isinstance(report['issues'], list) or not 1 <= len(report['issues']) <= 32):
        raise ValueError('Unmatched or stale public diagnostic.')
    blocks = public_blocks(document.text, protocol=report['protocol'])
    for issue in report['issues']:
        if (not isinstance(issue, dict) or set(issue) != ISSUE_FIELDS or issue['code'] not in REASONS
                or type(issue['block']) is not int or not 1 <= issue['block'] <= len(blocks)):
            raise ValueError('Unsupported public diagnostic issue.')
        block = blocks[issue['block']-1]
        if (type(issue['start']) is not int or type(issue['end']) is not int
                or (issue['start'], issue['end'], issue['block_sha256'], issue['quote']) !=
                   (block['start'], block['end'], block['sha256'], block['text'])
                or len(issue['quote'].encode()) > MAX_QUOTE_BYTES):
            raise ValueError('Public diagnostic span is invalid or oversized.')
    return report


def create_attachment(document, receipt_path, approved_digest):
    replay = replay_rejection(document, receipt_path, approved_digest)
    receipt = json.loads(receipt_path.read_text())
    if (replay['current_validation'] != 'REJECTED' or receipt.get('profile') != 'resource-month'
            or not replay.get('diagnostics')):
        raise ValueError('A currently rejected public resource proposal is required.')
    protocol = receipt.get('protocol', 'public_block_ids/1')
    blocks = public_blocks(document.text, protocol=protocol)
    issues = []
    for problem in replay['diagnostics']:
        index = problem.get('block')
        if type(index) is not int or not 1 <= index <= len(blocks):
            raise ValueError('An exact public source block is required for an attachment.')
        block = blocks[index-1]
        issue = dict(code=_code(problem['reason']), block=index, start=block['start'], end=block['end'],
                     quote=block['text'], block_sha256=block['sha256'])
        if issue not in issues:
            issues.append(issue)
    report = dict(schema=SCHEMA, source_sha256=approved_digest, source_uri=document.uri,
                  receipt_sha256=fingerprint(receipt), validator_revision=semantics_revision({'family':'resource-month/1'}),
                  protocol=protocol, historical_status='REJECTED', issues=issues)
    attachment = dict(sha256=fingerprint(report), report=report)
    _checked_report(document, attachment)
    return attachment


def publish_attachment(document, attachment, directory):
    report = _checked_report(document, attachment)
    path = _save_immutable_json(report, directory/'public-diagnostics')
    # The operator explicitly selects this immutable report for this exact source.
    # Normal intake resolves this small pointer and never searches a rejection archive.
    pointer = directory/(report['source_sha256']+'.diagnostic.json')
    with NamedTemporaryFile(dir=directory, mode='w', delete=False) as temp:
        temporary = Path(temp.name)
        json.dump({'sha256':attachment['sha256']}, temp)
        temp.flush()
        os.fsync(temp.fileno())
    try:
        temporary.chmod(0o400)
        os.replace(temporary, pointer)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def selected_attachment(document):
    """Read the operator's explicit public attachment, with generic failure fallback."""
    try:
        directory = os.getenv('UPTIME_PUBLIC_EXTRACTIONS')
        if not directory:
            return None
        _validate_document(document)
        root = Path(directory)
        pointer = root/(sha256(document.text.encode()).hexdigest()+'.diagnostic.json')
        if pointer.is_symlink() or pointer.stat().st_size > 512:
            return None
        selection = json.loads(pointer.read_bytes())
        if not isinstance(selection, dict) or set(selection) != {'sha256'} or not _hex(selection['sha256']):
            return None
        folder = root/'public-diagnostics'
        path = folder/(selection['sha256']+'.json')
        if folder.is_symlink() or path.is_symlink() or path.stat().st_size > MAX_ATTACHMENT_BYTES:
            return None
        attachment = selection | {'report':json.loads(path.read_bytes())}
        _checked_report(document, attachment)
        return attachment
    except (OSError, ValueError, TypeError, KeyError):
        return None


def public_issues(document_data, attachment):
    """Build explanations solely from fixed codes and checked original public slices."""
    try:
        document = Document.model_validate(document_data)
        report = _checked_report(document, attachment)
        return [dict(issue, explanation=REASONS[issue['code']], source_uri=report['source_uri'],
                     source_sha256=report['source_sha256'], receipt_sha256=report['receipt_sha256'],
                     diagnostic_sha256=attachment['sha256'], historical_status='REJECTED') for issue in report['issues']]
    except (ValueError, TypeError, KeyError):
        return []
