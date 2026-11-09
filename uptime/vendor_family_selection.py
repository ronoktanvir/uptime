"""Automatic rule-family selection for public vendor sources (team decision D05).

Uptime, not the operator, chooses the rule family, and deterministic validation decides:

1. Offline: when the deterministic monthly parser accepts the complete source by itself, and the
   source contains no resource-family language, the monthly family is selected without inference.
2. Otherwise each supported family is evaluated by its own exact-approved public proposal job:
   ``monthly-propositions`` (strict parser first, then guarded propositions) and ``resource-month``.
   Both requests must be approved before either is queued, and both share one attempt identifier.
3. The outcome is derived on read and never stored:

   * SELECTED: exactly one family validated the complete source, and every other family's grounded
     reading of it was refused. A refusal without a grounded reading (unstructured output or quotes
     that do not match the source) does not rule a family out.
     Families are close to mutually exclusive by vocabulary: a source fully covered by monthly clauses has
     no symptom, cause or evidence clauses for the resource family, and resource clauses have no monthly
     field. Each view still reports whether a loser was ruled out structurally (a deterministic finding
     about the source) or by a refused reading, so the reviewer sees why.
   * AMBIGUOUS: more than one family has validated this exact source in any attempt by any reviewer
     in the tenant. Retrying cannot turn an ambiguous source into a selected one.
   * NO_SUPPORTED_FAMILY: every family refused; each refusal's verified public diagnostic is the
     concrete review requirement.
   * INCOMPLETE: a family evaluation ended without a conclusive result, or the losing family's refusal
     was an extraction failure. A new attempt identifier evaluates both families again.
   * PENDING, NOT_SUBMITTED, APPROVAL_REQUIRED, PROVIDER_UNCONFIGURED: work not yet done.

Selection never approves anything. A person still reviews the SHADOW candidate, authors independent
tests and approves before activation. This module is outside the reviewed-semantics file set and
leaves ``vendor_model_jobs.py`` (part of every proposal context pin) byte-identical.
"""
from hashlib import sha256
import re
from typing import Literal

from pydantic import Field

from .contracts import fingerprint
from .vendor_model_jobs import KIND, ProposalRequest, _vendor
from .vendor_refusal_diagnostics import DiagnosingVendorModelJobs, project
from .vendor_terms import Document, Strict, compile_terms

SCHEMA = 'automatic-family-selection/1'
MONTHLY = 'monthly-availability/1'
RESOURCE = 'resource-month/1'
# (family, extraction profile used to evaluate it, label). One profile per family, fixed by the server.
FAMILIES = ((MONTHLY, 'monthly-propositions', 'Monthly availability'),
            (RESOURCE, 'resource-month', 'Resource month'))
# Refusal codes that are deterministic findings about the source text under that family's grammar.
STRUCTURAL = frozenset({'UNSUPPORTED_SOURCE_MATERIAL', 'REQUIRED_TERMS_MISSING', 'SOURCE_COVERAGE_INCOMPLETE'})
# Refusals where the extraction produced no grounded reading of the source at all: the family was not evaluated.
NO_READING = frozenset({'OUTPUT_NOT_STRUCTURED', 'PROPOSAL_NOT_SOURCE_GROUNDED'})
RULED_OUT = frozenset({'REFUSED_STRUCTURAL', 'REFUSED_READING'})
# Language belonging to the resource family's required terms. Its presence sends even a canonically
# formatted source through both families' validation instead of the offline monthly shortcut.
RESOURCE_MARKERS = re.compile(
    r'\b(?:resources?|instances?|stations?|devices?|symptoms?|causes?|caused|incidents?|intervals?|telemetry|'
    r'evidence|records?|outages?|failures?|tickets?|requests?|unavailable minutes)\b', re.IGNORECASE)
OUTCOMES = frozenset({'SELECTED', 'AMBIGUOUS', 'NO_SUPPORTED_FAMILY', 'INCOMPLETE', 'PENDING', 'NOT_SUBMITTED',
                      'APPROVAL_REQUIRED', 'PROVIDER_UNCONFIGURED'})
DETERMINISTIC = 'deterministic_document_parser'
JOB = 'public_proposal_job'


class AutoProposalRequest(Strict):
    """Automatic selection request. The client supplies the public source only; never a family."""
    document: Document
    profile: Literal['auto']
    attempt_nonce: str = Field(default='initial', min_length=1, max_length=30)


class SelectionRefused(ValueError):
    """A candidate was requested that automatic family selection did not choose."""

    def __init__(self, outcome, requirements):
        self.outcome = outcome
        self.requirements = list(requirements)
        super().__init__(f'Automatic family selection is {outcome}. ' + ' '.join(self.requirements))


def offline_monthly(document):
    """(manifest, None) when the deterministic parser alone establishes the monthly family, else (None, code)."""
    if RESOURCE_MARKERS.search(document.text):
        return None, 'RESOURCE_LANGUAGE_PRESENT'
    try:
        return compile_terms(document), None
    except (ValueError, TypeError, KeyError, OverflowError):
        return None, 'NOT_CANONICAL'


def classify(status, reason, diagnostic):
    if status in ('QUEUED', 'RUNNING'):
        return 'PENDING'
    if status == 'SUCCEEDED':
        return 'VALIDATED'
    if status == 'REFUSED' and reason == 'proposal_validation_failed' and diagnostic is not None:
        codes = {issue['code'] for issue in diagnostic['issues']}
        if codes <= NO_READING:
            return 'NOT_EVALUATED'
        return 'REFUSED_STRUCTURAL' if codes <= STRUCTURAL else 'REFUSED_READING'
    return 'INCONCLUSIVE'


def _summary(diagnostic):
    if diagnostic is None:
        return None
    return {'codes': [issue['code'] for issue in diagnostic['issues']],
            'explanations': list(dict.fromkeys(issue['explanation'] for issue in diagnostic['issues'])),
            'passages': [issue['quote'] for issue in diagnostic['issues'] if issue['quote'] is not None],
            'missing_terms': list(diagnostic['missing_terms'])}


def _refusal_requirements(family):
    summary = family['refusal'] or {}
    parts = list(summary.get('explanations', []))
    if summary.get('missing_terms'):
        parts.append('Missing: ' + ', '.join(summary['missing_terms']) + '.')
    if summary.get('passages'):
        parts.append('Passage: “' + summary['passages'][0][:300] + '”.')
    text = f"{family['label']}: " + (' '.join(parts) if parts else 'refused without a verified public explanation.')
    if family['state'] == 'REFUSED_READING':
        text += ' This refused the extraction’s reading, not a deterministic finding about the source text.'
    elif family['state'] == 'NOT_EVALUATED':
        text += ' The extraction produced no grounded reading, so this family was not evaluated.'
    return text


def decide(families, offline_manifest, offline_reason, configured):
    """Pure outcome derivation from the families' current states. Returns (outcome, selected, requirements)."""
    labels = {f['family']: f['label'] for f in families}
    validated_anywhere = [f['family'] for f in families if f['attempts']['validated']]
    if offline_manifest is not None:
        if any(name != MONTHLY for name in validated_anywhere):
            return 'AMBIGUOUS', None, [_ambiguous([MONTHLY] + [n for n in validated_anywhere if n != MONTHLY], labels)]
        return 'SELECTED', {'family': MONTHLY, 'method': DETERMINISTIC, 'job_id': None, 'profile': None}, [
            'The deterministic parser establishes the monthly availability family from the complete source with no '
            'model call. Stage the candidate with POST /api/vendors/{id}/candidates, author independent shadow tests, '
            'and have a person approve before activation.']
    if len(validated_anywhere) > 1:
        return 'AMBIGUOUS', None, [_ambiguous(validated_anywhere, labels)]
    if not configured:
        return 'PROVIDER_UNCONFIGURED', None, [
            'The deterministic parser alone cannot establish a family for this source '
            f'({offline_reason}), and public proposal generation is not configured for this deployment.']
    if any(f['job'] is None for f in families):
        unapproved = [f['label'] for f in families if f['job'] is None and not f['enabled']]
        if unapproved:
            return 'APPROVAL_REQUIRED', None, [
                'An operator must approve the exact public request for every supported family before automatic '
                'selection starts. Not yet approved: ' + ', '.join(unapproved) + '.']
        return 'NOT_SUBMITTED', None, ['Submit automatic selection. Every supported family is evaluated with one attempt identifier.']
    if any(f['state'] == 'PENDING' for f in families):
        return 'PENDING', None, ['Wait for every family evaluation to finish.']
    if any(f['state'] == 'INCONCLUSIVE' for f in families):
        stalled = [f"{f['label']} ({f['job']['status']})" for f in families if f['state'] == 'INCONCLUSIVE']
        return 'INCOMPLETE', None, [
            'These family evaluations ended without a conclusive result: ' + ', '.join(stalled) + '. '
            'Submit a new attempt identifier; every family is evaluated again.']
    winners = [f for f in families if f['state'] == 'VALIDATED']
    unevaluated = [f for f in families if f['state'] == 'NOT_EVALUATED']
    if len(winners) == 1:
        winner = winners[0]
        losers = [f for f in families if f is not winner]
        unproven = [f for f in losers if f['state'] not in RULED_OUT]
        if unproven:
            return 'INCOMPLETE', None, [
                f"{winner['label']} validated, but Uptime cannot rule out " + ', '.join(f['label'] for f in unproven)
                + ': its extraction produced no grounded reading of the source. Submit a new attempt identifier.'
            ] + [_refusal_requirements(f) for f in unproven]
        return 'SELECTED', {'family': winner['family'], 'method': JOB, 'job_id': winner['job']['job_id'],
                            'profile': winner['profile']}, [
            f"Uptime selected the {winner['label'].lower()} family: it alone validated the complete source. "
            'Stage the candidate from the selected proposal job, review why the other families were refused, '
            'accept or reject the source interpretation, author independent shadow tests, and have a person approve '
            'before activation.'] + [_refusal_requirements(f) for f in losers]
    if unevaluated:
        return 'INCOMPLETE', None, [_refusal_requirements(f) for f in families] + [
            'At least one family was not evaluated because its extraction produced no grounded reading. '
            'Submit a new attempt identifier before concluding that no supported family applies.']
    return 'NO_SUPPORTED_FAMILY', None, [_refusal_requirements(f) for f in families] + [
        'No supported rule family represents this complete source. It cannot become an adapter without a new reviewed '
        'family, a corrected source, or manual handling.']


def _ambiguous(names, labels):
    return ('More than one supported rule family validated this complete source (' + ', '.join(labels[n] for n in names)
            + '). Uptime does not choose between readings. A reviewer must establish which obligation governs, for '
            'example from the customer’s signed agreement, and onboard a source that states only that obligation.')


class SelectingVendorModelJobs(DiagnosingVendorModelJobs):
    """Vendor proposal jobs with automatic family selection and verified refusal diagnostics."""

    def _attempt_states(self, p, vendor, context):
        reader = getattr(self.service, 'attempts', None)
        if not callable(reader):
            return []
        return [classify(row.get('status'), row.get('reason'),
                         project(row['public_diagnostic'], vendor=vendor, context_sha256=context)
                         if row.get('public_diagnostic') is not None else None)
                for row in reader(p.tenant, KIND, vendor, context)]

    def _family(self, p, vendor, body, family, profile, label):
        request = ProposalRequest(document=body.document, profile=profile, attempt_nonce=body.attempt_nonce)
        access = self.access(p, vendor, request)
        context, job = access['context_sha256'], access['existing_job']
        diagnostic = None
        if job is not None and job['status'] == 'REFUSED':
            reader = getattr(self.service, 'refusal_diagnostic', None)
            stored = reader(p.tenant, p.subject, job['job_id']) if callable(reader) else None
            diagnostic = project(stored, vendor=vendor, context_sha256=context) if stored is not None else None
        history = self._attempt_states(p, vendor, context) if access.get('request_sha256') else []
        return {'family': family, 'label': label, 'profile': profile, 'enabled': bool(access.get('enabled')),
                'approval_reason': access.get('reason'), 'context_sha256': context,
                'request_sha256': access.get('request_sha256'), 'disclosure': access.get('disclosure'),
                'job': job, 'state': None if job is None else classify(job['status'], job.get('reason'), diagnostic),
                'refusal': _summary(diagnostic), 'public_diagnostic': diagnostic,
                'attempts': {'total': len(history), 'validated': sum(state == 'VALIDATED' for state in history),
                             'structural_refusals': sum(state == 'REFUSED_STRUCTURAL' for state in history)}}

    def selection(self, p, vendor, body):
        """Read-only selection view. No provider call and no job submission."""
        body = AutoProposalRequest.model_validate(body.model_dump() if isinstance(body, Strict) else body)
        _vendor(vendor)
        document = Document.model_validate(body.document.model_dump())
        offline, offline_reason = offline_monthly(document)
        families = [self._family(p, vendor, body, *entry) for entry in FAMILIES]
        configured = all(f['request_sha256'] is not None for f in families)
        outcome, selected, requirements = decide(families, offline, offline_reason, configured)
        return _view(vendor, document, body.attempt_nonce, offline, offline_reason, families, outcome, selected, requirements)

    def submit_selection(self, p, vendor, body):
        """Queue every family evaluation together, only when every exact request is approved."""
        view = self.selection(p, vendor, body)
        if view['outcome'] != 'NOT_SUBMITTED':
            return view  # selected offline, already submitted, ambiguous, unconfigured or awaiting approval
        body = AutoProposalRequest.model_validate(body.model_dump() if isinstance(body, Strict) else body)
        for family in view['families']:
            if family['job'] is None:
                self.submit(p, vendor, ProposalRequest(document=body.document, profile=family['profile'],
                                                      attempt_nonce=body.attempt_nonce))
        return self.selection(p, vendor, body)

    def candidate(self, p, vendor, job_id, overlay):
        """Stage a candidate only from the job automatic selection chose for its source and attempt (D05)."""
        job = self._owned(p, vendor, job_id)
        document, result, _ = self._resolve(job, vendor)
        if result['profile'] not in {profile for _, profile, _ in FAMILIES}:
            raise SelectionRefused('NOT_AUTOMATIC', [
                f"This proposal used an operator-chosen extraction profile ({result['profile']}). Uptime selects the "
                'rule family: submit the source with profile "auto", and stage the candidate from the job it selects.'])
        view = self.selection(p, vendor, {'document': document.model_dump(), 'profile': 'auto',
                                          'attempt_nonce': result['attempt_nonce']})
        if view['outcome'] != 'SELECTED':
            raise SelectionRefused(view['outcome'], view['review_requirements'])
        if view['selected']['job_id'] != job_id:
            raise SelectionRefused('NOT_SELECTED', [
                'Automatic selection did not choose this job for its source and attempt. '
                + ('The deterministic parser selected the monthly family; stage it with POST /api/vendors/{id}/candidates.'
                   if view['selected']['method'] == DETERMINISTIC else
                   f"Stage the selected job {view['selected']['job_id']} instead.")])
        return super().candidate(p, vendor, job_id, overlay)


def unconfigured_selection(vendor, body):
    """Selection view without a proposal service: only the offline deterministic step can select."""
    body = AutoProposalRequest.model_validate(body.model_dump() if isinstance(body, Strict) else body)
    _vendor(vendor)
    document = Document.model_validate(body.document.model_dump())
    offline, offline_reason = offline_monthly(document)
    families = [{'family': family, 'label': label, 'profile': profile, 'enabled': False,
                 'approval_reason': 'PROPOSAL_SERVICE_UNCONFIGURED', 'context_sha256': None, 'request_sha256': None,
                 'disclosure': None, 'job': None, 'state': None, 'refusal': None, 'public_diagnostic': None,
                 'attempts': {'total': 0, 'validated': 0, 'structural_refusals': 0}} for family, profile, label in FAMILIES]
    outcome, selected, requirements = decide(families, offline, offline_reason, False)
    return _view(vendor, document, body.attempt_nonce, offline, offline_reason, families, outcome, selected, requirements)


def _view(vendor, document, nonce, offline, offline_reason, families, outcome, selected, requirements):
    source = sha256(document.text.encode()).hexdigest()
    pins = {'schema': SCHEMA, 'vendor_id': vendor, 'source_sha256': source, 'attempt_nonce': nonce,
            'contexts': {f['family']: f['context_sha256'] for f in families},
            'jobs': {f['family']: (f['job'] or {}).get('job_id') for f in families},
            'outcome': outcome, 'selected': selected}
    return {'schema': SCHEMA, 'mode': 'automatic', 'vendor_id': vendor, 'source_sha256': source, 'attempt_nonce': nonce,
            'offline': {'accepted': offline is not None, 'method': DETERMINISTIC,
                        'reason': None if offline is not None else offline_reason},
            'families': families, 'outcome': outcome, 'selected': selected, 'review_requirements': requirements,
            'selection_sha256': fingerprint(pins),
            'authority': {'approval_gate': False, 'dispatch_authorized': False}}


def review_summary(view):
    """Compact selection record for the reviewer's requirement view."""
    return {'outcome': view['outcome'], 'selected': view['selected'], 'selection_sha256': view['selection_sha256'],
            'offline': view['offline'], 'review_requirements': view['review_requirements'],
            'families': [{'family': f['family'], 'label': f['label'], 'state': f['state'], 'refusal': f['refusal'],
                          'attempts': f['attempts']} for f in view['families']]}
