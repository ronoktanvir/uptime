"""Out-of-scope refusals from verified signed sources, audited through the ordinary signed routes.

Every key is generated per test. Only a current, unspent, validly signed Ed25519 delivery whose
grant does not cover it reaches the refusal journal. It still answers 403, stores metadata only,
and never spends the nonce or changes intake, claim or authority state.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import secrets
import sqlite3
from threading import Barrier
from time import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from uptime import auth as auth_module
from uptime import mandates
from uptime.auth import DEFAULT_ORIGIN, Authority, enroll, service_message
from uptime.auth_client import ReviewerClient, service_headers
from uptime.auth_keys import generate_reviewer_key
from uptime.contracts import fingerprint
from uptime.correspondence_refusals import COLUMNS, REASON
from uptime.correspondence_types import Scope
from uptime.server import create_app
from uptime.source_config import (SenderCredential, SourceConfig, SourceRegistry, init_config, load_private,
                                  update_source)

CLAIM = "inbox-refusal-audit-1"
EVENTS = f"/api/correspondence/claims/{CLAIM}/events"
SCOPE = Scope(account="test-account", vendor="Twilio", contract="signed-agreement", service="Twilio Messaging API",
              component="api-east", invoice="oct-bill", incident="oct-synthetic-outage", currency="USD",
              month="2026-10")
OTHER_COMPONENT = SCOPE.model_copy(update={"component": "api-west"})
DENIED = 403


def raw_event(scope=SCOPE, kind="status", event_id="event.source"):
    body = {"kind": kind, "start": "2026-10-08T01:00:00Z", "end": "2026-10-08T02:00:00Z"}
    if kind == "impact":
        body.update(affected=True, exclusion="none")
    return json.dumps({"event_id": event_id, "scope": scope.model_dump(), "body": body}, indent=1).encode()


def setup(directory, tenant="bears"):
    directory.mkdir(parents=True, exist_ok=True)
    config, sender_file = directory/"public-grants.json", directory/"private-status.json"
    init_config(config, "replay", DEFAULT_ORIGIN, tenant)
    update_source(config, "add", "status.synthetic", source="status", scope=SCOPE, sender_path=sender_file)
    db = directory/"workspace.db"
    human = generate_reviewer_key()
    enroll(db, "source.operator", human, tenant=tenant)
    return config, db, load_private(sender_file, SenderCredential), human


def app_for(config, db, *, enabled=True, tenant="bears"):
    loaded = load_private(config, SourceConfig)
    app = create_app(db, origin=DEFAULT_ORIGIN, approvals_enabled=enabled, tenant=tenant,
                     service_credentials=loaded.credentials("replay", DEFAULT_ORIGIN, tenant))
    loaded.bind(app.state.correspondence)
    return app


def local(app):
    return TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 50000))


def signed(app, sender, raw, *, path=EVENTS, nonce=None, stamp=None):
    instance = app.state.auth.instance
    headers = service_headers(instance=instance, origin=DEFAULT_ORIGIN, path=path, body=raw,
                              subject=sender.subject, key=sender)
    if nonce is None and stamp is None:
        return headers
    nonce, stamp = nonce or headers["X-Uptime-Nonce"], stamp or headers["X-Uptime-Time"]
    proof = sender.sign(service_message(instance, DEFAULT_ORIGIN, sender.subject, path, raw, stamp, nonce,
                                        sender.tenant, sender.mode))
    return {**headers, "X-Uptime-Nonce": nonce, "X-Uptime-Time": stamp, "X-Uptime-Proof": proof}


def query(db, sql, args=()):
    with closing(sqlite3.connect(db)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(sql, args)]


def has_table(db, name):
    return bool(query(db, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)))


def audit_rows(db):
    if not has_table(db, "source_refusal_audit"):
        return []
    return query(db, "SELECT * FROM source_refusal_audit ORDER BY received_at, refusal_digest")


def accepted_deliveries(db):
    if not has_table(db, "inbox_delivery"):
        return 0
    return query(db, "SELECT count(*) AS n FROM inbox_delivery")[0]["n"]


def key_history(db, public_key):
    return [row["subject"] for row in query(db, "SELECT subject FROM source_key_history WHERE public_key=?",
                                            (public_key,))]


def grant_of(config):
    return load_private(config, SourceConfig).services[0]


def expected_identity(grant, tenant="bears"):
    return ("ed25519-sha256:" + sha256(bytes.fromhex(grant.public_key)).hexdigest(),
            fingerprint([tenant, "replay", grant.model_dump()]))


def open_claim(client, human):
    reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "source.operator", human)
    created = reviewer.post("/api/correspondence/claims", {"claim_id": CLAIM, "scope": SCOPE.model_dump()})
    assert created.status_code == 200, created.text


def tampered(proof):
    return proof[:-1] + ("0" if proof[-1] != "0" else "1")


class FrozenClock:
    """Stands in for ``datetime`` inside uptime.auth so the stored first receipt time is exact."""
    def __init__(self, *moments):
        self.moments, self.calls = list(moments), 0

    def now(self, tz=None):
        assert tz is not None, "the refusal timestamp must be offset-aware"
        moment = self.moments[min(self.calls, len(self.moments) - 1)]
        self.calls += 1
        return moment


def test_verified_out_of_scope_delivery_records_exact_metadata_and_stays_403(tmp_path):
    config, db, sender, _ = setup(tmp_path)
    app = app_for(config, db)
    key_id, grant_id = expected_identity(grant_of(config))
    wrong_component, wrong_kind = raw_event(OTHER_COMPONENT), raw_event(kind="impact")
    with local(app) as client:
        authority = app.state.auth
        revision = authority.revision
        before = datetime.now(UTC)
        refused = client.post(EVENTS, content=wrong_component, headers=signed(app, sender, wrong_component))
        assert refused.status_code == DENIED
        assert client.post(EVENTS, content=wrong_kind, headers=signed(app, sender, wrong_kind)).status_code == DENIED
        after = datetime.now(UTC)
        # A denial spends no nonce, bumps no authority revision and creates no intake.
        assert authority.deliveries == {} and authority.revision == revision
    assert accepted_deliveries(db) == 0
    rows = audit_rows(db)
    assert len(rows) == 2
    assert {row["body_sha256"] for row in rows} == {sha256(wrong_component).hexdigest(), sha256(wrong_kind).hexdigest()}
    for row in rows:
        assert set(row) == set(COLUMNS)
        assert (row["tenant"], row["subject"], row["source_key_id"], row["source_grant_id"], row["request_path"],
                row["reason"]) == ("bears", sender.subject, key_id, grant_id, EVENTS, REASON)
        stamp = datetime.fromisoformat(row["received_at"])
        assert stamp.utcoffset() is not None and before <= stamp <= after


def test_identical_redelivery_keeps_one_row_and_first_timestamp(tmp_path, monkeypatch):
    config, db, sender, _ = setup(tmp_path)
    app = app_for(config, db)
    first = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
    clock = FrozenClock(first, first + timedelta(seconds=5))
    monkeypatch.setattr(auth_module, "datetime", clock)
    raw = raw_event(OTHER_COMPONENT)
    with local(app) as client:
        headers = signed(app, sender, raw)
        assert client.post(EVENTS, content=raw, headers=headers).status_code == DENIED
        assert client.post(EVENTS, content=raw, headers=headers).status_code == DENIED
    assert clock.calls == 2  # Both copies reached the journal; the second deduplicated.
    rows = audit_rows(db)
    assert len(rows) == 1 and rows[0]["received_at"] == first.isoformat()


def test_fresh_nonce_for_same_body_deduplicates_and_refused_nonce_stays_unspent(tmp_path, monkeypatch):
    config, db, sender, human = setup(tmp_path)
    app = app_for(config, db)
    first = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
    clock = FrozenClock(first, first + timedelta(seconds=7), first + timedelta(seconds=9))
    monkeypatch.setattr(auth_module, "datetime", clock)
    raw, other = raw_event(OTHER_COMPONENT), raw_event(kind="impact")
    with local(app) as client:
        refused = signed(app, sender, raw)
        assert client.post(EVENTS, content=raw, headers=refused).status_code == DENIED
        assert client.post(EVENTS, content=raw, headers=signed(app, sender, raw)).status_code == DENIED
        assert len(audit_rows(db)) == 1 and audit_rows(db)[0]["received_at"] == first.isoformat()
        assert client.post(EVENTS, content=other, headers=signed(app, sender, other)).status_code == DENIED
        assert len(audit_rows(db)) == 2
        assert clock.calls == 3
        # As before, an out-of-scope refusal does not consume the nonce: an in-scope delivery can use it.
        open_claim(client, human)
        good = raw_event()
        accepted = client.post(EVENTS, content=good, headers=signed(app, sender, good, nonce=refused["X-Uptime-Nonce"]))
        assert accepted.status_code == 200, accepted.text
        # Once an accepted request has spent it, a refusal replay on that nonce is not audited.
        assert client.post(EVENTS, content=raw, headers=refused).status_code == DENIED
        assert clock.calls == 3
    assert accepted_deliveries(db) == 1
    assert len(audit_rows(db)) == 2


def test_unverified_unknown_expired_closed_or_misrouted_deliveries_record_nothing(tmp_path):
    config, db, sender, _ = setup(tmp_path)
    app = app_for(config, db)
    raw = raw_event(OTHER_COMPONENT)
    forger = Ed25519PrivateKey.generate()
    with local(app) as client:
        valid = signed(app, sender, raw)
        message = service_message(app.state.auth.instance, DEFAULT_ORIGIN, sender.subject, EVENTS, raw,
                                  valid["X-Uptime-Time"], valid["X-Uptime-Nonce"], sender.tenant, sender.mode)
        attempts = [
            (raw, {**valid, "X-Uptime-Proof": tampered(valid["X-Uptime-Proof"])}),
            (raw, {**valid, "X-Uptime-Proof": forger.sign(message.encode()).hex()}),
            (raw, {k: v for k, v in valid.items() if k != "X-Uptime-Proof"}),
            (raw + b" ", valid),
            (raw, {**valid, "X-Uptime-Service": "unknown.source"}),
            (raw, signed(app, sender, raw, stamp=str(int(time()) - 121))),
            (raw, signed(app, sender, raw, stamp=str(int(time()) + 121))),
            (raw, {**valid, "Origin": "http://127.0.0.1:8766"}),
        ]
        for body, headers in attempts:
            assert client.post(EVENTS, content=body, headers=headers).status_code == DENIED
        # A valid signature on a route that is not an exact claim events route is denied, not audited.
        misrouted = "/api/correspondence/claims/not-an-inbox-claim/events"
        assert client.post(misrouted, content=raw, headers=signed(app, sender, raw, path=misrouted)).status_code == DENIED
        assert app.state.auth.deliveries == {}
    closed_app = app_for(config, db, enabled=False)
    with local(closed_app) as closed:
        assert closed.post(EVENTS, content=raw, headers=signed(closed_app, sender, raw)).status_code == DENIED
    assert audit_rows(db) == []
    assert accepted_deliveries(db) == 0


def test_nonce_spent_by_accepted_delivery_is_never_audited(tmp_path):
    config, db, sender, human = setup(tmp_path)
    app = app_for(config, db)
    good, wrong = raw_event(), raw_event(OTHER_COMPONENT)
    with local(app) as client:
        open_claim(client, human)
        accepted = signed(app, sender, good)
        assert client.post(EVENTS, content=good, headers=accepted).status_code == 200
        nonce = accepted["X-Uptime-Nonce"]
        # Freshly and validly signed by the real sender, but reusing a spent nonce.
        assert client.post(EVENTS, content=wrong, headers=signed(app, sender, wrong, nonce=nonce)).status_code == DENIED
        again = raw_event(event_id="event.again")
        assert client.post(EVENTS, content=again, headers=signed(app, sender, again, nonce=nonce)).status_code == DENIED
    assert audit_rows(db) == []
    assert accepted_deliveries(db) == 1


def test_tenants_record_separate_refusals(tmp_path):
    raw = raw_event(OTHER_COMPONENT)
    results = {}
    for tenant in ("bears", "north-co"):
        config, db, sender, _ = setup(tmp_path/tenant, tenant)
        app = app_for(config, db, tenant=tenant)
        with local(app) as client:
            assert client.post(EVENTS, content=raw, headers=signed(app, sender, raw)).status_code == DENIED
        rows = audit_rows(db)
        assert len(rows) == 1 and rows[0]["tenant"] == tenant
        assert (rows[0]["source_key_id"], rows[0]["source_grant_id"]) == expected_identity(grant_of(config), tenant)
        results[tenant] = rows[0]
    bears, north = results["bears"], results["north-co"]
    assert bears["body_sha256"] == north["body_sha256"] == sha256(raw).hexdigest()
    assert bears["refusal_digest"] != north["refusal_digest"]
    assert bears["source_grant_id"] != north["source_grant_id"]


def test_refusal_attribution_matches_the_accepted_principal(tmp_path):
    config, db, sender, _ = setup(tmp_path, tenant="north-co")
    grants = load_private(config, SourceConfig).credentials("replay", DEFAULT_ORIGIN, "north-co")
    authority = Authority(db, "replay", False, True, None, grants, DEFAULT_ORIGIN, "north-co")
    app = FastAPI()
    app.state.auth = authority
    authority.register(app)

    @app.post(EVENTS)
    def ingest(p=Depends(authority.service)):
        return {"tenant": p.tenant, "subject": p.subject, "key": p.source_key_id, "grant": p.source_grant_id}

    good, wrong = raw_event(), raw_event(OTHER_COMPONENT)
    with local(app) as client:
        accepted = client.post(EVENTS, content=good, headers=signed(app, sender, good))
        assert accepted.status_code == 200, accepted.text
        principal = accepted.json()
        assert client.post(EVENTS, content=wrong, headers=signed(app, sender, wrong)).status_code == DENIED
    [row] = audit_rows(db)
    assert (row["tenant"], row["subject"], row["source_key_id"], row["source_grant_id"]) == (
        principal["tenant"], principal["subject"], principal["key"], principal["grant"])


def test_journal_failure_fails_closed_with_generic_503(tmp_path, monkeypatch):
    config, db, sender, human = setup(tmp_path)
    # An incompatible pre-existing table makes the real journal insert fail.
    with closing(sqlite3.connect(db)) as connection, connection:
        connection.execute("CREATE TABLE source_refusal_audit(refusal_digest TEXT)")
    app = app_for(config, db)
    raw = raw_event(OTHER_COMPONENT)
    with local(app) as client:
        headers = signed(app, sender, raw)
        revision = app.state.auth.revision
        for _ in range(2):
            failed = client.post(EVENTS, content=raw, headers=headers)
            assert failed.status_code == 503
            for secret in (headers["X-Uptime-Nonce"], headers["X-Uptime-Proof"], sender.subject,
                           sha256(raw).hexdigest(), "api-west", "sqlite", "no column"):
                assert secret not in failed.text
        assert app.state.auth.deliveries == {} and app.state.auth.revision == revision

        def broken(*args, **kwargs):
            raise ValueError("journal validation detail")
        monkeypatch.setattr(auth_module, "record_verified_source_refusal", broken)
        failed = client.post(EVENTS, content=raw, headers=signed(app, sender, raw))
        assert failed.status_code == 503 and "journal validation detail" not in failed.text
        # Only refusals use the journal; an in-scope delivery is unaffected and nothing fell through.
        open_claim(client, human)
        good = raw_event()
        assert client.post(EVENTS, content=good, headers=signed(app, sender, good)).status_code == 200
    assert accepted_deliveries(db) == 1
    assert query(db, "SELECT count(*) AS n FROM source_refusal_audit")[0]["n"] == 0


def test_journal_holds_no_body_proof_or_nonce(tmp_path):
    config, db, sender, _ = setup(tmp_path)
    app = app_for(config, db)
    marker = "event.private-marker-" + secrets.token_hex(8)
    raw = raw_event(OTHER_COMPONENT, event_id=marker)
    with local(app) as client:
        headers = signed(app, sender, raw)
        assert client.post(EVENTS, content=raw, headers=headers).status_code == DENIED
    columns = [row["name"] for row in query(db, "PRAGMA table_info(source_refusal_audit)")]
    assert tuple(columns) == COLUMNS
    with closing(sqlite3.connect(db)) as connection:
        dump = "\n".join(connection.iterdump())
    for sensitive in (headers["X-Uptime-Nonce"], headers["X-Uptime-Proof"], marker, raw.decode(), "api-west"):
        assert sensitive not in dump
    [row] = audit_rows(db)
    assert row["body_sha256"] == sha256(raw).hexdigest()


def test_concurrent_copies_audit_once_and_never_authenticate(tmp_path):
    config, db, sender, _ = setup(tmp_path)
    app = app_for(config, db)
    raw = raw_event(OTHER_COMPONENT)
    with local(app) as client:
        same = signed(app, sender, raw)
        fresh = [signed(app, sender, raw) for _ in range(8)]
        requests = [same] * 8 + fresh
        ready = Barrier(len(requests))

        def submit(headers):
            ready.wait(timeout=10)
            return client.post(EVENTS, content=raw, headers=headers).status_code
        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            statuses = list(pool.map(submit, requests))
        assert statuses == [DENIED] * len(requests)
        assert app.state.auth.deliveries == {}
    assert len(audit_rows(db)) == 1
    assert accepted_deliveries(db) == 0


def test_rotated_key_bound_to_another_identity_is_refused_before_attribution(tmp_path):
    config, db, old, _ = setup(tmp_path)
    registry = SourceRegistry(config, "replay", DEFAULT_ORIGIN, "bears")
    app = create_app(db, approvals_enabled=True, service_credentials=registry)
    registry.config.bind(app.state.correspondence)
    update_source(config, "rotate", old.subject, sender_path=tmp_path/"rotated.json")
    fresh = load_private(tmp_path/"rotated.json", SenderCredential)
    fresh_public = grant_of(config).public_key
    wrong, good = raw_event(OTHER_COMPONENT), raw_event()
    with local(app) as client:
        # An unverified proof from the rotated subject neither binds the key nor audits.
        forged = signed(app, fresh, wrong)
        forged["X-Uptime-Proof"] = tampered(forged["X-Uptime-Proof"])
        assert client.post(EVENTS, content=wrong, headers=forged).status_code == DENIED
        assert key_history(db, fresh_public) == []
        mandates.remember_source_keys(db, [("other.source", fresh_public)])
        for body in (wrong, good):
            refused = client.post(EVENTS, content=body, headers=signed(app, fresh, body))
            assert refused.status_code == DENIED
            assert refused.json()["detail"] == "Source key belongs to a separate authority"
    assert key_history(db, fresh_public) == ["other.source"]
    assert audit_rows(db) == []
    assert accepted_deliveries(db) == 0


def test_rotated_key_is_bound_to_its_subject_before_an_out_of_scope_refusal(tmp_path):
    config, db, old, _ = setup(tmp_path)
    registry = SourceRegistry(config, "replay", DEFAULT_ORIGIN, "bears")
    app = create_app(db, approvals_enabled=True, service_credentials=registry)
    registry.config.bind(app.state.correspondence)
    update_source(config, "rotate", old.subject, sender_path=tmp_path/"rotated.json")
    fresh = load_private(tmp_path/"rotated.json", SenderCredential)
    grant = grant_of(config)
    wrong = raw_event(OTHER_COMPONENT)
    with local(app) as client:
        assert client.post(EVENTS, content=wrong, headers=signed(app, fresh, wrong)).status_code == DENIED
        # The retired key is no longer this subject's current grant and is not attributed.
        assert client.post(EVENTS, content=wrong, headers=signed(app, old, wrong)).status_code == DENIED
    assert key_history(db, grant.public_key) == [fresh.subject]
    [row] = audit_rows(db)
    assert (row["source_key_id"], row["source_grant_id"]) == expected_identity(grant)
    # The rotated key now belongs to its subject; it cannot later be claimed by another identity.
    with pytest.raises(PermissionError):
        mandates.remember_source_keys(db, [("other.source", grant.public_key)])


def test_legacy_fixture_hmac_channel_is_unchanged_and_never_audited(tmp_path):
    db, path = tmp_path/"fixture.db", "/api/v4/test-inbound"
    keys = {"fixture.vendor.one": secrets.token_urlsafe(32)}
    app = create_app(db, service_credentials=keys, approvals_enabled=True)

    @app.post(path)
    async def inbound(p=Depends(app.state.auth.service)):
        return {"subject": p.subject, "key": p.source_key_id}

    payload = b'{"receipt":"synthetic"}'
    with local(app) as client:
        headers = service_headers(instance=app.state.auth.instance, origin=DEFAULT_ORIGIN, subject="fixture.vendor.one",
                                  key=keys["fixture.vendor.one"], path=path, body=payload)
        bad = {**headers, "X-Uptime-Proof": tampered(headers["X-Uptime-Proof"])}
        assert client.post(path, content=payload, headers=bad).status_code == DENIED
        accepted = client.post(path, content=payload, headers=headers)
        assert accepted.status_code == 200 and accepted.json()["key"].startswith("fixture-hmac:")
        assert client.post(path, content=payload, headers=headers).status_code == DENIED
    assert not has_table(db, "source_refusal_audit")
