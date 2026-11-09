from datetime import timedelta
import json
import sqlite3
from uuid import UUID

import pytest

from uptime.auth_keys import generate_reviewer_key, public_bytes, reviewer_signature
from uptime.ramp import RampError
from uptime.ramp_workflow import (RampWorkflow, SimulatedWorkflowProvider, WorkflowError, WorkflowReviewer,
                                  inspector_url, register_ramp_workflow)
from uptime.ramp_webhooks import RampWebhookInbox
from test_ramp_workflow_webhooks import (NOW, BUSINESS, REQUEST_ID, TRIGGER, RESET, activate, deployment,
                                         native_event, signed)

BILL = str(UUID(int=501))
DRAFT = str(UUID(int=502))
TRANSACTION = str(UUID(int=503))
FINDING = "a"*64
TENANT = "test-tenant"


def make_finding(object_type, object_id):
    return {"provider_object_type": object_type, "provider_id": object_id, "business_id": BUSINESS,
            "workspace_tenant": TENANT, "finding_digest": FINDING, "sources": ["SYNTHETIC_CUSTOMER"],
            "observed_at": NOW.isoformat()}


@pytest.fixture
def setup(tmp_path):
    records = {("bills", BILL): {"id": BILL, "status": "OPEN", "approval_status": "PENDING"},
               ("draft-bills", DRAFT): {"id": DRAFT, "status": "DRAFT"},
               ("transactions", TRANSACTION): {"id": TRANSACTION, "state": "CLEARED"},
               ("unified-requests", REQUEST_ID): {"id": REQUEST_ID, "request_status": "SUBMITTED"}}
    findings = {key: make_finding(*key) for key in records}
    inbox = RampWebhookInbox(tmp_path/"workflow.db", deployment(), clock=lambda: NOW)
    activate(inbox)
    inbox.receive(*signed(native_event()))
    provider = SimulatedWorkflowProvider(business_id=BUSINESS, records=records, clock=lambda: NOW,
                                        contexts={TRIGGER: {"node_id": "node-external-review", "service_key": "Uptime-v4"}})
    key = generate_reviewer_key()
    reviewers = {"test-reviewer": WorkflowReviewer(public_bytes(key))}
    def create():
        return RampWorkflow(inbox.path, tenant=TENANT, business_id=BUSINESS, finding_resolver=lambda t, i: findings[t, i],
                            reviewers=reviewers, inbox=inbox, inspector_origins=("https://inspector.example",), clock=lambda: NOW)
    return create(), provider, key, findings, inbox, create


def review(flow, key, plan):
    expires = int(NOW.timestamp())+240
    message = flow.review_message(plan["id"], reviewer="test-reviewer", expires_at=expires)
    return flow.review(plan["id"], reviewer="test-reviewer", expires_at=expires, proof=reviewer_signature(key, message))


@pytest.mark.parametrize("obj,ident", [("bills", BILL), ("draft-bills", DRAFT), ("transactions", TRANSACTION)])
def test_exact_native_discussion_lifecycle_durable_dedup(setup, obj, ident):
    flow, provider, key, _, _, restart = setup
    plan = flow.prepare_comment(obj, ident, provider=provider)
    assert plan["path"] == f"/developer/v1/comments/{obj}/{ident}"
    assert plan["method"] == "POST"
    assert plan["approval_trigger_instance_id"] is None
    with pytest.raises(WorkflowError, match="review"):
        flow.execute(plan["id"], provider=provider)
    review(flow, key, plan)
    result = flow.execute(plan["id"], provider=provider)
    assert result["status"] == "DELIVERED"
    assert result["remote_state"]["verification"] == "EXACT_DISCUSSION_GET"
    assert result["transport_provenance"] == "SIMULATED_RAMP"
    assert result["actual_money_prevented"] is None and result["actual_recovery"] is None
    assert result["remote_id"] == provider.threads[obj, ident][0]["id"]
    assert result["dedup_marker"] in provider.threads[obj, ident][0]["message"]
    assert restart().execute(plan["id"], provider=provider)["status"] == "DELIVERED"
    assert restart().prepare_comment(obj, ident, provider=provider)["id"] == result["id"]
    assert len(provider.calls) == 1


@pytest.mark.parametrize("change", ["finding", "remote", "grant", "business", "signature", "reviewer", "expiry"])
def test_review_binds_exact_finding_state_capabilities_and_authority(setup, change):
    flow, provider, key, findings, _, _ = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    if change == "finding":
        findings["bills", BILL]["finding_digest"] = "b"*64
    elif change == "remote":
        provider.records["bills", BILL]["status"] = "PAID"
    elif change == "grant":
        provider._scopes -= {"bills:write"}
    elif change == "business":
        provider.business_id = str(UUID(int=999))
    elif change == "reviewer":
        flow.reviewers.clear()
    elif change == "expiry":
        flow.clock = lambda: NOW+timedelta(minutes=6)
    elif change == "signature":
        with sqlite3.connect(flow.path) as db:
            data = json.loads(db.execute("SELECT review FROM rw_outbox").fetchone()[0])
            data["proof"] = "0"*128
            db.execute("UPDATE rw_outbox SET review=?", (json.dumps(data),))
    with pytest.raises(RampError):
        flow.execute(plan["id"], provider=provider)
    assert provider.calls == []


def test_signature_for_other_plan_fails(setup):
    flow, provider, key, *_ = setup
    first = flow.prepare_comment("bills", BILL, provider=provider)
    second = flow.prepare_comment("draft-bills", DRAFT, provider=provider)
    expires = int(NOW.timestamp())+120
    proof = reviewer_signature(key, flow.review_message(first["id"], reviewer="test-reviewer", expires_at=expires))
    with pytest.raises(WorkflowError, match="signature"):
        flow.review(second["id"], reviewer="test-reviewer", expires_at=expires, proof=proof)
    assert provider.calls == []


def test_exact_lookup_never_falls_back_to_unrelated_object(setup):
    flow, provider, _, findings, *_ = setup
    del findings["bills", BILL]
    with pytest.raises(WorkflowError, match="no fallback"):
        flow.prepare_comment("bills", BILL, provider=provider)
    assert provider.calls == []
    assert ("transactions", TRANSACTION) in findings


@pytest.mark.parametrize("field,value", [("business_id", str(UUID(int=999))), ("workspace_tenant", "other"),
                                         ("provider_id", TRANSACTION), ("finding_digest", "missing"),
                                         ("observed_at", (NOW-timedelta(days=3)).isoformat())])
def test_bad_or_stale_finding_is_not_authority(setup, field, value):
    flow, provider, _, findings, *_ = setup
    findings["bills", BILL][field] = value
    with pytest.raises(RampError):
        flow.prepare_comment("bills", BILL, provider=provider)


def test_uncertain_post_then_readback_recovers_without_second_post(setup, monkeypatch):
    flow, provider, key, _, _, restart = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    post = provider.post_comment
    def timeout_after_write(p):
        post(p)
        raise TimeoutError("PRIVATE_RESPONSE_WITH_TOKEN")
    monkeypatch.setattr(provider, "post_comment", timeout_after_write)
    assert flow.execute(plan["id"], provider=provider)["status"] == "UNCERTAIN"
    with pytest.raises(WorkflowError, match="reconcile"):
        restart().execute(plan["id"], provider=provider)
    result = restart().reconcile(plan["id"], provider=provider)
    assert result["status"] == "DELIVERED"
    assert len(provider.calls) == 1
    assert b"PRIVATE_RESPONSE_WITH_TOKEN" not in flow.path.read_bytes()


def test_uncertain_absence_never_authorizes_resend(setup, monkeypatch):
    flow, provider, key, *_ = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    def timeout(p):
        raise TimeoutError
    monkeypatch.setattr(provider, "post_comment", timeout)
    assert flow.execute(plan["id"], provider=provider)["status"] == "UNCERTAIN"
    assert flow.reconcile(plan["id"], provider=provider)["status"] == "UNCERTAIN"
    with pytest.raises(WorkflowError, match="reconcile"):
        flow.execute(plan["id"], provider=provider)
    provider.observed_at = (NOW-timedelta(minutes=1)).isoformat()
    with pytest.raises(WorkflowError, match="already attempted"):
        flow.prepare_comment("bills", BILL, provider=provider)


def test_same_content_wrong_remote_comment_id_is_not_readback(setup, monkeypatch):
    flow, provider, key, *_ = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    post = provider.post_comment
    def mismatch(p):
        result = post(p)
        result["id"] = str(UUID(int=991))
        return result
    monkeypatch.setattr(provider, "post_comment", mismatch)
    with pytest.raises(WorkflowError, match="ID"):
        flow.execute(plan["id"], provider=provider)
    assert flow.get(plan["id"])["status"] == "UNCERTAIN"
    assert len(provider.calls) == 1


def test_crashed_dispatch_is_reconcile_only(setup):
    flow, provider, key, *_ = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    with sqlite3.connect(flow.path) as db:
        db.execute("UPDATE rw_outbox SET status='DISPATCHING'")
    with pytest.raises(WorkflowError, match="reconcile"):
        flow.execute(plan["id"], provider=provider)
    assert flow.reconcile(plan["id"], provider=provider)["status"] == "DISPATCHING"
    assert provider.calls == []


def test_changed_plan_invalidates_signed_review(setup):
    flow, provider, key, findings, *_ = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    provider.records["bills", BILL]["approval_status"] = "APPROVED"
    updated = flow.prepare_comment("bills", BILL, provider=provider)
    assert updated["id"] == plan["id"]
    assert updated["review_digest"] != plan["review_digest"]
    assert updated["status"] == "PREPARED"
    with pytest.raises(WorkflowError):
        flow.execute(updated["id"], provider=provider)


def test_metadata_uses_true_trigger_and_informational_response(setup):
    flow, provider, key, _, _, _ = setup
    plan = flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/cases/local-case")
    assert plan["object_id"] == REQUEST_ID and plan["approval_trigger_instance_id"] == TRIGGER
    assert plan["body"] == {"status": "Human review required", "url": "https://inspector.example/cases/local-case"}
    review(flow, key, plan)
    result = flow.execute(plan["id"], provider=provider)
    assert result["status"] == "DELIVERED"
    assert result["remote_id"] == TRIGGER
    assert result["remote_state"]["verification"] == "PATCH_RESPONSE_ONLY"
    with pytest.raises(RampError):
        flow.prepare_metadata(BILL, provider=provider, url="https://inspector.example/cases/local-case")


@pytest.mark.parametrize("url", ["http://inspector.example/case", "https://user:password@inspector.example/case",
    "https://other.example/case", "https://inspector.example/case?token=private", "https://inspector.example/case#private",
    "https://inspector.example:invalid/case", "https://inspector.example/%0a"])
def test_inspector_urls_cannot_export_secret_links(setup, url):
    flow, provider, *_ = setup
    with pytest.raises(WorkflowError):
        flow.prepare_metadata(TRIGGER, provider=provider, url=url)


@pytest.mark.parametrize("status", ["Approved", "Payment authorized", "Savings found", "Rejected"])
def test_metadata_never_implies_financial_decision(setup, status):
    flow, provider, *_ = setup
    with pytest.raises(WorkflowError):
        flow.prepare_metadata(TRIGGER, provider=provider, status=status, url="https://inspector.example/case")


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_financial_decision_only_explicit_simulation(setup, action):
    flow, provider, key, *_ = setup
    plan = flow.prepare_decision(TRIGGER, provider=provider, action=action)
    assert plan["body"] == {"action": action}
    review(flow, key, plan)
    result = flow.execute(plan["id"], provider=provider)
    assert result["status"] == "DELIVERED" and result["transport_provenance"] == "SIMULATED_RAMP"
    assert result["remote_state"]["verification"] == "SIMULATED_RESPONSE_ONLY"
    with pytest.raises(WorkflowError, match="already attempted"):
        flow.prepare_decision(TRIGGER, provider=provider, action="reject" if action == "approve" else "approve")


@pytest.mark.parametrize("kind", ["metadata", "decision"])
def test_reset_blocks_prepared_reviewed_and_restarted_actions(setup, kind):
    flow, provider, key, _, inbox, restart = setup
    plan = (flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/case") if kind == "metadata"
            else flow.prepare_decision(TRIGGER, provider=provider, action="approve"))
    review(flow, key, plan)
    inbox.receive(*signed(native_event(ident=222, kind=RESET)))
    with pytest.raises(RampError):
        restart().execute(plan["id"], provider=provider)
    assert not provider.calls


def test_reset_during_preflight_prevents_mutation(setup, monkeypatch):
    flow, provider, key, _, inbox, _ = setup
    plan = flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/case")
    review(flow, key, plan)
    read = provider.context
    def reset_during_read(trigger):
        result = read(trigger)
        inbox.receive(*signed(native_event(ident=222, kind=RESET)))
        return result
    monkeypatch.setattr(provider, "context", reset_during_read)
    with pytest.raises(RampError):
        flow.execute(plan["id"], provider=provider)
    assert provider.calls == []


def test_metadata_uncertainty_does_not_invent_get_endpoint_or_retry(setup, monkeypatch):
    flow, provider, key, *_ = setup
    plan = flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/case")
    review(flow, key, plan)
    def lost(p):
        raise TimeoutError
    monkeypatch.setattr(provider, "patch_metadata", lost)
    assert flow.execute(plan["id"], provider=provider)["status"] == "UNCERTAIN"
    assert flow.reconcile(plan["id"], provider=provider)["status"] == "UNCERTAIN"


def test_root_mount_tenant_boundary(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from uptime.contracts import Principal
    flow, provider, key, *_ = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    class Auth:
        def actor(self):
            return Principal("other", "test-reviewer", "reviewer")
        reviewer = actor
    app = FastAPI()
    register_ramp_workflow(app, flow, provider, Auth())
    client = TestClient(app)
    assert client.get(f"/api/ramp/workflow/actions/{plan['id']}").status_code == 403
    assert client.post("/webhooks/ramp", json={}).status_code == 404


def test_generic_workflow_ignores_native_reason_extension_and_preserves_bytes(setup):
    flow, provider, key, findings, _, _ = setup
    original = flow.prepare_comment("bills", BILL, provider=provider)
    findings["bills", BILL].update(native_review_reason="ATTESTED_PRICE_EXCEPTION", native_review_digest="b"*64)
    current = flow.prepare_comment("bills", BILL, provider=provider)
    assert current == original
    assert current["body"] == {"message": (
        f"Uptime informational finding for bills/{BILL}. Finding SHA-256: {FINDING}. "
        "Evidence requires human review. No approval, payment instruction, entitlement or realized savings is asserted.\n"
        + current["dedup_marker"]), "message_format": "PLAIN_TEXT"}
    review(flow, key, current)
    assert flow.execute(current["id"], provider=provider)["status"] == "DELIVERED"


def test_concurrent_workers_dispatch_at_most_once(setup, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    flow, provider, key, _, _, restart = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    gate = Barrier(2)
    read = provider.read_object
    def together(*args):
        result = read(*args)
        gate.wait(timeout=5)
        return result
    monkeypatch.setattr(provider, "read_object", together)
    def execute():
        try:
            return restart().execute(plan["id"], provider=provider)["status"]
        except RampError:
            return "CONCURRENT_DISPATCH_BLOCKED"
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: execute(), range(2)))
    assert "DELIVERED" in results
    assert len(provider.calls) == 1


def test_process_crash_after_remote_write_keeps_durable_uncertainty(setup, monkeypatch):
    flow, provider, key, _, _, restart = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    post = provider.post_comment
    def crash(p):
        post(p)
        raise KeyboardInterrupt
    monkeypatch.setattr(provider, "post_comment", crash)
    with pytest.raises(KeyboardInterrupt):
        flow.execute(plan["id"], provider=provider)
    assert restart().get(plan["id"])["status"] == "DISPATCHING"
    assert restart().reconcile(plan["id"], provider=provider)["status"] == "DELIVERED"
    assert len(provider.calls) == 1


def test_uncertain_prior_finding_cannot_be_bypassed_with_new_finding(setup):
    flow, provider, key, findings, *_ = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    with sqlite3.connect(flow.path) as db:
        db.execute("UPDATE rw_outbox SET status='UNCERTAIN'")
    findings["bills", BILL]["finding_digest"] = "c"*64
    with pytest.raises(WorkflowError, match="reconciled first"):
        flow.prepare_comment("bills", BILL, provider=provider)


def test_stored_plan_tampering_detected_before_dispatch(setup):
    flow, provider, key, *_ = setup
    plan = flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/case")
    review(flow, key, plan)
    with sqlite3.connect(flow.path) as db:
        body = json.loads(db.execute("SELECT plan FROM rw_outbox").fetchone()[0])
        body["body"]["status"] = "Evidence available"
        db.execute("UPDATE rw_outbox SET plan=?", (json.dumps(body),))
    with pytest.raises(WorkflowError, match="integrity"):
        flow.execute(plan["id"], provider=provider)
    assert provider.calls == []


def test_reset_receipt_does_not_rewrite_prior_delivery_history(setup):
    flow, provider, key, _, inbox, _ = setup
    plan = flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/case")
    review(flow, key, plan)
    assert flow.execute(plan["id"], provider=provider)["trigger_current"] is True
    inbox.receive(*signed(native_event(ident=222, kind=RESET)))
    result = flow.get(plan["id"])
    assert result["status"] == "DELIVERED" and result["trigger_current"] is False


def test_existing_exact_dedup_marker_prevents_post(setup):
    flow, provider, key, *_ = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    provider.post_comment(plan)
    assert flow.execute(plan["id"], provider=provider)["status"] == "DELIVERED"
    assert len(provider.calls) == 1


def test_conflicting_remote_marker_requires_manual_resolution(setup):
    flow, provider, key, *_ = setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    provider.post_comment(plan)
    provider.threads["bills", BILL][0]["message"] += " altered"
    with pytest.raises(WorkflowError, match="conflicts"):
        flow.execute(plan["id"], provider=provider)
    assert len(provider.calls) == 1
