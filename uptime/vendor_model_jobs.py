"""Bounded public vendor proposal jobs over the shared PublicProposalJobs service.

The browser supplies only an exact public Document, one fixed extraction profile and
an attempt nonce. The server derives the complete transmitted request, its local
context pins and the result validator. The shared core invokes its configured
provider once, outside HTTP handlers and global POST locks. Results are inert: a
separate signed candidate request attaches a private overlay, and the normal SHADOW
install completely revalidates the receipt. Nothing here approves, tests, activates
or evaluates a vendor, and nothing mutates UPTIME_PUBLIC_EXTRACTIONS.

Assumed shared surface (root-owned; confirm at merge):
  provider('vendor') -> configured provider exposing .profile, .model, .system
  inspect(*, tenant, subject, kind, target, context_sha256, request) ->
      {enabled: bool, reason: str, request_sha256: sha256(request).hexdigest(), existing_job: job | None}
  submit(same keyword arguments, validate=callable) -> job
  get(tenant, subject, job_id) -> owned job (KeyError when absent or not owned)
  job: {JOB_ID_FIELD, 'status', 'kind', 'target', 'context_sha256', 'request_sha256',
        optional JOB_REASON_FIELD code, 'result' only when SUCCEEDED}
"""
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import Field

from .contracts import fingerprint
from . import vendor_terms
from .vendor_model import (MODEL, PROPOSAL_PROFILES, VENDOR_SYSTEM, ProposalEnvelopeError, job_extraction,
                           proposal_input, proposal_receipt, serialize_proposal_request)
from .vendor_terms import Document, Strict

__all__ = ['VENDOR_SYSTEM', 'build_vendor_provider', 'VendorModelJobs', 'ProposalRequest', 'ProposalCandidate',
           'proposal_context', 'unconfigured_access', 'public_approval_request']

KIND = 'vendor'
SERVICE_PROVIDER = 'vendor'
JOB_ID_FIELD = 'job_id'        # The single identifier field of the shared job record.
JOB_REASON_FIELD = 'reason'    # Optional bounded status code; free text is never projected.
JOB_PIN_FIELDS = ('kind', 'target', 'context_sha256', 'request_sha256')
STATUSES = frozenset({'QUEUED', 'RUNNING', 'SUCCEEDED', 'REFUSED', 'CANCELLED', 'UNCERTAIN'})
RESULT_PROTOCOL = 'uptime-public-vendor-proposal-result/1'
CONTEXT_PROTOCOL = 'uptime-public-vendor-proposal-context/1'
RESULT_FIELDS = frozenset({'protocol', 'kind', 'target', 'context_sha256', 'request_sha256', 'profile',
                           'attempt_nonce', 'document', 'receipt'})
VENDOR_ID = re.compile(r'[a-z0-9][a-z0-9_-]{0,79}')
JOB_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}')
CODE = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}')
_MODULE_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


class ProposalRequest(Strict):
    """Exact public input only. No provider, model, command, path, receipt, hash or approval field exists."""
    document: Document
    profile: Literal['monthly', 'resource-month']
    attempt_nonce: str = Field(default='initial', min_length=1, max_length=30)


class ProposalCandidate(Strict):
    """Only the private overlay. Source and receipt come from the immutable owned job result."""
    overlay: dict


class ProposalRefused(ValueError):
    """Raised inside the shared worker's validate step. The message is a fixed public code."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class ProposalUnavailable(ValueError):
    MESSAGES = {
        'NOT_SUCCEEDED': 'Only a succeeded proposal job can stage a candidate.',
        'RESULT_INTEGRITY': 'The proposal job result failed its integrity pins. No candidate was created.',
        'STALE_CONTEXT': 'The proposal no longer matches the current source, profile or evaluator semantics. '
                         'Generate a new proposal.',
        'REQUEST_CHANGED': 'The proposal request pins no longer match the configured transport. Generate a new proposal.',
    }

    def __init__(self, code):
        self.code = code
        super().__init__(self.MESSAGES[code])


def build_vendor_provider(executable):
    """The only vendor provider: the established pinned safe public transport profile."""
    from .correspondence_model_transport import SafePublicClaude
    return SafePublicClaude(executable, model=MODEL, system=VENDOR_SYSTEM)


def _vendor(vendor):
    if type(vendor) is not str or not VENDOR_ID.fullmatch(vendor):
        raise ValueError('Invalid vendor catalog identifier.')
    return vendor


def _job_ref(job_id):
    if type(job_id) is not str or not JOB_ID.fullmatch(job_id):
        raise ValueError('Invalid proposal job identifier.')
    return job_id


def job_identifier(job):
    value = job.get(JOB_ID_FIELD) if isinstance(job, dict) else None
    if type(value) is not str or not JOB_ID.fullmatch(value):
        raise ValueError('The proposal service returned a job without a valid identifier.')
    return value


def proposal_context(vendor, document, profile):
    """Local pins: vendor, exact Document metadata and bytes, profile and current semantic dependencies."""
    if profile not in PROPOSAL_PROFILES:
        raise ValueError('Unknown extraction profile.')
    return fingerprint({'protocol': CONTEXT_PROTOCOL, 'kind': KIND, 'vendor_id': _vendor(vendor),
                        'document': document.model_dump(), 'source_sha256': sha256(document.text.encode()).hexdigest(),
                        'profile': profile, 'allow_propositions': PROPOSAL_PROFILES[profile],
                        'system_sha256': sha256(VENDOR_SYSTEM.encode()).hexdigest(),
                        'semantics': vendor_terms.SEMANTICS_REVISIONS, 'module_sha256': _MODULE_SHA256})


def _disclosure(document, body, request):
    """What is transmitted, derived from the actual request. Not an authorization."""
    sent = sorted(json.loads(request)) if request is not None else None
    return {'model': MODEL, 'tools': [], 'profile': body.profile, 'attempt_nonce': body.attempt_nonce,
            'source_sha256': sha256(document.text.encode()).hexdigest(), 'source_characters': len(document.text),
            'request_bytes': len(request) if request is not None else None, 'transmitted_fields': sent}


def _prepare_public(vendor, body, transport):
    _vendor(vendor)
    document = Document.model_validate(body.document.model_dump())
    proposal_input(document, body.profile)
    context = proposal_context(vendor, document, body.profile)
    request = None if transport is None else serialize_proposal_request(
        document, body.profile, transport, attempt_nonce=body.attempt_nonce)
    return document, context, request


def public_approval_request(provider, principal, vendor, body):
    """Operator-only readable request preparation; no queue, approval, provider call or DB lock."""
    if (getattr(provider, 'model', None) != MODEL or getattr(provider, 'system', None) != VENDOR_SYSTEM
            or not isinstance(getattr(provider, 'profile', None), dict) or not provider.profile):
        raise ValueError('A configured public vendor provider profile is required.')
    body = ProposalRequest.model_validate(body)
    document, context, request = _prepare_public(vendor, body, provider.profile)
    return {'tenant': principal.tenant, 'subject': principal.subject, 'kind': KIND, 'target': vendor,
            'context_sha256': context, 'request': json.loads(request),
            'source_references': [{'reference': document.uri, 'sha256': sha256(document.text.encode()).hexdigest()}]}


def unconfigured_access(vendor, body):
    """Fail-closed permission state when no proposal service is mounted. Zero service or provider calls."""
    _vendor(vendor)
    proposal_input(body.document, body.profile)
    return {'enabled': False, 'reason': 'PROPOSAL_SERVICE_UNCONFIGURED', 'vendor_id': vendor,
            'request_sha256': None, 'context_sha256': proposal_context(vendor, body.document, body.profile),
            'existing_job': None, 'disclosure': _disclosure(body.document, body, None)}


def _validated_result(vendor, document, profile, nonce, context, request_sha, provider_result):
    """Runs in the shared worker after its single provider call. Returns an inert result or refuses."""
    try:
        receipt = proposal_receipt(document, profile, provider_result, at=datetime.now(UTC).isoformat())
    except ProposalEnvelopeError:
        raise ProposalRefused('PROVIDER_IDENTITY_UNVERIFIED') from None
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError):
        # Exception text may quote provider output; only a fixed code leaves this function.
        raise ProposalRefused('PROPOSAL_REFUSED') from None
    return {'protocol': RESULT_PROTOCOL, 'kind': KIND, 'target': vendor, 'context_sha256': context,
            'request_sha256': request_sha, 'profile': profile, 'attempt_nonce': nonce,
            'document': document.model_dump(), 'receipt': receipt}


class VendorModelJobs:
    def __init__(self, service):
        if not all(callable(getattr(service, name, None)) for name in ('provider', 'inspect', 'submit', 'get')):
            raise TypeError('A configured PublicProposalJobs service is required.')
        self.service = service

    def _transport(self):
        """Server-configured provider profile only; any absence or mismatch fails closed."""
        try:
            provider = self.service.provider(SERVICE_PROVIDER)
        except (KeyError, LookupError, PermissionError, ValueError, OSError):
            return None
        profile = getattr(provider, 'profile', None)
        if (provider is None or getattr(provider, 'model', None) != MODEL
                or getattr(provider, 'system', None) != VENDOR_SYSTEM or not isinstance(profile, dict) or not profile):
            return None
        return profile

    def _prepare(self, vendor, body):
        # A fresh copy: the reservation closure never shares a mutable client object.
        return _prepare_public(vendor, body, self._transport())

    @staticmethod
    def _pins(p, vendor, context, request):
        return dict(tenant=p.tenant, subject=p.subject, kind=KIND, target=vendor, context_sha256=context, request=request)

    def access(self, p, vendor, body):
        document, context, request = self._prepare(vendor, body)
        state = {'vendor_id': vendor, 'context_sha256': context, 'existing_job': None,
                 'disclosure': _disclosure(document, body, request)}
        if request is None:
            return state | {'enabled': False, 'reason': 'PROVIDER_UNCONFIGURED', 'request_sha256': None}
        request_sha = sha256(request).hexdigest()
        answer = self.service.inspect(**self._pins(p, vendor, context, request))
        if (not isinstance(answer, dict) or type(answer.get('enabled')) is not bool
                or answer.get('request_sha256') != request_sha):
            raise ValueError('The proposal service returned an inconsistent permission state.')
        reason = answer.get('reason')
        existing = answer.get('existing_job')
        return state | {'enabled': answer['enabled'], 'request_sha256': request_sha,
                        'reason': reason if type(reason) is str and CODE.fullmatch(reason) else None,
                        'existing_job': self._project(existing, vendor, request_sha) if existing is not None else None}

    def submit(self, p, vendor, body):
        document, context, request = self._prepare(vendor, body)
        if request is None:
            raise PermissionError('Public proposal generation is not configured for this deployment.')
        request_sha = sha256(request).hexdigest()
        profile, nonce = body.profile, body.attempt_nonce

        def validate(provider_result):
            return _validated_result(vendor, document, profile, nonce, context, request_sha, provider_result)

        job = self.service.submit(**self._pins(p, vendor, context, request), validate=validate)
        return self._project(job, vendor, request_sha)

    def _owned(self, p, vendor, job_id):
        _vendor(vendor)
        _job_ref(job_id)
        job = self.service.get(p.tenant, p.subject, job_id)
        if job_identifier(job) != job_id:
            raise ValueError('The proposal service returned a different job.')
        if not isinstance(job, dict) or job.get('kind') != KIND or job.get('target') != vendor:
            raise KeyError(job_id)  # another kind or vendor's job is indistinguishable from absence
        return job

    def status(self, p, vendor, job_id):
        return self._project(self._owned(p, vendor, job_id), vendor)

    def _resolve(self, job, vendor):
        """Immutable result -> exact Document, profile, nonce and receipt, after every local pin is rechecked."""
        if job.get('status') != 'SUCCEEDED':
            raise ProposalUnavailable('NOT_SUCCEEDED')
        result = job.get('result')
        if (not isinstance(result, dict) or set(result) != RESULT_FIELDS or result['protocol'] != RESULT_PROTOCOL
                or result['kind'] != KIND or result['target'] != vendor
                or result['context_sha256'] != job.get('context_sha256')
                or result['request_sha256'] != job.get('request_sha256')
                or result['profile'] not in PROPOSAL_PROFILES or type(result['attempt_nonce']) is not str
                or not isinstance(result['document'], dict) or not isinstance(result['receipt'], dict)):
            raise ProposalUnavailable('RESULT_INTEGRITY')
        try:
            document = Document.model_validate(result['document'])
            exact = document.model_dump() == result['document'] and (
                result['receipt'].get('source_sha256') == sha256(document.text.encode()).hexdigest())
        except ValueError:
            exact = False
        if not exact:
            raise ProposalUnavailable('RESULT_INTEGRITY')
        if proposal_context(vendor, document, result['profile']) != result['context_sha256']:
            raise ProposalUnavailable('STALE_CONTEXT')
        transport = self._transport()
        if transport is None:
            raise PermissionError('Public proposal generation is not configured for this deployment.')
        try:
            request = serialize_proposal_request(document, result['profile'], transport,
                                                 attempt_nonce=result['attempt_nonce'])
        except ValueError:
            raise ProposalUnavailable('RESULT_INTEGRITY') from None
        if sha256(request).hexdigest() != result['request_sha256']:
            raise ProposalUnavailable('REQUEST_CHANGED')
        provenance = {'origin': 'public_proposal_job', 'job_id': job_identifier(job),
                      'request_sha256': result['request_sha256'], 'context_sha256': result['context_sha256'],
                      'profile': result['profile'], 'attempt_nonce': result['attempt_nonce']}
        public_receipt = {'profile': result['profile'], 'receipt': result['receipt'], 'provenance': provenance}
        try:
            # Same pure check registry.install repeats; nothing unvalidated is displayed or staged.
            job_extraction(document, public_receipt)
        except (ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError):
            raise ProposalUnavailable('RESULT_INTEGRITY') from None
        return document, result, public_receipt

    def candidate(self, p, vendor, job_id, overlay):
        """Server-resolved intake plus receipt for registry.install. No provider call; nothing is approved."""
        job = self._owned(p, vendor, job_id)
        document, _, public_receipt = self._resolve(job, vendor)
        return {'document': document.model_dump(), 'overlay': overlay}, public_receipt

    def _project(self, job, vendor, expected_request=None):
        """Bounded safe projection: pins, status, a code and validated public clauses only."""
        job_id = job_identifier(job)
        status = job.get('status')
        if status not in STATUSES or any(type(job.get(key)) is not str for key in JOB_PIN_FIELDS):
            raise ValueError('The proposal service returned an unrecognized job.')
        if job['kind'] != KIND or job['target'] != vendor:
            raise KeyError(job_id)
        if expected_request is not None and job['request_sha256'] != expected_request:
            raise ValueError('The proposal service returned a job for different request bytes.')
        view = {'job_id': job_id, 'status': status, 'vendor_id': vendor,
                'request_sha256': job['request_sha256'], 'context_sha256': job['context_sha256'],
                'candidate_available': False, 'completed_after_expiry': job.get('completed_after_expiry', False)}
        reason = job.get(JOB_REASON_FIELD)
        if status != 'SUCCEEDED' and type(reason) is str and CODE.fullmatch(reason):
            view['reason'] = reason
        if status != 'SUCCEEDED':
            return view
        try:
            document, result, _ = self._resolve(job, vendor)
        except ProposalUnavailable as exc:
            return view | {'refusal': exc.code}
        except PermissionError:
            return view | {'refusal': 'PROVIDER_UNCONFIGURED'}
        receipt = result['receipt']
        clauses = [{'quote': row.get('quote'), 'field': row.get('field'), 'value': row.get('value')}
                   for row in receipt.get('proposal', []) if isinstance(row, dict)]
        return view | {'candidate_available': True, 'proposal': {
            'profile': result['profile'], 'attempt_nonce': result['attempt_nonce'],
            'source_sha256': receipt['source_sha256'], 'proposal_sha256': receipt.get('proposal_sha256'),
            'session': receipt.get('session'), 'model': receipt.get('model'),
            'document': {key: document.model_dump()[key] for key in ('name', 'uri', 'classification')},
            'clauses': clauses}}
