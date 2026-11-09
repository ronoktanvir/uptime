"""Decision 89: identity (D03-A, implemented) and claim scope (D04) invariants.

D03-A was confirmed by the team on 2026-11-09: account and agreement identities
are bounded exact source values, refused rather than rewritten, in one domain
shared by onboarding, claim intake, signed evidence, the claim registry and the
ledger. Earlier characterization tests that pinned the defect were replaced by
these invariants; docs/v4/TEST-CHANGES-89.md names each replacement.
"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sqlite3

import pytest
from pydantic import TypeAdapter, ValidationError

from fixtures.northwind.loader import build_fee_registry, load_package
from test_allocation_ledger import bill
from uptime import claim_identity
from uptime.allocations import AllocationLedger
from uptime.contracts import fingerprint
from uptime.correspondence_types import Claim, IssuedCredit, Line, MaintenanceRecord, MonitorRow, Scope
from uptime.governing_fees import authenticated_invoice_snapshot
from uptime.ramp_terms_store import Ref
from uptime.source_identity import SourceIdentity, refusal
from uptime.vendor_eval import FACT_FIELDS, evaluate
from uptime.vendor_terms import Overlay, bind_overlay

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / "docs/v4/evidence/pause-20261106"
SAMPLES = ["harborline-001", "Cedar Orrery Studio", "Talus Signal Availability Agreement", "Acme, Inc.",
           "O'Neil & Sons (US)", "Plan+Plus", "acct:42/eu", "Café Nord", "東京 Analytics", "x", "a" * 96,
           "Harborline ", " Harborline", "Harborline  Analytics", "Cafe\u0301 Nord", "Agreement \u2014 2026",
           "Acme #4", "a" * 97, "Tab\tName", "No\u00a0Break", "()"]


def _accepts(check, value):
    try:
        check(value)
    except (ValueError, ValidationError):
        return False
    return True


def _field(model, name):
    return TypeAdapter(model.model_fields[name].rebuild_annotation()).validate_python


def _reserve(account, agreement="Talus Signal Availability Agreement", *, month="2033-10", case="case-1",
             receipt="receipt-1", db=None):
    db = db or sqlite3.connect(":memory:")
    if not db.in_transaction:
        db.execute("BEGIN")
    identity = dict(tenant="bears", vendor="Talus Signal", account=account, agreement_id=agreement,
                    agreement_version="v1", service="Event Relay", month=month, remedy="availability")
    return db, claim_identity.reserve_claim(db, **identity, route="correspondence", case_id=case, packet_digest="a" * 64,
                                            scope={"account": account, "month": month}, receipt_id=receipt,
                                            at="2033-11-02T00:00:00+00:00")


def _onboard_account(value):
    package = load_package()
    bind_overlay(package["manifest"], Overlay(**package["overlay"] | {"account": value}))


def _onboard_agreement(value):
    package = load_package()
    bind_overlay(package["manifest"] | {"agreement": value}, Overlay(**package["overlay"] | {"agreement": value}))


def _ledger_account(value):
    import tempfile
    directory = Path(tempfile.mkdtemp())
    try:
        AllocationLedger(directory / "ledger.db").record_bill("tenant", bill(account_id=value, contract_id=value))
    finally:
        for child in directory.iterdir():
            child.unlink()
        directory.rmdir()


CHECKS = {
    "onboarding_account": _onboard_account,
    "onboarding_agreement": _onboard_agreement,
    "claim_scope_account": _field(Scope, "account"),
    "claim_scope_contract": _field(Scope, "contract"),
    "signed_line_account": _field(Line, "account"),
    "signed_line_contract": _field(Line, "contract"),
    "monitor_row_account": _field(MonitorRow, "account"),
    "maintenance_account": _field(MaintenanceRecord, "account"),
    "issued_credit_account": _field(IssuedCredit, "account"),
    "issued_credit_agreement": _field(IssuedCredit, "agreement"),
    "new_filing_account": lambda v: _reserve(v),
    "ledger_account_and_contract": _ledger_account,
}


@pytest.mark.parametrize("value", SAMPLES)
def test_every_account_and_agreement_entry_point_applies_the_same_bounded_rule(value):
    expected = refusal(value) is None
    assert {name: _accepts(check, value) for name, check in CHECKS.items()} == {name: expected for name in CHECKS}


@pytest.mark.parametrize("value", SAMPLES)
def test_ramp_terms_agreement_accepts_the_shared_rule_and_keeps_legacy_references(value):
    legacy = _accepts(TypeAdapter(Ref).validate_python, value)
    assert _accepts(TypeAdapter(Ref | SourceIdentity).validate_python, value) == (refusal(value) is None or legacy)


def test_accepted_identities_are_never_rewritten():
    for value in [v for v in SAMPLES if refusal(v) is None]:
        assert Scope.model_fields["account"] and _field(Scope, "account")(value) == value
        bound = bind_overlay(load_package()["manifest"], Overlay(**load_package()["overlay"] | {"account": value}))
        assert bound["account"].encode() == value.encode()


def test_recorded_requests_no_longer_refuse_their_exact_source_identities():
    """The preserved e86 bodies stay immutable; only their identity refusals disappear under D03-A."""
    for receipt in ("e86-01", "e86-04"):
        recorded = json.loads((RECEIPTS / f"{receipt}.json").read_text())
        assert {tuple(e["loc"]) for e in recorded["response"]["detail"]} >= {("body", "scope", "account"), ("body", "scope", "contract")}
        try:
            Claim.model_validate(recorded["request"])
            errors = []
        except ValidationError as error:
            errors = error.errors()
        assert not [e for e in errors if e["loc"][-1] in ("account", "contract")]


def _northwind_with_account(account):
    package = deepcopy(load_package())
    package["overlay"]["account"] = account
    for row in package["months"]:
        row["facts"]["account"] = account
        row["scope"]["account"] = account
    package["settlement"]["scope"]["account"] = account
    return package


def _january(package):
    row = package["months"][0]
    body = {"kind": "invoice", "lines": [{"id": line.id, "kind": "affected_api", "amount": str(line.net)}
                                         for line in row["invoice"].lines]}
    event = dict(source="billing", kind="invoice", body=body, digest=fingerprint(body), subject="scripted-financial-source",
                 source_key_id="unit-test-key", source_grant_id="unit-test-grant", received_at=row["facts"]["received_at"])
    snapshot = authenticated_invoice_snapshot(package["tenant"], Scope(**row["scope"]), event)
    context = build_fee_registry(package).resolve(snapshot, as_of=datetime.fromisoformat(row["facts"]["received_at"]))
    overlay = bind_overlay(package["manifest"], Overlay(**package["overlay"]))
    return evaluate(package["manifest"], overlay, row["facts"], package["tenant"], governing_fee=context)


def test_spaced_source_account_keeps_the_same_northwind_economics():
    authored = _january(load_package())
    spaced = _january(_northwind_with_account("Harborline Analytics"))
    assert (authored["outcome"], authored["amount"]) == ("ELIGIBLE", "2400.00")
    assert {k: spaced[k] for k in ("outcome", "amount", "rate_units", "completed_steps", "governing_fee_cents")} == {
        k: authored[k] for k in ("outcome", "amount", "rate_units", "completed_steps", "governing_fee_cents")}
    package = _northwind_with_account("Harborline Analytics")
    identity = claim_identity.vendor_economic_identity(package["tenant"], package["manifest"],
                                                       bind_overlay(package["manifest"], Overlay(**package["overlay"])),
                                                       "2026-01", "order-v1")
    assert identity["account"] == "Harborline Analytics"


def test_another_accounts_fee_context_is_still_never_borrowed():
    package = load_package()
    row = package["months"][0]
    body = {"kind": "invoice", "lines": [{"id": line.id, "kind": "affected_api", "amount": str(line.net)} for line in row["invoice"].lines]}
    event = dict(source="billing", kind="invoice", body=body, digest=fingerprint(body), subject="scripted-financial-source",
                 source_key_id="unit-test-key", source_grant_id="unit-test-grant", received_at=row["facts"]["received_at"])
    context = build_fee_registry(package).resolve(authenticated_invoice_snapshot(package["tenant"], Scope(**row["scope"]), event),
                                                  as_of=datetime.fromisoformat(row["facts"]["received_at"]))
    spaced = _northwind_with_account("Harborline Analytics")
    overlay = bind_overlay(spaced["manifest"], Overlay(**spaced["overlay"]))
    result = evaluate(spaced["manifest"], overlay, spaced["months"][0]["facts"], spaced["tenant"], governing_fee=context)
    assert (result["outcome"], result["missing"], result["amount"]) == ("INSUFFICIENT_EVIDENCE", ["governing_fee_context"], None)


@pytest.mark.parametrize("value", ["harborline-001 ", " harborline-001", "harborline  001", "harborline\t001"])
def test_padded_or_irregular_accounts_are_refused_at_onboarding_intake_and_filing(value):
    with pytest.raises(ValueError):
        _onboard_account(value)
    with pytest.raises(ValidationError):
        Scope(**load_package()["months"][0]["scope"] | {"account": value})
    with pytest.raises(ValueError):
        _reserve(value)


# Near-duplicate guard (D03-A; refused, no override path) --------------------------

@pytest.mark.parametrize("account,agreement", [
    ("CEDAR ORRERY STUDIO", "Talus Signal Availability Agreement"),
    ("CedarOrrery Studio", "Talus Signal Availability Agreement"),
    ("Cedar Orrery Studio", "talus signal availability agreement"),
    ("cedar orrery studio", "TalusSignal Availability Agreement"),
])
def test_case_or_spacing_variant_cannot_file_the_same_obligation_twice(account, agreement):
    db, first = _reserve("Cedar Orrery Studio")
    assert first["created"]
    with pytest.raises(claim_identity.NearDuplicateIdentity, match="No override is available"):
        _reserve(account, agreement, case="case-2", receipt="receipt-2", db=db)
    assert db.execute(f"SELECT count(*) FROM {claim_identity.TABLE}").fetchone()[0] == 1


@pytest.mark.parametrize("changes", [dict(month="2033-11"), dict(account="Cedar Orrery Studios"), dict(agreement="Talus Signal SLA")])
def test_distinct_obligations_and_exact_retries_are_not_blocked(changes):
    db, first = _reserve("Cedar Orrery Studio")
    retry = _reserve("Cedar Orrery Studio", db=db)[1]
    assert retry["created"] is False and retry["obligation"] == first["obligation"]
    arguments = dict(account="Cedar Orrery Studio", agreement="Talus Signal Availability Agreement") | changes
    other = _reserve(arguments.pop("account"), arguments.pop("agreement"), case="case-2", receipt="receipt-2", db=db, **arguments)[1]
    assert other["created"] and other["obligation"] != first["obligation"]


SCOPE_FIELDS = {"account", "vendor", "contract", "service", "component", "invoice", "incident", "currency", "month", "region"}


def test_claim_scope_requires_every_field_for_every_obligation_family():
    assert set(Scope.model_fields) == SCOPE_FIELDS
    assert all(field.is_required() for field in Scope.model_fields.values())


@pytest.mark.parametrize("receipt,missing", [
    ("e86-01", {"component", "incident", "region"}),  # whole-service monthly claim
    ("e86-04", {"invoice", "incident", "region"}),  # resource-month claim
])
def test_recorded_scopes_lack_fields_their_obligation_may_not_need(receipt, missing):
    request = json.loads((RECEIPTS / f"{receipt}.json").read_text())["request"]
    with pytest.raises(ValidationError) as caught:
        Scope(**request["scope"])
    assert {e["loc"][0] for e in caught.value.errors() if e["type"] == "missing"} == missing


def test_northwind_whole_service_scope_carries_authored_values_the_evaluator_never_reads():
    package = load_package()
    assert package["manifest"]["family"] == "monthly-availability/1"
    assert not {"component", "incident", "region"} & FACT_FIELDS
    for row in package["months"]:
        # Authored placeholders satisfy the universal Scope; they are not inputs to the monthly obligation.
        assert all(row["scope"][field] for field in ("component", "incident", "region"))
        assert not {"component", "incident", "region"} & set(row["facts"])
