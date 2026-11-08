"""Explicit, expiring local adapter review; never a general or native release.

The operator-owned approval and revocation store lives outside the workspace.
Its filesystem owner is a trust boundary, not an independent release witness.
"""
import asyncio
from contextlib import contextmanager
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sqlite3
import subprocess
from time import monotonic, time
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import Field, model_validator
from starlette.requests import Request
from starlette.responses import JSONResponse

from .auth_keys import public_bytes, reviewer_signature, verify_reviewer
from .contracts import Principal, fingerprint
from .gates import source_identity
from .mandates import describe
from .ramp_webhooks import strict_json
from .source_config import Strict, _check_file, _protected_path
from .storage import database
from .vendor_bindings import dependency
from . import vendor_registry as registry

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_ROOT = Path.home() / ".config/uptime/local-review-exceptions"
DENIED = "Local review permission is unavailable or outside its scope"
DOMAIN = "uptime-local-review-exception-signature/1\n"
OPERATIONS = ("interpret", "approve", "activate", "rollback")
PREFIX = "/api/vendors/calyxquay/actions/"
EMPTY_SHA = sha256(b"{}").hexdigest()
Hex = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
ERRORS = (OSError, ValueError, TypeError, KeyError, sqlite3.Error, subprocess.SubprocessError, OverflowError)


class SourceIdentity(Strict):
    commit: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    manifest_sha256: Hex


class Proposal(Strict):
    schema_version: Literal["uptime-local-review-exception/1"]
    grant_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    workspace_path: Annotated[str, Field(min_length=1, max_length=4096)]
    workspace_id: Hex
    host_sha256: Hex
    origin: Annotated[str, Field(min_length=1, max_length=128)]
    tenant: Literal["bears"]
    mode: Literal["replay"]
    rehearsal: Literal[False]
    reviewer: Annotated[str, Field(min_length=2, max_length=64)]
    reviewer_key_sha256: Hex
    vendor: Literal["calyxquay"]
    candidate_version: Hex
    dependency_sha256: Hex
    suite_sha256: Hex
    initial_revision: Annotated[int, Field(ge=1)]
    initial_history_sha256: Hex
    source: SourceIdentity
    test_evidence_path: Annotated[str, Field(min_length=1, max_length=4096)]
    test_evidence_sha256: Hex
    not_before: int
    expires_at: int
    scope: Literal["interpret,approve,activate,rollback"]

    @model_validator(mode="after")
    def bounded(self):
        if not 0 < self.expires_at - self.not_before <= 48 * 3600:
            raise ValueError(DENIED)
        return self


class Envelope(Strict):
    schema_version: Literal["uptime-local-review-exception-envelope/1"]
    proposal: Proposal
    signature: Annotated[str, Field(pattern=r"^[a-f0-9]{128}$")]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def proposal_digest(proposal):
    return sha256(canonical(proposal)).hexdigest()


def signing_message(proposal):
    return DOMAIN + canonical(proposal).decode()


def write_json(path, value):
    path = _protected_path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def _read(path, *, protected=True):
    path = Path(path)
    if protected:
        path = _protected_path(path)
    elif not path.is_absolute() or path.resolve() != path:
        raise ValueError(DENIED)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        if protected:
            _check_file(handle.fileno())
        raw = handle.read(262145)
    if len(raw) > 262144:
        raise ValueError(DENIED)
    return strict_json(raw), sha256(raw).hexdigest()


def _host(*, create=False):
    root = AUTHORITY_ROOT
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.resolve() != root or root.stat().st_uid != os.geteuid() or root.stat().st_mode & 0o777 != 0o700:
        raise ValueError(DENIED)
    path = root / "host.json"
    if create and not path.exists():
        try:
            write_json(path, {"schema_version": "uptime-local-review-host/1", "nonce": secrets.token_hex(32)})
        except FileExistsError:
            pass
    value, digest = _read(path)
    if (set(value) != {"schema_version", "nonce"} or value["schema_version"] != "uptime-local-review-host/1"
            or not isinstance(value["nonce"], str) or not re.fullmatch(r"[a-f0-9]{64}", value["nonce"])):
        raise ValueError(DENIED)
    return digest


@contextmanager
def _lock():
    _host()
    path = _protected_path(AUTHORITY_ROOT / "authority.lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        _check_file(fd)
        # Do not block the event loop while another process changes authority.
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


@contextmanager
def _audit_db():
    path = _protected_path(AUTHORITY_ROOT / "authority.sqlite")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        _check_file(fd)
    finally:
        os.close(fd)
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS review_exception_event (sequence INTEGER PRIMARY KEY, grant_id TEXT NOT NULL, event TEXT NOT NULL, at INTEGER NOT NULL, payload TEXT NOT NULL)")
    for operation in ("UPDATE", "DELETE"):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS review_exception_no_{operation} BEFORE {operation} ON review_exception_event BEGIN SELECT RAISE(ABORT,'immutable exception audit'); END")
    db.execute("CREATE TRIGGER IF NOT EXISTS review_exception_no_replace BEFORE INSERT ON review_exception_event WHEN EXISTS (SELECT 1 FROM review_exception_event WHERE sequence=NEW.sequence) BEGIN SELECT RAISE(ABORT,'immutable exception audit'); END")
    db.commit()
    try:
        with db:
            yield db
    finally:
        db.close()


def _events(grant_id):
    with _audit_db() as db:
        return [dict(row) for row in db.execute("SELECT event,at,payload FROM review_exception_event WHERE grant_id=? ORDER BY sequence", (grant_id,))]


def _event(grant_id, event, payload):
    with _audit_db() as db:
        db.execute("INSERT INTO review_exception_event(grant_id,event,at,payload) VALUES(?,?,?,?)",
                   (grant_id, event, int(time()), canonical(payload).decode()))


def _metadata(directory):
    from scripts.setup_live_reviewer import _directory, _load_metadata
    directory = _directory(directory)
    return directory, _load_metadata(directory)


def _evidence(path):
    value, digest = _read(path, protected=False)
    if not isinstance(value, dict) or type(value.get("exit_code")) is not int or value["exit_code"] != 0:
        raise ValueError(DENIED)
    command = shlex.split(value.get("command", ""))
    if (command[:4] != ["uv", "run", "--locked", "pytest"]
            or any(not word.startswith("--basetemp=") for word in command[4:])):
        raise ValueError(DENIED)
    summary = value.get("actual_summary", "")
    if (not isinstance(summary, str) or not re.fullmatch(r"[1-9][0-9]* passed(?:, [0-9]+ (?:skipped|warnings?))* in [0-9.]+s(?: \([0-9:]+\))?", summary)):
        raise ValueError(DENIED)
    source = SourceIdentity.model_validate(source_identity(commit=value.get("tested_commit")))
    if value.get("tested_commit") != source.commit:
        raise ValueError(DENIED)
    return source.model_dump(), digest


def _current(directory, metadata):
    path = directory / "workspace.db"
    binding = describe(path, metadata["subject"])
    if binding["mode"] != "replay" or binding["tenant"] != "bears":
        raise ValueError(DENIED)
    principal = Principal("bears", metadata["subject"], "reviewer")
    state = registry.get_vendor(path, principal, "calyxquay")
    return binding, state


def build_proposal(directory, evidence_path, lifetime_seconds=172800):
    """Read current state and create an UNSIGNED proposal, never an approval."""
    directory, metadata = _metadata(directory)
    binding, state = _current(directory, metadata)
    if (state["state"] != "SHADOW" or state["active_version"] is not None or state["reviewer"] is not None
            or state.get("interpretation_reviewer") is not None or not state["checks"]
            or not all(row["passed"] for row in state["checks"])
            or [row["operation"] for row in state["actions"]] != ["interpret"]):
        raise ValueError(DENIED)
    source, evidence_sha = _evidence(evidence_path)
    at = int(time())
    proposal = Proposal(schema_version="uptime-local-review-exception/1", grant_id=secrets.token_hex(16),
        workspace_path=str(directory), host_sha256=_host(create=True), origin=metadata["origin"], rehearsal=False,
        **binding, vendor="calyxquay", candidate_version=state["version"],
        dependency_sha256=dependency(state["manifest"]), suite_sha256=state["suite"], initial_revision=state["revision"],
        initial_history_sha256=fingerprint(state["audit"]), source=SourceIdentity(**source),
        test_evidence_path=str(Path(evidence_path)), test_evidence_sha256=evidence_sha,
        not_before=at, expires_at=at+lifetime_seconds, scope="interpret,approve,activate,rollback")
    return proposal.model_dump()


def _validate_proposal(directory, proposal):
    proposal = Proposal.model_validate(proposal)
    directory, metadata = _metadata(directory)
    binding, state = _current(directory, metadata)
    if (str(directory) != proposal.workspace_path or proposal.host_sha256 != _host()
            or metadata["origin"] != proposal.origin or metadata["subject"] != proposal.reviewer
            or any(binding[key] != getattr(proposal, key) for key in binding)
            or not proposal.not_before <= time() < proposal.expires_at):
        raise ValueError(DENIED)
    source, evidence_sha = _evidence(proposal.test_evidence_path)
    if source != proposal.source.model_dump() or evidence_sha != proposal.test_evidence_sha256:
        raise ValueError(DENIED)
    if (state["version"] != proposal.candidate_version or state["suite"] != proposal.suite_sha256
            or dependency(state["manifest"]) != proposal.dependency_sha256
            or state.get("semantic_binding_status") != "REVIEWED" or not state["checks"]
            or not all(row["passed"] for row in state["checks"])):
        raise ValueError(DENIED)
    prefix = [row for row in state["audit"] if row["revision"] <= proposal.initial_revision]
    later = [row for row in state["audit"] if row["revision"] > proposal.initial_revision]
    if (fingerprint(prefix) != proposal.initial_history_sha256 or len(later) > 4
            or [row["kind"] for row in later] != [registry.OPS[op] for op in OPERATIONS[:len(later)]]
            or any(row["actor"] != proposal.reviewer for row in later)
            or state["revision"] != proposal.initial_revision + len(later)):
        raise ValueError(DENIED)
    expected_state = ("SHADOW", "SHADOW", "APPROVED", "ACTIVE", "REVOKED")[len(later)]
    if state["state"] != expected_state:
        raise ValueError(DENIED)
    if len(later) and len(later) < 4 and state.get("interpretation_reviewer") != proposal.reviewer:
        raise ValueError(DENIED)
    return proposal, state


def owner_approve(directory, proposal_path, reviewed_sha256):
    """Person-run filesystem-owner approval of one exact proposal; not independent QA."""
    proposal, _ = _read(proposal_path)
    if proposal_digest(proposal) != reviewed_sha256:
        raise ValueError(DENIED)
    value, state = _validate_proposal(directory, proposal)
    if state["revision"] != value.initial_revision:
        raise ValueError(DENIED)
    with _lock():
        if _events(value.grant_id):
            raise ValueError(DENIED)
        approval = {"schema_version": "uptime-local-review-owner-approval/1", "grant_id": value.grant_id,
                    "proposal_sha256": reviewed_sha256, "host_sha256": value.host_sha256, "approved_at": int(time())}
        output = AUTHORITY_ROOT / (value.grant_id + ".json")
        write_json(output, approval)
        _event(value.grant_id, "OWNER_APPROVED", {"proposal_sha256": reviewed_sha256})
    return output


def _owner(proposal):
    approval, _ = _read(AUTHORITY_ROOT / (proposal.grant_id + ".json"))
    expected = {"schema_version", "grant_id", "proposal_sha256", "host_sha256", "approved_at"}
    if (set(approval) != expected or approval["schema_version"] != "uptime-local-review-owner-approval/1"
            or approval["grant_id"] != proposal.grant_id or approval["host_sha256"] != proposal.host_sha256
            or approval["proposal_sha256"] != proposal_digest(proposal.model_dump())
            or type(approval["approved_at"]) is not int
            or not proposal.not_before <= approval["approved_at"] < proposal.expires_at):
        raise ValueError(DENIED)


def authorize(directory, proposal_path, credential_path, output_path, reviewed_sha256):
    """Person-run exact-proposal signature; never invoked during draft preparation."""
    proposal, _ = _read(proposal_path)
    if proposal_digest(proposal) != reviewed_sha256:
        raise ValueError(DENIED)
    value, state = _validate_proposal(directory, proposal)
    if state["revision"] != value.initial_revision:
        raise ValueError(DENIED)
    with _lock():
        _owner(value)
        if any(row["event"] in {"REVOKED", "COMPLETED", "ACCEPTED"} for row in _events(value.grant_id)):
            raise ValueError(DENIED)
        credential, _ = _read(credential_path)
        if credential.get("uptime_rehearsal") or sha256(public_bytes(credential)).hexdigest() != value.reviewer_key_sha256:
            raise ValueError(DENIED)
        envelope = {"schema_version": "uptime-local-review-exception-envelope/1", "proposal": proposal,
                    "signature": reviewer_signature(credential, signing_message(proposal))}
        write_json(output_path, envelope)
    return Path(output_path)


def revoke(grant_id):
    if not isinstance(grant_id, str) or not re.fullmatch(r"[a-f0-9]{32}", grant_id):
        raise ValueError(DENIED)
    with _lock():
        _event(grant_id, "REVOKED", {"reason": "Explicit operator revocation"})


class ExceptionPolicy:
    def __init__(self, directory, grant_path):
        self.directory, self.metadata = _metadata(directory)
        self.grant_path = _protected_path(grant_path)
        raw, self.envelope_sha256 = _read(self.grant_path)
        self.envelope = Envelope.model_validate(raw)
        self.started_source = source_identity(commit=self.envelope.proposal.source.commit)
        remaining = self.envelope.proposal.expires_at - time()
        self.monotonic_until = monotonic() + max(0, min(remaining, 48 * 3600))
        self.async_lock = asyncio.Lock()

    def validate(self):
        if monotonic() >= self.monotonic_until:
            raise ValueError(DENIED)
        raw, digest = _read(self.grant_path)
        if digest != self.envelope_sha256 or Envelope.model_validate(raw) != self.envelope:
            raise ValueError(DENIED)
        p, state = _validate_proposal(self.directory, self.envelope.proposal.model_dump())
        if p.source.model_dump() != self.started_source:
            raise ValueError(DENIED)
        _owner(p)
        with database(self.directory / "workspace.db") as db:
            row = db.execute("SELECT public_key FROM authority_user WHERE subject=? AND role='reviewer'", (p.reviewer,)).fetchone()
        if not row or not verify_reviewer(row[0], signing_message(p.model_dump()), self.envelope.signature):
            raise ValueError(DENIED)
        events = _events(p.grant_id)
        if (any(row["event"] in {"REVOKED", "COMPLETED"} for row in events)
                or state["revision"] == p.initial_revision + 4):
            raise ValueError(DENIED)
        progress = [json.loads(row["payload"]) for row in events if row["event"] in {"ACCEPTED", "ACTION"}]
        if progress and progress[-1]["history_sha256"] != fingerprint(state["audit"]):
            raise ValueError(DENIED)
        if not progress and state["revision"] != p.initial_revision:
            raise ValueError(DENIED)
        return p, state

    def ready(self):
        try:
            self.validate()
            return True
        except ERRORS:
            return False


def attach(app, directory, grant_path):
    """Only the dedicated helper calls this; normal application release policy is unchanged."""
    auth = app.state.auth
    if (auth.mode != "replay" or auth.rehearsal or auth.tenant != "bears" or auth.services
            or auth.source_registry is not None or app.state.public_proposal_jobs is not None
            or getattr(app.state, "native_binding", None) is not None or getattr(app.state, "workflow", None) is not None):
        raise ValueError(DENIED)
    policy = ExceptionPolicy(directory, grant_path)
    with _lock():
        proposal, state = policy.validate()
        if (auth.path != policy.directory / "workspace.db" or auth.origin != proposal.origin
                or policy.metadata["subject"] != proposal.reviewer):
            raise ValueError(DENIED)
        if not any(row["event"] == "ACCEPTED" for row in _events(proposal.grant_id)):
            _event(proposal.grant_id, "ACCEPTED", {"proposal_sha256": proposal_digest(proposal.model_dump()),
                   "history_sha256": fingerprint(state["audit"]), "revision": state["revision"]})
    app.state.local_review_exception = policy
    auth.approvals_enabled = True
    auth.local_gate = policy.ready
    app.add_middleware(ExceptionMiddleware, policy=policy, authority=auth)
    return policy


class ExceptionMiddleware:
    def __init__(self, app, *, policy, authority):
        self.app, self.policy, self.authority = app, policy, authority

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD"}:
            return await self.app(scope, receive, send)
        started = False
        async def guarded_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)
        try:
            async with self.policy.async_lock:
                with _lock():
                    await self._guarded(scope, receive, guarded_send)
        except (*ERRORS, HTTPException):
            if started:
                raise RuntimeError("Local review audit completion failed; refresh before continuing") from None
            await JSONResponse({"detail": DENIED}, status_code=403)(scope, receive, send)

    async def _guarded(self, scope, receive, send):
        proposal, state = self.policy.validate()
        raw_path = scope.get("raw_path", b"")
        if (scope["method"] != "POST" or scope.get("query_string") or not raw_path.isascii()
                or raw_path.decode() != scope["path"] or b"%" in raw_path):
            raise ValueError(DENIED)
        path = scope["path"]
        allowed_auth = {"/api/auth/challenge", "/api/auth/login", "/api/auth/logout"}
        offered = {PREFIX + row["id"]: row["operation"] for row in state["actions"]
                   if row["operation"] in OPERATIONS}
        if path not in allowed_auth and path not in offered:
            raise ValueError(DENIED)
        headers = scope.get("headers", [])
        if len({key.lower() for key, _ in headers}) != len(headers):
            raise ValueError(DENIED)
        header_map = {key.lower(): value for key, value in headers}
        if any(name in header_map for name in (b"transfer-encoding", b"x-http-method-override", b"x-method-override", b"x-http-method", b"x-method")):
            raise ValueError(DENIED)
        length = header_map.get(b"content-length", b"")
        if (not length.isdigit() or len(length) > 4 or length != str(int(length)).encode()
                or int(length) > 4096 or header_map.get(b"origin") != proposal.origin.encode()
                or header_map.get(b"content-type", b"").split(b";")[0] != b"application/json"):
            raise ValueError(DENIED)
        body = bytearray()
        while True:
            chunk = await receive()
            if chunk["type"] != "http.request":
                raise ValueError(DENIED)
            body.extend(chunk.get("body", b""))
            if len(body) > 4096:
                raise ValueError(DENIED)
            if not chunk.get("more_body", False):
                break
        body = bytes(body)
        if len(body) != int(length):
            raise ValueError(DENIED)
        data = strict_json(body)
        if path == "/api/auth/challenge":
            if (not isinstance(data, dict) or set(data) != {"subject", "path", "body_sha256"}
                    or data["subject"] != proposal.reviewer):
                raise ValueError(DENIED)
            if data["path"] == "/api/auth/login":
                if data["body_sha256"] != "":
                    raise ValueError(DENIED)
            elif data["path"] not in offered or data["body_sha256"] != EMPTY_SHA:
                raise ValueError(DENIED)
        elif path == "/api/auth/login":
            if not isinstance(data, dict) or set(data) != {"challenge", "proof"}:
                raise ValueError(DENIED)
            challenge = self.authority.challenges.get(data["challenge"])
            if challenge is None or challenge.subject != proposal.reviewer or challenge.path != path:
                raise ValueError(DENIED)
        else:
            if body != b"{}":
                raise ValueError(DENIED)
            principal = self.authority.actor(Request(scope))
            if principal.subject != proposal.reviewer or principal.tenant != proposal.tenant:
                raise ValueError(DENIED)
        async def replay():
            return {"type": "http.request", "body": body, "more_body": False}
        status, response_bytes = None, 0
        response = []
        async def capture(message):
            nonlocal status, response_bytes
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                response_bytes += len(message.get("body", b""))
                if response_bytes > 2 * 1024 * 1024:
                    raise ValueError(DENIED)
            else:
                raise ValueError(DENIED)
            response.append(message)
        try:
            await self.app(scope, replay, capture)
        finally:
            if path in offered:
                _, after = _current(self.policy.directory, self.policy.metadata)
                changed = after["audit"] != state["audit"]
                _event(proposal.grant_id, "REQUEST", {"operation": offered[path], "status": status,
                       "body_sha256": EMPTY_SHA, "changed": changed})
                if changed:
                    _event(proposal.grant_id, "ACTION", {"operation": offered[path], "revision": after["revision"],
                           "history_sha256": fingerprint(after["audit"]), "status": status})
                    if offered[path] == "rollback":
                        _event(proposal.grant_id, "COMPLETED", {"reason": "Rollback ends this permission"})
        # Do not announce completion until its separate authority audit commits.
        for message in response:
            await send(message)
