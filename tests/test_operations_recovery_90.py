"""Phase90 operations: backup restoration, restart, revocation, tenant isolation and health reporting."""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from time import time
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
import pytest

from uptime import installation_revocation, mandates, workspace_recovery
from uptime.allocations import settlement_reconciliation
from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key
from uptime.contracts import Principal
from uptime.operations_health import check
from uptime.ramp_records import seal_snapshot
from uptime.ramp_webhooks import RampWebhookInbox, WebhookDeployment, WebhookError
from uptime.ramp_workspace import PACKAGED, RampWorkspace
from uptime.server import create_app
from uptime.storage import case_versions, initialize, save_cases, settlement_events, stored_cases, transition_settlement
from uptime.workbench import Workbench
from uptime.workspace_recovery import (RecoveryError, acknowledge_reconciliation, backup, restore, table_digests,
                                       verify)

ROOT = Path(__file__).resolve().parents[1]
TENANT = "tenant-a"
OTHER = "tenant-b"
BUSINESS = "10000000-0000-4000-8000-000000000001"
OTHER_BUSINESS = "10000000-0000-4000-8000-000000000002"
BILL = "20000000-0000-4000-8000-000000000001"
USER = "alice.reviewer"
ISSUER = "authority.fixture"
COMMENT = {"business_id": BUSINESS, "resource_type": "bill", "resource_id": BILL, "action": "bill.comment.create",
           "payload_sha256": mandates.native_effect_digest("POST", f"/developer/v1/comments/bills/{BILL}",
                                                           b'{"message":"fixture"}')}


@pytest.fixture(autouse=True)
def host_store(tmp_path, monkeypatch):
    root = tmp_path / "host" / "installation-revocations"
    monkeypatch.setattr(installation_revocation, "REVOCATION_ROOT", root)
    return root


def capture(offset=0):
    observed = json.loads(PACKAGED.read_text())
    moment = datetime.now(UTC) + timedelta(seconds=offset - 5)
    observed["observed_at"] = moment.isoformat()
    observed["completed_at"] = (moment + timedelta(seconds=1)).isoformat()
    return seal_snapshot(observed)


def private_dir(path):
    path.mkdir(mode=0o700, parents=True)
    return path


def mandate(db, signer):
    signed = signed_mandate(db, signer)
    mandates.install(db, signed)
    return signed.mandate.mandate_id


def signed_mandate(db, signer):
    at = int(time())
    values = {**mandates.describe(db, USER), "schema_version": "uptime-reviewer-mandate/1", "mandate_id": str(uuid4()),
              "valid_from": at - 1, "valid_until": at + 300, "issuer": ISSUER, "path": "/api/native/actions/dispatch",
              "body_sha256": sha256(b"{}").hexdigest(), "effect": COMMENT}
    m = mandates.Mandate.model_validate(values)
    return mandates.SignedMandate(mandate=m, signature=signer.sign(m.signing_bytes()).hex())


def live_workspace(tmp_path, tenant=TENANT, business=BUSINESS, folder="live"):
    """A sandbox workspace with an enrolled reviewer, an unused mandate, a Ramp capture and ledger history."""
    db = private_dir(tmp_path / folder) / "work.sqlite"
    key = generate_reviewer_key()
    enroll(db, USER, key, "reviewer", "sandbox", tenant)
    signer = Ed25519PrivateKey.generate()
    mandates.register_issuer(db, mandates.Issuer(subject=ISSUER, public_key=signer.public_key().public_bytes_raw().hex(),
                                                 business_id=business, native_actions=("bill.comment.create",)))
    initialize(db)
    workspace = RampWorkspace(Workbench(db, "sandbox", tenant=tenant))
    workspace.import_observation(capture(), business)
    actor = Principal(tenant, USER, "reviewer")
    transition_settlement(db, actor, "case-credit", "record-credit", "125.50")
    transition_settlement(db, actor, "case-credit", "apply-partial", "125.50")
    return db, key, signer


def financial_state(db, tenant=TENANT):
    with sqlite3.connect(db) as conn:
        digests = table_digests(conn)
    keep = {name: digests[name] for name in digests if name.startswith(("allocation_", "settlement_", "case_",
                                                                        "native_capture", "native_installation",
                                                                        "ramp_credit"))}
    return {"tables": keep, "events": [{k: v for k, v in e.items()} for e in settlement_events(db, tenant, "case-credit")],
            "reconciliation": settlement_reconciliation(db, tenant, "case-credit", "125.50"),
            "cases": sorted(c["id"] for c in stored_cases(db, tenant))}


def without_clock(value):
    if isinstance(value, dict):
        return {k: without_clock(v) for k, v in value.items() if k not in {"evaluated_at", "as_of"}}
    if isinstance(value, list):
        return [without_clock(v) for v in value]
    return value


def dashboard(db, key, tenant=TENANT, port=46001):
    app = create_app(db, mode="sandbox", tenant=tenant)
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", port)) as client:
        actor = ReviewerClient(client, DEFAULT_ORIGIN, USER, key)
        board = client.get("/api/dashboard", headers=actor.headers)
        ramp = client.get("/api/ramp/workspace", headers=actor.headers)
        assert board.status_code == ramp.status_code == 200, (board.text, ramp.text)
        token = actor.headers["Authorization"]
    return board.json(), ramp.json(), token


def test_backup_restore_restart_preserves_authority_and_financial_state(tmp_path):
    db, key, signer = live_workspace(tmp_path)
    unused = mandate(db, signer)
    before = financial_state(db)
    assert before["reconciliation"]["applied_cents"] == 6275
    board, ramp, old_token = dashboard(db, key)

    folder = private_dir(tmp_path / "backups") / "nightly"
    manifest = backup(db, folder)
    assert manifest["binding"]["tenant"] == TENANT and manifest["binding"]["mode"] == "sandbox"
    assert manifest["case_history"] == "VERIFIED" and manifest["integrity"] == "ok"
    assert os.stat(folder).st_mode & 0o777 == 0o700
    assert {p.name: os.stat(p).st_mode & 0o777 for p in folder.iterdir()} == {"workspace.sqlite": 0o600,
                                                                              "manifest.json": 0o600}
    assert verify(folder)["database"]["sha256"] == manifest["database"]["sha256"]

    target = private_dir(tmp_path / "restored") / "work.sqlite"
    receipt = restore(folder, target, tenant=TENANT, mode="sandbox")
    assert receipt["fenced_unused_mandates"] == 1 and receipt["revocations_carried_forward"] is None
    assert receipt["reconcile_external_effects_since"] == manifest["created_at"]
    assert financial_state(target) == before
    assert case_versions(target, TENANT, before["cases"][0]) == case_versions(db, TENANT, before["cases"][0])

    # Restart on the restored copy: the same enrolled key signs in, financial views are identical,
    # the previous process's session is not accepted.
    restored_board, restored_ramp, _ = dashboard(target, key, port=46002)
    assert restored_board == board
    # Sandbox views evaluate at the current wall clock; that evaluation instant is not stored state.
    assert without_clock(restored_ramp) == without_clock(ramp)
    app = create_app(target, mode="sandbox", tenant=TENANT)
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 46003)) as client:
        assert client.get("/api/dashboard", headers={"Authorization": old_token}).status_code == 401

    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT revoked,used FROM reviewer_mandate WHERE id=?", (unused,)).fetchone() == (1, 0)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT revoked,used FROM reviewer_mandate WHERE id=?", (unused,)).fetchone() == (0, 0)

    # Configuration recovery keeps the binding: the restored database refuses another tenant or mode.
    with pytest.raises(ValueError):
        create_app(target, mode="sandbox", tenant=OTHER)
    with pytest.raises(ValueError):
        create_app(target, mode="replay", tenant=TENANT)


def test_restore_carries_forward_later_revocations_and_never_overwrites(tmp_path):
    db, _, signer = live_workspace(tmp_path)
    folder = private_dir(tmp_path / "backups") / "before-revocation"
    backup(db, folder)
    mandates.revoke(db, "issuer", ISSUER)  # after the backup

    plain = private_dir(tmp_path / "plain") / "work.sqlite"
    restore(folder, plain, tenant=TENANT, mode="sandbox")
    with sqlite3.connect(plain) as conn:
        assert conn.execute("SELECT revoked FROM mandate_issuer WHERE subject=?", (ISSUER,)).fetchone() == (0,)

    carried = private_dir(tmp_path / "carried") / "work.sqlite"
    receipt = restore(folder, carried, tenant=TENANT, mode="sandbox", previous=db)
    assert receipt["revocations_carried_forward"]["mandate_issuer"] == 1
    with sqlite3.connect(carried) as conn:
        assert conn.execute("SELECT revoked FROM mandate_issuer WHERE subject=?", (ISSUER,)).fetchone() == (1,)

    with pytest.raises(RecoveryError, match="never overwrites"):
        restore(folder, carried, tenant=TENANT, mode="sandbox")
    with pytest.raises(RecoveryError, match="different tenant"):
        restore(folder, private_dir(tmp_path / "x") / "a.sqlite", tenant=OTHER, mode="sandbox")
    with pytest.raises(RecoveryError, match="different tenant"):
        restore(folder, private_dir(tmp_path / "y") / "a.sqlite", tenant=TENANT, mode="replay")
    foreign, _, _ = live_workspace(tmp_path, tenant=OTHER, business=OTHER_BUSINESS, folder="foreign")
    with pytest.raises(RecoveryError, match="different workspace"):
        restore(folder, private_dir(tmp_path / "z") / "a.sqlite", tenant=TENANT, mode="sandbox", previous=foreign)
    with pytest.raises(RecoveryError, match="outside repositories"):
        restore(folder, ROOT / "restored-workspace.sqlite", tenant=TENANT, mode="sandbox")
    with pytest.raises(RecoveryError, match="outside repositories"):
        backup(db, ROOT / "backup-should-not-exist")
    assert not (ROOT / "restored-workspace.sqlite").exists() and not (ROOT / "backup-should-not-exist").exists()


@pytest.mark.parametrize("tamper", ["database", "manifest", "permissions"])
def test_tampered_or_exposed_backup_is_refused(tmp_path, tamper):
    db, _, _ = live_workspace(tmp_path)
    folder = private_dir(tmp_path / "backups") / "copy"
    backup(db, folder)
    if tamper == "database":
        with sqlite3.connect(folder / "workspace.sqlite") as conn:
            conn.execute("UPDATE settlement_event SET awarded='999.00'")
    elif tamper == "manifest":
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["tables"]["settlement_event"]["rows"] += 1
        (folder / "manifest.json").write_text(json.dumps(manifest))
    else:
        os.chmod(folder / "workspace.sqlite", 0o644)
    with pytest.raises(RecoveryError):
        verify(folder)
    target = private_dir(tmp_path / "restored") / "work.sqlite"
    with pytest.raises(RecoveryError):
        restore(folder, target, tenant=TENANT, mode="sandbox")
    assert not target.exists() and not target.with_name(".work.sqlite.restoring").exists()


def test_backup_contains_no_credentials_or_session_material(tmp_path):
    db, key, _ = live_workspace(tmp_path)
    _, _, token = dashboard(db, key, port=46010)
    folder = private_dir(tmp_path / "backups") / "copy"
    backup(db, folder)
    blob = b"".join(p.read_bytes() for p in folder.iterdir())
    private_scalar = key["d"] if isinstance(key, dict) else None
    assert private_scalar and private_scalar.encode() not in blob
    assert token.split()[1].encode() not in blob
    assert b"client_secret" not in blob and b"access_token" not in blob


def test_installation_revocation_survives_restart_and_restore_and_stays_tenant_scoped(tmp_path, host_store):
    db, _, _ = live_workspace(tmp_path)
    other, _, _ = live_workspace(tmp_path, tenant=OTHER, business=OTHER_BUSINESS, folder="other")
    folder = private_dir(tmp_path / "backups") / "pre-revocation"
    backup(db, folder)

    record = installation_revocation.revoke(TENANT, BUSINESS, reason="Customer uninstalled Uptime")
    assert record["duplicate"] is False
    installation_revocation.record_workspace_event(db, TENANT, BUSINESS, record)
    assert installation_revocation.revoke(TENANT, BUSINESS, reason="again")["revoked_at"] == record["revoked_at"]
    assert os.stat(host_store).st_mode & 0o777 == 0o700

    restarted = RampWorkspace(Workbench(db, "sandbox", tenant=TENANT))
    with pytest.raises(PermissionError, match="revoked"):
        restarted.import_observation(capture(), BUSINESS)
    snapshot, _, _, _ = restarted._view()
    bill = next(r for r in snapshot["resources"]["bills"]["records"] if r["kind"] == "bill")
    with pytest.raises(PermissionError, match="revoked"):
        restarted.record_for_native("bills", bill["id"])
    assert restarted.overview()["records"]  # recorded history stays readable

    restored = private_dir(tmp_path / "restored") / "work.sqlite"
    restore(folder, restored, tenant=TENANT, mode="sandbox")
    with pytest.raises(PermissionError, match="revoked"):
        RampWorkspace(Workbench(restored, "sandbox", tenant=TENANT)).import_observation(capture(), BUSINESS)

    # Another tenant's installation is unaffected.
    RampWorkspace(Workbench(other, "sandbox", tenant=OTHER)).import_observation(capture(1), OTHER_BUSINESS)
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM native_installation_event")


def test_revoked_refresh_makes_no_provider_request(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("ramp_refresh_workspace", ROOT / "scripts/ramp_refresh_workspace.py")
    refresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(refresh)
    db, _, _ = live_workspace(tmp_path)
    installation_revocation.revoke(TENANT, BUSINESS, reason="Disconnected")

    class NoNetwork:
        def __getattr__(self, name):
            raise AssertionError("provider touched after revocation: " + name)

    with pytest.raises(PermissionError, match="revoked"):
        refresh.refresh(db, TENANT, provider=NoNetwork())


@pytest.mark.parametrize("damage", ["mode", "foreign-record", "malformed"])
def test_unsafe_revocation_store_fails_closed(tmp_path, host_store, damage):
    db, _, _ = live_workspace(tmp_path)
    if damage == "mode":
        host_store.mkdir(mode=0o755, parents=True)
        os.chmod(host_store, 0o755)
    else:
        installation_revocation.revoke(OTHER, OTHER_BUSINESS, reason="other")
        name = installation_revocation._identity(TENANT, BUSINESS) + ".json"
        body = (host_store / (installation_revocation._identity(OTHER, OTHER_BUSINESS) + ".json")).read_bytes()
        fd = os.open(host_store / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, body if damage == "foreign-record" else b"{not json")
        os.close(fd)
    with pytest.raises(PermissionError, match="unsafe"):
        RampWorkspace(Workbench(db, "sandbox", tenant=TENANT)).import_observation(capture(), BUSINESS)
    report = check(db)
    assert report["installation"]["state"] == "UNKNOWN"
    assert "REVOCATION_STORE_UNSAFE" in {f["code"] for f in report["findings"]}


def test_health_report_separates_retryable_reads_from_uncertain_effects(tmp_path):
    db, _, _ = live_workspace(tmp_path)
    before = sha256(db.read_bytes()).hexdigest()
    report = check(db)
    assert report["status"] == "OK" and report["case_history"] == "VERIFIED"
    assert report["installation"] == {"business_id": BUSINESS, "state": "ACTIVE"}
    assert report["provider_requests"] == 0 and report["writes"] == 0
    assert sha256(db.read_bytes()).hexdigest() == before

    stale = check(db, now=datetime.now(UTC) + timedelta(hours=30))
    assert {f["code"]: f.get("retryable_read") for f in stale["findings"]} == {"RAMP_CAPTURE_STALE": True}

    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO native_capture VALUES(?,?,?,?,'pending')", (TENANT, "0" * 64, datetime.now(UTC).isoformat(), "{}"))
        conn.execute("""CREATE TABLE public_proposal_jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL)""")
        conn.execute("INSERT INTO public_proposal_jobs VALUES('job-1','UNCERTAIN'),('job-2','SUCCEEDED')")
    codes = {f["code"]: f for f in check(db)["findings"]}
    assert codes["RAMP_IMPORT_INTERRUPTED"]["retryable_read"] is True
    assert codes["MODEL_JOB_OUTCOME_UNKNOWN"]["retryable_read"] is False

    outbox = tmp_path / "live" / "native.outbox.sqlite3"
    with sqlite3.connect(outbox) as conn:
        conn.execute("CREATE TABLE rw_outbox (tenant TEXT, id TEXT, plan TEXT, status TEXT, review TEXT, remote_id TEXT,"
                     " remote_state TEXT, attempted_at TEXT, PRIMARY KEY(tenant,id))")
        conn.execute("INSERT INTO rw_outbox(tenant,id,plan,status) VALUES(?,?,?,?)", (TENANT, "a1", "{}", "UNCERTAIN"))
    effect = {f["code"]: f for f in check(db, outbox=outbox)["findings"]}["EXTERNAL_EFFECT_UNCERTAIN"]
    assert effect["count"] == 1 and effect["retryable_read"] is False
    assert {f["code"] for f in check(db, outbox=tmp_path / "missing.sqlite3")["findings"]} >= {"OUTBOX_MISSING"}


def test_health_report_flags_quarantined_webhook_after_conflicting_replay(tmp_path):
    import hmac
    db, _, _ = live_workspace(tmp_path)
    secret = os.urandom(32)
    path = tmp_path / "live" / "native.outbox.sqlite3"
    inbox = RampWebhookInbox(path, WebhookDeployment(deployment_id="dep-1", tenant=TENANT, business_id=BUSINESS,
                                                    subscription_id=str(uuid4()), service_key="svc-1", secret=secret,
                                                    event_types=frozenset({"bills.updated"})))

    def send(event, with_id=True):
        raw = json.dumps(event).encode()
        headers = {"x-ramp-signature": hmac.new(secret, raw, sha256).hexdigest()}
        if with_id:
            headers["x-ramp-webhook-id"] = event["id"]
        return inbox.receive(raw, headers)

    send({"type": "webhooks.verification", "challenge": "abc"}, with_id=False)
    inbox.record_verification("abc", {"success": True})
    event = {"id": str(uuid4()), "type": "bills.updated", "business_id": BUSINESS,
             "created_at": datetime.now(UTC).isoformat(), "object": {"id": BILL}}
    assert send(event)["status"] == "QUEUED"
    assert send(event)["duplicate"] is True
    with pytest.raises(WebhookError):
        send(dict(event, created_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat()))
    report = check(db, outbox=path)
    assert report["webhooks"] == {"quarantined": 1}
    assert "WEBHOOK_QUARANTINED" in {f["code"] for f in report["findings"]}
    assert secret.hex() not in json.dumps(report)


def test_health_report_alerts_actionable_claim_cutoffs_only(tmp_path):
    db, _, _ = live_workspace(tmp_path)
    now = datetime.now(UTC)
    soon, later = (now + timedelta(days=3)).isoformat(), (now + timedelta(days=30)).isoformat()
    save_cases(db, TENANT, [
        {"id": "eligible-soon", "outcome": "ELIGIBLE", "stage": "EVALUATED", "claim_cutoff": soon},
        {"id": "missing-soon", "outcome": "INSUFFICIENT_EVIDENCE", "stage": "REVIEW_REQUIRED", "claim_cutoff_exclusive": soon},
        {"id": "ineligible-soon", "outcome": "INELIGIBLE", "stage": "EVALUATED", "claim_cutoff": soon},
        {"id": "eligible-later", "outcome": "ELIGIBLE", "stage": "EVALUATED", "claim_cutoff": later},
    ])
    finding = {f["code"]: f for f in check(db, now=now)["findings"]}["CLAIM_DEADLINE_APPROACHING"]
    assert {c["case_id"]: c["outcome"] for c in finding["cases"]} == {
        "eligible-soon": "ELIGIBLE", "missing-soon": "INSUFFICIENT_EVIDENCE"}


def test_configuration_custody_is_checked_without_reading_contents(tmp_path):
    db, _, _ = live_workspace(tmp_path)
    config = private_dir(tmp_path / "config")
    good, loose = config / "ramp-sandbox.json", config / "loose.json"
    for path, mode in ((good, 0o600), (loose, 0o644)):
        path.write_text('{"client_secret":"do-not-print-this-value"}')
        os.chmod(path, mode)
    report = check(db, config_files=[good, loose, config / "absent.json"])
    assert [c["custody"] for c in report["configuration"]] == ["PROTECTED", "UNSAFE_CUSTODY", "MISSING"]
    assert "do-not-print-this-value" not in json.dumps(report)
    assert report["status"] == "ATTENTION"


def test_operator_commands_print_no_secrets_and_signal_attention(tmp_path, capsys):
    import importlib.util

    def load(name):
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    db, key, _ = live_workspace(tmp_path)
    folder = private_dir(tmp_path / "backups") / "cli"
    load("workspace_recovery").main(["backup", "--db", str(db), "--output", str(folder)])
    load("workspace_recovery").main(["verify", "--backup", str(folder)])
    target = private_dir(tmp_path / "restored") / "work.sqlite"
    load("workspace_recovery").main(["restore", "--backup", str(folder), "--target", str(target),
                                     "--tenant", TENANT, "--mode", "sandbox", "--previous", str(db)])
    revoke = load("revoke_installation")
    revoke.main(["revoke", "--db", str(db), "--tenant", TENANT, "--reason", "Customer uninstalled"])
    revoke.main(["status", "--db", str(db), "--tenant", TENANT])
    health = load("operations_check")
    assert health.main(["--db", str(target)]) == 2  # restore reconciliation pending
    load("workspace_recovery").main(["acknowledge", "--db", str(target), "--operator", "ops.lead",
                                     "--note", "Bill threads read back since the backup; no later deliveries"])
    assert health.main(["--db", str(target)]) == 0
    assert health.main(["--db", str(db), "--stale-hours", "1", "--deadline-days", "1"]) in (0, 2)
    output = capsys.readouterr().out
    assert '"state": "REVOKED"' in output and '"fenced_unused_mandates": 0' in output
    assert key["d"] not in output


def test_restore_blocks_native_preparation_until_reconciled(tmp_path):
    db, _, _ = live_workspace(tmp_path)
    folder = private_dir(tmp_path / "backups") / "copy"
    manifest = backup(db, folder)
    target = private_dir(tmp_path / "restored") / "work.sqlite"
    receipt = restore(folder, target, tenant=TENANT, mode="sandbox")
    assert receipt["native_actions"] == "BLOCKED_UNTIL_RECONCILED"
    workspace = RampWorkspace(Workbench(target, "sandbox", tenant=TENANT))
    snapshot, _, _, _ = workspace._view()
    bill = next(r for r in snapshot["resources"]["bills"]["records"] if r["kind"] == "bill")
    with pytest.raises(PermissionError, match="reconcile"):
        workspace.record_for_native("bills", bill["id"])
    pending = {f["code"]: f for f in check(target)["findings"]}["RESTORE_RECONCILIATION_PENDING"]
    assert pending["reconcile_since"] == manifest["created_at"]

    with pytest.raises(RecoveryError):
        acknowledge_reconciliation(target, "Not An Operator", "checked")
    done = acknowledge_reconciliation(target, "ops.lead", "Ramp threads read back since the backup")
    assert done["restore_epochs"] == 1
    with pytest.raises(RecoveryError, match="No restored epoch"):
        acknowledge_reconciliation(target, "ops.lead", "again")
    with sqlite3.connect(target) as conn:
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            conn.execute("UPDATE operations_restore SET reconciled_at=NULL")
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            conn.execute("DELETE FROM operations_restore")
    assert "RESTORE_RECONCILIATION_PENDING" not in {f["code"] for f in check(target)["findings"]}


def test_deleted_host_store_cannot_reopen_a_revoked_workspace(tmp_path, host_store):
    import shutil
    db, _, _ = live_workspace(tmp_path)
    record = installation_revocation.revoke(TENANT, BUSINESS, reason="Customer uninstalled Uptime")
    installation_revocation.record_workspace_event(db, TENANT, BUSINESS, record)
    shutil.rmtree(host_store)
    assert installation_revocation.status(TENANT, BUSINESS) is None
    with pytest.raises(PermissionError, match="revoked"):
        RampWorkspace(Workbench(db, "sandbox", tenant=TENANT)).import_observation(capture(), BUSINESS)
    report = check(db)
    assert report["installation"]["state"] == "REVOKED"
    assert "REVOCATION_HOST_RECORD_MISSING" in {f["code"] for f in report["findings"]}


def test_repository_paths_are_refused_through_symlinks_and_case_variants(tmp_path):
    db, _, _ = live_workspace(tmp_path)
    link = private_dir(tmp_path / "links") / "repo"
    link.symlink_to(ROOT)
    with pytest.raises(RecoveryError):
        backup(db, link / "backup-via-link")
    folder = private_dir(tmp_path / "backups") / "copy"
    backup(db, folder)
    with pytest.raises(RecoveryError):
        restore(folder, link / "restored.sqlite", tenant=TENANT, mode="sandbox")
    variant = Path(str(ROOT).upper())
    if variant.exists() and variant != ROOT:  # case-insensitive volume
        with pytest.raises(RecoveryError):
            restore(folder, variant / "restored.sqlite", tenant=TENANT, mode="sandbox")
        assert not (ROOT / "restored.sqlite").exists()
    assert not (ROOT / "backup-via-link").exists()


def test_backup_during_concurrent_writes_is_a_consistent_snapshot(tmp_path):
    from threading import Event, Thread
    db, _, _ = live_workspace(tmp_path)
    actor, stop, errors = Principal(TENANT, USER, "reviewer"), Event(), []

    def write():
        n = 0
        while not stop.is_set() and n < 200:
            try:
                transition_settlement(db, actor, f"busy-{n}", "record-credit", "1.00")
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(exc)
            n += 1

    worker = Thread(target=write)
    worker.start()
    try:
        folders = []
        for i in range(3):
            folder = private_dir(tmp_path / "backups" / str(i)) / "copy"
            backup(db, folder)
            folders.append(folder)
    finally:
        stop.set()
        worker.join()
    assert not errors
    for folder in folders:
        manifest = verify(folder)
        assert manifest["integrity"] == "ok" and manifest["case_history"] == "VERIFIED"
        with sqlite3.connect(folder / "workspace.sqlite") as conn:
            events = conn.execute("SELECT count(*) FROM settlement_event").fetchone()[0]
            awards = conn.execute("SELECT count(*) FROM allocation_award").fetchone()[0]
        assert events - 2 == awards - 1  # each busy credit wrote its event and award together


def test_restore_staging_collision_and_corrupt_database_fail_closed(tmp_path):
    import importlib.util
    db, _, _ = live_workspace(tmp_path)
    folder = private_dir(tmp_path / "backups") / "copy"
    backup(db, folder)
    target = private_dir(tmp_path / "restored") / "work.sqlite"
    staging = target.with_name(".work.sqlite.restoring")
    staging.write_bytes(b"")
    with pytest.raises(RecoveryError):
        restore(folder, target, tenant=TENANT, mode="sandbox")
    assert not target.exists() and staging.exists()

    spec = importlib.util.spec_from_file_location("operations_check", ROOT / "scripts/operations_check.py")
    health = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(health)
    corrupt = tmp_path / "restored" / "corrupt.sqlite"
    corrupt.write_bytes(b"SQLite format 3\x00" + b"\x00" * 200)
    with pytest.raises(SystemExit) as stopped:
        health.main(["--db", str(corrupt)])
    assert stopped.value.code == 1


def _refresh_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ramp_refresh_workspace", ROOT / "scripts/ramp_refresh_workspace.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bounded_read_retries_only_follow_transient_failures():
    from uptime.ramp import RampError, RampHTTPError, RampNetworkError
    refresh = _refresh_module()
    waits = []

    def flaky(*failures):
        calls = []

        def run(path, tenant, **options):
            calls.append(options)
            if len(calls) <= len(failures):
                raise failures[len(calls) - 1]
            return {"snapshot": True}, {"digest": "d", "status": "ready"}
        return run, calls

    run, calls = flaky(RampHTTPError(503), RampNetworkError("Sandbox network or response unavailable"))
    assert refresh.refresh_with_retries("db", TENANT, attempts=3, sleep=waits.append, run=run, page_size=5)[2] == 3
    assert waits == [5, 30] and calls == [{"page_size": 5}] * 3

    for refusal in (RampHTTPError(403), RampHTTPError(401), RampError("Exact bills:read grant required"),
                    PermissionError(installation_revocation.REVOKED), ValueError("binding")):
        run, calls = flaky(refusal)
        with pytest.raises(type(refusal)):
            refresh.refresh_with_retries("db", TENANT, attempts=3, sleep=waits.append, run=run)
        assert len(calls) == 1

    run, calls = flaky(RampHTTPError(429), RampHTTPError(429), RampHTTPError(429))
    with pytest.raises(RampHTTPError):
        refresh.refresh_with_retries("db", TENANT, attempts=3, sleep=lambda _: None, run=run)
    assert len(calls) == 3
    for bad in (0, 4, True, "2"):
        with pytest.raises(ValueError):
            refresh.refresh_with_retries("db", TENANT, attempts=bad, run=run)


def test_transport_failures_are_typed_without_leaking_provider_detail(monkeypatch):
    import http.client
    from uptime import ramp
    monkeypatch.setenv("RAMP_ENV", "sandbox")
    monkeypatch.delenv("RAMP_BASE_URL", raising=False)

    class Down:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            raise OSError("connection reset by secret-bearing peer")

        def close(self):
            pass

    monkeypatch.setattr(http.client, "HTTPSConnection", Down)
    provider = object.__new__(ramp.SandboxRampProvider)
    with pytest.raises(ramp.RampNetworkError) as failure:
        provider._http("GET", "business", {"Authorization": "Bearer not-a-real-token"})
    assert isinstance(failure.value, ramp.RampError)
    assert str(failure.value) == "Sandbox network or response unavailable" and failure.value.__cause__ is None


def test_restored_workspace_refuses_new_mandates_until_acknowledged(tmp_path):
    db, _, signer = live_workspace(tmp_path)
    folder = private_dir(tmp_path / "backups") / "copy"
    backup(db, folder)
    target = private_dir(tmp_path / "restored") / "work.sqlite"
    receipt = restore(folder, target, tenant=TENANT, mode="sandbox")
    assert receipt["new_mandates"] == "BLOCKED_UNTIL_RECONCILED"
    with pytest.raises(PermissionError, match="reconcile"):
        mandate(target, signer)
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT count(*) FROM reviewer_mandate WHERE used=0 AND revoked=0").fetchone() == (0,)
    acknowledge_reconciliation(target, "ops.lead", "Ramp threads read back since the backup")
    assert mandate(target, signer)  # new authority only after the acknowledgement
    assert mandate(db, signer)  # the original workspace was never gated


def test_never_restored_workspace_mandate_install_is_byte_identical(tmp_path, monkeypatch):
    import shutil
    db, _, signer = live_workspace(tmp_path)
    assert not Path(str(db) + "-wal").exists()
    gated = private_dir(tmp_path / "gated") / "work.sqlite"
    ungated = private_dir(tmp_path / "ungated") / "work.sqlite"
    shutil.copyfile(db, gated)
    shutil.copyfile(db, ungated)
    assert gated.read_bytes() == ungated.read_bytes()
    signed = signed_mandate(gated, signer)
    calls, real = [], workspace_recovery.require_reconciled

    def observed(conn):
        calls.append(1)
        return real(conn)

    monkeypatch.setattr(workspace_recovery, "require_reconciled", observed)
    mandates.install(gated, signed)
    monkeypatch.setattr(workspace_recovery, "require_reconciled", lambda conn: None)
    mandates.install(ungated, signed)
    assert calls == [1]  # the gate ran on the gated copy and refused nothing
    assert not Path(str(gated) + "-wal").exists() and not Path(str(ungated) + "-wal").exists()
    assert gated.read_bytes() == ungated.read_bytes()
    with sqlite3.connect(gated) as conn:
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='operations_restore'").fetchone() is None


def test_revocation_tenant_domain_is_pinned_to_the_workspace_id_domain():
    """Revocation keys use the exact workspace tenant domain. A D03 change to Id must update both deliberately."""
    from typing import get_args
    from uptime.correspondence_types import Id
    constraint = next(m for m in get_args(Id)[1:] if getattr(m, "pattern", None))
    assert constraint.pattern == "^" + installation_revocation.TENANT.pattern + "$"
    for accepted in ("bears", "tenant-a", "Tenant.B:01/x", "a" * 96):
        assert installation_revocation._identity(accepted, BUSINESS)
    for refused in ("", " bears", "bears ", "-bears", "a" * 97, "b\u00e9ars", "bears\n"):
        with pytest.raises(ValueError):
            installation_revocation._identity(refused, BUSINESS)
    lettered = "a0000000-0000-4000-8000-00000000000b"
    assert installation_revocation._identity("bears", lettered)
    with pytest.raises(ValueError):
        installation_revocation._identity("bears", lettered.upper())  # provider IDs are never case-folded


def test_deadline_alerts_exclude_filed_and_closed_claims_and_report_missed_cutoffs(tmp_path):
    from uptime.claim_identity import claim_key, reserve_claim
    from uptime.storage import database
    db, _, _ = live_workspace(tmp_path)
    now = datetime.now(UTC)
    identity = dict(tenant=TENANT, vendor="Acme Cloud", account="acct-1", agreement_id="agreement-1",
                    agreement_version="v1", service="Compute", month="2026-10", remedy="availability")
    soon, past, old = ((now + timedelta(days=d)).isoformat() for d in (2, -3, -60))
    save_cases(db, TENANT, [
        {"id": "due-open", "outcome": "ELIGIBLE", "stage": "EVALUATED", "claim_cutoff": soon},
        {"id": "due-awarded", "outcome": "ELIGIBLE", "stage": "AWARDED", "claim_cutoff": soon},
        {"id": "due-filed", "outcome": "ELIGIBLE", "stage": "EVALUATED", "claim_cutoff": soon,
         "obligation_id": claim_key(**identity)},
        {"id": "missed-open", "outcome": "INSUFFICIENT_EVIDENCE", "stage": "REVIEW_REQUIRED", "claim_cutoff": past},
        {"id": "missed-long-ago", "outcome": "ELIGIBLE", "stage": "EVALUATED", "claim_cutoff": old},
    ])
    with database(db) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        reserve_claim(conn, **identity, route="vendor", case_id="due-filed", packet_digest="a" * 64,
                      scope={"account": "acct-1"}, receipt_id="receipt-1", at=now.isoformat())
    report = check(db, now=now)
    codes = {f["code"]: f for f in report["findings"]}
    assert [c["case_id"] for c in codes["CLAIM_DEADLINE_APPROACHING"]["cases"]] == ["due-open"]
    assert codes["CLAIM_DEADLINE_PASSED_UNFILED"]["level"] == "INFO"
    assert [c["case_id"] for c in codes["CLAIM_DEADLINE_PASSED_UNFILED"]["cases"]] == ["missed-open"]
    assert report["deadlines"] == {"status": "EVALUATED", "approaching": 1, "passed_unfiled": 1, "window_days": 7}


def test_replay_workspace_does_not_raise_wall_clock_deadline_alerts(tmp_path):
    db = private_dir(tmp_path / "replay") / "work.sqlite"
    enroll(db, USER, generate_reviewer_key(), "reviewer", "replay", TENANT)
    initialize(db)
    soon = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    save_cases(db, TENANT, [{"id": "authored", "outcome": "ELIGIBLE", "stage": "EVALUATED", "claim_cutoff": soon}])
    report = check(db)
    assert report["deadlines"]["status"] == "NOT_EVALUATED"
    assert not {f["code"] for f in report["findings"]} & {"CLAIM_DEADLINE_APPROACHING", "CLAIM_DEADLINE_PASSED_UNFILED"}


def test_clock_skew_and_capture_near_limit_are_reported(tmp_path):
    db, _, _ = live_workspace(tmp_path)
    now = datetime.now(UTC)
    behind = {f["code"] for f in check(db, now=now - timedelta(hours=1))["findings"]}
    assert "CLOCK_BEHIND_CAPTURE" in behind and "RAMP_CAPTURE_STALE" not in behind
    near = check(db, now=now + timedelta(hours=21))
    finding = {f["code"]: f for f in near["findings"]}["RAMP_CAPTURE_NEAR_LIMIT"]
    assert finding["level"] == "INFO" and finding["retryable_read"] is True
    assert datetime.fromisoformat(finding["expires_at"]) - now < timedelta(hours=24)
    assert near["status"] == "OK"
    assert "RAMP_CAPTURE_NEAR_LIMIT" not in {f["code"] for f in check(db, now=now)["findings"]}


def _preflight_probes(**overrides):
    from collections import namedtuple
    usage = namedtuple("usage", "total used free")
    probes = dict(environ={"RAMP_ENV": "sandbox", "RAMP_BASE_URL": "https://demo-api.ramp.com"},
                  listeners=lambda: [("Python", "127.0.0.1", 8776), ("python3.1", "[::1]", 8777)],
                  processes=lambda: ["zsh", "python3.13", "node"],
                  disk_usage=lambda path: usage(500 * 2 ** 30, 490 * 2 ** 30, 10 * 2 ** 30))
    probes.update(overrides)
    return probes


def test_preflight_is_ready_for_a_safe_local_demo_machine(tmp_path):
    from uptime import operations_preflight
    db, _, _ = live_workspace(tmp_path)
    backups = private_dir(tmp_path / "backups")
    backup(db, backups / "before-demo")
    config = private_dir(tmp_path / "config") / "ramp-sandbox.json"
    config.write_text('{"client_secret":"never-printed"}')
    os.chmod(config, 0o600)
    before = db.read_bytes()
    report = operations_preflight.check([db], ports=[8776, 8777], backup_dir=backups, config_files=[config],
                                        **_preflight_probes())
    assert report["status"] == "READY" and report["findings"] == []
    assert report["workspaces"][0]["backup"]["verified"] is True
    assert report["ports"] == {"8776": {"listening": True, "addresses": ["127.0.0.1"]},
                               "8777": {"listening": True, "addresses": ["[::1]"]}}
    assert report["provider_requests"] == 0 and report["writes"] == 0 and db.read_bytes() == before
    assert "never-printed" not in json.dumps(report)


def test_preflight_flags_tunnels_exposed_ports_wrong_ramp_environment_and_low_disk(tmp_path):
    from collections import namedtuple
    from uptime import operations_preflight
    db, _, _ = live_workspace(tmp_path)
    usage = namedtuple("usage", "total used free")
    report = operations_preflight.check(
        [db], ports=[8776, 8777, 8780],
        **_preflight_probes(environ={"RAMP_ENV": "production", "RAMP_BASE_URL": "https://api.ramp.com"},
                            listeners=lambda: [("Python", "*", 8776), ("Python", "127.0.0.1", 8777)],
                            processes=lambda: ["zsh", "ngrok", "cloudflared"],
                            disk_usage=lambda path: usage(500 * 2 ** 30, 499 * 2 ** 30, 2 ** 30)))
    codes = {f["code"]: f for f in report["findings"]}
    assert report["status"] == "ATTENTION"
    assert codes["TUNNEL_PROCESS_RUNNING"]["processes"] == ["cloudflared", "ngrok"]
    assert codes["LISTENER_NOT_LOOPBACK"]["port"] == 8776 and codes["LISTENER_NOT_LOOPBACK"]["addresses"] == ["*"]
    assert codes["PORT_NOT_LISTENING"]["level"] == "INFO" and codes["PORT_NOT_LISTENING"]["port"] == 8780
    assert "RAMP_ENV_NOT_SANDBOX" in codes and codes["DISK_LOW"]["free_bytes"] == 2 ** 30
    unavailable = operations_preflight.check([db], ports=[8776], **_preflight_probes(
        listeners=lambda: None, processes=lambda: None))
    assert {"LISTENERS_UNAVAILABLE", "PROCESS_LIST_UNAVAILABLE"} <= {f["code"] for f in unavailable["findings"]}


def test_preflight_requires_a_recent_verified_backup_of_each_exact_workspace(tmp_path):
    from uptime import operations_preflight
    fresh, _, _ = live_workspace(tmp_path, folder="fresh")
    stale, _, _ = live_workspace(tmp_path, folder="stale")
    broken, _, _ = live_workspace(tmp_path, folder="broken")
    unbacked, _, _ = live_workspace(tmp_path, folder="unbacked")
    backups = private_dir(tmp_path / "backups")
    backup(fresh, backups / "fresh")
    backup(stale, backups / "stale", now=datetime.now(UTC) - timedelta(days=2))
    backup(broken, backups / "broken")
    with sqlite3.connect(backups / "broken" / "workspace.sqlite") as conn:
        conn.execute("UPDATE settlement_event SET awarded='999.00'")
    # Every database is named work.sqlite; only the exact binding (tenant, mode, realm) may match.
    report = operations_preflight.check([fresh, stale, broken, unbacked, tmp_path / "absent.sqlite"],
                                        backup_dir=backups, **_preflight_probes())
    by_path = {f.get("path"): f["code"] for f in report["findings"]}
    assert by_path == {str(stale): "BACKUP_STALE", str(broken): "BACKUP_INVALID", str(unbacked): "BACKUP_MISSING",
                       str(tmp_path / "absent.sqlite"): "WORKSPACE_MISSING"}
    assert report["workspaces"][0]["backup"]["verified"] is True


def test_preflight_reads_process_names_only_and_parses_listeners(monkeypatch):
    import subprocess
    from uptime import operations_preflight
    calls = []

    class Done:
        def __init__(self, stdout):
            self.stdout = stdout

    def run(args, **kwargs):
        calls.append(args)
        return Done("/usr/local/bin/ngrok\n/bin/zsh\n")

    monkeypatch.setattr(subprocess, "run", run)
    assert operations_preflight._process_names() == ["ngrok", "zsh"]
    assert calls == [["ps", "-axo", "comm="]]  # the command name column only; never arguments
    sample = "p10\ncPython\nf3\nn127.0.0.1:8776\np11\ncnode\nf4\nn*:3000\nf5\nn[::1]:8777\n"
    assert operations_preflight.parse_lsof(sample) == [("Python", "127.0.0.1", 8776), ("node", "*", 3000),
                                                       ("node", "[::1]", 8777)]


def test_preflight_command_prints_json_and_signals_attention(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("operations_preflight_cli", ROOT / "scripts/operations_preflight.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    db, _, _ = live_workspace(tmp_path)
    code = cli.main(["--workspace", str(db), "--backup-dir", str(private_dir(tmp_path / "empty-backups"))])
    report = json.loads(capsys.readouterr().out)
    assert code == 2 and report["schema"] == "uptime-operations-preflight/1"
    assert "BACKUP_MISSING" in {f["code"] for f in report["findings"]}


def _w1_native(tmp_path, folder="native"):
    """W1's real workflow, inbox and simulated provider on a native outbox file, beside a bound workspace."""
    from test_ramp_workflow import BILL as W1_BILL, TENANT as W1_TENANT, make_finding
    from test_ramp_workflow_webhooks import NOW as W1_NOW, BUSINESS as W1_BUSINESS, REQUEST_ID, TRIGGER, activate, \
        deployment, native_event, signed
    from uptime.auth_keys import public_bytes
    from uptime.ramp_workflow import RampWorkflow, SimulatedWorkflowProvider, WorkflowReviewer

    base = private_dir(tmp_path / folder)
    workspace = base / "work.sqlite"
    enroll(workspace, USER, generate_reviewer_key(), "reviewer", "sandbox", W1_TENANT)
    initialize(workspace)
    outbox = base / "native.outbox.sqlite3"
    inbox = RampWebhookInbox(outbox, deployment(), clock=lambda: W1_NOW)
    activate(inbox)
    inbox.receive(*signed(native_event()))
    records = {("bills", W1_BILL): {"id": W1_BILL, "status": "OPEN", "approval_status": "PENDING"},
               ("unified-requests", REQUEST_ID): {"id": REQUEST_ID, "request_status": "SUBMITTED"}}
    findings = {key: make_finding(*key) for key in records}
    provider = SimulatedWorkflowProvider(business_id=W1_BUSINESS, records=records, clock=lambda: W1_NOW,
                                        contexts={TRIGGER: {"node_id": "node-external-review", "service_key": "Uptime-v4"}})
    key = generate_reviewer_key()
    reviewers = {"test-reviewer": WorkflowReviewer(public_bytes(key))}

    def open_flow(path):
        box = RampWebhookInbox(path, deployment(), clock=lambda: W1_NOW)
        return RampWorkflow(path, tenant=W1_TENANT, business_id=W1_BUSINESS, finding_resolver=lambda t, i: findings[t, i],
                            reviewers=reviewers, inbox=box, inspector_origins=("https://inspector.example",),
                            clock=lambda: W1_NOW)
    open_flow(outbox)  # creates W1's rw_installation and rw_outbox tables
    return dict(workspace=workspace, outbox=outbox, provider=provider, key=key, open=open_flow, tenant=W1_TENANT,
                bill=W1_BILL, trigger=TRIGGER)


def _restore_native(tmp_path, env, folder, **options):
    target_dir = private_dir(tmp_path / "restored")
    receipt = restore(folder, target_dir / "work.sqlite", tenant=env["tenant"], mode="sandbox",
                      outbox_target=target_dir / "native.outbox.sqlite3", **options)
    return receipt, target_dir / "native.outbox.sqlite3"


def test_restored_reviewed_comment_delivered_after_backup_is_never_reposted(tmp_path):
    from test_ramp_workflow import review as w1_review
    from uptime.ramp_workflow import WorkflowError
    env = _w1_native(tmp_path)
    flow, provider = env["open"](env["outbox"]), env["provider"]
    plan = flow.prepare_comment("bills", env["bill"], provider=provider)
    w1_review(flow, env["key"], plan)
    folder = private_dir(tmp_path / "backups") / "reviewed"
    manifest = backup(env["workspace"], folder, outbox=env["outbox"])
    assert manifest["outbox"]["status_counts"] == {"REVIEWED": 1}
    assert flow.execute(plan["id"], provider=provider)["status"] == "DELIVERED"  # after the backup
    assert len(provider.calls) == 1

    receipt, restored = _restore_native(tmp_path, env, folder)
    assert receipt["outbox"]["comment_reviews_cleared"] == 1 and receipt["outbox"]["marked_uncertain"] == 0
    again = env["open"](restored)
    assert again.get(plan["id"])["status"] == "PREPARED"
    with pytest.raises(WorkflowError, match="review"):
        again.execute(plan["id"], provider=provider)
    w1_review(again, env["key"], again.get(plan["id"]))
    result = again.execute(plan["id"], provider=provider)
    assert result["status"] == "DELIVERED" and result["remote_state"]["verification"] == "EXACT_DISCUSSION_GET"
    assert len(provider.calls) == 1  # the marker was already in the thread: zero new POSTs
    assert os.stat(restored).st_mode & 0o777 == 0o600 and os.stat(restored).st_nlink == 1


def test_restored_dispatching_comment_can_only_be_reconciled(tmp_path):
    from test_ramp_workflow import review as w1_review
    from uptime.ramp_workflow import WorkflowError
    env = _w1_native(tmp_path)
    flow, provider = env["open"](env["outbox"]), env["provider"]
    plan = flow.prepare_comment("bills", env["bill"], provider=provider)
    w1_review(flow, env["key"], plan)
    with sqlite3.connect(env["outbox"]) as conn:
        conn.execute("UPDATE rw_outbox SET status='DISPATCHING'")
    folder = private_dir(tmp_path / "backups") / "dispatching"
    backup(env["workspace"], folder, outbox=env["outbox"])
    receipt, restored = _restore_native(tmp_path, env, folder)
    assert receipt["outbox"]["marked_uncertain"] == 1
    again = env["open"](restored)
    assert again.get(plan["id"])["status"] == "UNCERTAIN"
    with pytest.raises(WorkflowError, match="reconcile"):
        again.execute(plan["id"], provider=provider)
    assert again.reconcile(plan["id"], provider=provider)["status"] == "UNCERTAIN"  # absence never authorizes resend
    assert provider.calls == []
    codes = {f["code"] for f in check(tmp_path / "restored" / "work.sqlite", outbox=restored)["findings"]}
    assert {"EXTERNAL_EFFECT_UNCERTAIN", "RESTORE_RECONCILIATION_PENDING"} <= codes


def test_restored_metadata_is_uncertain_and_unprepared_comments_are_unchanged(tmp_path):
    from test_ramp_workflow import review as w1_review
    from uptime.ramp_workflow import WorkflowError
    env = _w1_native(tmp_path)
    flow, provider = env["open"](env["outbox"]), env["provider"]
    metadata = flow.prepare_metadata(env["trigger"], provider=provider, url="https://inspector.example/cases/local-case")
    w1_review(flow, env["key"], metadata)
    comment = flow.prepare_comment("bills", env["bill"], provider=provider)
    with sqlite3.connect(env["outbox"]) as conn:
        plans = dict(conn.execute("SELECT id,plan FROM rw_outbox").fetchall())
    folder = private_dir(tmp_path / "backups") / "metadata"
    backup(env["workspace"], folder, outbox=env["outbox"])
    receipt, restored = _restore_native(tmp_path, env, folder)
    assert receipt["outbox"]["marked_uncertain"] == 1 and receipt["outbox"]["comment_reviews_cleared"] == 0
    again = env["open"](restored)
    assert again.get(metadata["id"])["status"] == "UNCERTAIN"
    assert again.get(comment["id"])["status"] == "PREPARED"
    with pytest.raises(WorkflowError, match="reconcile"):
        again.execute(metadata["id"], provider=provider)
    assert provider.calls == []
    with sqlite3.connect(restored) as conn:
        assert dict(conn.execute("SELECT id,plan FROM rw_outbox").fetchall()) == plans  # plans never rewritten


def test_outbox_restore_carries_quarantine_forward_and_refuses_mismatches(tmp_path):
    env = _w1_native(tmp_path)
    folder = private_dir(tmp_path / "backups") / "active"
    backup(env["workspace"], folder, outbox=env["outbox"])
    with sqlite3.connect(env["outbox"]) as conn:  # after the backup, a conflicting event quarantined it
        conn.execute("UPDATE rw_deployment SET status='quarantined'")
    receipt, restored = _restore_native(tmp_path, env, folder, previous_outbox=env["outbox"])
    assert receipt["outbox"]["quarantine_carried_forward"] == 1
    with sqlite3.connect(restored) as conn:
        assert {r[0] for r in conn.execute("SELECT status FROM rw_deployment")} == {"quarantined"}

    plain = private_dir(tmp_path / "plain") / "work.sqlite"
    with pytest.raises(RecoveryError, match="previous outbox"):
        restore(folder, plain, tenant=env["tenant"], mode="sandbox", previous_outbox=env["outbox"])
    no_outbox = private_dir(tmp_path / "backups-plain") / "copy"
    backup(env["workspace"], no_outbox)
    with pytest.raises(RecoveryError, match="does not contain"):
        restore(no_outbox, plain, tenant=env["tenant"], mode="sandbox", outbox_target=plain.with_name("o.sqlite3"))
    with pytest.raises(RecoveryError, match="not a native outbox"):
        backup(env["workspace"], private_dir(tmp_path / "b2") / "x", outbox=live_workspace(tmp_path, folder="other-ws")[0])
    foreign = _w1_native(tmp_path, folder="foreign")
    db, _, _ = live_workspace(tmp_path, folder="tenant-a-ws")
    with pytest.raises(RecoveryError, match="different tenant"):
        backup(db, private_dir(tmp_path / "b3") / "x", outbox=foreign["outbox"])
    rewritten = private_dir(tmp_path / "backups-vacuum") / "copy"
    backup(env["workspace"], rewritten, outbox=env["outbox"])
    conn = sqlite3.connect(rewritten / "outbox.sqlite")
    conn.execute("VACUUM")  # same rows, different bytes: only the file checksum can tell
    conn.close()
    with pytest.raises(RecoveryError, match="does not match its manifest"):
        verify(rewritten)
    with sqlite3.connect(folder / "outbox.sqlite") as conn:
        assert conn.execute("UPDATE rw_deployment SET status='active-tampered'").rowcount == 1
    with pytest.raises(RecoveryError, match="outbox"):
        verify(folder)
    assert not plain.exists() and not plain.with_name("o.sqlite3").exists()
