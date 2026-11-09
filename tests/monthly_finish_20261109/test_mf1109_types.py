"""Typed strict whole-month records: wire schema, source roles and the existing signed-grant scope check.

Authored records only. The refusals here happen at the wire boundary, before storage.
"""
import json

import pytest
from pydantic import ValidationError

from uptime.correspondence_types import (SOURCE, Coverage, Delivery, MonthlyAttribution, MonthlyCoverage, Scope)
from uptime.source_config import event_in_scope

WHOLE = dict(account="north-612", vendor="Boreal Relay", contract="BR-74", service="Message Store",
             currency="USD", month="2026-10")
REPORT = dict(source_ref="report-oct", observed_at="2026-11-01T06:00:00Z", start="2026-10-01T00:00:00Z",
              end="2026-11-01T00:00:00Z", plan="Team", complete=True, exclusions_removed=True, gaps=[],
              unresolved_exclusions=[], eligible_downtime_minutes=45)


def wire(kind, **changes):
    return json.dumps(dict(event_id="evt-1", scope=WHOLE, body=dict(REPORT, kind=kind) | changes))


@pytest.mark.parametrize("kind,model,role", [("monthly_coverage", MonthlyCoverage, "status"),
                                             ("monthly_attribution", MonthlyAttribution, "customer")])
def test_strict_month_records_parse_with_their_fixed_source_role(kind, model, role):
    event = Delivery.model_validate_json(wire(kind))
    assert type(event.body) is model and SOURCE[kind] == role
    assert event.body.start == "2026-10-01T00:00:00+00:00" and event.body.end == "2026-11-01T00:00:00+00:00"
    stored = event.body.model_dump(exclude_unset=True)
    assert stored["eligible_downtime_minutes"] == 45 and stored["gaps"] == [] and stored["unresolved_exclusions"] == []
    assert not {"account", "vendor", "incident", "component", "region"} & stored.keys()  # absent stays absent


@pytest.mark.parametrize("raw", ["45.5", "45.0", '"45"', "true", "-1", "44641", "NaN", "Infinity", "1e2", "null"])
def test_downtime_must_be_a_bounded_whole_minute_integer(raw):
    payload = wire("monthly_coverage").replace('"eligible_downtime_minutes": 45', '"eligible_downtime_minutes": ' + raw)
    assert raw in payload
    with pytest.raises(ValidationError):
        Delivery.model_validate_json(payload)


@pytest.mark.parametrize("field", ["eligible_downtime_minutes", "gaps", "unresolved_exclusions", "complete",
                                   "exclusions_removed", "plan", "observed_at", "start", "end"])
def test_no_month_fact_defaults_when_omitted(field):
    body = dict(REPORT, kind="monthly_attribution")
    del body[field]
    with pytest.raises(ValidationError):
        Delivery.model_validate(dict(event_id="evt-1", scope=WHOLE, body=body))


@pytest.mark.parametrize("extra", [{"incident": "INC-1"}, {"component": "store-east"}, {"region": "east"},
                                   {"incident_ids": ["INC-1"]}, {"total_eligible_minutes": 45}, {"affected": True},
                                   {"account": None}, {"month": None}, {"currency": "usd"}, {"month": "2026-13"},
                                   {"gaps": [{"ref": "g-1", "start": "2026-10-02T00:00:00Z"}]}])
def test_invented_obligation_legacy_fields_and_null_identity_are_refused(extra):
    with pytest.raises(ValidationError):
        Delivery.model_validate_json(wire("monthly_coverage", **extra))


def test_repeated_identity_is_checked_by_the_existing_signed_grant_scope():
    scope = Scope(**WHOLE)
    matching = Delivery.model_validate_json(wire("monthly_coverage", **WHOLE))
    assert event_in_scope(matching, "status", scope)
    assert not event_in_scope(matching, "customer", scope)  # wrong role for the record kind
    for field, other in [("account", "north-613"), ("vendor", "Other Relay"), ("contract", "BR-75"),
                         ("service", "Message Queue"), ("month", "2026-09"), ("currency", "EUR")]:
        foreign = Delivery.model_validate_json(wire("monthly_attribution", **{field: other}))
        assert not event_in_scope(foreign, "customer", scope), field


def test_legacy_record_types_and_roles_are_unchanged():
    assert {k: SOURCE[k] for k in ("status", "coverage", "impact", "component", "notice", "invoice")} == dict(
        status="status", coverage="status", impact="customer", component="customer", notice="customer", invoice="billing")
    assert set(SOURCE.values()) == {"status", "customer", "billing", "vendor"}
    with pytest.raises(ValidationError):  # legacy coverage still names its single incident
        Coverage.model_validate(dict(kind="coverage", start="2026-10-01T00:00:00Z", end="2026-11-01T00:00:00Z",
                                     complete=True, exclusions_removed=True, incident_ids=[], total_eligible_minutes=0))
