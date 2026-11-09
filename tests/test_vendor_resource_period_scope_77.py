"""Decision 77: source-bound complete UTC calendar-month periods and service-month-scoped filing cutoffs.

All sources here are authored synthetic public text. Meaning review uses the named scripted test fixture
from test_vendor_semantic_bindings; nothing here claims an actual human review.
"""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import re

import pytest

from uptime.contracts import fingerprint
from uptime import vendor_service_month as service
from uptime.vendor_eval import evaluate
from uptime.vendor_model import validate_proposal
from uptime.vendor_resource_eval import Gap, Unsupported, deadline, month_bounds
from uptime.vendor_resource_operators import apply_operator
from uptime.vendor_terms import Document, Overlay, bind_overlay
import test_vendor_resource as resource


def compile_rows(rows, name='Synthetic Decision77 terms'):
    document = Document(name=name, classification='synthetic_public', uri='urn:synthetic:decision77',
                        text='\n'.join(quote for quote, _ in rows))
    return validate_proposal(document, [{'quote':q,'field':'resource_terms','value':v} for q, v in rows],
                             allow_propositions=True)


def reviewed(manifest, overlay, facts, tenant):
    from test_vendor_semantic_bindings import reviewed_context
    bound = bind_overlay(manifest, Overlay(**overlay))
    return evaluate(manifest, bound, facts, tenant, bindings=reviewed_context(manifest, bound, tenant=tenant))


# ---------------------------------------------------------------------------
# Part 1: the single fixed_period validator
# ---------------------------------------------------------------------------

APRIL = ('This commitment covers Oriole Index Business for the UTC calendar month April 2026, '
         'from 2026-04-01T00:00:00Z until 2026-05-01T00:00:00Z. That month contains 43,200 minutes.')
APRIL_PERIOD = {'start':'2026-04-01T00:00:00Z', 'end':'2026-05-01T00:00:00Z'}


def former_keyword_gate(quote, value):
    """Frozen copy of the removed keyword-presence condition, kept only as a before/after witness."""
    text = ' '.join(quote.casefold().split())
    return (value['start'].lower() in text and value['end'].lower() in text
            and bool(re.search('inclusive|including', text)) and bool(re.search('exclusive|excluding', text)))


def period(quote, value):
    manifest = {}
    service.validate(manifest, 'fixed_period', value, ' '.join(quote.split()))
    return manifest['fixed_period']


def test_unchanged_april_clause_was_refused_by_keyword_gate_and_now_binds_exact_endpoints():
    assert former_keyword_gate(APRIL, APRIL_PERIOD) is False
    assert period(APRIL, APRIL_PERIOD) == APRIL_PERIOD
    assert period(APRIL.split(' That month')[0], APRIL_PERIOD) == APRIL_PERIOD


@pytest.mark.parametrize('quote,value', [
    ('For the UTC calendar month February 2028, from 2028-02-01T00:00:00Z until 2028-03-01T00:00:00Z. '
     'That month contains 41,760 minutes.', {'start':'2028-02-01T00:00:00Z','end':'2028-03-01T00:00:00Z'}),
    ('This subscription covers from 2026-12-01T00:00:00Z until 2027-01-01T00:00:00Z, the UTC calendar month December 2026.',
     {'start':'2026-12-01T00:00:00Z','end':'2027-01-01T00:00:00Z'}),
    ('The service level commitment applies to Tern Relay during the entire UTC calendar month of September 2027 '
     '(from 2027-09-01T00:00:00Z until 2027-10-01T00:00:00Z).', {'start':'2027-09-01T00:00:00Z','end':'2027-10-01T00:00:00Z'}),
    ('For the UTC calendar month June 2026, from 2026-06-01T00:00:00+00:00 to 2026-07-01T00:00:00+00:00.',
     {'start':'2026-06-01T00:00:00+00:00','end':'2026-07-01T00:00:00+00:00'}),
    ('For the complete UTC calendar month January 2027, from 2027-01-01T00:00:00Z inclusive until 2027-02-01T00:00:00Z exclusive. '
     'The UTC month has 44640 minutes.', {'start':'2027-01-01T00:00:00Z','end':'2027-02-01T00:00:00Z'}),
])
def test_other_month_and_year_templates_bind_label_and_both_endpoints(quote, value):
    assert period(quote, value) == value


@pytest.mark.parametrize('quote', [
    'This subscription covers 2027-02-01T00:00:00Z inclusive to 2027-03-01T00:00:00Z exclusive.',
    'From 2027-02-01T00:00:00Z (inclusive) until 2027-03-01T00:00:00Z (exclusive).',
    'The agreement covers from and including 2027-02-01T00:00:00Z to but excluding 2027-03-01T00:00:00Z.',
])
def test_old_explicit_start_inclusive_end_exclusive_forms_are_preserved(quote):
    value = {'start':'2027-02-01T00:00:00Z','end':'2027-03-01T00:00:00Z'}
    assert period(quote, value) == value


A, B = APRIL_PERIOD['start'], APRIL_PERIOD['end']
REFUSED_PERIODS = [
    # "until" alone has no endpoint authority without the calendar-month assertion.
    (f'This commitment covers Oriole Index Business from {A} until {B}.', APRIL_PERIOD),
    (f'For the calendar month April 2026, from {A} until {B}.', APRIL_PERIOD),
    (f'For the UTC calendar month March 2026, from {A} until {B}.', APRIL_PERIOD),
    (f'For the UTC calendar month April 2027, from {A} until {B}.', APRIL_PERIOD),
    (f'For the UTC calendar month April, from {A} until {B}.', APRIL_PERIOD),
    (f'For the UTC calendar month Apr 2026, from {A} until {B}.', APRIL_PERIOD),
    (f'For the UTC calendar month April 2026, from {B} until {A}.', APRIL_PERIOD),
    ('For the UTC calendar month April 2026, from 2026-05-01T00:00:00Z until 2026-04-01T00:00:00Z.',
     {'start':'2026-05-01T00:00:00Z','end':'2026-04-01T00:00:00Z'}),
    ('For the UTC calendar month April 2026, from 2026-04-01T00:00:01Z until 2026-05-01T00:00:01Z.',
     {'start':'2026-04-01T00:00:01Z','end':'2026-05-01T00:00:01Z'}),
    (f'For the UTC calendar month April 2026, from {A} until 2026-04-30T00:00:00Z.', {'start':A,'end':'2026-04-30T00:00:00Z'}),
    (f'For the UTC calendar month April 2026, from {A} until 2026-05-02T00:00:00Z.', {'start':A,'end':'2026-05-02T00:00:00Z'}),
    (f'For the UTC calendar month April 2026, from {A} until 2026-06-01T00:00:00Z.', {'start':A,'end':'2026-06-01T00:00:00Z'}),
    (f'For the UTC calendar month April 2026, from {A} until {B} inclusive.', APRIL_PERIOD),
    (f'For the UTC calendar month April 2026, from {A} through {B}.', APRIL_PERIOD),
    (f'This period is not the complete UTC calendar month April 2026, from {A} until {B}.', APRIL_PERIOD),
    (f'For the UTC calendar month April 2026, from {A} until {B}, unless maintenance extends it.', APRIL_PERIOD),
    (f'For the UTC calendar month April 2026, from {A} until {B}, except scheduled maintenance days.', APRIL_PERIOD),
    (f'If renewed, for the UTC calendar month April 2026, from {A} until {B}.', APRIL_PERIOD),
    (APRIL + ' A transition period runs from 2026-04-15T00:00:00Z until 2026-05-15T00:00:00Z.', APRIL_PERIOD),
    (APRIL.replace('43,200', '44,640'), APRIL_PERIOD),
    ('That month contains 43,200 minutes. ' + APRIL.split(' That month')[0], APRIL_PERIOD),
    (APRIL.split(' That month')[0] + ' ' + APRIL.split(' That month')[0], APRIL_PERIOD),
    (f'The UTC calendar month is April 2026. The period runs from {A} until {B}.', APRIL_PERIOD),
    (f'This commitment covers Partial April Index for the UTC calendar month April 2026, from {A} until {B}.', APRIL_PERIOD),
    (f'For the UTC calendar month April 2026, from {A.lower()} until {B.lower()}.', APRIL_PERIOD),
    # Old explicit forms: comparators bind to the matching timestamp only.
    (f'This subscription covers {A} exclusive to {B} inclusive.', APRIL_PERIOD),
    (f'This subscription covers {A} inclusive to {B} non-exclusive.', APRIL_PERIOD),
    (f'Fees including taxes are charged from {A} to {B}, excluding credits.', APRIL_PERIOD),
    (f'This subscription covers {A} to {B}. Start is inclusive and end is exclusive.', APRIL_PERIOD),
]


@pytest.mark.parametrize('quote,value', REFUSED_PERIODS)
def test_unsupported_or_contradictory_period_assertions_refuse(quote, value):
    with pytest.raises(ValueError, match='Fixed period'):
        period(quote, value)


def test_keyword_gate_accepted_cross_clause_and_reversed_forms_that_now_refuse():
    for quote in (f'This subscription covers {A} exclusive to {B} inclusive.',
                  f'Fees including taxes are charged from {A} to {B}, excluding credits.',
                  f'This subscription covers {A} to {B}. Start is inclusive and end is exclusive.'):
        assert former_keyword_gate(quote, APRIL_PERIOD) is True
        with pytest.raises(ValueError):
            period(quote, APRIL_PERIOD)


@pytest.mark.parametrize('value', [
    {'start':'2026-04-01T02:00:00+02:00','end':'2026-05-01T02:00:00+02:00'},
    {'start':'2026-04-01T00:00:00.000Z','end':'2026-05-01T00:00:00.000Z'},
    {'start':'2026-04-01T00:00:00','end':'2026-05-01T00:00:00'},
    {'start':A},
])
def test_non_utc_subsecond_and_incomplete_bounds_refuse(value):
    quote = f"For the UTC calendar month April 2026, from {value['start']} until {value.get('end', B)}."
    with pytest.raises(ValueError):
        period(quote, value)


SCOPE_APRIL = {'scope':{'product':'Oriole Index','plan':'Business'}, 'fixed_period':APRIL_PERIOD}
AGGREGATE_ROWS = [
    ('Provider: Oriole Data Works', {'vendor':'Oriole Data Works'}),
    (APRIL, SCOPE_APRIL),
    ('Monthly availability is 100 times (43,200 minus unavailable minutes) divided by 43,200.',
     {'interval_measurement':['availability_ratio']}),
    ('Monthly availability below 99.5% receives a 10% service credit.',
     {'tiers':[{'below':'99.5','credit':'10','at_least':None}]}),
    ('Use the paid recurring subscription fee on the itemized invoice.', {'service_fee':'paid_recurring_subscription'}),
    ('Round credits to the nearest cent, half up.', {'rounding':'nearest_cent_half_up'}),
    ('The remedy is a noncash service credit.', {'remedy':'noncash_service_credit'}),
    ('The claim must be received no later than 2026-05-15T00:00:00Z inclusive.',
     {'fixed_filing':{'at':'2026-05-15T00:00:00Z','endpoint':'inclusive'}}),
    ('The provider status record of unavailable minutes is authoritative.', {'aggregate_monitor':'authoritative_vendor_minutes'}),
]
AGGREGATE_OVERLAY = {'agreement':'Oriole-4','account':'acct-4','product':'Oriole Index','plan':'Business',
                     'effective_from':'2026-04-01','effective_until':'2026-04-30','currency':'USD',
                     'fee_line_ref':'oriole-subscription'}


def aggregate_facts():
    scope = {k:AGGREGATE_OVERLAY[k] for k in ('agreement','account','product','plan')} | {'month':'2026-04'}

    def record(ref, content):
        return dict(**scope, ref=ref, verified=True, complete=True, recorded_at='2026-05-02T12:00:00Z',
                    content=content, content_sha256=fingerprint(content))
    return dict(**scope, fee_line_ref='oriole-subscription',
                service_monitor=record('status-4', {'source':'simulated_vendor','unavailable_minutes':300}),
                service_invoice=record('invoice-4', {'currency':'USD','paid':True,'lines':[
                    {'ref':'oriole-subscription','kind':'recurring_subscription','category':'subscription','amount_cents':10000}]}),
                filing_proof=dict(**scope, verified=True, ref='claim-4', received_at='2026-05-15T00:00:00Z'))


def test_april_aggregate_source_compiles_end_to_end_with_scope_and_original_citation():
    manifest = compile_rows(AGGREGATE_ROWS)
    assert manifest['fixed_period'] == APRIL_PERIOD and manifest['scope'] == SCOPE_APRIL['scope']
    assert manifest['effective'] == ['2026-04-01', '2026-04-30']
    citation = manifest['citations'][1]
    assert citation['quote'] == APRIL and citation['propositions'] == SCOPE_APRIL
    assert 'inclusive' not in citation['quote'] and 'exclusive' not in citation['quote']
    result = reviewed(manifest, AGGREGATE_OVERLAY, aggregate_facts(), 'oriole-tenant')
    assert result['outcome'] == 'ELIGIBLE' and result['amount'] == '10.00'
    assert result['total_microseconds'] == 43_200 * 60_000_000


def test_aggregate_profile_refuses_a_scoped_filing_primitive():
    rows = AGGREGATE_ROWS + [('Claims must be received no later than 2026-05-15T00:00:00Z for the April 2026 service month.',
                              {'scoped_filing':{'month':'2026-04','at':'2026-05-15T00:00:00Z','endpoint':'inclusive','basis':'received'}})]
    with pytest.raises(ValueError, match='scoped filing'):
        compile_rows(rows)


# ---------------------------------------------------------------------------
# Part 2: scoped_filing operator, compilation and deadline dispatch
# ---------------------------------------------------------------------------

NOV_QUOTE = 'Claims must be received no later than 2026-12-10T18:00:00Z for the November 2026 service month.'
NOV = {'month':'2026-11','at':'2026-12-10T18:00:00Z','endpoint':'inclusive','basis':'received'}
NOV_EXCLUSIVE_QUOTE = 'For the November 2026 service month, credit requests must be received before 2026-12-10T18:00:00Z.'
NOV_EXCLUSIVE = NOV | {'endpoint':'exclusive'}
DEC_QUOTE = 'Credit requests shall be received before 2027-01-08T00:00:00Z for the December 2026 service month.'
DEC = {'month':'2026-12','at':'2027-01-08T00:00:00Z','endpoint':'exclusive','basis':'received'}


def scoped_rows(*extra):
    """The authored resource source, with its relative filing block replaced by scoped blocks."""
    return resource.ROWS[:9] + [(quote, {'scoped_filing':value}) for quote, value in extra] + resource.ROWS[10:]


def interval(ref, left, right, base, cause='instrument gateway failure'):
    return resource.interval(ref, left, right, cause) | {'start':(base + timedelta(minutes=left)).isoformat(),
                                                          'end':(base + timedelta(minutes=right)).isoformat()}


def month_facts(month, received_at):
    base = datetime.fromisoformat(month + '-05T00:00:00+00:00')
    facts = deepcopy(resource.FACTS)
    facts.update(month=month, received_at=received_at,
                 intervals=[interval('n1', 0, 900, base), interval('n2', 400, 600, base)],
                 exclusions=[interval('s1', 100, 267, base, 'Customer cable damage')],
                 fee_lines=[line | {'month':month} for line in resource.FACTS['fee_lines']])
    return facts


def run(manifest, facts):
    return reviewed(manifest, resource.OVERLAY, facts, resource.P.tenant)


def test_source_bound_november_policy_compiles_with_exact_citation_and_no_relative_count():
    manifest = compile_rows(scoped_rows((NOV_QUOTE, NOV)))
    citation = manifest['citations'][9]
    assert citation['quote'] == NOV_QUOTE and citation['propositions'] == {'scoped_filing':NOV}
    assert manifest['filing'] == {'kind':'scoped_absolute', 'policies':{'2026-11':{
        'at':'2026-12-10T18:00:00Z', 'endpoint':'inclusive', 'basis':'received', 'citation':citation['id'],
        'block_sha256':sha256(NOV_QUOTE.encode()).hexdigest()}}}
    assert not {'fixed_filing', 'fixed_filing_days', 'scoped_filing'} & manifest.keys()
    assert manifest['effective'] == ['2026-02-01', None]


@pytest.mark.parametrize('received,outcome', [
    ('2026-12-10T17:59:59Z', 'ELIGIBLE'),
    ('2026-12-10T18:00:00Z', 'ELIGIBLE'),
    ('2026-12-10T18:00:00.000001Z', 'INELIGIBLE'),
    ('2026-11-30T23:59:59Z', 'INELIGIBLE'),
])
def test_matching_month_inclusive_boundary(received, outcome):
    result = run(compile_rows(scoped_rows((NOV_QUOTE, NOV))), month_facts('2026-11', received))
    assert result['outcome'] == outcome
    assert result['claim_cutoff'] == '2026-12-10T18:00:00+00:00' and result['cutoff_inclusive'] is True
    assert result['amount'] == ('12.51' if outcome == 'ELIGIBLE' else None)


@pytest.mark.parametrize('received,outcome', [
    ('2026-12-10T17:59:59.999999Z', 'ELIGIBLE'),
    ('2026-12-10T18:00:00Z', 'INELIGIBLE'),
    ('2026-12-10T18:00:01Z', 'INELIGIBLE'),
])
def test_matching_month_exclusive_boundary(received, outcome):
    result = run(compile_rows(scoped_rows((NOV_EXCLUSIVE_QUOTE, NOV_EXCLUSIVE))), month_facts('2026-11', received))
    assert result['outcome'] == outcome and result['cutoff_inclusive'] is False
    assert result['claim_cutoff_exclusive'] == '2026-12-10T18:00:00+00:00'
    if outcome == 'INELIGIBLE':
        assert result['filing_status'] == 'OUTSIDE_WINDOW' and result['amount'] is None


@pytest.mark.parametrize('month,received', [('2026-12', '2027-01-05T00:00:00Z'), ('2026-10', '2026-11-05T00:00:00Z'),
                                            ('2027-11', '2027-12-05T00:00:00Z')])
def test_otherwise_complete_off_month_claim_stays_unknown_and_never_inherits_november(month, received):
    manifest = compile_rows(scoped_rows((NOV_QUOTE, NOV)))
    result = run(manifest, month_facts(month, received))
    assert result['outcome'] == 'INSUFFICIENT_EVIDENCE' and result['amount'] is None
    assert 'claim_cutoff' not in result and 'cutoff_inclusive' not in result
    assert result['missing'] == ['No source-bound filing deadline is established for this service month.']
    # Without reviewed meaning, the published-clock context still never borrows November's cutoff.
    bound = bind_overlay(manifest, Overlay(**resource.OVERLAY))
    unreviewed = evaluate(manifest, bound, month_facts(month, received), resource.P.tenant)
    assert unreviewed['amount'] is None and 'claim_cutoff' not in unreviewed
    matching = evaluate(manifest, bound, month_facts('2026-11', '2026-12-01T00:00:00Z'), resource.P.tenant)
    assert matching['amount'] is None and matching['claim_cutoff'] == '2026-12-10T18:00:00+00:00'


def test_distinct_named_month_policies_coexist_and_each_governs_only_its_month():
    manifest = compile_rows(scoped_rows((NOV_QUOTE, NOV), (DEC_QUOTE, DEC)))
    assert set(manifest['filing']['policies']) == {'2026-11', '2026-12'}
    december = run(manifest, month_facts('2026-12', '2027-01-07T23:59:59Z'))
    assert december['outcome'] == 'ELIGIBLE' and december['claim_cutoff'] == '2027-01-08T00:00:00+00:00'
    assert run(manifest, month_facts('2026-12', '2027-01-08T00:00:00Z'))['outcome'] == 'INELIGIBLE'
    assert run(manifest, month_facts('2027-01', '2027-02-01T00:00:00Z'))['outcome'] == 'INSUFFICIENT_EVIDENCE'


SCOPED_POLICY = {'kind':'scoped_absolute', 'policies':{'2026-11':{'at':'2026-12-10T18:00:00Z','endpoint':'inclusive',
                                                                    'basis':'received','citation':10,'block_sha256':'0'*64}}}


def test_direct_deadline_requires_exact_month_matching_bounds_and_receipt_evidence():
    manifest = {'filing':SCOPED_POLICY}
    _, november_end = month_bounds('2026-11')
    _, december_end = month_bounds('2026-12')
    facts = {'month':'2026-11', 'received_at':'2026-12-01T00:00:00Z'}
    assert deadline(facts, {}, manifest, november_end) == (datetime(2026, 12, 10, 18, tzinfo=UTC), True)
    exclusive = deepcopy(manifest)
    exclusive['filing']['policies']['2026-11']['endpoint'] = 'exclusive'
    assert deadline(facts, {}, exclusive, november_end) == (datetime(2026, 12, 10, 18, tzinfo=UTC), False)
    for changed, end in [({'month':'2026-12'}, december_end), ({'month':None}, november_end),
                         ({'month':['2026-11']}, november_end), ({'month':'2026-11/2026-12'}, december_end),
                         ({'month':'November 2026'}, november_end), ({}, december_end),
                         ({'received_at':None}, november_end), ({'received_at':'2026-12-01'}, november_end)]:
        with pytest.raises(Gap):
            deadline(facts | changed, {}, manifest, end)
    with pytest.raises(Gap):
        deadline({'received_at':'2026-12-01T00:00:00Z'}, {}, manifest, november_end)
    with pytest.raises(Gap):
        deadline({'month':'2026-11', 'filed_at':'2026-12-01T00:00:00Z'}, {}, manifest, november_end)
    with pytest.raises(Unsupported):
        deadline(facts, {'override':{'filing_days':30}}, manifest, november_end)
    for broken in ({'basis':'filed'}, {'endpoint':'whole_day'}, {'at':'2026-12-10T18:00:00+01:00'}):
        damaged = deepcopy(manifest)
        damaged['filing']['policies']['2026-11'].update(broken)
        with pytest.raises(Unsupported):
            deadline(facts, {}, damaged, november_end)


def test_relative_filing_paths_are_unchanged_by_the_scoped_dispatch():
    _, end = month_bounds('2026-06')
    assert deadline({'month':'2026-06'}, {}, resource.compiled(), end) == (datetime(2026, 7, 10, 18, tzinfo=UTC), True)


def test_private_relative_override_cannot_replace_a_scoped_deadline():
    manifest = compile_rows(scoped_rows((NOV_QUOTE, NOV)))
    override = {'filing_days':30, 'source_ref':'signed-order-page-4', 'effective_from':'2026-03-01',
                'quote':'Claims must be received within 30 calendar days after month end.'}
    with pytest.raises(ValueError, match='calendar-day override'):
        bind_overlay(manifest, Overlay(**(resource.OVERLAY | {'override':override})))


@pytest.mark.parametrize('rows', [
    pytest.param(resource.ROWS + [(NOV_QUOTE, {'scoped_filing':NOV})], id='relative-then-scoped'),
    pytest.param(resource.ROWS[:9] + [(NOV_QUOTE, {'scoped_filing':NOV}), resource.ROWS[9]] + resource.ROWS[10:],
                 id='scoped-then-relative'),
    pytest.param(scoped_rows((NOV_QUOTE, NOV), (NOV_EXCLUSIVE_QUOTE.replace('18:00:00Z', '18:00:01Z'),
                                                NOV_EXCLUSIVE | {'at':'2026-12-10T18:00:01Z'})), id='duplicate-month'),
    pytest.param(scoped_rows(('Claims must be received no later than 2026-02-10T18:00:00Z for the January 2026 service month.',
                              NOV | {'month':'2026-01','at':'2026-02-10T18:00:00Z'})), id='before-effective-coverage'),
])
def test_conflicting_duplicate_or_out_of_coverage_scoped_policies_refuse(rows):
    with pytest.raises(ValueError):
        compile_rows(rows)


def test_scoped_month_must_lie_wholly_inside_a_bounded_effective_interval():
    rows = scoped_rows((NOV_QUOTE, NOV))
    rows[1] = ('Version effective February 1, 2026 through November 15, 2026.', {'effective':['2026-02-01', '2026-11-15']})
    with pytest.raises(ValueError, match='effective coverage'):
        compile_rows(rows)
    rows[1] = ('Version effective February 1, 2026 through November 30, 2026.', {'effective':['2026-02-01', '2026-11-30']})
    assert compile_rows(rows)['effective'] == ['2026-02-01', '2026-11-30']


REFUSED_SCOPED = [
    ('Claims must be received no later than 2026-12-10T18:00:00Z for the November service month.', NOV),
    (NOV_QUOTE, NOV | {'basis':'filed'}),
    (NOV_QUOTE.replace('received', 'filed'), NOV | {'basis':'filed'}),
    (NOV_QUOTE.replace('received', 'submitted'), NOV),
    (NOV_QUOTE, {k:v for k, v in NOV.items() if k != 'basis'}),
    (NOV_QUOTE, NOV | {'at':'2026-12-10T18:00:01Z'}),
    (NOV_QUOTE, NOV | {'month':'2026-12'}),
    (NOV_QUOTE, NOV | {'endpoint':'exclusive'}),
    (NOV_EXCLUSIVE_QUOTE, NOV),
    (NOV_QUOTE, NOV | {'filed_at':'2026-12-10T18:00:00Z'}),
    (NOV_QUOTE.replace('18:00:00Z', '18:00:00+01:00'), NOV | {'at':'2026-12-10T18:00:00+01:00'}),
    (NOV_QUOTE.replace('18:00:00Z', '18:00:00.000Z'), NOV | {'at':'2026-12-10T18:00:00.000Z'}),
    (NOV_QUOTE.replace('18:00:00Z', '18:00:00'), NOV | {'at':'2026-12-10T18:00:00'}),
    (NOV_QUOTE[:-1] + ', within 10 calendar days after the service month.', NOV),
    (NOV_QUOTE + ' Claims must be received within 10 calendar days after the service month.', NOV),
    (NOV_QUOTE + ' Claims must be received before 2026-12-12T00:00:00Z for the November 2026 service month.', NOV),
    ('Claims must not be received later than 2026-12-10T18:00:00Z for the November 2026 service month.', NOV),
    ('Claims need not be received no later than 2026-12-10T18:00:00Z for the November 2026 service month.', NOV),
    (NOV_QUOTE[:-1] + ' unless extended in writing.', NOV),
    (NOV_QUOTE[:-1] + ' where practicable.', NOV),
    ('Claims must be received by the vendor at 2026-12-10T18:00:00Z for the November 2026 service month.', NOV),
    ('Claims must be received by the vendor before 2026-12-10T18:00:00Z for the November 2026 service month.', NOV),
    ('Claims must be received no later than 2026-11-20T00:00:00Z for the November 2026 service month.',
     NOV | {'at':'2026-11-20T00:00:00Z'}),
    ('Claims must be received before 2026-12-01T00:00:00Z for the November 2026 service month.',
     NOV | {'at':'2026-12-01T00:00:00Z','endpoint':'exclusive'}),
    ('Claims must be received no later than 2026-12-10T18:00:00Z for the November 2026 and December 2026 service months.', NOV),
    ('Claims must be received no later than 2026-12-10T18:00:00Z.', NOV),
]


@pytest.mark.parametrize('quote,value', REFUSED_SCOPED)
def test_ungrounded_qualified_or_contradictory_scoped_filing_refuses_without_side_effects(quote, value):
    manifest = {'citations':[{'id':1, 'block_sha256':'0'*64}]}
    with pytest.raises(ValueError):
        apply_operator(manifest, 'scoped_filing', value, ' '.join(quote.split()))
    assert manifest == {'citations':[{'id':1, 'block_sha256':'0'*64}]}
    with pytest.raises(ValueError):
        compile_rows(scoped_rows((quote, value)))


def test_accepted_scoped_forms_never_write_a_relative_day_count():
    for quote, value in [(NOV_QUOTE, NOV), (NOV_EXCLUSIVE_QUOTE, NOV_EXCLUSIVE), (DEC_QUOTE, DEC),
                         ('Claims must be received by the provider on or before 2026-12-10T18:00:00Z for the November 2026 UTC service month.', NOV),
                         ('Service credit claims must be received by 2026-12-10T18:00:00Z for November 2026 service month.', NOV)]:
        manifest = {'citations':[{'id':7, 'block_sha256':'1'*64}]}
        apply_operator(manifest, 'scoped_filing', value, quote)
        assert set(manifest) == {'citations', 'filing'} and manifest['filing']['kind'] == 'scoped_absolute'
        assert manifest['filing']['policies'][value['month']]['citation'] == 7


def test_supported_scoped_filing_never_discards_an_unsupported_neighbor():
    rows = scoped_rows((NOV_QUOTE, NOV)) + [
        ('The provider may extend any filing deadline at its sole discretion.',
         {'unsupported':'Discretionary filing extension has no finite decision rule.'})]
    with pytest.raises(ValueError, match='Unsupported material'):
        compile_rows(rows)


@pytest.mark.parametrize('year,month,end,days', [(2032, '02', '2032-03-01', 29), (2029, '12', '2030-01-01', 31)])
def test_explicit_period_retains_finite_supplier_duration_and_closed_scope_context(year, month, end, days):
    start = f'{year}-{month}-01T00:00:00Z'
    stop = end + 'T00:00:00Z'
    quote = (f'Birch Harbor supplies Queue Store on the Silver plan. This agreement covers that service '
             f'for the single monthly period from {start} inclusive to {stop} exclusive. '
             f'The monthly period is exactly {days} days, or {days * 1440:,} minutes. '
             'All times are UTC. There are no other covered services or periods.')
    value = {'start':start, 'end':stop}
    assert period(quote, value) == value
    for malformed in (
        quote.replace(f'{days} days', f'{days + 1} days'),
        quote.replace(f'{days * 1440:,} minutes', '1 minutes'),
        quote.replace(f'{start} inclusive', f'{start} exclusive'),
        quote.replace(f'{stop} exclusive', f'{stop} inclusive'),
        quote.replace('covers that service', 'does not cover that service'),
        quote.replace(' supplies ', ' does not supply '),
        quote.replace('All times are UTC.', 'All times are local.'),
        quote.replace('There are no other covered services or periods.', 'There are other covered services or periods.'),
        quote + ' Except the last day.',
        quote + f' The next period starts at {stop}.',
    ):
        with pytest.raises(ValueError, match='Fixed period'):
            period(malformed, value)
