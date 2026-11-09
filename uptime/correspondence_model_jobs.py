"""Operator-approved, queued public interpretation proposals around InterpretationDesk.

The shared ``PublicProposalJobs`` service (installed by the root as
``desk.public_proposal_jobs``) owns approval, durable queueing and the single
provider invocation on the exact approved request bytes. This wrapper only:

* derives the current server context and the complete public block request;
* asks the shared service whether that exact request is approved for this
  actor, target and context (never calling the provider);
* enqueues after the actor's own independent reading; and
* supplies a pure validator that parses a successful provider result and
  attaches one inert candidate to the exact unchanged context.

No model output gains review, preview, preparation, financial or action authority.
"""
from copy import deepcopy
from hashlib import sha256

from .correspondence import authorize
from .correspondence_block_model import BLOCK_VERSION, MAX_REQUEST_BYTES, _canonical, parse_block_result, serialized_block_request
from .correspondence_blocks import source_blocks
from .correspondence_model_transport import strict_json

PROVIDER = 'correspondence'
KIND = 'correspondence'
STATES = ('QUEUED', 'RUNNING', 'SUCCEEDED', 'REFUSED', 'CANCELLED', 'UNCERTAIN')
TERMINAL = frozenset({'SUCCEEDED', 'REFUSED', 'CANCELLED', 'UNCERTAIN'})
RESULT_KEYS = ('candidate_id', 'claim', 'kind', 'context_digest', 'request_sha256', 'response_sha256', 'representation',
               'semantic_review_required', 'ledger_unchanged', 'external_actions')

MESSAGES = {
    'not_configured': 'Interpretation requests are not enabled for this workspace.',
    'provider_not_configured': 'No interpretation provider is configured for this workspace.',
    'request_refused': 'This reply cannot be sent as an interpretation request.',
    'request_mismatch': 'The permission record does not match this exact request. Refresh the original source.',
    'unavailable': 'Permission for this request could not be checked.',
    'reviewer_required': 'Only a reviewer can request an interpretation.',
    'independent_reading_required': 'Save your independent reading before requesting an interpretation.',
    'existing_request': 'A request for this exact source already exists. Check its status below.',
    'approved': 'An operator approved this exact request.',
}
APPROVAL_REQUIRED = 'Permission required: an operator must approve this exact request before it can be sent.'


def serialized_runtime_request(context, profile):
    """Initial runtime attempt only; standalone adapter request bytes stay unchanged."""
    value = strict_json(serialized_block_request(context, profile))
    value['attempt_nonce'] = 'initial'
    return _canonical(value)


def _field(value, *names, default=None):
    """Duck-typed read of the shared service's dict or object results."""
    for name in names:
        if isinstance(value, dict):
            if name in value:
                return value[name]
        elif value is not None and hasattr(value, name):
            return getattr(value, name)
    return default


def _text(value, limit=200):
    value = getattr(value, 'value', value)
    return value[:limit] if isinstance(value, str) else None


class CorrespondenceModelJobs:
    def __init__(self, desk, reviews):
        self.desk, self.reviews = desk, reviews

    # --- shared service lookup (dynamic: root installs it after router creation) ---
    def _service(self):
        return getattr(self.desk, 'public_proposal_jobs', None)

    @staticmethod
    def _provider(service):
        try:
            return service.provider(PROVIDER)
        except (LookupError, PermissionError, ValueError, AttributeError):
            return None

    @staticmethod
    def _request(context, provider):
        request = serialized_runtime_request(context, getattr(provider, 'profile', None))
        if len(request) > MAX_REQUEST_BYTES:
            raise ValueError('Model request exceeds the explicit budget.')
        return request

    @staticmethod
    def _args(p, claim_id, context, request):
        return dict(tenant=p.tenant, subject=p.subject, kind=KIND, target=claim_id,
                    context_sha256=context['digest'], request=request)

    @staticmethod
    def _owned(job, claim_id, p):
        if (job is None or _text(_field(job, 'kind')) != KIND or _text(_field(job, 'target')) != claim_id
                or _field(job, 'tenant') not in (None, p.tenant) or _field(job, 'subject') not in (None, p.subject)):
            raise KeyError('Interpretation request not found.')
        return job

    @staticmethod
    def _job_view(job):
        state = _text(_field(job, 'state', 'status'))
        if state not in STATES:
            state = 'UNCERTAIN'
        identity = _field(job, 'id', 'job_id')
        view = dict(id=None if identity is None else str(identity)[:200], state=state, terminal=state in TERMINAL,
                    kind=KIND, target=_text(_field(job, 'target')),
                    context_digest=_text(_field(job, 'context_sha256')), request_sha256=_text(_field(job, 'request_sha256')),
                    reason=_text(_field(job, 'reason', 'reason_code', 'error_code')), result=None,
                    submitted_at=_text(_field(job, 'submitted_at')), started_at=_text(_field(job, 'started_at')),
                    finished_at=_text(_field(job, 'finished_at')))
        provider = _field(job, 'provider')
        if isinstance(provider, dict):
            # The shared service already publishes only its bounded public receipt subset
            # (public_proposal_jobs.PUBLIC_RECEIPT_KEYS plus transport); pass it through unchanged.
            view['provider'] = deepcopy(provider)
        result = _field(job, 'result')
        if state == 'SUCCEEDED' and isinstance(result, dict):
            view['result'] = {k: deepcopy(result[k]) for k in RESULT_KEYS if k in result}
        return view

    # --- permission/status (no provider call, no write) ---
    def status(self, p, claim_id, context, blind_saved):
        info = dict(kind=KIND, target=claim_id, context_digest=context['digest'], enabled=False, can_request=False,
                    reason='not_configured', message=None, request_sha256=None, request_bytes=None, profile=None, job=None)
        service = self._service()
        provider = self._provider(service) if service is not None else None
        if service is not None and provider is None:
            info['reason'] = 'provider_not_configured'
        elif provider is not None:
            info.update(self._inspect(service, provider, p, claim_id, context))
        if info['enabled'] is True and info['reason'] == 'approved':
            try:
                authorize(p, True)
                reviewer = True
            except PermissionError:
                reviewer = False
            if not reviewer:
                info['reason'] = 'reviewer_required'
            elif not blind_saved:
                info['reason'] = 'independent_reading_required'
            elif info['job'] is not None:
                info['reason'] = 'existing_request'
            else:
                info['can_request'] = True
        info['message'] = MESSAGES.get(info['reason'], APPROVAL_REQUIRED)
        return info

    def _inspect(self, service, provider, p, claim_id, context):
        out = dict(profile=_text(_field(getattr(provider, 'profile', None), 'name')))
        try:
            request = self._request(context, provider)
        except ValueError:
            return dict(out, reason='request_refused')
        digest = sha256(request).hexdigest()
        out.update(request_sha256=digest, request_bytes=len(request), approval_request=dict(
            tenant=p.tenant, subject=p.subject, kind=KIND, target=claim_id,
            context_sha256=context['digest'], request=strict_json(request),
            source_references=[dict(reference='correspondence/'+claim_id+'/reply/'+context['event_digest'],
                                    sha256=context['text_sha256'])]))
        try:
            status = service.inspect(**self._args(p, claim_id, context, request))
        except (LookupError, PermissionError, ValueError):
            return dict(out, reason='unavailable')
        if _field(status, 'request_sha256') != digest:
            return dict(out, reason='request_mismatch')
        existing = _field(status, 'existing_job')
        if existing is not None:
            try:
                out['job'] = self._job_view(self._owned(existing, claim_id, p))
            except KeyError:
                return dict(out, reason='request_mismatch')
        enabled = _field(status, 'enabled') is True
        out['enabled'] = enabled
        reason = _text(_field(status, 'reason', 'reason_code'))
        if enabled:
            out['reason'] = 'approved'
        else:  # a service code cannot impersonate a local status
            out['reason'] = 'approval_required' if not reason or reason in MESSAGES else reason
        return out

    def view(self, p, claim_id):
        """Existing view (candidates still withheld before blind entry) plus source blocks and permission."""
        data = self.reviews.view(p, claim_id)
        context = data['context']
        try:
            data['source_blocks'] = source_blocks(context['text'])
        except ValueError:
            data['source_blocks'] = None
        data['model_job'] = self.status(p, claim_id, context, data['blind_entry'] is not None)
        return data

    # --- submission: enqueue only; the shared service invokes the provider later ---
    def submit(self, p, claim_id, body):
        authorize(p, True)
        service = self._service()
        if service is None:
            raise PermissionError(MESSAGES['not_configured'])
        provider = self._provider(service)
        if provider is None:
            raise PermissionError(MESSAGES['provider_not_configured'])
        context = self.reviews.snapshot(p, claim_id, body.context_digest, require_blind=True)
        request = self._request(context, provider)
        args = self._args(p, claim_id, context, request)
        status = service.inspect(**args)
        if _field(status, 'request_sha256') != sha256(request).hexdigest():
            raise ValueError(MESSAGES['request_mismatch'])
        existing = _field(status, 'existing_job')
        if existing is not None:
            return self._job_view(self._owned(existing, claim_id, p))  # never resubmitted or retried
        if _field(status, 'enabled') is not True:
            raise PermissionError(APPROVAL_REQUIRED)
        job = service.submit(**args, validate=self._validator(p, claim_id, context, request))
        return self._job_view(self._owned(job, claim_id, p))

    def _validator(self, p, claim_id, context, request):
        context, request = deepcopy(context), bytes(request)
        request_sha256 = sha256(request).hexdigest()

        def validate(provider_result):
            # Pure parse of the already-obtained result; this never calls a provider.
            parsed = parse_block_result(context, provider_result, request)
            candidate_id = self.reviews.store_model_result(p, claim_id, context['digest'], parsed)
            return dict(candidate_id=candidate_id, claim=claim_id, kind=KIND, context_digest=context['digest'],
                        request_sha256=request_sha256, response_sha256=parsed['provenance']['response_sha256'],
                        representation=BLOCK_VERSION, semantic_review_required=True, ledger_unchanged=True,
                        external_actions=[])
        return validate

    # --- polling: requester-scoped by the shared service, then target/kind checked here ---
    def get(self, p, claim_id, job_id):
        authorize(p)
        service = self._service()
        if service is None:
            raise KeyError('Interpretation request not found.')
        job = service.get(p.tenant, p.subject, job_id)
        return self._job_view(self._owned(job, claim_id, p))
