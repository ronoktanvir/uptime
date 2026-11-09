"""Public diagnostics for refused vendor proposal jobs (decision 90 addendum).

A refused vendor proposal job used to expose only ``proposal_validation_failed``.
This module explains the refusal using only:

* fixed codes and fixed explanations from ``CODES``;
* names from the fixed ``TERM_LABELS`` vocabulary, and only where the validator
  itself established which required terms are absent;
* offsets into the exact public document that was submitted, with SHA-256 values.

The deterministic validator is re-run to obtain its own finding. Model output is
used only to locate the passage that finding names, and neither model text nor
exception text is ever copied out. A passage the extraction merely labels as
unsupported is not cited unless the validator refused because of it.

The stored record keeps the public document so that a read can recompute the job's
pinned ``context_sha256`` (the same check applied to succeeded results) and re-slice
every quote from verified bytes. A stale or inconsistent record is not shown.

This module is outside the reviewed-semantics file set, and the job hook below is a
subclass, so ``vendor_model_jobs.py`` (whose bytes are part of every proposal context
pin) is unchanged. Nothing here grants approval or adapter authority.
"""
from hashlib import sha256
import re

from .vendor_model_jobs import ProposalRefused, VendorModelJobs, _validated_result, proposal_context

SCHEMA = 'public-refusal-diagnostic/1'
CODES = {
    'UNSUPPORTED_SOURCE_MATERIAL': 'The validator could not represent this passage in the selected adapter family. '
                                   'The source needs a different supported family or manual handling.',
    'EXTRACTION_FLAGGED_UNSUPPORTED': 'The extraction marked this passage as outside the supported terms, and the '
                                      'validator refused on that basis. Review the passage before preparing a fresh extraction.',
    'UNSUPPORTED_BLOCK_PROPOSITION': 'This block contains an unsupported proposed effect. Review its public terms and '
                                     'supported operators before preparing a fresh extraction.',
    'ISSUER_AUTHORITY_UNESTABLISHED': 'This block does not establish the proposed issuer verification authority. '
                                      'Customer records and custodian statements establish their stated evidence roles.',
    'PUBLIC_PROPOSITION_UNESTABLISHED': 'The proposed reading could not be established from the public source. '
                                        'Review the source before preparing a fresh extraction.',
    'REQUIRED_TERMS_MISSING': 'No passage establishes the listed required terms. Without them this family cannot '
                              'produce an adapter.',
    'SOURCE_COVERAGE_INCOMPLETE': 'The source does not establish every term this adapter family requires.',
    'PROPOSAL_NOT_SOURCE_GROUNDED': 'The extraction did not quote the source exactly and completely, so no passage '
                                    'can be cited. Prepare a fresh extraction.',
    'OUTPUT_NOT_STRUCTURED': 'The extraction output was not in the required structured form.',
}
TERM_LABELS = {
    'vendor': 'vendor', 'agreement': 'agreement identifier', 'effective': 'effective dates',
    'period': 'measurement period', 'tier': 'credit tiers', 'tiers': 'credit tiers',
    'filing_days': 'claim filing deadline', 'filing': 'claim filing deadline', 'remedy': 'credit remedy',
    'fee_basis': 'eligible fee basis', 'evidence': 'evidence requirements', 'scope': 'covered service scope',
    'symptoms': 'qualifying symptoms', 'provider_causes': 'provider-caused conditions',
}
_PROPOSITION_REQUIRED = ('vendor', 'agreement', 'effective', 'period', 'filing_days', 'remedy')
_VALIDATOR_AT_CLAUSE = re.compile(r'(?:Unsupported source language|Unsupported percentage table|'
                                  r'Unsupported material qualification) at clause ([0-9]{1,3})\.')
_FLAGGED_AT_CLAUSE = re.compile(r'Model identified unsupported material at clause ([0-9]{1,3})\.')
_UNGROUNDED = {'Model proposal dropped or invented source material.', 'Incomplete proposed source coverage.',
               'Invalid proposed clause span.', 'Invalid proposed clause index.', 'Invalid public model proposal.',
               'Model must return exactly one effect record per source block.',
               'Missing, altered, duplicate or reordered immutable source block ID.'}
_RESOURCE_INCOMPLETE = re.compile(r'Incomplete resource-month source propositions: ([a-z_]+(?:, [a-z_]+)*)')
MAX_ISSUES = 32
MAX_QUOTE_BYTES = 4096
MAX_STORED_BYTES = 300_000
STORED_FIELDS = frozenset({'schema', 'profile', 'source_sha256', 'document', 'issues', 'missing_terms'})
STORED_ISSUE_FIELDS = frozenset({'code', 'block', 'start', 'end', 'block_sha256'})


def _issue(code, text=None, block=None, start=None, end=None):
    located = text is not None and start is not None
    return {'code': code, 'block': block if located else None, 'start': start if located else None,
            'end': end if located else None,
            'block_sha256': sha256(text[start:end].encode()).hexdigest() if located else None}


def _validator_message(document, profile, proposal):
    """Re-run the deterministic validator on the projected proposal; return its message or None."""
    from .vendor_model import PROPOSAL_PROFILES, _project, _resource_protocol, validate_proposal
    block_protocol = _resource_protocol(document)[1] if profile == 'resource-month' else 'public_block_ids/1'
    clauses, _ = _project(document, profile, proposal, block_protocol)
    try:
        validate_proposal(document, clauses, allow_propositions=PROPOSAL_PROFILES[profile])
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError) as exc:
        return clauses, str(exc)
    return clauses, None


def _monthly(document, profile, proposal):
    from .vendor_terms import _clauses
    try:
        clauses, message = _validator_message(document, profile, proposal)
    except (ValueError, TypeError, KeyError):
        return [_issue('OUTPUT_NOT_STRUCTURED')], []
    if message is None:
        return [], []
    if message in _UNGROUNDED:
        return [_issue('PROPOSAL_NOT_SOURCE_GROUNDED')], []
    try:
        spans = _clauses(document.text, [c.get('quote') if isinstance(c, dict) else None for c in clauses])
    except (ValueError, TypeError):
        return [_issue('PROPOSAL_NOT_SOURCE_GROUNDED')], []
    for pattern, code in ((_VALIDATOR_AT_CLAUSE, 'UNSUPPORTED_SOURCE_MATERIAL'),
                          (_FLAGGED_AT_CLAUSE, 'EXTRACTION_FLAGGED_UNSUPPORTED')):
        if (match := pattern.fullmatch(message)) and 1 <= int(match[1]) <= len(spans):
            start, end, _ = spans[int(match[1]) - 1]
            return [_issue(code, document.text, int(match[1]), start, end)], []
    if message == 'Incomplete model propositions.':
        # Raised only after every proposed field passed its own source check, so the present fields are validated.
        fields = {c['field'] for c in clauses if isinstance(c, dict) and isinstance(c.get('field'), str)}
        missing = sorted(TERM_LABELS[f] for f in set(_PROPOSITION_REQUIRED) - fields)
        if 'tier' not in fields:
            missing.append(TERM_LABELS['tier'])
        return ([_issue('REQUIRED_TERMS_MISSING')], sorted(missing)) if missing else ([_issue('SOURCE_COVERAGE_INCOMPLETE')], [])
    if message == 'Document lacks complete, unambiguous source coverage.':
        return [_issue('SOURCE_COVERAGE_INCOMPLETE')], []
    return [], []


def _resource(document, proposal):
    from .vendor_model import _resource_protocol
    from .vendor_public_diagnostics import _code
    from .vendor_resource_terms import diagnose_resource, project_blocks, public_blocks
    _, protocol = _resource_protocol(document)
    try:
        clauses, _ = project_blocks(document.text, proposal, protocol=protocol)
    except (ValueError, TypeError, KeyError):
        return [_issue('PROPOSAL_NOT_SOURCE_GROUNDED')], []
    blocks = public_blocks(document.text, protocol=protocol)
    issues, missing = [], []
    for problem in diagnose_resource(document, clauses):
        index, reason = problem.get('block'), problem.get('reason')
        if type(index) is int and 1 <= index <= len(blocks) and isinstance(reason, str):
            issue = _issue(_code(reason), document.text, index, blocks[index - 1]['start'], blocks[index - 1]['end'])
            if issue not in issues:
                issues.append(issue)
        elif isinstance(reason, str) and (match := _RESOURCE_INCOMPLETE.fullmatch(reason)):
            missing = sorted({TERM_LABELS[n] for n in match[1].split(', ') if n in TERM_LABELS})
    if missing:
        issues.append(_issue('REQUIRED_TERMS_MISSING'))
    return issues, missing


def build(document, profile, provider_result):
    """Stored diagnostic for one refused proposal, or None. Never raises."""
    from .correspondence_model_transport import strict_json
    try:
        try:
            proposal = strict_json(provider_result['text'])
        except (ValueError, TypeError, KeyError):
            issues, missing = [_issue('OUTPUT_NOT_STRUCTURED')], []
        else:
            if profile == 'resource-month':
                issues, missing = _resource(document, proposal)
            elif profile in ('monthly', 'monthly-propositions'):
                issues, missing = _monthly(document, profile, proposal)
            else:
                return None
        value = {'schema': SCHEMA, 'profile': profile, 'source_sha256': sha256(document.text.encode()).hexdigest(),
                 'document': document.model_dump(), 'missing_terms': missing,
                 'issues': (issues or [_issue('PUBLIC_PROPOSITION_UNESTABLISHED')])[:MAX_ISSUES]}
        return value if _stored_shape(value) else None
    except Exception:  # Optional; its absence leaves the generic refusal exactly as before.
        return None


def _hex(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def _stored_shape(value):
    if not isinstance(value, dict) or set(value) != STORED_FIELDS or value['schema'] != SCHEMA:
        return False
    if value['profile'] not in ('monthly', 'monthly-propositions', 'resource-month') or not _hex(value['source_sha256']):
        return False
    issues, missing = value['issues'], value['missing_terms']
    if (not isinstance(issues, list) or not 1 <= len(issues) <= MAX_ISSUES or not isinstance(missing, list)
            or len(missing) > len(TERM_LABELS) or not all(m in set(TERM_LABELS.values()) for m in missing)):
        return False
    for issue in issues:
        if not isinstance(issue, dict) or set(issue) != STORED_ISSUE_FIELDS or issue['code'] not in CODES:
            return False
        located = (issue['block'], issue['start'], issue['end'], issue['block_sha256'])
        if located != (None, None, None, None) and (
                any(type(v) is not int for v in located[:3]) or not 0 <= issue['start'] < issue['end']
                or not _hex(issue['block_sha256'])):
            return False
    return True


def project(stored, *, vendor, context_sha256):
    """Public view of a stored diagnostic, verified against the job's pinned context. None when unverifiable."""
    from .vendor_terms import Document
    try:
        if not _stored_shape(stored):
            return None
        document = Document.model_validate(stored['document'])
        text = document.text
        if (sha256(text.encode()).hexdigest() != stored['source_sha256']
                or proposal_context(vendor, document, stored['profile']) != context_sha256):
            return None
        issues = []
        for issue in stored['issues']:
            quote = None
            if issue['start'] is not None:
                if issue['end'] > len(text) or sha256(text[issue['start']:issue['end']].encode()).hexdigest() != issue['block_sha256']:
                    return None
                quote = text[issue['start']:issue['end']]
                quote = quote if len(quote.encode()) <= MAX_QUOTE_BYTES else None
            issues.append(issue | {'explanation': CODES[issue['code']], 'quote': quote})
        return {'schema': SCHEMA, 'profile': stored['profile'], 'source_sha256': stored['source_sha256'],
                'document': {k: stored['document'][k] for k in ('name', 'uri', 'classification')},
                'issues': issues, 'missing_terms': list(stored['missing_terms'])}
    except (ValueError, TypeError, KeyError):
        return None


class DiagnosingVendorModelJobs(VendorModelJobs):
    """Same requests, pins and validation as VendorModelJobs; a refusal may also carry a public diagnostic."""

    def submit(self, p, vendor, body):
        from hashlib import sha256 as _sha256
        document, context, request = self._prepare(vendor, body)
        if request is None:
            raise PermissionError('Public proposal generation is not configured for this deployment.')
        request_sha = _sha256(request).hexdigest()
        profile, nonce = body.profile, body.attempt_nonce

        def validate(provider_result):
            try:
                return _validated_result(vendor, document, profile, nonce, context, request_sha, provider_result)
            except ProposalRefused as exc:
                if exc.code == 'PROPOSAL_REFUSED':
                    exc.public_diagnostic = build(document, profile, provider_result)
                raise

        job = self.service.submit(**self._pins(p, vendor, context, request), validate=validate)
        return self._project(job, vendor, request_sha)

    def status(self, p, vendor, job_id):
        view = super().status(p, vendor, job_id)
        reader = getattr(self.service, 'refusal_diagnostic', None)
        if view.get('status') == 'REFUSED' and callable(reader):
            diagnostic = project(reader(p.tenant, p.subject, job_id), vendor=vendor, context_sha256=view['context_sha256'])
            if diagnostic is not None:
                view['public_diagnostic'] = diagnostic
        return view
