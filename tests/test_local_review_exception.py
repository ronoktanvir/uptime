"""Disposable fixture permissions only; these tests never authorize an actual reviewer."""
import json
from pathlib import Path
import shutil
import subprocess

from fastapi.testclient import TestClient
import pytest

from scripts import setup_live_reviewer as setup
from scripts import review_local_exception as cli
from uptime import local_review_exception as permission
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key, reviewer_signature
from uptime.contracts import Principal
from uptime import vendor_registry as registry


@pytest.fixture
def installation(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "local_release_ready", lambda: False)
    monkeypatch.setattr(permission, "AUTHORITY_ROOT", tmp_path / "authority")
    source = {"commit": "a" * 40, "manifest_sha256": "b" * 64}
    monkeypatch.setattr(permission, "source_identity", lambda **kwargs: source.copy())
    folder = tmp_path / "review"
    app, metadata, state = setup.prepare(folder, "http://127.0.0.1:8777", "reviewer.fixture",
                                         credential_file=folder / "reviewer.jwk")
    evidence = tmp_path / "verification.json"
    evidence.write_text(json.dumps({"tested_commit": source["commit"], "command": "uv run --locked pytest",
                                   "exit_code": 0, "actual_summary": "15 passed in 0.10s"}))
    proposal = permission.build_proposal(folder, evidence)
    proposal_path = tmp_path / "proposal.json"
    permission.write_json(proposal_path, proposal)
    return dict(folder=folder, app=app, metadata=metadata, state=state, evidence=evidence,
                proposal=proposal, proposal_path=proposal_path, source=source,
                envelope=tmp_path / "envelope.json", root=tmp_path)


def sign_fixture(item, *, owner=True):
    digest = permission.proposal_digest(item["proposal"])
    if owner:
        permission.owner_approve(item["folder"], item["proposal_path"], digest)
    permission.authorize(item["folder"], item["proposal_path"], item["folder"] / "reviewer.jwk",
                         item["envelope"], digest)
    return setup.open_workspace(item["folder"], review_exception=item["envelope"])[0]


def connect(item, app):
    client = TestClient(app, base_url=item["metadata"]["origin"], client=("127.0.0.1", 4531))
    key = json.loads((item["folder"] / "reviewer.jwk").read_text())
    actor = ReviewerClient(client, item["metadata"]["origin"], "reviewer.fixture", key)
    return client, actor


def browser_sign_in_request(subject):
    """The first request the real sign-in page sends, captured by running web/auth.js in node."""
    result = subprocess.run(["node", "tests/helpers/browser_sign_in_challenge.cjs", subject],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_browser_sign_in_request_passes_the_review_guard(installation):
    item = installation
    app = sign_fixture(item)
    sent = browser_sign_in_request("reviewer.fixture")
    # The enrolled credential is reviewer.jwk; the picker must let the person select it.
    assert ".jwk" in sent["credential_accept"].split(",")
    origin = item["metadata"]["origin"]
    with TestClient(app, base_url=origin, client=("127.0.0.1", 4531)) as client:
        response = client.request(sent["method"], sent["url"], content=sent["body"],
                                  headers={**sent["headers"], "Origin": origin})
    assert response.status_code == 200, response.text
    assert response.json()["challenge"]


def current(client, actor):
    response = client.get("/api/vendors/calyxquay", headers=actor.headers)
    assert response.status_code == 200
    return response.json()


def next_action(client, actor, operation):
    state = current(client, actor)
    offer = next(row for row in state["actions"] if row["operation"] == operation)
    return actor.post(permission.PREFIX + offer["id"], {})


def test_unsigned_preparation_cannot_enable_actions_or_create_owner_approval(installation):
    item = installation
    root = permission.AUTHORITY_ROOT
    assert sorted(p.name for p in root.iterdir()) == ["host.json"]
    assert item["proposal_path"].stat().st_mode & 0o777 == 0o600
    assert item["proposal"]["reviewer"] == "reviewer.fixture"
    assert item["proposal"]["initial_revision"] == item["state"]["revision"]
    assert item["proposal"]["expires_at"] - item["proposal"]["not_before"] == 48 * 3600
    assert not item["app"].state.auth.approvals_enabled
    with pytest.raises((OSError, ValueError)):
        setup.open_workspace(item["folder"], review_exception=item["proposal_path"])
    assert not item["envelope"].exists()


def test_owner_and_reviewer_channels_both_required_and_domain_separated(installation):
    item = installation
    with pytest.raises(OSError):
        sign_fixture(item, owner=False)
    digest = permission.proposal_digest(item["proposal"])
    with pytest.raises(ValueError):
        permission.owner_approve(item["folder"], item["proposal_path"], "0" * 64)
    permission.owner_approve(item["folder"], item["proposal_path"], digest)
    wrong_key = item["root"] / "wrong-key.json"
    permission.write_json(wrong_key, generate_reviewer_key())
    with pytest.raises(ValueError):
        permission.authorize(item["folder"], item["proposal_path"], wrong_key, item["envelope"], digest)
    key = json.loads((item["folder"] / "reviewer.jwk").read_text())
    unsigned_domain = {"schema_version": "uptime-local-review-exception-envelope/1", "proposal": item["proposal"],
                       "signature": reviewer_signature(key, permission.canonical(item["proposal"]).decode())}
    permission.write_json(item["envelope"], unsigned_domain)
    with pytest.raises(ValueError):
        setup.open_workspace(item["folder"], review_exception=item["envelope"])


def test_scoped_signed_lifecycle_records_real_actor_and_terminal_rollback_in_fixture(installation):
    item = installation
    app = sign_fixture(item)
    client, actor = connect(item, app)
    with client:
        for operation, expected in (("interpret", "SHADOW"), ("approve", "APPROVED"), ("activate", "ACTIVE"), ("rollback", "REVOKED")):
            response = next_action(client, actor, operation)
            assert response.status_code == 200, response.text
            assert response.json()["state"] == expected
            assert response.json()["version"] == item["proposal"]["candidate_version"]
        state = current(client, actor)
        assert state["active_version"] is None
        assert {row["actor"] for row in state["audit"][-4:]} == {"reviewer.fixture"}
        assert all(row["at"] for row in state["audit"][-4:])
        assert not app.state.auth.local_gate()
        response = client.post("/api/auth/challenge", headers=actor.headers,
                               json={"subject": "reviewer.fixture", "path": "/api/auth/login", "body_sha256": ""})
        assert response.status_code == 403
    events = permission._events(item["proposal"]["grant_id"])
    assert [json.loads(row["payload"])["operation"] for row in events if row["event"] == "ACTION"] == list(permission.OPERATIONS)
    assert events[-1]["event"] == "COMPLETED"
    with pytest.raises(ValueError):
        setup.open_workspace(item["folder"], review_exception=item["envelope"])


def test_source_receipt_or_candidate_drift_disables_existing_permission(installation):
    item = installation
    app = sign_fixture(item)
    assert app.state.auth.local_gate()
    item["source"]["manifest_sha256"] = "c" * 64
    assert not app.state.auth.local_gate()
    item["source"]["manifest_sha256"] = "b" * 64
    item["evidence"].write_text(item["evidence"].read_text() + "\n")
    assert not app.state.auth.local_gate()


@pytest.mark.parametrize("field,value", [("expires_at", 1), ("candidate_version", "c" * 64),
                                        ("workspace_id", "d" * 64), ("reviewer_key_sha256", "e" * 64),
                                        ("dependency_sha256", "f" * 64)])
def test_tampered_proposal_is_rejected_before_any_reviewer_action(installation, field, value):
    item = installation
    sign_fixture(item)
    envelope = json.loads(item["envelope"].read_text())
    envelope["proposal"][field] = value
    item["envelope"].write_text(json.dumps(envelope))
    with pytest.raises(ValueError):
        setup.open_workspace(item["folder"], review_exception=item["envelope"])
    state = registry.get_vendor(item["folder"] / "workspace.db", Principal("bears", "reviewer.fixture", "reviewer"), "calyxquay")
    assert state["audit"] == item["state"]["audit"]


def test_copied_workspace_and_old_snapshot_cannot_reuse_revoked_grant(installation):
    item = installation
    sign_fixture(item)
    snapshot = item["root"] / "snapshot"
    shutil.copytree(item["folder"], snapshot)
    with pytest.raises(ValueError):
        setup.open_workspace(snapshot, review_exception=item["envelope"])
    permission.revoke(item["proposal"]["grant_id"])
    shutil.rmtree(item["folder"])
    shutil.copytree(snapshot, item["folder"])
    with pytest.raises(ValueError):
        setup.open_workspace(item["folder"], review_exception=item["envelope"])
    with pytest.raises(ValueError):
        permission.owner_approve(item["folder"], item["proposal_path"], permission.proposal_digest(item["proposal"]))


def test_revocation_between_challenge_and_action_preserves_shadow(installation):
    item = installation
    app = sign_fixture(item)
    client, actor = connect(item, app)
    with client:
        state = current(client, actor)
        path = permission.PREFIX + state["actions"][0]["id"]
        prepared = actor.prepare(path, {})
        permission.revoke(item["proposal"]["grant_id"])
        response = client.post(path, **prepared)
        assert response.status_code == 403
        assert current(client, actor)["audit"] == state["audit"]


def test_monotonic_ceiling_refuses_extension_after_wall_clock_rollback(installation, monkeypatch):
    item = installation
    app = sign_fixture(item)
    policy = app.state.local_review_exception
    assert policy.ready()
    monkeypatch.setattr(permission, "time", lambda: item["proposal"]["not_before"] + 1)
    monkeypatch.setattr(permission, "monotonic", lambda: policy.monotonic_until + 1)
    assert not policy.ready()


def test_audit_failure_never_returns_success_and_blocks_further_actions(installation, monkeypatch):
    item = installation
    app = sign_fixture(item)
    client, actor = connect(item, app)
    original = permission._event
    def interrupted(grant_id, event, payload):
        if event == "ACTION":
            raise OSError("fixture audit write failure")
        return original(grant_id, event, payload)
    monkeypatch.setattr(permission, "_event", interrupted)
    with client:
        result = next_action(client, actor, "interpret")
        assert result.status_code == 403
        # The ordinary local event committed, but its authority audit did not.
        # Its state remains inspectable, and no further mutation is permitted.
        assert current(client, actor)["interpretation_reviewer"] == "reviewer.fixture"
        assert not app.state.auth.local_gate()


def test_cli_prepare_reports_unsigned_and_never_reads_reviewer_private_key(installation, capsys, monkeypatch):
    item = installation
    key = item["folder"] / "reviewer.jwk"
    key.rename(item["folder"] / "unavailable.jwk")
    output = item["root"] / "second-proposal.json"
    assert cli.main(["prepare", "--directory", str(item["folder"]), "--evidence", str(item["evidence"]),
                     "--output", str(output), "--hours", "1"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "UNSIGNED_REVIEW_REQUIRED"
    assert not receipt["owner_approval_created"] and not receipt["reviewer_signature_created"] and not receipt["permission_installed"]
    assert sorted(p.name for p in permission.AUTHORITY_ROOT.iterdir()) == ["host.json"]
