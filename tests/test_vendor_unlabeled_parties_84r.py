"""Unlabeled party statements and title-line agreements in the guarded monthly propositions grammar.

Named remediation for one phrasing class found in the evaluation 84 first attempts (summaries only; no
corpus text, label or sealed answer was read). Every source here is authored. The 0/4 first-attempt
score is unchanged by this work; only a new independent cohort can measure improvement.
"""
from copy import deepcopy

import pytest

from uptime.vendor_model import validate_proposal
from uptime.vendor_terms import Document

ROWS = [
    ('Halcyon Ferry Service Commitment', 'agreement', 'Halcyon Ferry Service Commitment'),
    ('Halcyon Ferry provides Queue Mesh on the Basin plan.', 'vendor', 'Halcyon Ferry'),
    ('This service level agreement is effective on 2026-02-01.', 'effective', ['2026-02-01', None]),
    ('We calculate availability for full calendar months using UTC.', 'period', 'utc_calendar_month'),
    ('The availability commitment applies to the Queue Mesh product and the Basin plan.', 'scope',
     {'product': 'Queue Mesh', 'plan': 'Basin'}),
    ('| Monthly availability below | Service credit |', 'table_header', None),
    ('| --- | --- |', 'table_separator', None),
    ('| 99.9% | 15% |', 'tier', {'product': 'Queue Mesh', 'plan': 'Basin', 'below': '99.9', 'credit': '15'}),
    ('A claim must be submitted within 21 calendar days following month end.', 'filing_days', 21),
    ('The credit is calculated from the affected monthly service fees and credited to your next invoice.', 'remedy',
     'affected_monthly_fees_future_invoice'),
]


def source(rows=ROWS):
    document = {'name': 'Authored unlabeled-party SLA', 'uri': 'urn:synthetic:halcyon-ferry-commitment',
                'classification': 'synthetic_public', 'text': '\n'.join(quote for quote, _, _ in rows)}
    return Document(**document), [{'quote': q, 'field': f, 'value': deepcopy(v)} for q, f, v in rows]


def test_unlabeled_party_statement_and_title_line_ground_vendor_and_agreement():
    manifest = validate_proposal(*source(), allow_propositions=True)
    assert manifest['vendor'] == 'Halcyon Ferry' and manifest['agreement'] == 'Halcyon Ferry Service Commitment'
    assert manifest['interpretation'] == 'model_proposition_human_review_required'
    assert {c['field'] for c in manifest['citations']} >= {'vendor', 'agreement'}


@pytest.mark.parametrize('index,quote,value', [
    # The provider must be the grammatical subject of the supply verb, stated exactly.
    (1, 'Queue Mesh is supplied by Halcyon Ferry on the Basin plan.', 'Halcyon Ferry'),
    (1, 'Halcyon Ferry provides Queue Mesh on the Basin plan.', 'Halcyon'),
    (1, 'halcyon ferry provides Queue Mesh on the Basin plan.', 'Halcyon Ferry'),
    (1, 'Halcyon Ferry resells Queue Mesh on the Basin plan.', 'Halcyon Ferry'),
    # Qualified supply is refused before grounding.
    (1, 'Halcyon Ferry may provide Queue Mesh on the Basin plan.', 'Halcyon Ferry'),
])
def test_party_statement_must_name_the_provider_as_subject_of_a_supply_verb(index, quote, value):
    rows = list(ROWS)
    rows[index] = (quote, 'vendor', value)
    with pytest.raises(ValueError):
        validate_proposal(*source(rows), allow_propositions=True)


@pytest.mark.parametrize('change', [
    lambda rows: [rows[1], rows[0]] + rows[2:],                                   # title not the opening line
    lambda rows: [('Halcyon Ferry Service Commitment', 'agreement', 'Halcyon Ferry')] + rows[1:],   # value not the whole title
    lambda rows: [('Halcyon Ferry Service Commitment, 2026 edition', 'agreement',
                   'Halcyon Ferry Service Commitment, 2026 edition')] + rows[1:],  # punctuation
    lambda rows: [('Halcyon Ferry Service Commitment effective 2026-02-01', 'agreement',
                   'Halcyon Ferry Service Commitment effective 2026-02-01')] + rows[1:],  # a date
    lambda rows: [('Halcyon Ferry Queue Mesh Basin Plan Availability Service Credit Claims Filing Remedy Terms Edition',
                   'agreement', 'Halcyon Ferry Queue Mesh Basin Plan Availability Service Credit Claims Filing Remedy Terms Edition')] + rows[1:],
])
def test_title_agreement_must_be_the_whole_short_opening_line(change):
    with pytest.raises(ValueError):
        validate_proposal(*source(change(list(ROWS))), allow_propositions=True)


def test_labeled_forms_are_unchanged():
    from test_vendor_catalog import proposition_document
    document, proposal = proposition_document()
    manifest = validate_proposal(Document(**document), proposal, allow_propositions=True)
    assert manifest['vendor'] == 'Stratosphere Networks' and manifest['agreement'] == 'Test-AG-3'
