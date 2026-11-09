"""W5 acceptance: wrong-customer, wrong-period, stale and tampered evidence never reaches storage.

Every delivery crosses the mounted HTTP intake with real Ed25519 grants, as an enrolled source
would send it. Refusals are HTTP 403 (outside the source's grant or proof) or 409 (inconsistent
content); none of them may add an inbox row. Records are authored synthetic data.
"""
from datetime import timedelta
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from tests.test_source_config_v4 import SCOPE, app_for
from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient, service_headers
from uptime.auth_keys import generate_reviewer_key
from uptime.contracts import fingerprint
from uptime.evidence import load_snapshot
from uptime.evidence_status_source import StatusSourceRefusal, status_delivery
from uptime.source_config import SenderCredential, init_config, load_private, update_source

CLAIM = "inbox-acceptance-91"
EVENTS = f"/api/correspondence/claims/{CLAIM}/events"
OCTOBER = dict(start="2026-10-08T01:00:00Z", end="2026-10-08T02:00:00Z")
SEPTEMBER = dict(start="2026-09-08T01:00:00Z", end="2026-09-08T02:00:00Z")
MONTH = dict(start="2026-10-01T00:00:00Z", end="2026-11-01T00:00:00Z")


@pytest.fixture
def intake(tmp_path):
    config, db = tmp_path / "grants.json", tmp_path / "workspace.db"
    init_config(config, "replay", DEFAULT_ORIGIN, "bears")
    senders = {}
    for role in ("status", "customer"):
        update_source(config, "add", role + ".acceptance", source=role, scope=SCOPE, sender_path=tmp_path / (role + ".json"))
        senders[role] = load_private(tmp_path / (role + ".json"), SenderCredential)
    human = generate_reviewer_key()
    enroll(db, "acceptance.operator", human, tenant="bears")
    with TestClient(app_for(config, db), base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 50000)) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "acceptance.operator", human)
        assert reviewer.post("/api/correspondence/claims", {"claim_id": CLAIM, "scope": SCOPE.model_dump()}).status_code == 200

        def post(role, body, event_id, *, scope=SCOPE, tamper=None):
            raw = json.dumps({"event_id": event_id, "scope": scope.model_dump(), "body": body}).encode()
            instance = client.get("/api/auth/context").json()["instance"]
            headers = service_headers(instance=instance, origin=DEFAULT_ORIGIN, path=EVENTS, body=raw,
                                      subject=senders[role].subject, key=senders[role])
            return client.post(EVENTS, content=tamper(raw) if tamper else raw, headers=headers)

        def stored():
            with sqlite3.connect(db) as connection:
                return [r[0] for r in connection.execute("SELECT event_id FROM inbox_delivery ORDER BY rowid")]

        yield post, stored


def telemetry(**changes):
    row = dict(ref="row-1", account=SCOPE.account, product=SCOPE.service, region=SCOPE.region,
               resource_id=SCOPE.component, status="unavailable", **OCTOBER)
    body = dict(kind="provider_telemetry", source_ref="monitor-export", observed_at="2026-11-01T06:00:00Z",
                source_id="monitor-1", complete=True, records=[row], **MONTH)
    return {**body, **changes}


def test_wrong_customer_evidence_is_refused(intake):
    post, stored = intake
    other = SCOPE.model_copy(update=dict(account="other-account"))
    assert post("status", dict(kind="status", **OCTOBER), "status.other", scope=other).status_code == 403
    foreign_row = telemetry()
    foreign_row["records"][0]["account"] = "other-account"
    assert post("status", foreign_row, "telemetry.foreign").status_code == 403
    other_resource = telemetry()
    other_resource["records"][0]["resource_id"] = "api-west"
    assert post("status", other_resource, "telemetry.other-resource").status_code == 403
    assert stored() == []


def test_wrong_period_evidence_is_refused_and_cannot_block_the_correct_record(intake):
    post, stored = intake
    assert post("status", dict(kind="status", **SEPTEMBER), "status.september").status_code == 403
    adjacent = telemetry(start="2026-09-01T00:00:00Z", end="2026-10-01T00:00:00Z", observed_at="2026-10-01T06:00:00Z",
                         records=[])
    assert post("status", adjacent, "telemetry.september").status_code == 403
    stray_row = telemetry()
    stray_row["records"][0].update(SEPTEMBER)
    assert post("status", stray_row, "telemetry.stray-row").status_code == 403
    assert stored() == []
    assert post("status", dict(kind="status", **OCTOBER), "status.october").status_code == 200
    assert stored() == ["status.october"]


def test_stale_or_premature_evidence_is_refused():
    snapshot = load_snapshot()
    from datetime import datetime
    observed = datetime.fromisoformat(snapshot.observed_at)
    scope = SCOPE.model_copy(update=dict(incident="3cdw1jrt88l2", component="8qjql0kqnd33", month="2026-11"))
    with pytest.raises(StatusSourceRefusal, match="older than 24 hours"):
        status_delivery(snapshot, "3cdw1jrt88l2", scope, now=observed + timedelta(days=2))
    assert status_delivery(snapshot, "3cdw1jrt88l2", scope, now=observed + timedelta(hours=1))[0].body.kind == "status"


def test_a_complete_report_observed_before_its_period_ended_is_refused(intake):
    post, stored = intake
    assert post("status", telemetry(observed_at="2026-10-31T23:55:00Z"), "telemetry.early").status_code == 403
    assert post("status", telemetry(), "telemetry.complete").status_code == 200
    assert stored() == ["telemetry.complete"]


def test_tampered_evidence_is_refused(intake):
    post, stored = intake
    # Bytes changed after signing: the proof covers the exact body.
    assert post("status", dict(kind="status", **OCTOBER), "status.a", tamper=lambda raw: raw + b" ").status_code == 403
    assert post("status", dict(kind="status", **OCTOBER), "status.b",
                tamper=lambda raw: raw.replace(b"02:00:00Z", b"03:00:00Z")).status_code == 403
    # Declared content digests are recomputed by intake.
    content = dict(source="simulated_vendor", unavailable_minutes=12)
    monitor = dict(kind="service_monitor", source_ref="monitor-export", observed_at="2026-11-01T06:00:00Z",
                   plan="Business", complete=True, recorded_at="2026-11-01T05:00:00Z",
                   content_sha256=fingerprint({**content, "unavailable_minutes": 13}), content=content)
    refused = post("status", monitor, "monitor.mismatch")
    assert refused.status_code == 409 and "must match its attestation" in refused.json()["detail"]
    artifact = dict(kind="artifact", source_ref="archive", observed_at="2026-11-01T06:00:00Z", artifact_ref="log-1",
                    artifact_type="resource_log", body_sha256="0" * 64, content="2026-10-08 01:00 unavailable")
    refused = post("customer", artifact, "artifact.mismatch")
    assert refused.status_code == 409 and "do not match their declared content digest" in refused.json()["detail"]
    assert stored() == []
    # Positive control: the same record with its true digest is admitted.
    honest = post("status", {**monitor, "content_sha256": fingerprint(content)}, "monitor.honest")
    assert honest.status_code == 200, honest.text
    assert stored() == ["monitor.honest"]


def test_tampered_public_snapshot_is_refused(tmp_path):
    snapshot = json.loads((load_snapshot.__defaults__[0]).read_text())
    snapshot["observations"][0]["resolved_at"] = "2026-11-03T00:00:00.000-08:00"
    path = tmp_path / "edited.json"
    path.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError, match="integrity mismatch"):
        load_snapshot(path)


def test_reused_event_identity_with_different_content_is_refused(intake):
    post, stored = intake
    first = post("status", dict(kind="status", **OCTOBER), "status.october")
    assert first.status_code == 200
    changed = dict(kind="status", start="2026-10-08T01:00:00Z", end="2026-10-08T03:00:00Z")
    assert post("status", changed, "status.october").status_code == 409
    again = post("status", dict(kind="status", **OCTOBER), "status.october")
    assert again.status_code == 200 and again.json() == first.json()
    assert stored() == ["status.october"]
