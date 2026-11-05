"""Operational source grants through the mounted HTTP inbox and its real signature dependency."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from scripts.deliver_evidence import deliver
from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient, service_headers
from uptime.auth_keys import generate_reviewer_key
from uptime.correspondence_types import Scope
from uptime.server import create_app
from uptime.source_config import SenderCredential, SourceConfig, init_config, load_private, update_source

CLAIM = "inbox-source-intake-1"
EVENTS = f"/api/correspondence/claims/{CLAIM}/events"
SCOPE = Scope(account="test-account", vendor="Twilio", contract="signed-agreement", service="Twilio Messaging API",
              component="api-east", invoice="oct-bill", incident="oct-synthetic-outage", currency="USD",
              month="2026-10", region="east")


def app_for(path, db, *, enabled=True, tenant="bears"):
    config = load_private(path, SourceConfig)
    app = create_app(db, origin=DEFAULT_ORIGIN, approvals_enabled=enabled, tenant=tenant,
                     service_credentials=config.credentials("replay", DEFAULT_ORIGIN, tenant))
    config.bind(app.state.correspondence)
    return app


def local(app):
    return TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1",50000))


def raw_event(s=SCOPE, kind="status", event_id="event.source"):
    body = {"kind":kind, "start":"2026-10-08T01:00:00Z", "end":"2026-10-08T02:00:00Z"}
    if kind == "impact":
        body.update(affected=True, exclusion="none")
    return json.dumps({"event_id":event_id, "scope":s.model_dump(), "body":body}, indent=1).encode()


def setup(tmp_path, tenant="bears"):
    config, sender_file = tmp_path/"public-grants.json", tmp_path/"private-status.json"
    init_config(config, "replay", DEFAULT_ORIGIN, tenant)
    update_source(config, "add", "status.synthetic", source="status", scope=SCOPE, sender_path=sender_file)
    db = tmp_path/"workspace.db"
    human = generate_reviewer_key()
    enroll(db, "source.operator", human, tenant=tenant)
    sender = load_private(sender_file, SenderCredential)
    return config, db, sender, human


def signed(client, sender, raw):
    instance = client.get("/api/auth/context").json()["instance"]
    return service_headers(instance=instance, origin=DEFAULT_ORIGIN, path=EVENTS, body=raw,
                           subject=sender.subject, key=sender)


def test_signed_delivery_native_receipt_and_forgery_rejection(tmp_path):
    path, db, sender, human = setup(tmp_path)
    assert sender.private_key not in path.read_text()
    app = app_for(path, db)
    with local(app) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "source.operator", human)
        create = reviewer.post("/api/correspondence/claims", {"claim_id":CLAIM,"scope":SCOPE.model_dump()})
        assert create.status_code == 200, create.text
        raw = raw_event()
        headers = signed(client, sender, raw)
        assert sender.private_key not in str(headers)
        from time import time
        from uptime.auth import service_message
        stale_time = str(int(time())-121)
        expired = {**headers, "X-Uptime-Time":stale_time,
                   "X-Uptime-Proof":sender.sign(service_message(app.state.auth.instance, DEFAULT_ORIGIN,
                       sender.subject, EVENTS, raw, stale_time, headers["X-Uptime-Nonce"], sender.tenant, sender.mode))}
        assert client.post(EVENTS, content=raw, headers=expired).status_code == 403
        assert client.post(EVENTS, content=raw+b" ", headers=headers).status_code == 403
        assert client.post(EVENTS, content=raw, headers={**headers,"Origin":"http://127.0.0.1:8766"}).status_code == 403
        assert client.post(EVENTS, content=raw, headers={k:v for k,v in headers.items() if k!="X-Uptime-Proof"}).status_code == 403
        receipt = client.post(EVENTS, content=raw, headers=headers)
        assert receipt.status_code == 200 and set(receipt.json()) == {"event_id","digest","received_at"}
        assert client.post(EVENTS, content=raw, headers=headers).status_code == 403
        assert deliver(client, sender, CLAIM, raw) == receipt.json()
        # Correct keys still cannot sign outside their explicit source-kind and complete scope.
        wrong = [raw_event(kind="impact"), raw_event(SCOPE.model_copy(update={"component":"api-west"})),
                 raw_event(SCOPE.model_copy(update={"contract":"other-agreement"})),
                 raw_event(SCOPE.model_copy(update={"invoice":"other-invoice"}))]
        for body in wrong:
            assert client.post(EVENTS, content=body, headers=signed(client, sender, body)).status_code == 403
        with sqlite3.connect(db) as connection:
            assert connection.execute("SELECT count(*) FROM inbox_delivery").fetchone()[0] == 1
    # The same private credential cannot act through the default closed launch.
    with local(app_for(path, db, enabled=False)) as closed:
        assert closed.post(EVENTS, content=raw, headers=signed(closed, sender, raw)).status_code == 403


def test_rotate_revoke_and_process_restart_reject_old_authority(tmp_path):
    path, db, old, human = setup(tmp_path)
    raw = raw_event()
    with local(app_for(path, db)) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "source.operator", human)
        assert reviewer.post("/api/correspondence/claims", {"claim_id":CLAIM,"scope":SCOPE.model_dump()}).status_code == 200
        before = signed(client, old, raw)
    # Isolate instance rotation from key rotation: same DB, grant and key, previously unused proof.
    with local(app_for(path, db)) as same_key:
        assert same_key.post(EVENTS, content=raw, headers=before).status_code == 403
        assert deliver(same_key, old, CLAIM, raw)["event_id"] == "event.source"
    new_file = tmp_path/"rotated.json"
    update_source(path, "rotate", old.subject, sender_path=new_file)
    new = load_private(new_file, SenderCredential)
    with local(app_for(path, db)) as restarted:
        assert restarted.post(EVENTS, content=raw, headers=before).status_code == 403
        assert restarted.post(EVENTS, content=raw, headers=signed(restarted, old, raw)).status_code == 403
        assert deliver(restarted, new, CLAIM, raw)["event_id"] == "event.source"
    update_source(path, "revoke", new.subject)
    with local(app_for(path, db)) as revoked:
        assert revoked.post(EVENTS, content=raw, headers=signed(revoked, new, raw)).status_code == 403


def test_protected_files_refuse_symlinks_permissive_permissions_and_wrong_audiences(tmp_path):
    config, _, _, _ = setup(tmp_path)
    loaded = load_private(config, SourceConfig)
    for mode, origin, tenant in [("sandbox",DEFAULT_ORIGIN,"bears"),("replay","http://127.0.0.1:8888","bears"),
                                  ("replay",DEFAULT_ORIGIN,"another-tenant")]:
        with pytest.raises(ValueError):
            loaded.credentials(mode, origin, tenant)
    alias = tmp_path/"symlink"
    alias.symlink_to(config)
    with pytest.raises(ValueError):
        load_private(alias, SourceConfig)
    config.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        load_private(config, SourceConfig)
    config.chmod(0o600)
    import os
    linked = tmp_path/"hardlink"
    os.link(config, linked)
    with pytest.raises(ValueError, match="single-link"):
        load_private(config, SourceConfig)
    with pytest.raises(ValueError):
        init_config(Path(__file__).resolve().parents[1]/"private.fixture.test.json", "replay", DEFAULT_ORIGIN)
    for origin in ("https://example.invalid", "http://localhost:8765", "http://127.0.0.1:8765/path"):
        with pytest.raises(ValueError):
            init_config(tmp_path/"invalid.json", "replay", origin)


def test_operator_cli_keeps_generated_secrets_out_of_outputs(tmp_path):
    project = Path(__file__).resolve().parents[1]
    path, private = tmp_path/"config.json", tmp_path/"status.json"
    scope = tmp_path/"scope.json"
    scope.write_text(SCOPE.model_dump_json())
    command = [sys.executable, str(project/"scripts/provision_sources.py")]
    first = subprocess.run([*command,"init","--config",str(path),"--mode","replay","--origin",DEFAULT_ORIGIN],
                           capture_output=True, text=True)
    assert first.returncode == 0
    added = subprocess.run([*command,"add","--config",str(path),"--subject","status.test","--source","status",
                            "--scope",str(scope),"--credential-file",str(private)], capture_output=True, text=True)
    assert added.returncode == 0
    secret = load_private(private, SenderCredential).private_key
    listed = subprocess.run([*command,"list","--config",str(path)], capture_output=True, text=True)
    assert listed.returncode == 0 and "status.test" in listed.stdout
    assert secret not in first.stdout+first.stderr+added.stdout+added.stderr+listed.stdout+listed.stderr+path.read_text()
    assert private.stat().st_mode & 0o777 == path.stat().st_mode & 0o777 == 0o600


def test_workspace_tenant_is_pinned_and_legacy_v4_migrates_only_to_original_tenant(tmp_path):
    from uptime.auth import bind_workspace
    db = tmp_path/"tenant.db"
    bind_workspace(db, "replay", False, "north-co")
    with pytest.raises(ValueError, match="tenant"):
        bind_workspace(db, "replay", False, "south-co")
    legacy = tmp_path/"legacy-v4.db"
    with sqlite3.connect(legacy) as con:
        con.execute("CREATE TABLE authority_workspace(id INTEGER PRIMARY KEY,mode TEXT,rehearsal INTEGER)")
        con.execute("INSERT INTO authority_workspace VALUES(1,'replay',0)")
    with pytest.raises(ValueError, match="belongs to bears"):
        bind_workspace(legacy, "replay", False, "north-co")
    bind_workspace(legacy, "replay", False)
    with sqlite3.connect(legacy) as con:
        assert con.execute("SELECT tenant FROM authority_workspace").fetchone()[0] == "bears"


def test_delivery_cli_posts_original_file_to_real_loopback_and_prints_only_receipt(tmp_path):
    import httpx
    from test_v4_authority_browser import running
    path, sender_file = tmp_path/"public.json", tmp_path/"private.json"
    db = tmp_path/"cli-workbench.db"
    key = generate_reviewer_key()
    enroll(db, "delivery.operator", key)

    def factory(origin):
        init_config(path, "replay", origin)
        update_source(path, "add", "synthetic.status", source="status", scope=SCOPE, sender_path=sender_file)
        config = load_private(path, SourceConfig)
        app = create_app(db, origin=origin, approvals_enabled=True, service_credentials=config.credentials("replay", origin))
        config.bind(app.state.correspondence)
        return app

    with running(factory) as (origin, app), httpx.Client(base_url=origin, trust_env=False) as client:
        reviewer = ReviewerClient(client, origin, "delivery.operator", key)
        assert reviewer.post("/api/correspondence/claims", {"claim_id":CLAIM,"scope":SCOPE.model_dump()}).status_code == 200
        raw = tmp_path/"event.json"
        raw.write_bytes(raw_event())
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/"scripts/deliver_evidence.py"),
                                 "--credential-file", str(sender_file), "--claim", CLAIM, "--event", str(raw)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        printed = json.loads(result.stdout)
        assert set(printed) == {"event_id","digest","received_at"} and printed["event_id"] == "event.source"
        assert load_private(sender_file, SenderCredential).private_key not in result.stdout+result.stderr
        assert "oct-synthetic-outage" not in result.stdout+result.stderr


def test_trusted_custom_tenant_binds_named_reviewer_and_service_signature(tmp_path):
    # Isolate tenant binding from manual account-name/key differences: reuse the same
    # private credential and live instance when submitting a deliberately wrong realm.
    from fastapi import Depends, FastAPI
    from uptime.auth import Authority
    config, db, source, key = setup(tmp_path, tenant="north-co")
    grants = load_private(config, SourceConfig).credentials("replay", DEFAULT_ORIGIN, "north-co")
    authority = Authority(db, "replay", False, True, None, grants, DEFAULT_ORIGIN, "north-co")
    app = FastAPI()
    authority.register(app)
    @app.post("/api/probe-action")
    def action(p=Depends(authority.reviewer)):
        return {"tenant":p.tenant}
    @app.post(EVENTS)
    def ingest(p=Depends(authority.service)):
        return {"tenant":p.tenant, "key":p.source_key_id, "grant":p.source_grant_id}
    with local(app) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "source.operator", key)
        assert reviewer.post("/api/probe-action", {}).json() == {"tenant":"north-co"}
        assert client.get("/api/auth/context").json()["tenant"] == "north-co"
        raw = raw_event()
        wrong_tenant = source.model_copy(update={"tenant":"south-co"})
        assert client.post(EVENTS, content=raw, headers=signed(client, wrong_tenant, raw)).status_code == 403
        result = client.post(EVENTS, content=raw, headers=signed(client, source, raw)).json()
        assert result["tenant"] == "north-co" and result["key"].startswith("ed25519-sha256:")
        assert len(result["grant"]) == 64
