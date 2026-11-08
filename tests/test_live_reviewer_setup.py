"""Prepared fixtures do not become human decisions or bypass the release gate.

The successful lifecycle below is an automated signed-client control with a
mocked release verifier. It is not evidence of a person reviewing the adapter.
"""
import json
import os

from fastapi.testclient import TestClient
import pytest

from scripts import setup_live_reviewer as setup
from uptime.auth import SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key, public_bytes
from uptime.contracts import Principal
from uptime.storage import database
from uptime import vendor_registry as registry


def fixture(tmp_path, monkeypatch, ready=False):
    gate = {"ready": ready}
    monkeypatch.setattr(setup, "local_release_ready", lambda: gate["ready"])
    folder = tmp_path / "live-review"
    app, metadata, state = setup.prepare(folder, "http://127.0.0.1:8777", "reviewer.fixture",
                                          credential_file=folder / "reviewer.jwk")
    credential = json.loads((folder / "reviewer.jwk").read_text())
    return folder, app, metadata, state, credential, gate


def signed(client, metadata, credential):
    return ReviewerClient(client, metadata["origin"], metadata["subject"], credential)


def view(client, actor):
    response = client.get("/api/vendors/calyxquay", headers=actor.headers)
    assert response.status_code == 200
    return response.json()


def action(actor, state, operation):
    offer = next(row for row in state["actions"] if row["operation"] == operation)
    return actor.post("/api/vendors/calyxquay/actions/" + offer["id"], {})


def test_preparation_stops_in_shadow_with_scripted_history_and_separate_named_key(tmp_path, monkeypatch):
    folder, app, metadata, state, credential, _ = fixture(tmp_path, monkeypatch)
    assert state["state"] == "SHADOW" and state["reviewer"] is None and state["active_version"] is None
    assert state["interpretation_reviewer"] is None
    assert {row["actor"] for row in state["audit"]} == {SCRIPT}
    assert not any(row["kind"] in registry.OPS.values() for row in state["audit"])
    assert state["test_author"] == SCRIPT
    assert state["extraction"]["semantic_binding"]
    assert all(row["passed"] for row in state["checks"])
    assert [(row["actual"]["outcome"], row["actual"]["amount"]) for row in state["checks"] if "actual" in row] == [
        ("ELIGIBLE", "12.00"), ("INSUFFICIENT_EVIDENCE", None), ("INELIGIBLE", None)]
    assert app.state.auth.rehearsal is False and app.state.auth.mode == "replay"
    assert not credential.get("uptime_rehearsal")
    assert app.state.auth.account(SCRIPT) is None
    assert app.state.auth.account("reviewer.fixture") is not None
    assert app.state.auth.local_gate() is False and app.state.auth.approvals_enabled is False
    assert folder.stat().st_mode & 0o777 == 0o700
    for name in ("reviewer.jwk", "workspace.json", "workspace.db"):
        assert (folder / name).stat().st_mode & 0o777 == 0o600
    with database(folder / "workspace.db") as db:
        assert tuple(db.execute("SELECT mode,rehearsal,tenant FROM authority_workspace").fetchone()) == ("replay", 0, "bears")
        assert json.loads(db.execute("SELECT payload FROM v4_vendor_semantic_review").fetchone()[0])["reviewer_kind"] == "scripted_test"


def test_unverified_release_allows_named_read_but_refuses_promotion(tmp_path, monkeypatch):
    folder, app, metadata, _, credential, _ = fixture(tmp_path, monkeypatch)
    with TestClient(app, base_url=metadata["origin"], client=("127.0.0.1", 4521)) as client:
        actor = signed(client, metadata, credential)
        state = view(client, actor)
        assert state["state"] == "SHADOW"
        offered = registry.get_vendor(folder / "workspace.db", Principal("bears", "reviewer.fixture", "reviewer"), "calyxquay")
        path = "/api/vendors/calyxquay/actions/" + offered["actions"][0]["id"]
        response = client.post("/api/auth/challenge", headers=actor.headers,
                               json={"subject": "reviewer.fixture", "path": path, "body_sha256": "0" * 64})
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"]
        assert view(client, actor)["audit"] == state["audit"]


def test_mocked_release_signed_lifecycle_keeps_actor_version_and_rollback(tmp_path, monkeypatch):
    _, app, metadata, prepared, credential, _ = fixture(tmp_path, monkeypatch, ready=True)
    with TestClient(app, base_url=metadata["origin"], client=("127.0.0.1", 4521)) as client:
        actor = signed(client, metadata, credential)
        state = view(client, actor)
        assert [row["operation"] for row in state["actions"]] == ["interpret"]
        interpreted = action(actor, state, "interpret")
        assert interpreted.status_code == 200
        state = interpreted.json()
        assert state["interpretation_reviewer"] == "reviewer.fixture"
        stale = next(row for row in state["actions"] if row["operation"] == "approve")
        approved = action(actor, state, "approve")
        assert approved.status_code == 200
        assert approved.json()["state"] == "APPROVED"
        assert actor.post("/api/vendors/calyxquay/actions/" + stale["id"], {}).status_code == 409
        activated = action(actor, approved.json(), "activate")
        assert activated.status_code == 200
        state = activated.json()
        assert state["state"] == "ACTIVE" and state["active_version"] == prepared["version"]
        assert state["reviewer"] == "reviewer.fixture" and state["reviewer_kind"] == "authenticated_reviewer"
        rolled = action(actor, state, "rollback")
        assert rolled.status_code == 200
        state = rolled.json()
        assert state["state"] == "REVOKED" and state["active_version"] is None
        assert state["version"] == prepared["version"]
        additions = state["audit"][len(prepared["audit"]):]
        assert [row["kind"] for row in additions] == [registry.OPS[op] for op in ("interpret", "approve", "activate", "rollback")]
        assert {row["actor"] for row in additions} == {"reviewer.fixture"}
        assert all(row["at"] for row in additions)


def test_release_revocation_after_start_refuses_signed_action_without_an_event(tmp_path, monkeypatch):
    _, app, metadata, prepared, credential, gate = fixture(tmp_path, monkeypatch, ready=True)
    with TestClient(app, base_url=metadata["origin"], client=("127.0.0.1", 4521)) as client:
        actor = signed(client, metadata, credential)
        state = view(client, actor)
        path = "/api/vendors/calyxquay/actions/" + state["actions"][0]["id"]
        request = actor.prepare(path, {})
        gate["ready"] = False
        response = client.post(path, **request)
        assert response.status_code == 403
        assert view(client, actor)["audit"] == prepared["audit"]


def test_resume_preserves_key_and_all_append_only_history(tmp_path, monkeypatch):
    folder, app, metadata, prepared, credential, _ = fixture(tmp_path, monkeypatch)
    before = (folder / "reviewer.jwk").read_bytes()
    resumed, saved = setup.open_workspace(folder)
    assert saved == metadata
    assert resumed.state.auth.instance != app.state.auth.instance
    assert (folder / "reviewer.jwk").read_bytes() == before
    state = registry.get_vendor(folder / "workspace.db", Principal("bears", "reviewer.fixture", "reviewer"), "calyxquay")
    assert state["audit"] == prepared["audit"] and state["version"] == prepared["version"]
    with pytest.raises(ValueError, match="fresh"):
        setup.prepare(folder, metadata["origin"], metadata["subject"], credential_file=folder / "reviewer.jwk")
    assert (folder / "reviewer.jwk").read_bytes() == before


def test_resume_rejects_changed_input_and_unsafe_metadata_permissions(tmp_path, monkeypatch):
    folder, _, _, _, _, _ = fixture(tmp_path, monkeypatch)
    (folder / "workspace.json").chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        setup.open_workspace(folder)
    (folder / "workspace.json").chmod(0o600)
    original = setup.inputs
    def changed():
        body, controls = original()
        body["overlay"]["account"] = "unrelated-account"
        return body, controls
    monkeypatch.setattr(setup, "inputs", changed)
    with pytest.raises(ValueError, match="Source inputs changed"):
        setup.open_workspace(folder)


@pytest.mark.parametrize("subject", [SCRIPT, "service-agent", "local-reviewer", "Dana Reyes", "../reviewer"])
def test_invalid_account_cannot_leave_a_provisioned_workspace(tmp_path, subject):
    folder = tmp_path / "refused"
    with pytest.raises(ValueError, match="named local account"):
        setup.prepare(folder, "http://127.0.0.1:8777", subject)
    assert not folder.exists()


def test_provisioning_refuses_repository_and_symlink_paths(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").write_text("gitdir: elsewhere\n")
    with pytest.raises(ValueError, match="outside repositories"):
        setup.prepare(checkout / "review", "http://127.0.0.1:8777", "reviewer.fixture")
    target = tmp_path / "physical"
    target.mkdir()
    link = tmp_path / "alias"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="without symlinks"):
        setup.prepare(link / "review", "http://127.0.0.1:8777", "reviewer.fixture")
    assert not (target / "review").exists()


def test_cli_receipt_states_release_pending_without_secret_bytes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(setup, "local_release_ready", lambda: False)
    folder = tmp_path / "cli"
    previous_umask = os.umask(0o077)
    try:
        assert setup.main(["--directory", str(folder), "--subject", "reviewer.fixture",
                           "--credential-file", str(folder / "reviewer.jwk")]) == 0
    finally:
        os.umask(previous_umask)
    raw = capsys.readouterr().out
    receipt = json.loads(raw)
    key = json.loads((folder / "reviewer.jwk").read_text())
    assert receipt["account"] == "reviewer.fixture" and receipt["local_approvals"] == "RELEASE_PENDING"
    assert receipt["human_actions_performed"] is False and receipt["provider_actions_performed"] is False
    assert key["d"] not in raw and key["x"] not in raw and key["y"] not in raw


def test_reviewer_owned_public_key_enrolls_without_creating_or_reading_a_private_key(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "local_release_ready", lambda: False)
    private = generate_reviewer_key()
    public_file = tmp_path / "reviewer-public.json"
    public_file.write_bytes(public_bytes(private))
    public_file.chmod(0o644)
    folder = tmp_path / "public-enrollment"
    app, metadata, state = setup.prepare(folder, "http://127.0.0.1:8777", "reviewer.fixture", public_key=public_file)
    assert app.state.auth.account("reviewer.fixture")[1] == public_bytes(private)
    assert metadata["credential_file"] is None and not (folder / "reviewer.jwk").exists()
    assert state["reviewer"] is None
    assert {row["actor"] for row in state["audit"]} == {SCRIPT}
    assert private["d"] not in (folder / "workspace.json").read_text()


def test_public_key_input_refuses_private_material_before_creating_workspace(tmp_path):
    key_file = tmp_path / "private.json"
    key_file.write_text(json.dumps(generate_reviewer_key()))
    key_file.chmod(0o600)
    folder = tmp_path / "refused-private-import"
    with pytest.raises(ValueError, match="without private key material"):
        setup.prepare(folder, "http://127.0.0.1:8777", "reviewer.fixture", public_key=key_file)
    assert not folder.exists()
