"""Native provider-shaped events signed locally; never provider-origin evidence."""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import hmac
import json
import sqlite3
from uuid import UUID

from fastapi.testclient import TestClient
import pytest

from uptime.ramp import RampError
from uptime.ramp_webhooks import (MAX_BODY, REQUEST, RESET, RampWebhookInbox, WebhookDeployment,
                                  WebhookError, create_webhook_app)

NOW = datetime(2026, 11, 4, 20, tzinfo=UTC)
BUSINESS = str(UUID(int=101))
REQUEST_ID = str(UUID(int=102))
TRIGGER = str(UUID(int=103))
SUBSCRIPTION = str(UUID(int=104))
SECRET = b"local-test-signing-material-only-32bytes"


def deployment(**kwargs):
    return WebhookDeployment(**dict(dict(deployment_id="test-deployment", tenant="test-tenant", business_id=BUSINESS,
        subscription_id=SUBSCRIPTION, service_key="Uptime-v4", secret=SECRET,
        event_types=frozenset({REQUEST, RESET, "bills.updated", "transactions.cleared", "transactions.authorized"})), **kwargs))


def signed(value, *, event_header=True, secret=SECRET, raw=None):
    body = raw if raw is not None else json.dumps(value, separators=(",", ":")).encode()
    headers = {"X-Ramp-Signature": hmac.new(secret, body, sha256).hexdigest(), "Content-Type": "application/json"}
    if event_header and value.get("id"):
        headers["X-Ramp-Webhook-ID"] = value["id"]
    return body, headers


def activate(inbox):
    event = {"type": "webhooks.verification", "challenge": "ramp_challenge_local_test"}
    raw, headers = signed(event, event_header=False)
    assert inbox.receive(raw, headers)["status"] == "pending_verification"
    request = inbox.verification_request(raw, headers)
    assert request["path"] == f"/developer/v1/webhooks/{SUBSCRIPTION}/verify"
    inbox.record_verification(event["challenge"], {"success": True})


def native_event(*, ident=201, kind=REQUEST, trigger=TRIGGER, at=NOW, business=BUSINESS, request=REQUEST_ID):
    obj = {"id": request}
    if kind in {REQUEST, RESET}:
        obj.update(approval_trigger_instance_uuid=trigger, service_key="Uptime-v4", node_id="node-external-review")
    return {"id": str(UUID(int=ident)), "type": kind, "created_at": at.isoformat(), "business_id": business, "object": obj}


@pytest.fixture
def inbox(tmp_path):
    result = RampWebhookInbox(tmp_path/"native.db", deployment(), clock=lambda: NOW)
    activate(result)
    return result


def test_challenge_is_separate_durable_and_does_not_activate(tmp_path):
    box = RampWebhookInbox(tmp_path/"native.db", deployment(), clock=lambda: NOW)
    event = {"type": "webhooks.verification", "challenge": "ramp_challenge_not_a_secret_for_test"}
    raw, headers = signed(event)
    assert box.receive(raw, headers)["kind"] == "verification"
    assert event["challenge"].encode() not in box.path.read_bytes()
    assert SECRET not in box.path.read_bytes()
    with pytest.raises(WebhookError, match="not active"):
        box.receive(*signed(native_event()))
    restarted = RampWebhookInbox(box.path, deployment(), clock=lambda: NOW)
    with pytest.raises(RampError, match="receipt"):
        restarted.record_verification("wrong", {"success": True})
    with pytest.raises(RampError, match="receipt"):
        restarted.record_verification(event["challenge"], {"success": False})
    restarted.record_verification(event["challenge"], {"success": True})
    assert restarted.receive(*signed(native_event()))["status"] == "ACTIVE"


def test_native_event_duplicate_is_durable_minimized(inbox):
    event = native_event()
    event["object"]["private_note"] = "DO-NOT-PERSIST-PRIVATE-TEXT"
    raw, headers = signed(event)
    assert inbox.receive(raw, headers)["duplicate"] is False
    restarted = RampWebhookInbox(inbox.path, deployment(), clock=lambda: NOW+timedelta(days=10))
    assert restarted.receive(raw, headers)["duplicate"] is True  # constant retry ID even after horizon
    assert len(restarted.events()) == 1
    assert restarted.trigger(TRIGGER)["request_id"] == REQUEST_ID
    assert b"DO-NOT-PERSIST-PRIVATE-TEXT" not in inbox.path.read_bytes()
    assert restarted.events()[0]["source"] == "SIMULATED_RAMP"


@pytest.mark.parametrize("mutation,status", [
    (lambda e: e.update(business_id=str(UUID(int=999))), 403),
    (lambda e: e["object"].update(service_key="uptime-v4"), 403),
    (lambda e: e.update(type="bills.fake_approval_trigger"), 400),
    (lambda e: e["object"].pop("approval_trigger_instance_uuid"), 400),
    (lambda e: e["object"].update(id="../bills/other"), 400),
    (lambda e: e.update(created_at=NOW.replace(tzinfo=None).isoformat()), 400),
    (lambda e: e.update(created_at=(NOW+timedelta(hours=1)).isoformat()), 400),
    (lambda e: e.update(created_at=(NOW-timedelta(days=8)).isoformat()), 400),
])
def test_invalid_native_event_rejected(inbox, mutation, status):
    event = native_event()
    mutation(event)
    with pytest.raises(WebhookError) as caught:
        inbox.receive(*signed(event))
    assert caught.value.status == status
    assert inbox.events() == []


def test_exact_raw_octets_and_forgery_and_header_id(inbox):
    event = native_event()
    raw, headers = signed(event)
    with pytest.raises(WebhookError, match="signature"):
        inbox.receive(raw+b" ", headers)
    with pytest.raises(WebhookError, match="signature"):
        inbox.receive(*signed(event, secret=b"wrong-test-key"))
    with pytest.raises(WebhookError, match="header ID"):
        inbox.receive(raw, {**headers, "X-Ramp-Webhook-ID": str(UUID(int=999))})
    dup = raw[:-1] + b',"business_id":"' + BUSINESS.encode() + b'"}'
    with pytest.raises(WebhookError, match="JSON"):
        inbox.receive(*signed(event, raw=dup))
    assert not inbox.events()


def test_conflicting_id_quarantines_and_survives_restart(inbox):
    inbox.receive(*signed(native_event()))
    with pytest.raises(WebhookError, match="quarantined"):
        inbox.receive(*signed(native_event(request=str(UUID(int=333)))))
    restarted = RampWebhookInbox(inbox.path, deployment(), clock=lambda: NOW)
    with pytest.raises(RampError, match="active verified"):
        restarted.trigger(TRIGGER)
    with pytest.raises(WebhookError, match="not active"):
        restarted.receive(*signed(native_event(ident=202)))
    with sqlite3.connect(inbox.path) as db:
        assert db.execute("SELECT COUNT(*) FROM rw_conflict").fetchone()[0] == 1


def test_out_of_order_financial_events_do_not_regress_watermark(inbox):
    new = native_event(kind="transactions.cleared", at=NOW)
    old = native_event(ident=202, kind="transactions.authorized", at=NOW-timedelta(minutes=3))
    assert inbox.receive(*signed(new))["status"] == "QUEUED"
    assert inbox.receive(*signed(old))["status"] == "OUT_OF_ORDER"
    # Events are hints to refresh the native object; no amount or approval inferred.
    assert "amount" not in inbox.events()[0]


@pytest.mark.parametrize("reset_first", [True, False])
def test_reset_tombstone_blocks_old_trigger_even_when_out_of_order(inbox, reset_first):
    request = native_event(at=NOW-timedelta(minutes=3))
    reset = native_event(ident=202, kind=RESET, at=NOW-timedelta(minutes=1))
    for event in ([reset, request] if reset_first else [request, reset]):
        inbox.receive(*signed(event))
    restarted = RampWebhookInbox(inbox.path, deployment(), clock=lambda: NOW)
    with pytest.raises(RampError):
        restarted.trigger(TRIGGER)
    assert restarted.receive(*signed(native_event(ident=203)))["status"] == "BLOCKED_OLD_TRIGGER"
    new_trigger = str(UUID(int=1040))
    restarted.receive(*signed(native_event(ident=204, trigger=new_trigger)))
    assert restarted.trigger(new_trigger)["id"] == new_trigger
    with pytest.raises(RampError):
        restarted.trigger(TRIGGER)


def test_past_reset_is_honored_even_outside_replay_horizon(inbox):
    inbox.receive(*signed(native_event()))
    assert inbox.receive(*signed(native_event(ident=203, kind=RESET, at=NOW-timedelta(days=30))))["status"] == "RESET"
    with pytest.raises(RampError):
        inbox.trigger(TRIGGER)


def test_equal_time_distinct_triggers_fail_closed(inbox):
    inbox.receive(*signed(native_event()))
    other = str(UUID(int=300))
    inbox.receive(*signed(native_event(ident=202, trigger=other)))
    for trigger in (TRIGGER, other):
        with pytest.raises(RampError):
            inbox.trigger(trigger)


def test_subscription_binding_cannot_be_swapped(inbox):
    with pytest.raises(RampError, match="binding"):
        RampWebhookInbox(inbox.path, deployment(business_id=str(UUID(int=999))), clock=lambda: NOW)


def test_isolated_fastapi_surface_and_durable_failure(inbox, monkeypatch):
    app = create_webhook_app(inbox)
    client = TestClient(app)
    raw, headers = signed(native_event())
    assert client.post("/webhooks/ramp", content=raw, headers=headers).status_code == 200
    assert client.get("/api/auth/context").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.post("/webhooks/ramp?tenant=other", content=raw, headers=headers).status_code == 400
    assert client.post("/webhooks/ramp", content=b"x"*(MAX_BODY+1), headers=headers).status_code == 413
    assert client.post("/webhooks/ramp", content=raw, headers={"Content-Type": "application/json"}).status_code == 401
    def broken(*args):
        raise sqlite3.OperationalError("PRIVATE-DATABASE-INFORMATION")
    monkeypatch.setattr(inbox, "receive", broken)
    response = client.post("/webhooks/ramp", content=raw, headers=headers)
    assert response.status_code == 503
    assert "PRIVATE" not in response.text
