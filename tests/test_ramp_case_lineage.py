"""Controlled lineage, association and operator-procedure tests.

Every Ramp record here comes from an injected fake read-only provider through the real
``sync_records`` sanitizer and snapshot validator. No credentials, network, captures or
provider writes are used, and no result here is a live execution receipt. The only real
artifacts read are the committed human-note receipt and verifier script, read-only.
"""
import ast
import copy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from uuid import UUID

import pytest

from uptime.contracts import Citation
from uptime.pricing import Agreement, ContractVersion, Rate, Tier
from uptime.ramp import Token
from uptime.ramp_association import (
    APPLICABLE, CONFLICT, NOT_APPLICABLE, UNKNOWN, AssociationError, ContractScope,
    NativeAssociation, applicability, associate, exact_identity, scope_from_claim_identity,
)
from uptime.ramp_case_lineage import (
    EVIDENCE_GAP_NOTE, AwardRecord, CaseIdentity, CreditBinding, LineageError, build_lineage,
    confirm_operator_application, prepare_operator_application, surface_plan,
)
from uptime.ramp_findings import PriceBinding, ServiceMapping, evaluate_snapshot, line_digest
from uptime.ramp_records import seal_snapshot, sync_records

ROOT = Path(__file__).resolve().parents[1]


def uid(n):
    return str(UUID(int=n))


BUSINESS, OTHER_BUSINESS = uid(900), uid(901)
VENDOR, OTHER_VENDOR, ENTITY, OTHER_ENTITY = uid(1), uid(2), uid(3), uid(4)
JANUARY, APRIL, UNRELATED, FOREIGN_ENTITY_BILL = uid(10), uid(11), uid(12), uid(13)
CREDIT, OTHER_CREDIT, LINE, TX = uid(20), uid(21), uid(30), uid(40)
COMMENT = "376563cf-950c-409d-b3d8-a68599c45fa0"
T0 = datetime(2026, 5, 1, 12, tzinfo=UTC)
TENANT, CONTRACT, VERSION = "northwind tenant", "Northwind MSA 2026", "v1"
ACCOUNT, CLAIM = "Northwind account 0042", "claim January price cap"


def money(n, currency="USD"):
    return {"amount": n, "currency_code": currency, "minor_unit_conversion_rate": 100}


def raw_bill(ident, *, vendor=VENDOR, entity=ENTITY, total=12000, status="PAID", issued="2026-02-01T00:00:00+00:00",
             applied=(), status_summary=None, inventory=False, currency="USD"):
    row = {"id": ident, "vendor": {"id": vendor, "name": "PRIVATE"}, "entity_id": entity, "status": status,
           "approval_status": "APPROVED", "amount": money(total, currency), "issued_at": issued, "deep_link_url": None,
           "purchase_order_id": None, "applied_vendor_credits": [{"id": c, "amount": money(a, currency)} for c, a in applied],
           "line_items": [], "inventory_line_items": [], "memo": "PRIVATE"}
    if status_summary:
        row["status_summary"] = status_summary
    if inventory:
        row["inventory_line_items"] = [{"id": LINE, "quantity": Decimal("10"), "unit_price": money(total // 10),
                                        "amount": money(total), "memo": "PRIVATE"}]
    else:
        row["line_items"] = [{"id": uid(1000 + UUID(ident).int), "amount": money(total), "memo": "PRIVATE"}]
    return row


def raw_credit(ident=CREDIT, *, total=4000, bills=(), drafts=(), vendor=VENDOR, entity=ENTITY, currency="USD",
               reference=JANUARY, archived=None):
    applied = sum(a for _, a in bills) + sum(a for _, a in drafts)
    return {"id": ident, "vendor_id": vendor, "entity_id": entity, "reference_bill_id": reference,
            "accounting_date": "2026-04-15", "archived_at": archived, "created_at": "2026-04-15T00:00:00+00:00",
            "total_amount": money(total, currency), "remaining_amount": money(total - applied, currency),
            "total_applied_amount": money(applied, currency),
            "applied_bills": [{"bill_id": b, "amount": money(a, currency)} for b, a in bills],
            "applied_draft_bills": [{"bill_id": b, "amount": money(a, currency)} for b, a in drafts],
            "expense_line_items": [{"amount": money(total, currency), "memo": "PRIVATE"}], "reference_number": "PRIVATE"}


class FakeRamp:
    """Read-only test double of the provider contract; it has no write method."""

    def __init__(self, bills, credits=(), comments=None, transactions=()):
        self.rows = {"bills": list(bills), "bills/drafts": [], "vendors": [{"id": v, "approval_status": "APPROVED", "is_active": True,
                     "name": "PRIVATE"} for v in (VENDOR, OTHER_VENDOR)], "transactions": list(transactions),
                     "vendors/agreements": [], "vendors/credits": list(credits)}
        self.comments = comments or {}

    def token(self, scopes):
        return Token("FAKE", frozenset(scopes), frozenset(scopes))

    def request(self, token, method, path, query=None, data=None):
        assert method == "GET" or (method, path) == ("POST", "vendors/agreements")
        if path in self.rows:
            return {"data": copy.deepcopy(self.rows[path]), "page": {"next": None}}
        if path == "approvals":
            return {"data": [], "page": {"next": None}}
        if path.startswith("comments/"):
            ident = path.rsplit("/", 1)[1]
            return {"data": copy.deepcopy(self.comments.get(ident, [])), "page": {"next": None}}
        prefix, ident = path.rsplit("/", 1)
        return copy.deepcopy(next(r for r in self.rows[prefix] if r["id"] == ident))


def capture(at, bills, credits=(), comments=None, statuses=None):
    snapshot = sync_records(FakeRamp(bills, credits, comments), page_size=10, detail_limit=10)
    snapshot = {**snapshot, "observed_at": at.isoformat(), "completed_at": at.isoformat()}
    for resource, status in (statuses or {}).items():
        group = snapshot["resources"][resource]
        group.update(status=status, complete=False)
        for cov in group["coverage"].values():
            cov.update(list_complete=False, has_next=True)
    return seal_snapshot({k: v for k, v in snapshot.items() if k != "checksum"})


def base_bills(**april):
    return [raw_bill(JANUARY, inventory=True), raw_bill(APRIL, total=20000, status="OPEN",
            issued="2026-04-30T00:00:00+00:00", **april), raw_bill(UNRELATED, vendor=OTHER_VENDOR, status="OPEN")]


def scope():
    return ContractScope(TENANT, CONTRACT, VERSION, ACCOUNT, "Northwind Data Services", "USD", date(2026, 1, 1))


def native(**changes):
    values = dict(tenant=TENANT, contract_id=CONTRACT, contract_version=VERSION, provider_business_id=BUSINESS,
                  vendor_id=VENDOR, entity_ids=(ENTITY,), evidence_ref="fixture:reviewed-association",
                  evidence_digest="c" * 64)
    values.update(changes)
    return NativeAssociation(**values)


def price_binding(snapshot, *, contract=CONTRACT, vendor=VENDOR, entity=ENTITY):
    bill = next(r for r in snapshot["resources"]["bills"]["records"] if r["id"] == JANUARY)
    version = ContractVersion(VERSION, datetime(2026, 1, 1, tzinfo=UTC), datetime(2025, 12, 1, tzinfo=UTC),
                              (entity, vendor), None, (Rate("compute-unit", "unit", (Tier(None, Decimal("8")),)),), (),
                              Citation("Authored negotiated terms", VERSION, "unit-cap", "fixture:terms/v1"))
    agreement = Agreement(contract, entity, vendor, datetime(2027, 1, 1, tzinfo=UTC), (version,))
    mapping = ServiceMapping(LINE, line_digest(bill["lines"][0]), None, None, None, "compute-unit", "unit",
                             datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC),
                             "fixture:reviewed-service", "a" * 64, True, True, "BILL_INVENTORY")
    return PriceBinding("bills", JANUARY, snapshot["checksum"], "operator:test", agreement, (mapping,),
                        terms_evidence_ref="fixture:terms", terms_evidence_digest="b" * 64)


def finding_for(snapshot, binding=None, ident=JANUARY):
    cases = evaluate_snapshot(snapshot, as_of=datetime.fromisoformat(snapshot["completed_at"]) + timedelta(minutes=5),
                              bindings=(binding,) if binding else ())
    return next(c for c in cases if c["provider_id"] == ident)


def identity(**changes):
    values = dict(tenant=TENANT, provider_business_id=BUSINESS, vendor_id=VENDOR, entity_id=ENTITY,
                  object_type="bills", object_id=JANUARY, currency="USD", contract_id=CONTRACT,
                  contract_version=VERSION, account_id=ACCOUNT, claim_id=CLAIM)
    values.update(changes)
    return CaseIdentity(**values)


def award(**changes):
    values = dict(award_id="award northwind 1", claim_id=CLAIM, contract_id=CONTRACT, contract_version=VERSION,
                  account_id=ACCOUNT, vendor_id=VENDOR, currency="USD", amount_minor=4000,
                  minor_unit_conversion_rate=100, provenance="VERIFIED_VENDOR_AWARD", memo_ref="CM-1001",
                  evidence_digest="d" * 64)
    values.update(changes)
    return AwardRecord(**values)


BINDING = CreditBinding(CREDIT, "award northwind 1", CLAIM, "fixture:reviewed-credit-binding", "e" * 64)


def contract_case(reads=(), *, credit_binding=BINDING, the_award=None, assoc=None, registry=None, **lineage):
    snapshot = capture(T0, base_bills())
    binding = price_binding(snapshot)
    association = assoc if assoc is not None else associate(snapshot, scope(), native(), provider_business_id=BUSINESS)
    kwargs = dict(snapshot=snapshot, provider_business_id=BUSINESS, finding=finding_for(snapshot, binding),
                  association=association, price_binding=binding,
                  award=the_award if the_award is not None else award(), credit_binding=credit_binding,
                  readbacks=tuple((BUSINESS, r) for r in reads),
                  binding_registry=registry if registry is not None else (credit_binding,) if credit_binding else None)
    kwargs.update(lineage)
    return build_lineage(identity(), **kwargs), snapshot, association


def stage(lineage, name):
    return next(s for s in lineage["stages"] if s["stage"] == name)


def later(hours, credits, **april):
    return capture(T0 + timedelta(hours=hours), base_bills(**april), credits)


# --- Exact identity and association -------------------------------------------------

def test_exact_identity_keeps_spaces_and_refuses_rewrites():
    assert exact_identity("Northwind account 0042") == "Northwind account 0042"
    for bad in (" Northwind", "Northwind ", "", "line\nbreak", "Café", 42):
        with pytest.raises(AssociationError):
            exact_identity(bad)
    mapped = scope_from_claim_identity({"tenant": TENANT, "vendor": "Northwind Data Services", "account": ACCOUNT,
                                        "agreement_id": CONTRACT, "agreement_version": VERSION, "service": "x",
                                        "month": "2026-01", "remedy": "availability"},
                                       currency="USD", effective_start=date(2026, 1, 1))
    assert (mapped.contract_id, mapped.account_id, mapped.vendor_label) == (CONTRACT, ACCOUNT, "Northwind Data Services")


def test_association_uses_native_ids_never_names_or_amounts():
    snapshot = capture(T0, base_bills() + [raw_bill(FOREIGN_ENTITY_BILL, entity=OTHER_ENTITY)])
    result = associate(snapshot, scope(), native(), provider_business_id=BUSINESS)
    assert applicability(result, "bills", JANUARY) == (APPLICABLE, [])
    assert applicability(result, "bills", APRIL) == (APPLICABLE, [])
    # Same amount and dates, different native vendor: Northwind terms never attach.
    assert applicability(result, "bills", UNRELATED) == (NOT_APPLICABLE, ["DIFFERENT_VENDOR"])
    assert applicability(result, "bills", FOREIGN_ENTITY_BILL) == (NOT_APPLICABLE, ["DIFFERENT_ENTITY"])
    assert applicability(result, "bills", uid(999)) == (UNKNOWN, ["RECORD_NOT_OBSERVED"])
    assert "Northwind" not in json.dumps(result["records"])
    assert result["entitlement_established"] is False and result["writes_attempted"] is False


def test_missing_provider_fact_is_unknown_not_ineligible():
    bills = base_bills()
    bills[0]["issued_at"] = None
    snapshot = capture(T0, bills)
    result = associate(snapshot, scope(), native(), provider_business_id=BUSINESS)
    status, reasons = applicability(result, "bills", JANUARY)
    assert status == UNKNOWN and reasons == ["ISSUE_DATE_UNAVAILABLE"]


def test_period_currency_allowlist_and_conflict_rules():
    bills = base_bills() + [raw_bill(uid(14), issued="2025-12-31T00:00:00+00:00"),
                            raw_bill(uid(15), currency="EUR")]
    snapshot = capture(T0, bills)
    result = associate(snapshot, scope(), native(), provider_business_id=BUSINESS)
    assert applicability(result, "bills", uid(14))[1] == ["OUTSIDE_EFFECTIVE_PERIOD"]
    assert applicability(result, "bills", uid(15))[1] == ["CURRENCY_MISMATCH"]
    listed = associate(snapshot, scope(), native(bill_ids=(APRIL, UNRELATED)), provider_business_id=BUSINESS)
    assert applicability(listed, "bills", APRIL)[0] == APPLICABLE
    assert applicability(listed, "bills", JANUARY) == (NOT_APPLICABLE, ["NOT_IN_REVIEWED_ALLOWLIST"])
    # A reviewed allowlist that names another vendor's bill contradicts the provider record.
    assert applicability(listed, "bills", UNRELATED) == (CONFLICT, ["ALLOWLISTED_BILL_VENDOR_CONFLICT"])


def test_card_transactions_need_explicit_review_and_agreement_absence_is_reported():
    snapshot = capture(T0, base_bills())
    result = associate(snapshot, scope(), native(agreement_id=uid(50)), provider_business_id=BUSINESS)
    assert result["reviewed_ids_not_observed"] == [{"object_type": "vendor-agreements", "id": uid(50),
        "status": "ABSENT_FROM_COMPLETE_LIST", "reasons": ["REVIEWED_ID_NOT_IN_PROVIDER_LIST"]}]
    truncated = capture(T0, base_bills(), statuses={"agreements": "TRUNCATED"})
    result = associate(truncated, scope(), native(agreement_id=uid(50)), provider_business_id=BUSINESS)
    assert result["reviewed_ids_not_observed"][0]["status"] == "NOT_OBSERVED"


def test_association_refuses_wrong_business_or_contract():
    snapshot = capture(T0, base_bills())
    with pytest.raises(AssociationError, match="BUSINESS_MISMATCH"):
        associate(snapshot, scope(), native(), provider_business_id=OTHER_BUSINESS)
    with pytest.raises(AssociationError, match="ASSOCIATION_CONTRACT_MISMATCH"):
        associate(snapshot, scope(), native(contract_id="Other MSA"), provider_business_id=BUSINESS)
    with pytest.raises(AssociationError, match="ENTITY_SCOPE_REQUIRED"):
        associate(snapshot, scope(), native(entity_ids=()), provider_business_id=BUSINESS)


# --- One identity across record, finding, surface and reconciliation -----------------

def test_one_case_keeps_identity_and_applied_comes_only_from_reciprocal_readback():
    reads = (later(1, [raw_credit()]),
             later(2, [raw_credit(bills=[(APRIL, 1500)])], applied=[(CREDIT, 1500)]),
             later(3, [raw_credit(bills=[(APRIL, 4000)])], applied=[(CREDIT, 4000)]))
    partial, _, _ = contract_case(reads[:2])
    assert partial["status"] == "CREDIT_PARTIALLY_APPLIED"
    assert partial["money"]["applied_minor"] == 1500 and partial["money"]["remaining_credit_minor"] == 2500
    full, snapshot, _ = contract_case(reads)
    assert full["refusals"] == [] and full["review_required"] == []
    assert [s["status"] for s in full["stages"]] == [
        "OBSERVED", "APPLICABLE", "ELIGIBLE", "NOT_SURFACED", "VERIFIED_VENDOR_AWARD", "RECORDED", "FULLY_APPLIED"]
    money = full["money"]
    assert money["finding_estimate"] == "40.00" and money["awarded_minor"] == 4000
    assert money["recorded_credit_minor"] == 4000 and money["applied_minor"] == 4000
    assert money["actual_recovery"] is None and money["claimed_minor"] is None
    assert "total" not in json.dumps(money).lower().replace("stages_are_not_additive", "")
    assert stage(full, "APPLICATION")["applications"] == {APRIL: 4000}
    assert stage(full, "CREDIT")["reference_bill_relation"] == "EVALUATED_RECORD"
    assert full["identity"]["account_id"] == ACCOUNT and full["capture_checksum"] == snapshot["checksum"]
    assert full["writes_attempted"] is False


def test_recorded_credit_without_application_is_not_applied_value():
    lineage, _, _ = contract_case((later(1, [raw_credit()]),))
    assert lineage["status"] == "CREDIT_NOT_APPLIED"
    assert lineage["money"]["recorded_credit_minor"] == 4000 and lineage["money"]["applied_minor"] == 0


def test_draft_reservation_is_separate_from_applied():
    read = later(1, [raw_credit(bills=[(APRIL, 1000)], drafts=[(uid(60), 500)])], applied=[(CREDIT, 1000)])
    lineage, _, _ = contract_case((read,))
    assert lineage["money"]["applied_minor"] == 1000 and lineage["money"]["draft_reserved_minor"] == 500


def test_one_sided_application_leaves_applied_unknown():
    read = later(1, [raw_credit(bills=[(APRIL, 1000)])], applied=[(CREDIT, 900)])
    lineage, _, _ = contract_case((read,))
    application = stage(lineage, "APPLICATION")
    assert application["status"] == "UNKNOWN" and application["reasons"] == ["RECIPROCAL_APPLICATION_CONFLICT"]
    assert lineage["money"]["applied_minor"] is None


def test_reversal_and_later_absence_require_review_not_silent_values():
    applied = later(1, [raw_credit(bills=[(APRIL, 1000)])], applied=[(CREDIT, 1000)])
    removed = later(2, [raw_credit()])
    lineage, _, _ = contract_case((applied, removed))
    assert lineage["status"] == "REVIEW_REQUIRED" and "APPLICATION_DECREASED" in lineage["review_required"]
    assert lineage["money"]["applied_minor"] is None
    gone = later(2, [])
    lineage, _, _ = contract_case((applied, gone))
    assert "CREDIT_ABSENT_FROM_LATER_COMPLETE_LIST" in lineage["review_required"]
    assert lineage["money"]["applied_minor"] is None


def test_duplicate_imports_count_once_and_truncated_latest_read_is_unknown():
    read = later(1, [raw_credit(bills=[(APRIL, 1000)])], applied=[(CREDIT, 1000)])
    once, _, _ = contract_case((read,))
    twice, _, _ = contract_case((read, copy.deepcopy(read)))
    assert once["money"] == twice["money"] and once["stages"] == twice["stages"]
    truncated = capture(T0 + timedelta(hours=2), base_bills(), [], statuses={"credits": "TRUNCATED"})
    lineage, _, _ = contract_case((read, truncated))
    assert stage(lineage, "APPLICATION")["status"] == "UNKNOWN"
    assert lineage["money"]["applied_minor"] is None


def test_unbound_same_vendor_credit_is_never_attributed():
    read = later(1, [raw_credit(OTHER_CREDIT, bills=[(APRIL, 4000)])], applied=[(OTHER_CREDIT, 4000)])
    lineage, _, _ = contract_case((read,))
    assert stage(lineage, "CREDIT")["status"] == "ABSENT_FROM_COMPLETE_LIST"
    assert lineage["money"]["applied_minor"] is None


def test_application_outside_contract_scope_or_credit_over_award_needs_review():
    allow = associate(capture(T0, base_bills()), scope(), native(bill_ids=(JANUARY,)), provider_business_id=BUSINESS)
    read = later(1, [raw_credit(bills=[(APRIL, 1000)])], applied=[(CREDIT, 1000)])
    lineage, _, _ = contract_case((read,), assoc=allow)
    assert stage(lineage, "APPLICATION")["reasons"] == ["APPLIED_BILL_OUTSIDE_CONTRACT_SCOPE"]
    big = later(1, [raw_credit(total=9000)])
    lineage, _, _ = contract_case((big,))
    assert "CREDIT_EXCEEDS_AWARD_REQUIRES_ATTRIBUTION_REVIEW" in lineage["review_required"]


@pytest.mark.parametrize("change,code,where", [
    (dict(finding_id=APRIL), "FINDING_RECORD_MISMATCH", "FINDING"),
    (dict(binding_contract="Other MSA"), "PRICE_TERMS_CONTRACT_MISMATCH", "FINDING"),
    (dict(credit_vendor=OTHER_VENDOR), "CREDIT_VENDOR_MISMATCH", "CREDIT"),
    (dict(award=dict(contract_id="Other MSA")), "AWARD_SCOPE_MISMATCH", "AWARD"),
    (dict(award=dict(claim_id="claim February")), "AWARD_SCOPE_MISMATCH", "AWARD"),
    (dict(binding_award="award other"), "CREDIT_BINDING_AWARD_MISMATCH", "CREDIT"),
    (dict(read_business=OTHER_BUSINESS), "READBACK_BUSINESS_MISMATCH", "FINANCIAL_RECORD"),
    (dict(credit_currency="EUR"), "CREDIT_CURRENCY_MISMATCH", "CREDIT"),
])
def test_identity_breaks_stop_the_chain(change, code, where):
    snapshot = capture(T0, base_bills())
    binding = price_binding(snapshot)
    association = associate(snapshot, scope(), native(), provider_business_id=BUSINESS)
    finding = finding_for(snapshot, binding, change.get("finding_id", JANUARY))
    if "binding_contract" in change:
        bad = price_binding(snapshot, contract=change["binding_contract"])
        finding, binding = finding_for(snapshot, bad), bad
    credit = raw_credit(vendor=change.get("credit_vendor", VENDOR), currency=change.get("credit_currency", "USD"))
    read = later(1, [credit])
    bound = replace(BINDING, award_id=change.get("binding_award", BINDING.award_id))
    lineage = build_lineage(identity(), snapshot=snapshot, provider_business_id=BUSINESS, finding=finding,
                            association=association, price_binding=binding, award=award(**change.get("award", {})),
                            credit_binding=bound, readbacks=((change.get("read_business", BUSINESS), read),),
                            binding_registry=(bound,))
    assert lineage["status"] == "IDENTITY_BROKEN" and lineage["refusals"] == [code]
    assert stage(lineage, where)["status"] == "IDENTITY_BROKEN"
    assert lineage["money"]["applied_minor"] is None and lineage["money"]["awarded_minor"] is None
    later_stages = [s["stage"] for s in lineage["stages"]][[s["stage"] for s in lineage["stages"]].index(where) + 1:]
    assert all(stage(lineage, name)["status"] == "NOT_EVALUATED" for name in later_stages)


def test_northwind_terms_never_attach_to_an_unrelated_ramp_bill():
    snapshot = capture(T0, base_bills())
    association = associate(snapshot, scope(), native(), provider_business_id=BUSINESS)
    lineage = build_lineage(identity(object_id=UNRELATED, vendor_id=OTHER_VENDOR), snapshot=snapshot,
                            provider_business_id=BUSINESS, finding=finding_for(snapshot, ident=UNRELATED),
                            association=association)
    assert lineage["refusals"] == ["ASSOCIATION_VENDOR_ID_MISMATCH"]
    # Even with a matching vendor claim, the record itself must be applicable.
    lineage = build_lineage(identity(object_id=UNRELATED), snapshot=snapshot, provider_business_id=BUSINESS,
                            finding=finding_for(snapshot, ident=UNRELATED), association=association)
    assert lineage["refusals"] == ["RECORD_VENDOR_MISMATCH"]
    # Without a reviewed association, a contract case stops before any finding.
    lineage = build_lineage(identity(), snapshot=snapshot, provider_business_id=BUSINESS,
                            finding=finding_for(snapshot))
    assert lineage["refusals"] == ["REVIEWED_ASSOCIATION_REQUIRED"]


def test_tampered_finding_and_monetary_finding_without_terms_are_refused():
    snapshot = capture(T0, base_bills())
    finding = finding_for(snapshot)
    tampered = {**finding, "outcome": "ELIGIBLE"}
    gap = identity(contract_id=None, contract_version=None, account_id=None, claim_id=None)
    lineage = build_lineage(gap, snapshot=snapshot, provider_business_id=BUSINESS, finding=tampered)
    assert lineage["refusals"] == ["FINDING_DIGEST_MISMATCH"]
    with pytest.raises(LineageError, match="PARTIAL_CONTRACT_IDENTITY"):
        build_lineage(identity(account_id=None), snapshot=snapshot, provider_business_id=BUSINESS, finding=finding)


# --- Surfacing: informational note versus intervention ------------------------------

def note_receipt(**changes):
    receipt = {"schema": "uptime-human-ramp-note-readback/1", "status": "VERIFIED_READBACK", "business_id": BUSINESS,
               "bill_id": JANUARY, "comment_id": COMMENT, "body": EVIDENCE_GAP_NOTE,
               "created_at": "2026-04-30T01:46:45+00:00", "observed_at": "2026-04-30T01:50:35+00:00",
               "write_attempted": False, "api_write_proven": False, "authorship_proven": False}
    receipt.update(changes)
    return receipt


def gap_case(receipt, comment_time="2026-04-30T01:46:45+00:00", **lineage):
    comments = {JANUARY: [{"id": COMMENT, "created_at": comment_time, "message": "PRIVATE", "user_id": uid(77)}]}
    snapshot = capture(T0, base_bills(), comments=comments)
    gap = identity(contract_id=None, contract_version=None, account_id=None, claim_id=None)
    return build_lineage(gap, snapshot=snapshot, provider_business_id=BUSINESS, finding=finding_for(snapshot),
                         surface=receipt, **lineage)


def test_evidence_gap_note_is_informational_and_never_duplicated():
    lineage = gap_case(note_receipt())
    assert lineage["status"] == "FINDING_SURFACED"
    surface = stage(lineage, "SURFACE")
    assert (surface["kind"], surface["origin"], surface["payment_effect"]) == ("INFORMATIONAL_COMMENT", "HUMAN_POSTED", "NONE")
    assert surface["api_write_proven"] is False and surface["reobserved_at"] == [T0.isoformat()]
    assert stage(lineage, "APPLICATION")["record_applied_credits_observed_minor"] == 0
    assert all(v is None for k, v in lineage["money"].items() if k.endswith("_minor"))
    assert surface_plan(lineage) == {"action": "NONE", "reason": "ALREADY_SURFACED_AND_VERIFIED", "comment_id": COMMENT}
    unsurfaced = gap_case(None)
    plan = surface_plan(unsurfaced)
    assert plan["action"] == "PERSON_POSTS_NOTE_IN_RAMP_UI" and plan["payment_effect"] == "NONE"


@pytest.mark.parametrize("changes,code", [
    (dict(bill_id=APRIL), "NOTE_OBJECT_MISMATCH"),
    (dict(business_id=OTHER_BUSINESS), "NOTE_OBJECT_MISMATCH"),
    (dict(body=EVIDENCE_GAP_NOTE + " Payment stopped."), "NOTE_BODY_NOT_APPROVED"),
    (dict(status="NOT_FOUND"), "NOTE_NOT_VERIFIED"),
    (dict(write_attempted=True), "NOTE_NOT_VERIFIED"),
    (dict(observed_at=None), "NOTE_NOT_VERIFIED"),
    (dict(observed_at="2026-04-30T01:50:35"), "NOTE_NOT_VERIFIED"),
])
def test_note_receipt_must_match_the_same_object(changes, code):
    assert gap_case(note_receipt(**changes))["refusals"] == [code]


def test_note_cannot_sit_on_a_monetary_finding_or_changed_comment():
    assert gap_case(note_receipt(), comment_time="2026-04-30T02:00:00+00:00")["refusals"] == ["NOTE_TIMESTAMP_CHANGED"]
    lineage, _, _ = contract_case(surface=note_receipt())
    assert lineage["refusals"] == ["NOTE_CONTRADICTS_FINDING"]


def test_payment_hold_counts_only_when_read_back_after_the_request():
    snapshot = capture(T0, base_bills())
    finding = finding_for(snapshot, price_binding(snapshot))
    hold = {"kind": "PAYMENT_HOLD", "object_type": "bills", "object_id": JANUARY, "origin": "PERSON_IN_RAMP_UI",
            "finding_digest": finding["finding_digest"], "requested_at": (T0 + timedelta(minutes=30)).isoformat()}
    held = capture(T0 + timedelta(hours=1), [raw_bill(JANUARY, inventory=True, status_summary="ON_HOLD")] + base_bills()[1:])
    lineage, _, _ = contract_case((held,), surface=hold, credit_binding=None, the_award=award())
    surface = stage(lineage, "SURFACE")
    assert surface["status"] == "HOLD_VERIFIED_BY_READBACK" and surface["payment_effect"] == "BLOCKS_ALL_PAYMENT_RAILS"
    lineage, _, _ = contract_case((), surface=hold, credit_binding=None)
    assert stage(lineage, "SURFACE")["status"] == "HOLD_NOT_OBSERVED"
    lineage, _, _ = contract_case((), surface={"kind": "APPROVAL_STEP"}, credit_binding=None)
    assert stage(lineage, "SURFACE")["status"] == "INTERVENTION_NOT_VERIFIED"


def test_uncertain_uptime_delivery_is_read_back_never_resent():
    snapshot = capture(T0, base_bills())
    finding = finding_for(snapshot, price_binding(snapshot))
    outbox = {"kind": "UPTIME_COMMENT_OUTBOX", "object_type": "bills", "object_id": JANUARY, "status": "UNCERTAIN",
              "finding_digest": finding["finding_digest"], "remote_id": None}
    lineage, _, _ = contract_case(surface=outbox, credit_binding=None)
    assert stage(lineage, "SURFACE")["status"] == "OUTCOME_UNCERTAIN"
    assert surface_plan(lineage)["action"] == "READ_BACK_SAME_THREAD"
    delivered = {**outbox, "status": "DELIVERED", "remote_id": COMMENT}
    seen = capture(T0 + timedelta(hours=1), base_bills(), comments={JANUARY: [
        {"id": COMMENT, "created_at": T0.isoformat(), "message": "PRIVATE", "user_id": uid(77)}]})
    lineage, _, _ = contract_case((seen,), surface=delivered, credit_binding=None)
    assert stage(lineage, "SURFACE")["status"] == "VERIFIED_READBACK"
    assert stage(lineage, "SURFACE")["resend_allowed"] is False


# --- Person-operated credit application: preparation and uncertain outcomes ----------

def ready_case(**kwargs):
    current = later(1, [raw_credit(total=kwargs.pop("total", 4000))])
    lineage, _, _ = contract_case((current,), **kwargs)
    return lineage, current, associate(current, scope(), native(), provider_business_id=BUSINESS)


def prepared(amount=2400):
    lineage, current, association = ready_case()
    return prepare_operator_application(lineage, snapshot=current, provider_business_id=BUSINESS,
                                        association=association, target_bill_id=APRIL, amount_minor=amount,
                                        prepared_by="finance reviewer", prepared_at=T0.isoformat())


def test_preparation_is_not_execution_and_simulated_awards_cannot_drive_it():
    instruction = prepared()
    assert instruction["status"] == "PREPARED_NOT_EXECUTED" and instruction["executor"] == "PERSON_IN_RAMP_UI"
    assert instruction["expected_after"] == {"pair_minor": 2400, "credit_remaining_minor": 1600}
    assert any("legacy" in step for step in instruction["procedure"])
    lineage, current, association = ready_case(the_award=award(provenance="SIMULATED_VENDOR"))
    with pytest.raises(LineageError, match="VERIFIED_AWARD_REQUIRED"):
        prepare_operator_application(lineage, snapshot=current, provider_business_id=BUSINESS, association=association,
                                     target_bill_id=APRIL, amount_minor=100, prepared_by="finance reviewer",
                                     prepared_at=T0.isoformat())


@pytest.mark.parametrize("target,amount,code", [
    (APRIL, 4001, "INSUFFICIENT_USABLE_CREDIT"),
    (JANUARY, 100, "TARGET_BILL_NOT_UNPAID"),
    (UNRELATED, 100, "TARGET_BILL_SCOPE_MISMATCH"),
    (APRIL, 0, "POSITIVE_MINOR_AMOUNT_REQUIRED"),
])
def test_preparation_gates(target, amount, code):
    lineage, current, association = ready_case()
    with pytest.raises(LineageError, match=code):
        prepare_operator_application(lineage, snapshot=current, provider_business_id=BUSINESS, association=association,
                                     target_bill_id=target, amount_minor=amount, prepared_by="finance reviewer",
                                     prepared_at=T0.isoformat())


def test_preparation_refuses_over_application_of_the_bill():
    lineage, current, association = ready_case(total=40000, the_award=award(amount_minor=40000))
    with pytest.raises(LineageError, match="TARGET_BILL_OVER_APPLICATION"):
        prepare_operator_application(lineage, snapshot=current, provider_business_id=BUSINESS, association=association,
                                     target_bill_id=APRIL, amount_minor=20001, prepared_by="finance reviewer",
                                     prepared_at=T0.isoformat())


@pytest.mark.parametrize("credits,applied,expected", [
    ([raw_credit()], [], "NOT_YET_OBSERVED"),
    ([raw_credit(bills=[(APRIL, 2400)])], [(CREDIT, 2400)], "CONFIRMED_BY_READBACK"),
    ([raw_credit(bills=[(APRIL, 2400)])], [], "ONE_SIDED_UNCERTAIN"),
    ([raw_credit(bills=[(APRIL, 2000)])], [(CREDIT, 2000)], "DIFFERENT_AMOUNT_APPLIED"),
    ([raw_credit(), raw_credit(OTHER_CREDIT, bills=[(APRIL, 2400)])], [(OTHER_CREDIT, 2400)], "OTHER_CREDIT_APPLIED"),
    ([], [], "UNVERIFIABLE"),
])
def test_readback_classifies_uncertain_outcomes_without_retry(credits, applied, expected):
    instruction = prepared()
    result = confirm_operator_application(instruction, provider_business_id=BUSINESS,
                                          snapshot=later(3, credits, applied=applied))
    assert result["status"] == expected and result["retry_allowed"] is False and result["writes_attempted"] is False


def test_readback_refuses_tampering_wrong_business_and_stale_reads():
    instruction = prepared()
    with pytest.raises(LineageError, match="INVALID_INSTRUCTION"):
        confirm_operator_application({**instruction, "amount_minor": 1}, provider_business_id=BUSINESS,
                                     snapshot=later(3, [raw_credit()]))
    assert confirm_operator_application(instruction, provider_business_id=OTHER_BUSINESS,
                                        snapshot=later(3, [raw_credit()]))["status"] == "BUSINESS_MISMATCH"
    assert confirm_operator_application(instruction, provider_business_id=BUSINESS,
                                        snapshot=later(1, [raw_credit()]))["status"] == "READ_NOT_AFTER_PREPARATION"


# --- Preserved real evidence and module boundaries -----------------------------------

def test_approved_note_text_matches_the_readback_verifier_and_the_preserved_receipt():
    spec = importlib.util.spec_from_file_location("verify_ramp_comment", ROOT / "scripts/verify_ramp_comment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.NOTE == EVIDENCE_GAP_NOTE
    path = ROOT / "docs/v4/evidence/demo-path-87/human-ramp-note.json"
    # The human-posted note's committed read-back receipt is preserved byte-for-byte.
    assert sha256(path.read_bytes()).hexdigest() == "c688cfeba24a78d29d66f92842112dbc7770c1580e79ba41f05835715f8d2da2"
    receipt = json.loads(path.read_text())
    assert receipt["body"] == EVIDENCE_GAP_NOTE and receipt["write_attempted"] is False
    assert receipt["api_write_proven"] is False and receipt["actual_money_recovered"] is None


def test_new_modules_have_no_transport_or_write_path():
    for name in ("ramp_association", "ramp_case_lineage"):
        tree = ast.parse((ROOT / "uptime" / f"{name}.py").read_text())
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not imported & {"requests", "httpx", "urllib", "socket", "uptime.ramp", ".ramp", "ramp"}
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & {"post_comment", "request", "token", "dispatch", "execute"}


# --- Falsification tests from the decision93 Opus critique ---------------------------

def test_one_credit_cannot_be_counted_by_two_cases_or_split_silently():
    read = later(1, [raw_credit(bills=[(APRIL, 1000)])], applied=[(CREDIT, 1000)])
    other_case = CreditBinding(CREDIT, "award northwind 2", "claim February", "fixture:other-binding", "f" * 64)
    lineage, _, _ = contract_case((read,), registry=(BINDING, other_case))
    assert "CREDIT_BOUND_TO_MULTIPLE_CASES" in lineage["review_required"]
    assert lineage["money"]["applied_minor"] is None
    split = CreditBinding(OTHER_CREDIT, BINDING.award_id, CLAIM, "fixture:split-binding", "f" * 64)
    lineage, _, _ = contract_case((read,), registry=(BINDING, split))
    assert "AWARD_SPLIT_ACROSS_CREDITS_REQUIRES_ATTRIBUTION" in lineage["review_required"]
    lineage, _, _ = contract_case((read,), registry=(other_case,))
    assert lineage["refusals"] == ["CREDIT_BINDING_NOT_REGISTERED"]


def test_bill_side_only_application_leaves_applied_unknown():
    read = later(1, [raw_credit()], applied=[(CREDIT, 1000)])
    lineage, _, _ = contract_case((read,))
    assert stage(lineage, "APPLICATION")["reasons"] == ["RECIPROCAL_APPLICATION_CONFLICT"]
    assert lineage["money"]["applied_minor"] is None


def test_note_missing_from_a_later_complete_thread_needs_review():
    gap = identity(contract_id=None, contract_version=None, account_id=None, claim_id=None)
    first = capture(T0, base_bills(), comments={JANUARY: [
        {"id": COMMENT, "created_at": "2026-04-30T01:46:45+00:00", "message": "PRIVATE", "user_id": uid(77)}]})
    deleted = capture(T0 + timedelta(hours=1), base_bills(), comments={})
    lineage = build_lineage(gap, snapshot=first, provider_business_id=BUSINESS, finding=finding_for(first),
                            surface=note_receipt(), readbacks=((BUSINESS, deleted),))
    assert lineage["status"] == "REVIEW_REQUIRED"
    assert stage(lineage, "SURFACE")["absent_from_complete_thread_at"] == [deleted["observed_at"]]


def test_released_or_preexisting_hold_is_not_a_current_intervention():
    snapshot = capture(T0, base_bills())
    finding = finding_for(snapshot, price_binding(snapshot))
    hold = {"kind": "PAYMENT_HOLD", "object_type": "bills", "object_id": JANUARY, "origin": "PERSON_IN_RAMP_UI",
            "finding_digest": finding["finding_digest"], "requested_at": (T0 + timedelta(minutes=30)).isoformat()}
    held_bills = [raw_bill(JANUARY, inventory=True, status_summary="ON_HOLD")] + base_bills()[1:]
    held = capture(T0 + timedelta(hours=1), held_bills)
    released = capture(T0 + timedelta(hours=2), base_bills())
    lineage, _, _ = contract_case((held, released), surface=hold, credit_binding=None)
    assert stage(lineage, "SURFACE")["status"] == "HOLD_NOT_CURRENT"
    assert stage(lineage, "SURFACE")["payment_effect"] == "UNKNOWN"
    early = {**hold, "requested_at": (T0 + timedelta(hours=1, minutes=30)).isoformat()}
    lineage, _, _ = contract_case((held, capture(T0 + timedelta(hours=2), held_bills)), surface=early, credit_binding=None)
    assert stage(lineage, "SURFACE")["status"] == "HOLD_PREEXISTING_NOT_ATTRIBUTED"


def test_preparation_rechecks_lineage_and_needs_current_association():
    lineage, current, association = ready_case()
    edited = copy.deepcopy(lineage)
    edited["money"]["awarded_minor"] = 999999
    kwargs = dict(snapshot=current, provider_business_id=BUSINESS, target_bill_id=APRIL, amount_minor=100,
                  prepared_by="finance reviewer", prepared_at=T0.isoformat())
    with pytest.raises(LineageError, match="INVALID_LINEAGE"):
        prepare_operator_application(edited, association=association, **kwargs)
    stale = associate(capture(T0, base_bills()), scope(), native(), provider_business_id=BUSINESS)
    with pytest.raises(LineageError, match="CURRENT_ASSOCIATION_REQUIRED"):
        prepare_operator_application(lineage, association=stale, **kwargs)


def test_row_without_known_kind_is_never_the_case_record():
    from uptime.ramp_case_lineage import _record
    fake = {"resources": {"bills": {"status": "COMPLETE", "records": [{"id": JANUARY}]}}}
    assert _record(fake, identity()) is None


def test_concurrent_use_elsewhere_is_not_a_wrong_amount_and_executor_is_recorded():
    instruction = prepared()
    elsewhere = later(3, [raw_credit(bills=[(APRIL, 2400), (uid(61), 500)])], applied=[(CREDIT, 2400)])
    result = confirm_operator_application(instruction, provider_business_id=BUSINESS, snapshot=elsewhere,
                                          executed_by="finance reviewer")
    assert result["status"] == "CONFIRMED_CREDIT_ALSO_USED_ELSEWHERE"
    assert result["separation_of_duties"] is False and result["retry_allowed"] is False


def test_double_binding_needs_review_even_when_credit_is_not_observed():
    other_case = CreditBinding(CREDIT, "award northwind 2", "claim February", "fixture:other-binding", "f" * 64)
    lineage, _, _ = contract_case((later(1, []),), registry=(BINDING, other_case))
    assert stage(lineage, "CREDIT")["status"] == "ABSENT_FROM_COMPLETE_LIST"
    assert lineage["review_required"] == ["CREDIT_BOUND_TO_MULTIPLE_CASES"] and lineage["status"] == "REVIEW_REQUIRED"
