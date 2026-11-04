"""V4 financial audit regression and independent oracles.

Review decisions: consistently excluded products do not need a performance
version; unknown mixed lines retain verified findings but no aggregate money.
Disconnected Twilio history is irrelevant, while touching chains remain proof
obligations. Canonical IDs/references are rejected, never silently normalized.
The existing pricing partial-claim test is updated for retained line evidence;
its missing outcome and absent claim amount are unchanged. No fixtures changed.
"""
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D, localcontext, ROUND_DOWN, ROUND_UP
from itertools import groupby
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings, strategies as st

from uptime import other_obligations as ob, pricing as p, twilio as t
from uptime.contracts import Outcome, Source
from uptime.pricing_demo import load_agreement, load_demo_inputs
from uptime.twilio_demo import demo_inputs

LA = ZoneInfo("America/Los_Angeles")
A = load_agreement()
N = load_demo_inputs()[0][1]
T = demo_inputs()[0][1]
ORIGIN = datetime(2026, 11, 1, 8, tzinfo=UTC)


def invoice(*lines):
    return replace(N, lines=lines, total=sum((line.net + line.tax for line in lines), D(0)))


def fold(minute, n):
    return datetime(2026, 11, 1, 1, minute, tzinfo=LA, fold=n)


def provider(mapping, lines=()):
    return p.ProviderBill(mapping.id, mapping.total, mapping.currency, mapping.payment_status,
                          mapping.provider_vendor_id, Source.RAMP, True, "test-read", N.issued_at,
                          "https://demo-api.ramp.com", lines)


@given(boundary=st.integers(1, 119), begin=st.integers(0, 118), duration=st.integers(1, 15),
       zone=st.sampled_from(["America/Los_Angeles", "UTC", "Asia/Kolkata"]))
def test_price_fold_selection_matches_integer_instant_oracle(boundary, begin, duration, zone):
    tz = ZoneInfo(zone)
    amendment = replace(A.versions[1], effective_at=(ORIGIN + timedelta(minutes=boundary)).astimezone(tz))
    agreement = replace(A, versions=(A.versions[0], amendment))
    line = replace(N.lines[0], quantity=D(1), net=D(20),
                   start=(ORIGIN + timedelta(minutes=begin)).astimezone(tz),
                   end=(ORIGIN + timedelta(minutes=begin + duration)).astimezone(tz))
    result = p.evaluate_price(agreement, invoice(line))
    if begin < boundary < begin + duration:
        assert result.evaluation.outcome == Outcome.MISSING
        assert result.overcharge is None
    else:
        expected = D(20) if begin < boundary else D(15)
        assert result.lines[0].expected == expected
        assert result.overcharge == 20 - expected


@pytest.mark.parametrize("signed,effective,outcome", [
    (fold(45, 0), fold(15, 1), Outcome.ELIGIBLE),
    (fold(15, 1), fold(45, 0), Outcome.UNSUPPORTED),
])
def test_signature_order_uses_actual_instants(signed, effective, outcome):
    agreement = replace(A, versions=(A.versions[0], replace(A.versions[1],
                        effective_at=effective, signed_at=signed)))
    line = replace(N.lines[0], start=fold(50, 1), end=fold(55, 1))
    result = p.evaluate_price(agreement, invoice(line))
    assert result.evaluation.outcome == outcome
    if outcome == Outcome.ELIGIBLE:
        assert result.overcharge == D("7500.00")
    else:
        assert result.evaluation.amount is None


@given(minute=st.integers(0, 59), fold_no=st.integers(0, 1), field=st.sampled_from(["start", "end"]))
def test_provider_binding_accepts_same_instant_rejects_opposite_fold(minute, fold_no, field):
    line = replace(N.lines[0], **{field: fold(minute, fold_no)})
    mapping = replace(invoice(line), provider_vendor_id="test-vendor")
    good = p.ProviderLine(line.id, **{field: fold(minute, fold_no).astimezone(UTC)})
    assert p.bind_sandbox_bill(provider(mapping, (good,)), mapping)
    bad = replace(good, **{field: fold(minute, 1 - fold_no)})
    with pytest.raises(p.PricingInputError):
        p.bind_sandbox_bill(provider(mapping, (bad,)), mapping)


def test_expiration_issue_and_overlap_use_utc_instants():
    line = replace(N.lines[0], start=fold(45, 0), end=fold(15, 1))
    valid = replace(A, expires_at=fold(20, 1))
    assert p.evaluate_price(valid, invoice(line)).overcharge == D("7500.00")
    assert p.evaluate_price(replace(valid, expires_at=fold(30, 0)), invoice(line)).evaluation.outcome == Outcome.INELIGIBLE
    assert p.evaluate_price(valid, replace(invoice(line), issued_at=fold(30, 0))).evaluation.outcome == Outcome.UNSUPPORTED
    first = replace(line, end=fold(55, 0))
    second = replace(line, id="second", allocation_ref="second-allocation", start=fold(10, 1), end=fold(20, 1))
    assert p.evaluate_price(A, invoice(first, second)).overcharge == D("15000.00")
    overlapping = replace(second, start=fold(50, 0))
    assert p.evaluate_price(A, invoice(first, overlapping)).evaluation.outcome == Outcome.MISSING


@given(days=st.integers(1, 1000), reverse=st.booleans())
def test_consistently_noncovered_out_of_term_line_cannot_mask_overcharge(days, reverse):
    end = A.versions[0].effective_at - timedelta(days=days)
    support = replace(N.lines[1], start=end - timedelta(days=1), end=end)
    lines = (support, N.lines[0]) if reverse else (N.lines[0], support)
    result = p.evaluate_price(A, invoice(*lines))
    assert result.overcharge == D("7500.00")
    assert result.evaluation.outcome == Outcome.ELIGIBLE


@pytest.mark.parametrize("product", [None, "unknown-storage"])
@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_unknown_lines_preserve_only_verified_detail_without_claim(product, reverse):
    unknown = replace(N.lines[1], product=product)
    lines = (unknown, N.lines[0]) if reverse else (N.lines[0], unknown)
    result = p.evaluate_price(A, invoice(*lines))
    assert result.evaluation.outcome == Outcome.MISSING
    assert result.overcharge is result.undercharge is result.evaluation.amount is None
    assert len(result.lines) == 1 and result.lines[0].delta == D("7500.00")


def test_exclusion_must_hold_across_all_versions_for_undated_bypass():
    old = replace(A.versions[0], excluded_products=())
    support = replace(N.lines[1], start=None, end=None)
    result = p.evaluate_price(replace(A, versions=(old, A.versions[1])), invoice(N.lines[0], support))
    assert result.evaluation.outcome == Outcome.MISSING and result.overcharge is None


BAD_IDS = ["", " ", "usage ", " usage", "usage\n", 123, None]


@pytest.mark.parametrize("bad", BAD_IDS)
def test_canonical_invoice_provider_and_rebate_ids(bad):
    assert p.evaluate_price(A, replace(N, id=bad)).evaluation.outcome == Outcome.MISSING
    assert p.evaluate_price(A, invoice(replace(N.lines[0], id=bad))).evaluation.outcome == Outcome.MISSING
    mapping = replace(N, id=bad, provider_vendor_id="test-vendor")
    with pytest.raises(p.PricingInputError):
        p.bind_sandbox_bill(provider(mapping), mapping)
    mapping = replace(N, provider_vendor_id=bad)
    with pytest.raises(p.PricingInputError):
        p.bind_sandbox_bill(provider(mapping), mapping)
    assert ob.evaluate_rebate(ledger([paid(bad, "100000.00")])).outcome == Outcome.MISSING
    assert t.evaluate(replace(T, fees=(replace(T.fees[0], id=bad),))).outcome == Outcome.MISSING


def paid(identifier, amount):
    return dict(id=identifier, date="2026-09-30", product="Core", kind="paid", amount=amount, currency="USD")


def ledger(charges, credits=None):
    return dict(complete=True, through="2026-09-30", charges=charges, credits=credits or [])


def test_rebate_and_twilio_padded_aliases_never_create_value():
    charge = paid("source-1", "50000.00")
    assert ob.evaluate_rebate(ledger([charge, charge.copy()])).outcome == Outcome.INELIGIBLE
    assert ob.evaluate_rebate(ledger([charge, charge | {"id": "source-1 "}])).outcome == Outcome.MISSING
    fee = replace(T.fees[0], id=T.fees[0].id + " ")
    assert t.evaluate(replace(T, fees=T.fees + (fee,))).outcome == Outcome.MISSING


@pytest.mark.parametrize("bad", ["", "  ", "\n", None, 42])
def test_meaningful_document_references(bad):
    incident = replace(T.intervals[0], documentation_refs=(bad,))
    assert t.evaluate(replace(T, intervals=(incident,))).outcome == Outcome.MISSING
    assert t.evaluate(replace(T, agreement_ref=bad)).outcome == Outcome.MISSING
    assert t.evaluate(replace(T, fees=(replace(T.fees[0], mapping_ref=bad),))).outcome == Outcome.MISSING
    assert p.evaluate_price(A, invoice(replace(N.lines[0], allocation_ref=bad))).evaluation.outcome == Outcome.MISSING
    citation = replace(A.versions[1].citation, uri=bad)
    assert p.evaluate_price(replace(A, versions=(A.versions[0], replace(A.versions[1], citation=citation))), N).evaluation.outcome == Outcome.MISSING


@given(days=st.integers(2, 1000), future=st.booleans())
def test_disconnected_unknown_history_does_not_withhold_month(days, future):
    boundary = datetime(2026, 11 if future else 10, 1, tzinfo=UTC)
    start = boundary + timedelta(days=days if future else -days)
    unrelated = replace(T.intervals[0], start=start, end=start + timedelta(minutes=10),
                        documentation_refs=(), customer_affected=None, exclusion=t.Exclusion.UNKNOWN)
    result = t.evaluate(replace(T, intervals=(*T.intervals, unrelated)))
    assert result.outcome == Outcome.ELIGIBLE and result.amount.amount == D("100.0000")


def test_connected_history_requires_proof_and_preserves_five_minute_chain():
    origin = datetime(2026, 10, 1, tzinfo=UTC)
    first = replace(T.intervals[0], start=origin - timedelta(minutes=4), end=origin)
    tail = replace(first, start=origin, end=origin + timedelta(minutes=5))
    other = replace(first, start=origin - timedelta(minutes=5), end=first.start, customer_affected=None)
    valid = replace(T, plan=t.Plan.ENTERPRISE, intervals=(first, tail))
    assert t.evaluate(valid).outcome == Outcome.ELIGIBLE
    assert t.evaluate(replace(valid, intervals=(other, tail, first))).outcome == Outcome.MISSING
    gap = replace(other, end=other.end - timedelta(microseconds=1))
    assert t.evaluate(replace(valid, intervals=(gap, tail, first))).outcome == Outcome.ELIGIBLE


@settings(max_examples=150)
@given(spans=st.lists(st.tuples(st.integers(-12, 30), st.integers(1, 15), st.booleans()), max_size=10))
def test_twilio_interval_union_matches_independent_minute_mask(spans):
    origin = datetime(2026, 10, 1, tzinfo=UTC)
    included, excluded, incidents = set(), set(), []
    for begin, length, exclusion in spans:
        (excluded if exclusion else included).update(range(begin, begin + length))
        incidents.append(replace(T.intervals[0], start=origin + timedelta(minutes=begin),
                                 end=origin + timedelta(minutes=begin + length),
                                 exclusion=t.Exclusion.EMERGENCY_MAINTENANCE if exclusion else t.Exclusion.NONE))
    runs = [list(group) for _, group in groupby(enumerate(sorted(included - excluded)), lambda x: x[1] - x[0])]
    minutes = sum(sum(minute >= 0 for _, minute in run) for run in runs if len(run) >= 5)
    expected = Outcome.ELIGIBLE if minutes * 10000 > 44640 else Outcome.INELIGIBLE
    assert t.evaluate(replace(T, plan=t.Plan.ENTERPRISE, intervals=tuple(incidents))).outcome == expected


@pytest.mark.parametrize("precision", [3, 4, 8, 28])
@pytest.mark.parametrize("rounding", [ROUND_DOWN, ROUND_UP])
def test_exact_fractional_fees_do_not_depend_on_ambient_context(precision, rounding):
    tiny = replace(T.fees[0], amount=D("0.01"))
    with localcontext() as context:
        context.prec, context.rounding = precision, rounding
        assert t.evaluate(replace(T, fees=(tiny,))).amount.amount == D("0.0010")
        assert p.evaluate_price(A, N).overcharge == D("7500.00")
        assert ob.evaluate_rebate(ledger([paid("a", "100000.25")])).amount.amount == D("2000.01")


def test_twilio_preserves_more_than_fifty_decimal_digits():
    fee = D("123456789012345678901234567890123456789012345678901234567890.01")
    expected = D("12345678901234567890123456789012345678901234567890123456789.0010")
    assert t.evaluate(replace(T, fees=(replace(T.fees[0], amount=fee),))).amount.amount == expected


@given(cents=st.integers(0, 20000000), returned=st.integers(0, 1000000), credit=st.integers(0, 100000))
def test_rebate_matches_integer_cent_oracle(cents, returned, credit):
    def money(n):
        return f"{n // 100}.{n % 100:02}"
    data = ledger([paid("charge", money(cents)), paid("return", money(returned)) | {"kind": "return"}],
                  [dict(id="memo", clause="R-1", year_end="2026-09-30", amount=money(credit), currency="USD")])
    net = cents - returned
    outstanding = max(0, (net * 2 + 50) // 100 - credit) if net >= 10000000 else 0
    with localcontext() as context:
        context.prec = 4
        result = ob.evaluate_rebate(data)
    assert result.outcome == (Outcome.ELIGIBLE if outstanding else Outcome.INELIGIBLE)
    assert result.amount is None if not outstanding else result.amount.amount == D(money(outstanding))


def test_same_currency_service_scope_positive_and_negative_controls():
    assert t.evaluate(T).amount.amount == D("100.0000")
    foreign = replace(T.fees[0], id="foreign", api_id="other-api", currency="EUR")
    assert t.evaluate(replace(T, fees=(*T.fees, foreign))).amount.amount == D("100.0000")
    assert t.evaluate(replace(T, fees=(replace(foreign, api_id=T.service.api_id),))).outcome == Outcome.UNSUPPORTED
    unknown = replace(T.fees[0], id="unknown", kind=t.FeeKind.UNKNOWN)
    assert t.evaluate(replace(T, fees=(*T.fees, unknown))).outcome == Outcome.MISSING
    assert ob.evaluate_rebate(ledger([paid("a", "100000.00")])).amount.amount == D("2000.00")
    assert ob.evaluate_rebate(ledger([paid("a", "100000.00") | {"currency": "EUR"}])).outcome == Outcome.UNSUPPORTED
    assert p.evaluate_price(A, replace(N, currency="EUR")).evaluation.outcome == Outcome.UNSUPPORTED


def test_out_of_term_covered_line_does_not_deny_verified_discrepancy():
    end = A.versions[0].effective_at
    outside = replace(N.lines[0], id="outside", start=end - timedelta(days=1), end=end,
                      allocation_ref="outside-allocation")
    result = p.evaluate_price(A, invoice(outside, N.lines[0]))
    assert result.evaluation.outcome == Outcome.MISSING and result.evaluation.amount is None
    assert result.overcharge is None and result.lines[0].delta == D("7500.00")


def test_noncovered_provenance_does_not_invent_an_effective_version():
    historical = load_demo_inputs()[2][1]
    support = p.evaluate_price(A, historical).lines[1]
    assert support.version == A.versions[0].id
    outside = replace(N.lines[1], start=None, end=None)
    support = p.evaluate_price(A, invoice(outside)).lines[0]
    assert support.version == "all versions: agreement-v1, amendment-v2"


@pytest.mark.parametrize("field", ["start", "end"])
def test_provider_timestamp_requires_aware_mapping(field):
    mapped_line = replace(N.lines[0], **{field: None})
    mapping = replace(invoice(mapped_line), provider_vendor_id="test-vendor")
    read_line = p.ProviderLine(mapped_line.id, **{field: getattr(N.lines[0], field)})
    with pytest.raises(p.PricingInputError):
        p.bind_sandbox_bill(provider(mapping, (read_line,)), mapping)


def test_rebate_large_coefficients_and_scientific_notation_stay_exact():
    result = ob.evaluate_rebate(ledger([paid("large", "1E+80"), paid("cent", "0.25")]))
    assert result.amount.amount == D("2" + "0" * 78 + ".01")
