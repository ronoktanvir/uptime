"""Decision 89: reproduction of the identity-domain (D03) and universal-scope (D04) defects.

These are characterization tests. They pin today's observed behaviour, including
the defect, so that the team-chosen repair changes it deliberately and records
each changed expectation in docs/v4/TEST-CHANGES-89.md. They do not assert any
post-decision representation: D03 and D04 are pending team decisions.
"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from fixtures.northwind.loader import build_fee_registry, load_package
from uptime import claim_identity, disputes_wire, pricing, ramp_terms_store, reconciliation, vendor_terms
from uptime.contracts import fingerprint
from uptime.correspondence_types import Claim, Id, Name, Scope
from uptime.governing_fees import authenticated_invoice_snapshot
from uptime.vendor_eval import FACT_FIELDS, evaluate
from uptime.vendor_terms import Overlay, bind_overlay

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / "docs/v4/evidence/pause-20261106"


def _accepts(check, value):
    try:
        result = check(value)
    except (ValueError, ValidationError):
        return False
    return result is not None and result is not False


# Every validator that currently decides whether an exact source identity is usable.
DOMAINS = {
    "onboarding_overlay": lambda v: vendor_terms._match(vendor_terms.NAME, v),
    "claim_scope_id": TypeAdapter(Id).validate_python,
    "claim_scope_name": TypeAdapter(Name).validate_python,
    "claim_key": claim_identity._identity,
    "pricing": pricing._canonical,
    "ramp_terms_ref": TypeAdapter(ramp_terms_store.Ref).validate_python,
    "dispute_wire": disputes_wire.canonical,
    "reconciliation": lambda v: reconciliation._required({"field": v}, "field"),
}

# Observed on 03b372e. Columns follow DOMAINS order. 1 accepts, 0 refuses.
OBSERVED = {
    "harborline-001": (1, 1, 1, 1, 1, 1, 1, 1),
    "Cedar Orrery Studio": (1, 0, 1, 1, 1, 0, 1, 1),
    "Talus Signal Availability Agreement": (1, 0, 1, 1, 1, 0, 1, 1),
    "Acme, Inc.": (1, 0, 0, 1, 1, 0, 1, 1),
    "O'Neil & Sons (US)": (1, 0, 0, 1, 1, 0, 1, 1),
    "Plan+Plus": (1, 0, 0, 1, 1, 0, 1, 1),
    "acct:42/eu": (0, 1, 0, 1, 1, 1, 1, 1),
    "Harborline ": (1, 0, 0, 0, 0, 0, 0, 0),
    "Harborline  Analytics": (1, 0, 1, 1, 1, 0, 1, 1),
    " Harborline": (0, 0, 0, 0, 0, 0, 0, 0),
    "Café Nord": (0, 0, 0, 1, 1, 0, 1, 1),
    "a" * 97: (1, 0, 0, 1, 1, 1, 1, 1),
    "a" * 101: (0, 0, 0, 1, 1, 1, 1, 1),
    "Tab\tName": (0, 0, 0, 0, 0, 0, 0, 0),
}


@pytest.mark.parametrize("value", sorted(OBSERVED))
def test_identity_validators_disagree_on_exact_source_values(value):
    actual = tuple(int(_accepts(check, value)) for check in DOMAINS.values())
    assert actual == OBSERVED[value]


def test_onboarding_accepts_identities_that_claim_intake_or_claim_key_cannot_represent():
    columns = list(DOMAINS)
    onboarding, scope_id, key = (columns.index(n) for n in ("onboarding_overlay", "claim_scope_id", "claim_key"))
    stranded_at_intake = {v for v, row in OBSERVED.items() if row[onboarding] and not row[scope_id]}
    stranded_at_key = {v for v, row in OBSERVED.items() if row[onboarding] and not row[key]}
    assert {"Cedar Orrery Studio", "Talus Signal Availability Agreement", "Acme, Inc."} <= stranded_at_intake
    # A trailing space passes onboarding but cannot form an economic claim key.
    assert stranded_at_key == {"Harborline "}
    # Nothing here trims, folds or slugs a value into an apparently valid identity.
    assert not _accepts(DOMAINS["claim_scope_id"], "Cedar-Orrery-Studio".replace("-", " "))


@pytest.mark.parametrize("receipt", ["e86-01", "e86-04"])
def test_recorded_claim_intake_refusals_reproduce_on_current_source(receipt):
    """The exact preserved request bytes still produce the preserved 422 detail."""
    recorded = json.loads((RECEIPTS / f"{receipt}.json").read_text())
    assert recorded["route"] == "/api/correspondence/claims"
    with pytest.raises(ValidationError) as caught:
        Claim.model_validate(recorded["request"])
    actual = sorted((e["type"], ("body", *e["loc"])) for e in caught.value.errors())
    expected = sorted((e["type"], tuple(e["loc"])) for e in recorded["response"]["detail"])
    assert actual == expected


def _northwind_january(package, *, account=None):
    overlay = dict(package["overlay"], **({"account": account} if account else {}))
    row = deepcopy(package["months"][0])
    facts = dict(row["facts"], **({"account": account} if account else {}))
    scope = dict(row["scope"], **({"account": account} if account else {}))
    return overlay, row, facts, scope


def _january_context(package):
    row = package["months"][0]
    body = {"kind": "invoice", "lines": [{"id": line.id, "kind": "affected_api", "amount": str(line.net)}
                                         for line in row["invoice"].lines]}
    event = dict(source="billing", kind="invoice", body=body, digest=fingerprint(body), subject="scripted-financial-source",
                 source_key_id="unit-test-key", source_grant_id="unit-test-grant", received_at=row["facts"]["received_at"])
    snapshot = authenticated_invoice_snapshot(package["tenant"], Scope(**row["scope"]), event)
    return build_fee_registry(package).resolve(snapshot, as_of=datetime.fromisoformat(row["facts"]["received_at"]))


def test_spaced_onboarded_account_is_stranded_before_claim_and_governing_fee():
    package = load_package()
    tenant, manifest = package["tenant"], package["manifest"]
    context = _january_context(package)

    _, _, facts, _ = _northwind_january(package)
    baseline = evaluate(manifest, bind_overlay(manifest, Overlay(**package["overlay"])), facts, tenant, governing_fee=context)
    assert (baseline["outcome"], baseline["amount"]) == ("ELIGIBLE", "2400.00")

    overlay, _, facts, scope = _northwind_january(package, account="Harborline Analytics")
    bound = bind_overlay(manifest, Overlay(**overlay))  # onboarding accepts the exact source value
    assert bound["account"] == "Harborline Analytics"
    identity = claim_identity.vendor_economic_identity(tenant, manifest, bound, "2026-01", "order-v1")
    assert identity["account"] == "Harborline Analytics"  # the economic claim key also accepts it

    with pytest.raises(ValidationError) as caught:  # signed claim intake and FeeEntry cannot
        Scope(**scope)
    assert [e["loc"] for e in caught.value.errors()] == [("account",)]

    # The only governing-fee authority belongs to another account; it must not be borrowed.
    stranded = evaluate(manifest, bound, facts, tenant, governing_fee=context)
    assert stranded["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert stranded["missing"] == ["governing_fee_context"] and stranded["amount"] is None


def test_trailing_space_account_passes_onboarding_but_not_economic_identity():
    package = load_package()
    overlay, *_ = _northwind_january(package, account="harborline-001 ")
    bound = bind_overlay(package["manifest"], Overlay(**overlay))
    assert bound["account"] == "harborline-001 "  # not trimmed
    with pytest.raises(ValueError, match="Canonical nonempty identity required"):
        claim_identity.vendor_economic_identity(package["tenant"], package["manifest"], bound, "2026-01", "order-v1")


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
