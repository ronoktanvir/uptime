from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json

import pytest

from uptime.contracts import Outcome, Source
from uptime.pricing import Tier, demo_cases, evaluate_price
from uptime.pricing_demo import load_agreement, load_demo_inputs


D = Decimal


@pytest.fixture
def agreement():
    return load_agreement()


@pytest.fixture
def invoice():
    return load_demo_inputs()[0][1]


def with_line(invoice, **changes):
    lines = (replace(invoice.lines[0], **changes), *invoice.lines[1:])
    total = sum((line.net + (line.tax or D("0")) for line in lines), D("0"))
    return replace(invoice, lines=lines, total=total)


def with_version(agreement, **changes):
    return replace(agreement, versions=(*agreement.versions[:-1], replace(agreement.versions[-1], **changes)))


def with_rate(agreement, **changes):
    return with_version(agreement, rates=(replace(agreement.versions[-1].rates[0], **changes),))


def assert_closed(result, outcome):
    assert result.evaluation.outcome == outcome
    assert result.evaluation.amount is None
    assert result.overcharge is None and result.undercharge is None
    assert not result.lines
    assert result.evaluation.trace[-1].startswith("FAIL CLOSED:")
    if outcome == Outcome.MISSING:
        assert result.evaluation.missing


def test_fixture_oracles_and_payment_immutability(agreement):
    for case, invoice in load_demo_inputs():
        before = repr(invoice), repr(agreement)
        result = evaluate_price(agreement, invoice)
        assert result.evaluation.outcome.value == case["expected_outcome"]
        assert (str(result.overcharge) if result.overcharge is not None else None) == case["expected_overcharge"]
        assert (repr(invoice), repr(agreement)) == before
        assert result.sources == (Source.CUSTOMER, Source.REPLAY)


def test_preapproval_and_retrospective_are_candidates_only(agreement, invoice):
    pre = evaluate_price(agreement, invoice)
    paid = evaluate_price(agreement, replace(invoice, payment_status="paid"))
    assert pre.stage == "PREPAYMENT_REVIEW"
    assert paid.stage == "RETROSPECTIVE_REVIEW"
    assert pre.evaluation.amount.amount == paid.evaluation.amount.amount == D("7500.00")
    assert pre.lines[0].expected == D("20000.00")
    assert pre.lines[1].direction == "NON_COVERED" and pre.lines[1].delta is None
    trace = "\n".join(pre.evaluation.trace)
    for text in ("1000.00 × 15.00", "500 × 10.00", "amendment-v2", "usage-ledger", "tax", "non-covered", "signed"):
        assert text in trace


@pytest.mark.parametrize(("quantity", "expected"), [("1", "15.00"), ("999", "14985.00"), ("1000", "15000.00"), ("1001", "15010.00"), ("1500", "20000.00")])
def test_inclusive_graduated_thresholds(agreement, invoice, quantity, expected):
    result = evaluate_price(agreement, with_line(invoice, quantity=D(quantity), net=D(expected)))
    assert result.evaluation.outcome == Outcome.INELIGIBLE
    assert result.lines[0].expected == D(expected)
    assert result.lines[0].direction == "MATCH"


def test_performance_timestamp_and_timezone_control_amendment(agreement, invoice):
    boundary = agreement.versions[1].effective_at
    before = with_line(invoice, start=boundary - timedelta(seconds=1), end=boundary)
    after = with_line(invoice, start=boundary.astimezone(timezone(timedelta(hours=-7))), end=boundary + timedelta(seconds=1))
    assert evaluate_price(agreement, before).lines[0].expected == D("27500.00")
    assert evaluate_price(agreement, after).lines[0].expected == D("20000.00")
    # Later invoice date cannot rewrite historical performance.
    assert evaluate_price(agreement, replace(before, issued_at=datetime(2027, 1, 2, tzinfo=timezone.utc))).overcharge == 0


def test_cross_amendment_needs_allocation_and_explicit_splits_work(agreement, invoice):
    boundary = agreement.versions[1].effective_at
    spanning = with_line(invoice, start=boundary - timedelta(days=1), end=boundary + timedelta(days=1))
    assert_closed(evaluate_price(agreement, spanning), Outcome.MISSING)
    first = replace(invoice.lines[0], id="before", start=boundary - timedelta(days=1), end=boundary,
                    quantity=D("1000"), net=D("20000"), allocation_ref="ledger-before")
    second = replace(invoice.lines[0], id="after", start=boundary, end=boundary + timedelta(days=1),
                     quantity=D("500"), net=D("7500"), allocation_ref="ledger-after")
    split = replace(invoice, lines=(first, second), total=D("27500"))
    result = evaluate_price(agreement, split)
    assert result.overcharge == 0
    assert [f.version for f in result.lines] == ["agreement-v1", "amendment-v2"]
    assert [f.expected for f in result.lines] == [D("20000.00"), D("7500.00")]


def test_undercharge_and_overcharge_reported_without_netting(agreement, invoice):
    boundary = agreement.versions[1].effective_at
    under = replace(invoice.lines[0], id="under", start=boundary - timedelta(days=1), end=boundary,
                    net=D("26500"), allocation_ref="ledger-under")
    result = evaluate_price(agreement, replace(invoice, lines=(under, invoice.lines[0]), total=D("54000")))
    assert result.overcharge == D("7500") and result.undercharge == D("1000")
    assert result.evaluation.amount.amount == D("7500")
    assert [line.direction for line in result.lines] == ["UNDERCHARGE", "OVERCHARGE"]


def test_undercharge_alone_carries_no_claimable_money(agreement, invoice):
    result = evaluate_price(agreement, with_line(invoice, net=D("19000")))
    assert result.evaluation.outcome == Outcome.INELIGIBLE
    assert result.overcharge == 0 and result.undercharge == D("1000")
    assert result.lines[0].delta == D("-1000")
    assert result.evaluation.amount is None


def test_round_each_line_not_invoice_total(agreement, invoice):
    agreement = with_rate(agreement, tiers=(Tier(None, D("0.335")),))
    first = replace(invoice.lines[0], end=invoice.lines[0].start + timedelta(days=1), quantity=D("1"), net=D("0.34"))
    second = replace(first, id="second", start=first.end, end=first.end + timedelta(days=1), allocation_ref="second-ledger")
    result = evaluate_price(agreement, replace(invoice, lines=(first, second), total=D("0.68")))
    assert result.overcharge == result.undercharge == 0
    assert sum(line.expected for line in result.lines) == D("0.68")


def test_global_decimal_context_does_not_change_evaluation(agreement, invoice):
    with localcontext() as ctx:
        ctx.prec = 3
        result = evaluate_price(agreement, invoice)
    assert result.overcharge == D("7500.00")


@pytest.mark.parametrize("change", [
    {"product": None}, {"product": "unidentified-storage"}, {"quantity": None},
    {"quantity": D("0")}, {"quantity": D("-1")}, {"quantity": D("1.5")},
    {"quantity": 1500.0}, {"quantity": D("NaN")}, {"quantity": D("Infinity")},
    {"unit": None}, {"unit": "seat"}, {"start": None}, {"end": None},
    {"start": datetime(2026, 10, 1)}, {"tax": None}, {"allocation_ref": None},
    {"allocation_complete": False},
])
def test_missing_line_proof_fails_closed(agreement, invoice, change):
    assert_closed(evaluate_price(agreement, with_line(invoice, **change)), Outcome.MISSING)


@pytest.mark.parametrize("change", [{"lines": ()}, {"total": D("30001")}, {"total": D("NaN")}, {"total": 30000.0}])
def test_unitemized_or_unreconciled_invoice_fails_closed(agreement, invoice, change):
    assert_closed(evaluate_price(agreement, replace(invoice, **change)), Outcome.MISSING)


@pytest.mark.parametrize("change", [{"currency": "EUR"}, {"payment_status": "unknown"}])
def test_unsupported_invoice(agreement, invoice, change):
    assert_closed(evaluate_price(agreement, replace(invoice, **change)), Outcome.UNSUPPORTED)


def test_no_partial_claim_when_one_line_unidentified(agreement, invoice):
    invoice = replace(invoice, lines=(invoice.lines[0], replace(invoice.lines[1], product=None)))
    # V4 audit B04: retain verified line evidence without asserting that an
    # incomplete invoice has a known aggregate claim. Historical fixtures stay.
    result = evaluate_price(agreement, invoice)
    assert result.evaluation.outcome == Outcome.MISSING
    assert result.evaluation.amount is None
    assert result.overcharge is result.undercharge is None
    assert len(result.lines) == 1 and result.lines[0].delta == D("7500.00")


def test_explicitly_noncovered_only_is_ineligible(agreement, invoice):
    result = evaluate_price(agreement, replace(invoice, lines=(invoice.lines[1],), total=D("2500")))
    assert result.evaluation.outcome == Outcome.INELIGIBLE
    assert result.overcharge == 0 and result.lines[0].direction == "NON_COVERED"


@pytest.mark.parametrize("change", [{"customer": "other-tenant"}, {"vendor": "other-vendor"}])
def test_party_mismatch_rejected(agreement, invoice, change):
    assert_closed(evaluate_price(agreement, replace(invoice, **change)), Outcome.INELIGIBLE)


def test_outside_contract_dates(agreement, invoice):
    invoice = with_line(invoice, start=agreement.versions[0].effective_at - timedelta(days=1), end=agreement.versions[0].effective_at)
    assert_closed(evaluate_price(agreement, invoice), Outcome.INELIGIBLE)


def test_future_performance_is_not_silently_authorized(agreement, invoice):
    assert_closed(evaluate_price(agreement, replace(invoice, issued_at=invoice.lines[0].start)), Outcome.UNSUPPORTED)


@pytest.mark.parametrize("change", [
    {"signed_at": None}, {"signed_at": datetime(2026, 9, 20)},
    {"signatories": ("synthetic-bears",)}, {"supersedes": "missing-version"},
    {"effective_at": datetime(2026, 1, 1, tzinfo=timezone.utc), "signed_at": datetime(2025, 12, 21, tzinfo=timezone.utc)},
])
def test_missing_signatures_and_ambiguous_chain(agreement, invoice, change):
    assert_closed(evaluate_price(with_version(agreement, **change), invoice), Outcome.MISSING)


@pytest.mark.parametrize("change", [
    {"signed_at": datetime(2026, 10, 2, tzinfo=timezone.utc)},
    {"currency": "EUR"}, {"tax_treatment": "tax_included"}, {"rounding": "invoice_total"},
])
def test_unsupported_contract_interpretations(agreement, invoice, change):
    assert_closed(evaluate_price(with_version(agreement, **change), invoice), Outcome.UNSUPPORTED)


@pytest.mark.parametrize("change", [
    {"mode": "volume"}, {"quantity_scope": "monthly_cumulative"}, {"boundary": "unknown"},
    {"tiers": (Tier(D("1000"), D("15")),)},
    {"tiers": (Tier(D("1000"), D("15")), Tier(D("1000"), D("10")), Tier(None, D("5")))},
    {"tiers": (Tier(None, D("15")), Tier(None, D("10")))},
])
def test_ambiguous_tier_semantics_fail_closed(agreement, invoice, change):
    assert_closed(evaluate_price(with_rate(agreement, **change), invoice), Outcome.UNSUPPORTED)


@pytest.mark.parametrize("rate", [D("NaN"), D("Infinity"), D("-1"), 0.1])
def test_invalid_rates_cannot_make_money(agreement, invoice, rate):
    assert_closed(evaluate_price(with_rate(agreement, tiers=(Tier(None, rate),)), invoice), Outcome.MISSING)


def test_tax_excluded_only_when_separately_itemized(agreement, invoice):
    result = evaluate_price(agreement, with_line(invoice, tax=D("1500.00")))
    assert result.overcharge == D("7500.00")
    assert "tax 1500.00 separately excluded" in "\n".join(result.evaluation.trace)
    assert_closed(evaluate_price(agreement, with_line(invoice, tax=None)), Outcome.MISSING)


@pytest.mark.parametrize("variant", ["duplicate-id", "overlap", "duplicate-allocation"])
def test_no_double_counting_or_arbitrary_tier_resets(agreement, invoice, variant):
    first = invoice.lines[0]
    second = replace(first, id="second", allocation_ref="different-ledger")
    if variant == "duplicate-id":
        second = replace(second, id=first.id)
    if variant == "duplicate-allocation":
        second = replace(second, allocation_ref=first.allocation_ref,
                         start=first.start - timedelta(days=1), end=first.start)
    assert_closed(evaluate_price(agreement, replace(invoice, lines=(first, second), total=D("55000"))), Outcome.MISSING)


def test_versions_and_input_values_are_immutable(agreement, invoice):
    with pytest.raises(FrozenInstanceError):
        agreement.versions[1].effective_at = invoice.issued_at
    with pytest.raises(FrozenInstanceError):
        invoice.payment_status = "paid"
    with pytest.raises(FrozenInstanceError):
        agreement.versions[1].rates[0].tiers[0].rate = D("0")
    # Unapproved amendment does not mutate prior snapshots or earlier results.
    before = evaluate_price(agreement, invoice)
    changed = with_rate(agreement, tiers=(Tier(None, D("1")),))
    assert evaluate_price(changed, invoice).overcharge != before.overcharge
    assert evaluate_price(agreement, invoice) == before


def test_later_price_increase_is_permitted_by_explicit_snapshot(agreement, invoice):
    increased = with_rate(agreement, tiers=(Tier(D("1000"), D("25")), Tier(None, D("20"))))
    result = evaluate_price(increased, with_line(invoice, net=D("35000")))
    assert result.overcharge == 0 and result.lines[0].expected == D("35000")
    historical = load_demo_inputs()[2][1]
    assert evaluate_price(increased, historical).lines[0].expected == D("27500")


def test_demo_contract_json_serializable_provenance_and_financials():
    cases = demo_cases()
    assert len(cases) >= 5 and len({case["id"] for case in cases}) == len(cases)
    json.dumps(cases, allow_nan=False)
    required = {"id", "vendor", "title", "outcome", "stage", "amount", "currency", "sources", "trace", "clauses", "evidence", "timeline", "actions", "financials"}
    for case in cases:
        assert required <= case.keys() and case["id"].startswith("price-")
        assert case["sources"] == ["SYNTHETIC_CUSTOMER", "DETERMINISTIC_REPLAY"]
        assert case["provider_binding"] is None and case["actions"] == []
        assert case["trace"] and case["clauses"] and case["evidence"] and case["timeline"]
        for row in case["financials"]:
            if row["label"] in ("Prevented", "Claimed", "Awarded", "Recovered", "Applied"):
                assert row["value"] == "0.00"
    assert cases[0]["amount"] == cases[1]["amount"] == "7500.00"
    assert cases[-1]["amount"] is None
    cases[0]["trace"].clear()
    assert demo_cases()[0]["trace"]  # callers cannot corrupt subsequent replays
