"""D04 option C (2026-11-09): server-side claim scope family table, "monthly keeps incident".

Required obligation fields must be present, not-applicable ones absent; invoice is an
optional evidence reference; unknown or ambiguous families refuse with a distinct
InvalidClaimScope; stored ten-field scopes serialize byte-identically.
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from uptime import claim_scope
from uptime.claim_scope import (IncidentScope, InvalidClaimScope, ResourcePeriodScope, ServiceMonthScope,
                                VERSION, admit, resolve, variant_for)
from uptime.contracts import fingerprint
from uptime.correspondence_types import Claim, Scope

ROOT = Path(__file__).resolve().parents[1]
FULL = dict(account="acct-1", vendor="Talus Signal", contract="TS-1", service="Event Relay", component="relay-1",
            invoice="INV-1", incident="INC-1", currency="USD", month="2033-10", region="us-east")
BASE = {k: v for k, v in FULL.items() if k not in ("component", "invoice", "incident", "region")}
TWILIO = BASE | dict(vendor="Twilio", service="Twilio Messaging API", contract="twilio-apis")


def test_table_is_versioned_and_monthly_keeps_incident():
    assert VERSION == "claim-scope/1"
    monthly = variant_for({"family": "monthly-availability/1"}, {})
    assert type(monthly) is IncidentScope and monthly.required == {"incident"}


@pytest.mark.parametrize("fields,label,required", [
    ([], None, {"component", "region"}),
    (["incident_number"], {"incident_number": {"phrase": "the outage ticket number"}}, {"component", "region", "incident"}),
])
def test_resource_period_requires_resource_region_and_any_cited_incident(fields, label, required):
    manifest = {"family": "resource-month/1", "request_fields": fields, "label_bindings": {"request_fields": label or {}}}
    variant = variant_for(manifest, {"resource_label": "station"})
    assert type(variant) is ResourcePeriodScope and variant.required == required


@pytest.mark.parametrize("fields,required", [([], set()), (["region"], {"region"}), (["station id"], {"component"})])
def test_service_month_requires_only_what_its_filing_cites(fields, required):
    variant = variant_for({"family": "resource-month/1", "aggregate_monitor": True, "request_fields": fields},
                          {"resource_label": "station"})
    assert type(variant) is ServiceMonthScope and variant.required == required


def test_unsupported_family_is_refused():
    with pytest.raises(InvalidClaimScope):
        variant_for({"family": "rebate/1"}, {})


def test_absent_fields_are_not_serialized_and_ten_field_scopes_are_byte_identical():
    full = Scope(**FULL)
    assert full.model_dump() == FULL and json.loads(full.model_dump_json()) == FULL
    assert fingerprint(full.model_dump()) == fingerprint(FULL)
    partial = Scope(**BASE | {"incident": "INC-1"})
    assert partial.model_dump() == BASE | {"incident": "INC-1"}
    assert "null" not in partial.model_dump_json() and partial.component is None
    assert Scope.model_validate_json(partial.model_dump_json()) == partial


@pytest.mark.parametrize("field", ["component", "incident", "region", "invoice"])
def test_explicit_null_is_refused_so_absent_stays_distinct(field):
    with pytest.raises(ValidationError):
        Scope(**BASE | {field: None})
    with pytest.raises(ValidationError):
        Claim.model_validate({"claim_id": "inbox-x", "scope": BASE | {field: None}})


def test_required_fields_still_required():
    for field in ("account", "vendor", "contract", "service", "currency", "month"):
        with pytest.raises(ValidationError):
            Scope(**{k: v for k, v in FULL.items() if k != field})


def test_variant_check_refuses_missing_required_and_present_not_applicable():
    incident = IncidentScope("monthly-availability/1", frozenset({"incident"}))
    assert incident.check(Scope(**BASE | {"incident": "INC-1", "invoice": "INV-1"})) is incident
    with pytest.raises(InvalidClaimScope, match="requires incident"):
        incident.check(Scope(**BASE))
    with pytest.raises(InvalidClaimScope, match="component, region not applicable"):
        incident.check(Scope(**FULL))
    service = ServiceMonthScope("resource-month/1/service-month", frozenset())
    assert service.check(Scope(**BASE)) is service
    with pytest.raises(InvalidClaimScope, match="incident not applicable"):
        service.check(Scope(**BASE | {"incident": "INC-invented"}))
    assert not issubclass(InvalidClaimScope, KeyError) and issubclass(InvalidClaimScope, ValueError)


def test_builtin_twilio_profile_is_one_table_entry():
    variant = resolve(_no_tables(), "bears", Scope(**TWILIO | {"incident": "INC-1", "component": "api"}))
    assert type(variant) is IncidentScope and variant.builtin and variant.required == {"incident", "component"}
    with pytest.raises(InvalidClaimScope, match="region not applicable"):
        admit(_no_tables(), "bears", Scope(**TWILIO | {"incident": "INC-1", "component": "api", "region": "us1"}))
    with pytest.raises(InvalidClaimScope, match="requires component"):
        admit(_no_tables(), "bears", Scope(**TWILIO | {"incident": "INC-1"}))


def test_unknown_and_ambiguous_families_are_refused(monkeypatch):
    with pytest.raises(InvalidClaimScope, match="unknown family"):
        resolve(_no_tables(), "bears", Scope(**BASE))
    monkeypatch.setattr(claim_scope, "_installed", lambda db, tenant, scope: [
        {"manifest": {"family": "monthly-availability/1"}, "overlay": {}},
        {"manifest": {"family": "resource-month/1", "aggregate_monitor": True}, "overlay": {}}])
    with pytest.raises(InvalidClaimScope, match="ambiguous"):
        resolve(_no_tables(), "bears", Scope(**BASE))
    monkeypatch.setattr(claim_scope, "_installed", lambda db, tenant, scope: [
        {"manifest": {"family": "monthly-availability/1"}, "overlay": {}}])
    with pytest.raises(InvalidClaimScope, match="ambiguous"):
        resolve(_no_tables(), "bears", Scope(**TWILIO | {"incident": "INC-1"}))


def _no_tables():
    import sqlite3
    return sqlite3.connect(":memory:")
