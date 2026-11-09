"""Consistent workspace backups and fenced restoration for the local deployment.

A backup is a new owner-only directory with a SQLite online-backup copy of one
workspace database and a manifest: its tenant/mode binding, schema version,
integrity result and a digest of every table. It never contains credential
files, private keys, session tokens or host authority stores. Those stay with
their custodians and are listed as external dependencies.

Restoration writes a new database only and never overwrites. It verifies the
copy against the manifest, then applies an authority-reducing fence:

* every unused reviewer mandate in the snapshot is revoked, so an older copy
  cannot resurrect single-use authority that may have been consumed later;
* when the operator supplies the previous database of the same workspace,
  its issuer, mandate and price-evidence revocations are carried forward;
* native preparation stays refused until an
  operator acknowledges reconciliation of external effects since the backup.

The manifest is a checksum record, not an authenticated signature: it detects
accidental or partial alteration, not an administrator who rewrites both.

Financial and case history are not rewritten. Installation revocations live in
the host store (installation_revocation) and apply to restored copies as well.
The native outbox is a separate file and is not restored by this module.
"""
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from .storage import _read_versions

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "uptime-workspace-backup/1"
RESTORE_SCHEMA = "uptime-workspace-restore/1"
DATABASE = "workspace.sqlite"
MANIFEST = "manifest.json"
EXTERNAL = (
    "Ramp client credential file (operator custody; never copied)",
    "reviewer and mandate-issuer private keys (holder custody; never copied)",
    "source, native, award-office and proposal configuration files (operator custody)",
    "host installation-revocation and local-review authority stores (outside the workspace)",
    "native outbox database next to the native configuration (separate file)",
    "in-memory sessions and challenges (invalidated by every restart)",
)
# Authority-reducing columns that a restore may carry forward. Never the reverse.
REVOCATIONS = (
    ("mandate_issuer", "subject"),
    ("reviewer_mandate", "id"),
    ("price_finance_key", "subject"),
    ("price_signed_package", "id"),
)


class RecoveryError(ValueError):
    pass


def _now(now=None):
    return (now or datetime.now(UTC)).astimezone(UTC).isoformat()


def _outside_repositories(path):
    path = Path(path)
    if not path.is_absolute() or path != path.resolve():
        raise RecoveryError("Use an absolute path without symlinks or traversal")
    if path.is_relative_to(ROOT) or any((parent / ".git").exists() for parent in path.parents):
        raise RecoveryError("Keep workspace backups outside repositories")
    parent = path.parent.stat()
    if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o022:
        raise RecoveryError("Use an operator-owned parent directory that others cannot write")
    return path


def _absent(path):
    for candidate in (path, *(Path(str(path) + s) for s in ("-wal", "-shm", "-journal"))):
        if candidate.exists() or candidate.is_symlink():
            raise RecoveryError("Restoration never overwrites an existing database")


def _private_new_file(path):
    os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600))


def _connect(path, *, readonly=False):
    db = (sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10) if readonly
          else sqlite3.connect(path, timeout=10))
    db.row_factory = sqlite3.Row
    return db


def _cell(value):
    if isinstance(value, bytes):
        return {"b": value.hex()}
    if isinstance(value, float):
        return {"f": value.hex()}
    return value


def table_digests(db):
    """Order-independent of physical layout; every column of every table."""
    result = {}
    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for name in names:
        quoted = '"' + name.replace('"', '""') + '"'
        columns = [r[1] for r in db.execute(f"PRAGMA table_info({quoted})")]
        order = ",".join(str(i) for i in range(1, len(columns) + 1))
        digest, rows = sha256(json.dumps(columns).encode()), 0
        for row in db.execute(f"SELECT * FROM {quoted} ORDER BY {order}"):
            digest.update(json.dumps([_cell(v) for v in row], separators=(",", ":")).encode() + b"\n")
            rows += 1
        result[name] = {"rows": rows, "sha256": digest.hexdigest()}
    return result


def _binding(db):
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "authority_workspace" not in tables:
        raise RecoveryError("Only a tenant-bound V4 workspace can be backed up")
    row = db.execute("SELECT mode,rehearsal,tenant FROM authority_workspace WHERE id=1").fetchone()
    if row is None:
        raise RecoveryError("Workspace binding is missing")
    realm = (db.execute("SELECT realm FROM mandate_workspace WHERE id=1").fetchone()
             if "mandate_workspace" in tables else None)
    return {"mode": row[0], "rehearsal": bool(row[1]), "tenant": row[2],
            "realm_sha256": sha256(realm[0].encode()).hexdigest() if realm else None}, tables


def _check(db, binding, tables):
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RecoveryError("Database integrity check failed")
    history = "ABSENT"
    if {"case_snapshot", "case_revision"} <= tables:
        try:
            for _ in _read_versions(db, binding["tenant"]):
                pass
        except (ValueError, KeyError, TypeError):
            raise RecoveryError("Case history failed its integrity check") from None
        history = "VERIFIED"
    return history


def _file_sha256(path):
    digest = sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy(source, target):
    """SQLite online backup into an already created private file, as one self-contained file."""
    with _connect(source) as src, _connect(target) as dst:
        src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")
    src.close()
    dst.close()


def backup(database_path, destination, *, now=None):
    source = Path(database_path)
    if not source.is_absolute() or not source.is_file() or source.is_symlink():
        raise RecoveryError("Select the existing workspace database by absolute path")
    destination = _outside_repositories(destination)
    if destination.exists() or destination.is_symlink():
        raise RecoveryError("Choose a new backup directory")
    destination.mkdir(mode=0o700)
    copy = destination / DATABASE
    _private_new_file(copy)
    _copy(source, copy)
    db = _connect(copy, readonly=True)
    try:
        binding, tables = _binding(db)
        history = _check(db, binding, tables)
        digests = table_digests(db)
        version = db.execute("PRAGMA user_version").fetchone()[0]
    finally:
        db.close()
    manifest = {"schema": SCHEMA, "created_at": _now(now), "source_name": source.name, "binding": binding,
                "user_version": version, "integrity": "ok", "case_history": history,
                "database": {"name": DATABASE, "sha256": _file_sha256(copy), "bytes": copy.stat().st_size},
                "tables": digests, "not_included": list(EXTERNAL)}
    path = destination / MANIFEST
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    return manifest


def _private(path, *, directory=False):
    info = os.lstat(path)
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    mode = 0o700 if directory else 0o600
    if (not kind(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != mode
            or (not directory and info.st_nlink != 1)):
        raise RecoveryError("Backup files must be private to the operator")


def verify(backup_directory):
    """Recheck a backup without modifying it. Returns its manifest."""
    folder = Path(backup_directory)
    if not folder.is_absolute() or folder != folder.resolve():
        raise RecoveryError("Select the backup directory by absolute path")
    try:
        _private(folder, directory=True)
        _private(folder / MANIFEST)
        _private(folder / DATABASE)
        raw = (folder / MANIFEST).read_bytes()
    except OSError:
        raise RecoveryError("Backup is incomplete or unreadable") from None
    if len(raw) > 2_000_000:
        raise RecoveryError("Backup manifest exceeds its limit")
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeError):
        raise RecoveryError("Backup manifest is invalid") from None
    try:
        if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
                or not isinstance(manifest["database"]["sha256"], str) or not isinstance(manifest["tables"], dict)
                or not isinstance(manifest["created_at"], str) or not isinstance(manifest["binding"], dict)):
            raise RecoveryError("Unsupported backup manifest")
    except (KeyError, TypeError):
        raise RecoveryError("Unsupported backup manifest") from None
    if _file_sha256(folder / DATABASE) != manifest["database"]["sha256"]:
        raise RecoveryError("Backup database does not match its manifest")
    db = _connect(folder / DATABASE, readonly=True)
    try:
        binding, tables = _binding(db)
        history = _check(db, binding, tables)
        if (binding != manifest["binding"] or history != manifest["case_history"]
                or table_digests(db) != manifest["tables"]):
            raise RecoveryError("Backup contents do not match its manifest")
    finally:
        db.close()
    return manifest


def _carry_forward(db, previous, binding):
    """Copy revocations from the previous database of the same workspace. Authority only decreases."""
    old = _connect(previous, readonly=True)
    try:
        old_binding, old_tables = _binding(old)
        if old_binding != binding:
            raise RecoveryError("The previous database belongs to a different workspace binding")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        carried = {}
        for table, key in REVOCATIONS:
            if table not in old_tables or table not in tables:
                continue
            revoked = [r[0] for r in old.execute(f"SELECT {key} FROM {table} WHERE revoked=1")]
            count = 0
            for identity in revoked:
                count += db.execute(f"UPDATE {table} SET revoked=1 WHERE {key}=? AND revoked=0", (identity,)).rowcount
            carried[table] = count
        return carried
    finally:
        old.close()


RECONCILE = "Restored workspace: reconcile external effects since {since} and acknowledge it before native actions"
OPERATOR = re.compile(r"[a-z][a-z0-9_.-]{1,63}")


def _restore_schema(db):
    """One row per restore: the restore epoch. Reconciliation is a separate, one-time acknowledgement."""
    db.execute("""CREATE TABLE IF NOT EXISTS operations_restore (
        sequence INTEGER PRIMARY KEY, backup_sha256 TEXT NOT NULL, backup_created_at TEXT NOT NULL,
        restored_at TEXT NOT NULL, fenced_mandates INTEGER NOT NULL, revocations_carried TEXT,
        reconciled_at TEXT, reconciled_by TEXT, reconciliation_note TEXT)""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS operations_restore_no_delete BEFORE DELETE ON operations_restore
        BEGIN SELECT RAISE(ABORT,'restore epoch is immutable'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS operations_restore_once BEFORE UPDATE ON operations_restore
        WHEN OLD.reconciled_at IS NOT NULL OR NEW.backup_sha256 != OLD.backup_sha256
          OR NEW.backup_created_at != OLD.backup_created_at OR NEW.restored_at != OLD.restored_at
          OR NEW.fenced_mandates != OLD.fenced_mandates OR NEW.revocations_carried IS NOT OLD.revocations_carried
        BEGIN SELECT RAISE(ABORT,'restore epoch is immutable'); END""")


def pending_reconciliation(db):
    """The earliest unacknowledged restore point in an open connection, or None."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='operations_restore'").fetchone():
        return None
    row = db.execute("SELECT min(backup_created_at) FROM operations_restore WHERE reconciled_at IS NULL").fetchone()
    return row[0] if row else None


def require_reconciled(db):
    since = pending_reconciliation(db)
    if since is not None:
        raise PermissionError(RECONCILE.format(since=since))


def acknowledge_reconciliation(path, operator, note, *, now=None):
    """Operator attests that Ramp threads and vendor channels were reconciled since each restore point."""
    if not isinstance(operator, str) or not OPERATOR.fullmatch(operator):
        raise RecoveryError("Name the operator account that reconciled the external effects")
    if not isinstance(note, str) or not 1 <= len(note) <= 500 or any(ord(c) < 32 for c in note):
        raise RecoveryError("A short single-line reconciliation note is required")
    db = _connect(path)
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            if pending_reconciliation(db) is None:
                raise RecoveryError("No restored epoch is awaiting reconciliation")
            at = _now(now)
            count = db.execute("UPDATE operations_restore SET reconciled_at=?,reconciled_by=?,reconciliation_note=? "
                               "WHERE reconciled_at IS NULL", (at, operator, note)).rowcount
    finally:
        db.close()
    return {"reconciled_at": at, "reconciled_by": operator, "restore_epochs": count}


def restore(backup_directory, target, *, tenant, mode, previous=None, now=None):
    """Create a new fenced workspace database from a verified backup."""
    manifest = verify(backup_directory)
    binding = manifest["binding"]
    if (binding["tenant"], binding["mode"]) != (tenant, mode):
        raise RecoveryError("Backup belongs to a different tenant or execution mode")
    target = _outside_repositories(target)
    _absent(target)
    staging = target.with_name("." + target.name + ".restoring")
    _absent(staging)
    _private_new_file(staging)
    try:
        _copy(Path(backup_directory) / DATABASE, staging)
        db = _connect(staging)
        try:
            if table_digests(db) != manifest["tables"]:
                raise RecoveryError("Restored copy does not match the verified backup")
            restored_at = _now(now)
            with db:
                db.execute("BEGIN IMMEDIATE")
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                fenced = 0
                if "reviewer_mandate" in tables:
                    fenced = db.execute("UPDATE reviewer_mandate SET revoked=1 WHERE used=0 AND revoked=0").rowcount
                carried = _carry_forward(db, previous, binding) if previous is not None else None
                _restore_schema(db)
                db.execute("INSERT INTO operations_restore(backup_sha256,backup_created_at,restored_at,fenced_mandates,"
                           "revocations_carried) VALUES(?,?,?,?,?)",
                           (manifest["database"]["sha256"], manifest["created_at"], restored_at, fenced,
                            None if carried is None else json.dumps(carried, sort_keys=True)))
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RecoveryError("Restored database failed its integrity check")
        finally:
            db.close()
        os.link(staging, target)  # Fails rather than replacing a database created meanwhile.
    finally:
        staging.unlink(missing_ok=True)
    os.chmod(target, 0o600)
    return {"schema": RESTORE_SCHEMA, "restored_at": restored_at, "target_name": target.name,
            "backup_sha256": manifest["database"]["sha256"], "backup_created_at": manifest["created_at"],
            "binding": binding, "fenced_unused_mandates": fenced,
            "revocations_carried_forward": carried,
            "reconcile_external_effects_since": manifest["created_at"],
            "native_actions": "BLOCKED_UNTIL_RECONCILED",
            "required_next_steps": [
                "Reconcile any Ramp comment or vendor submission made after the backup time against the provider before a new action.",
                "Record that reconciliation with `workspace_recovery.py acknowledge`; native preparation stays refused until then.",
                "Re-apply any revocation made after the backup unless the previous database was supplied.",
                "Launch with the same tenant and mode; sessions must sign in again."]}
