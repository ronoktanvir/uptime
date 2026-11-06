"""Named monthly profile controls over authored source; no blind/model/human claim."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from uptime import vendor_registry as registry, vendor_terms
from uptime.contracts import Principal
from uptime.public_proposal_jobs import canonical
from uptime.vendor_eval import evaluate
from uptime.vendor_model import MODEL, proposal_receipt, verify_receipt, serialize_proposal_request
from uptime.vendor_model_jobs import ProposalRequest, proposal_context, public_approval_request
from uptime.vendor_terms import Document, Overlay, bind_overlay
from test_vendor_model_jobs_runtime import P, VENDOR, runtime, finished, write_manifest

FIXTURES = Path(__file__).resolve().parent.parent/'fixtures/onboarding79_public'
DOCUMENT = json.loads((FIXTURES/'document.json').read_text())
PROPOSAL = json.loads((FIXTURES/'proposal.authored.json').read_text())
OVERLAY = dict(account='phase79-authored-account', agreement='JRC-2026-05', product='Event Archive', plan='Standard',
               currency='USD', effective_from='2026-03-01', effective_until='2026-12-31', fee_line_ref='phase79-fee-line')
# Explicit test observations; a positive result is an arithmetic control, not real service evidence.
FACTS = {k:OVERLAY[k] for k in ('account','agreement','product','plan','fee_line_ref')} | dict(
    month='2026-04', eligible_downtime_minutes=200, monitor_source='simulated_vendor', month_complete=True,
    exclusions_removed=True, monthly_fee_cents=10000, monitor_ref='phase79-monitor', fee_ref='phase79-fee',
    received_at='2026-05-18T23:59:59Z')
TEST_REVIEWER = Principal(P.tenant, 'scripted-phase79-reviewer', 'reviewer')


def result(proposal=PROPOSAL):
    return dict(model=MODEL, session='authored-phase79-provider-double', text=json.dumps(proposal))


def grant(runtime, profile):
    _, manifest, provider, _, _ = runtime
    body = ProposalRequest(document=DOCUMENT, profile=profile)
    entry = public_approval_request(provider, P, VENDOR, body)
    write_manifest(manifest, [entry | dict(approved_by='scripted-public-operator',
        approved_at='2026-11-01T00:00:00Z', expires_at='2026-12-01T00:00:00Z')])
    return body


def test_named_profile_uses_existing_monthly_propositions_without_changing_strict_profile():
    document = Document(**DOCUMENT)
    with pytest.raises(ValueError, match='Unsupported source language'):
        proposal_receipt(document, 'monthly', result(), at='2026-11-06T00:00:00Z')
    receipt = proposal_receipt(document, 'monthly-propositions', result(), at='2026-11-06T00:00:00Z')
    manifest, extraction = verify_receipt(document, receipt, allow_propositions=True)
    assert manifest['family'] == 'monthly-availability/1'
    assert manifest['interpretation'] == 'model_proposition_human_review_required'
    assert extraction['method'] == 'tool_free_model_propositions'
    assert receipt['proposal'] == PROPOSAL['clauses']
    assert all(document.text[c['start']:c['end']] == c['quote'] for c in manifest['citations'])


def test_profile_request_and_context_are_distinct_and_bind_only_consumed_family(monkeypatch):
    document = Document(**DOCUMENT)
    transport = {'name':'public-test-profile'}
    strict = serialize_proposal_request(document, 'monthly', transport)
    proposition = serialize_proposal_request(document, 'monthly-propositions', transport)
    assert strict != proposition and sha256(strict).digest() != sha256(proposition).digest()
    assert json.loads(strict)['input'] == json.loads(proposition)['input']
    old = proposal_context(VENDOR, document, 'monthly-propositions')
    assert old != proposal_context(VENDOR, document, 'monthly')
    monkeypatch.setitem(vendor_terms.SEMANTICS_REVISIONS, 'resource-month/1', 'unused-resource')
    assert proposal_context(VENDOR, document, 'monthly-propositions') == old
    monkeypatch.setitem(vendor_terms.SEMANTICS_REVISIONS, 'monthly-availability/1', 'changed-monthly')
    assert proposal_context(VENDOR, document, 'monthly-propositions') != old


def test_actual_queue_needs_separate_profile_approval_then_preserves_interpretation_gate(runtime):
    db, _, provider, service, adapter = runtime
    provider.proposal = deepcopy(PROPOSAL['clauses'])
    strict = grant(runtime, 'monthly')
    proposed = ProposalRequest(document=DOCUMENT, profile='monthly-propositions')
    assert adapter.access(P, VENDOR, strict)['enabled'] is True
    assert adapter.access(P, VENDOR, proposed)['enabled'] is False
    with pytest.raises(PermissionError): adapter.submit(P, VENDOR, proposed)
    assert provider.calls == []
    strict_job = finished(service, adapter.submit(P, VENDOR, strict))
    assert strict_job['status'] == 'REFUSED'
    proposed = grant(runtime, 'monthly-propositions')
    job = finished(service, adapter.submit(P, VENDOR, proposed))
    assert job['status'] == 'SUCCEEDED' and job['job_id'] != strict_job['job_id']
    assert len(provider.calls) == 2
    intake, receipt = adapter.candidate(P, VENDOR, job['job_id'], OVERLAY)
    state = registry.install(db, P, VENDOR, intake, public_receipt=receipt)
    assert state['state'] == 'SHADOW' and state['active_version'] is None
    assert state['interpretation_required'] is True and state['interpretation_reviewer'] is None
    assert state['actions'] == []
    for private in (OVERLAY['account'], OVERLAY['fee_line_ref']):
        assert private.encode() not in provider.calls[-1]
    # 200/43200 > 0.4%; 172/43200 < 0.4%. $100 * 12% = $12.
    cases = [dict(name='authored positive', facts=FACTS, expected={'outcome':'ELIGIBLE','amount':'12.00'}),
             dict(name='authored below shortfall', facts=FACTS | {'eligible_downtime_minutes':172}, expected={'outcome':'INELIGIBLE'})]
    checked = registry.submit_tests(db, TEST_REVIEWER, VENDOR,
        registry.TestSubmission(revision=state['revision'], tests=cases))
    assert all(row['passed'] for row in checked['checks'])
    assert [action['operation'] for action in checked['actions']] == ['interpret']
    with pytest.raises((ValueError, PermissionError)):
        registry.act(db, TEST_REVIEWER, VENDOR, 'approve')
    with pytest.raises((ValueError, PermissionError)):
        registry.act(db, TEST_REVIEWER, VENDOR, 'activate')
    interpreted = registry.act(db, TEST_REVIEWER, VENDOR, checked['actions'][0]['id'])
    assert interpreted['interpretation_reviewer'] == TEST_REVIEWER.subject
    assert [action['operation'] for action in interpreted['actions']] == ['approve']
    assert interpreted['active_version'] is None
    # Replacing the checked cases invalidates the old interpretation acceptance.
    revised = registry.submit_tests(db, TEST_REVIEWER, VENDOR,
        registry.TestSubmission(revision=interpreted['revision'], tests=cases + [cases[0] | {'name':'additional authored positive'}]))
    assert revised['interpretation_reviewer'] is None
    assert [action['operation'] for action in revised['actions']] == ['interpret']


@pytest.mark.parametrize('mutation', ['missing_source','changed_value','qualification','fences','wrong_family'])
def test_profile_does_not_relax_full_source_grounding_or_family_boundaries(mutation):
    document, proposal = deepcopy(DOCUMENT), deepcopy(PROPOSAL)
    if mutation == 'missing_source': proposal['clauses'].pop()
    elif mutation == 'changed_value': proposal['clauses'][7]['value']['credit'] = '13'
    elif mutation == 'qualification':
        document['text'] += '\nClaims are excluded during maintenance.'
        proposal['clauses'].append(dict(quote='Claims are excluded during maintenance.',field='heading',value=None))
    elif mutation == 'wrong_family':
        from test_vendor_resource import DOC, PROPOSAL as RESOURCE_PROPOSAL
        document, proposal = DOC, {'clauses': RESOURCE_PROPOSAL}
    response = result(proposal)
    if mutation == 'fences': response['text'] = '```json\n'+response['text']+'\n```'
    with pytest.raises(ValueError):
        proposal_receipt(Document(**document), 'monthly-propositions', response, at='2026-11-06T00:00:00Z')


def test_opt_in_profile_cannot_mint_governing_fee_authority():
    from test_vendor_step_proposals import DOC, OVERLAY, facts, CASES
    from test_vendor_step_proposals import proposal as steps
    receipt = proposal_receipt(Document(**DOC), 'monthly-propositions', result({'clauses': steps()}), at='2026-11-06T00:00:00Z')
    manifest, _ = verify_receipt(Document(**DOC), receipt, allow_propositions=True)
    bound = bind_overlay(manifest, Overlay(**OVERLAY))
    observation = facts(next(case for case in CASES.values() if case['outcome'] == 'ELIGIBLE'))
    observed = evaluate(manifest, bound, observation | {'monthly_fee_cents':999999999}, P.tenant)
    assert observed['outcome'] == 'INSUFFICIENT_EVIDENCE' and observed['amount'] is None
