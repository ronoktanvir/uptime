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
    # Settlement has its own additive schema; unrelated V3 tables keep version 1.
    from .allocations import initialize_allocations
    initialize_allocations(path)


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
    from .allocations import (_connect, _cutoff, _demo_transition, _json,
                              canonical, initialize_allocations, usd_cents)
    if principal.role != "reviewer":
        raise PermissionError("Reviewer session required")
    total = usd_cents(award)
    if total <= 0:
        raise ValueError("a confirmed USD award in cents is required")
    required, next_stage, _ = SETTLEMENT_ACTIONS[action]
    tenant, case_id = canonical(principal.tenant), canonical(case_id)
    initialize_allocations(path)
    with _connect(path, write=True) as db:
        rows = db.execute("SELECT stage, action, awarded FROM settlement_event WHERE tenant=? AND case_id=? ORDER BY sequence",
                          (tenant, case_id)).fetchall()
        if rows and any(usd_cents(r["awarded"]) != total for r in rows):
            raise ValueError("award changed after reconciliation")
        if any(r["action"] == action for r in rows):
            return
        previous = rows[-1]["stage"] if rows else None
        # A cent has no positive proper half. Full application is the next action.
        direct_cent = total == 1 and action == "apply-balance" and previous == "POSTED"
        if previous != required and not direct_cent:
            raise ValueError("credit stage precondition failed")
        _demo_transition(db, tenant, case_id, action, total)
        cursor = db.execute("INSERT INTO settlement_event(tenant,case_id,action,stage,actor,awarded,at) VALUES (?,?,?,?,?,?,?)",
                           (tenant,case_id,action,next_stage,principal.subject,str(award),now()))
        row = db.execute("SELECT * FROM settlement_event WHERE sequence=?", (cursor.lastrowid,)).fetchone()
        # Mark V4-written events so restart never re-projects a live ledger entry.
        db.execute("INSERT INTO allocation_legacy VALUES(?,?,?,?,?)",
                   (row["sequence"],tenant,case_id,_json(dict(row)),_cutoff(db,None)))
