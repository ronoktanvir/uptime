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
* native preparation and new mandate installation stay refused until an
  operator acknowledges reconciliation of external effects since the backup.

The manifest is a checksum record, not an authenticated signature: it detects
accidental or partial alteration, not an administrator who rewrites both.

Financial and case history are not rewritten. Installation revocations live in
the host store (installation_revocation) and apply to restored copies as well.
The native outbox is a separate file. It is included only when the operator
passes it. A restored outbox is fenced as agreed with the W1 owner, changing
only status and review, never the plan:

* DISPATCHING becomes UNCERTAIN (reconcile-only, never resent);
* a REVIEWED comment returns to PREPARED with its review cleared, so it needs a
  fresh signed review; W1 execution reads the thread's dedup marker first and
  records DELIVERED without posting if it was delivered after the backup;
* PREPARED and BLOCKED comments are unchanged, so a never-sent comment does not
  block its object permanently;
* every other non-settled metadata or decision action becomes UNCERTAIN, because
  metadata has no read-back and decisions are simulation-only.
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
OUTBOX = "outbox.sqlite"
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


def _outbox_facts(db, tenant):
    """Tables, installation tenant and status counts of a native outbox file; refuses anything else."""
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RecoveryError("Native outbox integrity check failed")
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"rw_outbox", "rw_installation"} <= tables:
        raise RecoveryError("The selected file is not a native outbox")
    tenants = {r[0] for r in db.execute("SELECT tenant FROM rw_installation")}
    if tenants != {tenant}:
        raise RecoveryError("The native outbox belongs to a different tenant")
    counts = dict(db.execute("SELECT status,count(*) FROM rw_outbox GROUP BY status").fetchall())
    return tables, counts


def backup(database_path, destination, *, outbox=None, now=None):
    source = Path(database_path)
    if not source.is_absolute() or not source.is_file() or source.is_symlink():
        raise RecoveryError("Select the existing workspace database by absolute path")
    if outbox is not None:
        outbox = Path(outbox)
        if not outbox.is_absolute() or not outbox.is_file() or outbox.is_symlink() or outbox.resolve() == source.resolve():
            raise RecoveryError("Select the existing native outbox by absolute path")
        with _connect(source, readonly=True) as probe:
            tenant = _binding(probe)[0]["tenant"]
        probe.close()
        candidate = _connect(outbox, readonly=True)
        try:
            _outbox_facts(candidate, tenant)
        finally:
            candidate.close()
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
                "tables": digests,
                "not_included": [item for item in EXTERNAL if outbox is None or "outbox" not in item]}
    if outbox is not None:
        saved = destination / OUTBOX
        _private_new_file(saved)
        _copy(outbox, saved)
        db = _connect(saved, readonly=True)
        try:
            _, counts = _outbox_facts(db, binding["tenant"])
            outbox_digests = table_digests(db)
        finally:
            db.close()
        manifest["outbox"] = {"name": OUTBOX, "source_name": outbox.name, "sha256": _file_sha256(saved),
                              "bytes": saved.stat().st_size, "tables": outbox_digests, "status_counts": counts}
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
    if "outbox" in manifest:
        try:
            _private(folder / OUTBOX)
            ok = _file_sha256(folder / OUTBOX) == manifest["outbox"]["sha256"]
        except (OSError, KeyError, TypeError):
            raise RecoveryError("Backup outbox is incomplete or unreadable") from None
        if not ok:
            raise RecoveryError("Backup outbox does not match its manifest")
        db = _connect(folder / OUTBOX, readonly=True)
        try:
            if table_digests(db) != manifest["outbox"]["tables"]:
                raise RecoveryError("Backup outbox contents do not match its manifest")
        finally:
            db.close()
    elif (folder / OUTBOX).exists() or (folder / OUTBOX).is_symlink():
        raise RecoveryError("Backup contains an outbox its manifest does not describe")
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


RECONCILE = "Restored workspace: reconcile external effects since {since} and acknowledge it before native actions or new mandates"
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


def _stage_outbox(manifest, backup_directory, target, staging, previous_outbox, tenant):
    _copy(Path(backup_directory) / OUTBOX, staging)
    db = _connect(staging)
    try:
        if table_digests(db) != manifest["outbox"]["tables"]:
            raise RecoveryError("Restored outbox does not match the verified backup")
        quarantined = []
        if previous_outbox is not None:
            old = _connect(previous_outbox, readonly=True)
            try:
                old_tables, _ = _outbox_facts(old, tenant)
                if "rw_deployment" in old_tables:
                    quarantined = [r[0] for r in old.execute("SELECT id FROM rw_deployment WHERE status='quarantined'")]
            finally:
                old.close()
        with db:
            db.execute("BEGIN IMMEDIATE")
            tables, _ = _outbox_facts(db, tenant)
            reviews_cleared = db.execute(
                "UPDATE rw_outbox SET status='PREPARED',review=NULL "
                "WHERE status='REVIEWED' AND json_extract(plan,'$.kind')='comment'").rowcount
            uncertain = db.execute("UPDATE rw_outbox SET status='UNCERTAIN' WHERE status='DISPATCHING'").rowcount
            uncertain += db.execute(
                "UPDATE rw_outbox SET status='UNCERTAIN' WHERE status NOT IN ('DELIVERED','UNCERTAIN') "
                "AND json_extract(plan,'$.kind') IS NOT 'comment'").rowcount
            carried = 0
            if "rw_deployment" in tables:
                for identity in quarantined:
                    carried += db.execute("UPDATE rw_deployment SET status='quarantined' WHERE id=? AND status!='quarantined'",
                                          (identity,)).rowcount
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RecoveryError("Restored outbox failed its integrity check")
    finally:
        db.close()
    return {"target_name": target.name, "marked_uncertain": uncertain, "comment_reviews_cleared": reviews_cleared,
            "quarantine_carried_forward": carried if previous_outbox is not None else None}


def restore(backup_directory, target, *, tenant, mode, previous=None, outbox_target=None, previous_outbox=None,
            now=None):
    """Create a new fenced workspace database (and optionally its native outbox) from a verified backup."""
    manifest = verify(backup_directory)
    binding = manifest["binding"]
    if (binding["tenant"], binding["mode"]) != (tenant, mode):
        raise RecoveryError("Backup belongs to a different tenant or execution mode")
    if previous_outbox is not None and outbox_target is None:
        raise RecoveryError("A previous outbox only applies when restoring the outbox")
    if outbox_target is not None and "outbox" not in manifest:
        raise RecoveryError("This backup does not contain a native outbox")
    target = _outside_repositories(target)
    _absent(target)
    pairs = [(target, target.with_name("." + target.name + ".restoring"))]
    if outbox_target is not None:
        outbox_target = _outside_repositories(outbox_target)
        if outbox_target == target:
            raise RecoveryError("The outbox must be a separate file from the workspace database")
        _absent(outbox_target)
        pairs.append((outbox_target, outbox_target.with_name("." + outbox_target.name + ".restoring")))
    for _, staging in pairs:
        _absent(staging)
    created = []
    try:
        for _, staging in pairs:
            _private_new_file(staging)
            created.append(staging)
        staging = pairs[0][1]
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
        outbox = None
        if outbox_target is not None:
            outbox = _stage_outbox(manifest, backup_directory, outbox_target, pairs[1][1], previous_outbox,
                                   binding["tenant"])
        linked = []
        try:
            for final, staging in pairs:
                os.link(staging, final)  # Fails rather than replacing a file created meanwhile.
                linked.append(final)
        except OSError:
            for final in linked:  # All or nothing: remove only what this restore just created.
                final.unlink(missing_ok=True)
            raise RecoveryError("A restore target appeared during restoration; nothing was restored") from None
    finally:
        for staging in created:
            staging.unlink(missing_ok=True)
    for final, _ in pairs:
        os.chmod(final, 0o600)
    return {"schema": RESTORE_SCHEMA, "restored_at": restored_at, "target_name": target.name,
            "backup_sha256": manifest["database"]["sha256"], "backup_created_at": manifest["created_at"],
            "binding": binding, "fenced_unused_mandates": fenced,
            "revocations_carried_forward": carried, "outbox": outbox,
            "reconcile_external_effects_since": manifest["created_at"],
            "native_actions": "BLOCKED_UNTIL_RECONCILED", "new_mandates": "BLOCKED_UNTIL_RECONCILED",
            "required_next_steps": [
                "Reconcile any Ramp comment or vendor submission made after the backup time against the provider before a new action.",
                "Record that reconciliation with `workspace_recovery.py acknowledge`; native preparation and new mandates stay refused until then.",
                "Re-apply any revocation made after the backup unless the previous database was supplied.",
                "Settle each UNCERTAIN native outbox action with the exact Ramp read-back; it is never resent. "
                "Restored comments that were reviewed need a fresh signed review.",
                "Launch with the same tenant and mode; sessions must sign in again."]}
