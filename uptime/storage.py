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
        CREATE TABLE IF NOT EXISTS case_revision (
            tenant TEXT NOT NULL, case_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=2),
            previous_digest TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL, observed_at TEXT NOT NULL,
            PRIMARY KEY (tenant, case_id, revision),
            FOREIGN KEY (tenant,case_id) REFERENCES case_snapshot(tenant,case_id)
        );
        CREATE TRIGGER IF NOT EXISTS case_revision_no_update BEFORE UPDATE ON case_revision
          BEGIN SELECT RAISE(ABORT,'case revision is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS case_revision_no_delete BEFORE DELETE ON case_revision
          BEGIN SELECT RAISE(ABORT,'case revision is immutable'); END;
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


def persist_case(db, tenant, case):
    """Append the changed evaluation in the caller's transaction; V3 snapshots remain revision 1."""
    case_id=case["id"]
    value=json.dumps(case,allow_nan=False)
    digest=fingerprint(case)
    cur=db.execute("INSERT OR IGNORE INTO case_snapshot VALUES (?,?,?,?)",(tenant,case_id,digest,value))
    if cur.rowcount:
        return 1
    head=db.execute("SELECT revision,digest FROM case_revision WHERE tenant=? AND case_id=? ORDER BY revision DESC LIMIT 1",(tenant,case_id)).fetchone()
    if head is None:
        head=(1,db.execute("SELECT digest FROM case_snapshot WHERE tenant=? AND case_id=?",(tenant,case_id)).fetchone()[0])
    if head[1]==digest:
        return head[0]
    number=head[0]+1
    db.execute("INSERT INTO case_revision VALUES (?,?,?,?,?,?,?)",(tenant,case_id,number,head[1],digest,value,now()))
    return number


def save_cases(path, tenant, cases):
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        for case in cases:
            persist_case(db,tenant,case)


def _read_versions(db, tenant, case_id=None):
    sql="""SELECT case_id,1 AS revision,NULL AS previous_digest,digest,payload,NULL AS observed_at
             FROM case_snapshot WHERE tenant=?
           UNION ALL
           SELECT case_id,revision,previous_digest,digest,payload,observed_at
             FROM case_revision WHERE tenant=?"""
    params=[tenant,tenant]
    if case_id is not None:
        sql="SELECT * FROM ("+sql+") WHERE case_id=?"
        params.append(case_id)
    last={}
    for row in db.execute(sql+" ORDER BY case_id,revision",params):
        payload=json.loads(row["payload"])
        if (fingerprint(payload)!=row["digest"] or row["previous_digest"]!=last.get(row["case_id"])
                or payload.get("id")!=row["case_id"]):
            raise ValueError("case evaluation history failed its integrity check")
        last[row["case_id"]]=row["digest"]
        yield dict(row) | {"payload":payload}


def stored_cases(path, tenant):
    with database(path) as db:
        current={r["case_id"]:r["payload"] for r in _read_versions(db,tenant)}
        return list(current.values())


def case_versions(path, tenant, case_id):
    with database(path) as db:
        rows=list(_read_versions(db,tenant,case_id))
        if not rows:
            raise KeyError(case_id)
        return rows


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
