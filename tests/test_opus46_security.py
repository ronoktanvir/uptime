"""Public synthetic falsifiers for Opus46, through signed routes and a raw loopback socket."""
from copy import deepcopy
import http.client
import json
from urllib.parse import urlsplit

import httpx
import pytest

from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key
from uptime.server import create_app
from test_vendor_catalog import DOC, OVERLAY, FACTS, TESTS
from test_vendor_draft_authority import draft, intake, V
from test_v4_authority_browser import running
from test_ramp_native_binding import installed, native, USER
from test_ramp_award_claim_integration import external_harness, register, witness, twilio
from test_ramp_award_attribution import AttributionError, NOW, scope

RAW_VARIANTS = [
    "/api/vendors/draft-controls/%63andidates",
    "/api/vendors/draft-controls%2Fcandidates",
    "/api/vendors/draft-controls%252Fcandidates",
    "/api/vendors/draft-controls//candidates",
    "/api//vendors/draft-controls/candidates",
    "/api/vendors/draft-controls/candidates/",
    "/api/vendors/draft-controls/candidates/.",
    "/api/vendors/draft-controls/candidates/..",
    "/api/vendors/draft-controls/candidates/../../draft-controls/evaluate",
    "/api/vendors/draft-controls/candidates/%2e%2e/evaluate",
    "/api/vendors/draft-controls/candidates/%2e%2e%2fevaluate",
    "/api/vendors/draft-controls/candidates/%252e%252e/evaluate",
    "/api/vendors/draft-controls/candidates/..%2fevaluate",
    "/api/vendors/draft-controls/./candidates",
    "/api/vendors/draft-controls/../draft-controls/candidates",
    "/api/vendors/draft-controls/%2ecandidates",
    "/api/vendors/draft-controls/candidates;action=activate",
    "/api/vendors/draft-controls/candidates%00",
    "/api/vendors/draft-controls/candidates?next=evaluate",
    "/api/vendors/draft-controls/candidates#evaluate",
    "/api/vendors/draft-controls\\candidates",
    "/api/vendors/DRAFT/candidates",
]


def test_raw_socket_variants_cannot_borrow_a_canonical_draft_proof(tmp_path):
    path = tmp_path/"auth.db"
    key = generate_reviewer_key()
    enroll(path,"triage-reviewer",key,tenant="triage-tenant",mode="replay")
    observed = []
    def factory(origin):
        app = create_app(path,tenant="triage-tenant",mode="replay",origin=origin)
        @app.middleware("http")
        async def record(request, call_next):
            result = await call_next(request)
            route = request.scope.get("route")
            observed.append((request.scope["raw_path"].decode(),request.scope["path"],
                             getattr(route,"path",None),result.status_code))
            return result
        return app
    with running(factory) as (origin, app), httpx.Client(base_url=origin,trust_env=False) as client:
        reviewer = ReviewerClient(client,origin,"triage-reviewer",key)
        payload = {"document":DOC,"overlay":OVERLAY}
        target = V+"/candidates"
        prepared = reviewer.prepare(target,payload)
        peer = urlsplit(origin)
        def raw(path, proof):
            connection = http.client.HTTPConnection(peer.hostname,peer.port,timeout=10)
            try:
                connection.request("POST",path,body=proof["content"],headers=proof["headers"])
                result = connection.getresponse()
                status = result.status
                result.read()
                return status
            finally:
                connection.close()
        assert raw(target,prepared) == 200
        for path in RAW_VARIANTS:
            challenge = client.post("/api/auth/challenge",headers=reviewer.headers,json={
                "subject":"triage-reviewer","path":path,"body_sha256":"a"*64})
            assert challenge.status_code == 403, (path,challenge.text)
            assert not 200 <= raw(path,reviewer.prepare(target,payload)) < 300, path
        successes = [r for r in observed if r[2] == "/api/vendors/{vendor_id}/candidates" and 200 <= r[3] < 300]
        assert successes == [(target,target,"/api/vendors/{vendor_id}/candidates",200)]


def test_draft_quarantine_recovers_same_version_and_keeps_private_dates_out_of_reason(draft):
    app,reviewer,db = draft
    first = intake(reviewer)
    secret = "PRIVATE-CONTRACT-DATE-CANARY"
    bad = reviewer.post(V+"/candidates",{"document":DOC,"overlay":{**OVERLAY,"effective_from":secret}})
    assert bad.status_code == 200 and bad.json()["state"] == "QUARANTINED"
    assert bad.json()["version"] is None
    assert secret not in bad.text
    recovered = intake(reviewer)
    assert recovered["version"] == first["version"] and recovered["state"] == "SHADOW"
    assert recovered["revision"] > bad.json()["revision"] and recovered["actions"] == []


def test_active_vendor_rejects_draft_garbage_before_state_change(tmp_path):
    path = tmp_path/"active.db"
    key = generate_reviewer_key()
    enroll(path,"triage-reviewer",key,mode="replay")
    from fastapi.testclient import TestClient
    app = create_app(path,mode="replay",approvals_enabled=True)
    with TestClient(app,base_url=DEFAULT_ORIGIN,client=("127.0.0.1",12345)) as client:
        reviewer = ReviewerClient(client,DEFAULT_ORIGIN,"triage-reviewer",key)
        state = intake(reviewer)
        state = reviewer.post(V+"/tests",{"revision":state["revision"],"tests":TESTS}).json()
        for op in ("approve","activate"):
            action = next(a["id"] for a in state["actions"] if a["operation"] == op)
            result = reviewer.post(V+"/actions/"+action,{})
            assert result.status_code == 200,result.text
            state = result.json()
        assert state["state"] == "ACTIVE"
        app.state.auth.approvals_enabled = False
        for payload in ({},{"document":DOC,"overlay":{**OVERLAY,"effective_from":"private-invalid-date"}},
                        {"document":DOC,"overlay":OVERLAY}):
            assert reviewer.post(V+"/candidates",payload).status_code == 403
        unchanged = client.get(V,headers=reviewer.headers).json()
        assert {k:unchanged[k] for k in ("state","active_version","revision","version")} == {
            k:state[k] for k in ("state","active_version","revision","version")}


def test_separate_native_gate_survives_local_switch_but_rechecks_native_revocation(installed,monkeypatch):
    i = installed
    i.auth.approvals_enabled = False
    i.auth.local_gate = lambda: False
    assert i.post(native.PREFIX+"/preflight",{}).status_code == 200
    assert not i.protocol.posts
    response = i.client.post("/api/auth/challenge",headers=i.operator.headers,json={
        "subject":USER,"path":"/api/policy","body_sha256":"a"*64})
    assert response.status_code == 403
    monkeypatch.setattr(native.gates,"native_install_ready",lambda installation:False)
    before = list(i.protocol.calls)
    i.auth.native_gate = lambda:True  # Even a weakened challenge gate cannot override the binding's own check.
    assert i.post(native.PREFIX+"/preflight",{}).status_code == 409
    assert i.protocol.calls == before and not i.protocol.posts


def test_local_filed_packet_version_cannot_be_replaced_by_a_new_witness_scope(tmp_path):
    h,claim,sc,local = twilio(tmp_path/"db","correspondence",versions=["v2"])
    with pytest.raises(AttributionError,match="LOCAL_FILING_SCOPE_CONFLICT"):
        register(h,claim,{**sc,"contract_version":"v2"},local_contract=local)


def test_external_version_change_requires_explicit_new_scope_and_both_signatures(tmp_path):
    h,desk,local,sc = external_harness(tmp_path)
    wrong = {**sc,"contract_version":"v2"}
    with pytest.raises(AttributionError,match="WITNESS_SCOPE_CONFLICT"):
        register(h,"inbox-external",wrong,local_contract=local.contract,external=witness(h))
    signed = register(h,"inbox-external",sc,local_contract=local.contract,external=witness(h))
    tampered = deepcopy(signed)
    tampered["statement"]["body"]["scope"]["contract_version"] = "v2"
    with pytest.raises(AttributionError):
        h.store.register_claim(tampered,at=NOW)



def test_independent_new_version_signatures_cannot_replace_original_external_pin(tmp_path):
    v2 = scope() | {"remedy":"resource-month/station-1","contract_version":"v2"}
    h,desk,local,v1 = external_harness(tmp_path,extra=[v2])
    with pytest.raises(AttributionError,match="ORIGINAL_CONTRACT_VERSION_CONFLICT"):
        register(h,"inbox-external",v2,local_contract=local.contract,external=witness(h))
    assert h.store.history() == []
    register(h,"inbox-external",v1,local_contract=local.contract,external=witness(h))


def test_old_unpinned_original_stays_readable_but_cannot_support_actual_attribution(tmp_path):
    h,desk,local,sc = external_harness(tmp_path,pin_version=False)
    assert h.store.filing_identity("inbox-external")
    with pytest.raises(AttributionError,match="ORIGINAL_CONTRACT_VERSION_REQUIRED"):
        register(h,"inbox-external",sc,local_contract=local.contract,external=witness(h))
    assert not h.store.history()



def test_preupgrade_quarantine_reason_is_redacted_on_signed_read(draft):
    from uptime.contracts import DraftReviewer
    from uptime import vendor_registry
    app,reviewer,db = draft
    state = intake(reviewer)
    actor = DraftReviewer("draft-tenant","draft-reviewer","reviewer")
    with vendor_registry.transaction(db,actor,"draft-controls") as connection:
        state.update(state="QUARANTINED",version=None,reason="Invalid private value: PRIVATE-OLD-EXCEPTION")
        vendor_registry._event(connection,actor,"draft-controls",state,"Synthetic pre-upgrade quarantine")
    response = reviewer.client.get(V,headers=reviewer.headers)
    assert response.status_code == 200 and response.json()["state"] == "QUARANTINED"
    assert "PRIVATE-OLD-EXCEPTION" not in response.text
