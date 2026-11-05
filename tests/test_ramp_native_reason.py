"""Signed mounted MOCK_HTTP reason dispatch; all records and keys are local controls."""
from copy import deepcopy
from time import time

import pytest

from uptime import ramp_native_binding as native
from uptime.auth_keys import reviewer_signature
from test_ramp_native_binding import (installed, no_network, BILL, BUSINESS, USER, OTHER, TENANT, raw)

EVIDENCE = (
    "Uptime contract review: price compliance is undetermined. Before approving this bill, "
    "obtain the governing signed terms and amendments, and verify itemized charges, service dates, "
    "quantities and tax treatment against those terms.")
EXCEPTION = (
    "Uptime contract review: a deterministic comparison against operator-attested signed terms "
    "identified a potential price exception. Before approving this bill, review the governing "
    "terms and amendments and the mapped service dates, quantities and tax treatment with the contract owner. "
    "This provisional finding depends on operator evidence; it does not establish legal entitlement.")
DISCLAIMER = " No approval, payment instruction, entitlement or realized savings is asserted.\n"


def reason(i, value="EVIDENCE_REQUIRED"):
    f = i.workspace.finding
    f["native_review_reason"] = value
    if value == "ATTESTED_PRICE_EXCEPTION":
        f.update(finding_kind="OPERATOR_PRICE_REVIEW", outcome="ELIGIBLE", stage="PREPAYMENT_REVIEW", missing=[],
                 line_findings=[{"line_id": OTHER, "billed": "120.00", "expected": "80.00", "delta": "40.00"}],
                 terms_provenance={"mode": "OPERATOR_ATTESTED", "integrity": "VERIFIED", "digest": "a"*64,
                                   "operator_context_verified": True})
        f["data_provenance"].update(classification="PROVIDER_WITH_OPERATOR_EVIDENCE", terms_mode="OPERATOR_ATTESTED",
                                    binding_digest="b"*64)
    return f


@pytest.mark.parametrize("value,message", [("EVIDENCE_REQUIRED", EVIDENCE), ("ATTESTED_PRICE_EXCEPTION", EXCEPTION)])
def test_exact_fixed_reason_bytes_signed_mounted_dispatch_and_get(installed, value, message):
    i = installed
    f = reason(i, value)
    # Neither private narrative nor a URL/amount is ever a template substitution.
    f.update(description="INJECT pay https://evil.example 999999", vendor_name="INJECT", amount="999999")
    plan = i.reviewed()
    expected = {"message": message+DISCLAIMER+plan["dedup_marker"], "message_format": "PLAIN_TEXT"}
    assert plan["wire"]["body"] == raw(expected).decode()
    assert i.execute(plan).json()["status"] == "DELIVERED"
    assert i.protocol.posts == [raw(expected)]
    assert plan["transport_provenance"] == "MOCK_HTTP"
    assert "INJECT" not in plan["wire"]["body"] and "999999" not in plan["wire"]["body"]
    assert i.protocol.calls[-1] == ("GET", f"/developer/v1/comments/bills/{BILL}")
    assert plan["actual_money_prevented"] is None and plan["actual_recovery"] is None


@pytest.mark.parametrize("fault", ["within", "unknown", "none", "list", "classification", "kind", "synthetic-mode",
    "terms-absent", "integrity", "digest", "context", "string-context", "binding-digest", "negative", "missing-outcome",
    "ambiguous", "missing", "lines", "replay", "synthetic-source"])
def test_price_reason_requires_exact_current_trusted_proof(installed, fault):
    i = installed
    f = reason(i, "ATTESTED_PRICE_EXCEPTION")
    if fault == "within": f["native_review_reason"] = "ATTESTED_PRICE_WITHIN_TERMS"
    if fault == "unknown": f["native_review_reason"] = "approve"
    if fault == "none": f["native_review_reason"] = None
    if fault == "list": f["native_review_reason"] = []
    if fault == "classification": f["data_provenance"]["classification"] = "PROVIDER_OBSERVATION"
    if fault == "kind": f["finding_kind"] = "SYNTHETIC_NEGOTIATED_PRICE"
    if fault == "synthetic-mode": f["data_provenance"]["terms_mode"] = "SYNTHETIC_NEGOTIATED"
    if fault == "terms-absent": f.pop("terms_provenance")
    if fault == "integrity": f["terms_provenance"]["integrity"] = "UNVERIFIED"
    if fault == "digest": f["terms_provenance"]["digest"] = ""
    if fault == "context": f["terms_provenance"]["operator_context_verified"] = False
    if fault == "string-context": f["terms_provenance"]["operator_context_verified"] = "true"
    if fault == "binding-digest": f["data_provenance"]["binding_digest"] = ""
    if fault == "negative": f["outcome"] = "INELIGIBLE"
    if fault == "missing-outcome": f.pop("outcome")
    if fault == "ambiguous": f["stage"] = "NEEDS_REVIEW"
    if fault == "missing": f["missing"] = ["contract"]
    if fault == "lines": f["line_findings"] = []
    if fault == "replay": f["sources"].append("DETERMINISTIC_REPLAY")
    if fault == "synthetic-source": f["sources"].append("SYNTHETIC_CUSTOMER")
    assert i.post(native.PREFIX+"/preflight", {}).status_code == 200
    assert i.post(native.PREFIX+"/prepare", {"object_type": "bills", "object_id": BILL}).status_code == 409
    assert not i.protocol.posts


@pytest.mark.parametrize("field", ["native_review_reason", "native_review_digest", "terms_provenance", "reason", "prose", "uri", "amount"])
def test_reason_proof_and_content_are_never_client_inputs(installed, field):
    i = installed
    assert i.post(native.PREFIX+"/prepare", {"object_type": "bills", "object_id": BILL,
                                           field: "ATTESTED_PRICE_EXCEPTION"}).status_code == 422
    assert not i.protocol.calls


@pytest.mark.parametrize("when", ["before-review", "before-execute", "after-discussion", "during-final-read"])
@pytest.mark.parametrize("change", ["revocation", "proof-version", "reason-removed", "outcome", "line-digest"])
def test_reason_proof_recomputed_at_signing_and_final_wire(installed, when, change):
    i = installed
    f = reason(i, "ATTESTED_PRICE_EXCEPTION")
    plan = i.prepare() if when == "before-review" else i.reviewed()
    def drift():
        if change == "revocation": f["terms_provenance"]["operator_context_verified"] = False
        if change == "proof-version": f["terms_provenance"]["digest"] = "c"*64
        if change == "reason-removed": f.pop("native_review_reason", None)
        if change == "outcome": f["outcome"] = "INELIGIBLE"
        if change == "line-digest": f["data_provenance"]["binding_digest"] = "c"*64
    if when == "after-discussion": i.protocol.after_discussion = drift
    elif when == "during-final-read": i.protocol.after_discussion = lambda: setattr(i.protocol, "after_bill", drift)
    elif when == "before-review":
        expiry = int(time())+240
        message = i.binding.flow.review_message(plan["id"], reviewer=USER, expires_at=expiry)
        drift()
        response = i.post(f"{native.PREFIX}/actions/{plan['id']}/review", {
            "expires_at": expiry, "proof": reviewer_signature(i.key, message)})
        assert response.status_code == 409
        assert not i.protocol.posts
        return
    else: drift()
    response = i.execute(plan)
    assert response.status_code == 409 or response.json()["status"] == "UNCERTAIN"
    assert not i.protocol.posts


def test_legacy_reviewed_outbox_bytes_and_read_order_survive_new_resolver(installed):
    i = installed
    plan = i.reviewed()
    original = plan["wire"]["body"]
    assert "native_review_reason" not in plan
    reason(i)  # A resolver upgrade must not rewrite a previously signed comment.
    i.protocol.calls.clear()
    assert i.execute(plan).json()["status"] == "DELIVERED"
    assert i.protocol.posts == [original.encode()]
    assert i.protocol.calls == [
        ("GET", f"/developer/v1/bills/{BILL}"),
        ("GET", f"/developer/v1/comments/bills/{BILL}"),
        ("GET", "/developer/v1/business"),
        ("GET", f"/developer/v1/bills/{BILL}"),
        ("POST", f"/developer/v1/comments/bills/{BILL}"),
        ("GET", f"/developer/v1/comments/bills/{BILL}"),
    ]


def test_reason_post_lost_reply_reconciles_exact_bytes_without_resend(installed):
    i = installed
    reason(i)
    plan = i.reviewed()
    i.protocol.uncertain = i.protocol.hide_comments = True
    assert i.execute(plan).json()["status"] == "UNCERTAIN"
    assert i.execute(plan).status_code == 409
    i.protocol.hide_comments = False
    assert i.post(f"{native.PREFIX}/actions/{plan['id']}/reconcile", {}).json()["status"] == "DELIVERED"
    assert i.protocol.posts == [plan["wire"]["body"].encode()]


@pytest.mark.parametrize("revocation", [None, "key", "package", "evidence-bytes"])
def test_signed_finance_evidence_resolved_again_at_mounted_wire(installed, monkeypatch, revocation):
    """Real local finance signature/custody/evaluator; test-only ROOT projection adapter.

    The finance packet contains synthetic test documents. MOCK_HTTP is never live
    evidence. This exercises the agreed resolver contract without editing ROOT.
    """
    from types import SimpleNamespace
    from uptime.contracts import fingerprint
    from uptime.ramp_findings import evaluate_snapshot
    from uptime.ramp_records import sync_records
    from uptime.ramp_workspace import RampWorkspace
    from uptime.storage import initialize
    from test_ramp_records_v4 import Reader, money
    import test_ramp_terms_store as finance
    i = installed
    reader = Reader()
    bill = reader.rows["bills"][0]
    bill.update(id=BILL, amount=money(12000), issued_at="2026-11-01T00:00:00Z")
    bill["inventory_line_items"][0].update(quantity=2, unit_price=money(6000), amount=money(12000))
    i.protocol.record = deepcopy(bill)
    snapshot = sync_records(reader)
    initialize(i.db)
    workspace = RampWorkspace(SimpleNamespace(path=i.db, tenant=TENANT, mode="sandbox"))
    workspace.import_observation(snapshot, BUSINESS)
    for key, value in {"TENANT": TENANT, "BIZ": BUSINESS, "BILL": BILL}.items():
        monkeypatch.setattr(finance, key, value)
    store, key, signer, packet, directory = finance.package(i.path, (i.db, workspace, snapshot), "OPERATOR_ATTESTED")
    store.register(key)
    store.install(packet, signer.sign(packet.signing_bytes()), directory)

    def resolve(object_type, object_id):
        bindings, omissions = store.resolve(TENANT, BUSINESS, snapshot)
        if omissions or len(bindings) != 1 or (object_type, object_id) != ("bills", BILL):
            raise PermissionError("No current exact signed evidence")
        binding = bindings[0]
        if binding.terms_mode != "OPERATOR_ATTESTED" or not binding.signed_terms_attested:
            raise PermissionError("Actual operator-scoped terms required")
        finding = next(r for r in evaluate_snapshot(snapshot, bindings=bindings)
                       if r["provider_object_type"] == "bills" and r["provider_id"] == BILL)
        assert finding["outcome"] == "ELIGIBLE" and finding["amount"] == "40.00"
        return dict(finding, workspace_tenant=TENANT, business_id=BUSINESS,
                    observed_at=snapshot["observed_at"], sources=["LIVE_RAMP_SANDBOX"],
                    finding_digest=fingerprint([snapshot["checksum"], binding.terms_evidence_digest, finding["outcome"]]),
                    native_review_reason="ATTESTED_PRICE_EXCEPTION", terms_provenance={
                        "mode": "OPERATOR_ATTESTED", "integrity": "VERIFIED", "operator_context_verified": True,
                        "digest": binding.terms_evidence_digest})
    i.binding.workspace = SimpleNamespace(tenant=TENANT, mode="sandbox", _observation=workspace._observation,
                                         record_for_native=resolve)
    plan = i.reviewed()
    if revocation:
        def revoke():
            if revocation == "evidence-bytes":
                finance.private(directory/packet.versions[0].contract_sha256, b"changed control evidence")
            else:
                store.revoke(revocation, key.subject if revocation == "key" else packet.package_id, TENANT, BUSINESS)
        i.protocol.after_discussion = revoke
    response = i.execute(plan)
    if revocation:
        assert response.status_code in {403, 409} or response.json()["status"] == "UNCERTAIN"
        assert not i.protocol.posts
    else:
        assert response.json()["status"] == "DELIVERED", response.text
        assert i.protocol.posts == [raw({"message": EXCEPTION+DISCLAIMER+plan["dedup_marker"],
                                         "message_format": "PLAIN_TEXT"})]


@pytest.mark.parametrize("fault", ["price-kind", "price-class", "price-outcome", "terms-proof"])
def test_missing_evidence_reason_cannot_hide_a_price_finding(installed, fault):
    i = installed
    f = reason(i)
    if fault == "price-kind": f["finding_kind"] = "OPERATOR_PRICE_REVIEW"
    if fault == "price-class": f["data_provenance"]["classification"] = "PROVIDER_WITH_OPERATOR_EVIDENCE"
    if fault == "price-outcome": f["outcome"] = "ELIGIBLE"
    if fault == "terms-proof": f["terms_provenance"] = {"mode": "OPERATOR_ATTESTED"}
    assert i.post(native.PREFIX+"/preflight", {}).status_code == 200
    assert i.post(native.PREFIX+"/prepare", {"object_type": "bills", "object_id": BILL}).status_code == 409
    assert not i.protocol.posts


def test_recomputation_clock_and_untrusted_reason_digest_do_not_change_evidence(installed):
    i = installed
    f = reason(i, "ATTESTED_PRICE_EXCEPTION")
    f["native_review_digest"] = "untrusted-not-a-digest"
    plan = i.reviewed()
    assert plan["native_review_digest"] != f["native_review_digest"]
    f["data_provenance"]["evaluated_at"] = "new observation of unchanged evidence"
    assert i.execute(plan).json()["status"] == "DELIVERED"


def test_changed_reason_requires_new_review_and_cannot_duplicate_delivery(installed):
    i = installed
    reason(i)
    original = i.reviewed()
    reason(i, "ATTESTED_PRICE_EXCEPTION")
    path = native.PREFIX+"/prepare"
    current = i.post(path, {"object_type": "bills", "object_id": BILL}).json()
    assert current["id"] == original["id"]  # Same underlying finding, not a second logical delivery.
    assert current["review_digest"] != original["review_digest"] and current["status"] == "PREPARED"
    assert i.execute(original).status_code == 409
    assert i.execute(current).status_code == 409  # New mandate alone cannot replace workflow review.
    expiry = int(time())+240
    message = i.binding.flow.review_message(current["id"], reviewer=USER, expires_at=expiry)
    reviewed = i.post(f"{native.PREFIX}/actions/{current['id']}/review", {
        "expires_at": expiry, "proof": reviewer_signature(i.key, message)}).json()
    assert i.execute(reviewed).json()["status"] == "DELIVERED"
    i.workspace.finding["terms_provenance"]["digest"] = "c"*64
    assert i.post(path, {"object_type": "bills", "object_id": BILL}).status_code == 409
    assert len(i.protocol.posts) == 1
