"""Decision 80: source-bound aggregate fixed filing deadlines.

All sources here are authored synthetic public text. Meaning review uses the scripted test fixture from
test_vendor_semantic_bindings via the existing Decision77 helper; nothing here claims an actual human review,
a real claim filing or a real award. Eligibility previews below are local simulated evaluations only.
"""
from copy import deepcopy
import re

import pytest

from uptime import vendor_service_month as service
import test_vendor_resource_period_scope_77 as d77
import test_vendor_service_month as compass

T = '2026-05-15T00:00:00Z'
INC = {'at':T, 'endpoint':'inclusive'}
EXC = {'at':T, 'endpoint':'exclusive'}
BASE = f'The claim must be received no later than {T} inclusive.'
BUG = f'Claims may be received by the vendor at {T}; no filing deadline applies.'

# The three known complete source blocks, verbatim from the Decision80 packet.
FORM_DUE = 'The claim is due within 6 days after the service month, no later than 2027-03-07T00:00:00Z inclusive.'
FORM_RECEIVED = 'The claim must be received no later than 2026-05-15T00:00:00Z inclusive.'
FORM_FILED = ('The timestamped claim must be filed within 14 days after the monthly period ends, no later than '
              '2031-05-15T00:00:00Z. Filing exactly at that timestamp is permitted. A claim filed later receives no credit.')
SEED = {'citations':[{'id':1, 'block_sha256':'0'*64}]}


def former_filing_gate(quote, value):
    """Frozen copy of the removed keyword-presence condition, kept only as a before/after witness."""
    text = ' '.join(quote.casefold().split())
    return (bool(re.search('claim|filing|filed|receive', text)) and value['at'].lower() in text and bool(re.search(
        r'no later than|inclusive|exactly.{0,40}permitted|\bby\b' if value['endpoint'] == 'inclusive'
        else r'\bbefore\b|exclusive', text)))


def filing(quote, value, manifest=None):
    manifest = deepcopy(SEED) if manifest is None else manifest
    service.validate(manifest, 'fixed_filing', value, ' '.join(quote.split()))
    return manifest


def aggregate_rows(quote, value):
    rows = list(d77.AGGREGATE_ROWS)
    assert rows[7][1].keys() == {'fixed_filing'}
    rows[7] = (quote, {'fixed_filing':value})
    return rows


# ---------------------------------------------------------------------------
# Known forms and the finite comparator table
# ---------------------------------------------------------------------------

def test_known_blocks_are_the_authored_compatibility_sources():
    assert compass.ROWS[9][0] == FORM_DUE
    assert d77.AGGREGATE_ROWS[7][0] == FORM_RECEIVED


@pytest.mark.parametrize('quote,value,days', [
    (FORM_DUE, {'at':'2027-03-07T00:00:00Z', 'endpoint':'inclusive'}, 6),
    (FORM_RECEIVED, INC, None),
    (FORM_FILED, {'at':'2031-05-15T00:00:00Z', 'endpoint':'inclusive'}, 14),
])
def test_three_known_blocks_bind_cutoff_comparator_and_same_sentence_days(quote, value, days):
    manifest = filing(quote, value)
    expected = deepcopy(SEED) | {'fixed_filing':value} | ({} if days is None else {'fixed_filing_days':days})
    assert manifest == expected


@pytest.mark.parametrize('quote,value', [
    (f'The claim must be received by {T}.', INC),
    (f'The claim must be received by {T} inclusive.', INC),
    (f'The claim must be received at or before {T}.', INC),
    (f'The claim shall be filed on or before {T}.', INC),
    (f'The claim must be received no later than {T}.', INC),
    (f'The claim must be received by the vendor no later than {T} inclusive.', INC),
    (f'The claim must be received by the provider by {T}.', INC),
    (f'The claim must be received by the provider on or before {T}. Filing exactly at that timestamp is permitted.', INC),
    (f'The claim must be received before {T}.', EXC),
    (f'The claim must be received strictly before {T} exclusive.', EXC),
    (f'The claim must be received by the vendor before {T}.', EXC),
    (f'The claim must be filed before {T}. A claim filed later receives no credit.', EXC),
    (f'The claim must be filed no later than {T}. A claim filed later receives no credit.', INC),
    (f'The claim must be received no later than {T}. A claim filed later receives no credit. '
     'Filing exactly at that timestamp is permitted.', INC),
    ('The claim must be received no later than 2026-05-15T00:00:00+00:00 inclusive.',
     {'at':'2026-05-15T00:00:00+00:00', 'endpoint':'inclusive'}),
])
def test_explicit_comparator_table_and_finite_companions(quote, value):
    assert filing(quote, value) == deepcopy(SEED) | {'fixed_filing':value}


def test_relative_days_with_exclusive_endpoint_and_calendar_unit_are_same_sentence_only():
    quote = f'The claim must be received within 14 calendar days following the service month, before {T}.'
    assert filing(quote, EXC)['fixed_filing_days'] == 14


# ---------------------------------------------------------------------------
# Refusals: never mutate, never guess a comparator
# ---------------------------------------------------------------------------

REFUSED = [
    # The documented bug and recipient-only "by".
    (BUG, INC), (BUG, EXC),
    (f'The claim must be received by the vendor at {T}.', INC),
    (f'The claim must be received by the vendor {T}.', INC),
    (f'The claim must be received by the vendor. Filing exactly at {T} is permitted.', INC),
    (f'The claim must be received by the vendor. The claim must be received at {T}.', INC),
    (f'The claim must be received at {T}.', INC),
    (f'The claim is due by the vendor no later than {T}.', INC),
    # Negative, permissive, no-deadline, conditional and excepted forms.
    (f'The claim must not be received later than {T}.', INC),
    (f'The claim must not be received no later than {T} inclusive.', INC),
    (f'The claim need not be received no later than {T} inclusive.', INC),
    (f'The claim may be received no later than {T} inclusive.', INC),
    ('No filing deadline applies. ' + BASE, INC),
    (BASE + ' No filing deadline applies.', INC),
    (BASE[:-1] + '; no filing deadline applies.', INC),
    (f'If renewed, the claim must be received no later than {T} inclusive.', INC),
    (BASE[:-1] + ' unless extended in writing.', INC),
    (BASE[:-1] + ', except for disputed invoices.', INC),
    (BASE[:-1] + ' where practicable.', INC),
    # Contradictory suffixes and endpoints.
    (f'The claim must be received no later than {T} exclusive.', INC),
    (f'The claim must be received no later than {T} exclusive.', EXC),
    (f'The claim must be received no later than {T} non-inclusive.', INC),
    (f'The claim must be received no later than {T} non-inclusive.', EXC),
    (f'The claim must be received before {T} inclusive.', INC),
    (f'The claim must be received before {T} inclusive.', EXC),
    (f'The claim must be received before {T}.', INC),
    (f'The claim must be received by {T} exclusive.', EXC),
    (BASE, EXC),
    # Companions: enumerated, affirmative, consistent, once each.
    (f'The claim must be received before {T}. Filing exactly at that timestamp is permitted.', EXC),
    (BASE + ' Filing exactly at that timestamp is not permitted.', INC),
    (f'The claim must be received before {T}. Filing exactly at that timestamp is not permitted.', EXC),
    (BASE + ' Filing exactly at that timestamp is permitted. Filing exactly at that timestamp is permitted.', INC),
    (BASE + ' A claim filed later may still receive credit.', INC),
    (BASE + ' A claim received later receives no credit.', INC),
    ('Filing exactly at that timestamp is permitted. ' + BASE, INC),
    (BASE + ' ﬁling exactly at that timestamp is permitted.', INC),
    # Extra relative statements, second clocks, unrelated material and timestamps.
    (BASE + ' Credits are issued within 30 days after the service month.', INC),
    (FORM_DUE + ' Credits are issued within 30 days after the service month.', {'at':'2027-03-07T00:00:00Z', 'endpoint':'inclusive'}),
    (BASE + ' The claim must be received before 2026-05-20T00:00:00Z.', INC),
    (BASE + ' The monthly period ends at 2026-05-01T00:00:00Z.', INC),
    (f'The claim must be received no later than {T} inclusive and no later than 2026-05-20T00:00:00Z inclusive.', INC),
    (BASE + ' The credit is 10.00 USD.', INC),
    (BASE + ' Monthly availability below 99.5% receives a 10% service credit.', INC),
    (BASE[:-1] + ' for the April 2026 service month.', INC),
    # Days from the wrong obligation, unsupported clocks and unbounded counts.
    (f'Credits are issued within 14 days after the service month, and the claim must be received no later than {T} inclusive.', INC),
    (f'The claim must be received within 14 days after the service month. Credits are issued no later than {T} inclusive.', INC),
    (f'The credit must be issued within 14 days after the service month, no later than {T} inclusive.', INC),
    (f'The claim must be received within 14 business days after the service month, no later than {T} inclusive.', INC),
    (f'The claim must be received within 14 days after the outage starts, no later than {T} inclusive.', INC),
    (f'The claim must be received within 14 days after the service month no later than {T} inclusive.', INC),
    (f'The claim must be received within 0 days after the service month, no later than {T} inclusive.', INC),
    (f'The claim must be received within 1000 days after the service month, no later than {T} inclusive.', INC),
    (f'The claim must be received within 06 days after the service month, no later than {T} inclusive.', INC),
    (f'The claim must be received within ١٤ days after the service month, no later than {T} inclusive.', INC),
    (f'The claim must be received within 14 days after the service month, within 15 days after the monthly period ends, '
     f'no later than {T} inclusive.', INC),
    # Textual timestamp grounding.
    (BASE, {'at':'2026-05-15T00:00:01Z', 'endpoint':'inclusive'}),
    (BASE, {'at':'2026-05-15T00:00:00+00:00', 'endpoint':'inclusive'}),
    (BASE.replace('00Z', '00+00:00'), INC),
    (BASE.replace(T, T.lower()), INC),
    (BASE.replace(T, T + '1'), INC),
    (BASE.replace(T, 'https://example.invalid/' + T), INC),
    ('', INC),
]


@pytest.mark.parametrize('quote,value', REFUSED)
def test_unsupported_or_contradictory_filing_blocks_refuse_without_mutation(quote, value):
    manifest = deepcopy(SEED)
    with pytest.raises(ValueError):
        filing(quote, value, manifest)
    assert manifest == SEED


@pytest.mark.parametrize('quote,value', [(q, v) for q, v in REFUSED if q])
def test_refused_filing_blocks_never_compile_an_aggregate_source(quote, value):
    with pytest.raises(ValueError):
        d77.compile_rows(aggregate_rows(quote, value))


def test_keyword_gate_accepted_bug_negation_and_recipient_forms_that_now_refuse():
    for quote, value in [(BUG, INC), (BASE + ' Filing exactly at that timestamp is not permitted.', INC),
                         (f'The claim must be received no later than {T} non-inclusive.', INC),
                         (f'The claim must be received by the vendor at {T}.', INC),
                         (BASE + ' Credits are issued within 30 days after the service month.', INC)]:
        assert former_filing_gate(quote, value) is True
        with pytest.raises(ValueError, match='filing cutoff'):
            filing(quote, value)


@pytest.mark.parametrize('quote,value', [
    (BASE, None), (BASE, []), (BASE, 'inclusive'), (BASE, {'at':T}),
    (BASE, {'at':T, 'endpoint':'whole_day'}), (BASE, {'at':T, 'endpoint':'inclusive', 'days':6}),
    (BASE, {'at':1778803200, 'endpoint':'inclusive'}), (BASE, {'at':None, 'endpoint':'inclusive'}),
    (BASE.replace(T, '2026-05-15T00:00:00.000Z'), {'at':'2026-05-15T00:00:00.000Z', 'endpoint':'inclusive'}),
    (BASE.replace(T, '2026-05-15T02:00:00+02:00'), {'at':'2026-05-15T02:00:00+02:00', 'endpoint':'inclusive'}),
    (BASE.replace(T, '2026-05-15T00:00:00'), {'at':'2026-05-15T00:00:00', 'endpoint':'inclusive'}),
    (BASE.replace(T, '2026-02-30T00:00:00Z'), {'at':'2026-02-30T00:00:00Z', 'endpoint':'inclusive'}),
])
def test_malformed_proposals_and_non_utc_timestamps_refuse_without_mutation(quote, value):
    manifest = deepcopy(SEED)
    with pytest.raises(ValueError):
        filing(quote, value, manifest)
    assert manifest == SEED


# ---------------------------------------------------------------------------
# Atomic stored state and idempotence
# ---------------------------------------------------------------------------

DUE_VALUE = {'at':'2027-03-07T00:00:00Z', 'endpoint':'inclusive'}


def test_repeated_identical_validation_is_idempotent():
    for quote, value in [(FORM_DUE, DUE_VALUE), (FORM_RECEIVED, INC)]:
        once = filing(quote, value)
        assert filing(quote, value, deepcopy(once)) == once


def test_identical_absolute_assertion_without_days_keeps_established_days_in_either_order():
    absolute = 'The claim must be received no later than 2027-03-07T00:00:00Z inclusive.'
    first = filing(FORM_DUE, DUE_VALUE)
    assert filing(absolute, DUE_VALUE, deepcopy(first)) == first
    assert filing(FORM_DUE, DUE_VALUE, filing(absolute, DUE_VALUE)) == first


@pytest.mark.parametrize('stored', [
    {'fixed_filing_days':7},
    {'fixed_filing':DUE_VALUE, 'fixed_filing_days':7},
    {'fixed_filing':{'at':'2027-03-08T00:00:00Z', 'endpoint':'inclusive'}},
    {'fixed_filing':{'at':'2027-03-07T00:00:00Z', 'endpoint':'exclusive'}},
    {'fixed_filing':{'at':'2027-03-08T00:00:00Z', 'endpoint':'inclusive'}, 'fixed_filing_days':6},
])
def test_conflicting_stored_filing_or_days_refuse_atomically(stored):
    manifest = deepcopy(SEED) | deepcopy(stored)
    before = deepcopy(manifest)
    with pytest.raises(ValueError, match='Conflicting'):
        filing(FORM_DUE, DUE_VALUE, manifest)
    assert manifest == before


def test_conflicting_repeated_relative_count_refuses_atomically():
    manifest = filing(FORM_DUE, DUE_VALUE)
    before = deepcopy(manifest)
    with pytest.raises(ValueError, match='relative filing'):
        filing(FORM_DUE.replace('within 6 days', 'within 7 days'), DUE_VALUE, manifest)
    assert manifest == before


# ---------------------------------------------------------------------------
# Full compile and local simulated evaluation
# ---------------------------------------------------------------------------

def test_documented_bug_block_refuses_compilation_before_any_eligibility_preview():
    rows = aggregate_rows(BUG, INC)
    # Compilation raises, so no manifest exists from which an amount, filing status or preview could be built.
    with pytest.raises(ValueError, match='stated filing cutoff and comparator'):
        d77.compile_rows(rows)
    with pytest.raises(ValueError, match='stated filing cutoff and comparator'):
        d77.compile_rows(aggregate_rows(BUG, EXC))


def test_known_compass_and_april_sources_compile_with_unchanged_citation_and_clock():
    terms = compass.manifest()
    assert terms['fixed_filing'] == DUE_VALUE and terms['fixed_filing_days'] == 6
    assert terms['citations'][9]['quote'] == FORM_DUE
    april = d77.compile_rows(d77.AGGREGATE_ROWS)
    assert april['fixed_filing'] == INC and 'fixed_filing_days' not in april
    assert april['citations'][7]['quote'] == FORM_RECEIVED


def simulated(manifest, received):
    facts = d77.aggregate_facts()
    facts['filing_proof']['received_at'] = received
    return d77.reviewed(manifest, d77.AGGREGATE_OVERLAY, facts, 'oriole-tenant')


@pytest.mark.parametrize('received,outcome', [
    ('2026-05-14T23:59:59.999999Z', 'ELIGIBLE'),
    (T, 'ELIGIBLE'),
    ('2026-05-15T00:00:00.000001Z', 'INELIGIBLE'),
])
def test_inclusive_compiled_cutoff_before_at_and_after(received, outcome):
    result = simulated(d77.compile_rows(d77.AGGREGATE_ROWS), received)
    assert result['outcome'] == outcome and result['cutoff_inclusive'] is True
    assert result['amount'] == ('10.00' if outcome == 'ELIGIBLE' else None)
    if outcome == 'INELIGIBLE':
        assert result['filing_status'] == 'OUTSIDE_WINDOW'


@pytest.mark.parametrize('received,outcome', [
    ('2026-05-14T23:59:59.999999Z', 'ELIGIBLE'),
    (T, 'INELIGIBLE'),
    ('2026-05-15T00:00:00.000001Z', 'INELIGIBLE'),
])
def test_exclusive_compiled_cutoff_before_at_and_after(received, outcome):
    manifest = d77.compile_rows(aggregate_rows(f'The claim must be received before {T}.', EXC))
    assert manifest['fixed_filing'] == EXC
    result = simulated(manifest, received)
    assert result['outcome'] == outcome and result['cutoff_inclusive'] is False
    assert result['amount'] == ('10.00' if outcome == 'ELIGIBLE' else None)
    if outcome == 'INELIGIBLE':
        assert result['filing_status'] == 'OUTSIDE_WINDOW'


def test_compiler_relative_days_consistency_is_preserved():
    rows = deepcopy(compass.ROWS)
    rows[9] = (FORM_DUE.replace('within 6 days', 'within 7 days'), rows[9][1])
    with pytest.raises(ValueError, match='relative filing'):
        compass.manifest(rows)


@pytest.mark.parametrize('quote,value', [
    (f'Claims must be received no later than {T}.', INC),
    (f'The claims shall be received by the vendor before {T}.', EXC),
    (f'Claim must be filed on or before {T}.', INC),
    (f'Timestamped claims are due by {T} inclusive.', INC),
])
def test_singular_and_plural_claim_obligations_keep_exact_comparator_binding(quote, value):
    assert filing(quote, value)['fixed_filing'] == value
    assert d77.compile_rows(aggregate_rows(quote, value))['fixed_filing'] == value
    with pytest.raises(ValueError):
        filing(quote + ' No filing deadline applies.', value)
