"""Strict whole-service month evidence join (complete_service_month/1): authored refusal and acceptance matrix.

Each refusal is a ValueError, which the active route reports as INSUFFICIENT_EVIDENCE. The join's only
output is the existing evaluator observation. No frozen corpus, oracle or private expected answer is read.
"""
from datetime import UTC, datetime
from hashlib import sha256
import json

import pytest

from uptime.correspondence_monthly import monthly_observation
from uptime.correspondence_types import SOURCE, Delivery, Scope
from uptime.vendor_eval import FACT_FIELDS

WHOLE = dict(account="north-612", vendor="Boreal Relay", contract="BR-74", service="Message Store",
             currency="USD", month="2026-10")
SCOPE = Scope(**WHOLE)
OVERLAY = dict(agreement="BR-74", account="north-612", product="Message Store", plan="Team",
               fee_line_ref="monthly-store", currency="USD", effective_from="2026-01-01", effective_until="2026-12-31")
AT = datetime(2026, 11, 3, tzinfo=UTC)
RECEIVED = "2026-11-02T00:00:00+00:00"
OCTOBER = ("2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z")
INTERVAL = dict(start="2026-10-14T01:01:00Z", end="2026-10-14T01:46:00Z")
GAP = dict(ref="gap-1", start="2026-10-09T00:00:00Z", end="2026-10-09T01:00:00Z")


def report(kind, period=OCTOBER, observed="2026-11-01T06:00:00Z", **changes):
    """An authored report; ``changes`` may add repeated identity (including ``month``) or override facts."""
    return dict(kind=kind, source_ref=kind + "-ref", observed_at=observed, start=period[0], end=period[1], plan="Team",
                complete=True, exclusions_removed=True, gaps=[], unresolved_exclusions=[],
                eligible_downtime_minutes=45) | changes


def line(id="monthly-store", kind="affected_api", amount="417.36", **identity):
    return dict(id=id, kind=kind, amount=amount, **identity)


def invoice(*lines):
    return dict(kind="invoice", lines=list(lines) or [line(), line("tax-11", "tax", "0.00")])


def stored(raw):
    """The body exactly as intake stores it: the signed delivery parsed, then its set fields dumped."""
    return Delivery.model_validate(dict(event_id="evt-1", scope=WHOLE, body=raw)).body.model_dump(exclude_unset=True)


def fact(raw, *, source=None, subject=None, event_id=None, received=RECEIVED, known=None, parse=True):
    """A stored, server-authenticated delivery (the shape CorrespondenceDesk._receive records)."""
    kind = raw["kind"]
    source = source or SOURCE.get(kind, "customer")
    subject = subject or source + "-fixture"
    event_id = event_id or kind
    body = stored(raw) if parse else raw
    digest = sha256(json.dumps([event_id, source, subject, body], sort_keys=True, default=str).encode()).hexdigest()
    return dict(event_id=event_id, source=source, subject=subject, kind=kind, digest=digest,
                source_key_id="fixture-hmac:" + subject, source_grant_id="grant:" + subject,
                received_at=received, known_at=known or received, body=body)


def evidence(coverage=None, attribution=None, bill=None):
    return [coverage or fact(report("monthly_coverage")), attribution or fact(report("monthly_attribution")),
            bill or fact(invoice())]


def observe(events, scope=SCOPE, overlay=OVERLAY, filed=AT, at=AT):
    return monthly_observation(scope, events, overlay, filed, at)


def refused(events, match, **kwargs):
    with pytest.raises(ValueError, match=match):
        observe(events, **kwargs)


# Acceptance ---------------------------------------------------------------------------------------------

def test_complete_independent_month_is_exactly_the_existing_evaluator_observation():
    events = evidence()
    observation = observe(events)
    assert set(observation) <= FACT_FIELDS and "tenant" not in observation
    assert observation == dict(
        agreement="BR-74", account="north-612", product="Message Store", plan="Team", month="2026-10",
        eligible_downtime_minutes=45, monitor_source="simulated_vendor", monitor_month="2026-10",
        monitor_ref=events[0]["digest"], month_complete=True, exclusions_removed=True, monthly_fee_cents=41736,
        fee_line_ref="monthly-store", fee_month="2026-10", fee_ref=events[2]["digest"],
        received_at="2026-11-03T00:00:00+00:00")
    assert "incident" not in json.dumps(observation)


def test_original_filing_time_is_passed_through_unchanged():
    filed = datetime(2026, 11, 4, 9, 30, tzinfo=UTC)
    observation = observe(evidence(), filed=filed, at=datetime(2026, 11, 20, tzinfo=UTC))
    assert observation["received_at"] == "2026-11-04T09:30:00+00:00"


def test_zero_eligible_downtime_is_a_reported_zero_not_a_missing_value():
    observation = observe(evidence(fact(report("monthly_coverage", eligible_downtime_minutes=0)),
                                   fact(report("monthly_attribution", eligible_downtime_minutes=0))))
    assert observation["eligible_downtime_minutes"] == 0 and type(observation["eligible_downtime_minutes"]) is int


def test_whole_month_of_downtime_is_the_upper_bound():
    full = 31 * 24 * 60
    observation = observe(evidence(fact(report("monthly_coverage", eligible_downtime_minutes=full)),
                                   fact(report("monthly_attribution", eligible_downtime_minutes=full))))
    assert observation["eligible_downtime_minutes"] == 44640


def test_matching_repeated_identity_offset_bounds_and_report_at_month_end_are_accepted():
    coverage = fact(report("monthly_coverage", period=("2026-09-30T22:00:00-02:00", "2026-11-01T09:00:00+09:00"),
                           observed="2026-11-01T00:00:00Z", **WHOLE), received="2026-11-01T00:00:00+00:00")
    bill = fact(invoice(line(**WHOLE), line("tax-11", "tax", "0.00", invoice="oct-inv-3"),
                        line("carrier-2", "carrier", "12.00", invoice="oct-inv-3")))
    observation = observe(evidence(coverage, bill=bill))
    assert observation["monthly_fee_cents"] == 41736  # uncovered lines never join the covered base
    observe(evidence(coverage, bill=bill), scope=Scope(**WHOLE | {"invoice": "oct-inv-3"}))


def test_supplements_are_ignored_as_in_the_legacy_join():
    artifact = fact(dict(kind="artifact", source_ref="a-1", observed_at="2026-11-01T07:00:00Z", artifact_ref="log-1",
                         artifact_type="resource_log", body_sha256="0" * 64, content="x"), parse=False)
    assert observe(evidence() + [artifact])["eligible_downtime_minutes"] == 45


# Missing and conflicting data ---------------------------------------------------------------------------

@pytest.mark.parametrize("absent", [0, 2])
def test_each_independent_record_is_required(absent):
    events = evidence()
    kind = events.pop(absent)["kind"]
    refused(events, "Awaiting independent " + kind)


@pytest.mark.parametrize("value", [None, ..., 45.5, 45.0, float("nan"), float("inf"), -1, True, "45"])
def test_stored_downtime_is_never_defaulted_or_coerced(value):
    raw = report("monthly_attribution")
    if value is ...:
        del raw["eligible_downtime_minutes"]
    else:
        raw["eligible_downtime_minutes"] = value
    refused(evidence(attribution=fact(raw, parse=False)), "not a valid strict month report")


def test_coverage_and_attribution_must_agree_on_eligible_minutes():
    refused(evidence(attribution=fact(report("monthly_attribution", eligible_downtime_minutes=44))),
            "disagree about eligible downtime")


@pytest.mark.parametrize("kind", ["monthly_coverage", "monthly_attribution", "invoice"])
def test_a_second_record_of_one_kind_is_a_conflict_not_a_choice(kind):
    events = evidence()
    second = (fact(invoice(line(amount="400.00")), event_id="invoice-2") if kind == "invoice"
              else fact(report(kind, eligible_downtime_minutes=46), event_id=kind + "-2"))
    refused(events + [second], "Duplicate or wrong-role")


@pytest.mark.parametrize("kind,wrong", [("monthly_coverage", "customer"), ("monthly_attribution", "status"),
                                        ("invoice", "status"), ("monthly_coverage", "billing")])
def test_record_from_the_wrong_source_role_is_refused(kind, wrong):
    events = evidence()
    index = ["monthly_coverage", "monthly_attribution", "invoice"].index(kind)
    raw = invoice() if kind == "invoice" else report(kind)
    events[index] = fact(raw, source=wrong)
    refused(events, "Duplicate or wrong-role")


# Foreign identity, gaps, exclusions and period ----------------------------------------------------------

@pytest.mark.parametrize("field,other", [("account", "north-613"), ("vendor", "Other Relay"), ("contract", "BR-75"),
                                         ("service", "Message Queue"), ("month", "2026-09"), ("currency", "EUR")])
def test_report_naming_a_foreign_identity_is_refused(field, other):
    refused(evidence(fact(report("monthly_coverage", **{field: other}))), field + " outside the authenticated claim scope")
    refused(evidence(attribution=fact(report("monthly_attribution", **{field: other}))), "outside the authenticated")


@pytest.mark.parametrize("field,other", [("account", "north-613"), ("vendor", "Other Relay"), ("contract", "BR-75"),
                                         ("service", "Message Queue"), ("month", "2026-09"), ("currency", "EUR")])
def test_invoice_line_naming_a_foreign_identity_is_refused(field, other):
    refused(evidence(bill=fact(invoice(line(), line("tax-11", "tax", "0.00", **{field: other})))),
            "invoice line tax-11 names " + field)


@pytest.mark.parametrize("field", ["incident", "component", "region"])
def test_invoice_line_cannot_invent_an_obligation_field(field):
    refused(evidence(bill=fact(invoice(line(**{field: "x-1"})))), "cannot name a component, incident or region")


def test_invoice_lines_cannot_name_contradictory_invoices():
    split = invoice(line(invoice="inv-a"), line("tax-11", "tax", "0.00", invoice="inv-b"))
    refused(evidence(bill=fact(split)), "contradictory invoice identities")
    other = invoice(line(invoice="inv-b"))
    refused(evidence(bill=fact(other)), "contradictory invoice identities", scope=Scope(**WHOLE | {"invoice": "inv-a"}))


@pytest.mark.parametrize("kind", ["monthly_coverage", "monthly_attribution"])
@pytest.mark.parametrize("changes", [{"gaps": [GAP]},
                                     {"unresolved_exclusions": [dict(GAP, ref="exc-1", reason="customer network")]}])
def test_a_stated_gap_or_unresolved_exclusion_cannot_establish_the_month(kind, changes):
    events = evidence()
    events[0 if kind == "monthly_coverage" else 1] = fact(report(kind, **changes))
    refused(events, "gaps or unresolved exclusions")


@pytest.mark.parametrize("changes", [{"complete": False}, {"exclusions_removed": False}])
def test_incomplete_or_unadjusted_reports_are_refused(changes):
    refused(evidence(attribution=fact(report("monthly_attribution", **changes))), "complete with exclusions removed")


@pytest.mark.parametrize("period", [("2026-10-01T00:01:00Z", "2026-11-01T00:00:00Z"),
                                    ("2026-10-01T00:00:00Z", "2026-10-31T23:59:00Z"),
                                    ("2026-10-01T00:00:00Z", "2026-11-01T00:00:01Z"),
                                    ("2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z"),
                                    ("2026-10-01T00:00:00+01:00", "2026-11-01T00:00:00+01:00")])
def test_report_must_cover_exactly_the_utc_calendar_month(period):
    refused(evidence(fact(report("monthly_coverage", period=period))), "exactly the UTC calendar month 2026-10")


def test_report_for_another_plan_is_refused():
    refused(evidence(fact(report("monthly_coverage", plan="Enterprise"))), "different plan")


def test_downtime_beyond_the_actual_month_length_is_refused():
    february = Scope(**WHOLE | {"month": "2026-02"})
    bounds, observed, received = ("2026-02-01T00:00:00Z", "2026-03-01T00:00:00Z"), "2026-03-01T06:00:00Z", "2026-03-02T00:00:00+00:00"
    at = datetime(2026, 3, 3, tzinfo=UTC)

    def month_of(minutes):
        return [fact(report(kind, period=bounds, observed=observed, eligible_downtime_minutes=minutes), received=received)
                for kind in ("monthly_coverage", "monthly_attribution")] + [fact(invoice(), received=received)]

    assert observe(month_of(28 * 24 * 60), scope=february, filed=at, at=at)["eligible_downtime_minutes"] == 40320
    refused(month_of(28 * 24 * 60 + 1), "within the month", scope=february, filed=at, at=at)


# Independent provenance --------------------------------------------------------------------------------

@pytest.mark.parametrize("field,pair", [("subject", (0, 1)), ("source_key_id", (1, 2)), ("source_grant_id", (0, 2)),
                                        ("subject", (1, 2)), ("source_key_id", (0, 2)), ("source_grant_id", (0, 1))])
def test_status_customer_and_billing_need_distinct_enrolled_signers(field, pair):
    events = evidence()
    events[pair[1]][field] = events[pair[0]][field]
    refused(events, "distinct enrolled sources")


@pytest.mark.parametrize("field,value", [("subject", ""), ("subject", None), ("source_key_id", None),
                                         ("source_key_id", ""), ("source_grant_id", None), ("source_grant_id", 7),
                                         ("digest", "not-a-digest"), ("digest", None)])
def test_retained_authentic_provenance_is_required(field, value):
    for index in range(3):
        events = evidence()
        events[index][field] = value
        refused(events, "retained authenticated source provenance")


# Mixed legacy evidence and extra facts ------------------------------------------------------------------

LEGACY = [dict(kind="status", **INTERVAL), dict(kind="impact", affected=True, exclusion="none", **INTERVAL),
          dict(kind="coverage", start=OCTOBER[0], end=OCTOBER[1], complete=True, exclusions_removed=True,
               incident_ids=["inc-612"], total_eligible_minutes=45),
          dict(kind="component", component_id="store-east", **INTERVAL),
          dict(kind="notice", issued_at="2026-10-01T00:00:00Z", **INTERVAL)]


@pytest.mark.parametrize("raw", LEGACY, ids=[raw["kind"] for raw in LEGACY])
def test_legacy_incident_records_cannot_be_mixed_into_strict_month_evidence(raw):
    refused(evidence() + [fact(raw)], "cannot be mixed into strict whole-month evidence")


@pytest.mark.parametrize("kind", ["service_monitor", "service_invoice", "resource_invoice", "original_filing_receipt",
                                  "maintenance_evidence", "account_conditions", "filing_material", "request_evidence"])
def test_extra_non_supplement_facts_are_refused(kind):
    refused(evidence() + [fact(dict(kind=kind), parse=False)], "does not establish how to use this " + kind)


# Chronology: stale and future reports ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["monthly_coverage", "monthly_attribution"])
@pytest.mark.parametrize("observed,received,known", [
    ("2026-10-31T23:59:59Z", RECEIVED, None),                                      # observed before the month ended
    ("2026-11-01T00:00:00Z", "2026-10-31T23:59:59+00:00", None),                   # server receipt before month end
    ("2026-11-03T00:00:01Z", "2026-11-03T00:00:01+00:00", None),                   # observed after evaluation time
    ("2026-11-01T06:00:00Z", "2026-11-03T00:00:01+00:00", None),                   # received in the future
    ("2026-11-01T06:00:00Z", RECEIVED, "2026-11-03T00:00:01+00:00"),               # known in the future
    ("2026-11-02T06:00:00Z", RECEIVED, None),                                      # observed after the server knew it
])
def test_reports_must_be_observed_and_received_after_month_end_and_not_in_the_future(kind, observed, received, known):
    events = evidence()
    events[0 if kind == "monthly_coverage" else 1] = fact(report(kind, observed=observed), received=received, known=known)
    refused(events, "after the month ends, and not in the future")


def test_known_before_received_or_unparseable_receipt_is_refused():
    events = evidence()
    events[0]["known_at"] = "2026-11-01T12:00:00+00:00"
    refused(events, "cannot be known before the server received it")
    events = evidence()
    events[1]["received_at"] = "2026-11-02T00:00:00"  # offset-naive
    refused(events, "retained server receipt time")


def test_invoice_unknown_at_evaluation_time_is_refused():
    refused(evidence(bill=fact(invoice(), received="2026-11-03T00:00:01+00:00")), "not yet known")


def test_evaluation_and_filing_times_must_be_offset_aware():
    refused(evidence(), "offset-aware", at=datetime(2026, 11, 3))
    refused(evidence(), "offset-aware", filed=datetime(2026, 11, 3))


# Fee line, taxes and currency --------------------------------------------------------------------------

@pytest.mark.parametrize("lines", [
    [line("other-line")],                                                       # covered line differs from overlay
    [line(), line("monthly-store-2")],                                          # two covered lines
    [line("monthly-store", "unaffected_api")],                                  # the reference is not a covered line
    [line("carrier-2", "carrier", "12.00")],                                     # no covered line at all
])
def test_exactly_one_covered_line_must_match_the_overlay_fee_line(lines):
    refused(evidence(bill=fact(invoice(*lines))), "fee line reference")


def test_duplicate_invoice_line_references_are_refused():
    refused(evidence(bill=fact(invoice(line(), line(kind="tax", amount="0.00")))), "Duplicate invoice line")


@pytest.mark.parametrize("amount", ["0.01", "1", "20.00"])
def test_nonzero_tax_is_refused(amount):
    refused(evidence(bill=fact(invoice(line(), line("tax-11", "tax", amount)))), "nonzero tax")


def test_a_zero_covered_fee_is_a_verified_zero():
    assert observe(evidence(bill=fact(invoice(line(amount="0.00")))))["monthly_fee_cents"] == 0


def test_unsupported_or_mismatched_currency_is_refused():
    refused(evidence(), "Unsupported or mismatched currency", scope=Scope(**WHOLE | {"currency": "EUR"}),
            overlay=OVERLAY | {"currency": "EUR"})
    refused(evidence(), "Unsupported or mismatched currency", overlay=OVERLAY | {"currency": "EUR"})


@pytest.mark.parametrize("field", ["incident", "component", "region"])
def test_scope_with_an_obligation_field_is_not_a_whole_service_month(field):
    refused(evidence(), "whole-service scope", scope=Scope(**WHOLE | {field: "x-1"}))
