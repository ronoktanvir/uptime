"""Operator revocation of a Ramp installation, kept outside the workspace.

A revocation is a terminal, owner-only host record keyed by tenant and Ramp
business. Because it lives outside the workspace database, restoring an older
workspace snapshot cannot bring back a revoked installation. The store never
contains credentials or tokens. An unsafe store fails closed.

Revocation stops new provider imports and native actions for that business.
Recorded history stays readable. Disabling the Ramp developer app or rotating
its client secret is a separate action the Ramp administrator performs in Ramp.
"""
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat

from .storage import database

REVOCATION_ROOT = Path.home() / ".config/uptime/installation-revocations"
SCHEMA = "uptime-installation-revocation/1"
REVOKED = "This Ramp installation was revoked by the operator; reinstall in a new workspace"
UNSAFE = "Installation revocation store is unsafe or unreadable; provider access stays disabled"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# The exact workspace tenant domain (correspondence_types.Id); never normalized.
TENANT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}")
MAX_BYTES = 4096


def _identity(tenant, business_id):
    if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
        raise ValueError("Invalid tenant identifier")
    if not isinstance(business_id, str) or not UUID.fullmatch(business_id):
        raise ValueError("Invalid Ramp business identifier")
    return sha256(f"{tenant}\n{business_id}".encode()).hexdigest()


def _root(*, create=False):
    root = REVOCATION_ROOT
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not root.exists() and not root.is_symlink():
        return None
    try:
        info = os.lstat(root)
    except OSError:
        raise PermissionError(UNSAFE) from None
    if (not stat.S_ISDIR(info.st_mode) or root.resolve() != root or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise PermissionError(UNSAFE)
    return root


def _read(path, tenant, business_id):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        raise PermissionError(UNSAFE) from None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise PermissionError(UNSAFE)
        raw = handle.read(MAX_BYTES + 1)
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeError):
        raise PermissionError(UNSAFE) from None
    if (len(raw) > MAX_BYTES or not isinstance(record, dict)
            or set(record) != {"schema", "tenant", "business_id", "revoked_at", "reason"}
            or record["schema"] != SCHEMA or record["tenant"] != tenant or record["business_id"] != business_id):
        raise PermissionError(UNSAFE)
    return record


def status(tenant, business_id):
    """Return the revocation record, or None while the installation remains active."""
    name = _identity(tenant, business_id) + ".json"
    root = _root()
    if root is None:
        return None
    return _read(root / name, tenant, business_id)


def workspace_revoked(path, tenant, business_id):
    """The workspace's own immutable REVOKED event, read independently of the host store."""
    if path is None or not Path(path).is_file():
        return None
    with database(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='native_installation_event'").fetchone():
            return None
        row = db.execute("SELECT at FROM native_installation_event WHERE tenant=? AND business_id=? AND event='REVOKED'",
                         (tenant, business_id)).fetchone()
    return row[0] if row else None


def require_active(tenant, business_id, *, path=None):
    """Refuse when either the host store or the workspace records a revocation.

    A host store deleted after revocation therefore cannot re-enable a current
    workspace. An administrator who replaces both remains a trusted actor.
    """
    if status(tenant, business_id) is not None or workspace_revoked(path, tenant, business_id) is not None:
        raise PermissionError(REVOKED)


def revoke(tenant, business_id, *, reason, now=None):
    """Record a terminal revocation. Repeating it returns the original record."""
    if not isinstance(reason, str) or not 1 <= len(reason) <= 300 or any(ord(c) < 32 for c in reason):
        raise ValueError("A short single-line revocation reason is required")
    name = _identity(tenant, business_id) + ".json"
    root = _root(create=True)
    at = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
    record = {"schema": SCHEMA, "tenant": tenant, "business_id": business_id, "revoked_at": at, "reason": reason}
    try:
        fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        return _read(root / name, tenant, business_id) | {"duplicate": True}
    with os.fdopen(fd, "wb") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    return record | {"duplicate": False}


def installed_business(path, tenant):
    """The business already bound to this workspace tenant, without contacting Ramp."""
    if not Path(path).is_file():
        return None
    with database(path) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "native_installation" not in tables:
            return None
        row = db.execute("SELECT business_id FROM native_installation WHERE tenant=?", (tenant,)).fetchone()
    return row[0] if row else None


def require_workspace_active(path, tenant):
    """Refuse before any provider request when this workspace's installation was revoked."""
    business = installed_business(path, tenant)
    if business is not None:
        require_active(tenant, business, path=path)
    return business


def record_workspace_event(path, tenant, business_id, record):
    """Append an audit row inside the workspace. The host record remains authoritative."""
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS native_installation_event (
            sequence INTEGER PRIMARY KEY, tenant TEXT NOT NULL, business_id TEXT NOT NULL,
            event TEXT NOT NULL CHECK(event='REVOKED'), at TEXT NOT NULL, reason TEXT NOT NULL,
            UNIQUE(tenant,business_id,event))""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS native_installation_event_no_update
            BEFORE UPDATE ON native_installation_event BEGIN SELECT RAISE(ABORT,'installation event is immutable'); END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS native_installation_event_no_delete
            BEFORE DELETE ON native_installation_event BEGIN SELECT RAISE(ABORT,'installation event is immutable'); END""")
        db.execute("INSERT OR IGNORE INTO native_installation_event(tenant,business_id,event,at,reason) VALUES(?,?,?,?,?)",
                   (tenant, business_id, "REVOKED", record["revoked_at"], record["reason"]))
