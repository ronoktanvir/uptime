"""Synthetic, credential-free inputs only; no observed/customer fixture reads."""
import copy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hypothesis import given, strategies as st
import pytest

from uptime.ramp_cap import (InvoiceCapRefusal, InvoiceCapScope, evaluate_invoice_cap,
                             make_synthetic_binding, sign_synthetic_binding)


AT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
TERMS = json.loads((Path(__file__).resolve().parents[1]
                   / "fixtures/ramp/native-cap-terms.json").read_text())


def seal(snapshot):
    raw = {k: v for k, v in snapshot.items() if k not in {"checksum", "snapshot_status"}}
    snapshot["checksum"] = sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"),
                                              allow_nan=False).encode()).hexdigest()
    return snapshot


def amount(cents):
    return {"amount": f"{cents // 100}.{cents % 100:02d}", "currency": "USD",
            "amount_minor": cents, "minor_unit_conversion_rate": 100}


def capture(cents=84000):
    row = {"id": str(uuid4()), "kind": "bill", "vendor_id": str(uuid4()),
           "entity_id": str(uuid4()), "issued_at": "2026-11-01T10:00:00+00:00",
           "status": "OPEN", "approval_status": "PENDING", "archived_at": None,
           "amount": amount(cents), "sources": ["LIVE_RAMP_SANDBOX"], "lines": [],
           "applied_credits": None, "purchase_order_id": None, "deep_link_url": None}
    resources = {name: {"status": "NOT_REQUESTED", "records": [], "complete": False,
                        "grant": None, "issues": [], "coverage": {}}
                 for name in ("bills", "vendors", "transactions", "agreements",
                              "purchase_orders", "credits", "approvals", "comments")}
    resources["bills"].update(status="COMPLETE", complete=True, records=[row], grant={
        "requested": ["bills:read"], "granted": ["bills:read"], "missing": [],
        "unexpected": [], "scope_reported": True, "diagnosis": "EXACT_GRANT", "state": "GRANTED"})
    snapshot = seal({"schema": "uptime-ramp-records/1", "origin": "https://demo-api.ramp.com",
                     "observed_at": AT.isoformat(), "completed_at": AT.isoformat(),
                     "resources": resources})
    return snapshot, row


def scope_for(snapshot, row, terms=TERMS, **kwargs):
    key = Ed25519PrivateKey.generate()
    payload = make_synthetic_binding(snapshot, row["id"], tenant_id="test-tenant",
                                     operator_id="scripted-test-operator", terms=terms)
    return InvoiceCapScope("test-tenant", sign_synthetic_binding(payload, key),
                           {"scripted-test-operator": key.public_key()}, **kwargs)


def evaluate(snapshot, row, terms=TERMS, scope=None, at=AT):
    return evaluate_invoice_cap(snapshot, row, terms, as_of=at,
                                scope=scope if scope is not None else scope_for(snapshot, row, terms))


def test_840_over_800_is_only_hypothetical_and_deterministic():
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    before = copy.deepcopy((snapshot, row, TERMS, scope.binding))
    case = evaluate(snapshot, row, scope=scope)
    assert case == evaluate(snapshot, row, scope=scope)
    assert before == (snapshot, row, TERMS, scope.binding)
    assert case["kind"] == "case" and case["amount"] == "40.00"
    assert case["outcome"] == "ELIGIBLE" and case["stage"] == "SIMULATION_ONLY"
    assert case["sources"] == ["LIVE_RAMP_SANDBOX", "SYNTHETIC_CUSTOMER"]
    assert case["data_provenance"] == "MIXED" and not case["publishable"]
    assert case["actual_recovery"] is None and case["actual_money_prevented"] is None
    assert case["workflow_recommendation"]["real_financial_claim_allowed"] is False
    assert case["actions"] == [] and case["provider_uri"] is None
    assert case["native_amount"] == row["amount"]


def test_850_control_and_no_real_identifier_in_terms():
    snapshot, row = capture()
    control = copy.deepcopy(TERMS)
    control.update(terms_id="synthetic-gross-invoice-usd850-v1",
                   clause=TERMS["clause"].replace("800.00", "850.00"), cap=amount(85000))
    case = evaluate(snapshot, row, control)
    assert case["amount"] == "0.00" and case["outcome"] == "INELIGIBLE"
    assert row["id"] not in json.dumps(TERMS) and row["vendor_id"] not in json.dumps(TERMS)
    # A control must be separately pinned, not silently swapped into a binding.
    assert evaluate(snapshot, row, control, scope_for(snapshot, row))["reason"] == "BINDING_SCOPE_OR_CONTENT_MISMATCH"


@given(st.integers(min_value=0, max_value=10**24))
def test_generated_gross_values_have_exact_cents(cents):
    snapshot, row = capture(cents)
    case = evaluate(snapshot, row)
    delta = max(0, cents - 80000)
    assert case["kind"] == "case"
    assert case["amount"] == f"{delta // 100}.{delta % 100:02d}"
    assert case["outcome"] == ("ELIGIBLE" if delta else "INELIGIBLE")


@pytest.mark.parametrize("cents", [0, 79999, 80000, 80001, 84000, 85000])
def test_exact_cap_boundary(cents):
    snapshot, row = capture(cents)
    assert evaluate(snapshot, row)["hypothetical_discrepancy"] == amount(max(0, cents - 80000))["amount"]


def test_helper_requires_explicit_single_id_not_first_or_amount_search():
    snapshot, row = capture()
    other = copy.deepcopy(row)
    other["id"] = str(uuid4())
    snapshot["resources"]["bills"]["records"].insert(0, other)
    seal(snapshot)
    payload = make_synthetic_binding(snapshot, row["id"], tenant_id="test", operator_id="test")
    assert payload["bill_id"] == row["id"]
    assert "signature" not in payload
    assert "lines" not in payload and "amount" not in payload
    for missing in (None, "", str(uuid4())):
        with pytest.raises(InvoiceCapRefusal):
            make_synthetic_binding(snapshot, missing, tenant_id="test", operator_id="test")


@pytest.mark.parametrize("draft", [False, True])
def test_duplicate_ids_refused_even_if_different_kind(draft):
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    duplicate = copy.deepcopy(row)
    if draft:
        duplicate["kind"] = "draft"
    snapshot["resources"]["bills"]["records"].append(duplicate)
    seal(snapshot)
    assert evaluate(snapshot, row, scope=scope)["reason"] == "DUPLICATE_OR_AMBIGUOUS_BILL"


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("status", "PAID", "BILL_NOT_OPEN_PENDING"),
    ("status", "DRAFT", "BILL_NOT_OPEN_PENDING"),
    ("approval_status", "APPROVED", "BILL_NOT_OPEN_PENDING"),
    ("approval_status", "REJECTED", "BILL_NOT_OPEN_PENDING"),
    ("approval_status", None, "BILL_NOT_OPEN_PENDING"),
    ("kind", "draft", "NATIVE_BILL_REQUIRED"),
    ("archived_at", AT.isoformat(), "ARCHIVED_OR_UNKNOWN_BILL"),
    ("sources", ["SIMULATED_VENDOR"], "UNVERIFIED_BILL_PROVENANCE"),
])
def test_native_status_and_provenance_are_not_misclassified(field, value, reason):
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    row[field] = value
    seal(snapshot)
    result = evaluate(snapshot, row, scope=scope)
    assert result["reason"] == reason and result["amount"] is None
    with pytest.raises(InvoiceCapRefusal, match=reason):
        make_synthetic_binding(snapshot, row["id"], tenant_id="test", operator_id="test")


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("amount", "840.001", "RAW_SUBCENT_OR_INVALID_AMOUNT"),
    ("amount", "840.000", "RAW_SUBCENT_OR_INVALID_AMOUNT"),
    ("amount", "8.4e2", "RAW_SUBCENT_OR_INVALID_AMOUNT"),
    ("amount", 840.0, "RAW_SUBCENT_OR_INVALID_AMOUNT"),
    ("amount", "NaN", "RAW_SUBCENT_OR_INVALID_AMOUNT"),
    ("amount", "839.99", "AMOUNT_METADATA_MISMATCH"),
    ("amount_minor", 84000.1, "INVALID_MINOR_UNITS"),
    ("amount_minor", True, "INVALID_MINOR_UNITS"),
    ("amount_minor", -1, "INVALID_MINOR_UNITS"),
    ("minor_unit_conversion_rate", 1000, "INVALID_MINOR_UNITS"),
    ("currency", "EUR", "UNSUPPORTED_CURRENCY"),
])
def test_raw_money_and_metadata_mismatch_refused(field, value, reason):
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    row["amount"][field] = value
    seal(snapshot)
    assert evaluate(snapshot, row, scope=scope)["reason"] == reason


@given(st.integers(min_value=1, max_value=999))
def test_generated_raw_subcents_never_rounded(fraction):
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    row["amount"]["amount"] = "840." + f"{fraction:03d}"
    seal(snapshot)
    assert evaluate(snapshot, row, scope=scope)["reason"] == "RAW_SUBCENT_OR_INVALID_AMOUNT"


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("amount", "800.004", "RAW_SUBCENT_OR_INVALID_AMOUNT"),
    ("amount_minor", 80001, "AMOUNT_METADATA_MISMATCH"),
    ("minor_unit_conversion_rate", True, "INVALID_MINOR_UNITS"),
    ("currency", "EUR", "UNSUPPORTED_CURRENCY"),
])
def test_cap_money_is_as_strict_as_bill_money(field, value, reason):
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    terms = copy.deepcopy(TERMS)
    terms["cap"][field] = value
    assert evaluate(snapshot, row, terms, scope)["reason"] == reason


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("source", "REAL_CUSTOMER", "AUTHENTICATED_CUSTOMER_TERMS_REQUIRED"),
    ("real", True, "UNSUPPORTED_TERMS_SCHEMA"),
    ("basis", "SUBTOTAL_EXCLUDING_TAX", "AMBIGUOUS_TOTAL_BASIS"),
    ("date_basis", "USAGE_DATE", "UNSUPPORTED_DATE_BASIS"),
    ("superseded_by", "amendment-2", "AMENDED_OR_SUPERSEDED_TERMS"),
    ("supersedes", "earlier-version", "AMENDED_OR_SUPERSEDED_TERMS"),
    ("amendments", [{"cap": 90000}], "AMENDED_OR_SUPERSEDED_TERMS"),
    ("revision", 2, "AMENDED_OR_SUPERSEDED_TERMS"),
])
def test_unsupported_scope_and_terms_refuse(field, value, reason):
    snapshot, row = capture()
    terms = copy.deepcopy(TERMS)
    terms[field] = value
    assert evaluate(snapshot, row, terms, scope_for(snapshot, row))["reason"] == reason


def test_multiple_terms_are_ambiguous_and_real_flag_does_not_authorize():
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    assert evaluate(snapshot, row, [TERMS, TERMS], scope)["reason"] == "INVALID_TERMS"
    for source in ("LIVE_RAMP_SANDBOX", "VERIFIED_CUSTOMER", "REAL"):
        terms = {**TERMS, "source": source, "real": True}
        assert evaluate(snapshot, row, terms, scope)["reason"] == "AUTHENTICATED_CUSTOMER_TERMS_REQUIRED"


@pytest.mark.parametrize(("issued", "accepted"), [
    ("2026-01-01T00:00:00+00:00", True), ("2025-12-31T23:59:59+00:00", False),
    ("2026-12-31T23:59:59+00:00", True), ("2027-01-01T00:00:00+00:00", False),
    ("2025-12-31T16:00:00-08:00", True), ("2026-12-31T16:00:00-08:00", False),
])
def test_issued_date_effectivity_not_usage_date(issued, accepted):
    snapshot, row = capture()
    row["issued_at"] = issued
    row["lines"] = [{"service_date": "1999-01-01", "quantity": None, "unit_price": None}]
    seal(snapshot)
    if accepted:
        assert evaluate(snapshot, row)["kind"] == "case"
    else:
        with pytest.raises(InvoiceCapRefusal, match="OUTSIDE_ISSUED_DATE_TERM"):
            scope_for(snapshot, row)


@pytest.mark.parametrize(("age", "reason"), [
    (timedelta(days=1, microseconds=1), "STALE_SNAPSHOT"),
    (timedelta(seconds=-1), "FUTURE_OR_REVERSED_CAPTURE"),
])
def test_freshness(age, reason):
    snapshot, row = capture()
    assert evaluate(snapshot, row, at=AT + age)["reason"] == reason


def test_freshness_boundary_and_timezone():
    snapshot, row = capture()
    assert evaluate(snapshot, row, at=AT + timedelta(days=1))["kind"] == "case"
    assert evaluate(snapshot, row, at=AT.replace(tzinfo=None))["reason"] == "INVALID_AS_OF"
    snapshot["snapshot_status"] = {"freshness": "FRESH", "integrity": "CHECKSUM_VERIFIED"}
    assert evaluate(snapshot, row, at=AT + timedelta(days=2))["reason"] == "STALE_SNAPSHOT"


@pytest.mark.parametrize("field", ["vendor_id", "entity_id", "issued_at", "amount", "lines"])
def test_resealed_row_changes_require_new_binding(field):
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    row[field] = {"vendor_id": str(uuid4()), "entity_id": str(uuid4()),
                  "issued_at": "2026-11-02T10:00:00+00:00", "amount": amount(84001),
                  "lines": [{"kind": "expense"}]}[field]
    seal(snapshot)
    assert evaluate(snapshot, row, scope=scope)["reason"] == "BINDING_SCOPE_OR_CONTENT_MISMATCH"


def test_snapshot_checksum_detached_row_and_recapture():
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    detached = copy.deepcopy(row)
    detached["amount"] = amount(1)
    assert evaluate(snapshot, detached, scope=scope)["reason"] == "BILL_CONTENT_MISMATCH"
    snapshot["completed_at"] = (AT + timedelta(seconds=1)).isoformat()
    assert evaluate(snapshot, row, scope=scope)["reason"] == "SNAPSHOT_CHECKSUM_MISMATCH"
    seal(snapshot)
    assert evaluate(snapshot, row, scope=scope, at=AT + timedelta(seconds=1))["reason"] == "BINDING_SCOPE_OR_CONTENT_MISMATCH"


@pytest.mark.parametrize("change", ["signature", "key", "tenant", "payload", "unsigned"])
def test_authentication_exact_tenant_and_signed_operands(change):
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    if change == "signature":
        scope.binding["signature"] = "00" * 64
    elif change == "key":
        scope.trusted_operator_keys.clear()
    elif change == "tenant":
        scope = InvoiceCapScope("different-tenant", scope.binding, scope.trusted_operator_keys)
    elif change == "payload":
        scope.binding["payload"]["bill_id"] = str(uuid4())
    else:
        scope = InvoiceCapScope(scope.tenant_id, scope.binding["payload"], scope.trusted_operator_keys)
    assert evaluate(snapshot, row, scope=scope)["kind"] == "refusal"


def test_duplicate_overlay_and_missing_overlay_refused():
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    for envelope in (None, [], [scope.binding, scope.binding]):
        invalid = InvoiceCapScope(scope.tenant_id, envelope, scope.trusted_operator_keys)
        assert evaluate(snapshot, row, scope=invalid)["reason"] == "SIGNED_BINDING_REQUIRED"


def test_evaluator_version_is_signed_and_cannot_be_changed():
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    assert scope.binding["payload"]["evaluator_version"] == "uptime-invoice-cap/1"
    assert evaluate(snapshot, row, scope=scope)["evaluator_version"] == "uptime-invoice-cap/1"
    scope.binding["payload"]["evaluator_version"] = "uptime-invoice-cap/2"
    assert evaluate(snapshot, row, scope=scope)["reason"] == "INVALID_BINDING_SIGNATURE"


@pytest.mark.parametrize(("field", "value"), [
    ("granted", []), ("granted", ["bills:read", "bills:write"]),
    ("requested", ["vendors:read"]), ("scope_reported", False),
    ("diagnosis", "UNEXPECTED_GRANTS"), ("state", "SCOPE_MISMATCH"),
])
def test_grant_is_part_of_atomic_capture(field, value):
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    snapshot["resources"]["bills"]["grant"][field] = value
    seal(snapshot)
    assert evaluate(snapshot, row, scope=scope)["reason"] == "EXACT_BILLS_GRANT_REQUIRED"


def test_same_grant_with_changed_receipt_requires_rebinding():
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    snapshot["resources"]["bills"]["grant"]["observed_at"] = AT.isoformat()
    seal(snapshot)
    assert evaluate(snapshot, row, scope=scope)["reason"] == "BINDING_SCOPE_OR_CONTENT_MISMATCH"


@pytest.mark.parametrize("status", ["PARTIAL", "TRUNCATED", "UNAVAILABLE", "EMPTY", "FORBIDDEN"])
def test_incomplete_resource_never_becomes_financial_finding(status):
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    snapshot["resources"]["bills"].update(status=status, complete=False)
    seal(snapshot)
    assert evaluate(snapshot, row, scope=scope)["reason"] == "INCOMPLETE_BILL_CAPTURE"


def test_no_raw_private_values_in_refusal():
    snapshot, row = capture()
    scope = scope_for(snapshot, row)
    row["vendor_id"] = "PRIVATE_IDENTIFIER"
    seal(snapshot)
    result = evaluate(snapshot, row, scope=scope)
    assert result["kind"] == "refusal" and "PRIVATE" not in json.dumps(result)


def test_default_helper_pins_packaged_terms():
    snapshot, row = capture()
    default = make_synthetic_binding(snapshot, row["id"], tenant_id="test", operator_id="test")
    explicit = make_synthetic_binding(snapshot, row["id"], tenant_id="test", operator_id="test", terms=TERMS)
    assert default == explicit
