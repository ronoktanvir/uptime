"""Append-only audit of out-of-scope refusals from verified signed sources.

``record_verified_source_refusal`` is an internal hook for the root authority, not an endpoint and
not a signature verifier. Root calls it only after a request's Ed25519 proof is valid and current
and its nonce/replay check has passed, when the source grant does not cover the request. Root
still answers 403. An invalid signature, unknown sender or expired nonce never reaches this hook.

Inputs are server-side authentication context only. No raw body, proof or nonce is accepted or
stored. Each row holds bounded identifiers, the body digest, the exact claim events route, the
fixed reason ``OUT_OF_SCOPE`` and the time the first copy was received. Values are validated and
stored as given, never normalized. Rows are keyed by a stable digest of tenant, subject, key,
grant, route and body digest, so a repeated refusal keeps its first timestamp. Rows cannot be
updated or deleted.

The hook writes only ``source_refusal_audit``. It never reads or changes source, claim, evidence
or approval state, and it never associates a refusal with the claim the route names. Validation
failures raise ``ValueError`` before the database is opened. Persistence errors propagate so root
can answer with its generic 503 and still deny the request.
"""
from datetime import datetime
import re

from .contracts import fingerprint
from .source_config import CLAIM
from .source_identity import refusal as identity_refusal
from .storage import database

REASON = "OUT_OF_SCOPE"
KEY_VERSION = "source-refusal-audit/1"
ROUTE_PREFIX, ROUTE_SUFFIX = "/api/correspondence/claims/", "/events"
TENANT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}")
KEY_ID = re.compile(r"ed25519-sha256:[0-9a-f]{64}")
HEX64 = re.compile(r"[0-9a-f]{64}")
MAX_TIMESTAMP = 64

COLUMNS = ("refusal_digest", "tenant", "subject", "source_key_id", "source_grant_id",
           "request_path", "body_sha256", "reason", "received_at")

SCHEMA = (
    f"""CREATE TABLE IF NOT EXISTS source_refusal_audit (
        refusal_digest TEXT PRIMARY KEY CHECK(length(refusal_digest) = 64),
        tenant TEXT NOT NULL CHECK(length(tenant) BETWEEN 1 AND 96),
        subject TEXT NOT NULL CHECK(length(subject) BETWEEN 1 AND 96),
        source_key_id TEXT NOT NULL CHECK(length(source_key_id) = 79),
        source_grant_id TEXT NOT NULL CHECK(length(source_grant_id) = 64),
        request_path TEXT NOT NULL CHECK(length(request_path) <= 128),
        body_sha256 TEXT NOT NULL CHECK(length(body_sha256) = 64),
        reason TEXT NOT NULL CHECK(reason = '{REASON}'),
        received_at TEXT NOT NULL CHECK(length(received_at) BETWEEN 1 AND {MAX_TIMESTAMP}))""",
    """CREATE TRIGGER IF NOT EXISTS source_refusal_audit_no_update BEFORE UPDATE ON source_refusal_audit
        BEGIN SELECT RAISE(ABORT, 'source refusal audit is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS source_refusal_audit_no_delete BEFORE DELETE ON source_refusal_audit
        BEGIN SELECT RAISE(ABORT, 'source refusal audit is append-only'); END""",
)

INSERT = (f"INSERT INTO source_refusal_audit ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))}) "
          "ON CONFLICT(refusal_digest) DO NOTHING")


def _text(value):
    return type(value) is str


def _validate(tenant, subject, key_id, grant_id, request_path, body_sha256, received_at):
    if not _text(tenant) or not TENANT.fullmatch(tenant):
        raise ValueError("A bounded tenant identifier is required.")
    if not _text(subject) or identity_refusal(subject) is not None:
        raise ValueError("A bounded exact source subject is required.")
    if not _text(key_id) or not KEY_ID.fullmatch(key_id):
        raise ValueError("A source key id of the form ed25519-sha256:<64 lowercase hex> is required.")
    if not _text(grant_id) or not HEX64.fullmatch(grant_id):
        raise ValueError("A 64 lowercase hex source grant id is required.")
    if not _text(body_sha256) or not HEX64.fullmatch(body_sha256):
        raise ValueError("A 64 lowercase hex body digest is required.")
    if not (_text(request_path) and request_path.startswith(ROUTE_PREFIX) and request_path.endswith(ROUTE_SUFFIX)
            and len(request_path) > len(ROUTE_PREFIX) + len(ROUTE_SUFFIX)
            and CLAIM.fullmatch(request_path[len(ROUTE_PREFIX):-len(ROUTE_SUFFIX)])):
        raise ValueError("An exact correspondence claim events route is required.")
    if not isinstance(received_at, datetime) or received_at.utcoffset() is None:
        raise ValueError("An offset-aware received_at timestamp is required.")
    stamp = received_at.isoformat()
    if len(stamp) > MAX_TIMESTAMP:
        raise ValueError("A bounded received_at timestamp is required.")
    return stamp


def refusal_digest(*, tenant, subject, key_id, grant_id, request_path, body_sha256):
    """Stable audit key. received_at is excluded so a repeated refusal deduplicates."""
    return fingerprint([KEY_VERSION, tenant, subject, key_id, grant_id, request_path, body_sha256])


def record_verified_source_refusal(path, *, tenant, subject, key_id, grant_id, request_path, body_sha256,
                                   received_at) -> bool:
    """Append one out-of-scope refusal for a verified source. Return True when newly inserted.

    Returns False for a duplicate; the stored first ``received_at`` is kept. Raises ``ValueError``
    for invalid metadata without touching the database. Database errors propagate.
    """
    stamp = _validate(tenant, subject, key_id, grant_id, request_path, body_sha256, received_at)
    digest = refusal_digest(tenant=tenant, subject=subject, key_id=key_id, grant_id=grant_id,
                            request_path=request_path, body_sha256=body_sha256)
    with database(path) as db, db:
        # One immediate write transaction covers creation and insert, so concurrent first writers
        # serialize on the database lock and exactly one of them inserts.
        db.execute("BEGIN IMMEDIATE")
        for statement in SCHEMA:
            db.execute(statement)
        cursor = db.execute(INSERT, (digest, tenant, subject, key_id, grant_id, request_path, body_sha256,
                                     REASON, stamp))
        return cursor.rowcount == 1
