"""Explicit monthly source marker, independent of claim/authorization code."""
from copy import deepcopy
from hashlib import sha256

import pytest

from uptime.vendor_monthly_basis import KIND, is_monthly_basis_clause, validate_monthly_evidence_basis

QUOTE = ('Claims are based on a complete UTC calendar-month report for the entire service; '
         'incident identifiers are not required.')


def manifest():
    return {'family': 'monthly-availability/1', 'period': 'utc_calendar_month', 'filing_days': 30,
            'remedy': 'affected_monthly_fees_future_invoice', 'evidence_basis': KIND,
            'document': {'sha256': sha256(QUOTE.encode()).hexdigest()},
            'tiers': [{'product': 'Compute', 'plan': 'Team'}],
            'citations': [{'field': 'period'}, {'field': 'filing_days'},
                          {'id': 3, 'field': 'evidence_basis', 'start': 0, 'end': len(QUOTE), 'quote': QUOTE}]}


def test_absence_retains_legacy_and_does_not_implicitly_opt_in():
    old = manifest()
    del old['evidence_basis']
    assert validate_monthly_evidence_basis(old) is False
    assert validate_monthly_evidence_basis(manifest()) is True


@pytest.mark.parametrize('quote', [
    QUOTE.replace('are not required', 'are required'),
    QUOTE.replace('complete UTC', 'partial UTC'),
    QUOTE.replace('UTC calendar-month', 'rolling thirty-day'),
    QUOTE.replace('entire service', 'one incident'),
    QUOTE + ' Unless the provider requests incident details.',
    QUOTE.replace('; incident', '; except incident'),
    'Incident identifiers are not required.',
])
def test_negation_conditions_and_missing_month_basis_do_not_opt_in(quote):
    assert is_monthly_basis_clause(quote) is False
    changed = manifest()
    changed['citations'][-1].update(quote=quote, end=len(quote))
    with pytest.raises(ValueError):
        validate_monthly_evidence_basis(changed)


@pytest.mark.parametrize('field,value', [
    ('evidence_basis', 'unknown/1'), ('family', 'resource-month/1'), ('period', 'rolling_month'),
    ('remedy', 'cash_refund'), ('filing_days', True), ('filing_days', 0),
    ('tiers', []), ('tiers', [{'product': 'Compute', 'plan': 'Team'}, {'product': 'Storage', 'plan': 'Team'}]),
    ('document', {}),
])
def test_invalid_or_conflicting_manifest_context_refuses(field, value):
    changed = manifest()
    changed[field] = value
    with pytest.raises(ValueError):
        validate_monthly_evidence_basis(changed)


@pytest.mark.parametrize('field', ['period', 'filing_days', 'evidence_basis'])
def test_missing_or_duplicate_grounding_refuses(field):
    changed = manifest()
    row = next(row for row in changed['citations'] if row['field'] == field)
    changed['citations'].remove(row)
    with pytest.raises(ValueError):
        validate_monthly_evidence_basis(changed)
    changed['citations'].extend([row, deepcopy(row)])
    with pytest.raises(ValueError):
        validate_monthly_evidence_basis(changed)


@pytest.mark.parametrize('field,value', [('start', -1), ('start', True), ('end', len(QUOTE)-1), ('id', True)])
def test_citation_location_is_not_coerced(field, value):
    changed = manifest()
    changed['citations'][-1][field] = value
    with pytest.raises(ValueError):
        validate_monthly_evidence_basis(changed)
