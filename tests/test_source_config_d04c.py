"""W5 (gen5-approved) hunk for D04-C: event_in_scope maps resource_id only when the scope has a component.

(a) A component-less scope admits nested rows naming any resource, but still refuses a wrong
    account, month or currency in a row and a record outside the granted month.
(b) A legacy ten-field scope behaves as before (the existing
    tests/test_source_config_v4.py::test_grant_validates_every_nested_resource_and_invoice_line is unchanged).
(c) A component record is refused for a component-less scope.
"""
import pytest

from uptime.correspondence_types import Delivery, Scope
from uptime.source_config import event_in_scope

LEGACY = dict(account="acct-1", vendor="Talus Signal", contract="TS-1", service="Event Relay", component="relay-1",
              invoice="INV-1", incident="INC-1", currency="USD", month="2026-10", region="us-east")
COMPONENTLESS = {k: v for k, v in LEGACY.items() if k not in ("component", "region")}
WINDOW = {"start": "2026-10-08T01:00:00Z", "end": "2026-10-08T02:00:00Z"}
REPORT = {"source_ref": "report", "observed_at": "2026-10-31T23:59:59Z"}


def _in_scope(scope, role, body):
    return event_in_scope(Delivery(event_id="event-rows", scope=Scope(**scope), body=body), role, Scope(**scope))


def _telemetry(**row):
    base = {**WINDOW, "ref": "row-1", "account": "acct-1", "product": "Event Relay", "region": "us-east",
            "resource_id": "station-9", "status": "down"}
    return {"kind": "customer_telemetry", **WINDOW, **REPORT, "source_id": "monitor-1", "complete": True,
            "records": [base | row]}


def _invoice(**line):
    base = {"ref": "line-1", "resource_id": "station-9", "month": "2026-10", "currency": "USD",
            "kind": "resource_service", "amount_cents": 10}
    return {"kind": "resource_invoice", **REPORT, "itemized_complete": True, "lines": [base | line]}


def test_w5_componentless_scope_admits_rows_naming_any_resource():
    assert _in_scope(COMPONENTLESS, "customer", _telemetry())
    assert _in_scope(COMPONENTLESS, "customer", _telemetry(resource_id="station-10"))
    assert _in_scope(COMPONENTLESS, "billing", _invoice(resource_id="anything-else"))


@pytest.mark.parametrize("role,body", [
    ("customer", _telemetry(account="acct-2")),
    ("customer", _telemetry(product="Other Product")),
    ("billing", _invoice(month="2026-09")),
    ("billing", _invoice(currency="EUR")),
])
def test_w5_componentless_scope_still_refuses_wrong_identity_month_or_currency(role, body):
    assert not _in_scope(COMPONENTLESS, role, body)


def test_w5_componentless_scope_still_refuses_a_record_outside_the_granted_month():
    outside = _telemetry()
    outside.update(start="2026-09-08T01:00:00Z", end="2026-09-08T02:00:00Z")
    outside["records"][0].update(start="2026-09-08T01:00:00Z", end="2026-09-08T02:00:00Z")
    assert not _in_scope(COMPONENTLESS, "customer", outside)


def test_w5_legacy_ten_field_scope_still_compares_resource_rows():
    assert not _in_scope(LEGACY, "billing", _invoice(resource_id="station-9"))
    assert _in_scope(LEGACY, "billing", _invoice(resource_id="relay-1"))


def test_w5_component_record_is_refused_for_a_componentless_scope():
    body = {"kind": "component", **WINDOW, "component_id": "relay-1"}
    assert _in_scope(LEGACY, "customer", body)
    assert not _in_scope(COMPONENTLESS, "customer", body)
