from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json

import pytest

from uptime.contracts import EvaluationResult, Outcome, Source
from uptime.twilio import (ClaimBasis, Coverage, Exclusion, FeeKind, Plan,
                           ServiceFamily, TERMS_URL, TERMS_VERSION,
                           calendar_bounds, claim_deadline, demo_cases, evaluate)
from uptime.twilio_demo import demo_inputs

UTC = timezone.utc


@pytest.fixture
def base():
    return demo_inputs()[0][1]


def outage(base, seconds, start=None, **changes):
    beginning = start or datetime(2026, 10, 10, 12, tzinfo=UTC)
    return replace(base.intervals[0], start=beginning,
                   end=beginning + timedelta(seconds=seconds), **changes)


def evaluated_outage(base, seconds, **changes):
    return evaluate(replace(base, intervals=(outage(base, seconds),), **changes))


def test_four_independent_golden_outcomes_and_cp1():
    for fixture, inputs in demo_inputs():
        result = evaluate(inputs)
        assert isinstance(result, EvaluationResult)
        assert result.outcome.value == fixture["expected_outcome"]
        assert (str(result.amount.amount) if result.amount else None) == fixture["expected_amount"]
        assert result.trace and result.clauses
        assert all(c.version == TERMS_VERSION and c.uri == TERMS_URL for c in result.clauses)


def test_fee_basis_not_vendor_total(base):
    result = evaluate(base)
    assert result.amount.amount == Decimal("100")
    assert any("Eligible fees=1000.00" in line for line in result.trace)
    assert any("B=60 minutes; A=44640" in line for line in result.trace)
    assert all(any(name in line for line in result.trace) for name in ("carrier_fee_surcharge", "tax_levy_duty", "third_party"))


@pytest.mark.parametrize("plan,seconds,expected", [
    (Plan.BASE, 1339.199999, Outcome.INELIGIBLE),
    (Plan.BASE, 1339.2, Outcome.INELIGIBLE),  # exactly 99.95%, 22.32 min
    (Plan.BASE, 1339.200001, Outcome.ELIGIBLE),
    (Plan.BASE, 300, Outcome.INELIGIBLE),
    (Plan.ENTERPRISE, 299.999999, Outcome.INELIGIBLE),  # continuous minimum dominates threshold
    (Plan.ENTERPRISE, 300, Outcome.ELIGIBLE),
])
def test_strict_threshold_and_exact_five_minutes(base, plan, seconds, expected):
    assert evaluated_outage(base, seconds, plan=plan).outcome == expected


def test_enterprise_exact_threshold_with_month_boundary_minimum(base):
    # Full continuous outage lasts 600s; October portion is exactly 267.84s,
    # yielding 99.99%. Clipping must happen AFTER the continuous-duration test.
    boundary = datetime(2026, 10, 1, tzinfo=UTC)
    for extra, expected in [(0, Outcome.INELIGIBLE), (0.000001, Outcome.ELIGIBLE)]:
        incident = replace(base.intervals[0], start=boundary - timedelta(seconds=400),
                           end=boundary + timedelta(seconds=267.84 + extra))
        result = evaluate(replace(base, plan=Plan.ENTERPRISE, intervals=(incident,)))
        assert result.outcome == expected


@pytest.mark.parametrize("purchased,expected", [
    (date(2024, 10, 23), Outcome.ELIGIBLE),
    (date(2024, 10, 24), Outcome.INELIGIBLE),
    (date(2024, 10, 25), Outcome.INELIGIBLE),
    (None, Outcome.MISSING),
])
def test_administration_strict_purchase_cutoff(base, purchased, expected):
    assert evaluated_outage(base, 600, plan=Plan.ADMINISTRATION,
                            administration_purchased_on=purchased).outcome == expected


def test_overlapping_intervals_union_and_duplicates_do_not_inflate(base):
    first = outage(base, 1200)
    second = outage(base, 600, first.start + timedelta(minutes=10))
    result = evaluate(replace(base, intervals=(first, first, second)))
    assert result.outcome == Outcome.INELIGIBLE
    assert any("B=20 minutes" in line for line in result.trace)


def test_adjacent_records_merge_before_minimum_but_gaps_do_not(base):
    first = outage(base, 180)
    second = outage(base, 120, first.end)
    assert evaluate(replace(base, plan=Plan.ENTERPRISE, intervals=(first, second))).outcome == Outcome.ELIGIBLE
    gapped = replace(second, start=second.start + timedelta(microseconds=1),
                     end=second.end + timedelta(microseconds=1))
    assert evaluate(replace(base, plan=Plan.ENTERPRISE, intervals=(first, gapped))).outcome == Outcome.INELIGIBLE


def test_merge_before_month_clipping_and_support_outside_record_chains(base):
    boundary = datetime(2026, 10, 1, tzinfo=UTC)
    records = tuple(outage(base, 120, boundary + timedelta(seconds=offset))
                    for offset in (-240, -120, 0, 120, 240))
    result = evaluate(replace(base, plan=Plan.ENTERPRISE, intervals=records))
    assert result.outcome == Outcome.ELIGIBLE
    assert any("B=6 minutes" in line for line in result.trace)


def test_outage_crosses_end_month_and_clips_once(base):
    record = outage(base, 7200, datetime(2026, 10, 31, 23, tzinfo=UTC))
    result = evaluate(replace(base, intervals=(record, record)))
    assert any("B=60 minutes" in line for line in result.trace)


@pytest.mark.parametrize("exclusion", [
    Exclusion.OUTSIDE_CONTROL, Exclusion.CUSTOMER_OR_THIRD_PARTY,
    Exclusion.CUSTOMER_TECHNOLOGY, Exclusion.EMERGENCY_MAINTENANCE, Exclusion.PREVIEW,
])
def test_defined_exclusions(base, exclusion):
    result = evaluate(replace(base, intervals=(replace(base.intervals[0], exclusion=exclusion),)))
    assert result.outcome == Outcome.INELIGIBLE and result.amount is None


@pytest.mark.parametrize("hours,expected", [("24", Outcome.INELIGIBLE), ("23.999", Outcome.ELIGIBLE), (None, Outcome.MISSING)])
def test_scheduled_maintenance_requires_at_least_24_hours_notice(base, hours, expected):
    record = replace(base.intervals[0], exclusion=Exclusion.SCHEDULED_MAINTENANCE,
                     scheduled_notice_hours=Decimal(hours) if hours else None)
    assert evaluate(replace(base, intervals=(record,))).outcome == expected


def test_excluded_overlap_cannot_be_counted_by_other_record(base):
    record = base.intervals[0]
    excluded = replace(record, start=record.start + timedelta(minutes=10),
                       end=record.end - timedelta(minutes=10), exclusion=Exclusion.EMERGENCY_MAINTENANCE)
    result = evaluate(replace(base, intervals=(record, excluded)))
    assert result.outcome == Outcome.INELIGIBLE
    assert any("B=20 minutes" in line for line in result.trace)


@pytest.mark.parametrize("changes", [
    {"exclusion": Exclusion.UNKNOWN}, {"exclusion_ref": ""},
    {"status_url": "https://internal.example/metrics"},
    {"status_url": "https://status.twilio.com.evil.example/incident"},
    {"status_url": "http://status.twilio.com"}, {"documentation_refs": ()},
    {"customer_affected": None}, {"attribution_ref": ""},
])
def test_public_incident_or_internal_telemetry_alone_not_enough(base, changes):
    result = evaluate(replace(base, intervals=(replace(base.intervals[0], **changes),)))
    assert result.outcome == Outcome.MISSING and result.missing and result.amount is None


def test_not_customer_affected_and_other_api_do_not_count(base):
    for changes in ({"customer_affected": False}, {"api_id": "other-api"}):
        assert evaluate(replace(base, intervals=(replace(base.intervals[0], **changes),))).outcome == Outcome.INELIGIBLE


@pytest.mark.parametrize("changes", [
    {"timezone": None}, {"timezone_ref": ""}, {"timezone": "Unknown/Zone"},
    {"plan": None}, {"plan_ref": ""}, {"agreement_ref": ""},
    {"subscription_coverage": None}, {"status_coverage": None},
    {"fees_complete": False}, {"fees_ref": ""}, {"claim_subject": "credit please"},
])
def test_unknown_required_facts_fail_closed(base, changes):
    assert evaluate(replace(base, **changes)).outcome == Outcome.MISSING


def test_incomplete_partial_month_and_future_coverage(base):
    for coverage in (replace(base.status_coverage, complete=False),
                     replace(base.status_coverage, start=base.status_coverage.start + timedelta(seconds=1)),
                     replace(base.status_coverage, end=base.status_coverage.end - timedelta(seconds=1))):
        assert evaluate(replace(base, status_coverage=coverage)).outcome == Outcome.MISSING
    assert evaluate(replace(base, as_of=datetime(2026, 10, 31, tzinfo=UTC))).outcome == Outcome.MISSING
    assert evaluate(replace(base, intervals=(replace(base.intervals[0], end=base.as_of + timedelta(seconds=1)),))).outcome == Outcome.MISSING
    assert evaluate(replace(base, plan=Plan.ADMINISTRATION,
                            administration_purchased_on=date(2026, 10, 2))).outcome == Outcome.MISSING


def test_deadline_calendar_not_one_month_or_thirty_days_from_incident(base):
    assert claim_deadline(date(2026, 10, 1)) == date(2026, 11, 30)
    assert claim_deadline(date(2026, 2, 1)) == date(2026, 3, 30)
    assert claim_deadline(date(2028, 2, 1)) == date(2028, 3, 30)
    assert claim_deadline(date(2026, 12, 1)) == date(2027, 1, 30)
    assert evaluate(replace(base, as_of=datetime(2026, 11, 30, 23, 59, 59, 999999, tzinfo=UTC))).outcome == Outcome.ELIGIBLE
    assert evaluate(replace(base, as_of=datetime(2026, 12, 1, tzinfo=UTC))).outcome == Outcome.INELIGIBLE


def test_timely_receipt_preserves_claim_after_deadline_but_cannot_be_faked(base):
    later = replace(base, as_of=datetime(2026, 12, 10, tzinfo=UTC),
                    submitted_at=datetime(2026, 11, 20, tzinfo=UTC), submission_ref="synthetic:receipt")
    assert evaluate(later).outcome == Outcome.ELIGIBLE
    assert evaluate(replace(later, submission_ref="")).outcome == Outcome.MISSING
    assert evaluate(replace(later, submitted_at=datetime(2026, 12, 11, tzinfo=UTC))).outcome == Outcome.MISSING
    assert evaluate(replace(later, submitted_at=datetime(2026, 10, 31, tzinfo=UTC))).outcome == Outcome.MISSING


def test_calendar_month_dst_and_leap_year():
    for month, zone, expected_minutes in [
        (date(2026, 10, 1), "UTC", 44640), (date(2028, 2, 1), "UTC", 41760),
        (date(2026, 11, 1), "America/Los_Angeles", 43260),
        (date(2026, 3, 1), "America/Los_Angeles", 44580),
    ]:
        start, end = calendar_bounds(month, zone)
        assert (end - start) == timedelta(minutes=expected_minutes)


def test_explicit_timezone_changes_deadline_and_month_bounds(base):
    start, end = calendar_bounds(base.month, "America/Los_Angeles")
    coverage = Coverage(start, end, True, "synthetic:la-calendar-coverage")
    case = replace(base, timezone="America/Los_Angeles", status_coverage=coverage,
                   subscription_coverage=coverage, as_of=datetime(2026, 12, 1, 7, 59, 59, tzinfo=UTC))
    assert evaluate(case).outcome == Outcome.ELIGIBLE
    assert evaluate(replace(case, as_of=datetime(2026, 12, 1, 8, tzinfo=UTC))).outcome == Outcome.INELIGIBLE


@pytest.mark.parametrize("family", [ServiceFamily.SEGMENT, ServiceFamily.STYTCH, ServiceFamily.FLEX_CRITICAL])
def test_explicitly_excluded_services(base, family):
    assert evaluate(replace(base, service=replace(base.service, family=family))).outcome == Outcome.INELIGIBLE


@pytest.mark.parametrize("changes,expected", [
    ({"supported": False}, Outcome.INELIGIBLE),
    ({"generally_available": False}, Outcome.INELIGIBLE),
    ({"supported": None}, Outcome.MISSING),
    ({"evidence_ref": ""}, Outcome.MISSING),
    ({"family": ServiceFamily.OTHER}, Outcome.UNSUPPORTED),
])
def test_service_scope(base, changes, expected):
    assert evaluate(replace(base, service=replace(base.service, **changes))).outcome == expected


def sendgrid(base, **changes):
    return replace(base, service=replace(base.service, family=ServiceFamily.SENDGRID),
                   intervals=tuple(replace(i, status_url="https://status.sendgrid.com") for i in base.intervals),
                   fees=(replace(base.fees[0], kind=FeeKind.EMAIL_PACKAGE),), **changes)


def test_sendgrid_availability_uses_email_package(base):
    assert evaluate(sendgrid(base)).amount.amount == Decimal("100")
    for plan in (Plan.EMAIL_DELIVERABILITY, Plan.EMAIL_EXPERTS, Plan.EMAIL_MANAGEMENT,
                 Plan.EMAIL_MANAGEMENT_STRATEGY, Plan.EMAIL_STRATEGY_GOLD):
        assert evaluate(sendgrid(base, plan=plan)).outcome == Outcome.ELIGIBLE


def test_sendgrid_connection_exception_cannot_silently_deny(base):
    case = replace(sendgrid(base, plan=Plan.EMAIL_DELIVERABILITY), intervals=())
    assert evaluate(case).outcome == Outcome.UNSUPPORTED
    assert evaluate(replace(case, connection_rate_met=False)).outcome == Outcome.UNSUPPORTED
    assert evaluate(replace(case, connection_rate_met=True, connection_rate_ref="synthetic:qualified-rate-report")).outcome == Outcome.INELIGIBLE
    assert evaluate(replace(case, basis=ClaimBasis.CONNECTION_RATE)).outcome == Outcome.UNSUPPORTED


@pytest.mark.parametrize("changes", [
    {"kind": FeeKind.UNKNOWN}, {"api_id": None}, {"actually_incurred": None},
    {"evidence_ref": ""}, {"mapping_ref": ""},
])
def test_unresolved_fee_not_silently_excluded(base, changes):
    assert evaluate(replace(base, fees=(replace(base.fees[0], **changes),))).outcome == Outcome.MISSING


def test_duplicate_fees_negative_adjustments_non_usd_fail_closed(base):
    assert evaluate(replace(base, fees=(base.fees[0], base.fees[0]))).outcome == Outcome.MISSING
    for changes in ({"amount": Decimal("-1")}, {"currency": "EUR"}):
        assert evaluate(replace(base, fees=(replace(base.fees[0], **changes),))).outcome == Outcome.UNSUPPORTED
    assert evaluate(replace(base, currency="EUR")).outcome == Outcome.UNSUPPORTED


def test_no_fee_unincurred_or_wrong_month_no_claim_value(base):
    for fees in ((), (replace(base.fees[0], actually_incurred=False),),
                 (replace(base.fees[0], month=date(2026, 9, 1)),)):
        result = evaluate(replace(base, fees=fees))
        assert result.outcome == Outcome.INELIGIBLE and result.amount is None


def test_exact_fractional_cent_credit_and_ambient_precision_independent(base):
    case = replace(base, fees=(replace(base.fees[0], amount=Decimal("10.01")),))
    with localcontext() as context:
        context.prec = 3
        assert evaluate(case).amount.amount == Decimal("1.001")


def test_unsupported_agreement_and_plan_pairings(base):
    assert evaluate(replace(base, terms_version="2024-01-01")).outcome == Outcome.UNSUPPORTED
    assert evaluate(replace(base, month=date(2026, 3, 1))).outcome == Outcome.UNSUPPORTED
    assert evaluate(replace(base, plan=Plan.EMAIL_DELIVERABILITY)).outcome == Outcome.UNSUPPORTED
    assert evaluate(sendgrid(base, plan=Plan.ENTERPRISE)).outcome == Outcome.UNSUPPORTED


def test_malformed_types_timestamps_and_money_rejected(base):
    for invalid in (0.1, Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValueError):
            replace(base.fees[0], amount=invalid)
    with pytest.raises(ValueError):
        replace(base, as_of=datetime(2026, 11, 3))
    with pytest.raises(ValueError):
        replace(base.intervals[0], end=base.intervals[0].start)
    with pytest.raises(ValueError):
        replace(base, plan="enterprise")
    with pytest.raises(ValueError):
        replace(base.service, supported="false")
    with pytest.raises(ValueError):
        replace(base, fees_complete=1)
    with pytest.raises(ValueError):
        replace(base.intervals[0], customer_affected="yes")


def test_demo_contract_exact_provenance_and_no_recovered_value():
    cases = demo_cases()
    assert len(cases) == 4
    required = {"id", "vendor", "title", "outcome", "stage", "amount", "currency", "sources",
                "trace", "clauses", "evidence", "timeline", "actions", "financials"}
    for case in cases:
        assert required <= case.keys()
        assert case["id"].startswith("sla-") and case["actions"] == []
        assert case["evidence"][0]["sources"] == [Source.PUBLIC.value]
        assert all(Source.PUBLIC.value not in item["sources"] for item in case["evidence"][1:])
        assert all(Source.PUBLIC.value not in item["sources"] for item in case["financials"])
        assert all(item["value"] == "0.00" for item in case["financials"][1:])
        if case["outcome"] != Outcome.ELIGIBLE.value:
            assert case["amount"] is None
    assert json.loads(json.dumps(cases)) == cases
