"""Demo line: several verified Ramp bills, their match to walkthrough invoices, and Uptime's notes.

Nothing here computes money. A match copies the walkthrough's own decimal strings; the stage
follows the walkthrough ledger. A note is posted only through the scoped sandbox provider's
fixed comment call, once per bill and kind, and read back before it is reported as posted.
A refresh re-reads Ramp read-only and re-packages through the same code as the scripts.
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
from threading import RLock

from .ramp import RampError
from .ramp_context import DEMO_BILL_URL, VERIFIED_RECORD, package_verified_excerpt, verified_record_from
from .ramp_webhooks import utcnow
from .ramp_workflow import DEMO_NOTE_SHAPES, PREFIX, ScopedSandboxWorkflowProvider, _comment_body
from .storage import database

NOTE_KINDS = tuple(DEMO_NOTE_SHAPES)
NOTE_SCOPES = frozenset({"bills:read", "bills:write"})
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
STAGES = (("applied", "APPLIED"), ("posted", "POSTED"), ("awarded", "AWARDED"), ("claimed", "CLAIMED"))
NOTES_FOR = {"service_credit": ("possible_credit", "credit_applied"), "price_exception": ("price_exception",)}
RETRY_AFTER = timedelta(seconds=60)


class NoteRefused(Exception):
    """One plain sentence for the person; never carries provider bodies or credentials."""

    def __init__(self, sentence, status=409):
        super().__init__(sentence)
        self.status = status


# --- Loading ----------------------------------------------------------------------------

def _load(directories=()):
    """(excerpt body, verified view) for the packaged DocuSign bill, then each verifying ``*.json``."""
    seen, entries = set(), []
    paths = [VERIFIED_RECORD]
    for folder in directories:
        folder = Path(folder)
        if folder.is_dir():
            paths.extend(sorted(p for p in folder.glob("*.json") if p.is_file()))
    for path in paths:
        try:
            body = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            continue
        record = verified_record_from(body)
        if record is None or body["excerpt_checksum"] in seen:
            continue
        seen.add(body["excerpt_checksum"])
        entries.append((body, record))
    return entries


def load_verified_records(directories=()):
    return [record for _, record in _load(directories)]


# --- Matching ---------------------------------------------------------------------------

def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _nonzero(value):
    number = _decimal(value)
    return number is not None and number != 0


def _same_invoice(context, invoice):
    amount = context.get("amount") or {}
    total = _decimal(invoice.total)
    return (context.get("vendor_name") == invoice.vendor and context.get("invoice_number") == invoice.id
            and amount.get("currency") == invoice.currency and total is not None
            and _decimal(amount.get("amount")) == total)


def _cite(citation):
    return " · ".join(x for x in (citation.get("label"), citation.get("ref")) if x)


def _inputs(month_view):
    values = month_view.get("inputs") or {}
    rows = []
    for key, label, fmt in (("eligible_downtime_minutes", "Eligible downtime minutes", "{}"),
                            ("completed_steps", "Completed steps below target", "{}"),
                            ("credit_percent", "Credit percent", "{}%"),
                            ("governing_fee", "Governing monthly fee", values.get("currency", "") + " {}")):
        if values.get(key) is not None:
            rows.append({"label": label, "value": fmt.format(values[key]).strip()})
    return rows


def ramp_credit(body, record):
    """Ramp's own credit read-back for this bill: confirmed only on both the bill and the credit."""
    report = record["ramp_context"].get("credit_links") or {}
    if report.get("status") == "NO_APPLIED_CREDITS":
        return {"status": "NONE", "amount": None}
    if report.get("status") != "VERIFIED_APPLICATIONS":
        return {"status": "UNKNOWN", "amount": None}
    verified = [link["credit_id"] for link in report.get("links") or [] if link["state"] == "VERIFIED_BOTH_SIDES"]
    sides = [a for a in body["records"]["bill"].get("applied_credits") or [] if a["credit_id"] in verified]
    amount = sides[0]["amount"].get("amount") if len(sides) == 1 else None
    number = _decimal(amount)
    return {"status": "APPLIED_CONFIRMED", "amount": None if number is None else f"{number:.2f}"}


def credit_match(body, record, invoice, view, agreement):
    ledger, claim = view["ledger"], view["claim"]
    month = next((m for m in view["months"] if m["month"] == claim["month"]), {})
    stage, credit = "ESTIMATED", None
    for key, name in STAGES:
        if _nonzero(ledger.get(key)):
            stage, credit = name, ledger[key]
            break
    if credit is None:
        credit = ledger.get("estimated") or claim.get("amount") or month.get("amount")
    applied = ledger.get("applied") or "0.00"
    bill = ledger.get("bill") or {}
    if not _nonzero(applied):
        remaining = str(invoice.total)
    elif bill.get("id") == invoice.id:
        remaining = bill.get("outstanding_amount")
    else:
        remaining = None
    clause = next((c for c in month.get("citations") or [] if "service credit" in (c.get("quote") or "")), {})
    offers = view.get("next_actions") or []
    return {"kind": "service_credit", "basis": ["vendor_name", "invoice_number", "amount"],
            "invoice": {"id": invoice.id, "vendor": invoice.vendor, "total": str(invoice.total),
                        "currency": invoice.currency},
            "credit": {"amount": credit, "currency": ledger.get("currency") or invoice.currency,
                       "service_month": claim["month"], "stage": stage},
            "agreement": {"id": agreement, "clause": clause.get("quote"), "citation": _cite(clause) or None},
            "inputs": _inputs(month),
            "balance": {"invoice": str(invoice.total), "credit_applied": applied, "remaining": remaining},
            "ramp_credit": ramp_credit(body, record),
            "next_action": {"label": offers[0]["label"]} if offers else None,
            "route": "recovery"}


def price_match(invoice, view, agreement):
    finding = view["price_finding"]
    if finding.get("invoice_id") != invoice.id:
        return None
    lines = finding.get("lines") or []
    line = lines[0] if len(lines) == 1 else {}
    expected = line.get("expected")
    wanted = [expected] + ([f"{_decimal(expected):,.2f}"] if _decimal(expected) is not None else []) if expected else []
    cited = finding.get("citations") or []
    clause = next((c for c in cited if any(w in (c.get("quote") or "") for w in wanted)), cited[0] if cited else {})
    applied = finding.get("credit_applied") or "0.00"
    known = finding.get("amount") is not None
    return {"kind": "price_exception", "basis": ["vendor_name", "invoice_number", "amount"],
            "invoice": {"id": invoice.id, "vendor": invoice.vendor, "total": str(invoice.total),
                        "currency": invoice.currency},
            "exception": {"amount": finding.get("amount"), "currency": finding.get("currency"),
                          "billed": line.get("billed"), "expected": expected,
                          "basis": clause.get("label"),
                          "state": "OPEN" if known and not _nonzero(applied) else finding.get("state"),
                          "review_stage": finding.get("state")},
            "agreement": {"id": agreement, "clause": clause.get("quote"), "citation": _cite(clause) or None},
            "inputs": [],
            "balance": {"invoice": str(invoice.total), "credit_applied": applied,
                        "remaining": str(invoice.total) if not _nonzero(applied) else None},
            "next_action": None,
            "route": "recovery"}


# --- Note text --------------------------------------------------------------------------

def _money(currency, value):
    number = _decimal(value)
    if number is None or not currency:
        return None
    return f"{currency} {number:,.2f}"


def note_text(kind, match):
    if kind not in NOTES_FOR[match["kind"]]:
        raise NoteRefused("That note does not apply to this bill.")
    if kind == "price_exception":
        exception = match["exception"]
        amount = _money(exception["currency"], exception["amount"])
        if amount is None or not exception["basis"] or exception["state"] != "OPEN":
            raise NoteRefused("The price exception on this bill is not known yet, so Uptime has no note to post.")
        return (f"Uptime: this bill is {amount} above the contracted rate ({exception['basis']}). "
                "Review it in Uptime before payment.")
    credit, balance = match["credit"], match["balance"]
    amount = _money(credit["currency"], credit["amount"])
    if amount is None:
        raise NoteRefused("The credit amount is not known yet, so Uptime has no note to post.")
    if kind == "possible_credit":
        year, month = credit["service_month"].split("-")
        return (f"Uptime: this bill may be eligible for a {amount} service credit under agreement "
                f"{match['agreement']['id']} ({MONTHS[int(month) - 1]} {year} availability). "
                "A claim is being prepared in Uptime.")
    remaining = _money(match["invoice"]["currency"], balance["remaining"])
    if credit["stage"] != "APPLIED" or remaining is None:
        raise NoteRefused("The credit has not been applied to this invoice in Uptime yet.")
    return (f"Uptime: the vendor awarded a {amount} service credit and it has been applied to this invoice "
            f"in Uptime. Remaining balance {remaining}.")


# --- Live sandbox access (credential from this server's environment only) ----------------

def _sandbox():
    from .ramp import SandboxRampProvider
    if os.environ.get("RAMP_ENV") != "sandbox":
        raise NoteRefused("This server was not started with RAMP_ENV=sandbox, so Uptime cannot reach Ramp.")
    try:
        return SandboxRampProvider()
    except RampError:
        raise NoteRefused("No Ramp sandbox credential is available to this server; start it with "
                          "UPTIME_RAMP_CREDENTIAL_FILE set to the credential file.") from None


def sandbox_provider(business_id):
    """The live sandbox comment provider."""
    ramp = _sandbox()
    try:
        token = ramp.token(NOTE_SCOPES)
    except RampError:
        raise NoteRefused("Ramp did not issue a token with bills:read and bills:write for this credential.") from None
    missing = sorted(NOTE_SCOPES - token.granted)
    if missing:
        raise NoteRefused("The Ramp credential was not granted " + " and ".join(missing)
                          + ", so Uptime cannot post the note.")
    import httpx
    return ScopedSandboxWorkflowProvider(business_id=business_id, access_token=token.value,
                                         granted_scopes=NOTE_SCOPES, observed_at=utcnow().isoformat(),
                                         http=httpx.Client(), transport_provenance="LIVE_RAMP_SANDBOX")


def sandbox_reader():
    """The live read-only sandbox provider used by the existing read scripts."""
    return _sandbox()


# --- Notes, refresh and automatic notes ---------------------------------------------------

class RampDemo:
    def __init__(self, app, bench, *, record_dirs=(), provider_factory=None, notes_mode=None, reader_factory=None):
        self.app, self.bench, self.path, self.tenant = app, bench, bench.path, bench.tenant
        self.record_dirs = tuple(Path(d) for d in record_dirs)
        self.provider_factory = provider_factory
        self.notes_mode = notes_mode or ("manual" if provider_factory is not None else "off")
        if self.notes_mode not in {"off", "manual", "auto"} or (self.notes_mode != "off") != (provider_factory is not None):
            raise ValueError("Ramp notes need a provider and a mode of manual or auto.")
        self.reader_factory = reader_factory
        self.lock = RLock()
        self.live = {}            # bill_id -> (body, record) from a refresh, in memory only
        self.errors = {}          # (bill_id, kind) -> {"bill_id", "kind", "sentence", "at"}
        self._signature, self._failed_at = None, None
        with database(self.path) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS ramp_demo_note (
                tenant TEXT NOT NULL, bill_id TEXT NOT NULL, kind TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('POSTING','UNCONFIRMED','POSTED')),
                text TEXT NOT NULL, comment_id TEXT, at TEXT, PRIMARY KEY(tenant,bill_id,kind))""")

    def system_principal(self):
        from .auth import SCRIPT
        from .contracts import Principal
        return Principal(self.tenant, SCRIPT, "reviewer")

    def _notes(self):
        with database(self.path) as db:
            return [dict(r) for r in db.execute("SELECT * FROM ramp_demo_note WHERE tenant=?", (self.tenant,))]

    def _context(self, principal):
        workflow = getattr(self.app.state, "workflow", None)
        if workflow is None:
            return None
        return {"view": workflow.view(principal)["workflow"], "agreement": workflow.package["overlay"]["agreement"],
                "credit": workflow.settlement["invoice"], "price": workflow.months[workflow.bill_month]["invoice"]}

    @staticmethod
    def _match(body, record, context):
        if context is None:
            return None
        ramp = record["ramp_context"]
        if _same_invoice(ramp, context["credit"]):
            return credit_match(body, record, context["credit"], context["view"], context["agreement"])
        if _same_invoice(ramp, context["price"]):
            return price_match(context["price"], context["view"], context["agreement"])
        return None

    def _entries(self):
        result = []
        for body, record in _load(self.record_dirs):
            bill_id = record["ramp_context"]["object_id"]
            if bill_id in self.live:
                result.append((*self.live[bill_id], True))
            else:
                result.append((body, record, False))
        return result

    def records(self, principal):
        context = self._context(principal)
        posted = {(n["bill_id"], n["comment_id"]): n for n in self._notes() if n["comment_id"]}
        result = []
        for body, record, live in self._entries():
            bill_id = record["ramp_context"]["object_id"]
            notes, ids = [], set()
            for comment in record["ramp_context"]["discussion"]:
                ours = posted.get((bill_id, comment["comment_id"]))
                ids.add(comment["comment_id"])
                notes.append({"id": comment["comment_id"], "at": comment["created_at"],
                              "by": "UPTIME" if ours else "RAMP", "kind": ours["kind"] if ours else None})
            for (bill, ident), note in posted.items():
                if bill == bill_id and ident not in ids and note["status"] == "POSTED":
                    notes.append({"id": ident, "at": note["at"], "by": "UPTIME", "kind": note["kind"]})
            notes.sort(key=lambda n: n["at"] or "")
            result.append({**record, "match": self._match(body, record, context), "notes": notes,
                           "read": {"at": record["capture"]["observed_at"], "live": live}})
        return result

    def note_errors(self):
        return sorted(self.errors.values(), key=lambda e: e["at"])

    # Manual and automatic posting share one path and one lock.
    def post_note(self, principal, bill_id, kind, records=None):
        if self.provider_factory is None:
            raise NoteRefused("Posting notes to Ramp is not turned on for this server.", 404)
        if kind not in NOTE_KINDS:
            raise NoteRefused("The note kind must be possible_credit, credit_applied or price_exception.", 400)
        with self.lock:
            records = records if records is not None else self.records(principal)
            record = next((r for r in records if r["ramp_context"]["object_id"] == bill_id), None)
            if record is None:
                raise NoteRefused("No verified Ramp bill with that id is loaded in this workspace.", 404)
            with database(self.path) as db:
                row = db.execute("SELECT * FROM ramp_demo_note WHERE tenant=? AND bill_id=? AND kind=?",
                                 (self.tenant, bill_id, kind)).fetchone()
            if row is not None and row["status"] == "POSTED":
                return self._result(row)
            if row is None:
                if record["match"] is None:
                    raise NoteRefused("This Ramp bill does not match a walkthrough invoice, so Uptime has no note for it.")
                text = note_text(kind, record["match"])
            else:
                text = row["text"]
            plan = {"object_type": "bills", "object_id": bill_id, "path": f"{PREFIX}/comments/bills/{bill_id}",
                    "demo_note_kind": kind, "demo_note_text": text}
            plan["body"] = _comment_body(plan)
            provider = self.provider_factory(record["capture"]["business_id"])
            try:
                # A note with exactly this text already on the bill is adopted, never posted twice: an earlier attempt
                # that did not finish, or the same note left by an earlier workspace for the same bill.
                found = self._find(provider, bill_id, text, row["comment_id"] if row is not None else None)
                if found is not None:
                    if row is None:
                        self._save(bill_id, kind, "UNCONFIRMED", text, found["id"])
                    return self._mark_posted(bill_id, kind, found)
                if row is not None and row["status"] == "UNCONFIRMED":
                    raise NoteRefused("Ramp accepted the note earlier but it does not appear on the bill yet; try again shortly.")
                self._save(bill_id, kind, "POSTING", text)
                try:
                    created = provider.post_comment(plan)
                except RampError:
                    raise NoteRefused("Ramp did not confirm the note; post again to check the bill and retry.") from None
                ident = created.get("id") if isinstance(created, dict) and isinstance(created.get("id"), str) else None
                self._save(bill_id, kind, "UNCONFIRMED", text, ident)
                found = self._find(provider, bill_id, text, ident)
                if found is None:
                    raise NoteRefused("Ramp accepted the note but it did not appear when the bill was read back; try again shortly.")
                return self._mark_posted(bill_id, kind, found)
            finally:
                close = getattr(getattr(provider, "http", None), "close", None)
                if callable(close):
                    close()

    @staticmethod
    def _wanted(match):
        kinds = list(NOTES_FOR[match["kind"]])
        if match["kind"] == "service_credit" and match["credit"]["stage"] != "APPLIED":
            kinds.remove("credit_applied")
        return kinds

    def _signature_of(self, records):
        return tuple(sorted((r["ramp_context"]["object_id"], r["match"]["kind"],
                             r["match"].get("credit", {}).get("stage", "")) for r in records if r["match"]))

    def auto_sync(self, principal=None, records=None):
        """Post every note a matched bill should have and does not; never raises."""
        principal = principal or self.system_principal()
        posted, failed = [], []
        try:
            with self.lock:
                records = records if records is not None else self.records(principal)
                done = {(n["bill_id"], n["kind"]) for n in self._notes() if n["status"] == "POSTED"}
                for record in records:
                    if record["match"] is None:
                        continue
                    bill_id = record["ramp_context"]["object_id"]
                    for kind in self._wanted(record["match"]):
                        if (bill_id, kind) in done:
                            continue
                        try:
                            self.post_note(principal, bill_id, kind, records=records)
                            self.errors.pop((bill_id, kind), None)
                            posted.append((bill_id, kind))
                        except NoteRefused as refused:
                            failed.append(self._fail(bill_id, kind, str(refused)))
                        except Exception:  # noqa: BLE001 - a note must never break start-up or a decision
                            failed.append(self._fail(bill_id, kind, "Uptime could not post this note to Ramp."))
                self._signature = self._signature_of(records)
        except Exception:  # noqa: BLE001
            failed.append(self._fail(None, None, "Uptime could not check which notes to post to Ramp."))
        self._failed_at = utcnow() if failed else None
        return {"posted": posted, "failed": failed}

    def _fail(self, bill_id, kind, sentence):
        error = {"bill_id": bill_id, "kind": kind, "sentence": sentence, "at": utcnow().isoformat()}
        self.errors[(bill_id, kind)] = error
        return error

    def auto_check(self, principal=None, records=None):
        """In auto mode, post when the matched bills or a credit stage changed, or to retry a failure."""
        if self.notes_mode != "auto":
            return None
        try:
            principal = principal or self.system_principal()
            records = records if records is not None else self.records(principal)
            retry = self._failed_at is not None and utcnow() - self._failed_at >= RETRY_AFTER
            if self._signature_of(records) == self._signature and not retry:
                return None
        except Exception:  # noqa: BLE001
            return None
        return self.auto_sync(principal, records)

    def refresh(self, principal):
        if self.reader_factory is None:
            raise NoteRefused("Reading Ramp again is not turned on for this server.", 404)
        from .ramp_installation import verify_browser_bill
        from .ramp_records import sync_records
        with self.lock:
            matched = [r for r in self.records(principal) if r["match"] is not None]
            if not matched:
                raise NoteRefused("No matched Ramp bill is loaded, so there is nothing to read again.")
            reader = self.reader_factory()
            try:
                capture = sync_records(reader, page_size=100, max_pages=5, detail_limit=100)
            except RampError:
                raise NoteRefused("Ramp could not be read just now; the earlier reads are still shown.") from None
            errors = []
            for record in matched:
                bill_id, business = record["ramp_context"]["object_id"], record["capture"]["business_id"]
                try:
                    association = verify_browser_bill(reader, DEMO_BILL_URL + bill_id)
                    if association["business_id"] != business:
                        raise ValueError
                    body = package_verified_excerpt(capture, association)
                    fresh = verified_record_from(body)
                    if fresh is None:
                        raise ValueError
                    self.live[bill_id] = (body, fresh)
                except (RampError, ValueError, KeyError, TypeError, StopIteration):
                    errors.append({"bill_id": bill_id,
                                   "sentence": "This bill could not be read again from Ramp; its earlier read is still shown."})
            records = self.records(principal)
        self.auto_check(principal, records)
        return {"verified_records": self.records(principal), "read_errors": errors}

    @staticmethod
    def _find(provider, bill_id, text, ident):
        try:
            rows = provider.comments("bills", bill_id)
        except RampError:
            return None
        for row in rows:
            if (isinstance(row, dict) and isinstance(row.get("id"), str) and row.get("message") == text
                    and (ident is None or row["id"] == ident)):
                return row
        return None

    def _save(self, bill_id, kind, status, text, ident=None, at=None):
        with database(self.path) as db, db:
            db.execute("INSERT OR REPLACE INTO ramp_demo_note VALUES(?,?,?,?,?,?,?)",
                       (self.tenant, bill_id, kind, status, text, ident, at))

    def _mark_posted(self, bill_id, kind, comment):
        with database(self.path) as db:
            text = db.execute("SELECT text FROM ramp_demo_note WHERE tenant=? AND bill_id=? AND kind=?",
                              (self.tenant, bill_id, kind)).fetchone()[0]
        self._save(bill_id, kind, "POSTED", text, comment["id"], comment.get("created_at"))
        with database(self.path) as db:
            return self._result(db.execute("SELECT * FROM ramp_demo_note WHERE tenant=? AND bill_id=? AND kind=?",
                                           (self.tenant, bill_id, kind)).fetchone())

    @staticmethod
    def _result(row):
        return {"status": "POSTED", "comment_id": row["comment_id"], "at": row["at"], "text": row["text"]}


def _plain(call):
    from fastapi.responses import JSONResponse
    try:
        return call()
    except NoteRefused as refused:
        return JSONResponse({"detail": str(refused)}, refused.status)


def register_ramp_demo(app, demo, auth):
    """Mount the demo routes the server was started with."""
    from typing import Literal

    from fastapi import Depends
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, ConfigDict
    from starlette.concurrency import run_in_threadpool

    if demo.provider_factory is not None:
        class Note(BaseModel):
            model_config = ConfigDict(extra="forbid")
            bill_id: str
            kind: Literal["possible_credit", "credit_applied", "price_exception"]

        @app.post("/api/ramp/notes")
        def post_note(body: Note, principal=Depends(auth.reviewer)):
            demo.bench.require_tenant(principal)
            if not re.fullmatch(r"[0-9a-f-]{36}", body.bill_id):
                return JSONResponse({"detail": "The bill id must be a Ramp bill id."}, 400)
            return _plain(lambda: demo.post_note(principal, body.bill_id, body.kind))

    if demo.reader_factory is not None:
        from .correspondence_types import Empty

        @app.post("/api/ramp/refresh")
        def refresh(body: Empty, principal=Depends(auth.reviewer)):
            demo.bench.require_tenant(principal)
            return _plain(lambda: demo.refresh(principal))

    if demo.notes_mode == "auto":
        @app.middleware("http")
        async def notes_after_decisions(request, call_next):
            response = await call_next(request)
            if (request.method == "POST" and request.url.path.startswith("/api/workspace/workflow/actions/")
                    and response.status_code == 200):
                # A note never breaks a decision: auto_check records failures and never raises.
                await run_in_threadpool(demo.auto_check)
            return response
