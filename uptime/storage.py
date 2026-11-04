"""SQLite persistence for immutable case evaluations, sessions and reconciliation events."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .contracts import Principal, fingerprint


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def database(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys = ON")
        yield db
    finally:
        db.close()


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with database(path) as db:
        db.execute("PRAGMA journal_mode = WAL")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            raise ValueError("unrecognized Uptime schema version")
        db.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS case_snapshot (
            tenant TEXT NOT NULL, case_id TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY (tenant,case_id)
        );
        CREATE TABLE IF NOT EXISTS session (
            digest TEXT PRIMARY KEY, tenant TEXT NOT NULL, subject TEXT NOT NULL,
            role TEXT NOT NULL, expires REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settlement_event (
            sequence INTEGER PRIMARY KEY, tenant TEXT NOT NULL, case_id TEXT NOT NULL, action TEXT NOT NULL,
            stage TEXT NOT NULL, actor TEXT NOT NULL, awarded TEXT NOT NULL, at TEXT NOT NULL,
            UNIQUE(tenant,case_id,action)
        );
        PRAGMA user_version = 1;
        COMMIT;
        """)


def save_cases(path, tenant, cases):
    with database(path) as db, db:
        for case in cases:
            digest = fingerprint(case)
            db.execute("INSERT OR IGNORE INTO case_snapshot VALUES (?,?,?,?)",
                       (tenant, case["id"], digest, json.dumps(case, allow_nan=False)))


def stored_cases(path, tenant):
    with database(path) as db:
        rows = db.execute("SELECT payload,digest FROM case_snapshot WHERE tenant=? ORDER BY case_id", (tenant,))
        result = []
        for row in rows:
            payload = json.loads(row["payload"])
            if fingerprint(payload) != row["digest"]:
                raise ValueError("case snapshot failed its integrity check")
            result.append(payload)
        return result


def add_session(path, token, principal: Principal, expires):
    with database(path) as db, db:
        db.execute("INSERT INTO session VALUES (?,?,?,?,?)",
                   (sha256(token.encode()).hexdigest(), principal.tenant, principal.subject, principal.role, expires))


def lookup_session(path, token, timestamp):
    if not token or len(token) > 200:
        return None
    with database(path) as db:
        row = db.execute("SELECT tenant,subject,role FROM session WHERE digest=? AND expires>?",
                         (sha256(token.encode()).hexdigest(), timestamp)).fetchone()
        return Principal(*row) if row else None


def settlement_events(path, tenant, case_id):
    with database(path) as db:
        return [dict(row) for row in db.execute(
            "SELECT * FROM settlement_event WHERE tenant=? AND case_id=? ORDER BY sequence", (tenant,case_id))]


SETTLEMENT_ACTIONS = {
    "record-credit": (None, "POSTED", "Record simulated credit"),
    "apply-partial": ("POSTED", "PARTIALLY_APPLIED", "Apply part to a simulated bill"),
    "apply-balance": ("PARTIALLY_APPLIED", "APPLIED", "Apply the remaining simulated balance"),
}


def transition_settlement(path, principal, case_id, action, award):
    from decimal import Decimal
    if principal.role != "reviewer":
        raise PermissionError("Reviewer session required")
    total = Decimal(award)
    if not total.is_finite() or total <= 0 or total.as_tuple().exponent < -2:
        raise ValueError("a confirmed USD award in cents is required")
    required, next_stage, _ = SETTLEMENT_ACTIONS[action]
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute("SELECT stage, action, awarded FROM settlement_event WHERE tenant=? AND case_id=? ORDER BY sequence",
                          (principal.tenant, case_id)).fetchall()
        if rows and any(Decimal(r["awarded"]) != total for r in rows):
            raise ValueError("award changed after reconciliation")
        if any(r["action"] == action for r in rows):
            return
        if (rows[-1]["stage"] if rows else None) != required:
            raise ValueError("credit stage precondition failed")
        db.execute("INSERT INTO settlement_event(tenant,case_id,action,stage,actor,awarded,at) VALUES (?,?,?,?,?,?,?)",
                   (principal.tenant,case_id,action,next_stage,principal.subject,str(total),now()))
