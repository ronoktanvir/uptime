"""Read-only operator health report for one local workspace.

Nothing here contacts Ramp, a model provider or a vendor, retries work or
changes a database. Findings name what an operator must reconcile:

* retryable reads (a stale or interrupted Ramp capture) are fixed by rerunning
  the idempotent refresh, a bounded number of times;
* operations whose external effect is unknown (an UNCERTAIN or DISPATCHING
  outbox entry, an UNCERTAIN model job) are never retried automatically and
  must be reconciled against the provider first.

Configuration files are checked for custody (owner, mode, links) without being
read, so no credential content enters the report.
"""
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
import stat

from . import installation_revocation
from .storage import _read_versions
from .workspace_recovery import pending_reconciliation

SCHEMA = "uptime-operations-health/1"
ROOT = Path(__file__).resolve().parents[1]
# The vendor and correspondence model queues share this durable table.
JOB_TABLES = ("public_proposal_jobs",)
ACTIONABLE_OUTCOMES = {"ELIGIBLE", "INSUFFICIENT_EVIDENCE"}


def _instant(value):
    try:
        at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at.astimezone(UTC) if at.tzinfo else None


def _readonly(path):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def _tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def config_custody(path):
    """Owner-only, single-link regular file outside repositories. Contents are never read."""
    path = Path(path)
    try:
        info = os.lstat(path)
        parent = os.stat(path.parent)
    except OSError:
        return "MISSING"
    if path.is_relative_to(ROOT) or any((p / ".git").exists() for p in path.parents):
        return "INSIDE_REPOSITORY"
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077
            or info.st_nlink != 1 or parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o022):
        return "UNSAFE_CUSTODY"
    return "PROTECTED"


def check(db_path, *, now=None, stale_after=timedelta(hours=24), deadline_window=timedelta(days=7),
          outbox=None, config_files=()):
    now = (now or datetime.now(UTC)).astimezone(UTC)
    findings = []

    def note(level, code, detail, **extra):
        findings.append(dict(level=level, code=code, detail=detail, **extra))

    report = {"schema": SCHEMA, "checked_at": now.isoformat(), "database": Path(db_path).name,
              "provider_requests": 0, "writes": 0}
    db = _readonly(db_path)
    try:
        tables = _tables(db)
        report["integrity"] = db.execute("PRAGMA quick_check").fetchone()[0]
        if report["integrity"] != "ok":
            note("ATTENTION", "DATABASE_INTEGRITY", "SQLite quick_check failed; restore from a verified backup.")
        if "authority_workspace" not in tables:
            note("ATTENTION", "UNBOUND_WORKSPACE", "No tenant binding; this is not a V4 workspace.")
            return _finish(report, findings)
        mode, rehearsal, tenant = db.execute("SELECT mode,rehearsal,tenant FROM authority_workspace WHERE id=1").fetchone()
        report["binding"] = {"tenant": tenant, "mode": mode, "rehearsal": bool(rehearsal)}

        cases = {}
        if {"case_snapshot", "case_revision"} <= tables:
            try:
                for row in _read_versions(db, tenant):
                    cases[row["case_id"]] = row["payload"]
                report["case_history"] = "VERIFIED"
            except (ValueError, KeyError, TypeError):
                report["case_history"] = "FAILED"
                note("ATTENTION", "CASE_HISTORY_INTEGRITY", "Case revision chain failed verification.")

        if "native_capture" in tables:
            latest = db.execute("SELECT observed_at FROM native_capture WHERE tenant=? AND status='ready' "
                                "ORDER BY observed_at DESC LIMIT 1", (tenant,)).fetchone()
            pending = db.execute("SELECT count(*) FROM native_capture WHERE tenant=? AND status='pending'",
                                 (tenant,)).fetchone()[0]
            if latest is None:
                note("INFO", "NO_RAMP_CAPTURE", "No operator-imported Ramp capture is installed.")
            else:
                age = now - _instant(latest[0])
                report["ramp_capture"] = {"observed_at": latest[0], "age_hours": round(age.total_seconds() / 3600, 2)}
                if mode == "sandbox" and age > stale_after:
                    note("ATTENTION", "RAMP_CAPTURE_STALE",
                         "Latest Ramp capture is older than the freshness limit; rerun the read-only refresh.",
                         retryable_read=True)
            if pending:
                note("ATTENTION", "RAMP_IMPORT_INTERRUPTED",
                     "An import stopped before publication; rerunning the same refresh resumes it.",
                     count=pending, retryable_read=True)

        business = None
        if "native_installation" in tables:
            row = db.execute("SELECT business_id FROM native_installation WHERE tenant=?", (tenant,)).fetchone()
            business = row[0] if row else None
        if business:
            try:
                revoked = installation_revocation.status(tenant, business)
                local = installation_revocation.workspace_revoked(db_path, tenant, business)
                if revoked is None and local is not None:
                    revoked = {"revoked_at": local}
                    note("ATTENTION", "REVOCATION_HOST_RECORD_MISSING",
                         "The workspace records a revocation the host store lacks; access stays refused.")
                report["installation"] = {"business_id": business, "state": "REVOKED" if revoked else "ACTIVE"}
                if revoked:
                    note("INFO", "INSTALLATION_REVOKED", "Provider imports and native actions are refused.",
                         revoked_at=revoked["revoked_at"])
            except PermissionError:
                report["installation"] = {"business_id": business, "state": "UNKNOWN"}
                note("ATTENTION", "REVOCATION_STORE_UNSAFE", installation_revocation.UNSAFE)

        for table in JOB_TABLES:
            if table not in tables:
                continue
            counts = dict(db.execute(f"SELECT status,count(*) FROM {table} GROUP BY status").fetchall())
            report.setdefault("jobs", {})[table] = counts
            if counts.get("UNCERTAIN"):
                note("ATTENTION", "MODEL_JOB_OUTCOME_UNKNOWN",
                     "A model job may have run; inspect its receipt. Uptime never retries it automatically.",
                     table=table, count=counts["UNCERTAIN"], retryable_read=False)

        if "reviewer_mandate" in tables:
            report["unused_mandates"] = db.execute(
                "SELECT count(*) FROM reviewer_mandate WHERE used=0 AND revoked=0").fetchone()[0]
        if "operations_restore" in tables:
            last = db.execute("SELECT backup_created_at,restored_at,fenced_mandates,reconciled_at FROM operations_restore "
                              "ORDER BY sequence DESC LIMIT 1").fetchone()
            report["restored"] = dict(last)
            since = pending_reconciliation(db)
            if since is not None:
                note("ATTENTION", "RESTORE_RECONCILIATION_PENDING",
                     "Native actions are refused until external effects since the backup are reconciled.",
                     reconcile_since=since)

        due = []
        for case_id, payload in cases.items():
            cutoff = payload.get("claim_cutoff_exclusive") or payload.get("claim_cutoff")
            at = _instant(cutoff) if cutoff else None
            if at is None or payload.get("outcome") not in ACTIONABLE_OUTCOMES:
                continue
            if now <= at < now + deadline_window:
                due.append({"case_id": case_id, "claim_cutoff": cutoff, "outcome": payload.get("outcome"),
                            "stage": payload.get("stage")})
        if due:
            note("ATTENTION", "CLAIM_DEADLINE_APPROACHING",
                 "Claim cutoffs fall inside the alert window; missing evidence stays missing, not ineligible.",
                 cases=sorted(due, key=lambda c: c["claim_cutoff"]))
    finally:
        db.close()

    if outbox is not None:
        _outbox(Path(outbox), report, note)
    if config_files:
        report["configuration"] = [{"path": str(p), "custody": config_custody(p)} for p in config_files]
        for item in report["configuration"]:
            if item["custody"] != "PROTECTED":
                note("ATTENTION", "CONFIGURATION_CUSTODY", f"{item['path']}: {item['custody']}")
    return _finish(report, findings)


def _outbox(path, report, note):
    if not path.is_file():
        note("ATTENTION", "OUTBOX_MISSING", "Configured native outbox is unavailable; reconcile before any native action.")
        return
    db = _readonly(path)
    try:
        tables = _tables(db)
        if "rw_outbox" in tables:
            counts = dict(db.execute("SELECT status,count(*) FROM rw_outbox GROUP BY status").fetchall())
            report["outbox"] = counts
            unknown = sum(counts.get(s, 0) for s in ("UNCERTAIN", "DISPATCHING"))
            if unknown:
                note("ATTENTION", "EXTERNAL_EFFECT_UNCERTAIN",
                     "A native delivery may have happened; reconcile against the same Ramp thread. Never resend.",
                     count=unknown, retryable_read=False)
        if "rw_deployment" in tables:
            states = dict(db.execute("SELECT status,count(*) FROM rw_deployment GROUP BY status").fetchall())
            report["webhooks"] = states
            if states.get("quarantined"):
                note("ATTENTION", "WEBHOOK_QUARANTINED",
                     "A conflicting event ID quarantined a subscription; provision a separate deployment after review.")
    finally:
        db.close()


def _finish(report, findings):
    report["findings"] = findings
    report["status"] = "ATTENTION" if any(f["level"] == "ATTENTION" for f in findings) else "OK"
    return report


def render(report):
    return json.dumps(report, indent=2, sort_keys=True)
