"""Draft permission exercises real enrolled keys and the mounted HTTP entrypoints."""
import json

from fastapi.testclient import TestClient
import pytest

from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient, action_headers
from uptime.auth_keys import generate_reviewer_key
from uptime.contracts import DraftReviewer
from uptime.server import create_app
from uptime.storage import database
from uptime import vendor_registry
from uptime.vendor_api import Preview
from test_vendor_catalog import DOC, OVERLAY, FACTS, TESTS

V = "/api/vendors/draft-controls"


@pytest.fixture
def draft(tmp_path):
    db = tmp_path/"work.sqlite"
    key = generate_reviewer_key()
    enroll(db, "draft-reviewer", key, tenant="draft-tenant", mode="replay")
    app = create_app(db, tenant="draft-tenant", mode="replay", approvals_enabled=False)
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1",12345)) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "draft-reviewer", key)
        yield app, reviewer, db


def intake(reviewer):
    response = reviewer.post(V+"/candidates", {"document":DOC, "overlay":OVERLAY})
    assert response.status_code == 200, response.text
    return response.json()


def test_enrolled_reviewer_can_draft_test_and_preview_with_all_publishing_disabled(draft):
    app, reviewer, db = draft
    assert app.state.auth.approvals_enabled is False
    state = intake(reviewer)
    assert state["state"] == "SHADOW" and state["actions"] == []
    state = reviewer.post(V+"/tests", {"revision":state["revision"],"tests":TESTS}).json()
    assert all(c["passed"] for c in state["checks"]) and state["actions"] == []
    with database(db) as connection:
        before = list(connection.execute("SELECT * FROM case_snapshot"))
    result = reviewer.post(V+"/shadow-preview", {"revision":state["revision"],"facts":FACTS})
    assert result.status_code == 200, result.text
    assert result.json()["classification"] == "LOCAL_DRAFT_PREVIEW"
    assert result.json()["evaluation"]["amount"] == "12.50"
    assert result.json()["dispatch_authorized"] is False
    with database(db) as connection:
        assert list(connection.execute("SELECT * FROM case_snapshot")) == before
    persisted = reviewer.client.get(V, headers=reviewer.headers).json()
    assert persisted["revision"] == state["revision"] and persisted["actions"] == []
    for path in (V+"/evaluate",V+"/actions/activate","/api/policy","/api/lab/actions/approve","/api/ramp/native/preflight"):
        response = reviewer.client.post("/api/auth/challenge",headers=reviewer.headers,json={
            "subject":"draft-reviewer","path":path,"body_sha256":"a"*64})
        assert response.status_code == 403


def test_draft_requests_retain_body_origin_and_one_time_proof(draft):
    app, reviewer, db = draft
    state = intake(reviewer)
    payload = {"revision":state["revision"],"facts":FACTS}
    prepared = reviewer.prepare(V+"/shadow-preview",payload)
    bad = dict(prepared)
    bad["content"] = json.dumps({**payload,"revision":0}).encode()
    assert reviewer.client.post(V+"/shadow-preview",**bad).status_code == 403
    assert reviewer.client.post(V+"/shadow-preview",**prepared).status_code == 403
    prepared = reviewer.prepare(V+"/shadow-preview",payload)
    assert reviewer.client.post(V+"/shadow-preview",**prepared).status_code == 200
    assert reviewer.client.post(V+"/shadow-preview",**prepared).status_code == 403
    assert reviewer.client.post(V+"/candidates",json={"document":DOC,"overlay":OVERLAY},
        headers={**reviewer.headers,"Origin":"https://outside.invalid"}).status_code == 403


def test_draft_capability_cannot_reach_domain_dispatch_or_change_approved_history(draft):
    app, reviewer, db = draft
    state = intake(reviewer)
    p = DraftReviewer("draft-tenant","draft-reviewer","reviewer")
    for operation, arg in ((vendor_registry.act, "activate"),(vendor_registry.dispatch, FACTS)):
        with pytest.raises(PermissionError):
            operation(db,p,"draft-controls",arg)
    with vendor_registry.transaction(db,p,"draft-controls") as connection:
        state["state"] = "APPROVED"
        state["reviewer"] = "some-established-reviewer"
        vendor_registry._event(connection,p,"draft-controls",state,"Test-only approved history")
    for path,body in [
        ("/candidates",{"document":DOC,"overlay":OVERLAY}),
        ("/tests",{"revision":state["revision"],"tests":TESTS}),
        ("/shadow-preview",{"revision":state["revision"],"facts":FACTS})]:
        assert reviewer.post(V+path,body).status_code == 403


def test_viewer_has_no_draft_capability(draft):
    app, reviewer, db = draft
    key = generate_reviewer_key()
    enroll(db,"draft-viewer",key,"viewer",mode="replay",tenant="draft-tenant")
    viewer = ReviewerClient(reviewer.client,DEFAULT_ORIGIN,"draft-viewer",key)
    response = viewer.client.post("/api/auth/challenge",headers=viewer.headers,json={
        "subject":"draft-viewer","path":V+"/candidates","body_sha256":"a"*64})
    assert response.status_code == 403


def test_only_canonical_draft_paths_receive_a_challenge(draft):
    app, reviewer, db = draft
    for path in (V+"/tests/","/api/vendors/Draft/candidates",V+"/candidates?publish=true",
                 V+"/../other/candidates",V+"/%63andidates",V+"/actions/tests"):
        response = reviewer.client.post("/api/auth/challenge",headers=reviewer.headers,json={
            "subject":"draft-reviewer","path":path,"body_sha256":"a"*64})
        assert response.status_code == 403
