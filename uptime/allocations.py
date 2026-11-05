"""Persistent, tenant-scoped USD allocation ledger (V4 integration contract).

Workbench integration, owned by the lead:
  * Keep storage.transition_settlement(path, principal, case_id, action, amount).
    It writes real ledger rows and the compatibility stage event atomically.
  * Replace demo_reconciliation in persisted views with
    settlement_reconciliation(path, tenant, case_id, award_amount).
  * Use settlement_actions(stage, amount) for actions; a one-cent posted credit
    goes directly to apply-balance, without a zero-valued partial application.
  * For shared bill intake instantiate AllocationLedger(path), then call
    record_award(tenant, case_id, award), record_credit(tenant, credit),
    record_bill(tenant, bill), apply(tenant, application), reconcile(tenant, id).
    All records have id, source, source_ref, amount_cents (or decimal amount),
    effective_date (ISO calendar date), and the same explicit scope:
    vendor_id, account_id, product_id, contract_id, contract_version, currency.
    Award: confirmed=True, memo_ref. Credit: award_id, memo_ref.
    Bill: eligible_cents (verified opening eligible capacity, <= total amount_cents,
    before applications recorded in this ledger; already-excluded provider uses
    must not be imported a second time). bill_balance/list_bills return the
    remaining eligible amount after all cases' allocations.
    Application: credit_id, bill_id; scope is checked when supplied and otherwise
    derived from those immutable parents. Intake is trusted server-side code,
    never a provider confirmation endpoint or permission to perform a payment.

Consequential choices for the lead's Opus review:
  * BEGIN IMMEDIATE serializes independent SQLite writers; SQL triggers enforce
    cross-award bill capacity as well as per-credit/per-award caps.
  * Scope and capacity snapshots are immutable. Unknown account/product/contract
    or an unverified eligible outstanding balance fails closed. No display-name
    matching, guessed currency conversion, negative adjustment or reversal.
  * Source references are unique across cases, not namespaced by the case.
    Native Ramp utilization is a cumulative credit/bill pair; observations apply
    only its positive delta and retain history. Decreases require review.
  * V3 settlement_event history stays intact. Its explicitly simulated balances
    migrate with LEGACY_STAGE_PROJECTION origin, never provider confirmations.
    A legacy zero partial stage remains history but creates no application.
"""
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sqlite3
import unicodedata
from uuid import UUID

from .contracts import Source

MAX_CENTS = 10**15
SCOPE_FIELDS = ("vendor_id", "account_id", "product_id", "contract_id", "contract_version", "currency")


def canonical(value, field="identifier"):
    if not isinstance(value, str):
        raise ValueError(f"Missing {field}")
    value = unicodedata.normalize("NFC", value).strip()
    if not value or len(value) > 512 or not value.isprintable():
        raise ValueError(f"Invalid {field}")
    try:
        return str(UUID(value))
    except ValueError:
        return value


def usd_cents(value):
    """Exact conversion independent of the caller's Decimal precision/rounding."""
    if not isinstance(value, (str, Decimal)):
        raise ValueError("USD amount must be decimal text")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid USD amount") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("Invalid USD amount")
    sign, digits, exponent = number.as_tuple()
    if not any(digits):
        return 0
    if len(digits) + exponent > 14 or exponent < -1000 or len(digits) > 1000:
        raise ValueError("USD amount outside supported range")
    coefficient = int("".join(map(str, digits)))
    power = exponent + 2
    if power < 0:
        coefficient, fraction = divmod(coefficient, 10 ** -power)
        if fraction:
            raise ValueError("USD amount must have whole cents")
    else:
        coefficient *= 10 ** power
    if coefficient > MAX_CENTS:
        raise ValueError("USD amount outside supported range")
    return coefficient


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def _cents(row, field="amount_cents", amount="amount", positive=True):
    value = row.get(field)
    if value is None and amount in row:
        value = usd_cents(row[amount])
    if type(value) is not int or value < int(positive) or value > MAX_CENTS:
        raise ValueError(f"{field} must be {'positive ' if positive else ''}integer USD cents")
    if amount in row and usd_cents(row[amount]) != value:
        raise ValueError(f"Conflicting {field} and {amount}")
    return value


def calendar_date(value):
    if not isinstance(value, str):
        raise ValueError("Explicit ISO calendar date required")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Explicit ISO calendar date required") from exc
    if parsed.isoformat() != value:
        raise ValueError("Canonical ISO calendar date required")
    return value


def instant(value):
    if not isinstance(value, str):
        raise ValueError("An observed instant with timezone is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid observed instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("An observed instant with timezone is required")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@contextmanager
def _connect(path, *, write=False):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield db
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise ValueError(str(exc)) from exc
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def _schema(db):
    # execute, not executescript: the caller's migration/write transaction survives.
    statements = [
        """CREATE TABLE IF NOT EXISTS allocation_meta (version INTEGER PRIMARY KEY CHECK(version=1))""",
        """INSERT OR IGNORE INTO allocation_meta VALUES(1)""",
        """CREATE TABLE IF NOT EXISTS allocation_scope (
            scope_id INTEGER PRIMARY KEY, tenant TEXT NOT NULL,
            vendor_id TEXT NOT NULL, account_id TEXT NOT NULL, product_id TEXT NOT NULL,
            contract_id TEXT NOT NULL, contract_version TEXT NOT NULL,
            currency TEXT NOT NULL CHECK(currency='USD'),
            UNIQUE(tenant,vendor_id,account_id,product_id,contract_id,contract_version,currency),
            UNIQUE(tenant,scope_id))""",
        """CREATE TABLE IF NOT EXISTS allocation_journal (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, kind TEXT NOT NULL,
            event_id TEXT NOT NULL, payload TEXT NOT NULL, recorded_at TEXT NOT NULL,
            origin TEXT NOT NULL CHECK(origin IN ('INTAKE','LEGACY_STAGE_PROJECTION')),
            UNIQUE(tenant,kind,event_id), UNIQUE(tenant,sequence))""",
        f"""CREATE TABLE IF NOT EXISTS allocation_award (
            tenant TEXT NOT NULL, id TEXT NOT NULL, scope_id INTEGER NOT NULL,
            source TEXT NOT NULL CHECK(source='SIMULATED_VENDOR'), source_ref TEXT NOT NULL,
            memo_ref TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents BETWEEN 1 AND {MAX_CENTS}),
            effective_date TEXT NOT NULL, case_id TEXT NOT NULL, sequence INTEGER NOT NULL,
            PRIMARY KEY(tenant,id), UNIQUE(tenant,source,source_ref),
            FOREIGN KEY(tenant,scope_id) REFERENCES allocation_scope(tenant,scope_id),
            FOREIGN KEY(tenant,sequence) REFERENCES allocation_journal(tenant,sequence))""",
        f"""CREATE TABLE IF NOT EXISTS allocation_credit (
            tenant TEXT NOT NULL, id TEXT NOT NULL, scope_id INTEGER NOT NULL,
            source TEXT NOT NULL CHECK(source IN ('DETERMINISTIC_REPLAY','LIVE_RAMP_SANDBOX')),
            source_ref TEXT NOT NULL, memo_ref TEXT NOT NULL, award_id TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents BETWEEN 1 AND {MAX_CENTS}),
            effective_date TEXT NOT NULL, sequence INTEGER NOT NULL,
            PRIMARY KEY(tenant,id), UNIQUE(tenant,source,source_ref),
            FOREIGN KEY(tenant,award_id) REFERENCES allocation_award(tenant,id),
            FOREIGN KEY(tenant,scope_id) REFERENCES allocation_scope(tenant,scope_id),
            FOREIGN KEY(tenant,sequence) REFERENCES allocation_journal(tenant,sequence))""",
        f"""CREATE TABLE IF NOT EXISTS allocation_bill (
            tenant TEXT NOT NULL, id TEXT NOT NULL, scope_id INTEGER NOT NULL,
            source TEXT NOT NULL CHECK(source IN ('SYNTHETIC_CUSTOMER','DETERMINISTIC_REPLAY','LIVE_RAMP_SANDBOX')),
            source_ref TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents BETWEEN 1 AND {MAX_CENTS}),
            eligible_cents INTEGER NOT NULL CHECK(typeof(eligible_cents)='integer' AND eligible_cents BETWEEN 0 AND amount_cents),
            effective_date TEXT NOT NULL, sequence INTEGER NOT NULL,
            PRIMARY KEY(tenant,id), UNIQUE(tenant,source,source_ref),
            FOREIGN KEY(tenant,scope_id) REFERENCES allocation_scope(tenant,scope_id),
            FOREIGN KEY(tenant,sequence) REFERENCES allocation_journal(tenant,sequence))""",
        f"""CREATE TABLE IF NOT EXISTS allocation_application (
            tenant TEXT NOT NULL, id TEXT NOT NULL, credit_id TEXT NOT NULL, bill_id TEXT NOT NULL,
            source TEXT NOT NULL CHECK(source IN ('DETERMINISTIC_REPLAY','LIVE_RAMP_SANDBOX')),
            source_ref TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents BETWEEN 1 AND {MAX_CENTS}),
            effective_date TEXT NOT NULL, sequence INTEGER NOT NULL,
            PRIMARY KEY(tenant,id), UNIQUE(tenant,source,source_ref),
            FOREIGN KEY(tenant,credit_id) REFERENCES allocation_credit(tenant,id),
            FOREIGN KEY(tenant,bill_id) REFERENCES allocation_bill(tenant,id),
            FOREIGN KEY(tenant,sequence) REFERENCES allocation_journal(tenant,sequence))""",
        f"""CREATE TABLE IF NOT EXISTS allocation_observation (
            tenant TEXT NOT NULL, id TEXT NOT NULL, credit_id TEXT NOT NULL, bill_id TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents BETWEEN 0 AND {MAX_CENTS}),
            observed_at TEXT NOT NULL, effective_date TEXT NOT NULL, sequence INTEGER NOT NULL,
            PRIMARY KEY(tenant,id), UNIQUE(tenant,credit_id,bill_id,observed_at),
            FOREIGN KEY(tenant,credit_id) REFERENCES allocation_credit(tenant,id),
            FOREIGN KEY(tenant,bill_id) REFERENCES allocation_bill(tenant,id),
            FOREIGN KEY(tenant,sequence) REFERENCES allocation_journal(tenant,sequence))""",
        """CREATE TABLE IF NOT EXISTS allocation_legacy (
            settlement_sequence INTEGER PRIMARY KEY, tenant TEXT NOT NULL, case_id TEXT NOT NULL,
            original_payload TEXT NOT NULL, journal_sequence INTEGER,
            FOREIGN KEY(tenant,journal_sequence) REFERENCES allocation_journal(tenant,sequence))""",
        "CREATE INDEX IF NOT EXISTS allocation_credit_award ON allocation_credit(tenant,award_id)",
        "CREATE INDEX IF NOT EXISTS allocation_application_credit ON allocation_application(tenant,credit_id,sequence)",
        "CREATE INDEX IF NOT EXISTS allocation_application_bill ON allocation_application(tenant,bill_id,sequence)",
        "CREATE INDEX IF NOT EXISTS allocation_award_case ON allocation_award(tenant,case_id)",
        """CREATE UNIQUE INDEX IF NOT EXISTS allocation_bill_canonical_source
            ON allocation_bill(tenant,(source='LIVE_RAMP_SANDBOX'),source_ref)""",
        """CREATE TRIGGER IF NOT EXISTS allocation_award_memo BEFORE INSERT ON allocation_award BEGIN
          SELECT CASE WHEN EXISTS (
            SELECT 1 FROM allocation_award a JOIN allocation_scope s ON s.scope_id=a.scope_id
            JOIN allocation_scope n ON n.scope_id=NEW.scope_id
            WHERE a.tenant=NEW.tenant AND a.source=NEW.source AND a.memo_ref=NEW.memo_ref
              AND s.vendor_id=n.vendor_id AND s.account_id=n.account_id)
            THEN RAISE(ABORT,'Duplicate vendor/account memo identity') END;
        END""",
        """CREATE TRIGGER IF NOT EXISTS allocation_credit_limits BEFORE INSERT ON allocation_credit BEGIN
          SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM allocation_award a
            WHERE a.tenant=NEW.tenant AND a.id=NEW.award_id AND a.scope_id=NEW.scope_id
              AND a.memo_ref=NEW.memo_ref AND a.effective_date<=NEW.effective_date)
            THEN RAISE(ABORT,'Credit award/memo/scope/date mismatch') END;
          SELECT CASE WHEN NEW.amount_cents >
            (SELECT amount_cents FROM allocation_award WHERE tenant=NEW.tenant AND id=NEW.award_id)
            - COALESCE((SELECT SUM(amount_cents) FROM allocation_credit WHERE tenant=NEW.tenant AND award_id=NEW.award_id),0)
            THEN RAISE(ABORT,'Posted credit exceeds award') END;
          SELECT CASE WHEN EXISTS (SELECT 1 FROM allocation_credit WHERE tenant=NEW.tenant
            AND award_id=NEW.award_id AND source<>NEW.source)
            THEN RAISE(ABORT,'Sandbox and fixture settlement records cannot be combined') END;
        END""",
        """CREATE TRIGGER IF NOT EXISTS allocation_application_limits BEFORE INSERT ON allocation_application BEGIN
          SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM allocation_credit c
            JOIN allocation_bill b ON b.tenant=c.tenant AND b.scope_id=c.scope_id
            JOIN allocation_award a ON a.tenant=c.tenant AND a.id=c.award_id
            WHERE c.tenant=NEW.tenant AND c.id=NEW.credit_id AND b.id=NEW.bill_id
              AND c.source=NEW.source
              AND (c.source='LIVE_RAMP_SANDBOX')=(b.source='LIVE_RAMP_SANDBOX')
              AND b.effective_date>=a.effective_date AND b.effective_date>=c.effective_date
              AND NEW.effective_date>=b.effective_date AND NEW.effective_date>=c.effective_date)
            THEN RAISE(ABORT,'Application scope/source/date mismatch or predating bill') END;
          SELECT CASE WHEN NEW.amount_cents >
            (SELECT amount_cents FROM allocation_credit WHERE tenant=NEW.tenant AND id=NEW.credit_id)
            - COALESCE((SELECT SUM(amount_cents) FROM allocation_application WHERE tenant=NEW.tenant AND credit_id=NEW.credit_id),0)
            THEN RAISE(ABORT,'Application exceeds remaining credit') END;
          SELECT CASE WHEN NEW.amount_cents >
            (SELECT eligible_cents FROM allocation_bill WHERE tenant=NEW.tenant AND id=NEW.bill_id)
            - COALESCE((SELECT SUM(amount_cents) FROM allocation_application WHERE tenant=NEW.tenant AND bill_id=NEW.bill_id),0)
            THEN RAISE(ABORT,'Application exceeds remaining eligible bill amount') END;
        END""",
    ]
    for statement in statements:
        db.execute(statement)
    for table in ("award", "credit", "bill", "application", "observation"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS allocation_{table}_date
            BEFORE INSERT ON allocation_{table} BEGIN
            SELECT CASE WHEN length(NEW.effective_date)<>10
                OR date(NEW.effective_date,'+0 days') IS NULL
                OR date(NEW.effective_date,'+0 days')<>NEW.effective_date
                THEN RAISE(ABORT,'Canonical valid calendar date required') END; END""")
    for table in ("scope", "journal", "award", "credit", "bill", "application", "observation", "legacy"):
        for operation in ("UPDATE", "DELETE"):
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS allocation_{table}_no_{operation.lower()}
                BEFORE {operation} ON allocation_{table} BEGIN
                SELECT RAISE(ABORT,'Allocation history is immutable'); END""")


def _scope(db, tenant, row):
    values = [canonical(row.get(key), key) for key in SCOPE_FIELDS]
    values[-1] = values[-1].upper()
    if values[-1] != "USD":
        raise ValueError("Only USD settlement is supported")
    db.execute("""INSERT OR IGNORE INTO allocation_scope
      (tenant,vendor_id,account_id,product_id,contract_id,contract_version,currency)
      VALUES (?,?,?,?,?,?,?)""", (tenant, *values))
    return dict(db.execute("""SELECT * FROM allocation_scope WHERE tenant=? AND vendor_id=?
        AND account_id=? AND product_id=? AND contract_id=? AND contract_version=? AND currency=?""",
        (tenant, *values)).fetchone())


def _native(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Native Ramp UUID required") from exc


def _record(db, kind, tenant, row, *, case_id=None, origin="INTAKE"):
    tenant = canonical(tenant, "tenant")
    if "tenant" in row and canonical(row["tenant"], "tenant") != tenant:
        raise ValueError("Mismatched tenant")
    ident = canonical(row.get("id"))
    source = Source(row.get("source")).value
    source_ref = canonical(row.get("source_ref"), "source_ref")
    amount = _cents(row)
    effective = calendar_date(row.get("effective_date"))
    scope = _scope(db, tenant, row)
    data = dict(tenant=tenant, id=ident, scope_id=scope["scope_id"], source=source,
                source_ref=source_ref, amount_cents=amount, effective_date=effective)
    if kind == "award":
        if row.get("confirmed") is not True:
            raise ValueError("Confirmed award required")
        data.update(memo_ref=canonical(row.get("memo_ref"), "memo_ref"), case_id=canonical(case_id, "case_id"))
    elif kind == "credit":
        data.update(memo_ref=canonical(row.get("memo_ref"), "memo_ref"), award_id=canonical(row.get("award_id"), "award_id"))
    elif kind == "bill":
        data["eligible_cents"] = _cents(row, "eligible_cents", "eligible_amount", positive=False)
    else:
        raise ValueError("Unknown allocation record kind")
    if source == Source.RAMP:
        _native(scope["vendor_id"])
        if ident != _native(ident) or source_ref != ident:
            raise ValueError("Ramp identity must equal its canonical native source reference")
    sequence, exists = _journal(db, tenant, kind, ident, data, origin)
    if not exists:
        data["sequence"] = sequence
        fields = ",".join(data)
        placeholders = ",".join("?" for _ in data)
        db.execute(f"INSERT INTO allocation_{kind} ({fields}) VALUES ({placeholders})", tuple(data.values()))
    return ident


def _journal(db, tenant, kind, event_id, data, origin="INTAKE"):
    payload = _json(data)
    previous = db.execute("SELECT sequence,payload FROM allocation_journal WHERE tenant=? AND kind=? AND event_id=?",
                          (tenant, kind, event_id)).fetchone()
    if previous:
        if previous["payload"] != payload:
            raise ValueError("Conflicting duplicate allocation event")
        return previous["sequence"], True
    cursor = db.execute("""INSERT INTO allocation_journal(tenant,kind,event_id,payload,recorded_at,origin)
        VALUES(?,?,?,?,?,?)""", (tenant, kind, event_id, payload, datetime.now(timezone.utc).isoformat(), origin))
    return cursor.lastrowid, False


def _parents(db, tenant, credit_id, bill_id):
    credit = db.execute("SELECT * FROM allocation_credit WHERE tenant=? AND id=?", (tenant, credit_id)).fetchone()
    bill = db.execute("SELECT * FROM allocation_bill WHERE tenant=? AND id=?", (tenant, bill_id)).fetchone()
    if not credit or not bill:
        raise ValueError("Unverified credit or bill")
    if credit["scope_id"] != bill["scope_id"]:
        raise ValueError("Mismatched account/product/contract scope")
    if (credit["source"] == Source.RAMP) != (bill["source"] == Source.RAMP):
        raise ValueError("Sandbox and fixture settlement records cannot be combined")
    return credit, bill


def _check_application_scope(db, credit, bill, row):
    scope = db.execute("SELECT * FROM allocation_scope WHERE scope_id=?", (credit["scope_id"],)).fetchone()
    for key in SCOPE_FIELDS:
        if key in row:
            value = canonical(row[key], key)
            if key == "currency":
                value = value.upper()
            if value != scope[key]:
                raise ValueError(f"Application {key} mismatch")
    award = db.execute("SELECT effective_date FROM allocation_award WHERE tenant=? AND id=?",
                       (credit["tenant"], credit["award_id"])).fetchone()
    if (bill["effective_date"] < max(award["effective_date"], credit["effective_date"])
            or row["effective_date"] < max(bill["effective_date"], credit["effective_date"])):
        raise ValueError("Application date mismatch or predating bill")


def _apply(db, tenant, row, *, origin="INTAKE", provider_delta=False):
    tenant = canonical(tenant, "tenant")
    if "tenant" in row and canonical(row["tenant"], "tenant") != tenant:
        raise ValueError("Mismatched tenant")
    source = Source(row.get("source")).value
    if source == Source.RAMP and not provider_delta:
        raise ValueError("Ramp application requires a cumulative observed record")
    data = dict(tenant=tenant, id=canonical(row.get("id")),
                credit_id=canonical(row.get("credit_id"), "credit_id"),
                bill_id=canonical(row.get("bill_id"), "bill_id"), source=source,
                source_ref=canonical(row.get("source_ref"), "source_ref"),
                amount_cents=_cents(row), effective_date=calendar_date(row.get("effective_date")))
    credit, bill = _parents(db, tenant, data["credit_id"], data["bill_id"])
    _check_application_scope(db, credit, bill, row)
    sequence, exists = _journal(db, tenant, "application", data["id"], data, origin)
    if not exists:
        db.execute("""INSERT INTO allocation_application
            (tenant,id,credit_id,bill_id,source,source_ref,amount_cents,effective_date,sequence)
            VALUES(?,?,?,?,?,?,?,?,?)""", (*data.values(), sequence))
    return data["id"]


class AllocationLedger:
    """Local persistence only. Authorization and evidence acquisition belong upstream."""
    def __init__(self, path):
        self.path = Path(path)
        initialize_allocations(self.path)

    def record_award(self, tenant, case_id, award):
        with _connect(self.path, write=True) as db:
            return _record(db, "award", tenant, award, case_id=case_id)

    def record_credit(self, tenant, credit):
        with _connect(self.path, write=True) as db:
            return _record(db, "credit", tenant, credit)

    def record_bill(self, tenant, bill):
        with _connect(self.path, write=True) as db:
            return _record(db, "bill", tenant, bill)

    def head(self):
        with _connect(self.path) as db:
            return _cutoff(db, None)

    def apply(self, tenant, application, *, check_authority=None, confirm=None):
        with _connect(self.path, write=True) as db:
            if check_authority:
                check_authority(db)
            identity=_apply(db, tenant, application)
            if confirm:
                confirm()
            return identity

    def ingest(self, tenant, case_id, award, credits=(), applications=(), bills=(), *, check_authority=None, confirm=None):
        """All-or-nothing fixture intake; persisted bills are shared across every case."""
        with _connect(self.path, write=True) as db:
            if check_authority:
                check_authority(db)
            ident = _record(db, "award", tenant, award, case_id=case_id)
            for row in credits:
                _record(db, "credit", tenant, row)
            for row in bills:
                _record(db, "bill", tenant, row)
            for row in applications:
                _apply(db, tenant, row)
            if confirm:
                confirm()
        return self.reconcile(tenant, ident)

    def observe_application(self, tenant, observation):
        """Record an observed sandbox cumulative pair without double counting replay.

        observation has id (delivery key), credit_id, bill_id, source,
        source_ref='ramp:<credit UUID>:<bill UUID>', amount_cents (cumulative),
        observed_at (timezone-aware), effective_date (application calendar date).
        A stale compatible snapshot is retained but never added again. Reversals
        and contradictory historical totals require explicit investigation.
        """
        with _connect(self.path, write=True) as db:
            return _observe(db, tenant, observation)

    def reconcile(self, tenant, award_id, *, as_of=None):
        with _connect(self.path) as db:
            return _reconcile(db, canonical(tenant, "tenant"), canonical(award_id), as_of)

    def bill_balance(self, tenant, bill_id, *, as_of=None):
        with _connect(self.path) as db:
            return _bill_balance(db, canonical(tenant, "tenant"), canonical(bill_id), _cutoff(db, as_of))

    def list_bills(self, tenant, *, as_of=None):
        with _connect(self.path) as db:
            tenant, cutoff = canonical(tenant, "tenant"), _cutoff(db, as_of)
            ids = db.execute("SELECT id FROM allocation_bill WHERE tenant=? AND sequence<=? ORDER BY id",
                             (tenant, cutoff)).fetchall()
            return [_bill_balance(db, tenant, row["id"], cutoff) for row in ids]

    def list_awards(self, tenant, *, case_id=None, as_of=None):
        with _connect(self.path) as db:
            tenant, cutoff = canonical(tenant, "tenant"), _cutoff(db, as_of)
            case_id = canonical(case_id, "case_id") if case_id is not None else None
            ids = db.execute("""SELECT id FROM allocation_award WHERE tenant=? AND sequence<=?
                AND (? IS NULL OR case_id=?) ORDER BY id""", (tenant, cutoff, case_id, case_id)).fetchall()
            return [_reconcile(db, tenant, row["id"], cutoff) for row in ids]

    def history(self, tenant):
        with _connect(self.path) as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM allocation_journal WHERE tenant=? ORDER BY sequence", (canonical(tenant, "tenant"),))]


def _observe(db, tenant, row):
    tenant = canonical(tenant, "tenant")
    if "tenant" in row and canonical(row["tenant"], "tenant") != tenant:
        raise ValueError("Mismatched tenant")
    if row.get("source") != Source.RAMP:
        raise ValueError("Cumulative provider observations require sandbox provenance")
    credit_id, bill_id = _native(row.get("credit_id")), _native(row.get("bill_id"))
    pair = f"ramp:{credit_id}:{bill_id}"
    if row.get("source_ref") != pair:
        raise ValueError("Unmatched provider application identifier")
    credit, bill = _parents(db, tenant, credit_id, bill_id)
    if credit["source"] != Source.RAMP or bill["source"] != Source.RAMP:
        raise ValueError("Sandbox and fixture settlement records cannot be combined")
    data = dict(tenant=tenant, id=canonical(row.get("id")), credit_id=credit_id, bill_id=bill_id,
                amount_cents=_cents(row, positive=False), observed_at=instant(row.get("observed_at")),
                effective_date=calendar_date(row.get("effective_date")), source_ref=pair, source=Source.RAMP.value)
    _check_application_scope(db, credit, bill, row)
    sequence, exists = _journal(db, tenant, "observation", data["id"], data)
    if exists:
        return data["id"]
    previous = db.execute("""SELECT amount_cents,observed_at,effective_date FROM allocation_observation
        WHERE tenant=? AND credit_id=? AND bill_id=? ORDER BY observed_at""", (tenant, credit_id, bill_id)).fetchall()
    for old in previous:
        if ((old["observed_at"] <= data["observed_at"] and old["amount_cents"] > data["amount_cents"])
                or (old["observed_at"] >= data["observed_at"] and old["amount_cents"] < data["amount_cents"])):
            raise ValueError("Conflicting cumulative observation or unsupported reversal")
    same_time = next((old for old in previous if old["observed_at"] == data["observed_at"]), None)
    if same_time and same_time["effective_date"] != data["effective_date"]:
        raise ValueError("Conflicting cumulative observation date")
    if not same_time:
        db.execute("""INSERT INTO allocation_observation
            (tenant,id,credit_id,bill_id,amount_cents,observed_at,effective_date,sequence) VALUES(?,?,?,?,?,?,?,?)""",
            (tenant, data["id"], credit_id, bill_id, data["amount_cents"], data["observed_at"], data["effective_date"], sequence))
    allocated = db.execute("""SELECT COALESCE(SUM(amount_cents),0) FROM allocation_application
        WHERE tenant=? AND credit_id=? AND bill_id=?""", (tenant, credit_id, bill_id)).fetchone()[0]
    if data["amount_cents"] > allocated:
        _apply(db, tenant, {**data, "id": pair + "@" + data["observed_at"],
                           "source_ref": pair + "@" + data["observed_at"],
                           "amount_cents": data["amount_cents"] - allocated}, provider_delta=True)
    return data["id"]


def _cutoff(db, as_of):
    if as_of is not None and (type(as_of) is not int or as_of < 0):
        raise ValueError("as_of must be a nonnegative journal sequence")
    return as_of if as_of is not None else db.execute("SELECT COALESCE(MAX(sequence),0) FROM allocation_journal").fetchone()[0]


def _bill_balance(db, tenant, bill_id, cutoff):
    bill = db.execute("SELECT * FROM allocation_bill WHERE tenant=? AND id=? AND sequence<=?",
                      (tenant, bill_id, cutoff)).fetchone()
    if not bill:
        raise KeyError("Unknown bill at this journal sequence")
    applied = db.execute("""SELECT COALESCE(SUM(amount_cents),0) FROM allocation_application
        WHERE tenant=? AND bill_id=? AND sequence<=?""", (tenant, bill_id, cutoff)).fetchone()[0]
    scope = dict(db.execute("SELECT * FROM allocation_scope WHERE scope_id=?", (bill["scope_id"],)).fetchone())
    return {**dict(bill), "scope": scope, "applied_cents": applied, "remaining_eligible_cents": bill["eligible_cents"] - applied,
            "total": money(bill["amount_cents"]), "eligible": money(bill["eligible_cents"]),
            "applied": money(applied), "remaining_eligible": money(bill["eligible_cents"] - applied),
            "as_of_sequence": cutoff}


def _reconcile(db, tenant, award_id, as_of=None):
    from .reconciliation import _provenance
    cutoff = _cutoff(db, as_of)
    award = db.execute("SELECT * FROM allocation_award WHERE tenant=? AND id=? AND sequence<=?",
                       (tenant, award_id, cutoff)).fetchone()
    if not award:
        raise KeyError("Unknown award at this journal sequence")
    credits = db.execute("SELECT * FROM allocation_credit WHERE tenant=? AND award_id=? AND sequence<=?",
                         (tenant, award_id, cutoff)).fetchall()
    apps = db.execute("""SELECT x.*,b.source AS bill_source FROM allocation_application x
        JOIN allocation_credit c ON c.tenant=x.tenant AND c.id=x.credit_id
        JOIN allocation_bill b ON b.tenant=x.tenant AND b.id=x.bill_id
        WHERE c.tenant=? AND c.award_id=? AND x.sequence<=? ORDER BY x.sequence""", (tenant, award_id, cutoff)).fetchall()
    posted, applied = sum(c["amount_cents"] for c in credits), sum(a["amount_cents"] for a in apps)
    total = award["amount_cents"]
    values = dict(awarded=total, posted=posted, applied=applied, outstanding=total-applied,
                  unposted=total-posted, unapplied_posted=posted-applied)
    posted_sources = {c["source"] for c in credits}
    applied_sources = {s for a in apps for s in (a["source"], a["bill_source"])}
    sources = {award["source"]} | posted_sources | applied_sources
    stage = "APPLIED" if applied == total else "PARTIALLY_APPLIED" if applied else "POSTED" if posted else "AWARDED"
    sequences = [award["sequence"], *[c["sequence"] for c in credits], *[a["sequence"] for a in apps]]
    origins = sorted({db.execute("SELECT origin FROM allocation_journal WHERE sequence=?", (seq,)).fetchone()[0]
                      for seq in sequences})
    bill_ids = sorted({a["bill_id"] for a in apps})
    scope = dict(db.execute("SELECT * FROM allocation_scope WHERE scope_id=?", (award["scope_id"],)).fetchone())
    return {**{key: money(value) for key, value in values.items()},
            **{key + "_cents": value for key, value in values.items()},
            "currency": "USD", "award_id": award_id, "memo_ref": award["memo_ref"], "case_id": award["case_id"],
            "scope": scope, "source_ref": award["source_ref"], "effective_date": award["effective_date"],
            "credit_ids": sorted(c["id"] for c in credits), "application_ids": sorted(a["id"] for a in apps),
            "bill_ids": bill_ids, "bill_balances": [_bill_balance(db, tenant, ident, cutoff) for ident in bill_ids],
            "stage": stage, "sources": sorted(sources), "origins": origins, "as_of_sequence": cutoff,
            "stage_sources": _provenance({award["source"]}, posted_sources, applied_sources), "actual_recovery": None}


def initialize_allocations(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with _connect(path, write=True) as db:
        _schema(db)
        _migrate_legacy(db)


def _demo_rows(tenant, case_id, amount, effective_date):
    """Explicit simulation identities; these never refer to a provider object."""
    key = "sim:" + canonical(case_id, "case_id") + ":"
    base = dict(tenant=canonical(tenant), vendor_id="fixture-vendor:" + case_id,
                account_id="fixture-account", product_id="fixture-product:" + case_id,
                contract_id="fixture-contract:" + case_id, contract_version="v3-simulation",
                currency="USD", amount_cents=amount, effective_date=effective_date)
    award = dict(base, id=key + "award", source_ref=key + "award", memo_ref=key + "memo",
                 source=Source.VENDOR.value, confirmed=True)
    credit = dict(base, id=key + "credit", source_ref=key + "credit", memo_ref=key + "memo",
                  award_id=award["id"], source=Source.REPLAY.value)
    bill = dict(base, id=key + "bill", source_ref=key + "bill", eligible_cents=amount,
                source=Source.CUSTOMER.value)
    return award, credit, bill


def _demo_transition(db, tenant, case_id, action, amount, *, origin="INTAKE", at=None):
    effective_date = instant(at or datetime.now(timezone.utc).isoformat())[:10]
    prior = db.execute("SELECT effective_date FROM allocation_award WHERE tenant=? AND id=?",
                       (tenant, "sim:" + case_id + ":award")).fetchone()
    award, credit, bill = _demo_rows(tenant, case_id, amount, prior[0] if prior else effective_date)
    _record(db, "award", tenant, award, case_id=case_id, origin=origin)
    _record(db, "credit", tenant, credit, origin=origin)
    if action in ("apply-partial", "apply-balance"):
        prior_bill = db.execute("SELECT effective_date FROM allocation_bill WHERE tenant=? AND id=?",
                                (tenant, bill["id"])).fetchone()
        bill["effective_date"] = prior_bill[0] if prior_bill else effective_date
        _record(db, "bill", tenant, bill, origin=origin)
        result = _reconcile(db, tenant, award["id"])
        apply_amount = amount // 2 if action == "apply-partial" else result["unapplied_posted_cents"]
        if apply_amount <= 0:
            if origin == "LEGACY_STAGE_PROJECTION":
                return
            raise ValueError("A partial application must have positive cents; apply the balance")
        app_id = "sim:" + case_id + ":" + action
        _apply(db, tenant, dict(id=app_id, source_ref=app_id, credit_id=credit["id"], bill_id=bill["id"],
                               amount_cents=apply_amount, effective_date=effective_date,
                               source=Source.REPLAY.value), origin=origin)


def _migrate_legacy(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='settlement_event'").fetchone():
        return
    rows = db.execute("""SELECT e.* FROM settlement_event e LEFT JOIN allocation_legacy l
        ON l.settlement_sequence=e.sequence WHERE l.settlement_sequence IS NULL ORDER BY e.sequence""").fetchall()
    for row in rows:
        amount = usd_cents(row["awarded"])
        if amount <= 0 or row["action"] not in ("record-credit", "apply-partial", "apply-balance"):
            raise ValueError("Invalid legacy settlement event; migration rolled back")
        previous = db.execute("""SELECT stage FROM settlement_event WHERE tenant=? AND case_id=?
            AND sequence<? ORDER BY sequence DESC LIMIT 1""", (row["tenant"],row["case_id"],row["sequence"])).fetchone()
        required, expected = {"record-credit": (None, "POSTED"),
                              "apply-partial": ("POSTED", "PARTIALLY_APPLIED"),
                              "apply-balance": ("PARTIALLY_APPLIED", "APPLIED")}[row["action"]]
        if row["stage"] != expected or (previous[0] if previous else None) != required:
            raise ValueError("Inconsistent legacy settlement history; migration rolled back")
        _demo_transition(db, row["tenant"], row["case_id"], row["action"], amount,
                         origin="LEGACY_STAGE_PROJECTION", at=row["at"])
        db.execute("INSERT INTO allocation_legacy VALUES(?,?,?,?,?)",
                   (row["sequence"], row["tenant"], row["case_id"], _json(dict(row)), _cutoff(db, None)))


def settlement_reconciliation(path, tenant, case_id, award_amount):
    """Read persisted demo allocations; unposted awards retain the V3 projection API."""
    from .reconciliation import demo_reconciliation
    ledger = AllocationLedger(path)
    tenant, case_id = canonical(tenant), canonical(case_id)
    award_id = "sim:" + case_id + ":award"
    try:
        result = ledger.reconcile(tenant, award_id)
    except KeyError:
        return demo_reconciliation(award_amount, "AWARDED" if usd_cents(award_amount) else "NONE",
                                   tenant=tenant, case_id=case_id)
    if result["awarded_cents"] != usd_cents(award_amount):
        raise ValueError("Award changed after reconciliation")
    return result


def settlement_actions(stage, amount):
    """Compatible action descriptors, including a direct one-cent full application."""
    from .storage import SETTLEMENT_ACTIONS
    previous = None if stage == "AWARDED" else stage
    actions = [dict(id=key, label=value[2]) for key, value in SETTLEMENT_ACTIONS.items() if value[0] == previous]
    if previous == "POSTED" and usd_cents(amount) == 1:
        actions = [dict(id="apply-balance", label=SETTLEMENT_ACTIONS["apply-balance"][2])]
    return actions
