"""Strict clause classifier parity with the parser on the released remediation templates.

Authored fictional sources only. On every probe, the first clause the classifier cannot read is exactly the
clause the parser refuses; a probe with no unread clause is refused, if at all, for a document-level reason.
Expected categories and amounts are written out by hand.
"""
from hashlib import sha256
import json
import re

import pytest

from uptime.contracts import Outcome
from uptime.vendor_eval import evaluate
from uptime.vendor_strict_diagnostics import SCHEMA, UNRECOGNIZED, _category, classify
from uptime.vendor_terms import Document, Overlay, bind_overlay, compile_terms

TITLE = 'Quillfeather Relay Mesh Hosting Agreement'
LINES = [
    TITLE,
    'Quillfeather Networks operates Relay Mesh on the Growth plan.',
    'This agreement is effective on 2026-03-01 through 2027-02-28.',
    'Uptime is measured over each UTC calendar month.',
    'Monthly uptime equals 100 * (1 - eligible downtime minutes / total minutes in the month).',
    '| Product | Plan | Monthly availability below | Service credit |',
    '| --- | --- | --- | --- |',
    '| Relay Mesh | Growth | 99.9% | 5% |',
    'Monthly uptime below 99% earns a 20% service credit.',
    'Only the highest applicable credit percentage applies; credit percentages do not accumulate.',
    'The service credit percentage applies to the affected monthly service fee in USD.',
    'Service credits will be credited to the next invoice.',
    'A complete claim must be filed within 45 calendar days following the end of the affected month.',
]
CATEGORIES = ['agreement_title', 'vendor_party_statement', 'effective_sentence', 'period', 'availability_formula',
              'table_header', 'table_separator', 'tier', 'tier_inherited_scope', 'tier_selection', 'remedy_fee_basis',
              'remedy_future_invoice', 'filing_days_article']
LOCATED = re.compile(r'Unsupported (?:source language|percentage table) at clause ([0-9]+)\.')


def document(lines):
    return Document(name='Fictional parity contract', uri='urn:uptime:fictional:quillfeather-relay',
                    classification='synthetic_public', text='\n'.join(lines) + '\n')


def parity(lines):
    """Classifier report and parser outcome, asserting the documented parity property."""
    report = classify(document(lines))
    try:
        manifest = compile_terms(document(lines))
    except ValueError as error:
        located = LOCATED.fullmatch(str(error))
        if report['unrecognized_clauses']:
            assert located is not None and int(located[1]) == report['unrecognized_clauses'][0], str(error)
        else:
            assert located is None, str(error)
        return report, str(error)
    assert report['unrecognized_clauses'] == [] and report['missing_required'] == []
    return report, manifest


def test_whole_contract_categories_offsets_and_parser_agree():
    report, manifest = parity(LINES)
    assert isinstance(manifest, dict)
    assert [row['category'] for row in report['clauses']] == CATEGORIES
    assert report['tier_present'] is True
    text = document(LINES).text
    for row, citation in zip(report['clauses'], manifest['citations'], strict=True):
        assert (row['clause'], row['start'], row['end']) == (citation['id'], citation['start'], citation['end'])
        assert row['characters'] == row['end'] - row['start']
        assert row['sha256'] == sha256(text[row['start']:row['end']].encode()).hexdigest()
    assert manifest['vendor'] == 'Quillfeather Networks' and manifest['agreement'] == TITLE
    assert manifest['effective'] == ['2026-03-01', '2027-02-28'] and manifest['filing_days'] == 45
    assert manifest['tiers'] == [
        {'product': 'Relay Mesh', 'plan': 'Growth', 'below_units': 99_000_000, 'credit_units': 20_000_000,
         'citation': 9, 'scope_citation': 8},
        {'product': 'Relay Mesh', 'plan': 'Growth', 'below_units': 99_900_000, 'credit_units': 5_000_000,
         'citation': 8}]


def test_report_shape_is_unchanged_and_carries_no_source_text():
    report = classify(document(LINES))
    assert set(report) == {'schema', 'source_sha256', 'clauses', 'unrecognized_clauses', 'missing_required',
                           'tier_present'}
    assert report['schema'] == SCHEMA == 'strict-clause-classification/1'
    dumped = json.dumps(report)
    for fragment in ('Quillfeather', 'Relay Mesh', 'Growth', '99.9', '2026-03-01', 'USD', 'next invoice'):
        assert fragment not in dumped


def without(index):
    return LINES[:index] + LINES[index + 1:]


def replaced(index, line):
    return LINES[:index] + [line] + LINES[index + 1:]


def inserted(index, line):
    return LINES[:index] + [line] + LINES[index:]


PROBES = [
    # (name, lines, first unread clause or None, parser message pattern for document-level refusals)
    ('title after a heading', ['Service Level Agreement'] + LINES, 2, None),
    ('title carrying a date', replaced(0, 'Quillfeather 2026 Relay Mesh Hosting Agreement'), 1, None),
    ('party statement with an exclusion',
     replaced(1, 'Quillfeather Networks operates Relay Mesh on the Growth plan except during previews.'), 2, None),
    ('party subject is not the vendor', replaced(1, 'The provider operates Relay Mesh on the Growth plan.'), 2, None),
    ('effective dates in words',
     replaced(2, 'This agreement is effective on March 1, 2026 through February 28, 2027.'), 3, None),
    ('formula with another denominator',
     replaced(4, 'Monthly uptime equals 100 * (1 - eligible downtime minutes / scheduled minutes in the month).'), 5, None),
    ('inherited tier before any scoped tier', LINES[:5] + [LINES[8]] + LINES[5:8] + LINES[9:], 6, None),
    ('accumulating tiers',
     replaced(9, 'Only the highest applicable credit percentage applies; credit percentages accumulate.'), 10, None),
    ('fee basis in another currency',
     replaced(10, 'The service credit percentage applies to the affected monthly service fee in EUR.'), 11, None),
    ('filing with a definite article',
     replaced(12, 'The complete claim must be filed within 45 calendar days following the end of the affected month.'),
     13, None),
    ('only the future-invoice half', without(10), None, r'Document lacks complete, unambiguous source coverage\.'),
    ('only the fee-basis half', without(11), None, r'Document lacks complete, unambiguous source coverage\.'),
    ('labeled agreement as well as a title', inserted(1, 'Contract ID: QF-2026-7'), None,
     r'Duplicate or conflicting source clause: agreement'),
    ('second declared scope', inserted(8, '| Relay Mesh | Scale | 99.5% | 10% |'), None,
     r'Ambiguous product/plan scope\.'),
    ('contradictory inherited tier', inserted(9, 'Monthly uptime below 99% earns a 25% service credit.'), None,
     r'Overlapping or nonmonotonic credit tiers\.'),
    ('reversed effective sentence', replaced(2, 'This agreement is effective on 2027-02-28 through 2026-03-01.'), None,
     r'Reversed effective interval\.'),
]


@pytest.mark.parametrize('name,lines,first_unread,message', PROBES, ids=[probe[0] for probe in PROBES])
def test_first_unread_clause_is_the_parser_refusal(name, lines, first_unread, message):
    report, outcome = parity(lines)
    assert isinstance(outcome, str), f'{name} must be refused'
    assert report['unrecognized_clauses'][:1] == ([first_unread] if first_unread else [])
    if message is not None:
        assert re.fullmatch(message, outcome)


def test_missing_required_counts_the_remedy_only_with_both_halves():
    assert classify(document(without(10)))['missing_required'] == ['remedy']
    assert classify(document(without(11)))['missing_required'] == ['remedy']
    assert classify(document(LINES))['missing_required'] == []
    title_late = classify(document(['Service Level Agreement'] + LINES))
    assert title_late['missing_required'] == ['agreement']


def test_original_template_categories_are_unchanged():
    legacy = ['Monthly Availability Agreement', 'Vendor: Lanternfish Data Co', 'Agreement: LF-SLA-7',
              'Effective: 2026-02-01 through 2027-01-31', 'Monthly availability is measured over each UTC calendar month.',
              'For Tidepool Storage on the Basic plan, monthly availability below 99.9% earns a 10% service credit.',
              'Service credits apply to the affected monthly fee and are applied to a future invoice.',
              'Claims must be received within 30 calendar days after month end.', 'Credits expire after one year.']
    report, outcome = parity(legacy)
    assert [row['category'] for row in report['clauses']] == [
        'heading', 'vendor', 'agreement', 'effective', 'period', 'tier', 'remedy', 'filing_days', UNRECOGNIZED]
    assert report['unrecognized_clauses'] == [9] and report['missing_required'] == []
    assert outcome == 'Unsupported source language at clause 9.'


def test_category_without_position_context_never_reads_position_dependent_templates():
    assert _category(TITLE, None) == (UNRECOGNIZED, None)
    assert _category('Monthly uptime below 99% earns a 20% service credit', None) == (UNRECOGNIZED, None)
    assert _category('Quillfeather Networks operates Relay Mesh on the Growth plan', None) == (
        'vendor_party_statement', None)


# June 2026 has 43,200 minutes. 99.9%: 0.999 * 43200 = 43156.8, so down 43 (43157 available) is not below and
# down 44 is. 99%: 0.99 * 43200 = 42768 exactly, so down 432 is exactly 99% (5% tier) and down 433 is below 99%.
# Fee USD 2,500.00: 5% = 125.00, 20% = 500.00. Filing: 45 days after 2026-07-01 closes at 2026-08-15T00:00Z.
@pytest.mark.parametrize('down,received,outcome,amount', [
    (43, '2026-08-14T23:59:59+00:00', Outcome.INELIGIBLE, None),
    (44, '2026-08-14T23:59:59+00:00', Outcome.ELIGIBLE, '125.00'),
    (432, '2026-07-01T00:00:00+00:00', Outcome.ELIGIBLE, '125.00'),
    (433, '2026-07-20T09:30:00+02:00', Outcome.ELIGIBLE, '500.00'),
    (433, '2026-08-15T00:00:00+00:00', Outcome.INELIGIBLE, None),
])
def test_table_scoped_inheritance_evaluates_exact_amounts(down, received, outcome, amount):
    manifest = compile_terms(document(LINES))
    bound = bind_overlay(manifest, Overlay(agreement=TITLE, account='QF-7781', product='Relay Mesh', plan='Growth',
                                           effective_from='2026-03-01', effective_until='2027-02-28',
                                           fee_line_ref='relay-mesh-growth', currency='USD'))
    facts = dict(agreement=TITLE, account='QF-7781', product='Relay Mesh', plan='Growth', fee_line_ref='relay-mesh-growth',
                 month='2026-06', monitor_source='simulated_vendor', month_complete=True, exclusions_removed=True,
                 eligible_downtime_minutes=down, monthly_fee_cents=250_000, received_at=received)
    result = evaluate(manifest, bound, facts, 'tenant-fictional')
    assert (result['outcome'], result['amount']) == (outcome.value, amount)
