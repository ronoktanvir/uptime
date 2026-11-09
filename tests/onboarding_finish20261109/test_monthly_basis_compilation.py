"""Source-to-manifest-to-proposal controls for the optional monthly evidence path.

Provider records here are explicit test doubles. Actual public-model quality is
measured separately by the independent evaluation owner.
"""
from copy import deepcopy
import json

import pytest

from uptime.vendor_model import MODEL, proposal_input, proposal_receipt, validate_proposal, verify_receipt
from uptime.vendor_monthly_basis import KIND, validate_monthly_evidence_basis
from uptime.vendor_terms import Document, compile_terms
from test_vendor_catalog import DOC, proposition_document
from test_monthly_basis_helper import QUOTE


def test_strict_source_opt_in_is_exactly_cited_and_legacy_has_no_marker():
    legacy = Document(**(DOC | {'text': DOC['text'].replace('| Message Relay | Premier | 99.9% | 40% |\n', '')}))
    old = compile_terms(legacy)
    assert 'evidence_basis' not in old
    source = legacy.model_copy(update={'text': legacy.text + '\n' + QUOTE})
    parsed = compile_terms(source)
    assert parsed['evidence_basis'] == KIND
    assert validate_monthly_evidence_basis(parsed)
    c = next(c for c in parsed['citations'] if c['field'] == 'evidence_basis')
    assert source.text[c['start']:c['end']] == QUOTE == c['quote']
    assert [(t['below_units'], t['credit_units']) for t in old['tiers']] == [
        (t['below_units'], t['credit_units']) for t in parsed['tiers']]


def proposal():
    raw, clauses = proposition_document()
    raw['text'] += '\n' + QUOTE
    clauses.append({'quote': QUOTE, 'field': 'evidence_basis', 'value': KIND})
    return Document(**raw), clauses


def test_proposition_path_preserves_human_interpretation_gate_and_explicit_basis():
    document, clauses = proposal()
    with pytest.raises(ValueError):
        validate_proposal(document, clauses, allow_propositions=False)
    manifest = validate_proposal(document, clauses, allow_propositions=True)
    assert manifest['interpretation'] == 'model_proposition_human_review_required'
    assert validate_monthly_evidence_basis(manifest)


def test_public_model_wire_carries_marker_and_receipt_revalidates_it():
    document, clauses = proposal()
    prompt, public_input = proposal_input(document, 'monthly-propositions')
    assert 'evidence_basis' in prompt and KIND in prompt
    assert public_input['text'] == document.text
    receipt = proposal_receipt(document, 'monthly-propositions',
                               {'model': MODEL, 'session': 'authored-wire-control',
                                'text': json.dumps({'clauses': clauses})}, at='2026-11-09T20:00:00Z')
    rebuilt, _ = verify_receipt(document, receipt, allow_propositions=True)
    assert validate_monthly_evidence_basis(rebuilt)
    assert rebuilt['interpretation'] == 'model_proposition_human_review_required'


@pytest.mark.parametrize('quote', [
    QUOTE.replace('are not required', 'are required'),
    QUOTE.replace('complete UTC calendar-month', 'partial UTC calendar-month'),
    QUOTE + ' Provider approval is also required.',
    QUOTE.replace('entire service', 'one incident'),
])
def test_model_cannot_override_the_source_with_a_monthly_marker(quote):
    document, clauses = proposal()
    document.text = document.text.replace(QUOTE, quote)
    clauses[-1]['quote'] = quote
    with pytest.raises(ValueError):
        validate_proposal(document, clauses, allow_propositions=True)


def test_model_cannot_infer_marker_by_relabeling_measurement_clause():
    raw, clauses = proposition_document()
    period = next(row for row in clauses if row['field'] == 'period')
    period.update(field='evidence_basis', value=KIND)
    with pytest.raises(ValueError):
        validate_proposal(Document(**raw), clauses, allow_propositions=True)


def test_duplicate_basis_and_multiple_scopes_refuse():
    document, clauses = proposal()
    document.text += '\n' + QUOTE
    clauses.append(deepcopy(clauses[-1]))
    with pytest.raises(ValueError):
        validate_proposal(document, clauses, allow_propositions=True)
    multi = Document(**(DOC | {'text': DOC['text'] + '\n' + QUOTE}))
    with pytest.raises(ValueError):
        compile_terms(multi)


@pytest.mark.parametrize('conflict', [
    'Claims must include an incident identifier.',
    'An incident report is required for every claim.',
    'Claims are assessed for individual incidents only.',
])
def test_separate_incident_requirement_conflicts_with_monthly_opt_in(conflict):
    base = DOC['text'].replace('| Message Relay | Premier | 99.9% | 40% |\n', '')
    strict = Document(**(DOC | {'text': base + '\n' + QUOTE + '\n' + conflict}))
    with pytest.raises(ValueError):
        compile_terms(strict)
    document, clauses = proposal()
    document.text += '\n' + conflict
    # A malicious extraction may not hide the extra requirement as a heading.
    clauses.append({'quote': conflict, 'field': 'heading', 'value': None})
    with pytest.raises(ValueError):
        validate_proposal(document, clauses, allow_propositions=True)


def test_model_must_quote_the_original_monthly_basis_without_rewriting():
    document, clauses = proposal()
    clauses[-1]['quote'] = QUOTE.replace('are based on', 'use')
    with pytest.raises(ValueError):
        validate_proposal(document, clauses, allow_propositions=True)


def test_new_strict_templates_have_representable_public_model_fields():
    from test_parent_financial_controls import SOURCE
    text = SOURCE + '\n' + QUOTE
    doc = Document(name='Authored public wire contract', uri='urn:synthetic:wire-contract',
                   classification='synthetic_public', text=text)
    fields = [
        ('agreement', 'Copperleaf Compute Agreement'), ('vendor', 'Copperleaf Systems'),
        ('effective', ['2026-01-01', '2026-12-31']), ('period', 'utc_calendar_month'),
        ('tier', {'product': 'Compute', 'plan': 'Standard', 'below': '99.9', 'credit': '10'}),
        ('tier', {'product': 'Compute', 'plan': 'Standard', 'below': '99', 'credit': '20'}),
        ('tier_selection', 'highest_applicable_only'),
        ('remedy', 'affected_monthly_fees_future_invoice'), ('remedy', 'affected_monthly_fees_future_invoice'),
        ('filing_days', 30), ('evidence_basis', KIND),
    ]
    clauses = [{'quote': q, 'field': f, 'value': v} for q, (f, v) in zip(text.split('\n'), fields, strict=True)]
    manifest = validate_proposal(doc, clauses, allow_propositions=True)
    assert validate_monthly_evidence_basis(manifest)
    assert manifest['tier_selection'] == 'highest_applicable_only'
    assert 'interpretation' not in manifest  # Fully supported strict clauses need no fallback inference.
    # The same reviewed forms remain usable when an unrelated, supported clause
    # requires the opt-in proposition path; they must not be silently dropped.
    broad = 'We calculate availability for full calendar months using UTC.'
    doc.text = doc.text.replace(clauses[3]['quote'], broad)
    clauses[3]['quote'] = broad
    manifest = validate_proposal(doc, clauses, allow_propositions=True)
    assert validate_monthly_evidence_basis(manifest)
    assert manifest['interpretation'] == 'model_proposition_human_review_required'


def test_requirement_card_recognizes_validated_new_fields_but_retains_unknown_review():
    from uptime.vendor_requirements import requirement_card
    from test_strict_template_remediation_20261109 import compiled, LINES
    manifest = compiled(LINES)
    marker_source = Document(**(DOC | {'text': DOC['text'].replace(
        '| Message Relay | Premier | 99.9% | 40% |\n', '') + '\n' + QUOTE}))
    for candidate in (manifest, compile_terms(marker_source)):
        card = requirement_card(candidate, {})
        exclusions = next(e for e in card['elements'] if e['element'] == 'exclusions')
        assert exclusions['status'] == 'NONE_STATED'
        changed = deepcopy(candidate)
        changed['unsupported_condition'] = 'provider discretion'
        unresolved = requirement_card(changed, {})
        exclusions = next(e for e in unresolved['elements'] if e['element'] == 'exclusions')
        assert exclusions['status'] == 'REVIEW_REQUIRED'
        assert exclusions['detail']['uncategorized'] == ['unsupported_condition']


def test_model_cannot_make_ambiguous_until_inclusive():
    raw, clauses = proposition_document()
    term = next(c for c in clauses if c['field'] == 'effective')
    replacement = 'This agreement is effective on 2026-01-01 until 2026-12-31.'
    raw['text'] = raw['text'].replace(term['quote'], replacement)
    term['quote'] = replacement
    with pytest.raises(ValueError, match='explicitly establish inclusion'):
        validate_proposal(Document(**raw), clauses, allow_propositions=True)
