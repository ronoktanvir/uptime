"""Strict-template onboarding remediation (plan classes 1-3, 5, 7-11) on authored fictional sources.

Every source here is invented for these tests; no vendor, customer, evaluation or runtime material is used.
Expected values are worked out by hand in the comments, never read back from the parser or the evaluator.
Nothing here calls a model, Ramp, a network, an approval or a signing path.
"""
from decimal import Decimal
from hashlib import sha256
import re

import pytest

from uptime.contracts import Outcome
from uptime.vendor_eval import evaluate, generated_checks
from uptime.vendor_model import validate_proposal
from uptime.vendor_requirements import requirement_card
from uptime.vendor_terms import Document, FilingOverride, Overlay, bind_overlay, compile_terms

TITLE = 'Harborlight Beacon Compute Service Agreement'  # 44 characters
LINES = [
    TITLE,                                                                                   # 1  class 1
    'Harborlight Systems provides Beacon Compute under the Standard plan.',                 # 2  class 2 (68 chars)
    'This agreement takes effect on 2026-01-01 and ends on 2026-12-31.',                     # 3  class 3
    'Monthly availability is measured over each UTC calendar month.',                        # 4  original template
    'Monthly availability is calculated as 100 × (1 − eligible downtime minutes ÷ total minutes in the month).',  # 5
    'For Beacon Compute on the Standard plan, monthly availability below 99.95% earns a 7.5% service credit.',  # 6
    'Monthly availability below 99.5% earns a 15% service credit.',                          # 7  class 7
    'Monthly availability below 97.25% earns a 30% service credit.',                         # 8  class 7
    'Only the highest applicable percentage applies; percentages do not accumulate.',        # 9  class 8
    'The credit percentage applies to the affected monthly service fee in USD.',             # 10 class 9
    'Credits are applied to a future invoice.',                                              # 11 class 10
    'A claim must be received within 30 calendar days after month end.',                     # 12 class 11
]
ACCOUNT, FEE_LINE, TENANT = 'HB-ACCT-0042', 'beacon-standard-monthly', 'tenant-fictional'
FEE_CENTS = 98_765  # USD 987.65
COVERAGE = '^' + re.escape('Document lacks complete, unambiguous source coverage.') + '$'
AMBIGUOUS = '^' + re.escape('Ambiguous product/plan scope.') + '$'
OVERLAP = '^' + re.escape('Overlapping or nonmonotonic credit tiers.') + '$'


def source(lines, newline='\n'):
    return newline.join(lines) + newline


def document(text):
    return Document(name='Fictional remediation contract', uri='urn:uptime:fictional:harborlight-beacon',
                    classification='synthetic_public', text=text)


def compiled(lines):
    return compile_terms(document(source(lines)))


def replaced(index, line):
    return LINES[:index] + [line] + LINES[index + 1:]


def inserted(index, line):
    return LINES[:index] + [line] + LINES[index:]


def removed(index):
    return LINES[:index] + LINES[index + 1:]


def at_clause(number):
    return '^' + re.escape(f'Unsupported source language at clause {number}.') + '$'


def duplicate(key):
    return '^' + re.escape('Duplicate or conflicting source clause: ' + key) + '$'


def refuses(lines, pattern):
    with pytest.raises(ValueError, match=pattern):
        compiled(lines)


def overlay(**changes):
    values = dict(agreement=TITLE, account=ACCOUNT, product='Beacon Compute', plan='Standard',
                  effective_from='2026-01-01', effective_until='2027-06-30', fee_line_ref=FEE_LINE, currency='USD')
    return Overlay(**(values | changes))


def facts(month, down, *, fee=FEE_CENTS, received='2026-05-10T12:00:00+00:00'):
    return dict(agreement=TITLE, account=ACCOUNT, product='Beacon Compute', plan='Standard', fee_line_ref=FEE_LINE,
                month=month, monitor_source='simulated_vendor', month_complete=True, exclusions_removed=True,
                eligible_downtime_minutes=down, monthly_fee_cents=fee, received_at=received)


@pytest.fixture(scope='module')
def bound():
    manifest = compiled(LINES)
    return manifest, bind_overlay(manifest, overlay())


# ---------- the whole authored contract ----------

def test_whole_contract_with_all_nine_classes_compiles_to_hand_derived_terms():
    manifest = compiled(LINES)
    assert set(manifest) == {'family', 'document', 'tiers', 'citations', 'vendor', 'agreement', 'effective', 'period',
                             'availability_formula', 'tier_selection', 'remedy', 'filing_days'}
    assert manifest['family'] == 'monthly-availability/1'
    assert manifest['document']['sha256'] == sha256(source(LINES).encode()).hexdigest()
    assert manifest['vendor'] == 'Harborlight Systems'
    assert manifest['agreement'] == TITLE
    assert manifest['effective'] == ['2026-01-01', '2026-12-31']
    assert manifest['period'] == 'utc_calendar_month'
    assert manifest['availability_formula'] == 'one_minus_eligible_downtime_over_month_minutes'
    assert manifest['tier_selection'] == 'highest_applicable_only'
    assert manifest['remedy'] == 'affected_monthly_fees_future_invoice'
    assert manifest['filing_days'] == 30 and type(manifest['filing_days']) is int
    # Units are millionths of a percent: 99.95% -> 99_950_000, 7.5% -> 7_500_000. Clauses 7 and 8 inherit the
    # only declared scope and cite the explicitly scoped tier (clause 6) it came from.
    assert manifest['tiers'] == [
        {'product': 'Beacon Compute', 'plan': 'Standard', 'below_units': 97_250_000, 'credit_units': 30_000_000,
         'citation': 8, 'scope_citation': 6},
        {'product': 'Beacon Compute', 'plan': 'Standard', 'below_units': 99_500_000, 'credit_units': 15_000_000,
         'citation': 7, 'scope_citation': 6},
        {'product': 'Beacon Compute', 'plan': 'Standard', 'below_units': 99_950_000, 'credit_units': 7_500_000,
         'citation': 6},
    ]
    assert [c['field'] for c in manifest['citations']] == [
        'agreement', 'vendor', 'effective', 'period', 'availability_formula', 'tier', 'tier', 'tier',
        'tier_selection', 'remedy', 'remedy', 'filing_days']


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_citation_offsets_quotes_and_identity_bytes_are_exact_source_slices(newline):
    text = source(LINES, newline)
    manifest = compile_terms(document(text))
    offset = 0
    for number, (line, citation) in enumerate(zip(LINES, manifest['citations'], strict=True), 1):
        assert citation['id'] == number
        assert (citation['start'], citation['end'], citation['quote']) == (offset, offset + len(line), line)
        assert text[citation['start']:citation['end']] == line
        offset += len(line) + len(newline)
    # Hand-counted: the title is 44 characters; the party statement is 68 and starts after one line break.
    step = len(newline)
    assert (manifest['citations'][0]['start'], manifest['citations'][0]['end']) == (0, 44)
    assert (manifest['citations'][1]['start'], manifest['citations'][1]['end']) == (44 + step, 44 + step + 68)
    # Identity values are byte-identical slices of the cited source, never rewritten.
    title, party = manifest['citations'][0], manifest['citations'][1]
    assert text[title['start']:title['end']].encode() == manifest['agreement'].encode() == TITLE.encode()
    assert text[party['start']:party['start'] + 19] == manifest['vendor'] == 'Harborlight Systems'
    # Every percentage the units came from is literally present in its cited clause.
    by_citation = {c['id']: c['quote'] for c in manifest['citations']}
    for below, credit, cited in (('99.95%', '7.5%', 6), ('99.5%', '15%', 7), ('97.25%', '30%', 8)):
        assert f'below {below} earns a {credit} service credit' in by_citation[cited]


def test_segment_proposal_route_compiles_the_same_terms_and_checks_every_value():
    text = source(LINES)
    standard = {'product': 'Beacon Compute', 'plan': 'Standard'}
    remedy = 'affected_monthly_fees_future_invoice'
    values = [('agreement', TITLE), ('vendor', 'Harborlight Systems'), ('effective', ['2026-01-01', '2026-12-31']),
              ('period', 'utc_calendar_month'),
              ('availability_formula', 'one_minus_eligible_downtime_over_month_minutes'),
              ('tier', standard | {'below': '99.95', 'credit': '7.5'}), ('tier', standard | {'below': '99.5', 'credit': '15'}),
              ('tier', standard | {'below': '97.25', 'credit': '30'}), ('tier_selection', 'highest_applicable_only'),
              ('remedy', remedy), ('remedy', remedy), ('filing_days', 30)]
    clauses = [{'quote': line, 'field': field, 'value': value} for line, (field, value) in zip(LINES, values, strict=True)]
    assert validate_proposal(document(text), clauses) == compile_terms(document(text))
    wrong = [dict(row) for row in clauses]
    wrong[1]['value'] = 'Harborlight'
    with pytest.raises(ValueError, match='does not match its independently interpreted source span'):
        validate_proposal(document(text), wrong)


# ---------- evaluator: exact boundaries and decimal money ----------

# April 2026 has 30 days = 43,200 minutes. Thresholds in whole minutes of eligible downtime:
#   99.95%: 0.9995 * 43200 = 43178.4 -> down 21 (43179 available) is not below; down 22 (43178) is.
#   99.5%:  0.995  * 43200 = 42984 exactly -> down 216 is exactly 99.5% (not below); down 217 is below.
#   97.25%: 0.9725 * 43200 = 42012 exactly -> down 1188 is exactly 97.25% (not below); down 1189 is below.
# Fee USD 987.65: 7.5% = 74.07375, 15% = 148.1475, 30% = 296.295 (sub-cent estimates are kept exactly).
APRIL = [
    (21, Outcome.INELIGIBLE, None, None, None),
    (22, Outcome.ELIGIBLE, '74.07375', '7.5', 6),
    (216, Outcome.ELIGIBLE, '74.07375', '7.5', 6),
    (217, Outcome.ELIGIBLE, '148.1475', '15', 7),
    (1188, Outcome.ELIGIBLE, '148.1475', '15', 7),
    (1189, Outcome.ELIGIBLE, '296.295', '30', 8),
    (43200, Outcome.ELIGIBLE, '296.295', '30', 8),
]


@pytest.mark.parametrize('down,outcome,amount,percent,cited', APRIL)
def test_exact_threshold_boundaries_and_decimal_amounts(bound, down, outcome, amount, percent, cited):
    manifest, bound_overlay = bound
    result = evaluate(manifest, bound_overlay, facts('2026-04', down), TENANT)
    assert result['outcome'] == outcome.value
    assert result['amount'] == amount
    assert result['citations'] == list(range(1, 13))
    if amount is not None:
        assert result['rate_units'] == int(Decimal(percent) * 1_000_000)
        assert result['tier_citation'] == cited
        assert Decimal(amount) == Decimal(FEE_CENTS) / 100 * Decimal(percent) / 100


def test_only_the_most_severe_tier_applies_never_a_sum(bound):
    manifest, bound_overlay = bound
    result = evaluate(manifest, bound_overlay, facts('2026-04', 43200), TENANT)
    accumulated = Decimal('987.65') * (Decimal('7.5') + Decimal('15') + Decimal('30')) / 100  # 518.51625
    assert result['amount'] == '296.295'
    assert Decimal(result['amount']) != accumulated


def test_thirty_one_day_month_and_inclusive_source_end(bound):
    manifest, bound_overlay = bound
    # December 2026: 44,640 minutes; 0.9995 * 44640 = 44617.68, so down 22 (44618 available) is not below
    # 99.95% and down 23 (44617 available) is. The source's last day, 2026-12-31, is governed.
    january = '2027-01-15T00:00:00+00:00'
    assert evaluate(manifest, bound_overlay, facts('2026-12', 22, received=january), TENANT)['outcome'] == Outcome.INELIGIBLE.value
    december = evaluate(manifest, bound_overlay, facts('2026-12', 23, received=january), TENANT)
    assert (december['outcome'], december['amount']) == (Outcome.ELIGIBLE.value, '74.07375')
    later = evaluate(manifest, bound_overlay, facts('2027-01', 23, received='2027-02-10T00:00:00+00:00'), TENANT)
    assert later['outcome'] == Outcome.UNSUPPORTED.value


@pytest.mark.parametrize('received,outcome', [
    ('2026-04-30T23:59:59+00:00', Outcome.INELIGIBLE),   # before the month ends
    ('2026-05-01T00:00:00+00:00', Outcome.ELIGIBLE),     # window opens at month end
    ('2026-05-30T23:59:59+00:00', Outcome.ELIGIBLE),     # last timely second of 30 days
    ('2026-05-30T19:59:59-04:00', Outcome.ELIGIBLE),     # the same instant in another offset
    ('2026-05-31T00:00:00+00:00', Outcome.INELIGIBLE),   # exclusive cutoff
])
def test_filing_window_from_the_article_clause(bound, received, outcome):
    manifest, bound_overlay = bound
    result = evaluate(manifest, bound_overlay, facts('2026-04', 22, received=received), TENANT)
    assert result['outcome'] == outcome.value
    assert result['claim_cutoff_exclusive'] == '2026-05-31T00:00:00+00:00'
    assert result['filing_status'] == ('TIMELY' if outcome == Outcome.ELIGIBLE else 'OUTSIDE_WINDOW')


@pytest.mark.parametrize('fee,down,amount', [(1, 22, '0.00075'), (100, 1189, '0.30'), (250_000, 217, '375.00')])
def test_sub_cent_and_whole_cent_estimates(bound, fee, down, amount):
    manifest, bound_overlay = bound
    result = evaluate(manifest, bound_overlay, facts('2026-04', down, fee=fee), TENANT)
    assert (result['outcome'], result['amount']) == (Outcome.ELIGIBLE.value, amount)


def test_zero_fee_has_no_claimable_credit(bound):
    manifest, bound_overlay = bound
    result = evaluate(manifest, bound_overlay, facts('2026-04', 1189, fee=0), TENANT)
    assert (result['outcome'], result['amount'], result['issuance_status']) == (
        Outcome.INELIGIBLE.value, None, 'NO_POSITIVE_CREDIT')


def test_generated_threshold_checks_pass_for_inherited_tiers():
    rows = generated_checks(compiled(LINES))
    assert len(rows) == 6 and all(row['passed'] for row in rows)


def test_overlay_must_bind_the_exact_title_identity():
    manifest = compiled(LINES)
    assert bind_overlay(manifest, overlay())['agreement'] == TITLE
    for other in (TITLE.lower(), TITLE + ' 2026', 'Harborlight Beacon Compute Agreement'):
        with pytest.raises(ValueError):
            bind_overlay(manifest, overlay(agreement=other))
    with pytest.raises(ValueError):
        bind_overlay(manifest, overlay(plan='Premium'))


def test_requirement_card_cites_both_remedy_halves():
    manifest = compiled(LINES)
    card = requirement_card(manifest, bind_overlay(manifest, overlay()))
    elements = {e['element']: e for e in card['elements']}
    assert card['supported'] is True
    assert (elements['eligible_fee']['status'], elements['eligible_fee']['citations']) == ('PRESENT', [10, 11])
    assert (elements['deadline']['status'], elements['deadline']['citations']) == ('PRESENT', [12])


# ---------- class 1: bare title line ----------

def test_title_with_twelve_words_and_inner_connectors_is_the_agreement():
    title = 'Harborlight Beacon Compute and Data Hosting Terms of the Cloud Service Agreement'
    assert compiled(replaced(0, title))['agreement'] == title


@pytest.mark.parametrize('title', [
    'Harborlight Beacon Compute Service Agreement.',                                 # sentence punctuation
    'Harborlight, Beacon Compute Service Agreement',
    'Harborlight Beacon Compute: Service Agreement',
    'Harborlight 2026 Compute Service Agreement',                                     # a date
    'Harborlight March Compute Service Agreement',
    'Harborlight Compute Agreement 2026-01-01 Agreement',
    'Harborlight beacon compute service Agreement',                                   # not title-cased
    'Harborlight Beacon Compute and Data Hosting Terms of the Edge Cloud Service Agreement',  # 13 words
    'Harborlight Beacon Compute Service Terms',                                       # not ending in Agreement
    'Agreement',
    'Draft Harborlight Compute Service Agreement',                                    # qualified
    'Amendment to the Harborlight Service Agreement',
    'Harborlight Non Exclusive Service Agreement',
    'The harborlight Service Agreement',
])
def test_qualified_or_malformed_titles_refuse_at_the_first_clause(title):
    refuses(replaced(0, title), at_clause(1))


def test_title_is_read_only_as_the_first_clause():
    refuses(['Service Level Agreement'] + LINES, at_clause(2))


def test_title_and_a_labeled_agreement_are_duplicates():
    refuses(inserted(1, 'Agreement: HB-2026-001'), duplicate('agreement'))
    refuses(inserted(4, 'Contract ID: HB-2026-001'), duplicate('agreement'))


def test_original_heading_keeps_precedence_over_the_title_template():
    # Unchanged: a first line the original heading template reads is a heading, never an agreement identity.
    refuses(replaced(0, 'Service Level Agreement'), COVERAGE)
    labeled = compiled(replaced(0, 'Service Level Agreement')[:1] + ['Agreement: HB-2026-001'] + LINES[1:])
    assert labeled['agreement'] == 'HB-2026-001'
    assert labeled['citations'][0]['field'] == 'heading'


def test_title_must_be_a_bare_line_not_a_prefix_of_one():
    joined = TITLE + ' ' + LINES[1]
    text = source([joined] + LINES[2:])
    segments = [TITLE, LINES[1]] + LINES[2:]
    with pytest.raises(ValueError, match=at_clause(1)):
        compile_terms(document(text), segments=segments)
    # Control: the same proposed segments over the original source, where the title is its own line.
    assert compile_terms(document(source(LINES)), segments=list(LINES))['agreement'] == TITLE


# ---------- class 2: unlabeled party statement ----------

@pytest.mark.parametrize('verb,preposition', [('supplies', 'on'), ('offers', 'under'), ('delivers', 'on'), ('operates', 'under')])
def test_party_statement_verbs(verb, preposition):
    manifest = compiled(replaced(1, f'Harborlight Systems {verb} Beacon Compute {preposition} the Standard plan.'))
    assert manifest['vendor'] == 'Harborlight Systems'


@pytest.mark.parametrize('statement', [
    'Harborlight Systems provides Beacon Compute under the Standard plan, excluding beta regions.',
    'Harborlight Systems provides Beacon Compute Except Archive under the Standard plan.',
    'Harborlight Systems provides Beacon Compute and Beacon Storage under the Standard plan.',
    'Harborlight Systems provides Beacon Compute (EU) under the Standard plan.',
    'Harborlight Systems no longer provides Beacon Compute under the Standard plan.',
    'Harborlight Systems or its affiliates provides Beacon Compute under the Standard plan.',
    'The Harborlight Systems affiliate provides Beacon Compute under the Standard plan.',
    'Our partner Harborlight Systems provides Beacon Compute under the Standard plan.',
    'Provider provides Beacon Compute under the Standard plan.',
    'Harborlight Systems may provide Beacon Compute under the Standard plan.',
    'Harborlight Systems provides Beacon Compute, which operates under the Standard plan.',
    'Harborlight Systems provides Beacon Compute under the Standard plan only.',
    'Harborlight  Systems provides Beacon Compute under the Standard plan.',          # identity bytes would change
])
def test_qualified_or_ambiguous_party_statements_refuse_at_their_clause(statement):
    refuses(replaced(1, statement), at_clause(2))


def test_party_statement_and_labeled_vendor_are_duplicates_even_with_the_same_value():
    refuses(inserted(1, 'Vendor: Harborlight Systems'), duplicate('vendor'))
    refuses(inserted(2, LINES[1]), duplicate('vendor'))


def test_party_scope_must_be_the_only_declared_scope():
    refuses(replaced(1, 'Harborlight Systems provides Beacon Compute under the Premium plan.'), AMBIGUOUS)
    refuses(replaced(1, 'Harborlight Systems provides Beacon Storage under the Standard plan.'), AMBIGUOUS)


def test_labeled_vendor_with_a_unique_tier_scope_still_supports_inheritance():
    manifest = compiled(replaced(1, 'Vendor: Harborlight Systems'))
    assert manifest['vendor'] == 'Harborlight Systems'
    assert [(t['plan'], t.get('scope_citation')) for t in manifest['tiers']] == [
        ('Standard', 6), ('Standard', 6), ('Standard', None)]


# ---------- class 3: effective sentence ----------

@pytest.mark.parametrize('sentence', [
    'This agreement takes effect on 2026-01-01 and ends on 2026-12-31.',
    'This agreement is effective on 2026-01-01 through 2026-12-31.',
    'This agreement takes effect on 2026-01-01 until and including 2026-12-31.',
])
def test_effective_sentences(sentence):
    assert compiled(replaced(2, sentence))['effective'] == ['2026-01-01', '2026-12-31']


@pytest.mark.parametrize('sentence', [
    'This agreement takes effect on 01/01/2026 and ends on 12/31/2026.',
    'This agreement takes effect on 2026-01-01 until 2026-12-31.',
    'This agreement takes effect on 2026-01-01.',
    'This agreement takes effect on 2026-01-01 and ends on 2026-12-31 unless renewed.',
    'This agreement does not take effect on 2026-01-01 and ends on 2026-12-31.',
    'This agreement takes effect on 2026-1-1 and ends on 2026-12-31.',
])
def test_unsupported_effective_sentences_refuse_at_their_clause(sentence):
    refuses(replaced(2, sentence), at_clause(3))


def test_reversed_or_impossible_effective_dates_refuse():
    refuses(replaced(2, 'This agreement takes effect on 2026-12-31 and ends on 2026-01-01.'),
            '^' + re.escape('Reversed effective interval.') + '$')
    with pytest.raises(ValueError):
        compiled(replaced(2, 'This agreement takes effect on 2026-02-30 and ends on 2026-12-31.'))


def test_effective_sentence_and_labeled_dates_are_duplicates():
    refuses(inserted(3, 'Effective: 2026-01-01 through 2026-12-31'), duplicate('effective'))


# ---------- class 5: availability formula in words ----------

@pytest.mark.parametrize('formula', [
    'Monthly availability = 100 * (1 - eligible downtime minutes / total minutes in the month).',
    'Monthly uptime percentage equals 100 times (1 minus (the eligible downtime minutes divided by the total minutes '
    'in the calendar month)).',
    'Availability is computed as 100 multiplied by (1 − eligible downtime minutes ÷ total minutes in the UTC month).',
])
def test_formula_operator_variants(formula):
    assert compiled(replaced(4, formula))['availability_formula'] == 'one_minus_eligible_downtime_over_month_minutes'


@pytest.mark.parametrize('formula', [
    'Monthly availability is calculated as 100 × (1 − eligible downtime minutes ÷ total minutes in the billing period).',
    'Monthly availability is calculated as 100 × (1 − downtime minutes ÷ total minutes in the month).',
    'Monthly availability is calculated as 100 × (1 − eligible downtime minutes ÷ scheduled minutes in the month).',
    'Monthly availability is calculated as 99 × (1 − eligible downtime minutes ÷ total minutes in the month).',
    'Monthly availability is calculated as 100 × (eligible downtime minutes ÷ total minutes in the month).',
    'Monthly availability is calculated as 100 × (1 − (eligible downtime minutes ÷ total minutes in the month).',
    'Monthly availability is calculated as 100 × (1 − eligible downtime minutes ÷ total minutes in the month), '
    'excluding scheduled maintenance.',
    'Monthly availability is calculated as 100 × (1 − eligible downtime minutes ÷ total minutes in the month) + 0.1.',
])
def test_other_formulas_denominators_or_adjustments_refuse(formula):
    refuses(replaced(4, formula), at_clause(5))


def test_duplicate_formula_statements_refuse():
    refuses(inserted(5, LINES[4]), duplicate('availability_formula'))


# ---------- class 7: tier inheriting a unique scope ----------

def test_unscoped_tier_before_any_scoped_tier_refuses_at_its_clause():
    refuses(LINES[:5] + [LINES[6], LINES[5]] + LINES[7:], at_clause(6))


def test_inherited_tier_cites_the_nearest_preceding_scoped_tier():
    lines = inserted(7, 'For Beacon Compute on the Standard plan, monthly availability below 99% earns a 20% service credit.')
    tiers = {t['citation']: t for t in compiled(lines)['tiers']}
    assert tiers[7].get('scope_citation') == 6 and tiers[9].get('scope_citation') == 8
    assert 'scope_citation' not in tiers[6] and 'scope_citation' not in tiers[8]


def test_inheritance_with_two_declared_scopes_is_ambiguous_but_explicit_tiers_alone_are_not():
    premium = 'For Beacon Compute on the Premium plan, monthly availability below 99.9% earns a 10% service credit.'
    labeled = replaced(1, 'Vendor: Harborlight Systems')
    refuses(labeled[:6] + [premium] + labeled[6:], AMBIGUOUS)
    explicit = labeled[:6] + [premium] + labeled[8:]  # no unscoped tiers left to inherit
    assert {(t['plan'], t['credit_units']) for t in compiled(explicit)['tiers']} == {
        ('Standard', 7_500_000), ('Premium', 10_000_000)}


@pytest.mark.parametrize('extra', [
    'Monthly availability below 99.5% earns a 20% service credit.',   # contradicts clause 7
    'Monthly availability below 99.5% earns a 15% service credit.',   # repeats clause 7 exactly
    'Monthly availability below 99.95% earns a 7.5% service credit.',  # repeats the scoped tier
])
def test_contradictory_or_repeated_tiers_refuse(extra):
    refuses(inserted(8, extra), OVERLAP)


def test_nonmonotonic_inherited_tier_refuses():
    refuses(replaced(7, 'Monthly availability below 97.25% earns a 10% service credit.'), OVERLAP)


@pytest.mark.parametrize('tier', [
    'Monthly availability below 99.5% earns a 15% service credit if requested within 10 days.',
    'Monthly availability below 99.5% does not earn a 15% service credit.',
    'Monthly availability below 99.1234567% earns a 15% service credit.',  # beyond six decimal places
    'Monthly availability above 99.5% earns a 15% service credit.',
])
def test_conditional_negated_or_unsupported_tiers_refuse_at_their_clause(tier):
    refuses(replaced(6, tier), at_clause(7))


def test_zero_percent_inherited_credit_refuses():
    refuses(replaced(7, 'Monthly availability below 97.25% earns a 0% service credit.'),
            '^' + re.escape('Percentage outside the supported interval.') + '$')


# ---------- class 8: highest applicable percentage ----------

def test_highest_tier_statement_variant():
    statement = 'Only the highest applicable service credit percentage applies, and credit percentages do not accumulate.'
    assert compiled(replaced(8, statement))['tier_selection'] == 'highest_applicable_only'


@pytest.mark.parametrize('statement', [
    'Only the highest applicable percentage applies; percentages accumulate.',
    'Credit percentages accumulate across tiers.',
    'Only the highest applicable percentage applies; percentages do not accumulate unless stated otherwise.',
    'Only the lowest applicable percentage applies; percentages do not accumulate.',
])
def test_accumulating_or_qualified_tier_statements_refuse(statement):
    refuses(replaced(8, statement), at_clause(9))


def test_duplicate_highest_tier_statements_refuse():
    refuses(inserted(9, LINES[8]), duplicate('tier_selection'))


# ---------- classes 9 + 10: fee basis and future invoice ----------

def test_either_remedy_half_alone_is_incomplete():
    refuses(removed(10), COVERAGE)
    refuses(removed(9), COVERAGE)


def test_remedy_halves_and_the_original_remedy_clause_are_duplicates():
    original = 'Service credits apply to the affected monthly fee and are applied to a future invoice.'
    refuses(replaced(10, original), duplicate('remedy'))
    refuses(inserted(11, original), duplicate('remedy'))
    refuses(inserted(10, LINES[9]), duplicate('remedy'))
    refuses(inserted(11, LINES[10]), duplicate('remedy'))


def test_remedy_half_variants():
    lines = replaced(9, 'The service credit percentage applies to the affected monthly fee in USD.')
    lines[10] = 'Service credits will be credited to the next invoice.'
    assert compiled(lines)['remedy'] == 'affected_monthly_fees_future_invoice'


@pytest.mark.parametrize('index,clause', [
    (9, 'The credit percentage applies to the affected monthly service fee in EUR.'),
    (9, 'The credit percentage applies to the affected monthly service fee in US dollars.'),
    (9, 'The credit percentage applies to the total monthly service fee in USD.'),
    (9, 'The credit percentage applies to the affected annual service fee in USD.'),
    (9, 'The credit percentage applies to the affected monthly service fee in USD, excluding taxes.'),
    (10, 'Credits are applied to a future invoice and are not refundable as cash.'),
    (10, 'Credits are applied to a future invoice within 12 months.'),
    (10, 'Credits are not applied to a future invoice.'),
    (10, 'Credits may be applied to a future invoice.'),
])
def test_other_currencies_bases_or_qualified_remedies_refuse_at_their_clause(index, clause):
    refuses(replaced(index, clause), at_clause(index + 1))


# ---------- class 11: filing sentence with an article ----------

def test_filing_article_variants():
    assert compiled(replaced(11, 'A credit request must be submitted within 45 calendar days following the end of '
                                 'the affected month.'))['filing_days'] == 45
    assert compiled(replaced(11, 'A complete claim must be filed within 365 calendar days after the end of each '
                                 'calendar month.'))['filing_days'] == 365


@pytest.mark.parametrize('days', ['0', '366', '999'])
def test_filing_window_outside_one_to_365_days_refuses(days):
    refuses(replaced(11, f'A claim must be received within {days} calendar days after month end.'),
            '^' + re.escape('Filing window outside supported interval.') + '$')


@pytest.mark.parametrize('clause', [
    'A claim must be received within 30 business days after month end.',
    'The claim must be received within 30 calendar days after month end.',
    'A claim must be received within 30 calendar days after month end unless extended.',
])
def test_unsupported_filing_sentences_refuse_at_their_clause(clause):
    refuses(replaced(11, clause), at_clause(12))


def test_article_filing_and_original_filing_are_duplicates():
    refuses(LINES + ['Claims must be received within 30 calendar days after month end.'], duplicate('filing_days'))


def test_private_filing_amendment_grammar_is_not_widened():
    manifest = compiled(LINES)

    def amended(quote):
        return overlay(override=FilingOverride(filing_days=60, source_ref='Order form 7', quote=quote,
                                               effective_from='2026-05-01'))
    assert bind_overlay(manifest, amended('Claims must be received within 60 calendar days after month end.'))
    with pytest.raises(ValueError, match='Private filing amendment must cite the matching contract clause'):
        bind_overlay(manifest, amended('A claim must be received within 60 calendar days after month end.'))


# ---------- completed-step rules keep their own semantics ----------

STEP_LINES = [
    'Agreement: HB-STEP-2026',
    'Harborlight Systems provides Beacon Compute under the Standard plan.',
    'Effective: 2026-01-01 through 2026-12-31',
    'Monthly availability is measured over each UTC calendar month.',
    'For Beacon Compute on the Standard plan, the monthly uptime target is 99.9%; each completed 0.1 percentage point '
    'of shortfall below the target earns a 1% service credit, capped at 10%.',
    'Round the resulting service credit once to the nearest cent, with half cents rounded up; do not round '
    'availability or shortfall before counting completed increments.',
    'Service credits apply to the affected monthly fee and are applied to a future invoice.',
    'Claims must be received within 30 calendar days after month end.',
]


def test_party_statement_scoping_a_completed_step_rule():
    manifest = compiled(STEP_LINES)
    assert 'tiers' not in manifest
    assert manifest['vendor'] == 'Harborlight Systems'
    assert manifest['credit_rule'] == {'kind': 'completed_steps', 'product': 'Beacon Compute', 'plan': 'Standard',
                                       'citation': 5, 'target_units': 99_900_000, 'step_units': 100_000,
                                       'credit_units': 1_000_000, 'cap_units': 10_000_000}


def test_completed_steps_refuse_a_highest_tier_statement_or_another_party_scope():
    refuses(STEP_LINES + [LINES[8]], '^' + re.escape(
        'A highest-applicable tier statement cannot govern a completed-step rule.') + '$')
    other = list(STEP_LINES)
    other[1] = 'Harborlight Systems provides Beacon Compute under the Premium plan.'
    refuses(other, AMBIGUOUS)


# ---------- original outcomes are preserved ----------

LEGACY = [
    'Monthly Availability Agreement',
    'Vendor: Lanternfish Data Co',
    'Agreement: LF-SLA-7',
    'Effective: 2026-02-01 through 2027-01-31',
    'Monthly availability is measured over each UTC calendar month.',
    'For Tidepool Storage on the Basic plan, monthly availability below 99.9% earns a 10% service credit.',
    'For Tidepool Storage on the Basic plan, monthly availability below 99% earns a 25% service credit.',
    'Service credits apply to the affected monthly fee and are applied to a future invoice.',
    'Claims must be received within 30 calendar days after month end.',
]


def test_original_template_contract_compiles_to_exactly_the_same_manifest():
    text = source(LEGACY)
    citations, offset = [], 0
    fields = ['heading', 'vendor', 'agreement', 'effective', 'period', 'tier', 'tier', 'remedy', 'filing_days']
    for number, (line, field) in enumerate(zip(LEGACY, fields, strict=True), 1):
        citations.append({'id': number, 'start': offset, 'end': offset + len(line), 'quote': line, 'field': field})
        offset += len(line) + 1
    expected = {
        'family': 'monthly-availability/1',
        'document': {'name': 'Fictional remediation contract', 'uri': 'urn:uptime:fictional:harborlight-beacon',
                     'classification': 'synthetic_public', 'sha256': sha256(text.encode()).hexdigest()},
        'tiers': [{'product': 'Tidepool Storage', 'plan': 'Basic', 'below_units': 99_000_000, 'credit_units': 25_000_000,
                   'citation': 7},
                  {'product': 'Tidepool Storage', 'plan': 'Basic', 'below_units': 99_900_000, 'credit_units': 10_000_000,
                   'citation': 6}],
        'citations': citations, 'vendor': 'Lanternfish Data Co', 'agreement': 'LF-SLA-7',
        'effective': ['2026-02-01', '2027-01-31'], 'period': 'utc_calendar_month', 'filing_days': 30,
        'remedy': 'affected_monthly_fees_future_invoice'}
    assert compile_terms(document(text)) == expected


def test_original_refusals_stay_refusals():
    with pytest.raises(ValueError, match=at_clause(10)):
        compiled(LEGACY + ['Credits are void if the account is past due.'])
    with pytest.raises(ValueError, match=duplicate('vendor')):
        compiled(LEGACY[:2] + ['Vendor: Lanternfish Data Co'] + LEGACY[2:])
