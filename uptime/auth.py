"""Local named identities, process-bound read sessions and exact single-use writes.

Enrollment is an offline operator action. A random P-256 key signs short-lived
challenges. The server stores only its public key. Private keys stay with the operator.
This is a single-process loopback prototype.
"""
from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
from threading import RLock
from time import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .auth_keys import public_bytes, rehearsal_key, verify_reviewer
from .contracts import Principal, fingerprint
from .correspondence_types import Id
from .source_config import SourceGrant
from .storage import database

TENANT = "bears"
SCRIPT = "scripted-test-reviewer"
DEFAULT_ORIGIN = "http://127.0.0.1:8765"
TTL = 60
NAME = re.compile(r"[a-z][a-z0-9_.-]{1,63}", re.ASCII)


def digest(data):
    return sha256(data).hexdigest()


def signature(key, message):
    return hmac.new(key, message.encode(), sha256).hexdigest()


def valid_origin(origin):
    url = urlsplit(origin)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or
            url.username or url.password or not url.port or url.path or url.query or url.fragment):
        raise ValueError("Choose an exact HTTP loopback origin with a port")
    return origin


def bind_workspace(path, mode, rehearsal, tenant=TENANT):
    """A rehearsal or other mode must never reuse human state or an ambiguous legacy DB."""
    if mode not in {"replay", "sandbox"} or (rehearsal and mode != "replay"):
        raise ValueError("Scripted rehearsal requires isolated replay mode")
    TypeAdapter(Id).validate_python(tenant, strict=True)
    scope = (mode, int(rehearsal), tenant)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and "authority_workspace" not in tables:
            raise ValueError("Unscoped legacy database. Choose a fresh V4 workspace.")
        db.execute("CREATE TABLE IF NOT EXISTS authority_workspace "
                   "(id INTEGER PRIMARY KEY CHECK(id=1), mode TEXT, rehearsal INTEGER, tenant TEXT NOT NULL)")
        columns = {row[1] for row in db.execute("PRAGMA table_info(authority_workspace)")}
        if "tenant" not in columns:
            if tenant != TENANT:
                raise ValueError("An existing single-tenant V4 database belongs to bears")
            db.execute("ALTER TABLE authority_workspace ADD COLUMN tenant TEXT NOT NULL DEFAULT 'bears'")
        db.execute("INSERT OR IGNORE INTO authority_workspace(id,mode,rehearsal,tenant) VALUES(1,?,?,?)", scope)
        row = db.execute("SELECT mode,rehearsal,tenant FROM authority_workspace WHERE id=1").fetchone()
        if tuple(row) != scope:
            raise ValueError("Database belongs to a different authority, tenant or execution mode")
        Path(path).chmod(0o600)
        if "authority_user" in tables:
            columns = {row[1] for row in db.execute("PRAGMA table_info(authority_user)")}
            if columns != {"subject", "role", "public_key"}:
                raise ValueError("Legacy password authority requires a fresh workspace and offline key enrollment")
        db.execute("CREATE TABLE IF NOT EXISTS authority_user "
                   "(subject TEXT PRIMARY KEY, role TEXT NOT NULL, public_key BLOB NOT NULL UNIQUE)")


def enroll(path, subject, credential, role="reviewer", mode="replay", tenant=TENANT):
    if (not NAME.fullmatch(subject) or subject.startswith(("scripted-", "service-", "local-"))
            or role not in {"viewer", "reviewer"}):
        raise ValueError("Use a named local human account and a viewer or reviewer role")
    if isinstance(credential, dict) and credential.get("uptime_rehearsal"):
        raise ValueError("A scripted rehearsal key cannot enroll a human")
    public = public_bytes(credential)
    bind_workspace(path, mode, False, tenant)
    try:
        with database(path) as db, db:
            db.execute("INSERT INTO authority_user VALUES(?,?,?)", (subject, role, public))
    except sqlite3.IntegrityError:
        raise ValueError("Account or public key already enrolled") from None


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChallengeRequest(Strict):
    subject: str = Field(min_length=2, max_length=64)
    path: str = Field(default="/api/auth/login", max_length=1024)
    body_sha256: str = Field(default="", max_length=64)


class LoginProof(Strict):
    challenge: str = Field(min_length=20, max_length=128)
    proof: str = Field(pattern=r"^[a-f0-9]{128}$")


@dataclass(frozen=True)
class Challenge:
    subject: str
    path: str
    body: str
    session: str
    revision: int
    expires: float
    message: str


@dataclass(frozen=True)
class Session:
    principal: Principal
    expires: float
    key_tag: str


@dataclass(frozen=True)
class ServicePrincipal(Principal):
    source_key_id: str
    source_grant_id: str


class Authority:
    def __init__(self, path, mode, rehearsal, approvals_enabled, rehearsal_secret, service_credentials, origin, tenant=TENANT):
        self.tenant = tenant
        self.origin = valid_origin(origin)
        self.instance = secrets.token_hex(24)
        self.approvals_enabled = bool(approvals_enabled)
        self.mode = mode
        self.rehearsal = rehearsal
        self.path = path
        self.lock = RLock()
        self.revision = 0
        self.sessions = {}
        self.challenges = {}
        self.deliveries = {}
        self.services = dict(service_credentials or {})
        identities = set()
        for subject, key in self.services.items():
            if not NAME.fullmatch(subject):
                raise ValueError("Inbound services need canonical subjects")
            if isinstance(key, SourceGrant):
                if key.subject != subject:
                    raise ValueError("Source identity and grant must match")
                identity = ("ed25519", key.public_key)
            else:
                if (not isinstance(key, str) or len(key) < 32 or
                        not (rehearsal or "fixture" in re.split(r"[._-]", subject))):
                    raise ValueError("Shared-key services require a named local fixture or scripted rehearsal")
                identity = ("fixture", key)
            if identity in identities:
                raise ValueError("Inbound sources require independent keys")
            identities.add(identity)
        if rehearsal != bool(rehearsal_secret) or (rehearsal and len(rehearsal_secret) < 32):
            raise ValueError("Only a scripted replay can use a private rehearsal credential")
        bind_workspace(path, mode, rehearsal, tenant)
        if rehearsal:
            self.script_account = ("reviewer", public_bytes(rehearsal_key(rehearsal_secret)))

    def account(self, subject):
        if self.rehearsal:
            return self.script_account if subject == SCRIPT else None
        with database(self.path) as db:
            row = db.execute("SELECT role,public_key FROM authority_user WHERE subject=?", (subject,)).fetchone()
        return tuple(row) if row else None

    def prune(self):
        now = time()
        for store in (self.sessions, self.challenges):
            for key in [k for k, value in store.items() if value.expires <= now]:
                del store[key]
        for key in [k for k, expires in self.deliveries.items() if expires <= now]:
            del self.deliveries[key]

    def session_id(self, request):
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme != "Bearer" or not token or len(token) > 128:
            raise HTTPException(401, "Sign in to this local workspace")
        return digest(token.encode())

    def actor(self, request: Request):
        with self.lock:
            session = self.sessions.get(self.session_id(request))
        if not session or session.expires <= time():
            raise HTTPException(401, "Session expired. Sign in again.")
        principal = session.principal
        account = self.account(principal.subject)
        if not account or principal.tenant != self.tenant or principal.role != account[0] or digest(account[1]) != session.key_tag:
            raise HTTPException(403, "Local authority changed. Sign in again.")
        return principal

    def require_origin(self, request):
        if (request.headers.get("origin") != self.origin or
                f"{request.url.scheme}://{request.headers.get('host', '')}" != self.origin):
            raise HTTPException(403, "Exact local origin required")

    def require_gate(self):
        if not self.approvals_enabled:
            raise HTTPException(403, "Consequential actions are disabled in this deployment")

    def challenge(self, request: Request, body: ChallengeRequest):
        self.require_origin(request)
        login = body.path == "/api/auth/login"
        session = ""
        if not login:
            self.require_gate()
            p = self.actor(request)
            if p.role != "reviewer" or p.subject != body.subject:
                raise HTTPException(403, "Named reviewer required")
            if (not body.path.startswith("/api/") or body.path.startswith("/api/auth/")
                    or any(c in body.path for c in "?#\\") or not re.fullmatch(r"[a-f0-9]{64}", body.body_sha256)):
                raise HTTPException(400, "A reviewer proof must name one exact API action and body digest")
            session = self.session_id(request)
        elif body.body_sha256:
            raise HTTPException(400, "Invalid login challenge")
        with self.lock:
            self.prune()
            if len(self.challenges) >= 2048:
                raise HTTPException(429, "Too many pending challenges")
            nonce = secrets.token_urlsafe(32)
            expires = int(time()) + TTL
            message = json.dumps(["uptime-v4", self.instance, self.origin, self.tenant, self.mode, self.rehearsal,
                                  body.subject, session, "POST", body.path, body.body_sha256,
                                  self.revision, expires, nonce], separators=(",", ":"))
            self.challenges[nonce] = Challenge(body.subject, body.path, body.body_sha256, session,
                                               self.revision, expires, message)
        return {"challenge": nonce, "message": message, "algorithm": "ES256"}

    def consume(self, nonce, proof, path, body, session):
        with self.lock:
            item = self.challenges.pop(nonce, None)
            if (not item or item.expires <= time() or item.path != path or item.body != body
                    or item.session != session or (session and item.revision != self.revision)):
                raise HTTPException(403, "Expired, reused or mismatched proof")
            account = self.account(item.subject)
            if not account or not verify_reviewer(account[1], item.message, proof):
                raise HTTPException(403, "Invalid credential proof")
            if session:
                # Invalidate every pending write after an authorized action, even if validation later fails.
                self.revision += 1
            return Principal(self.tenant, item.subject, account[0]), digest(account[1])

    def login(self, body: LoginProof):
        principal, tag = self.consume(body.challenge, body.proof, "/api/auth/login", "", "")
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.prune()
            if len(self.sessions) >= 2048:
                raise HTTPException(429, "Too many active sessions")
            self.sessions[digest(token.encode())] = Session(principal, time()+3600, tag)
        return {"token": token, "subject": principal.subject, "role": principal.role,
                "rehearsal": self.rehearsal, "approvals_enabled": self.approvals_enabled}

    def logout(self, request: Request):
        with self.lock:
            self.sessions.pop(self.session_id(request), None)
        return {"signed_out": True}

    async def reviewer(self, request: Request):
        self.require_origin(request)
        self.require_gate()
        principal = self.actor(request)
        if principal.role != "reviewer" or request.method != "POST" or request.url.query:
            raise HTTPException(403, "An exact reviewer POST is required")
        path = request.scope["raw_path"].decode("ascii")
        self.consume(request.headers.get("x-uptime-challenge", ""), request.headers.get("x-uptime-proof", ""),
                     path, digest(await request.body()), self.session_id(request))
        return principal

    async def service(self, request: Request):
        """Authenticate exact raw inbound bytes, consumed once within this service audience."""
        self.require_origin(request)
        self.require_gate()
        subject = request.headers.get("x-uptime-service", "")
        key = self.services.get(subject)
        nonce = request.headers.get("x-uptime-nonce", "")
        stamp = request.headers.get("x-uptime-time", "")
        proof = request.headers.get("x-uptime-proof", "")
        if (not key or request.method != "POST" or request.url.query or
                not re.fullmatch(r"[a-zA-Z0-9_-]{20,128}", nonce) or not re.fullmatch(r"[0-9]{10}", stamp)
                or abs(time() - int(stamp)) >= TTL):
            raise HTTPException(403, "An authenticated inbound service is required")
        path = request.scope["raw_path"].decode("ascii")
        body = await request.body()
        message = service_message(self.instance, self.origin, subject, path, body, stamp, nonce, self.tenant,
                                  self.mode if isinstance(key, SourceGrant) else None)
        if isinstance(key, SourceGrant):
            valid = key.verify(message, proof) and key.allows(path, body)
            key_id = "ed25519-sha256:" + digest(bytes.fromhex(key.public_key))
            grant_id = fingerprint([self.tenant, self.mode, key.model_dump()])
        else:
            valid = bool(re.fullmatch(r"[a-f0-9]{64}", proof)) and hmac.compare_digest(signature(key.encode(), message), proof)
            key_id = "fixture-hmac:" + signature(key.encode(), "uptime-local-fixture-key-id-v1")
            grant_id = fingerprint([self.tenant, self.mode, subject, key_id, "LOCAL_FIXTURE"])
        with self.lock:
            self.prune()
            if not valid or (subject, nonce) in self.deliveries:
                raise HTTPException(403, "Invalid, out-of-scope or reused inbound proof")
            # The acceptance window includes future timestamps. Retain through its full end.
            self.deliveries[(subject, nonce)] = int(stamp) + TTL
            self.revision += 1
        return ServicePrincipal(self.tenant, subject, "service", key_id, grant_id)

    def register(self, app):
        app.add_api_route("/api/auth/challenge", self.challenge, methods=["POST"])
        app.add_api_route("/api/auth/login", self.login, methods=["POST"])
        app.add_api_route("/api/auth/logout", self.logout, methods=["POST"])
        app.add_api_route("/api/auth/context", lambda: {"instance": self.instance, "origin": self.origin,
                                                         "mode": self.mode, "tenant": self.tenant},
                          methods=["GET"])


def service_message(instance, origin, subject, path, body, stamp, nonce, tenant=TENANT, mode=None):
    return json.dumps(["uptime-v4-inbound", instance, origin, tenant, mode, subject, "POST", path, digest(body), stamp, nonce],
                      separators=(",", ":"))
