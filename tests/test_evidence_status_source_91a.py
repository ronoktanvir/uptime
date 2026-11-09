"""Decision 91a: Twilio's public status page as the first real evidence source (D07).

The snapshot is the official public capture recorded in fixtures/evidence (collected
2026-11-04). Claim scopes below are authored local identifiers; no customer data is used.
"""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
import sqlite3

import pytest

from scripts.deliver_evidence import deliver
from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key
from uptime.correspondence_types import Scope
from uptime.evidence import load_snapshot
from uptime.evidence_status_source import FRESHNESS, StatusSourceRefusal, status_delivery
from uptime.source_config import SenderCredential, init_config, load_private, update_source

SNAPSHOT = load_snapshot()
OBSERVED = datetime.fromisoformat(SNAPSHOT.observed_at)
NOW = OBSERVED + timedelta(hours=1)
# Resolved public incident "SMS Delivery Failures from Twilio to KDDI Japan", 1 November 2026.
INCIDENT, COMPONENT = "3cdw1jrt88l2", "8qjql0kqnd33"
SCOPE = Scope(account="local-status-check", vendor="Twilio", contract="local-agreement", service="Twilio Messaging API",
              component=COMPONENT, invoice="local-invoice", incident=INCIDENT, currency="USD",
              month="2026-11")  # D04-C (2026-11-09): no Twilio region (W5 test input)


def test_a_resolved_public_incident_becomes_one_exact_status_record_with_provenance():
    delivery, provenance = status_delivery(SNAPSHOT, INCIDENT, SCOPE, now=NOW)
    row = next(o for o in SNAPSHOT.observations if o.incident_id == INCIDENT)
    assert delivery.scope == SCOPE and delivery.body.kind == "status"
    # Published times are converted to UTC without rounding or substitution.
    assert delivery.body.start == "2026-11-01T20:30:04.453000+00:00"
    assert delivery.body.end == "2026-11-02T00:37:57.392000+00:00"
    assert delivery.event_id == f"twilio-status:{INCIDENT}:{row.content_hash[:16]}"
    assert provenance == dict(
        source_uri="https://status.twilio.com/api/v2/incidents.json", observed_at=SNAPSHOT.observed_at,
        raw_sha256=SNAPSHOT.raw_sha256, incident_id=INCIDENT, content_hash=row.content_hash,
        published_status="resolved", published_components=[COMPONENT], event_id=delivery.event_id,
        customer_impact="unverified", month_coverage="not attested; a recent-incident feed is not complete month coverage",
        standalone_entitlement=False)
    # The public label is untrusted display text and never enters the signed record.
    assert row.label not in delivery.model_dump_json()


def test_same_public_record_yields_the_same_event_identity():
    first, _ = status_delivery(SNAPSHOT, INCIDENT, SCOPE, now=NOW)
    again, _ = status_delivery(SNAPSHOT, INCIDENT, SCOPE, now=NOW + timedelta(hours=2))
    assert first == again


def feed(row, *, reverse=False, collected_at):
    """Raw public bytes for one recorded incident, with unused fields the minimizer drops."""
    from hashlib import sha256
    from uptime.evidence import minimize
    fields = dict(id=row.incident_id, name=row.label, status=row.status, created_at=row.created_at,
                  started_at=row.started_at, resolved_at=row.resolved_at, updated_at=row.updated_at,
                  components=[dict(id=c, name="Component " + c) for c in row.components], shortlink="https://stspg.io/x")
    if reverse:
        fields = dict(reversed(list(fields.items())))
        fields["components"] = list(reversed(fields["components"])) + [dict(id="zzzz0000zzzz", name="Other")]
    raw = json.dumps({"page": {"id": "page"}, "incidents": [fields]}, indent=None if reverse else 2).encode()
    return minimize(raw, dict(url="https://status.twilio.com/api/v2/incidents.json", collected_at=collected_at,
                              sha256=sha256(raw).hexdigest()))


def test_two_fetches_with_reordered_serialization_keep_one_event_identity():
    # Decision 91a critique falsification: idempotency must hold across separate fetches, not one hash.
    row = next(o for o in SNAPSHOT.observations if o.incident_id == INCIDENT)
    first = feed(row, collected_at=SNAPSHOT.observed_at)
    later = (OBSERVED + timedelta(hours=3)).isoformat()
    second = feed(row, collected_at=later)
    assert first.raw_sha256 != feed(row, reverse=True, collected_at=later).raw_sha256
    one, _ = status_delivery(first, INCIDENT, SCOPE, now=NOW)
    two, _ = status_delivery(second, INCIDENT, SCOPE, now=NOW + timedelta(hours=3))
    assert one.event_id == two.event_id == f"twilio-status:{INCIDENT}:{row.content_hash[:16]}"
    # Reordered keys and components change the raw bytes but not the canonical incident record,
    # except for the additional published component, which is a real public edit.
    reordered = feed(row, reverse=True, collected_at=later)
    edited, _ = status_delivery(reordered, INCIDENT, SCOPE, now=NOW + timedelta(hours=3))
    assert edited.body == one.body and edited.event_id != one.event_id


@pytest.mark.parametrize("now,match", [
    (OBSERVED + FRESHNESS + timedelta(seconds=1), "older than 24 hours"),
    (OBSERVED - timedelta(seconds=1), "after the delivery clock"),
])
def test_stale_or_future_snapshots_are_refused(now, match):
    assert FRESHNESS == timedelta(hours=24)
    with pytest.raises(StatusSourceRefusal, match=match):
        status_delivery(SNAPSHOT, INCIDENT, SCOPE, now=now)


@pytest.mark.parametrize("update,match", [
    (dict(vendor="Atlassian"), "only Twilio"),
    (dict(incident="2ylvwxdqqjz2"), "grant names incident"),
    (dict(component="api-east"), "does not name the granted component"),
    (dict(month="2026-10"), "outside service month 2026-10"),
])
def test_wrong_vendor_incident_component_or_month_is_refused(update, match):
    with pytest.raises(StatusSourceRefusal, match=match):
        status_delivery(SNAPSHOT, INCIDENT, SCOPE.model_copy(update=update), now=NOW)


def test_unknown_or_unresolved_public_incidents_are_refused():
    with pytest.raises(StatusSourceRefusal, match="not in this snapshot"):
        status_delivery(SNAPSHOT, "zzzzzzzzzzzz", SCOPE.model_copy(update=dict(incident="zzzzzzzzzzzz")), now=NOW)
    open_row = next(o for o in SNAPSHOT.observations if o.status != "resolved")
    scope = SCOPE.model_copy(update=dict(incident=open_row.incident_id, component=open_row.components[0]))
    with pytest.raises(StatusSourceRefusal, match="not resolved"):
        status_delivery(SNAPSHOT, open_row.incident_id, scope, now=NOW)


def test_missing_published_start_is_not_replaced_by_creation_time():
    rows = tuple(replace(o, started_at=None) if o.incident_id == INCIDENT else o for o in SNAPSHOT.observations)
    with pytest.raises(StatusSourceRefusal, match="no published start"):
        status_delivery(replace(SNAPSHOT, observations=rows), INCIDENT, SCOPE, now=NOW)


def test_an_incident_resolved_after_its_own_observation_is_refused():
    rows = tuple(replace(o, resolved_at="2026-11-05T00:00:00+00:00") if o.incident_id == INCIDENT else o
                 for o in SNAPSHOT.observations)
    with pytest.raises(StatusSourceRefusal, match="after the snapshot was observed"):
        status_delivery(replace(SNAPSHOT, observations=rows), INCIDENT, SCOPE, now=NOW)


def test_another_status_origin_is_refused():
    with pytest.raises(StatusSourceRefusal, match="official Twilio status feed"):
        status_delivery(replace(SNAPSHOT, source_uri="https://example.com/incidents.json"), INCIDENT, SCOPE, now=NOW)


def test_real_public_record_through_the_ordinary_signed_enrollment_path(tmp_path):
    from fastapi.testclient import TestClient
    from tests.test_source_config_v4 import app_for
    from uptime.auth_client import service_headers

    def signed(client, sender, body):
        instance = client.get("/api/auth/context").json()["instance"]
        return service_headers(instance=instance, origin=DEFAULT_ORIGIN, path=f"/api/correspondence/claims/{claim}/events",
                               body=body, subject=sender.subject, key=sender)
    config, sender_file, db = tmp_path / "grants.json", tmp_path / "status.json", tmp_path / "workspace.db"
    init_config(config, "replay", DEFAULT_ORIGIN, "bears")
    update_source(config, "add", "status.twilio-public", source="status", scope=SCOPE, sender_path=sender_file)
    human = generate_reviewer_key()
    enroll(db, "source.operator", human, tenant="bears")
    sender = load_private(sender_file, SenderCredential)
    claim = "inbox-public-status-1"
    delivery, _ = status_delivery(SNAPSHOT, INCIDENT, SCOPE, now=NOW)
    raw = delivery.model_dump_json().encode()
    with TestClient(app_for(config, db), base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 50000)) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "source.operator", human)
        assert reviewer.post("/api/correspondence/claims", {"claim_id": claim, "scope": SCOPE.model_dump()}).status_code == 200
        receipt = deliver(client, sender, claim, raw)
        assert deliver(client, sender, claim, raw) == receipt
        case = client.get(f"/api/correspondence/claims/{claim}", headers=reviewer.headers).json()
        # A real public outage is a status record, not this customer's impact or fees.
        assert [e["detail"] for e in case["evidence"]] == [delivery.event_id + " · status"]
        assert case["outcome"] == "INSUFFICIENT_EVIDENCE" and case["amount"] is None
        assert case["preflight"]["missing"] == ["Awaiting an authenticated impact record for this exact claim."]
        # The same key cannot deliver a public record for an incident its grant does not name.
        other, _ = status_delivery(SNAPSHOT, "2ylvwxdqqjz2", SCOPE.model_copy(update=dict(
            incident="2ylvwxdqqjz2", component="8vdlvw3dsq8h")), now=NOW)
        foreign = other.model_dump_json().encode()
        assert client.post(f"/api/correspondence/claims/{claim}/events", content=foreign,
                           headers=signed(client, sender, foreign)).status_code == 403
        # A later public edit of the same incident is a distinct record; one-per-kind intake
        # surfaces it as a contradiction for a person instead of silently choosing a version.
        rows = tuple(replace(o, resolved_at="2026-11-02T01:00:00+00:00") if o.incident_id == INCIDENT else o
                     for o in SNAPSHOT.observations)
        rows = tuple(replace(o, content_hash="e" * 64) if o.incident_id == INCIDENT else o for o in rows)
        revised, _ = status_delivery(replace(SNAPSHOT, observations=rows), INCIDENT, SCOPE, now=NOW)
        assert revised.event_id != delivery.event_id
        deliver(client, sender, claim, revised.model_dump_json().encode())
    # Authored customer and billing records from their own enrolled sources complete the set.
    for subject, role in [("customer.local", "customer"), ("billing.local", "billing")]:
        update_source(config, "add", subject, source=role, scope=SCOPE, sender_path=tmp_path / (role + ".json"))
    with TestClient(app_for(config, db), base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 50000)) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "source.operator", human)
        for role, body in [("customer", dict(kind="impact", start=delivery.body.start, end=delivery.body.end,
                                             affected=True, exclusion="none")),
                           ("billing", dict(kind="invoice", lines=[dict(id="a", kind="affected_api", amount="10.00")]))]:
            source = load_private(tmp_path / (role + ".json"), SenderCredential)
            event = json.dumps({"event_id": role + ".authored", "scope": SCOPE.model_dump(), "body": body}).encode()
            deliver(client, source, claim, event)
        case = client.get(f"/api/correspondence/claims/{claim}", headers=reviewer.headers).json()
        assert case["preflight"]["missing"] == [
            "Contradictory independent records require review. No version is selected silently."]
        assert case["amount"] is None
    with sqlite3.connect(db) as connection:
        stored = connection.execute("SELECT event_id FROM inbox_delivery ORDER BY rowid").fetchall()
    assert stored == [(delivery.event_id,), (revised.event_id,), ("customer.authored",), ("billing.authored",)]


def test_operator_script_checks_role_and_joins_receipt_with_provenance(tmp_path):
    from scripts.deliver_public_status import deliver_public_status
    config, sender_file = tmp_path / "grants.json", tmp_path / "customer.json"
    init_config(config, "replay", DEFAULT_ORIGIN, "bears")
    update_source(config, "add", "customer.local", source="customer", scope=SCOPE, sender_path=sender_file)
    customer = load_private(sender_file, SenderCredential)

    class Unreachable:
        def get(self, *args, **kwargs):
            raise AssertionError("a refused record must not reach the listener")
        post = get

    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(SNAPSHOT.payload()))
    with pytest.raises(ValueError, match="enrolled status source"):
        deliver_public_status(Unreachable(), customer, "inbox-public-status-1", snapshot, INCIDENT, now=NOW)
    status_file = tmp_path / "status.json"
    update_source(config, "add", "status.twilio-public", source="status", scope=SCOPE, sender_path=status_file)
    status = load_private(status_file, SenderCredential)
    with pytest.raises(StatusSourceRefusal, match="older than 24 hours"):
        deliver_public_status(Unreachable(), status, "inbox-public-status-1", snapshot, INCIDENT,
                              now=OBSERVED + timedelta(days=5))
