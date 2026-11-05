"""Synthetic local observations only; these tests do not read captured/customer data."""
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from uptime.contracts import Citation, fingerprint
from uptime.pricing import Agreement, ContractVersion, Rate, Tier
from uptime.ramp_findings import (
    PriceBinding, ServiceMapping, binding_digest, evaluate_snapshot, line_digest,
    _case, _context, _price, _workflow,
)

AT = datetime(2026, 11, 4, 12, tzinfo=UTC)
START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2026, 11, 1, tzinfo=UTC)
BILL, VENDOR, ENTITY, PO, LINE, POLINE, TX, AGREEMENT = (
    f"00000000-0000-4000-8000-{n:012d}" for n in range(1, 9))


def money(cents):
    return dict(amount=f"{Decimal(cents) / 100:.2f}", currency="USD", amount_minor=cents, minor_unit_conversion_rate=100)


def seal(snapshot):
    snapshot["checksum"] = fingerprint({k: v for k, v in snapshot.items() if k not in {"checksum", "snapshot_status"}})
    return snapshot


def observation():
    """Normalized test double; not an assertion of a live provider capture."""
    resources = {name: dict(status="EMPTY", records=[], complete=True, grant={}, issues=[], coverage={})
                 for name in ("bills", "vendors", "transactions", "agreements", "purchase_orders", "credits", "approvals", "comments")}
    rows = {
        "bills": [dict(id=BILL, kind="bill", vendor_id=VENDOR, entity_id=ENTITY, status="OPEN", approval_status="PENDING",
                       issued_at=AT.isoformat(), archived_at=None, amount=money(12000),
                       lines=[dict(id=LINE, amount=money(12000), purchase_order_line_item_id=POLINE)],
                       applied_credits=None, purchase_order_id=PO, deep_link_url=None)],
        "vendors": [dict(id=VENDOR, parent_vendor_id=None, status="ACTIVE")],
        "purchase_orders": [dict(id=PO, vendor_id=VENDOR, entity_id=ENTITY, status="OPEN", amount=money(10000),
                                 lines=[dict(id=POLINE, amount=money(10000), quantity="10", unit_price=money(1000),
                                             external_id="compute-unit", start_date="2026-10-01", end_date="2026-11-01")],
                                 bill_ids=[BILL], reciprocal_bill_ids=[BILL], ramp_url=None, discovery=["LINKED"])],
        "transactions": [dict(id=TX, vendor_id=None, entity_id=ENTITY, status="CLEARED", amount=money(-100), currency="USD")],
        "agreements": [dict(id=AGREEMENT, vendor_id=VENDOR, currency="USD", start_date="2026-01-01", end_date="2027-01-01")],
    }
    for resource, data in rows.items():
        resources[resource].update(status="COMPLETE", records=[dict(row, sources=["LIVE_RAMP_SANDBOX"]) for row in data])
    return seal(dict(schema="uptime-ramp-records/1", origin="https://demo-api.ramp.com",
                     observed_at=AT.isoformat(), completed_at=AT.isoformat(), resources=resources))


def binding(snapshot):
    bill = snapshot["resources"]["bills"]["records"][0]
    po = snapshot["resources"]["purchase_orders"]["records"][0]
    version = ContractVersion("v1", datetime(2026, 1, 1, tzinfo=UTC), datetime(2025, 12, 1, tzinfo=UTC),
                              (ENTITY, VENDOR), None, (Rate("compute-unit", "unit", (Tier(None, Decimal("8")),)),), (),
                              Citation("Fictional negotiated terms", "v1", "unit-cap", "fixture:terms/v1"))
    agreement = Agreement("test-negotiated", ENTITY, VENDOR, datetime(2027, 1, 1, tzinfo=UTC), (version,))
    mapping = ServiceMapping(LINE, line_digest(bill["lines"][0]), PO, POLINE, line_digest(po["lines"][0]),
                             "compute-unit", "unit", START, END, "fixture:reviewed-service", "a" * 64, True, True, "ATTESTED_FULL_PO_LINE")
    return PriceBinding("bills", BILL, snapshot["checksum"], "operator:test", agreement, (mapping,),
                        terms_evidence_ref="fixture:terms", terms_evidence_digest="b" * 64)


def direct(snapshot, bound=None, fresh=True):
    """Exercise wrapper arithmetic without pretending to validate transport."""
    row = snapshot["resources"]["bills"]["records"][0]
    case = _case(snapshot, "bills", row, AT, fresh)
    _context(case, row, snapshot)
    if bound:
        _price(case, snapshot, row, bound, fresh)
    case["workflow_recommendation"] = _workflow(case)
    return case


def test_explicit_mixed_negotiated_cap_uses_native_amounts_and_quantity():
    snapshot = observation()
    case = direct(snapshot, binding(snapshot))
    assert case["outcome"] == "ELIGIBLE"
    assert case["amount"] == "40.00"  # 120 native net - 10 native units * 8 negotiated cap
    assert case["stage"] == "PREPAYMENT_REVIEW"
    assert case["native_status"] == "OPEN"
    assert case["native_approval_status"] == "PENDING"
    assert case["data_provenance"]["classification"] == "MIXED"
    assert case["sources"] == ["LIVE_RAMP_SANDBOX", "SYNTHETIC_CUSTOMER"]
    assert case["workflow_recommendation"]["status"] == "SIMULATION_ONLY"
    assert case["actual_recovery"] is None and case["actual_money_prevented"] is None
    assert not case["publishable"]


def test_paid_is_retrospective_without_changing_native_enum():
    snapshot = observation()
    snapshot["resources"]["bills"]["records"][0]["status"] = "PAID"
    seal(snapshot)
    case = direct(snapshot, binding(snapshot))
    assert case["stage"] == "RETROSPECTIVE_REVIEW"
    assert case["native_status"] == "PAID"


def test_po_variance_is_not_entitlement_and_has_no_amount():
    case = direct(observation())
    assert case["finding_kind"] == "PO_VARIANCE"
    assert case["line_findings"][0]["difference"] == "20.00"
    assert case["line_findings"][0]["legal_entitlement"] is False
    assert case["outcome"] == "INSUFFICIENT_EVIDENCE" and case["amount"] is None
    assert all("incident" not in item["label"].lower() for item in case["evidence"])


@pytest.mark.parametrize("change", [
    dict(capture_digest="0" * 64), dict(operator_ref=""), dict(terms_evidence_ref=""),
    dict(terms_evidence_digest=""), dict(terms_mode="unknown"),
    dict(terms_mode="OPERATOR_ATTESTED", signed_terms_attested=False), dict(mappings=()),
])
def test_bad_binding_refuses(change):
    snapshot = observation()
    case = direct(snapshot, replace(binding(snapshot), **change))
    assert case["outcome"] == "INSUFFICIENT_EVIDENCE" and case["amount"] is None


@pytest.mark.parametrize("change", [
    dict(line_digest="0" * 64), dict(purchase_order_line_digest="0" * 64), dict(purchase_order_id=TX),
    dict(purchase_order_line_id=TX), dict(product="wrong-sku"), dict(unit="wrong-unit"),
    dict(start=START + timedelta(days=1)), dict(end=END - timedelta(days=1)), dict(evidence_ref=""),
    dict(evidence_digest="x"), dict(complete_quantity_attested=False), dict(net_without_tax_attested=False),
])
def test_missing_conflicting_service_mapping_refuses(change):
    snapshot = observation()
    bound = binding(snapshot)
    case = direct(snapshot, replace(bound, mappings=(replace(bound.mappings[0], **change),)))
    assert case["outcome"] != "ELIGIBLE" and case["amount"] is None


@pytest.mark.parametrize("field,value", [("quantity", None), ("quantity", "0"), ("quantity", "2.5"),
    ("quantity", "NaN"), ("unit_price", None), ("unit_price", money(0)), ("sku", "wrong-sku"),
    ("start_date", None), ("end_date", None), ("amount", money(9999))])
def test_native_facts_cannot_be_fabricated_by_overlay(field, value):
    snapshot = observation()
    snapshot["resources"]["purchase_orders"]["records"][0]["lines"][0][field] = value
    seal(snapshot)
    case = direct(snapshot, binding(snapshot))
    assert case["amount"] is None and case["outcome"] == "INSUFFICIENT_EVIDENCE"


def test_stale_observation_does_not_become_entitlement():
    snapshot = observation()
    case = direct(snapshot, binding(snapshot), fresh=False)
    assert case["amount"] is None and case["outcome"] == "INSUFFICIENT_EVIDENCE"


def test_operator_terms_are_separate_from_synthetic_terms():
    snapshot = observation()
    bound = replace(binding(snapshot), terms_mode="OPERATOR_ATTESTED", signed_terms_attested=True)
    case = direct(snapshot, bound)
    assert case["outcome"] == "ELIGIBLE"
    assert case["data_provenance"]["classification"] == "PROVIDER_WITH_OPERATOR_EVIDENCE"
    assert "SYNTHETIC_CUSTOMER" not in case["sources"]
    assert "OPERATOR_ATTESTED_CUSTOMER" in case["sources"]
    assert not case["publishable"]


def test_amendment_effective_date_changes_rate_and_crossing_is_refused():
    snapshot = observation()
    bound = binding(snapshot)
    base = bound.agreement.versions[0]
    amended = replace(base, id="v2", effective_at=START, signed_at=START, supersedes="v1",
                      rates=(Rate("compute-unit", "unit", (Tier(None, Decimal("6")),)),),
                      citation=replace(base.citation, version="v2"))
    terms = replace(bound.agreement, versions=(base, amended))
    assert direct(snapshot, replace(bound, agreement=terms))["amount"] == "60.00"
    amended = replace(amended, effective_at=START + timedelta(days=1))
    case = direct(snapshot, replace(bound, agreement=replace(terms, versions=(base, amended))))
    assert case["amount"] is None
    assert case["outcome"] == "INSUFFICIENT_EVIDENCE"


def test_zero_cap_and_party_mismatch_are_refused():
    snapshot = observation()
    bound = binding(snapshot)
    version = replace(bound.agreement.versions[0], rates=(Rate("compute-unit", "unit", (Tier(None, Decimal(0)),)),))
    for terms in (replace(bound.agreement, versions=(version,)), replace(bound.agreement, vendor=TX),
                  replace(bound.agreement, customer=TX)):
        assert direct(snapshot, replace(bound, agreement=terms))["amount"] is None


def test_undercharge_is_not_net_savings():
    snapshot = observation()
    bound = binding(snapshot)
    version = replace(bound.agreement.versions[0], rates=(Rate("compute-unit", "unit", (Tier(None, Decimal(15)),)),))
    case = direct(snapshot, replace(bound, agreement=replace(bound.agreement, versions=(version,))))
    assert case["outcome"] == "INELIGIBLE" and case["amount"] is None
    assert case["line_findings"][0]["direction"] == "UNDERCHARGE"


@pytest.mark.parametrize("url", ["https://evil.example/bills/" + BILL,
    "https://demo.ramp.com.evil.example/bills/" + BILL, "https://demo.ramp.com/bills/" + TX,
    "https://demo.ramp.com/bills/" + BILL + "?token=private", "https://u:p@demo.ramp.com/bills/" + BILL])
def test_unvetted_link_never_rendered(url):
    snapshot = observation()
    snapshot["resources"]["bills"]["records"][0]["deep_link_url"] = url
    assert direct(snapshot)["provider_uri"] is None


def test_native_comment_support_does_not_invent_trigger_or_grant():
    snapshot = observation()
    bill = direct(snapshot)
    action = bill["workflow_recommendation"]
    assert action["path"] == f"/developer/v1/comments/bills/{BILL}"
    assert action["approval_trigger_instance_id"] is None and action["granted"] is None
    for resource in ("vendors", "purchase_orders", "agreements"):
        case = _case(snapshot, resource, snapshot["resources"][resource]["records"][0], AT, True)
        assert _workflow(case)["path"] is None


def test_terms_and_line_evidence_change_binding_digest():
    snapshot = observation()
    bound = binding(snapshot)
    assert binding_digest(bound) != binding_digest(replace(bound, terms_evidence_digest="c" * 64))
    assert binding_digest(bound) != binding_digest(replace(bound, mappings=(replace(bound.mappings[0], evidence_digest="d" * 64),)))


def test_foreign_po_does_not_create_variance_or_entitlement():
    snapshot = observation()
    snapshot["resources"]["purchase_orders"]["records"][0]["vendor_id"] = TX
    seal(snapshot)
    case = direct(snapshot, binding(snapshot))
    assert case["amount"] is None
    assert not case["line_findings"]


def test_transaction_refund_preserves_negative_native_amount():
    snapshot = observation()
    row = snapshot["resources"]["transactions"]["records"][0]
    case = _case(snapshot, "transactions", row, AT, True)
    _context(case, row, snapshot)
    assert case["native_amount"]["amount"] == "-1.00" and case["amount"] is None
    assert case["stage"] == "RETROSPECTIVE_REVIEW"


def test_evaluate_uses_records_validator_when_dependency_is_integrated():
    records = pytest.importorskip("uptime.ramp_records", reason="Records owner dependency is integrated by root")
    # Round-trip through the canonical owner validator; no substitute validator.
    snapshot = canonical_observation(records)
    records._validate_snapshot(snapshot)
    rows = evaluate_snapshot(snapshot, as_of=AT, bindings=(binding(snapshot),))
    assert len(rows) == 5
    assert next(c for c in rows if c["provider_id"] == BILL)["amount"] == "40.00"
    assert all(c["finding_digest"] == fingerprint({k: v for k, v in c.items() if k != "finding_digest"}) for c in rows)
    tampered = deepcopy(snapshot)
    tampered["resources"]["bills"]["records"][0]["status"] = "PAID"
    with pytest.raises(Exception):
        evaluate_snapshot(tampered, as_of=AT)


def canonical_observation(records):
    """Use the records owner's real sanitizers on artificial official-wire shapes."""
    snap = observation()
    def raw_money(cents):
        return dict(amount=cents, currency_code="USD", minor_unit_conversion_rate=100)
    r = snap["resources"]
    r["bills"]["records"] = [records.sanitize_bill(dict(id=BILL, vendor={"id": VENDOR}, entity_id=ENTITY,
        status="OPEN", approval_status="PENDING", issued_at=AT.isoformat(), amount=raw_money(12000),
        purchase_order_id=PO, line_items=[dict(id=LINE, amount=raw_money(12000), purchase_order_line_item_id=POLINE)]))]
    po = records.sanitize_purchase_order(dict(id=PO, vendor_id=VENDOR, entity_id=ENTITY,
        billing_status="UNBILLED", amount=raw_money(10000), bill_ids=[BILL], line_items=[dict(id=POLINE,
        amount=raw_money(10000), quantity=10, unit_price=raw_money(1000), start_date="2026-10-01", end_date="2026-11-01")]))
    po.update(discovery=["LINKED"], reciprocal_bill_ids=[BILL])
    r["purchase_orders"]["records"] = [po]
    r["vendors"]["records"] = [records.sanitize_vendor(dict(id=VENDOR, approval_status="APPROVED", is_active=True))]
    r["transactions"]["records"] = [records.sanitize_transaction(dict(id=TX, entity_id=ENTITY, state="CLEARED",
        entity_amount={"value": -100, "currency": "USD"}, minor_unit_conversion_rate=100))]
    r["agreements"]["records"] = [records.sanitize_agreement(dict(id=AGREEMENT, payee={"uuid": VENDOR},
        currency="USD", start_date="2026-01-01", end_date="2027-01-01"))]
    for name, resource in r.items():
        scope = records.RESOURCE_SCOPES[name]
        resource["grant"] = dict(requested=[scope], granted=[scope], scope_reported=True, state="GRANTED")
    return seal(snap)


def test_inventory_line_uses_its_own_quantity_without_po():
    snapshot = observation()
    row = snapshot["resources"]["bills"]["records"][0]
    row["purchase_order_id"] = None
    row["lines"][0].update(kind="inventory_line_items", quantity="10", unit_price=money(1200),
                            purchase_order_line_item_id=None)
    seal(snapshot)
    bound = binding(snapshot)
    mapping = replace(bound.mappings[0], purchase_order_id=None, purchase_order_line_id=None,
                      purchase_order_line_digest=None, quantity_source="BILL_INVENTORY")
    case = direct(snapshot, replace(bound, mappings=(mapping,)))
    assert case["amount"] == "40.00" and case["outcome"] == "ELIGIBLE"
    row["lines"][0]["quantity"] = "20"
    seal(snapshot)
    bound = replace(bound, capture_digest=snapshot["checksum"], mappings=(replace(mapping, line_digest=line_digest(row["lines"][0])),))
    assert direct(snapshot, bound)["amount"] is None


def test_actual_vetted_link_is_preserved():
    snapshot = observation()
    url = "https://demo.ramp.com/s/bill-pay/bills/" + BILL
    snapshot["resources"]["bills"]["records"][0]["deep_link_url"] = url
    assert direct(snapshot)["provider_uri"] == url


def test_raw_terms_text_and_private_document_urls_do_not_escape():
    snapshot = observation()
    bound = binding(snapshot)
    version = bound.agreement.versions[0]
    citation = replace(version.citation, uri="https://private.example/secret-document", section="private raw clause")
    case = direct(snapshot, replace(bound, agreement=replace(bound.agreement, versions=(replace(version, citation=citation),))))
    import json
    assert "private.example" not in json.dumps(case)
    assert "private raw clause" not in json.dumps(case)
    assert case["amount"] is None


def test_snapshot_freshness_digest_target_and_availability_integration():
    records = pytest.importorskip("uptime.ramp_records")
    snapshot = canonical_observation(records)
    bound = binding(snapshot)
    for at in (AT - timedelta(seconds=1), AT + timedelta(hours=25)):
        cases = evaluate_snapshot(snapshot, as_of=at, bindings=(bound,))
        case = next(c for c in cases if c["provider_id"] == BILL)
        assert case["amount"] is None and case["outcome"] == "INSUFFICIENT_EVIDENCE"
    with pytest.raises(ValueError, match="Ambiguous"):
        evaluate_snapshot(snapshot, as_of=AT, bindings=(bound, bound))
    with pytest.raises(ValueError, match="absent"):
        evaluate_snapshot(snapshot, as_of=AT, bindings=(replace(bound, object_id=ENTITY),))
    before = evaluate_snapshot(snapshot, as_of=AT)[0]["finding_digest"]
    snapshot["resources"]["bills"]["records"][0]["approval_status"] = "APPROVED"
    seal(snapshot)
    after = evaluate_snapshot(snapshot, as_of=AT)[0]["finding_digest"]
    assert before != after
    snapshot["resources"]["agreements"].update(status="FORBIDDEN", records=[], complete=False)
    seal(snapshot)
    rows = evaluate_snapshot(snapshot, as_of=AT)
    assert all(c["provider_id"] != AGREEMENT for c in rows)
    assert all(c["amount"] is None for c in rows)


def test_inventory_binding_through_actual_records_validator():
    records = pytest.importorskip("uptime.ramp_records")
    snapshot = canonical_observation(records)
    row = snapshot["resources"]["bills"]["records"][0]
    row["purchase_order_id"] = None
    row["lines"][0].update(kind="inventory_line_items", quantity="10", unit_price=records._money(dict(amount=1200, currency_code="USD", minor_unit_conversion_rate=100)),
                            quantity_rate_check="MATCH", purchase_order_line_item_id=None)
    snapshot["resources"]["purchase_orders"]["records"][0]["reciprocal_bill_ids"] = []
    seal(snapshot)
    bound = binding(snapshot)
    mapping = replace(bound.mappings[0], quantity_source="BILL_INVENTORY", purchase_order_id=None,
                      purchase_order_line_id=None, purchase_order_line_digest=None)
    cases = evaluate_snapshot(snapshot, as_of=AT, bindings=(replace(bound, mappings=(mapping,)),))
    case = next(c for c in cases if c["provider_id"] == BILL)
    assert case["id"].startswith("ramp-synthetic-price-")
    assert case["amount"] == "40.00"
    assert next(c for c in cases if c["provider_id"] == TX)["amount"] is None


def test_invalid_binding_reference_is_not_echoed_in_refusal():
    import json
    snapshot = observation()
    bound = replace(binding(snapshot), terms_evidence_ref="private customer contract raw text")
    case = direct(snapshot, bound)
    assert "private customer contract raw text" not in json.dumps(case)
    assert case["amount"] is None
