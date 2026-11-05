"""Synthetic local observations only; these tests do not read captured/customer data."""
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from unittest.mock import patch

import pytest

from uptime.contracts import Citation, fingerprint
from uptime.pricing import Agreement, ContractVersion, Rate, Tier
from uptime.ramp import RampError, RampHTTPError, Token
from uptime import ramp_records as records
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
    # Round-trip through the canonical owner validator; no substitute validator.
    snapshot = canonical_observation()
    records._validate_snapshot(snapshot)
    rows = evaluate_snapshot(snapshot, as_of=AT, bindings=(binding(snapshot),))
    assert len(rows) == 5
    case = next(c for c in rows if c["provider_id"] == BILL)
    assert case["amount"] == "40.00" and case["outcome"] == "ELIGIBLE"
    assert case["linked_records"] == [
        dict(object_type="vendors", id=VENDOR, relationship="provider_vendor_id"),
        dict(object_type="purchase-orders", id=PO, relationship="provider_purchase_order_id"),
        dict(object_type="vendor-agreements", id=AGREEMENT, relationship="same_vendor_context_only"),
    ]
    assert case["sources"] == ["LIVE_RAMP_SANDBOX", "SYNTHETIC_CUSTOMER"]
    assert case["data_provenance"]["classification"] == "MIXED"
    assert case["line_findings"][0]["line_id"] == LINE
    po = next(c for c in rows if c["provider_id"] == PO)
    assert dict(object_type="bills", id=BILL, relationship="reciprocal_provider_bill_id") in po["linked_records"]
    assert all(c["amount"] is None for c in rows if c["provider_id"] != BILL)
    tampered = deepcopy(snapshot)
    tampered["resources"]["bills"]["records"][0]["status"] = "PAID"
    with pytest.raises(RampError, match="Invalid Ramp records snapshot"):
        evaluate_snapshot(tampered, as_of=AT)


def raw_money(cents):
    return dict(amount=cents, currency_code="USD", minor_unit_conversion_rate=100)


class SyntheticReader:
    """Credential-free wire fixtures through the production importer.

    Shapes follow the native owner's published OpenAPI contract (00da82e).
    Labels emitted by the importer are assertions under test, not live captures.
    Quantities belong to structured inventory/PO lines; SKU/unit are deliberately
    absent because the native schema does not provide them.
    """
    def __init__(self, *, inventory=False):
        self.calls = []
        self.forbidden = set()
        self.approval_status = "PENDING"
        line = dict(id=LINE, amount=raw_money(12000))
        if inventory:
            line.update(quantity=10, unit_price=raw_money(1200))
        else:
            line["purchase_order_line_item_id"] = POLINE
        self.rows = {
            "bills": [dict(id=BILL, vendor={"id": VENDOR}, entity_id=ENTITY,
                status="OPEN", approval_status="PENDING", issued_at=AT.isoformat(), amount=raw_money(12000),
                purchase_order_id=None if inventory else PO,
                **{"inventory_line_items" if inventory else "line_items": [line]})],
            "bills/drafts": [],
            "purchase-orders": [dict(id=PO, vendor_id=VENDOR, entity_id=ENTITY,
                billing_status="UNBILLED", amount=raw_money(10000), bill_ids=[] if inventory else [BILL],
                line_items=[dict(id=POLINE, amount=raw_money(10000), quantity=10, unit_price=raw_money(1000),
                                start_date="2026-10-01", end_date="2026-11-01")])],
            "vendors": [dict(id=VENDOR, approval_status="APPROVED", is_active=True)],
            "transactions": [dict(id=TX, entity_id=ENTITY, state="CLEARED",
                entity_amount={"value": -100, "currency": "USD"}, minor_unit_conversion_rate=100)],
            "vendors/agreements": [dict(id=AGREEMENT, payee={"uuid": VENDOR}, currency="USD",
                start_date="2026-01-01", end_date="2027-01-01", purchase_orders=[{"id": PO}])],
            "vendors/credits": [],
        }

    def token(self, scopes):
        return Token("synthetic-test-token", frozenset(scopes), frozenset(scopes))

    def request(self, token, method, path, query=None, data=None):
        assert token.exact
        self.calls.append((method, path, deepcopy(query), deepcopy(data)))
        assert method == ("POST" if path == "vendors/agreements" else "GET")
        if path in self.forbidden:
            raise RampHTTPError(403)
        if path == "vendors/agreements":
            assert query is None and set(data) <= {"page_size", "start"}
        if path == "approvals":
            rows = [dict(entity_id=query["entity_ids"][0], entity_type=query["entity_type"].lower(),
                         status=self.approval_status, approval_history=[], next_approvers=[])]
        elif path.startswith("comments/"):
            rows = []
        elif path in self.rows:
            rows = self.rows[path]
        else:
            resource, ident = path.rsplit("/", 1)
            return deepcopy(next(row for row in self.rows[resource] if row["id"] == ident))
        return dict(data=deepcopy(rows), page={"next": None})


def canonical_observation(reader=None):
    with patch.object(records, "now", return_value=AT.isoformat()):
        snapshot = records.sync_records(reader if reader is not None else SyntheticReader())
    records._validate_snapshot(snapshot)
    return snapshot


def inventory_binding(snapshot):
    bound = binding(snapshot)
    mapping = replace(bound.mappings[0], quantity_source="BILL_INVENTORY", purchase_order_id=None,
                      purchase_order_line_id=None, purchase_order_line_digest=None)
    return replace(bound, mappings=(mapping,))


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
    reader = SyntheticReader()
    snapshot = canonical_observation(reader)
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
    reader.rows["bills"][0]["approval_status"] = "APPROVED"
    snapshot = canonical_observation(reader)
    after = evaluate_snapshot(snapshot, as_of=AT)[0]["finding_digest"]
    assert before != after
    reader.forbidden.add("vendors/agreements")
    snapshot = canonical_observation(reader)
    assert snapshot["resources"]["agreements"]["status"] == "FORBIDDEN"
    rows = evaluate_snapshot(snapshot, as_of=AT)
    assert all(c["provider_id"] != AGREEMENT for c in rows)
    assert all(c["amount"] is None for c in rows)


def test_inventory_binding_through_actual_records_validator():
    snapshot = canonical_observation(SyntheticReader(inventory=True))
    assert snapshot["resources"]["bills"]["records"][0]["lines"][0]["quantity_rate_check"] == "MATCH"
    cases = evaluate_snapshot(snapshot, as_of=AT, bindings=(inventory_binding(snapshot),))
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


def bill_case(snapshot, bound=None, at=AT):
    cases = evaluate_snapshot(snapshot, as_of=at, bindings=() if bound is None else (bound,))
    return next(case for case in cases if case["provider_id"] == BILL)


@pytest.mark.parametrize("mode", [None, "SYNTHETIC_NEGOTIATED", "OPERATOR_ATTESTED"])
def test_idempotent_readback_retains_audit_clock_without_changing_finding(tmp_path, mode):
    snapshot = canonical_observation()
    bound = None if mode is None else replace(binding(snapshot), terms_mode=mode, signed_terms_attested=True)
    original = deepcopy(snapshot)
    path = tmp_path / "synthetic-records.json"
    path.write_text(json.dumps(snapshot))
    first = evaluate_snapshot(snapshot, as_of=AT, bindings=() if bound is None else (bound,))
    for elapsed in (timedelta(microseconds=1), timedelta(minutes=10), timedelta(hours=24)):
        at = AT + elapsed
        # Exercise the actual disk loader, including its transient snapshot_status.
        loaded = records.load_snapshot(path, at=at)
        again = evaluate_snapshot(loaded, as_of=at, bindings=() if bound is None else (bound,))
        assert [c["finding_digest"] for c in again] == [c["finding_digest"] for c in first]
        assert all(c["data_provenance"]["evaluated_at"] == at.isoformat() for c in again)
        assert all(c["data_provenance"]["freshness"] == "FRESH" for c in again)
        for old, new in zip(first, again, strict=True):
            expected = deepcopy(old)
            expected["data_provenance"]["evaluated_at"] = at.isoformat()
            assert new == expected
    assert snapshot == original


def test_future_fresh_and_stale_findings_have_distinct_stable_digests():
    snapshot = canonical_observation()
    bound = binding(snapshot)
    checks = [
        (AT - timedelta(seconds=2), "FUTURE", None),
        (AT - timedelta(seconds=1), "FUTURE", None),
        (AT, "FRESH", "40.00"),
        (AT + timedelta(hours=24), "FRESH", "40.00"),
        (AT + timedelta(hours=24, microseconds=1), "STALE", None),
        (AT + timedelta(hours=25), "STALE", None),
    ]
    digests = {}
    for at, state, amount in checks:
        case = bill_case(snapshot, bound, at)
        assert case["data_provenance"]["freshness"] == state
        assert case["amount"] == amount
        assert case["outcome"] == ("ELIGIBLE" if state == "FRESH" else "INSUFFICIENT_EVIDENCE")
        assert digests.setdefault(state, case["finding_digest"]) == case["finding_digest"]
    assert len(set(digests.values())) == 3


@pytest.mark.parametrize("change", ["economics", "native_approval", "approval_evidence", "capture",
                                  "terms", "terms_evidence", "service_evidence", "source"])
def test_material_changes_invalidate_stable_finding_digest(change):
    reader = SyntheticReader()
    snapshot = canonical_observation(reader)
    bound = binding(snapshot)
    before = bill_case(snapshot, bound)
    if change == "economics":
        reader.rows["bills"][0]["amount"] = raw_money(13000)
        reader.rows["bills"][0]["line_items"][0]["amount"] = raw_money(13000)
    elif change == "native_approval":
        reader.rows["bills"][0]["approval_status"] = "APPROVED"
    elif change == "approval_evidence":
        reader.approval_status = "APPROVED"
    if change in {"economics", "native_approval", "approval_evidence"}:
        snapshot = canonical_observation(reader)
        bound = binding(snapshot)
    elif change == "capture":
        with patch.object(records, "now", return_value=(AT + timedelta(seconds=1)).isoformat()):
            snapshot = records.sync_records(reader)
        bound = binding(snapshot)
    elif change == "terms":
        version = replace(bound.agreement.versions[0], rates=(Rate("compute-unit", "unit", (Tier(None, Decimal(7)),)),))
        bound = replace(bound, agreement=replace(bound.agreement, versions=(version,)))
    elif change == "terms_evidence":
        bound = replace(bound, terms_evidence_digest="c" * 64)
    elif change == "service_evidence":
        bound = replace(bound, mappings=(replace(bound.mappings[0], evidence_digest="d" * 64),))
    elif change == "source":
        bound = replace(bound, terms_mode="OPERATOR_ATTESTED", signed_terms_attested=True)
    after = bill_case(snapshot, bound, AT + timedelta(minutes=1))
    assert after["outcome"] == "ELIGIBLE"
    assert after["amount"] == {"economics": "50.00", "terms": "50.00"}.get(change, "40.00")
    assert before["finding_digest"] != after["finding_digest"]
    if change == "source":
        assert after["sources"] == ["LIVE_RAMP_SANDBOX", "OPERATOR_ATTESTED_CUSTOMER"]
        assert after["data_provenance"]["classification"] == "PROVIDER_WITH_OPERATOR_EVIDENCE"


@pytest.mark.parametrize("inventory", [False, True])
@pytest.mark.parametrize("mode", ["SYNTHETIC_NEGOTIATED", "OPERATOR_ATTESTED"])
def test_withheld_native_quantity_cannot_be_filled_by_operator_attestation(inventory, mode):
    reader = SyntheticReader(inventory=inventory)
    snapshot = canonical_observation(reader)
    bind = inventory_binding if inventory else binding
    good = replace(bind(snapshot), terms_mode=mode, signed_terms_attested=True)
    assert bill_case(snapshot, good)["amount"] == "40.00"
    line = reader.rows["bills"][0]["inventory_line_items"][0] if inventory else reader.rows["purchase-orders"][0]["line_items"][0]
    line["quantity"] = None
    snapshot = canonical_observation(reader)
    bound = replace(bind(snapshot), terms_mode=mode, signed_terms_attested=True)
    case = bill_case(snapshot, bound)
    assert case["outcome"] == "INSUFFICIENT_EVIDENCE" and case["amount"] is None
    assert case["missing"] == ["Authoritative structured quantity required."]
    expected_source = "SYNTHETIC_CUSTOMER" if mode == "SYNTHETIC_NEGOTIATED" else "OPERATOR_ATTESTED_CUSTOMER"
    assert case["sources"] == ["LIVE_RAMP_SANDBOX", expected_source]
    assert case["evidence"][-1]["sources"] == [expected_source]
    assert case["actual_money_prevented"] is None and case["actual_recovery"] is None
    assert not case["publishable"]


@pytest.mark.parametrize("resource", ["bills", "purchase-orders"])
def test_withheld_native_money_scale_does_not_crash_or_create_po_variance(resource):
    reader = SyntheticReader()
    reader.rows[resource][0]["line_items"][0]["amount"]["minor_unit_conversion_rate"] = None
    snapshot = canonical_observation(reader)
    for bound in (None, binding(snapshot)):
        case = bill_case(snapshot, bound)
        assert case["amount"] is None and case["outcome"] == "INSUFFICIENT_EVIDENCE"
        assert not case["line_findings"]
        assert case["finding_kind"] != "PO_VARIANCE"


def test_missing_native_po_line_ids_do_not_establish_a_join():
    reader = SyntheticReader()
    reader.rows["bills"][0]["line_items"][0]["purchase_order_line_item_id"] = None
    reader.rows["purchase-orders"][0]["line_items"][0]["id"] = None
    snapshot = canonical_observation(reader)
    bound = binding(snapshot)
    bound = replace(bound, mappings=(replace(bound.mappings[0], purchase_order_line_id=None),))
    for candidate in (None, bound):
        case = bill_case(snapshot, candidate)
        assert case["outcome"] == "INSUFFICIENT_EVIDENCE" and case["amount"] is None
        assert not case["line_findings"]
        assert case["finding_kind"] != "PO_VARIANCE"


@pytest.mark.parametrize("change", ["unsupported_sku", "source", "coverage", "quantity_check", "reciprocal"])
def test_resealed_invalid_native_schema_is_still_rejected(change):
    snapshot = canonical_observation()
    resources = snapshot["resources"]
    if change == "unsupported_sku":
        resources["bills"]["records"][0]["lines"][0]["sku"] = "invented-native-sku"
    elif change == "source":
        resources["bills"]["records"][0]["sources"] = ["SYNTHETIC_CUSTOMER"]
    elif change == "coverage":
        resources["bills"]["coverage"] = {}
    elif change == "quantity_check":
        resources["purchase_orders"]["records"][0]["lines"][0]["quantity_rate_check"] = "UNAVAILABLE"
    else:
        resources["purchase_orders"]["records"][0]["reciprocal_bill_ids"] = []
    seal(snapshot)
    with pytest.raises(RampError, match="Invalid Ramp records snapshot"):
        evaluate_snapshot(snapshot, as_of=AT)


def test_operator_signed_terms_clock_transition_and_capture_expiry():
    signature_at = AT + timedelta(hours=12)
    snapshot = canonical_observation()
    bound = binding(snapshot)
    base = bound.agreement.versions[0]
    # A later amendment leaves the billed October service on v1. Its signature
    # must still be valid at the evaluation clock before accepting the binding.
    amendment = replace(base, id="v2", supersedes="v1", signed_at=signature_at,
                        effective_at=datetime(2026, 12, 1, tzinfo=UTC),
                        citation=replace(base.citation, version="v2"))
    bound = replace(bound, terms_mode="OPERATOR_ATTESTED", signed_terms_attested=True,
                    agreement=replace(bound.agreement, versions=(base, amendment)))
    before = bill_case(snapshot, bound, signature_at - timedelta(microseconds=1))
    valid = bill_case(snapshot, bound, signature_at)
    expired = bill_case(snapshot, bound, AT + timedelta(hours=24, microseconds=1))
    assert before["amount"] is None
    assert before["missing"] == ["Terms signature date is missing or after the evaluation clock."]
    assert valid["amount"] == "40.00" and valid["outcome"] == "ELIGIBLE"
    assert expired["amount"] is None and expired["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert len({c["finding_digest"] for c in (before, valid, expired)}) == 3
    for case in (before, valid, expired):
        assert case["sources"] == ["LIVE_RAMP_SANDBOX", "OPERATOR_ATTESTED_CUSTOMER"]
        assert case["data_provenance"]["classification"] == "PROVIDER_WITH_OPERATOR_EVIDENCE"
        assert not case["publishable"]


def test_operator_cryptographic_binding_cannot_extend_native_capture_freshness():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from uptime.ramp_cap import (InvoiceCapScope, evaluate_invoice_cap,
                                 make_synthetic_binding, sign_synthetic_binding)

    # All terms and key material are ephemeral synthetic test inputs. Exercise
    # the real signature verifier against a native-validator-accepted capture.
    snapshot = canonical_observation()
    row = snapshot["resources"]["bills"]["records"][0]
    terms = dict(schema="uptime-synthetic-invoice-cap/1", terms_id="fixture-cap", source="SYNTHETIC_CUSTOMER",
                 label="Fictional invoice cap", clause="Synthetic gross cap of USD 80",
                 basis="ENTIRE_INVOICE_INCLUSIVE_TAX_AND_FEES", date_basis="INVOICE_ISSUED_DATE_UTC",
                 cap=money(8000), effective_from="2026-01-01", effective_until="2027-01-01",
                 revision=1, supersedes=None, superseded_by=None, amendments=[])
    key = Ed25519PrivateKey.generate()
    payload = make_synthetic_binding(snapshot, BILL, tenant_id="test", operator_id="test", terms=terms)
    scope = InvoiceCapScope("test", sign_synthetic_binding(payload, key), {"test": key.public_key()})
    for at in (AT, AT + timedelta(hours=24)):
        case = evaluate_invoice_cap(snapshot, row, terms, as_of=at, scope=scope)
        assert case["outcome"] == "ELIGIBLE" and case["amount"] == "40.00"
        assert case["sources"] == ["LIVE_RAMP_SANDBOX", "SYNTHETIC_CUSTOMER"]
        assert case["data_provenance"] == "MIXED" and not case["publishable"]
    expired = evaluate_invoice_cap(snapshot, row, terms, as_of=AT + timedelta(hours=24, microseconds=1), scope=scope)
    assert expired["reason"] == "STALE_SNAPSHOT" and expired["amount"] is None
    invalid = replace(scope, binding={**scope.binding, "signature": "00" * 64})
    assert evaluate_invoice_cap(snapshot, row, terms, as_of=AT, scope=invalid)["reason"] == "INVALID_BINDING_SIGNATURE"
