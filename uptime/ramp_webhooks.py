"""Ramp's native webhook contract, isolated from the local reviewer protocol.

No registration, credential loading or HTTP transport. Secrets and raw private
payloads stay out of SQLite; only routing facts and raw-byte hashes are retained.
"""
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
import sqlite3
from typing import Mapping

from .ramp import RampError, uuid_text
from .storage import database

MAX_BODY = 256_000
REQUEST = "unified_requests.external_approval_request"
RESET = "unified_requests.external_approval_request_reset"
EVENTS = frozenset({
    "bills.approved", "bills.archived", "bills.created", "bills.paid", "bills.ready_to_sync",
    "bills.rejected", "bills.updated", "draft_bills.created", "transactions.authorized",
    "transactions.cleared", "transactions.declined", "transactions.ready_for_review",
    "transactions.ready_to_sync", "transactions.receipt_added", "transactions.synced",
    "transactions.sync_requested", "transactions.body_coding_updated",
    "transactions.all_requirements_met_and_approved_changed", REQUEST, RESET,
    "unified_requests.created", "unified_requests.modified", "unified_requests.updated",
    "unified_requests.node_advanced", "unified_requests.override_approved",
})
SOURCES = {"SIMULATED_RAMP", "RAMP_SANDBOX_WEBHOOK"}


def utcnow():
    return datetime.now(UTC)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError
        return result.astimezone(UTC)
    except (TypeError, ValueError):
        raise RampError("Invalid timestamp") from None


def opaque(value, limit=200):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0," + str(limit-1) + "}", value):
        raise RampError("Invalid integration identifier")
    return value


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise WebhookError(400, "Invalid JSON object") from None


class WebhookError(RampError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


@dataclass(frozen=True)
class WebhookDeployment:
    deployment_id: str
    tenant: str
    business_id: str
    subscription_id: str
    service_key: str
    secret: bytes = field(repr=False, compare=False)
    event_types: frozenset[str] = field(default_factory=lambda: frozenset({REQUEST, RESET}))
    source: str = "SIMULATED_RAMP"

    def __post_init__(self):
        for value in (self.deployment_id, self.tenant, self.service_key):
            opaque(value)
        uuid_text(self.business_id)
        uuid_text(self.subscription_id)
        if (not isinstance(self.secret, bytes) or len(self.secret) < 32 or
                not self.event_types or not self.event_types <= EVENTS or self.source not in SOURCES):
            raise RampError("Invalid webhook deployment")

    def binding(self):
        return {"deployment_id": self.deployment_id, "tenant": self.tenant,
                "business_id": self.business_id, "subscription_id": self.subscription_id,
                "service_key": self.service_key, "event_types": sorted(self.event_types), "source": self.source}


class RampWebhookInbox:
    def __init__(self, path, deployment, *, clock=utcnow, max_age=timedelta(days=7)):
        self.path, self.deployment, self.clock, self.max_age = Path(path), deployment, clock, max_age
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with database(self.path) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS rw_deployment (
                    id TEXT PRIMARY KEY, binding TEXT NOT NULL, status TEXT NOT NULL,
                    challenge_digest TEXT);
                CREATE TABLE IF NOT EXISTS rw_event (
                    deployment TEXT NOT NULL, id TEXT NOT NULL, digest TEXT NOT NULL,
                    event TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(deployment,id));
                CREATE TABLE IF NOT EXISTS rw_conflict (
                    deployment TEXT NOT NULL, id TEXT NOT NULL, digest TEXT NOT NULL,
                    PRIMARY KEY(deployment,id,digest));
                CREATE TABLE IF NOT EXISTS rw_object (
                    deployment TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, at TEXT NOT NULL,
                    PRIMARY KEY(deployment,kind,id));
                CREATE TABLE IF NOT EXISTS rw_trigger (
                    deployment TEXT NOT NULL, id TEXT NOT NULL, request_id TEXT NOT NULL,
                    node_id TEXT NOT NULL, service_key TEXT NOT NULL, event_id TEXT NOT NULL,
                    at TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(deployment,id));
            """)
            db.execute("INSERT OR IGNORE INTO rw_deployment VALUES(?,?,'pending_verification',NULL)",
                       (deployment.deployment_id, canonical(deployment.binding())))
            row = db.execute("SELECT binding FROM rw_deployment WHERE id=?", (deployment.deployment_id,)).fetchone()
            if row[0] != canonical(deployment.binding()):
                raise RampError("Deployment binding changed; provision a separate deployment")
        self.path.chmod(0o600)

    def _parse(self, raw_body, headers):
        if not isinstance(raw_body, bytes) or len(raw_body) > MAX_BODY:
            raise WebhookError(413, "Webhook body exceeds limit")
        headers = {k.lower(): v for k, v in headers.items()}
        signature = headers.get("x-ramp-signature", "")
        if (not isinstance(signature, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", signature) or
                not hmac.compare_digest(hmac.new(self.deployment.secret, raw_body, sha256).hexdigest(), signature.lower())):
            raise WebhookError(401, "Invalid Ramp signature")
        event = strict_json(raw_body)
        if event.get("type") == "webhooks.verification":
            challenge = event.get("challenge")
            if ("x-ramp-webhook-id" in headers or set(event) != {"type", "challenge"} or
                    not isinstance(challenge, str) or not 1 <= len(challenge) <= 1024 or
                    any(ord(c) < 32 for c in challenge)):
                raise WebhookError(400, "Invalid verification challenge")
            return event
        try:
            ident = uuid_text(event.get("id"))
            if headers.get("x-ramp-webhook-id") != ident:
                raise WebhookError(400, "Event header ID mismatch")
            if event.get("business_id") != self.deployment.business_id:
                raise WebhookError(403, "Webhook business mismatch")
            if event.get("type") not in self.deployment.event_types:
                raise WebhookError(400, "Unsubscribed event type")
            timestamp(event.get("created_at"))
            obj = event.get("object")
            if not isinstance(obj, dict):
                raise WebhookError(400, "Invalid event object")
            uuid_text(obj.get("id"))
            if event["type"] in {REQUEST, RESET}:
                uuid_text(obj.get("approval_trigger_instance_uuid"))
                opaque(obj.get("node_id"))
                if obj.get("service_key") != self.deployment.service_key:
                    raise WebhookError(403, "Webhook service key mismatch")
        except WebhookError:
            raise
        except RampError:
            raise WebhookError(400, "Invalid native event fields") from None
        return event

    def verification_request(self, raw_body, headers):
        """Root-only helper. Returns challenge to caller, never logs or persists it.

        Root must submit this request separately and call record_verification with
        its actual successful response. This worker has no verification transport.
        """
        event = self._parse(raw_body, headers)
        if event["type"] != "webhooks.verification":
            raise WebhookError(400, "Expected a verification challenge")
        return {"method": "POST", "path": f"/developer/v1/webhooks/{self.deployment.subscription_id}/verify",
                "body": {"challenge": event["challenge"]}}

    def record_verification(self, challenge, response):
        with database(self.path) as db, db:
            row = db.execute("SELECT status,challenge_digest FROM rw_deployment WHERE id=?",
                             (self.deployment.deployment_id,)).fetchone()
            if (response != {"success": True} or row[0] != "pending_verification" or
                    row[1] is None or not hmac.compare_digest(row[1], digest(challenge))):
                raise RampError("Matching successful verification receipt required")
            db.execute("UPDATE rw_deployment SET status='active',challenge_digest=NULL WHERE id=?",
                       (self.deployment.deployment_id,))

    def receive(self, raw_body: bytes, headers: Mapping):
        event = self._parse(raw_body, headers)
        dep, raw_digest = self.deployment.deployment_id, sha256(raw_body).hexdigest()
        conflict = False
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            state = db.execute("SELECT status FROM rw_deployment WHERE id=?", (dep,)).fetchone()[0]
            if event["type"] == "webhooks.verification":
                if state != "pending_verification":
                    raise WebhookError(409, "Subscription is not pending verification")
                db.execute("UPDATE rw_deployment SET challenge_digest=? WHERE id=?", (digest(event["challenge"]), dep))
                return {"received": True, "kind": "verification", "status": "pending_verification"}
            if state != "active":
                raise WebhookError(409, "Webhook subscription is not active")
            old = db.execute("SELECT digest,state FROM rw_event WHERE deployment=? AND id=?", (dep, event["id"])).fetchone()
            if old:
                if old[0] == raw_digest:
                    return {"received": True, "duplicate": True, "status": old[1]}
                db.execute("INSERT OR IGNORE INTO rw_conflict VALUES(?,?,?)", (dep, event["id"], raw_digest))
                db.execute("UPDATE rw_deployment SET status='quarantined' WHERE id=?", (dep,))
                conflict = True
            else:
                at = timestamp(event["created_at"])
                if at > self.clock() + timedelta(minutes=5) or (event["type"] != RESET and self.clock()-at > self.max_age):
                    raise WebhookError(400, "Event outside acceptance window")
                obj = {"id": event["object"]["id"]}
                if event["type"] in {REQUEST, RESET}:
                    obj.update({key: event["object"][key] for key in
                                ("approval_trigger_instance_uuid", "service_key", "node_id")})
                safe = {key: event[key] for key in ("id", "type", "business_id")}
                safe.update(created_at=at.isoformat(), object=obj, source=self.deployment.source)
                kind = event["type"].split(".")[0]
                watermark = db.execute("SELECT at FROM rw_object WHERE deployment=? AND kind=? AND id=?",
                                       (dep, kind, obj["id"])).fetchone()
                status = "OUT_OF_ORDER" if watermark and at <= timestamp(watermark[0]) else "QUEUED"
                if status == "QUEUED":
                    db.execute("INSERT OR REPLACE INTO rw_object VALUES(?,?,?,?)", (dep, kind, obj["id"], at.isoformat()))
                if event["type"] in {REQUEST, RESET}:
                    status = self._lifecycle(db, safe)
                db.execute("INSERT INTO rw_event VALUES(?,?,?,?,?)", (dep, event["id"], raw_digest, canonical(safe), status))
        if conflict:
            raise WebhookError(409, "Conflicting event ID quarantined")
        return {"received": True, "duplicate": False, "status": status}

    def _lifecycle(self, db, event):
        dep, obj, at = self.deployment.deployment_id, event["object"], event["created_at"]
        trigger = obj["approval_trigger_instance_uuid"]
        old = db.execute("SELECT * FROM rw_trigger WHERE deployment=? AND id=?", (dep, trigger)).fetchone()
        if old and (old["request_id"], old["node_id"], old["service_key"]) != (obj["id"], obj["node_id"], obj["service_key"]):
            db.execute("UPDATE rw_deployment SET status='quarantined' WHERE id=?", (dep,))
            return "QUARANTINED"
        if event["type"] == RESET:
            db.execute("INSERT OR REPLACE INTO rw_trigger VALUES(?,?,?,?,?,?,?,'RESET')",
                       (dep, trigger, obj["id"], obj["node_id"], obj["service_key"], event["id"], at))
            return "RESET"
        if old:
            # A previously reset/superseded ID cannot be revived, even by a newer request.
            return "TRIGGER_ALREADY_SEEN" if old["state"] == "ACTIVE" else "BLOCKED_OLD_TRIGGER"
        latest = db.execute("SELECT MAX(at) FROM rw_trigger WHERE deployment=? AND request_id=? AND node_id=?",
                            (dep, obj["id"], obj["node_id"])).fetchone()[0]
        status = "SUPERSEDED" if latest and timestamp(at) <= timestamp(latest) else "ACTIVE"
        if latest and timestamp(at) == timestamp(latest):
            db.execute("UPDATE rw_trigger SET state='AMBIGUOUS' WHERE deployment=? AND request_id=? AND node_id=? AND state='ACTIVE'",
                       (dep, obj["id"], obj["node_id"]))
        if status == "ACTIVE":
            db.execute("UPDATE rw_trigger SET state='SUPERSEDED' WHERE deployment=? AND request_id=? AND node_id=? AND state='ACTIVE'",
                       (dep, obj["id"], obj["node_id"]))
        db.execute("INSERT INTO rw_trigger VALUES(?,?,?,?,?,?,?,?)",
                   (dep, trigger, obj["id"], obj["node_id"], obj["service_key"], event["id"], at, status))
        return status

    def trigger(self, trigger_id, *, db=None):
        if db is None:
            with database(self.path) as conn:
                return self.trigger(trigger_id, db=conn)
        uuid_text(trigger_id)
        dep = self.deployment.deployment_id
        deployment = db.execute("SELECT status FROM rw_deployment WHERE id=?", (dep,)).fetchone()
        row = db.execute("SELECT * FROM rw_trigger WHERE deployment=? AND id=?", (dep, trigger_id)).fetchone()
        if not row or row["state"] != "ACTIVE" or deployment[0] != "active":
            raise RampError("No active verified trigger; reset or unavailable")
        return {**dict(row), "tenant": self.deployment.tenant, "business_id": self.deployment.business_id,
                "source": self.deployment.source}

    def events(self):
        with database(self.path) as db:
            return [dict(json.loads(r["event"]), status=r["state"]) for r in db.execute(
                "SELECT event,state FROM rw_event WHERE deployment=? ORDER BY rowid", (self.deployment.deployment_id,))]


def create_webhook_app(inbox):
    """Standalone app. Do not mount the reviewer's routes on this listener."""
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.post("/webhooks/ramp")
    async def receive(request: Request):
        try:
            if request.url.query or request.headers.get("content-type", "").split(";")[0] != "application/json":
                raise WebhookError(400, "JSON webhook request required")
            for name in ("x-ramp-signature", "x-ramp-webhook-id", "content-type"):
                if len(request.headers.getlist(name)) > 1:
                    raise WebhookError(400, "Duplicate webhook header")
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BODY:
                    raise WebhookError(413, "Webhook body exceeds limit")
            return inbox.receive(bytes(body), request.headers)
        except WebhookError as exc:
            return JSONResponse({"error": str(exc)}, status_code=exc.status)
        except sqlite3.Error:
            return JSONResponse({"error": "Durable webhook storage unavailable"}, status_code=503)
    return app
