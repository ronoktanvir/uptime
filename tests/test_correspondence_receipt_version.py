"""Original contract provenance is explicit, signed, scoped and immutable across revisions."""
from datetime import UTC, datetime
import json

from fastapi.testclient import TestClient

from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient, service_headers
from uptime.auth_keys import generate_reviewer_key
from uptime.contracts import Citation, EvaluationResult, Outcome, fingerprint
from uptime.correspondence_rules import ActiveRemedy
from uptime.correspondence_types import Scope
from uptime.server import create_app
from uptime.source_config import SenderCredential, SourceConfig, init_config, load_private, update_source
from test_correspondence_resource import env, install


def original(version=None):
    body = dict(kind="original_filing_receipt", source_ref="archived-vendor-receipt", receipt_id="original-pin-71",
                observed_at="2026-07-03T12:00:00Z", received_at="2026-07-02T12:00:00Z",
                submitted_to="claims@example.invalid", fields=[])
    if version is not None:
        body["contract_version"] = version
    return body


def test_published_scope_version_is_explicit_and_cannot_be_replaced(env, tmp_path, monkeypatch):
    install(env, tmp_path, monkeypatch)
    current = env.read()
    version, source_hash = current["contract_version"], current["contract_source_sha256"]
    assert isinstance(version, str) and len(version) == 64
    assert isinstance(source_hash, str) and len(source_hash) == 64
    wrong = env.source("vendor-fixture", original("different-reviewed-version"), event_id="wrong-pin")
    assert wrong.status_code == 409
    assert env.read()["evidence"] == []
    assert env.source("vendor-fixture", original(version) | {"contract_source_sha256":"0" * 64}, event_id="wrong-source").status_code == 409
    pinned = original(version) | {"contract_source_sha256":source_hash}
    accepted = env.source("vendor-fixture", pinned, event_id="original-versioned")
    assert accepted.status_code == 200, accepted.text
    row = env.read()
    assert row["evidence"][0]["contract_version"] == version
    assert row["evidence"][0]["contract_source_sha256"] == source_hash
    assert env.source("vendor-fixture", pinned, event_id="repeat-alias").json()["digest"] == accepted.json()["digest"]
    assert env.source("vendor-fixture", original(), event_id="strip-pin").status_code == 409
    assert env.source("vendor-fixture", original("new-version"), event_id="replace-pin").status_code == 409
    assert env.source("vendor-fixture", original(version), event_id="strip-source-pin").status_code == 409
    assert len(env.read()["evidence"]) == 1


def test_signed_public_source_proof_covers_original_pin_and_new_terms_cannot_repin_it(tmp_path, monkeypatch):
    # D04-C (2026-11-09): the injected resolver stands in for installed resource-month terms, so their family is
    # declared the same way; that family needs the resource and region, and the incident does not apply.
    from uptime import claim_scope
    monkeypatch.setattr(claim_scope, "_installed", lambda db, t, s: [{"manifest": {"family": "resource-month/1"}, "overlay": {}}])
    scope = Scope(account="version-fixture-account", vendor="Version Fixture Provider", contract="fixture-agreement",
                  service="Fixture Service", component="cell-1", invoice="fixture-invoice",
                  currency="USD", month="2026-06", region="west")
    config_path, sender_path, db_path = tmp_path / "source.json", tmp_path / "vendor.json", tmp_path / "workspace.db"
    init_config(config_path, "replay", DEFAULT_ORIGIN, "bears")
    update_source(config_path, "add", "version-fixture-vendor", source="vendor", scope=scope, sender_path=sender_path)
    config = load_private(config_path, SourceConfig)
    sender = load_private(sender_path, SenderCredential)
    reviewer_key = generate_reviewer_key()
    enroll(db_path, "version-fixture-reviewer", reviewer_key)
    app = create_app(db_path, origin=DEFAULT_ORIGIN, approvals_enabled=True,
                     service_credentials=config.credentials("replay", DEFAULT_ORIGIN))
    desk = app.state.correspondence
    config.bind(desk)
    desk.clock = lambda: datetime(2026, 7, 4, tzinfo=UTC)
    reviewed = ["version-one"]

    def resolver(tenant, requested, events, at):
        return ActiveRemedy(tenant, requested, fingerprint([[e["source"], e["digest"]] for e in events]),
            reviewed[0], datetime(2026, 7, 10, tzinfo=UTC),
            EvaluationResult(Outcome.MISSING, (Citation("Synthetic fixture terms", reviewed[0], "scope", "urn:fixture:terms"),),
                             ("Synthetic version-binding fixture",), ("Financial evidence absent",)),
            agreement_id=scope.contract, remedy="resource-month/" + scope.component, contract_source_sha256="a" * 64)

    desk.active_resolver = resolver
    claim_id = "inbox-version-source"
    prefix = "/api/correspondence/claims/" + claim_id
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 5900)) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "version-fixture-reviewer", reviewer_key)
        created = reviewer.post("/api/correspondence/claims", dict(claim_id=claim_id, scope=scope.model_dump()))
        assert created.status_code == 200 and created.json()["contract_version"] == reviewed[0]
        pinned = original(reviewed[0]) | {"contract_source_sha256":"a" * 64}
        payload = dict(event_id="source-original", scope=scope.model_dump(), body=pinned)
        raw = json.dumps(payload).encode()
        path = prefix + "/events"
        def headers(content):
            return service_headers(instance=app.state.auth.instance, origin=DEFAULT_ORIGIN,
                                   subject=sender.subject, key=sender, path=path, body=content)
        signed = headers(raw)
        changed = json.dumps(payload | {"body":original("version-two")}).encode()
        assert client.post(path, content=changed, headers=signed).status_code == 403
        changed = json.dumps(payload | {"body":pinned | {"contract_source_sha256":"b" * 64}}).encode()
        assert client.post(path, content=changed, headers=headers(raw)).status_code == 403
        assert client.post(path, content=raw, headers=headers(raw)).status_code == 200
        reviewed[0] = "version-two"
        changed = json.dumps(payload | {"event_id":"repinned-original", "body":original(reviewed[0])}).encode()
        assert client.post(path, content=changed, headers=headers(changed)).status_code == 409
        current = client.get(prefix, headers=reviewer.headers).json()
        assert current["contract_version"] == "version-two"
        assert current["evidence"][0]["contract_version"] == "version-one"
        assert len(current["evidence"]) == 1
