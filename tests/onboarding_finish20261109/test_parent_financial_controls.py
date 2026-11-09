"""Independent authored financial/ambiguity controls for the 1a grammar repair.

Expected amounts are hand-calculated from 43,200 June minutes and a $1,200 fee.
These are development controls, not the sealed generalization evaluation.
"""
from copy import deepcopy

import pytest

from uptime.vendor_terms import Document, compile_terms
from uptime.vendor_eval import evaluate

SOURCE = """Copperleaf Compute Agreement
Copperleaf Systems provides Compute on the Standard plan.
This agreement takes effect on 2026-01-01 and ends on 2026-12-31.
Availability is measured over each UTC calendar month.
For Compute on the Standard plan, monthly availability below 99.9% earns a 10% service credit.
Monthly availability below 99% earns a 20% service credit.
Only the highest applicable percentage applies; percentages do not accumulate.
The credit percentage applies to the affected monthly service fee in USD.
Credits are applied to a future invoice.
A claim must be submitted within 30 calendar days after month end."""


def document(text=SOURCE):
    return Document(name='Authored copperleaf controls', uri='urn:synthetic:copperleaf-controls',
                    classification='synthetic_public', text=text)


def context():
    overlay = dict(account='Account One', agreement='Copperleaf Compute Agreement', product='Compute', plan='Standard',
                   currency='USD', effective_from='2026-01-01', effective_until='2026-12-31', fee_line_ref='line-1')
    facts = dict(account=overlay['account'], agreement=overlay['agreement'], product='Compute', plan='Standard',
                 fee_line_ref='line-1', month='2026-06', eligible_downtime_minutes=433,
                 monitor_source='simulated_vendor', month_complete=True, exclusions_removed=True,
                 monthly_fee_cents=120000, fee_month='2026-06', monitor_month='2026-06',
                 monitor_ref='signed-month-control', fee_ref='signed-fee-control',
                 received_at='2026-07-15T00:00:00Z')
    return overlay, facts


@pytest.mark.parametrize('down,outcome,amount', [
    (43, 'INELIGIBLE', None),  # 43/43,200 < 0.1% missed.
    (44, 'ELIGIBLE', '120.00'),
    (432, 'ELIGIBLE', '120.00'),  # Exactly 99%; the 20% tier says below.
    (433, 'ELIGIBLE', '240.00'),  # The highest credit, never 10% + 20%.
])
def test_new_source_forms_keep_exact_boundary_and_nonaccumulation(down, outcome, amount):
    manifest = compile_terms(document())
    overlay, facts = context()
    result = evaluate(manifest, overlay, facts | {'eligible_downtime_minutes': down}, 'tenant-control')
    assert result['outcome'] == outcome
    assert result['amount'] == amount
    assert result['filing_status'] == 'TIMELY'


@pytest.mark.parametrize('change', [
    {'month_complete': False}, {'exclusions_removed': False}, {'eligible_downtime_minutes': None},
    {'monitor_source': 'public_status'}, {'fee_month': '2026-05'}, {'monthly_fee_cents': 120000.0},
    {'account': 'Another Account'}, {'agreement': 'Another Agreement'},
])
def test_new_source_forms_do_not_weaken_evidence_or_identity(change):
    overlay, facts = context()
    result = evaluate(compile_terms(document()), overlay, facts | change, 'tenant-control')
    assert result['outcome'] == 'INSUFFICIENT_EVIDENCE'
    assert result['amount'] is None


@pytest.mark.parametrize('at,outcome', [('2026-07-30T23:59:59Z', 'ELIGIBLE'),
                                       ('2026-07-31T00:00:00Z', 'INELIGIBLE')])
def test_article_in_filing_sentence_does_not_move_deadline(at, outcome):
    overlay, facts = context()
    result = evaluate(compile_terms(document()), overlay, facts | {'received_at': at}, 'tenant-control')
    assert result['claim_cutoff_exclusive'] == '2026-07-31T00:00:00+00:00'
    assert result['outcome'] == outcome
    if outcome == 'INELIGIBLE':
        assert result['amount'] is None


@pytest.mark.parametrize('suffix', [
    'Credits are paid in cash.',
    'Only customers in good standing qualify for a credit.',
    'Downtime caused by scheduled maintenance is excluded.',
    'The percentages accumulate.',
    'Claims must include the incident identifier.',
    'Agreement: Other Agreement',
    'Claims must be received within 31 calendar days after month end.',
])
def test_extra_material_terms_cannot_be_silently_dropped(suffix):
    with pytest.raises(ValueError):
        compile_terms(document(SOURCE + '\n' + suffix))


def test_citations_are_exact_source_spans_without_reconstructed_clauses():
    manifest = compile_terms(document())
    assert manifest['agreement'] == 'Copperleaf Compute Agreement'
    assert manifest['vendor'] == 'Copperleaf Systems'
    for citation in manifest['citations']:
        assert SOURCE[citation['start']:citation['end']] == citation['quote']
    overlay, facts = context()
    result = evaluate(manifest, overlay, facts, 'tenant-control')
    assert result['tier_citation'] in result['citations']
    chosen = next(c for c in manifest['citations'] if c['id'] == result['tier_citation'])
    assert '20%' in chosen['quote']
