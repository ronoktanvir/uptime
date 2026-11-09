"""Real contract adapter with injected httpx.MockTransport; no live HTTP."""
from copy import deepcopy
from datetime import timedelta
import json
from uuid import UUID

import httpx
import pytest

from uptime.auth_keys import generate_reviewer_key, public_bytes
from uptime.ramp import ORIGIN, RampError
from uptime.ramp_webhooks import RampWebhookInbox
from uptime.ramp_workflow import (CONTEXT_SCOPES, RampWorkflow, ScopedSandboxWorkflowProvider,
                                  ProviderFailure, WorkflowError, WorkflowReviewer)
from test_ramp_workflow import BILL, DRAFT, TRANSACTION, TENANT, FINDING, make_finding, review
from test_ramp_workflow_webhooks import NOW, BUSINESS, REQUEST_ID, TRIGGER, activate, deployment, native_event, signed

PROGRAM = str(UUID(int=601))
FORM = str(UUID(int=602))
USER = str(UUID(int=603))
COMMENT = str(UUID(int=604))
TOKEN = "test-only-token-never-live"


class NativeHTTP:
    def __init__(self):
        self.calls, self.comments = [], {}
        self.records = {
            f"/developer/v1/bills/{BILL}": {"id": BILL, "status": "OPEN", "approval_status": "PENDING"},
            f"/developer/v1/bills/drafts/{DRAFT}": {"id": DRAFT, "status": "DRAFT", "approval_status": "PENDING"},
            f"/developer/v1/transactions/{TRANSACTION}": {"id": TRANSACTION, "state": "CLEARED"},
            f"/developer/v1/unified-requests/{REQUEST_ID}": {"id": REQUEST_ID, "request_status": "SUBMITTED", "deleted_at": None,
                "custom_form_collection_response_uuid": FORM, "spend_intent": {"uuid": PROGRAM, "name": "Test program", "logo_id": "CUSTOM"}},
            f"/developer/v1/custom-form/collections/responses/{FORM}": {"id": FORM, "custom_form_collection_response": {}},
            f"/developer/v1/spend-programs/{PROGRAM}": {"id": PROGRAM},
            f"/developer/v1/spend-programs/{PROGRAM}/workflow-nodes": {"workflow_nodes": [
                {"node_id": "node-external-review", "service_key": "Uptime-v4", "next_node_id": None, "name": "External review"}]},
        }
        self.lost_post = False
        self.invisible_comment = False
        self.metadata_wrong_id = False

    def __call__(self, request):
        assert str(request.url).startswith(ORIGIN+"/developer/v1/")
        assert request.headers["authorization"] == "Bearer "+TOKEN
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, dict(request.url.params), body))
        path = request.url.path
        if request.method == "GET" and path in self.records:
            if path.endswith("workflow-nodes"):
                assert request.url.params["service_key"] == "Uptime-v4"
            return httpx.Response(200, json=deepcopy(self.records[path]))
        if "/comments/" in path:
            if request.method == "GET":
                return httpx.Response(200, json={"data": [] if self.invisible_comment else self.comments.get(path, []), "page": {"next": None}})
            if request.method == "POST":
                assert set(body) == {"message", "message_format"}
                assert body["message_format"] == "PLAIN_TEXT"
                result = {"id": COMMENT, "message": body["message"], "created_at": NOW.isoformat(), "user_id": USER}
                self.comments.setdefault(path, []).append(result)
                if self.lost_post:
                    raise httpx.ReadTimeout("private provider response and token", request=request)
                return httpx.Response(201, json=result)
        if path == f"/developer/v1/blank-canvas-approvals/{TRIGGER}/metadata" and request.method == "PATCH":
            return httpx.Response(200, json={"approval_trigger_instance_id": BILL if self.metadata_wrong_id else TRIGGER, **body})
        return httpx.Response(404, json={"private": "this body must never leak"})


@pytest.fixture
def adapter_setup(tmp_path):
    native = NativeHTTP()
    client = httpx.Client(transport=httpx.MockTransport(native), trust_env=False)
    provider = ScopedSandboxWorkflowProvider(business_id=BUSINESS, access_token=TOKEN,
        granted_scopes={"bills:read", "bills:write", "transactions:read", "transactions:write"} | CONTEXT_SCOPES,
        observed_at=NOW.isoformat(), http=client, clock=lambda: NOW)
    key = generate_reviewer_key()
    box = RampWebhookInbox(tmp_path/"workflow.db", deployment(), clock=lambda: NOW)
    activate(box)
    box.receive(*signed(native_event()))
    flow = RampWorkflow(box.path, tenant=TENANT, business_id=BUSINESS, finding_resolver=make_finding,
        reviewers={"test-reviewer": WorkflowReviewer(public_bytes(key))}, inbox=box,
        inspector_origins=("https://inspector.example",), clock=lambda: NOW)
    yield flow, provider, native, key
    client.close()


@pytest.mark.parametrize("obj,ident", [("bills", BILL), ("draft-bills", DRAFT), ("transactions", TRANSACTION)])
def test_genuine_adapter_native_comment_post_exact_get_and_scope(adapter_setup, obj, ident):
    flow, provider, native, key = adapter_setup
    plan = flow.prepare_comment(obj, ident, provider=provider)
    review(flow, key, plan)
    result = flow.execute(plan["id"], provider=provider)
    assert result["status"] == "DELIVERED"
    assert result["remote_id"] == COMMENT
    assert result["transport_provenance"] == "MOCK_HTTP"
    calls = [(method, path) for method, path, _, _ in native.calls]
    path = f"/developer/v1/comments/{obj}/{ident}"
    post = calls.index(("POST", path))
    assert calls[post+1] == ("GET", path)
    assert calls.count(("POST", path)) == 1
    assert TOKEN not in flow.path.read_text(errors="ignore")


def test_procurement_context_uses_actual_refs_and_verified_node(adapter_setup):
    flow, provider, native, key = adapter_setup
    plan = flow.prepare_metadata(TRIGGER, provider=provider, status="Evidence available", url="https://inspector.example/cases/test")
    assert [p for m, p, _, _ in native.calls][-4:] == [
        f"/developer/v1/unified-requests/{REQUEST_ID}",
        f"/developer/v1/custom-form/collections/responses/{FORM}",
        f"/developer/v1/spend-programs/{PROGRAM}",
        f"/developer/v1/spend-programs/{PROGRAM}/workflow-nodes"]
    assert plan["context"]["form_id"] == FORM
    review(flow, key, plan)
    result = flow.execute(plan["id"], provider=provider)
    assert result["status"] == "DELIVERED"
    assert result["remote_id"] == TRIGGER != REQUEST_ID != BILL
    assert result["remote_state"]["verification"] == "PATCH_RESPONSE_ONLY"
    assert native.calls[-1][0] == "PATCH"
    assert native.calls[-1][3] == {"status": "Evidence available", "url": "https://inspector.example/cases/test"}
    assert not any("metadata" in p and m == "GET" for m, p, _, _ in native.calls)


@pytest.mark.parametrize("bad", ["node", "key", "program", "form", "terminal", "guessed_reference"])
def test_no_assumed_procurement_context(adapter_setup, bad):
    flow, provider, native, _ = adapter_setup
    nodes = native.records[f"/developer/v1/spend-programs/{PROGRAM}/workflow-nodes"]
    if bad == "node":
        nodes["workflow_nodes"][0]["node_id"] = "other-node"
    elif bad == "key":
        nodes["workflow_nodes"][0]["service_key"] = "uptime-v4"
    elif bad == "program":
        native.records[f"/developer/v1/spend-programs/{PROGRAM}"]["id"] = BILL
    elif bad == "form":
        native.records[f"/developer/v1/custom-form/collections/responses/{FORM}"]["id"] = BILL
    elif bad == "terminal":
        native.records[f"/developer/v1/unified-requests/{REQUEST_ID}"]["request_status"] = "APPROVED"
    else:
        obj = native.records[f"/developer/v1/unified-requests/{REQUEST_ID}"]
        obj["spend_program_id"] = PROGRAM
        obj.pop("spend_intent")
    with pytest.raises(RampError):
        flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/cases/test")
    assert all(m == "GET" for m, _, _, _ in native.calls)


def test_actual_assigned_spend_intent_overrides_display_spend_intent(adapter_setup):
    flow, provider, native, _ = adapter_setup
    request = native.records[f"/developer/v1/unified-requests/{REQUEST_ID}"]
    request["assigned_spend_intent"] = request["spend_intent"]
    request["spend_intent"] = {"uuid": BILL}
    plan = flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/case")
    assert plan["context"]["spend_program_id"] == PROGRAM


def test_missing_grants_do_not_use_another_available_object(adapter_setup):
    flow, provider, native, _ = adapter_setup
    provider._scopes -= {"bills:write"}
    with pytest.raises(WorkflowError, match="scopes"):
        flow.prepare_comment("bills", BILL, provider=provider)
    assert native.calls == []
    assert "transactions:write" in provider._scopes


def test_real_adapter_financial_decisions_disabled_even_with_blank_canvas_grant(adapter_setup):
    flow, provider, native, _ = adapter_setup
    with pytest.raises(WorkflowError, match="simulated"):
        flow.prepare_decision(TRIGGER, provider=provider, action="approve")
    with pytest.raises(WorkflowError, match="disabled"):
        provider.decide({"body": {"action": "approve"}})
    assert native.calls == []


def test_signed_fixture_cannot_unlock_real_transport_label(adapter_setup):
    flow, provider, native, _ = adapter_setup
    provider.transport_provenance = "LIVE_RAMP_SANDBOX"
    with pytest.raises(WorkflowError, match="Simulated webhook"):
        flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/case")
    with pytest.raises(WorkflowError, match="Synthetic findings"):
        flow.prepare_comment("bills", BILL, provider=provider)
    assert native.calls == []


def test_mock_http_timeout_reconciles_on_exact_native_thread(adapter_setup):
    flow, provider, native, key = adapter_setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    native.lost_post = True
    result = flow.execute(plan["id"], provider=provider)
    assert result["status"] == "UNCERTAIN" and result["remote_id"] is None
    assert flow.reconcile(plan["id"], provider=provider)["remote_id"] == COMMENT
    assert sum(m == "POST" for m, _, _, _ in native.calls) == 1
    assert b"private provider" not in flow.path.read_bytes()


def test_read_replica_delay_is_not_success_or_resend(adapter_setup):
    flow, provider, native, key = adapter_setup
    plan = flow.prepare_comment("bills", BILL, provider=provider)
    review(flow, key, plan)
    native.invisible_comment = True
    result = flow.execute(plan["id"], provider=provider)
    assert result["status"] == "UNCERTAIN" and result["remote_id"] == COMMENT
    assert result["remote_state"]["verification"] == "POST_RESPONSE_ONLY"
    with pytest.raises(WorkflowError):
        flow.execute(plan["id"], provider=provider)
    native.invisible_comment = False
    assert flow.reconcile(plan["id"], provider=provider)["status"] == "DELIVERED"
    assert sum(m == "POST" for m, _, _, _ in native.calls) == 1


def test_wrong_metadata_trigger_id_stays_uncertain(adapter_setup):
    flow, provider, native, key = adapter_setup
    plan = flow.prepare_metadata(TRIGGER, provider=provider, url="https://inspector.example/case")
    review(flow, key, plan)
    native.metadata_wrong_id = True
    assert flow.execute(plan["id"], provider=provider)["status"] == "UNCERTAIN"
    assert flow.reconcile(plan["id"], provider=provider)["status"] == "UNCERTAIN"
    assert sum(m == "PATCH" for m, _, _, _ in native.calls) == 1


@pytest.mark.parametrize("next_url", [f"https://api.ramp.com/developer/v1/comments/bills/{BILL}?start=next",
    f"https://demo-api.ramp.com/developer/v1/comments/bills/{DRAFT}?start=next",
    f"https://demo-api.ramp.com/developer/v1/comments/bills/{BILL}?start=next&start=another",
    "https://attacker.example/capture", "/relative?start=next"])
def test_pagination_cannot_leave_exact_sandbox_discussion(adapter_setup, next_url):
    _, provider, native, _ = adapter_setup
    def pages(request):
        native.calls.append((request.method, request.url.path, {}, None))
        return httpx.Response(200, json={"data": [], "page": {"next": next_url}})
    with httpx.Client(transport=httpx.MockTransport(pages)) as http:
        provider.http = http
        with pytest.raises(ProviderFailure, match="pagination"):
            provider.comments("bills", BILL)
    assert len(native.calls) == 1


def test_paginated_exact_readback_follows_only_same_thread(adapter_setup):
    _, provider, _, _ = adapter_setup
    seen = []
    def pages(request):
        seen.append(str(request.url))
        if "start" not in request.url.params:
            return httpx.Response(200, json={"data": [], "page": {"next": f"{ORIGIN}/developer/v1/comments/bills/{BILL}?start={COMMENT}"}})
        return httpx.Response(200, json={"data": [{"id": COMMENT}], "page": {"next": None}})
    with httpx.Client(transport=httpx.MockTransport(pages)) as http:
        provider.http = http
        assert provider.comments("bills", BILL) == [{"id": COMMENT}]
    assert len(seen) == 2


def test_redirect_and_private_provider_errors_are_not_followed_or_exposed(adapter_setup):
    _, provider, _, _ = adapter_setup
    seen = []
    def redirect(request):
        seen.append(request.url)
        return httpx.Response(307, headers={"Location": "https://attacker.example/private"}, json={"error": TOKEN})
    with httpx.Client(transport=httpx.MockTransport(redirect), follow_redirects=True) as http:
        provider.http = http
        with pytest.raises(ProviderFailure) as caught:
            provider.read_object("bills", BILL)
    assert TOKEN not in str(caught.value) and "attacker" not in str(caught.value)
    assert len(seen) == 1


def test_stale_scope_receipt_rejected_before_http(adapter_setup):
    flow, provider, native, _ = adapter_setup
    provider.observed_at = (NOW-timedelta(minutes=16)).isoformat()
    with pytest.raises(WorkflowError):
        flow.prepare_comment("bills", BILL, provider=provider)
    assert native.calls == []
