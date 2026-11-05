"""Offline, tenant-scoped Ramp credit observations and explicit ledger reconciliation.

This module has no provider transport. Caller-supplied provenance is an upstream
custody assertion, not OAuth identity or commercial authority. Never makes awards,
bills, payments or real-recovery claims. See docs/v4/RAMP-CREDIT-SYNC.md.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

from .allocations import (
    AllocationLedger, MAX_CENTS, SCOPE_FIELDS, _connect, _json, _native,
    _observe, _record, calendar_date, canonical, instant,
)
from .contracts import Source

MAX_AGE = timedelta(hours=24)
CREDIT_FIELDS = ("id", "vendor_id", "entity_id", "reference_bill_id", "accounting_date",
                 "archived_at", "total_amount", "remaining_amount", "total_applied_amount",
                 "applied_bills", "applied_draft_bills")
BILL_FIELDS = ("id", "vendor", "entity_id", "issued_at", "archived_at", "status",
               "amount", "applied_vendor_credits")
BINDING_FIELDS = (*SCOPE_FIELDS, "credit_id", "award_id", "bill_id", "observation_id",
                  "provider_provenance_ref", "provenance_ref", "award_source",
                  "award_source_ref", "memo_ref")


class CreditSyncError(ValueError):
    """Reason code only: never echoes private provider payloads."""


def _fail(code):
    raise CreditSyncError(code)


def _money(value):
    if value is None:
        _fail("SPARSE_MONEY")
    if not isinstance(value, dict):
        _fail("INVALID_MONEY")
    amount, currency, rate = (value.get(k) for k in
                              ("amount", "currency_code", "minor_unit_conversion_rate"))
    if amount is None or currency is None or rate is None:
        _fail("SPARSE_MONEY")
    if (type(amount) is not int or not 0 <= amount <= MAX_CENTS or
            not isinstance(currency, str) or len(currency) != 3 or
            not currency.isascii() or not currency.isupper() or not currency.isalpha() or
            type(rate) is not int or rate not in (1, 10, 100, 1000, 10000) or
            (currency == "USD" and rate != 100)):
        _fail("INVALID_MONEY")
    return amount, currency, rate


def _links(rows, key, unit):
    if rows is None:
        _fail("SPARSE_APPLICATIONS")
    if not isinstance(rows, list):
        _fail("INVALID_APPLICATIONS")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            _fail("INVALID_APPLICATIONS")
        ident = _native(row.get(key))
        value = _money(row.get("amount"))
        if value[1:] != unit:
            _fail("CROSS_CURRENCY")
        if ident in result:
            _fail("DUPLICATE_APPLICATION")
        result[ident] = value[0]
    return result


def _project_fields(row, fields):
    """Retain only necessary financial readback fields, never descriptions/PII."""
    if not isinstance(row, dict):
        _fail("INVALID_RECORD")
    result = {k: row[k] for k in fields if k in row}
    result["id"] = _native(row.get("id"))
    for key in ("amount", "total_amount", "remaining_amount", "total_applied_amount"):
        if isinstance(result.get(key), dict):
            result[key] = {k: result[key].get(k) for k in
                           ("amount", "currency_code", "minor_unit_conversion_rate")}
    if isinstance(result.get("vendor"), dict):
        result["vendor"] = {"id": result["vendor"].get("id")}
    for key, ident in (("applied_bills", "bill_id"), ("applied_draft_bills", "bill_id"),
                       ("applied_vendor_credits", "id")):
        if isinstance(result.get(key), list):
            links = []
            for link in result[key]:
                if not isinstance(link, dict):
                    _fail("INVALID_APPLICATIONS")
                amount = link.get("amount")
                if isinstance(amount, dict):
                    amount = {k: amount.get(k) for k in
                              ("amount", "currency_code", "minor_unit_conversion_rate")}
                links.append({ident: _native(link.get(ident)), "amount": amount})
            result[key] = sorted(links, key=lambda link: link[ident])
    return result


def _normalize(snapshot):
    if not isinstance(snapshot, dict):
        _fail("INVALID_ENVELOPE")
    source = snapshot.get("source")
    if source not in (Source.RAMP.value, Source.REPLAY.value):
        _fail("UNSUPPORTED_PROVENANCE")
    scopes = snapshot.get("scopes")
    if isinstance(scopes, str):
        scopes = scopes.split()
    if scopes is not None and (not isinstance(scopes, list) or
                                any(not isinstance(s, str) for s in scopes)):
        _fail("INVALID_SCOPES")
    result = dict(id=canonical(snapshot.get("id")), observed_at=instant(snapshot.get("observed_at")),
                  source=source, provenance_ref=canonical(snapshot.get("provenance_ref")),
                  scopes=sorted(set(scopes)) if scopes is not None else None)
    for key in ("available", "list_complete"):
        value = snapshot.get(key)
        if value is not None and type(value) is not bool:
            _fail("INVALID_AVAILABILITY")
        result[key] = value
    for key, fields in (("credits", CREDIT_FIELDS), ("bills", BILL_FIELDS)):
        rows = snapshot.get(key)
        if rows is not None and not isinstance(rows, list):
            _fail("INVALID_RECORDS")
        result[key] = None if rows is None else [_project_fields(r, fields) for r in rows]
        if rows is not None:
            ids = [r["id"] for r in result[key]]
            if len(ids) != len(set(ids)):
                _fail("DUPLICATE_RECORD")
            result[key].sort(key=lambda r: r["id"])
    return result


def _facts(snapshot):
    """Validate official quantities without inventing contractual scope."""
    if snapshot["available"] is not True:
        _fail("UNAVAILABLE")
    if "vendors:read" not in (snapshot["scopes"] or []):
        _fail("SCOPE_UNCONFIRMED")
    if snapshot["credits"] is None:
        _fail("SPARSE_CREDITS")
    credits, bills = {}, {}
    for row in snapshot["credits"]:
        for key in ("vendor_id", "accounting_date", "archived_at"):
            if key not in row or (row[key] is None and key != "archived_at"):
                _fail("SPARSE_CREDIT")
        total = _money(row.get("total_amount"))
        remaining = _money(row.get("remaining_amount"))
        applied = _money(row.get("total_applied_amount"))
        if total[1:] != remaining[1:] or total[1:] != applied[1:]:
            _fail("CROSS_CURRENCY")
        links = _links(row.get("applied_bills"), "bill_id", total[1:])
        drafts = _links(row.get("applied_draft_bills"), "bill_id", total[1:])
        if set(links) & set(drafts):
            _fail("BILL_DRAFT_OVERLAP")
        if (remaining[0] + applied[0] != total[0] or
                sum(links.values()) + sum(drafts.values()) != applied[0]):
            _fail("CREDIT_TOTAL_CONFLICT")
        archived = row["archived_at"]
        if archived is not None:
            archived = instant(archived)
        credits[row["id"]] = dict(id=row["id"], vendor_id=_native(row["vendor_id"]),
                                  entity_id=row.get("entity_id"),
                                  effective_date=calendar_date(row["accounting_date"]),
                                  archived_at=archived, total=total[0], unit=total[1:],
                                  remaining=remaining[0], applied=applied[0], links=links, drafts=drafts)
    for row in snapshot["bills"] or []:
        if (row.get("amount") is None or not isinstance(row.get("vendor"), dict)
                or row["vendor"].get("id") is None):
            continue  # Sparse bills cannot satisfy a later binding/readback.
        total = _money(row["amount"])
        if row.get("applied_vendor_credits") is None:
            continue
        links = _links(row["applied_vendor_credits"], "id", total[1:])
        if sum(links.values()) > total[0]:
            _fail("BILL_OVERCAPACITY")
        bills[row["id"]] = dict(id=row["id"], vendor_id=_native(row["vendor"].get("id")),
                                entity_id=row.get("entity_id"), total=total[0], unit=total[1:],
                                archived_at=row.get("archived_at", "UNKNOWN"),
                                status=row.get("status"), links=links)
    for credit in credits.values():
        for bill_id, amount in credit["links"].items():
            if bill_id not in bills:
                continue  # Unmatched observations do not become allocations.
            bill = bills[bill_id]
            _same_provider_scope(credit, bill)
            if bill["links"].get(credit["id"]) != amount:
                _fail("RECIPROCAL_CONFLICT")
    for bill in bills.values():
        for credit_id, amount in bill["links"].items():
            if credit_id in credits and credits[credit_id]["links"].get(bill["id"]) != amount:
                _fail("RECIPROCAL_CONFLICT")
    return credits, bills


def _same_provider_scope(credit, bill):
    if credit["unit"] != bill["unit"]:
        _fail("CROSS_CURRENCY")
    if credit["vendor_id"] != bill["vendor_id"]:
        _fail("VENDOR_CONFLICT")
    if (credit["entity_id"] is not None and bill["entity_id"] is not None and
            credit["entity_id"] != bill["entity_id"]):
        _fail("ENTITY_CONFLICT")


def _fresh(snapshot, now):
    age = datetime.fromisoformat(instant(now)) - datetime.fromisoformat(snapshot["observed_at"])
    return timedelta(0) <= age <= MAX_AGE


class RampCreditSync:
    """Trusted local intake. Workbench authorization must precede these methods."""

    def __init__(self, path):
        self.path = Path(path)
        self.ledger = AllocationLedger(self.path)
        with _connect(self.path, write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS ramp_credit_snapshot (
                sequence INTEGER PRIMARY KEY, tenant TEXT NOT NULL, id TEXT NOT NULL,
                observed_at TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL,
                status TEXT NOT NULL, issues TEXT NOT NULL, UNIQUE(tenant,id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS ramp_credit_binding (
                tenant TEXT NOT NULL, credit_id TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(tenant,credit_id))""")
            for table in ("ramp_credit_snapshot", "ramp_credit_binding"):
                for operation in ("UPDATE", "DELETE"):
                    db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()}
                        BEFORE {operation} ON {table} BEGIN
                        SELECT RAISE(ABORT,'Credit sync history is immutable'); END""")

    def _history_check(self, db, tenant, snapshot, credits):
        for old in db.execute("SELECT payload,status FROM ramp_credit_snapshot WHERE tenant=?", (tenant,)):
            if old["status"] not in ("RECORDED", "EMPTY", "PARTIAL", "STALE"):
                continue
            earlier = json.loads(old["payload"])
            if earlier["source"] != snapshot["source"]:
                if any(r["id"] in credits for r in earlier["credits"] or []):
                    _fail("PROVENANCE_CONFLICT")
                continue
            prior, _ = _facts(earlier)
            for ident in set(prior) & set(credits):
                before, after = prior[ident], credits[ident]
                for key in ("vendor_id", "entity_id", "effective_date", "total", "unit"):
                    if before[key] != after[key]:
                        _fail("CREDIT_IDENTITY_CONFLICT")
                if earlier["observed_at"] > snapshot["observed_at"]:
                    before, after = after, before
                if (before["applied"] > after["applied"] or
                        any(value > after["links"].get(k, 0) for k, value in before["links"].items())):
                    _fail("DECREASING_APPLICATION")
                if before["archived_at"] and before != after:
                    _fail("ARCHIVED_CONFLICT")
                if earlier["observed_at"] == snapshot["observed_at"] and before != after:
                    _fail("SAME_TIME_CONFLICT")

    @staticmethod
    def _quarantined(db, tenant):
        # Reversals/archives/capacity contradictions need an explicit reviewed
        # resolution, never an automatic reset by the next successful-looking read.
        return db.execute("SELECT 1 FROM ramp_credit_snapshot WHERE tenant=? AND status='CONFLICT' LIMIT 1",
                          (tenant,)).fetchone() is not None

    def import_snapshot(self, tenant, snapshot, *, as_of=None):
        """Persist sanitized readbacks; quarantine conflicts without changing allocations."""
        if isinstance(snapshot, dict) and "tenant" in snapshot and canonical(snapshot["tenant"]) != canonical(tenant):
            _fail("TENANT_CONFLICT")
        tenant, snapshot = canonical(tenant), _normalize(snapshot)
        now = as_of or datetime.now(timezone.utc).isoformat()
        payload = _json(snapshot)
        digest = sha256(payload.encode()).hexdigest()
        with _connect(self.path, write=True) as db:
            old = db.execute("SELECT * FROM ramp_credit_snapshot WHERE tenant=? AND id=?",
                             (tenant, snapshot["id"])).fetchone()
            if old:
                if old["digest"] != digest:
                    _fail("OBSERVATION_ID_CONFLICT")
                return self._receipt(old)
            status, issues = "RECORDED", []
            db.execute("SAVEPOINT projection")
            try:
                credits, bills = _facts(snapshot)
                if self._quarantined(db, tenant):
                    _fail("PRIOR_CONFLICT_REQUIRES_REVIEW")
                self._history_check(db, tenant, snapshot, credits)
                if not _fresh(snapshot, now):
                    status, issues = "STALE", ["STALE_OR_FUTURE_OBSERVATION"]
                elif snapshot["list_complete"] is not True:
                    status, issues = "PARTIAL", ["INCOMPLETE_LIST"]
                else:
                    status = "RECORDED" if credits else "EMPTY"
                    newer = db.execute("SELECT 1 FROM ramp_credit_snapshot WHERE tenant=? AND observed_at>? LIMIT 1",
                                       (tenant, snapshot["observed_at"])).fetchone()
                    bindings = [] if newer else db.execute(
                        "SELECT payload FROM ramp_credit_binding WHERE tenant=?", (tenant,)).fetchall()
                    for row in bindings:
                        binding = json.loads(row[0])
                        if binding["credit_id"] not in credits:
                            _fail("MISSING_LINKED_CREDIT")
                        self._project(db, tenant, binding, snapshot, credits, bills)
            except CreditSyncError as exc:
                db.execute("ROLLBACK TO projection")
                code = str(exc)
                status = ("UNAVAILABLE" if code == "UNAVAILABLE" else "INSUFFICIENT_EVIDENCE"
                          if code.startswith("SPARSE_") or code == "SCOPE_UNCONFIRMED" else "CONFLICT")
                issues = [code]
            except ValueError:
                db.execute("ROLLBACK TO projection")
                status, issues = "CONFLICT", ["LEDGER_OR_RECORD_CONFLICT"]
            finally:
                db.execute("RELEASE projection")
            db.execute("""INSERT INTO ramp_credit_snapshot
                (tenant,id,observed_at,payload,digest,status,issues) VALUES(?,?,?,?,?,?,?)""",
                       (tenant, snapshot["id"], snapshot["observed_at"], payload, digest, status, _json(issues)))
            return dict(id=snapshot["id"], status=status, issues=issues, actual_recovery=None)

    @staticmethod
    def _receipt(row):
        return dict(id=row["id"], status=row["status"], issues=json.loads(row["issues"]), actual_recovery=None)

    def link_award(self, tenant, binding, *, as_of=None):
        """Bind an existing confirmed ledger award; never creates one from a claim."""
        tenant = canonical(tenant)
        if not isinstance(binding, dict):
            _fail("INVALID_BINDING")
        if "tenant" in binding and canonical(binding["tenant"]) != tenant:
            _fail("TENANT_CONFLICT")
        binding = {k: canonical(binding.get(k), k) for k in BINDING_FIELDS}
        for key in ("credit_id", "bill_id", "vendor_id"):
            binding[key] = _native(binding[key])
        if binding["currency"] != "USD":
            _fail("UNSUPPORTED_SETTLEMENT_CURRENCY")
        with _connect(self.path, write=True) as db:
            old = db.execute("SELECT payload FROM ramp_credit_binding WHERE tenant=? AND credit_id=?",
                             (tenant, binding["credit_id"])).fetchone()
            if old:
                if old[0] != _json(binding):
                    _fail("BINDING_CONFLICT")
                return dict(credit_id=binding["credit_id"], status="LINKED", actual_recovery=None)
            if self._quarantined(db, tenant):
                _fail("PRIOR_CONFLICT_REQUIRES_REVIEW")
            row = db.execute("SELECT * FROM ramp_credit_snapshot WHERE tenant=? ORDER BY observed_at DESC,sequence DESC LIMIT 1",
                             (tenant,)).fetchone()
            if not row or row["id"] != binding["observation_id"] or row["status"] != "RECORDED":
                _fail("CURRENT_COMPLETE_OBSERVATION_REQUIRED")
            snapshot = json.loads(row["payload"])
            if snapshot["provenance_ref"] != binding["provider_provenance_ref"]:
                _fail("PROVENANCE_CONFLICT")
            if not _fresh(snapshot, as_of or datetime.now(timezone.utc).isoformat()):
                _fail("STALE_OBSERVATION")
            credits, bills = _facts(snapshot)
            self._project(db, tenant, binding, snapshot, credits, bills)
            db.execute("INSERT INTO ramp_credit_binding VALUES(?,?,?)",
                       (tenant, binding["credit_id"], _json(binding)))
        return dict(credit_id=binding["credit_id"], status="LINKED", actual_recovery=None)

    def _project(self, db, tenant, binding, snapshot, credits, bills):
        if snapshot["source"] != Source.RAMP.value:
            _fail("REPLAY_CANNOT_CONFIRM_NATIVE_LINK")
        if "bills:read" not in (snapshot["scopes"] or []):
            _fail("SCOPE_UNCONFIRMED")
        credit = credits.get(binding["credit_id"])
        if not credit:
            _fail("SPARSE_LINKED_CREDIT")
        if credit["archived_at"] is not None:
            _fail("ARCHIVED_CREDIT")
        if credit["unit"] != (binding["currency"], 100):
            _fail("CROSS_CURRENCY")
        if credit["vendor_id"] != binding["vendor_id"]:
            _fail("VENDOR_CONFLICT")
        award = db.execute("""SELECT a.*,s.vendor_id,s.account_id,s.product_id,s.contract_id,
            s.contract_version,s.currency FROM allocation_award a
            JOIN allocation_scope s ON s.scope_id=a.scope_id WHERE a.tenant=? AND a.id=?""",
                           (tenant, binding["award_id"])).fetchone()
        if not award:
            _fail("INDEPENDENT_AWARD_REQUIRED")
        for key in SCOPE_FIELDS:
            if award[key] != binding[key]:
                _fail("AWARD_SCOPE_CONFLICT")
        if (award["source"] != binding["award_source"] or
                award["source_ref"] != binding["award_source_ref"] or award["memo_ref"] != binding["memo_ref"]):
            _fail("AWARD_PROVENANCE_CONFLICT")
        # Every bill needs an already verified eligible opening balance. No synthetic
        # bill or inferred capacity is inserted by this sync.
        for bill_id in set(credit["links"]) | {binding["bill_id"]}:
            bill = bills.get(bill_id)
            if not bill:
                _fail("SPARSE_BILL_READBACK")
            _same_provider_scope(credit, bill)
            if bill["archived_at"] is not None or bill["status"] not in ("OPEN", "PAID"):
                _fail("ARCHIVED_OR_UNKNOWN_BILL")
            local = db.execute("SELECT * FROM allocation_bill WHERE tenant=? AND id=?", (tenant, bill_id)).fetchone()
            if not local or local["source"] != Source.RAMP.value or local["scope_id"] != award["scope_id"]:
                _fail("VERIFIED_BILL_SCOPE_REQUIRED")
            if local["source_ref"] != bill_id or local["amount_cents"] != bill["total"]:
                _fail("BILL_CAPACITY_CONFLICT")
            if bill_id in credit["links"] and bill["links"].get(credit["id"]) != credit["links"][bill_id]:
                _fail("RECIPROCAL_CONFLICT")
            # Provider applications absent from this ledger still consume bill capacity.
            ledger_pairs = dict(db.execute("""SELECT credit_id,SUM(amount_cents) FROM allocation_application
                WHERE tenant=? AND bill_id=? GROUP BY credit_id""", (tenant, bill_id)).fetchall())
            if any(bill["links"].get(cid, 0) < value for cid, value in ledger_pairs.items()):
                _fail("DECREASING_BILL_APPLICATION")
            if sum(bill["links"].values()) > local["eligible_cents"]:
                _fail("BILL_ELIGIBLE_OVERCAPACITY")
        _record(db, "credit", tenant, dict(
            **{k: binding[k] for k in SCOPE_FIELDS}, id=credit["id"], source=Source.RAMP.value,
            source_ref=credit["id"], memo_ref=binding["memo_ref"], award_id=binding["award_id"],
            amount_cents=credit["total"], effective_date=credit["effective_date"]))
        for bill_id, amount in credit["links"].items():
            ident = sha256(_json([snapshot["id"], credit["id"], bill_id]).encode()).hexdigest()
            _observe(db, tenant, dict(id="credit-sync:" + ident, credit_id=credit["id"], bill_id=bill_id,
                source=Source.RAMP.value, source_ref=f"ramp:{credit['id']}:{bill_id}", amount_cents=amount,
                observed_at=snapshot["observed_at"], effective_date=snapshot["observed_at"][:10]))

    def history(self, tenant):
        with _connect(self.path) as db:
            return [dict(self._receipt(r), observed_at=r["observed_at"], digest=r["digest"])
                    for r in db.execute("SELECT * FROM ramp_credit_snapshot WHERE tenant=? ORDER BY sequence",
                                        (canonical(tenant),))]

    def summary(self, tenant, *, as_of=None):
        tenant = canonical(tenant)
        now = as_of or datetime.now(timezone.utc).isoformat()
        with _connect(self.path) as db:
            row = db.execute("SELECT * FROM ramp_credit_snapshot WHERE tenant=? ORDER BY observed_at DESC,sequence DESC LIMIT 1",
                             (tenant,)).fetchone()
            bindings = {r["credit_id"] for r in db.execute(
                "SELECT credit_id FROM ramp_credit_binding WHERE tenant=?", (tenant,))}
            amounts = db.execute("""SELECT COALESCE(SUM(c.amount_cents),0) FROM allocation_credit c
                JOIN ramp_credit_binding b ON b.tenant=c.tenant AND b.credit_id=c.id WHERE c.tenant=?""", (tenant,)).fetchone()[0]
            applied = db.execute("""SELECT COALESCE(SUM(a.amount_cents),0) FROM allocation_application a
                JOIN ramp_credit_binding b ON b.tenant=a.tenant AND b.credit_id=a.credit_id WHERE a.tenant=?""", (tenant,)).fetchone()[0]
            unlinked_awards = db.execute("""SELECT COUNT(*) FROM allocation_award a WHERE a.tenant=?
                AND NOT EXISTS (SELECT 1 FROM allocation_credit c JOIN ramp_credit_binding b
                ON b.tenant=c.tenant AND b.credit_id=c.id WHERE c.tenant=a.tenant AND c.award_id=a.id)""", (tenant,)).fetchone()[0]
            quarantined = self._quarantined(db, tenant)
        result = dict(status="UNAVAILABLE", observed_at=None, captured_credits=None,
                      unmatched_credits=None, linked_credits=len(bindings), recorded_cents=amounts,
                      applied_cents=applied, currency="USD", awards_without_native_credit=unlinked_awards,
                      claimed_only=None, claims_balance=None, actual_recovery=None,
                      claims_status="NOT_SUPPLIED", award_provenance=Source.VENDOR.value,
                      recovery_status="UNVERIFIED",
                      quarantined=quarantined,
                      external_writes=False, amounts_are_historical=True, observed_totals=[], issues=[])
        if not row:
            return result
        snapshot = json.loads(row["payload"])
        result.update(status=row["status"], observed_at=row["observed_at"], issues=json.loads(row["issues"]))
        if quarantined and row["status"] != "CONFLICT":
            result.update(status="CONFLICT", issues=["PRIOR_CONFLICT_REQUIRES_REVIEW"])
        if snapshot["available"] is True and snapshot["credits"] is not None:
            result["captured_credits"] = len(snapshot["credits"])
            result["unmatched_credits"] = sum(r["id"] not in bindings for r in snapshot["credits"])
        if not _fresh(snapshot, now):
            result["freshness"] = "STALE_OR_FUTURE"
        else:
            result["freshness"] = "FRESH"
        if not quarantined and row["status"] in ("RECORDED", "EMPTY", "PARTIAL", "STALE"):
            credits, _ = _facts(snapshot)
            totals = {}
            for credit in credits.values():
                key = credit["unit"]
                item = totals.setdefault(key, dict(currency=key[0], minor_unit_conversion_rate=key[1],
                    recorded_minor=0, provider_applied_minor=0, applied_bills_minor=0,
                    applied_drafts_minor=0, remaining_minor=0, archived_credits=0))
                for name, value in (("recorded_minor", credit["total"]), ("provider_applied_minor", credit["applied"]),
                                    ("applied_bills_minor", sum(credit["links"].values())),
                                    ("applied_drafts_minor", sum(credit["drafts"].values())),
                                    ("remaining_minor", credit["remaining"]),
                                    ("archived_credits", int(credit["archived_at"] is not None))):
                    item[name] += value
            result["observed_totals"] = [totals[k] for k in sorted(totals)]
        return result


def main(argv=None):
    """Offline CLI: only explicit local imports, links and aggregate reads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--as-of", help="Explicit offline replay clock (timezone-aware ISO instant)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("import", "link"):
        commands.add_parser(name).add_argument("file", type=Path)
    commands.add_parser("summary")
    args = parser.parse_args(argv)
    sync = RampCreditSync(args.db)
    try:
        if args.command == "summary":
            result = sync.summary(args.tenant, as_of=args.as_of)
        else:
            data = json.loads(args.file.read_text())
            method = sync.import_snapshot if args.command == "import" else sync.link_award
            result = method(args.tenant, data, as_of=args.as_of)
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(2, "Credit sync rejected local input; no remote action performed.\n")
    print(_json(result))
    return 0


if __name__ == "__main__":
    main()
