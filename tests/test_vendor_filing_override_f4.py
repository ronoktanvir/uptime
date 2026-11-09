"""F4: a private filing amendment governs only from the calendar month it states. F6: unverified evidence is labeled.

Expected dates are hand-computed. Months before the amendment keep the public source's filing rule.
"""
from datetime import UTC, datetime
from hashlib import sha256
import json

import pytest

from uptime import vendor_registry as registry
from uptime.contracts import fingerprint
from uptime.storage import initialize
from uptime.vendor_eval import evaluate
from uptime.vendor_resource_eval import Unsupported, deadline, month_bounds
from uptime.vendor_terms import Document, Overlay, bind_overlay, compile_terms, private_filing_days

from test_vendor_catalog import DOC, FACTS, OVERLAY
import test_vendor_resource as resource

QUOTE = 'Claims must be received within 19 calendar days after month end.'


def amended(effective_from='2026-07-01', **changes):
    override = {'filing_days': 19, 'quote': QUOTE, 'source_ref': 'private-addendum-section-2', 'effective_from': effective_from}
    return OVERLAY | {'override': override | changes}


def outcome(overlay, facts):
    manifest = compile_terms(Document(**DOC))
    return evaluate(manifest, bind_overlay(manifest, Overlay(**overlay)), facts, 'demo-tenant')


def test_mid_term_amendment_governs_only_months_from_its_effective_date():
    # The source window is 12 days. June 2026 ends June 30, so the June window closes 2026-07-13T00:00Z (exclusive).
    june = outcome(amended(), FACTS)
    assert june['claim_cutoff_exclusive'] == '2026-07-13T00:00:00+00:00' and june['outcome'] == 'ELIGIBLE'
    assert outcome(amended(), FACTS | {'received_at': '2026-07-13T00:00:00Z'})['filing_status'] == 'OUTSIDE_WINDOW'
    # July 2026 (31 days, 44,640 minutes; 120 down is below 99.75%) is governed by the 19-day amendment: closes 2026-08-20.
    july = FACTS | {'month': '2026-07', 'eligible_downtime_minutes': 120, 'received_at': '2026-08-19T23:59:59Z'}
    result = outcome(amended(), july)
    assert result['claim_cutoff_exclusive'] == '2026-08-20T00:00:00+00:00' and result['outcome'] == 'ELIGIBLE'
    assert outcome(amended(), july | {'received_at': '2026-08-20T00:00:00Z'})['filing_status'] == 'OUTSIDE_WINDOW'
    # An amendment dated from the overlay start governs every month, as before.
    assert outcome(amended('2026-04-01'), FACTS)['claim_cutoff_exclusive'] == '2026-07-20T00:00:00+00:00'


@pytest.mark.parametrize('effective_from', ['2026-07-15', '2026-03-01', '2026-12-01', '2026-13-01', '2026-7-01'])
def test_amendment_dates_outside_calendar_months_or_the_overlay_are_unsupported(effective_from):
    manifest = compile_terms(Document(**DOC))
    with pytest.raises(ValueError):
        bind_overlay(manifest, Overlay(**amended(effective_from)))


def test_an_undated_amendment_is_unsupported_not_defaulted():
    manifest = compile_terms(Document(**DOC))
    undated = {k: v for k, v in amended()['override'].items() if k != 'effective_from'}
    with pytest.raises(ValueError):
        bind_overlay(manifest, Overlay(**(OVERLAY | {'override': undated})))
    # A stored legacy overlay without a date never silently governs the whole interval.
    legacy = bind_overlay(manifest, Overlay(**OVERLAY)) | {'override': undated}
    result = evaluate(manifest, legacy, FACTS, 'demo-tenant')
    assert result['outcome'] == 'UNSUPPORTED_RULE' and 'calendar month it governs from' in result['trace'][0]
    with pytest.raises(ValueError):
        private_filing_days(legacy, '2026-06', 12)


def test_resource_calendar_day_window_follows_the_amendment_month():
    manifest = resource.compiled()
    override = {'override': {'filing_days': 19, 'effective_from': '2026-07-01'}}
    _, june_end = month_bounds('2026-06')
    _, july_end = month_bounds('2026-07')
    # The source window: tenth calendar day after the service month, 18:00 UTC, inclusive.
    assert deadline({'month': '2026-06'}, override, manifest, june_end) == (datetime(2026, 7, 10, 18, tzinfo=UTC), True)
    assert deadline({'month': '2026-07'}, override, manifest, july_end) == (datetime(2026, 8, 19, 18, tzinfo=UTC), True)
    with pytest.raises(Unsupported, match='calendar month it governs from'):
        deadline({'month': '2026-07'}, {'override': {'filing_days': 19}}, manifest, july_end)


def test_unverified_governing_evidence_digest_is_labeled_in_dispatched_citations(monkeypatch, tmp_path):
    """F6: the attestation's evidence digest is operator-supplied; the dispatched citation says it is unverified."""
    phrase, scope = 'this schedule controls', 'the availability and service credits addressed here'
    text = f'If the customer order conflicts with this schedule, {phrase} only with respect to {scope}.'
    row = {'precedence': {'op': 'this_sla_controls_conflicts_in_scope', 'phrase': phrase, 'scope': scope}}
    doc, proposal = resource.extend_source([(text, row)])
    manifest = resource.compiled(doc, proposal)
    attestation = {'verified': True, 'agreement': resource.OVERLAY['agreement'], 'source_sha256': manifest['document']['sha256'],
                   'effective_from': '2026-02-01', 'source_ref': 'signed-order-4', 'evidence_sha256': '7' * 64,
                   'unamended_terms': ['scope', 'measurement', 'exclusions', 'tiers', 'fee_basis', 'rounding', 'filing', 'remedy']}
    overlay = resource.OVERLAY | {'governing_terms': attestation}
    path = tmp_path / 'test.sqlite'
    initialize(path)
    digest = sha256(doc['text'].encode()).hexdigest()
    (tmp_path / (digest + '.json')).write_text(json.dumps({
        'model': resource.MODEL, 'source_sha256': digest, 'session': 'synthetic-test-model-f6', 'at': '2026-06-01T00:00:00Z',
        'proposal': proposal, 'proposal_sha256': fingerprint(proposal)}))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS', str(tmp_path))
    monkeypatch.setenv('UPTIME_MODEL_PROPOSITIONS', '1')
    P = resource.P
    shadow = registry.install(path, P, 'meters', {'document': doc, 'overlay': overlay})
    assert shadow['state'] == 'SHADOW', shadow
    from test_vendor_semantic_bindings import review_submission
    shadow = registry.review_semantics(path, P, 'meters', registry.SemanticSubmission(
        revision=shadow['revision'], review=review_submission(shadow['manifest'], shadow['overlay'], doc['text'])))
    current = registry.submit_tests(path, P, 'meters', registry.TestSubmission(revision=shadow['revision'], tests=[
        {'name': 'June hand calculation', 'facts': resource.FACTS, 'expected': {'outcome': 'ELIGIBLE', 'amount': '12.51'}},
        {'name': 'June no delivery loss', 'facts': resource.FACTS | {'intervals': []}, 'expected': {'outcome': 'INELIGIBLE'}}]))
    for op in ('interpret', 'approve', 'activate'):
        current = registry.act(path, P, 'meters', next(a['id'] for a in current['actions'] if a['operation'] == op))
    governing = [c for c in registry.dispatch(path, P, 'meters', resource.FACTS)['clauses'] if c['label'] == 'signed-order-4']
    assert len(governing) == 1 and governing[0]['evidence_verification'] == 'OPERATOR_SUPPLIED_UNVERIFIED'
    assert governing[0]['sha256'] == '7' * 64
