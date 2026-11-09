"""Decision 91: temporal applicability of one signed evidence delivery to its granted service month.

These controls are new. They do not change an existing assertion. Every body below is an
authored synthetic record; none is customer evidence or a provider capture.
"""
import json
import sqlite3

import pytest

from uptime.correspondence_types import Delivery, Scope
from uptime.evidence_applicability import MARGIN, temporal_refusal
from uptime.source_config import SourceGrant, event_in_scope

SCOPE = Scope(account="test-account", vendor="Twilio", contract="signed-agreement", service="Twilio Messaging API",
              component="api-east", invoice="oct-bill", incident="oct-synthetic-outage", currency="USD",
              month="2026-10")  # D04-C (2026-11-09): region is not applicable to the Twilio profile (W5 test input)
INSIDE = dict(start="2026-10-08T01:00:00Z", end="2026-10-08T02:00:00Z")
PREVIOUS = dict(start="2026-09-08T01:00:00Z", end="2026-09-08T02:00:00Z")
REPORT = dict(source_ref="monitor-export", observed_at="2026-11-01T06:00:00Z",
              start="2026-10-01T00:00:00Z", end="2026-11-01T00:00:00Z")


def delivery(body, scope=SCOPE):
    return Delivery(event_id="event-1", scope=scope, body=body)


def refusal(body, month="2026-10"):
    return temporal_refusal(delivery(body).body, month)


def monitor_row(**interval):
    return dict(ref="row-1", account=SCOPE.account, product=SCOPE.service, region="east",
                resource_id=SCOPE.component, status="unavailable", **interval)


@pytest.mark.parametrize("kind,extra", [
    ("status", {}), ("impact", dict(affected=True, exclusion="none")),
    ("component", dict(component_id="api-east")),
    ("notice", dict(issued_at="2026-09-30T01:00:00Z")),
])
def test_measured_interval_inside_the_month_is_admissible_and_entirely_previous_month_is_refused(kind, extra):
    assert refusal(dict(kind=kind, **INSIDE, **extra)) is None
    reason = refusal(dict(kind=kind, **PREVIOUS, **extra))
    assert reason and "2026-10" in reason


def test_month_boundary_overlap_is_left_to_the_evaluator_and_offset_months_keep_a_margin():
    # A partially overlapping incident is real evidence; clipping is a contract rule, not intake.
    assert refusal(dict(kind="status", start="2026-09-30T23:00:00Z", end="2026-10-01T01:00:00Z")) is None
    assert refusal(dict(kind="status", start="2026-10-31T23:00:00Z", end="2026-11-01T01:00:00Z")) is None
    # A contract can measure the month in a named zone. Up to fourteen hours outside the UTC
    # month is not refused at intake; the governing terms decide whether it counts.
    assert MARGIN.total_seconds() == 14 * 3600
    assert refusal(dict(kind="status", start="2026-11-01T10:00:00Z", end="2026-11-01T13:00:00Z")) is None
    assert refusal(dict(kind="status", start="2026-09-30T12:00:00Z", end="2026-09-30T13:00:00Z")) is None
    assert refusal(dict(kind="status", start="2026-11-01T14:00:00Z", end="2026-11-01T15:00:00Z"))
    assert refusal(dict(kind="status", start="2026-09-30T08:00:00Z", end="2026-09-30T09:59:59Z"))
    # The window is exclusive at its end: an interval ending exactly at the margin cannot overlap it.
    assert refusal(dict(kind="status", start="2026-09-30T09:00:00Z", end="2026-09-30T10:00:00Z"))


def test_coverage_report_for_another_month_is_refused():
    body = dict(kind="coverage", start="2026-09-01T00:00:00Z", end="2026-10-01T00:00:00Z", complete=True,
                exclusions_removed=True, incident_ids=[SCOPE.incident], total_eligible_minutes=29)
    # The most likely mistake is an adjacent month. A whole-period report is checked against the
    # unwidened UTC month, so the incident margin cannot admit it.
    assert "report period" in refusal(body)
    assert refusal({**body, "start": "2026-10-01T00:00:00Z", "end": "2026-11-01T00:00:00Z"}) is None
    # Zone-measured Octobers (UTC+14 and UTC-12) still overlap the UTC month and are admitted.
    assert refusal({**body, "start": "2026-09-30T10:00:00Z", "end": "2026-10-31T10:00:00Z"}) is None
    assert refusal({**body, "start": "2026-10-01T12:00:00Z", "end": "2026-11-01T12:00:00Z"}) is None
    # Adjacent months in the extreme civil zones overlap UTC October by at most fourteen hours.
    assert refusal({**body, "start": "2026-08-31T10:00:00Z", "end": "2026-09-30T10:00:00Z"})  # UTC+14 September
    assert refusal({**body, "start": "2026-09-01T12:00:00Z", "end": "2026-10-01T12:00:00Z"})  # UTC-12 September
    assert refusal({**body, "start": "2026-10-31T10:00:00Z", "end": "2026-11-30T10:00:00Z"})  # UTC+14 November
    # Decision 91 critique falsification case 1, before correction, admitted the UTC-12 September report.
    telemetry = dict(kind="provider_telemetry", source_id="monitor-1", complete=True, records=[],
                     **{**REPORT, "start": "2026-09-01T00:00:00Z", "end": "2026-10-01T00:00:00Z",
                        "observed_at": "2026-10-01T06:00:00Z"})
    assert "report period" in refusal(telemetry)


def test_nested_resource_rows_must_describe_the_granted_month_and_their_own_report():
    row = dict(ref="symptom-1", resource_id=SCOPE.component, symptom="unavailable", **INSIDE)
    body = dict(kind="resource_status", complete=True, intervals=[row], **REPORT)
    assert refusal(body) is None
    assert "row symptom-1" in refusal({**body, "intervals": [{**row, **PREVIOUS}]})
    # A row inside the month but outside the report's own measured interval is internally inconsistent.
    narrow = {**body, "start": "2026-10-15T00:00:00Z", "end": "2026-11-01T00:00:00Z", "complete": False}
    assert "row symptom-1" in refusal(narrow)
    cause = dict(ref="cause-1", resource_id=SCOPE.component, cause="provider", **PREVIOUS)
    attribution = dict(kind="resource_attribution", complete=True, causes=[], exclusions=[cause], **REPORT)
    assert "row cause-1" in refusal(attribution)


@pytest.mark.parametrize("kind", ["provider_telemetry", "customer_telemetry"])
def test_monitor_records_outside_the_month_are_refused(kind):
    body = dict(kind=kind, source_id="monitor-1", complete=True, records=[monitor_row(**INSIDE)], **REPORT)
    assert refusal(body) is None
    assert refusal({**body, "records": [monitor_row(**PREVIOUS)]})


def test_customer_exclusion_spans_and_maintenance_windows_must_overlap_the_month():
    excluded = dict(ref="ex-1", resource_id=SCOPE.component, cause="customer-change", **PREVIOUS)
    body = dict(kind="customer_telemetry", source_id="monitor-1", complete=True, records=[],
                exclusions=[excluded], **REPORT)
    assert "row ex-1" in refusal(body)
    record = dict(ref="mw-1", account=SCOPE.account, resource_id=SCOPE.component,
                  announced_at="2026-09-20T00:00:00Z", **INSIDE)
    maintenance = dict(kind="maintenance_evidence", source_ref="calendar", observed_at="2026-11-01T06:00:00Z",
                       complete=True, records=[record])
    # An announcement before the month is ordinary; only the maintenance window is measured time.
    assert refusal(maintenance) is None
    assert "row mw-1" in refusal({**maintenance, "records": [{**record, **PREVIOUS}]})


def test_request_witness_outside_the_month_is_refused():
    witness = dict(ref="req-1", resource_id=SCOPE.component, interval_ref="symptom-1",
                   requested_at="2026-10-08T01:30:00Z", valid=True, failed=True)
    body = dict(kind="request_evidence", source_ref="request-log", observed_at="2026-11-01T06:00:00Z", records=[witness])
    assert refusal(body) is None
    assert "row req-1" in refusal({**body, "records": [{**witness, "requested_at": "2026-09-08T01:30:00Z"}]})


@pytest.mark.parametrize("kind", ["provider_telemetry", "customer_telemetry"])
def test_a_complete_report_cannot_be_observed_before_its_period_ends(kind):
    early = {**REPORT, "observed_at": "2026-10-20T00:00:00Z"}
    body = dict(kind=kind, source_id="monitor-1", complete=True, records=[monitor_row(**INSIDE)], **early)
    assert "complete" in refusal(body)
    # An honestly partial snapshot is still admissible; evaluators keep it insufficient.
    assert refusal({**body, "complete": False}) is None
    maintenance = dict(kind="maintenance_evidence", source_ref="calendar", observed_at="2026-10-20T00:00:00Z",
                       complete=True, records=[])
    # Maintenance evidence has no reporting interval of its own, so no completion time can be compared.
    assert refusal(maintenance) is None


@pytest.mark.parametrize("body", [
    dict(kind="invoice", lines=[dict(id="a", kind="affected_api", amount="621.30")]),
    dict(kind="billing_calendar", source_ref="calendar", observed_at="2026-11-01T00:00:00Z",
         cycles=[dict(ref="cycle-9", start="2026-09-15T00:00:00Z", end="2026-10-15T00:00:00Z")]),
    dict(kind="original_filing_receipt", source_ref="portal", observed_at="2026-11-20T00:00:00Z",
         receipt_id="R-1", received_at="2026-11-19T00:00:00Z", submitted_to="vendor portal", fields=[]),
    dict(kind="message", receipt_id="R-1", text="We received your request."),
])
def test_records_whose_timestamps_are_not_measured_service_time_are_not_refused_by_this_rule(body):
    assert refusal(body) is None


def test_signed_grant_refuses_wrong_period_but_still_applies_every_existing_scope_check():
    key = "3d4017c3e843895a92b70aa74d1b7ecc9e2a1c4b0d2f1e7a83b6c8f5d4e3a2b1"
    grant = SourceGrant.model_construct(subject="status.synthetic", source="status", scope=SCOPE, public_key=key)
    good, early = delivery(dict(kind="status", **INSIDE)), delivery(dict(kind="status", **PREVIOUS))
    assert event_in_scope(good, "status", SCOPE)
    assert not event_in_scope(early, "status", SCOPE)
    assert grant.allows("/api/correspondence/claims/inbox-1/events", good.model_dump_json())
    assert not grant.allows("/api/correspondence/claims/inbox-1/events", early.model_dump_json())
    # Existing scope identity checks are unchanged and still run first.
    other = delivery(dict(kind="status", **INSIDE), SCOPE.model_copy(update={"invoice": "other-invoice"}))
    assert not event_in_scope(other, "status", SCOPE)
    assert not event_in_scope(delivery(dict(kind="impact", affected=True, exclusion="none", **INSIDE)), "status", SCOPE)


def test_boundary_crossing_period_reports_keep_more_than_fourteen_hours_inside_the_month():
    base = dict(kind="resource_status", complete=False, intervals=[], source_ref="monitor-export",
                observed_at="2026-11-02T06:00:00Z")
    # A report wholly inside the UTC month is admitted however short; evaluators judge partial coverage.
    assert refusal({**base, "start": "2026-10-08T01:00:00Z", "end": "2026-10-08T02:00:00Z"}) is None
    assert refusal({**base, "start": "2026-10-31T10:00:00Z", "end": "2026-11-01T00:00:00Z"}) is None
    # Crossing the boundary with most of a day inside the month is admitted.
    assert refusal({**base, "start": "2026-10-31T04:00:00Z", "end": "2026-11-01T02:00:00Z"}) is None
    # Crossing it with fourteen hours or less inside cannot be told apart from an adjacent zone-month.
    assert refusal({**base, "start": "2026-10-31T10:00:00Z", "end": "2026-11-01T02:00:00Z"})
    assert refusal({**base, "start": "2026-09-30T00:00:00Z", "end": "2026-10-01T14:00:00Z"})
    assert refusal({**base, "start": "2026-09-30T00:00:00Z", "end": "2026-10-01T14:00:01Z"}) is None


def test_decision_91_critique_falsification_cases():
    # A September-issued notice for an October maintenance window is ordinary.
    assert refusal(dict(kind="notice", issued_at="2026-09-20T00:00:00Z", **INSIDE)) is None
    # Ongoing intervals cannot be delivered: the schema requires an end.
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        delivery(dict(kind="status", start="2026-10-08T01:00:00Z", end=None))
    # A complete report observed five minutes before its own end is internally inconsistent.
    early = dict(kind="provider_telemetry", source_id="monitor-1", complete=True, records=[],
                 **{**REPORT, "observed_at": "2026-10-31T23:55:00Z"})
    assert "complete" in refusal(early)
    # Residual, recorded rather than hidden: a short record inside the civil-zone margin is admitted.
    # Under a UTC-only contract the evaluator returns insufficient evidence, and the one-record-per-kind
    # desk can still be occupied. Supersession belongs to the intake desk owner.
    assert refusal(dict(kind="status", start="2026-09-30T22:00:00Z", end="2026-09-30T22:30:00Z")) is None


def test_month_must_be_an_exact_granted_month():
    with pytest.raises(ValueError):
        temporal_refusal(delivery(dict(kind="status", **INSIDE)).body, "2026-13")


# Composition through the mounted HTTP inbox and its real signature dependency.
from tests.test_source_config_v4 import CLAIM, EVENTS, ReviewerClient, DEFAULT_ORIGIN, app_for, local, setup, signed  # noqa: E402


def raw(body, event_id):
    return json.dumps({"event_id": event_id, "scope": SCOPE.model_dump(), "body": body}).encode()


def test_delivery_client_names_the_operator_record_before_signing(tmp_path):
    from scripts.deliver_evidence import deliver
    _, _, sender, _ = setup(tmp_path)

    class Unreachable:
        def get(self, *args, **kwargs):
            raise AssertionError("an out-of-period record must not reach the listener")
        post = get

    with pytest.raises(ValueError, match="outside service month 2026-10"):
        deliver(Unreachable(), sender, CLAIM, raw(dict(kind="status", **PREVIOUS), "status.september"))


def test_wrong_period_signed_delivery_is_refused_before_storage_and_cannot_block_the_correct_record(tmp_path):
    path, db, sender, human = setup(tmp_path)
    with local(app_for(path, db)) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "source.operator", human)
        assert reviewer.post("/api/correspondence/claims", {"claim_id": CLAIM, "scope": SCOPE.model_dump()}).status_code == 200
        mistaken = raw(dict(kind="status", **PREVIOUS), "status.september")
        assert client.post(EVENTS, content=mistaken, headers=signed(client, sender, mistaken)).status_code == 403
        with sqlite3.connect(db) as connection:
            assert connection.execute("SELECT count(*) FROM inbox_delivery").fetchone()[0] == 0
        correct = raw(dict(kind="status", **INSIDE), "status.october")
        receipt = client.post(EVENTS, content=correct, headers=signed(client, sender, correct))
        assert receipt.status_code == 200, receipt.text
        case = client.get(f"/api/correspondence/claims/{CLAIM}", headers=reviewer.headers).json()
        assert [e["detail"].split(" · ")[0] for e in case["evidence"]] == ["status.october"]
        # One status record only: the evaluator waits for impact and billing, not a contradiction review.
        assert case["outcome"] == "INSUFFICIENT_EVIDENCE"
        assert "Contradictory" not in json.dumps(case)
