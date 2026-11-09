"""Automatic selection refuses a common unsupported pattern for the correct, stated reason.

An authored public-style SLA (unlabeled parties, a maintenance exclusion) is read by provider doubles the way a
careful extraction would read it. No real inference occurs, and nothing here is derived from any evaluation
corpus or the sealed D05 selection.
"""
import json

from uptime.vendor_family_selection import MONTHLY, RESOURCE

from test_vendor_family_selection_89 import VENDOR, approve, auto, blocks_text, by_family, run, selecting  # noqa: F401

LINES = [
    'Northfield Queue Service Level Agreement',
    'Northfield Labs provides Northfield Queue on the Standard plan.',
    'This service level agreement is effective on 2026-02-01.',
    'We calculate availability for full calendar months using UTC.',
    'The availability commitment applies to the Northfield Queue product and the Standard plan.',
    '| Monthly availability below | Service credit |',
    '| --- | --- |',
    '| 99.9% | 10% |',
    'Downtime during scheduled maintenance announced 48 hours in advance is excluded.',
    'A claim must be submitted within 30 calendar days following month end.',
    'The credit is calculated from the affected monthly service fees and credited to your next invoice.',
]
DOCUMENT = {'name': 'Authored public-style SLA with a maintenance exclusion', 'uri': 'urn:synthetic:northfield-queue-sla',
            'classification': 'synthetic_public', 'text': '\n'.join(LINES)}
MONTHLY_READING = [
    {'quote': LINES[0], 'field': 'agreement', 'value': LINES[0]},
    {'quote': LINES[1], 'field': 'vendor', 'value': 'Northfield Labs'},
    {'quote': LINES[2], 'field': 'effective', 'value': ['2026-02-01', None]},
    {'quote': LINES[3], 'field': 'period', 'value': 'utc_calendar_month'},
    {'quote': LINES[4], 'field': 'scope', 'value': {'product': 'Northfield Queue', 'plan': 'Standard'}},
    {'quote': LINES[5], 'field': 'table_header', 'value': None},
    {'quote': LINES[6], 'field': 'table_separator', 'value': None},
    {'quote': LINES[7], 'field': 'tier', 'value': {'product': 'Northfield Queue', 'plan': 'Standard', 'below': '99.9', 'credit': '10'}},
    # A careful reading labels the exclusion for what it is; the monthly family has no exclusion field.
    {'quote': LINES[8], 'field': 'remedy', 'value': None},
    {'quote': LINES[9], 'field': 'filing_days', 'value': 30},
    {'quote': LINES[10], 'field': 'remedy', 'value': 'affected_monthly_fees_future_invoice'},
]
RESOURCE_READING = [
    {'agreement': LINES[0]}, {'vendor': 'Northfield Labs', 'scope': {'product': 'Northfield Queue', 'plan': 'Standard'}},
    {'effective': ['2026-02-01', None]}, {'period': 'resource_billing_month'},
    {'scope': {'product': 'Northfield Queue', 'plan': 'Standard'}}, {'nonmaterial': 'table header'},
    {'nonmaterial': 'table separator'}, {'tiers': [{'below': '99.9', 'credit': '10', 'at_least': None}]},
    {'exclusions': ['scheduled maintenance announced 48 hours in advance']},
    {'filing': {'kind': 'calendar_days', 'count': 30, 'utc_time': '00:00', 'endpoint': 'inclusive'}},
    {'remedy': 'future_noncash_credit'},
]


def test_maintenance_exclusion_refuses_both_families_with_the_passage_and_missing_terms(selecting):
    _, _, provider, _, _ = selecting
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': MONTHLY_READING}),
                        'resource-month': blocks_text(DOCUMENT, RESOURCE_READING)}
    approve(selecting, DOCUMENT)
    view = run(selecting, DOCUMENT)
    families = by_family(view)
    assert view['outcome'] == 'NO_SUPPORTED_FAMILY' and view['selected'] is None
    assert view['offline']['reason'] == 'NOT_CANONICAL'
    # Monthly: the exclusion sentence is refused deterministically (a material qualifier), and that passage is cited.
    assert families[MONTHLY]['state'] == 'REFUSED_STRUCTURAL'
    assert families[MONTHLY]['refusal']['codes'] == ['UNSUPPORTED_SOURCE_MATERIAL']
    assert families[MONTHLY]['refusal']['passages'] == [LINES[8]]
    # Resource month: no symptom, provider-cause or evidence terms exist in the source.
    missing = families[RESOURCE]['refusal']['missing_terms']
    assert {'qualifying symptoms', 'provider-caused conditions', 'evidence requirements'} <= set(missing)
    assert view['review_requirements'][0].startswith('Monthly availability:') and LINES[8] in view['review_requirements'][0]
    assert view['review_requirements'][1].startswith('Resource month:')
    assert 'No supported rule family' in view['review_requirements'][-1]
    assert sorted(provider.calls) == ['monthly-propositions', 'resource-month']


def test_the_same_source_without_the_exclusion_is_selected_as_monthly(selecting):
    _, _, provider, _, _ = selecting
    document = DOCUMENT | {'text': '\n'.join(LINES[:8] + LINES[9:])}
    reading = MONTHLY_READING[:8] + MONTHLY_READING[9:]
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': reading}),
                        'resource-month': blocks_text(document, RESOURCE_READING[:8] + RESOURCE_READING[9:])}
    approve(selecting, document)
    view = run(selecting, document)
    assert view['outcome'] == 'SELECTED' and view['selected']['family'] == MONTHLY
    assert by_family(view)[RESOURCE]['state'] in {'REFUSED_READING', 'REFUSED_STRUCTURAL'}
