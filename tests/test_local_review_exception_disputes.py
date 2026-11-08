"""Independent negative boundaries for a disposable local adapter exception.

All identities, credentials, owner approvals and verification receipts here are
test fixtures. They neither enable the operator's workspace nor contact Ramp.
"""
import json
from hashlib import sha256
import socket
import subprocess

import pytest
from fastapi.testclient import TestClient

from scripts import setup_live_reviewer as setup
from uptime import local_review_exception as exception
from uptime.auth_client import ReviewerClient
from uptime.contracts import Principal
from uptime.storage import database


ORIGIN = "http://127.0.0.1:8777"
SUBJECT = "boundary.fixture"
SOURCE = {"commit": "a" * 40, "manifest_sha256": "b" * 64}
CLAIM = "inbox-exception-boundary"
SCOPE = dict(account="boundary-account", vendor="Boundary Vendor", contract="BV-1",
             service="Storage", component="storage-east", invoice="invoice-1",
             incident="incident-1", currency="USD", month="2026-10", region="east")


def financial_state(path):
    """Observe domain rows, including receipts and journal, independently of UI."""
    with database(path) as db:
        tables = sorted(row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        if row[0].startswith(("dispute_", "inbox_", "allocation_", "policy_", "settlement_", "case_")))
        return {name: sorted(repr(tuple(row)) for row in db.execute('SELECT * FROM "' + name + '"')) for name in tables}


def prepare_fixture(tmp_path, monkeypatch, *, owner=True):
    def no_connection(*args, **kwargs):
        raise AssertionError("A local review exception must not open a provider or model connection")
    monkeypatch.setattr(socket.socket, "connect", no_connection)
    monkeypatch.setattr(setup, "local_release_ready", lambda: False)
    monkeypatch.setattr(exception, "source_identity", lambda *args, **kwargs: dict(SOURCE))
    monkeypatch.setattr(exception, "AUTHORITY_ROOT", tmp_path / "operator-authority")
    folder = tmp_path / "review-workspace"
    credential_path = folder / "fixture-reviewer.jwk"
    _, metadata, state = setup.prepare(folder, ORIGIN, SUBJECT, credential_file=credential_path)
    evidence = folder / "verification.json"
    exception.write_json(evidence, dict(tested_commit=SOURCE["commit"], command="uv run --locked pytest",
                                        exit_code=0, actual_summary="15 passed in 0.10s"))
    proposal = exception.build_proposal(folder, evidence, lifetime_seconds=172800)
    proposal_path = folder / "proposal.json"
    exception.write_json(proposal_path, proposal)
    reviewed = exception.proposal_digest(proposal)
    if owner:
        exception.owner_approve(folder, proposal_path, reviewed)
    grant = folder / "review-grant.json"
    return folder, metadata, state, credential_path, proposal_path, reviewed, grant


@pytest.fixture
def limited(tmp_path, monkeypatch):
    folder, metadata, state, credential_path, proposal_path, reviewed, grant = prepare_fixture(tmp_path, monkeypatch)
    exception.authorize(folder, proposal_path, credential_path, grant, reviewed)
    app, metadata = setup.open_workspace(folder, review_exception=grant)
    key = json.loads(credential_path.read_text())
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 4527)) as client:
        actor = ReviewerClient(client, ORIGIN, SUBJECT, key)
        initial = client.get("/api/vendors/calyxquay", headers=actor.headers).json()
        interpret = next(row for row in initial["actions"] if row["operation"] == "interpret")
        response = actor.post("/api/vendors/calyxquay/actions/" + interpret["id"], {})
        assert response.status_code == 200, response.text
        assert response.json()["interpretation_reviewer"] == SUBJECT
        # The exception is usable for its allowed operation, while the normal
        # deployment release remains false. Negative controls are not a dead app.
        assert setup.local_release_ready() is False
        assert not any(getattr(route, "path", "").startswith("/api/ramp/native/") for route in app.routes)
        existing_case = client.get("/api/cases/dispute-cure", headers=actor.headers)
        assert existing_case.status_code == 200 and existing_case.json()["stage"] == "DRAFTED"
        yield folder, app, client, actor, response.json(), grant


CASE_ACTIONS = ("approve-claim", "submit-claim", "prepare-response", "approve-response", "submit-response",
                "record-credit", "apply-balance", "advance-cooldown", "refresh-claim", "close-expired")
INBOX_ACTIONS = ("approve-claim", "submit-claim", "approve-response", "submit-response")
FORBIDDEN = [("/api/cases/dispute-cure/actions/" + action, {}) for action in CASE_ACTIONS]
FORBIDDEN += [("/api/correspondence/claims/" + CLAIM + "/actions/" + action, {}) for action in INBOX_ACTIONS]
FORBIDDEN += [
    ("/api/correspondence/claims", dict(claim_id=CLAIM, scope=SCOPE)),
    ("/api/policy", dict(mode="ASSISTED", cap="10000.00")),
    ("/api/onboarding/actions/approve", {}),
    ("/api/onboarding/actions/activate", {}),
    ("/api/vendors/calyxquay/evaluate", dict(facts={})),
    ("/api/correspondence/claims/" + CLAIM + "/interpretation/model-jobs", dict(context_digest="c" * 64)),
    ("/api/correspondence/claims/" + CLAIM + "/interpretation/candidates/model", dict(context_digest="c" * 64)),
    ("/api/correspondence/claims/" + CLAIM + "/interpretation/prepare-response", dict(review_id="d" * 64, preview_digest="e" * 64)),
    ("/api/correspondence/claims/" + CLAIM + "/events", dict(event_id="forged-award", scope=SCOPE,
        body=dict(kind="message", receipt_id="LOCAL-" + "f" * 24, text="We have approved a service credit of USD 2400.00."))),
    ("/api/ramp/native/preflight", {}),
    ("/api/ramp/native/prepare", dict(object_type="bills", object_id="00000000-0000-4000-8000-000000000001")),
]
FORBIDDEN += [("/api/ramp/native/actions/" + "a" * 64 + "/" + action,
               dict(review_digest="b" * 64) if action == "execute" else {})
              for action in ("review", "execute", "reconcile")]


@pytest.mark.parametrize("path,body", FORBIDDEN, ids=[path for path, _ in FORBIDDEN])
def test_adapter_exception_cannot_issue_a_proof_for_financial_or_external_mutation(limited, path, body):
    folder, app, client, actor, state, _ = limited
    before = financial_state(folder / "workspace.db")
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    response = client.post("/api/auth/challenge", headers=actor.headers,
                           json=dict(subject=SUBJECT, path=path, body_sha256=sha256(raw).hexdigest()))
    assert response.status_code == 403, response.text
    assert financial_state(folder / "workspace.db") == before
    assert app.state.auth.native_gate is None
    assert app.state.auth.mode == "replay" and app.state.auth.rehearsal is False


@pytest.mark.parametrize("path,body", [row for row in FORBIDDEN if not row[0].startswith("/api/ramp/native/")],
                         ids=[path for path, _ in FORBIDDEN if not path.startswith("/api/ramp/native/")])
def test_adapter_signature_cannot_be_transplanted_to_a_claim_dispute_or_policy(limited, path, body):
    folder, _, client, actor, state, _ = limited
    allowed = next(row for row in state["actions"] if row["operation"] == "approve")
    request = actor.prepare("/api/vendors/calyxquay/actions/" + allowed["id"], {})
    before = financial_state(folder / "workspace.db")
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    response = client.post(path, content=raw, headers=request["headers"])
    assert response.status_code == 403, response.text
    assert financial_state(folder / "workspace.db") == before
    current = client.get("/api/vendors/calyxquay", headers=actor.headers).json()
    assert current["state"] == "SHADOW" and current["audit"] == state["audit"]


def test_source_change_with_a_prepared_proof_cannot_activate_the_exception(limited, monkeypatch):
    folder, _, client, actor, state, _ = limited
    allowed = next(row for row in state["actions"] if row["operation"] == "approve")
    path = "/api/vendors/calyxquay/actions/" + allowed["id"]
    request = actor.prepare(path, {})
    before = financial_state(folder / "workspace.db")
    monkeypatch.setattr(exception, "source_identity", lambda *args, **kwargs: SOURCE | {"manifest_sha256": "c" * 64})
    response = client.post(path, **request)
    assert response.status_code == 403, response.text
    assert financial_state(folder / "workspace.db") == before
    from uptime import vendor_registry
    current = vendor_registry.get_vendor(folder / "workspace.db", Principal("bears", SUBJECT, "reviewer"), "calyxquay")
    assert current["state"] == "SHADOW" and current["audit"] == state["audit"]


def test_adapter_replacement_cannot_borrow_the_previous_version_permission(limited, monkeypatch):
    from uptime import vendor_registry
    from uptime.auth import SCRIPT
    folder, _, client, actor, state, _ = limited
    offer = next(row for row in state["actions"] if row["operation"] == "approve")
    path = "/api/vendors/calyxquay/actions/" + offer["id"]
    request = actor.prepare(path, {})
    body, _ = setup.inputs()
    body["overlay"]["account"] = "different-customer-account"
    with monkeypatch.context() as source:
        source.setenv("UPTIME_PUBLIC_EXTRACTIONS", str(setup.ROOT / "docs/v4/evidence/public-extractions"))
        source.setenv("UPTIME_MODEL_PROPOSITIONS", "1")
        replacement = vendor_registry.install(folder / "workspace.db", Principal("bears", SCRIPT, "reviewer"), "calyxquay", body)
    assert replacement["version"] != state["version"]
    before = financial_state(folder / "workspace.db")
    response = client.post(path, **request)
    assert response.status_code == 403, response.text
    assert financial_state(folder / "workspace.db") == before
    current = vendor_registry.get_vendor(folder / "workspace.db", Principal("bears", SUBJECT, "reviewer"), "calyxquay")
    assert current["state"] == "SHADOW" and current["active_version"] is None
    assert current["reviewer"] is None and current["audit"] == replacement["audit"]


def test_a_valid_reviewer_signature_alone_does_not_supply_operator_approval(tmp_path, monkeypatch):
    from uptime.auth_keys import public_bytes, reviewer_signature, verify_reviewer
    from uptime import vendor_registry
    folder, _, state, credential_path, proposal_path, _, grant = prepare_fixture(tmp_path, monkeypatch, owner=False)
    proposal = json.loads(proposal_path.read_text())
    credential = json.loads(credential_path.read_text())
    message = exception.signing_message(proposal)
    signature = reviewer_signature(credential, message)
    assert verify_reviewer(public_bytes(credential), message, signature)
    exception.write_json(grant, dict(schema_version="uptime-local-review-exception-envelope/1",
                                    proposal=proposal, signature=signature))
    with pytest.raises((OSError, ValueError)):
        setup.open_workspace(folder, review_exception=grant)
    current = vendor_registry.get_vendor(folder / "workspace.db", Principal("bears", SUBJECT, "reviewer"), "calyxquay")
    assert current["state"] == "SHADOW" and current["audit"] == state["audit"]


def advance(actor, state, operation):
    offer = next(row for row in state["actions"] if row["operation"] == operation)
    response = actor.post("/api/vendors/calyxquay/actions/" + offer["id"], {})
    assert response.status_code == 200, response.text
    return response.json()


def test_expiry_freezes_an_active_adapter_and_never_opens_evaluation_or_claim_writes(limited, monkeypatch):
    from uptime import vendor_registry
    folder, app, client, actor, state, grant = limited
    state = advance(actor, advance(actor, state, "approve"), "activate")
    assert state["state"] == "ACTIVE"
    rollback = next(row for row in state["actions"] if row["operation"] == "rollback")
    path = "/api/vendors/calyxquay/actions/" + rollback["id"]
    request = actor.prepare(path, {})
    expires = json.loads(grant.read_text())["proposal"]["expires_at"]
    before = financial_state(folder / "workspace.db")
    monkeypatch.setattr(exception, "time", lambda: expires)
    assert app.state.local_review_exception.ready() is False
    assert client.post(path, **request).status_code == 403
    for denied in ("/api/vendors/calyxquay/evaluate", "/api/cases/dispute-cure/actions/submit-claim"):
        response = client.post("/api/auth/challenge", headers=actor.headers,
            json=dict(subject=SUBJECT, path=denied, body_sha256=sha256(b"{}").hexdigest()))
        assert response.status_code == 403
    assert financial_state(folder / "workspace.db") == before
    current = vendor_registry.get_vendor(folder / "workspace.db", Principal("bears", SUBJECT, "reviewer"), "calyxquay")
    assert current["state"] == "ACTIVE" and current["audit"] == state["audit"]


def test_rollback_ends_permission_and_restoring_the_envelope_does_not_reopen_it(limited):
    folder, app, client, actor, state, grant = limited
    raw = grant.read_bytes()
    state = advance(actor, advance(actor, advance(actor, state, "approve"), "activate"), "rollback")
    assert state["state"] == "REVOKED" and state["active_version"] is None
    assert app.state.local_review_exception.ready() is False
    grant.write_bytes(raw)
    before = financial_state(folder / "workspace.db")
    with pytest.raises((OSError, ValueError)):
        setup.open_workspace(folder, review_exception=grant)
    assert financial_state(folder / "workspace.db") == before


def test_git_source_verification_failure_is_a_denial_without_a_domain_effect(limited, monkeypatch):
    folder, app, client, actor, state, _ = limited
    approve = next(row for row in state["actions"] if row["operation"] == "approve")
    path = "/api/vendors/calyxquay/actions/" + approve["id"]
    request = actor.prepare(path, {})
    before = financial_state(folder / "workspace.db")
    def changed_source(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["git", "diff", "--quiet"])
    monkeypatch.setattr(exception, "source_identity", changed_source)
    assert app.state.local_review_exception.ready() is False
    response = client.post(path, **request)
    assert response.status_code == 403, response.text
    assert financial_state(folder / "workspace.db") == before


@pytest.mark.parametrize("variant", (
    "trailing-slash", "encoded-slash", "double-encoded-slash", "encoded-vendor", "query",
    "method-override", "spaced-body", "newline-body", "chunked", "padded-length", "duplicate-length", "wrong-length",
))
def test_request_representation_cannot_expand_the_exact_adapter_permission(limited, variant):
    folder, _, client, actor, state, _ = limited
    approve = next(row for row in state["actions"] if row["operation"] == "approve")
    path = "/api/vendors/calyxquay/actions/" + approve["id"]
    request = actor.prepare(path, {})
    body, headers = request["content"], dict(request["headers"])
    if variant == "trailing-slash":
        path += "/"
    elif variant == "encoded-slash":
        path = path.replace("/actions/", "/actions%2F")
    elif variant == "double-encoded-slash":
        path = path.replace("/actions/", "/actions%252F")
    elif variant == "encoded-vendor":
        path = path.replace("calyxquay", "%63alyxquay")
    elif variant == "query":
        path += "?operation=submit-claim"
    elif variant == "method-override":
        headers["X-HTTP-Method-Override"] = "PUT"
    elif variant == "spaced-body":
        body = b"{ }"
    elif variant == "newline-body":
        body = b"{}\n"
    elif variant == "chunked":
        headers["Transfer-Encoding"] = "chunked"
    elif variant == "padded-length":
        headers["Content-Length"] = "02"
    elif variant == "duplicate-length":
        headers = [*headers.items(), ("Content-Length", "2"), ("content-length", "2")]
    elif variant == "wrong-length":
        headers["Content-Length"] = "3"
    before = financial_state(folder / "workspace.db")
    with database(exception.AUTHORITY_ROOT / "authority.sqlite") as db:
        authority_before = [tuple(row) for row in db.execute("SELECT * FROM review_exception_event ORDER BY sequence")]
    response = client.post(path, content=body, headers=headers, follow_redirects=False)
    assert response.status_code == 403, response.text
    assert financial_state(folder / "workspace.db") == before
    with database(exception.AUTHORITY_ROOT / "authority.sqlite") as db:
        assert [tuple(row) for row in db.execute("SELECT * FROM review_exception_event ORDER BY sequence")] == authority_before
    current = client.get("/api/vendors/calyxquay", headers=actor.headers).json()
    assert current["state"] == "SHADOW" and current["audit"] == state["audit"]
