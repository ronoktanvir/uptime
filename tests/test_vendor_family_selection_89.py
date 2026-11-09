"""Automatic rule-family selection (team decision D05): Uptime, not the operator, chooses the family.

The real durable job service and the real deterministic validators run every case. The provider is an
explicit test double that returns a scripted reading per family profile; no real inference occurs.
"""
from copy import deepcopy
from datetime import UTC, datetime
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from uptime import vendor_registry
from uptime.auth import DEFAULT_ORIGIN, bind_workspace, enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key
from uptime.public_proposal_jobs import PublicProposalJobs, canonical
from uptime.server import create_app
from uptime.storage import initialize
from uptime.vendor_family_selection import (FAMILIES, MONTHLY, RESOURCE, SelectingVendorModelJobs, SelectionRefused,
                                            classify, decide, offline_monthly)
from uptime.vendor_model import MODEL, VENDOR_SYSTEM, validate_proposal
from uptime.vendor_model_jobs import ProposalRequest, public_approval_request, proposal_context
from uptime.vendor_resource_terms import public_blocks
from uptime.vendor_terms import Document, compile_terms

from test_vendor_catalog import DOC as CANONICAL, OVERLAY as CANONICAL_OVERLAY, proposition_document
from test_vendor_model_jobs_runtime import P, finished, write_manifest
import test_vendor_resource as resource

VENDOR = 'auto-selected-vendor'
NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)
PROSE, PROSE_PROPOSAL = proposition_document()
PROSE_OVERLAY = dict(account='acct-auto', agreement='Test-AG-3', product='Data Lake', plan='Advanced', currency='USD',
                     effective_from='2026-03-01', effective_until='2026-08-31', fee_line_ref='line-auto')
# Resource reading of the monthly prose source. Every block is grounded; the period and filing blocks cannot be
# represented in the resource grammar (no resource denominator, no UTC clock), and its required terms are absent.
PROSE_AS_RESOURCE = [{'vendor': 'Stratosphere Networks'}, {'agreement': 'Test-AG-3'}, {'effective': ['2026-02-01', None]},
                     {'period': 'utc_calendar_month'}, {'scope': {'product': 'Data Lake', 'plan': 'Advanced'}},
                     {'nonmaterial': 'table header'}, {'nonmaterial': 'table separator'},
                     {'tiers': [{'below': '99.9', 'credit': '15', 'at_least': None}]},
                     {'filing': {'kind': 'calendar_days', 'count': 21, 'utc_time': '00:00', 'endpoint': 'inclusive'}},
                     {'remedy': 'future_noncash_credit'}]
# The resource source with its exclusion sentence first, so a monthly reading meets a deterministic qualifier.
RESOURCE_ROWS = [resource.ROWS[5]] + resource.ROWS[:5] + resource.ROWS[6:]
RESOURCE_DOC = resource.DOC | {'text': '\n'.join(quote for quote, _ in RESOURCE_ROWS)}


def blocks_text(document, values):
    blocks = public_blocks(document['text'])
    assert len(blocks) == len(values)
    return json.dumps({'blocks': [{'id': b['id'], 'value': v} for b, v in zip(blocks, values, strict=True)]})


def lines_text(document, field='heading', first=None):
    lines = [line for line in document['text'].split('\n') if line.strip()]
    clauses = [{'quote': line, 'field': field, 'value': None} for line in lines]
    if first:
        clauses[0] = clauses[0] | first
    return json.dumps({'clauses': clauses})


class FamilyProvider:
    """Scripted public reading per family profile. Records every request it receives."""
    model, system = MODEL, VENDOR_SYSTEM
    profile = {'name': 'explicit-public-test-provider', 'revision': 1}

    def __init__(self):
        self.calls, self.outputs = [], {}

    def __call__(self, request):
        self.calls.append(json.loads(request)['profile'])
        return {'model': MODEL, 'session': 'scripted-family-provider', 'text': self.outputs[json.loads(request)['profile']]}


@pytest.fixture
def selecting(tmp_path):
    root = tmp_path / 'protected'
    root.mkdir(mode=0o700)
    manifest = root / 'approvals.json'
    write_manifest(manifest)
    db = tmp_path / 'runtime.sqlite'
    bind_workspace(db, 'replay', False, P.tenant)
    initialize(db)
    provider = FamilyProvider()
    service = PublicProposalJobs(db, manifest, {'vendor': provider}, clock=lambda: NOW)
    yield db, manifest, provider, service, SelectingVendorModelJobs(service)
    service.close()


def auto(document, nonce='initial'):
    return {'document': document, 'profile': 'auto', 'attempt_nonce': nonce}


def approve(runtime, document, *, nonce='initial', profiles=None, subject=P):
    _, manifest, provider, _, _ = runtime
    records = json.loads(manifest.read_text())['approvals']
    for _, profile, _ in FAMILIES:
        if profiles is None or profile in profiles:
            record = public_approval_request(provider, subject, VENDOR,
                                             ProposalRequest(document=document, profile=profile, attempt_nonce=nonce))
            records.append(record | {'approved_by': 'scripted-public-engineering-operator',
                                     'approved_at': '2026-11-01T00:00:00Z', 'expires_at': '2026-12-01T00:00:00Z'})
    write_manifest(manifest, records)


def settle(runtime, view):
    _, _, _, service, _ = runtime
    for family in view['families']:
        if family['job'] is not None:
            finished(service, {'job_id': family['job']['job_id']})


def run(runtime, document, nonce='initial'):
    _, _, _, _, jobs = runtime
    submitted = jobs.submit_selection(P, VENDOR, auto(document, nonce))
    settle(runtime, submitted)
    return jobs.selection(P, VENDOR, auto(document, nonce))


def by_family(view):
    return {f['family']: f for f in view['families']}


# ---- Offline deterministic selection ----

def test_canonical_monthly_source_is_selected_offline_without_inference(selecting):
    _, _, provider, _, jobs = selecting
    view = jobs.selection(P, VENDOR, auto(CANONICAL))
    assert view['outcome'] == 'SELECTED' and view['selected'] == {
        'family': MONTHLY, 'method': 'deterministic_document_parser', 'job_id': None, 'profile': None}
    assert view['offline'] == {'accepted': True, 'method': 'deterministic_document_parser', 'reason': None}
    assert jobs.submit_selection(P, VENDOR, auto(CANONICAL))['outcome'] == 'SELECTED'
    assert provider.calls == [] and all(f['job'] is None for f in view['families'])
    assert view['authority'] == {'approval_gate': False, 'dispatch_authorized': False}


def test_resource_language_keeps_even_a_canonical_source_off_the_offline_shortcut():
    """Opus falsification probe 1: a canonical monthly source that also states resource terms."""
    dual = CANONICAL | {'text': CANONICAL['text'] + '\nDowntime means rejected samples caused by gateway failure.'}
    assert offline_monthly(Document(**dual)) == (None, 'RESOURCE_LANGUAGE_PRESENT')
    with pytest.raises(ValueError):
        compile_terms(Document(**dual))  # the strict grammar refuses it on its own as well


def test_a_resource_symptom_clause_has_no_monthly_reading():
    """Vocabulary exclusivity probe: a symptom/cause definition is refused under every monthly field label."""
    sentence = 'Downtime means rejected samples or lost acknowledgments caused by instrument gateway failure.'
    document = Document(**(CANONICAL | {'text': sentence}))
    for field in ('heading', 'vendor', 'agreement', 'effective', 'period', 'scope', 'tier', 'filing_days', 'remedy',
                  'credit_rule', 'nonmaterial'):
        with pytest.raises(ValueError):
            validate_proposal(document, [{'quote': sentence, 'field': field, 'value': None}], allow_propositions=True)


# ---- Validation-decided selection through the real job service ----

def test_no_job_is_queued_until_every_family_request_is_approved(selecting):
    _, _, provider, _, jobs = selecting
    view = jobs.selection(P, VENDOR, auto(PROSE))
    assert view['outcome'] == 'APPROVAL_REQUIRED' and view['offline']['reason'] == 'NOT_CANONICAL'
    approve(selecting, PROSE, profiles={'monthly-propositions'})
    partial = jobs.submit_selection(P, VENDOR, auto(PROSE))
    assert partial['outcome'] == 'APPROVAL_REQUIRED' and 'Resource month' in partial['review_requirements'][0]
    assert provider.calls == [] and all(f['job'] is None for f in partial['families'])


def test_monthly_family_selected_when_the_resource_reading_is_refused(selecting):
    db, _, provider, _, jobs = selecting
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}),
                        'resource-month': blocks_text(PROSE, PROSE_AS_RESOURCE)}
    approve(selecting, PROSE)
    view = run(selecting, PROSE)
    families = by_family(view)
    assert sorted(provider.calls) == ['monthly-propositions', 'resource-month']
    assert view['outcome'] == 'SELECTED' and view['selected']['family'] == MONTHLY
    assert view['selected']['job_id'] == families[MONTHLY]['job']['job_id']
    assert families[RESOURCE]['state'] == 'REFUSED_READING'
    assert 'claim filing deadline' in families[RESOURCE]['refusal']['missing_terms']
    assert any(r.startswith('Resource month:') for r in view['review_requirements'])
    # The selected job stages a SHADOW candidate; nothing is approved or activated.
    intake, receipt = jobs.candidate(P, VENDOR, view['selected']['job_id'], PROSE_OVERLAY)
    staged = vendor_registry.install(db, P, VENDOR, intake, public_receipt=receipt)
    assert staged['state'] == 'SHADOW' and staged['actions'] == [] and staged['active_version'] is None
    assert jobs.submit_selection(P, VENDOR, auto(PROSE))['selection_sha256'] == view['selection_sha256']
    assert len(provider.calls) == 2  # resubmission is idempotent


def test_resource_family_selected_when_the_monthly_reading_meets_a_deterministic_qualifier(selecting):
    _, _, provider, _, jobs = selecting
    provider.outputs = {'monthly-propositions': lines_text(RESOURCE_DOC, first={'field': 'remedy'}),
                        'resource-month': blocks_text(RESOURCE_DOC, [v for _, v in RESOURCE_ROWS])}
    approve(selecting, RESOURCE_DOC)
    view = run(selecting, RESOURCE_DOC)
    families = by_family(view)
    assert view['offline']['reason'] == 'RESOURCE_LANGUAGE_PRESENT'
    assert view['outcome'] == 'SELECTED' and view['selected']['family'] == RESOURCE
    assert families[MONTHLY]['state'] == 'REFUSED_STRUCTURAL'
    assert families[MONTHLY]['refusal']['codes'] == ['UNSUPPORTED_SOURCE_MATERIAL']
    assert families[MONTHLY]['refusal']['passages'] == [RESOURCE_ROWS[0][0]]


def test_both_refused_is_no_supported_family_with_concrete_requirements(selecting):
    _, _, provider, _, jobs = selecting
    values = [v for _, v in RESOURCE_ROWS]
    values[3] = {'unsupported': 'scripted'}
    provider.outputs = {'monthly-propositions': lines_text(RESOURCE_DOC, first={'field': 'remedy'}),
                        'resource-month': blocks_text(RESOURCE_DOC, values)}
    approve(selecting, RESOURCE_DOC)
    view = run(selecting, RESOURCE_DOC)
    assert view['outcome'] == 'NO_SUPPORTED_FAMILY' and view['selected'] is None
    assert view['review_requirements'][0].startswith('Monthly availability:')
    assert view['review_requirements'][1].startswith('Resource month:')
    assert 'No supported rule family' in view['review_requirements'][-1]


def test_a_family_with_no_grounded_reading_cannot_be_ruled_out(selecting):
    _, _, provider, _, jobs = selecting
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}), 'resource-month': 'not json'}
    approve(selecting, PROSE)
    view = run(selecting, PROSE)
    assert view['outcome'] == 'INCOMPLETE' and view['selected'] is None
    assert by_family(view)[RESOURCE]['state'] == 'NOT_EVALUATED'
    assert 'new attempt identifier' in view['review_requirements'][0]


def _inject_success(db, tenant, subject, family_profile, document):
    context = proposal_context(VENDOR, Document(**document), family_profile)
    with sqlite3.connect(db) as connection:
        connection.execute('''INSERT INTO public_proposal_jobs (id,tenant,subject,kind,target,context_sha256,request_sha256,
            status,submitted_at,approved_by,approved_at,expires_at,budget_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('injected-other-attempt', tenant, subject, 'vendor', VENDOR, context, 'c' * 64, 'SUCCEEDED',
             '2026-11-05T11:00:00+00:00', 'op', '2026-11-01T00:00:00+00:00', '2026-12-01T00:00:00+00:00', '1.00'))


def test_any_other_validated_family_makes_the_source_ambiguous_and_blocks_its_candidate(selecting):
    db, _, provider, _, jobs = selecting
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}),
                        'resource-month': blocks_text(PROSE, PROSE_AS_RESOURCE)}
    approve(selecting, PROSE)
    selected = run(selecting, PROSE)
    assert selected['outcome'] == 'SELECTED'
    # Another reviewer's earlier attempt validated the resource family for the same exact source.
    _inject_success(db, P.tenant, 'another-reviewer', 'resource-month', PROSE)
    view = jobs.selection(P, VENDOR, auto(PROSE))
    assert view['outcome'] == 'AMBIGUOUS' and 'Monthly availability, Resource month' in view['review_requirements'][0]
    assert by_family(view)[RESOURCE]['attempts'] == {'total': 2, 'validated': 1, 'structural_refusals': 0}
    with pytest.raises(SelectionRefused, match='AMBIGUOUS'):
        jobs.candidate(P, VENDOR, selected['selected']['job_id'], PROSE_OVERLAY)
    # A new attempt cannot turn the ambiguous source back into a selected one.
    approve(selecting, PROSE, nonce='retry-a')
    assert run(selecting, PROSE, 'retry-a')['outcome'] == 'AMBIGUOUS'


def test_offline_selection_is_also_ambiguous_when_another_family_validated(selecting):
    db, _, _, _, jobs = selecting
    _inject_success(db, P.tenant, P.subject, 'resource-month', CANONICAL)
    assert jobs.selection(P, VENDOR, auto(CANONICAL))['outcome'] == 'AMBIGUOUS'


# ---- Pure outcome derivation ----

def _family(name, state, *, validated=0, job=True, enabled=True):
    label = dict((f, l) for f, _, l in FAMILIES)[name]
    return {'family': name, 'label': label, 'profile': None, 'enabled': enabled, 'job': {'job_id': name, 'status': 'X'} if job else None,
            'state': state, 'refusal': None, 'attempts': {'validated': validated}}


@pytest.mark.parametrize('monthly,resource_state,expected', [
    (('VALIDATED', 1), ('REFUSED_STRUCTURAL', 0), 'SELECTED'),
    (('VALIDATED', 1), ('REFUSED_READING', 0), 'SELECTED'),
    (('VALIDATED', 1), ('NOT_EVALUATED', 0), 'INCOMPLETE'),
    (('VALIDATED', 1), ('INCONCLUSIVE', 0), 'INCOMPLETE'),
    (('VALIDATED', 1), ('PENDING', 0), 'PENDING'),
    (('VALIDATED', 1), ('REFUSED_READING', 1), 'AMBIGUOUS'),
    (('REFUSED_READING', 0), ('REFUSED_STRUCTURAL', 0), 'NO_SUPPORTED_FAMILY'),
    (('REFUSED_READING', 0), ('NOT_EVALUATED', 0), 'INCOMPLETE'),
])
def test_outcome_matrix(monthly, resource_state, expected):
    families = [_family(MONTHLY, monthly[0], validated=monthly[1]), _family(RESOURCE, resource_state[0], validated=resource_state[1])]
    assert decide(families, None, 'NOT_CANONICAL', True)[0] == expected


def test_unsubmitted_and_unconfigured_outcomes():
    unapproved = [_family(MONTHLY, None, job=False, enabled=True), _family(RESOURCE, None, job=False, enabled=False)]
    assert decide(unapproved, None, 'NOT_CANONICAL', True)[0] == 'APPROVAL_REQUIRED'
    approved = [_family(MONTHLY, None, job=False), _family(RESOURCE, None, job=False)]
    assert decide(approved, None, 'NOT_CANONICAL', True)[0] == 'NOT_SUBMITTED'
    assert decide(approved, None, 'NOT_CANONICAL', False)[0] == 'PROVIDER_UNCONFIGURED'


def test_refusal_classification():
    def diagnostic(*codes):
        return {'issues': [{'code': code} for code in codes]}
    assert classify('SUCCEEDED', None, None) == 'VALIDATED'
    assert classify('REFUSED', 'proposal_validation_failed', diagnostic('REQUIRED_TERMS_MISSING')) == 'REFUSED_STRUCTURAL'
    assert classify('REFUSED', 'proposal_validation_failed',
                    diagnostic('UNSUPPORTED_BLOCK_PROPOSITION', 'REQUIRED_TERMS_MISSING')) == 'REFUSED_READING'
    assert classify('REFUSED', 'proposal_validation_failed', diagnostic('OUTPUT_NOT_STRUCTURED')) == 'NOT_EVALUATED'
    assert classify('REFUSED', 'proposal_validation_failed', None) == 'INCONCLUSIVE'
    assert classify('REFUSED', 'approval_unavailable_before_dispatch', diagnostic('REQUIRED_TERMS_MISSING')) == 'INCONCLUSIVE'
    assert classify('UNCERTAIN', 'provider_timeout', None) == 'INCONCLUSIVE'


# ---- Ordinary signed application path ----

@pytest.fixture
def signed(selecting):
    db, _, _, service, _ = selecting
    key = generate_reviewer_key()
    enroll(db, P.subject, key, tenant=P.tenant, mode='replay')
    app = create_app(db, tenant=P.tenant, proposal_jobs=service, approvals_enabled=False)
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 12345)) as client:
        yield selecting, ReviewerClient(client, DEFAULT_ORIGIN, P.subject, key)


def test_signed_app_path_selects_stages_and_explains_the_family(signed):
    runtime, reviewer = signed
    _, _, provider, service, _ = runtime
    base = '/api/vendors/' + VENDOR
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}),
                        'resource-month': blocks_text(PROSE, PROSE_AS_RESOURCE)}
    assert reviewer.post(base + '/proposal-access', auto(PROSE)).json()['outcome'] == 'APPROVAL_REQUIRED'
    for extra in ({'family': MONTHLY}, {'approved': True}, {'overlay': PROSE_OVERLAY}):
        assert reviewer.post(base + '/proposal-access', auto(PROSE) | extra).status_code == 422
    approve(runtime, PROSE)
    submitted = reviewer.post(base + '/proposal-jobs', auto(PROSE)).json()
    for family in submitted['families']:
        finished(service, {'job_id': family['job']['job_id']})
    view = reviewer.post(base + '/proposal-access', auto(PROSE)).json()
    assert view['outcome'] == 'SELECTED' and view['selected']['family'] == MONTHLY
    staged = reviewer.post(base + '/proposal-jobs/' + view['selected']['job_id'] + '/candidate', {'overlay': PROSE_OVERLAY})
    assert staged.status_code == 200, staged.text
    assert staged.json()['state'] == 'SHADOW' and staged.json()['actions'] == []
    record = reviewer.client.get(base + '/requirements', headers=reviewer.headers).json()['family_selection']
    assert record['outcome'] == 'SELECTED' and record['selected']['family'] == MONTHLY
    assert {f['family']: f['state'] for f in record['families']}[RESOURCE] == 'REFUSED_READING'
    assert sorted(provider.calls) == ['monthly-propositions', 'resource-month']


def test_signed_app_path_offline_selection_and_explanation(signed):
    runtime, reviewer = signed
    base = '/api/vendors/' + VENDOR
    view = reviewer.post(base + '/proposal-access', auto(CANONICAL)).json()
    assert view['outcome'] == 'SELECTED' and view['selected']['method'] == 'deterministic_document_parser'
    staged = reviewer.post(base + '/candidates', {'document': CANONICAL, 'overlay': CANONICAL_OVERLAY})
    assert staged.status_code == 200, staged.text
    record = reviewer.client.get(base + '/requirements', headers=reviewer.headers).json()['family_selection']
    assert record['outcome'] == 'SELECTED' and record['selected']['method'] == 'deterministic_document_parser'
    assert runtime[2].calls == []
