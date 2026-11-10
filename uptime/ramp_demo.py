"""Demo line: several verified Ramp bills, their match to the walkthrough invoice, and Uptime's notes.

Nothing here computes money. A match copies the walkthrough's own decimal strings; the stage
follows the walkthrough ledger. A note is posted only through the scoped sandbox provider's
fixed comment call, once per bill and kind, and read back before it is reported as posted.
"""

from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re

from .ramp import RampError
from .ramp_context import VERIFIED_RECORD, verified_record
from .ramp_webhooks import utcnow
from .ramp_workflow import DEMO_NOTE_SHAPES, PREFIX, ScopedSandboxWorkflowProvider, _comment_body
from .storage import database

NOTE_KINDS = tuple(DEMO_NOTE_SHAPES)
NOTE_SCOPES = frozenset({"bills:read", "bills:write"})
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
STAGES = (("applied", "APPLIED"), ("posted", "POSTED"), ("awarded", "AWARDED"), ("claimed", "CLAIMED"))


class NoteRefused(Exception):
    """One plain sentence for the person; never carries provider bodies or credentials."""

    def __init__(self, sentence, status=409):
        super().__init__(sentence)
        self.status = status


# --- Loading ----------------------------------------------------------------------------

def load_verified_records(directories=()):
    """The packaged DocuSign bill first, then every verifying ``*.json`` in the given folders."""
    seen, records = set(), []
    paths = [VERIFIED_RECORD]
    for folder in directories:
        folder = Path(folder)
        if folder.is_dir():
            paths.extend(sorted(p for p in folder.glob("*.json") if p.is_file()))
    for path in paths:
        record = verified_record(path)
        if record is None:
            continue
        key = record["capture"]["excerpt_checksum"]
        if key not in seen:
            seen.add(key)
            records.append(record)
    return records


# --- Matching ---------------------------------------------------------------------------

def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _nonzero(value):
    number = _decimal(value)
    return number is not None and number != 0


def _clause(month_view):
    citations = month_view.get("citations") or []
    chosen = next((c for c in citations if "service credit" in (c.get("quote") or "")), None)
    if chosen is None:
        return None, None
    return chosen["quote"], " · ".join(x for x in (chosen.get("label"), chosen.get("ref")) if x)


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


def invoice_match(record, invoice, view, agreement):
    """Exact vendor, invoice number and amount against the walkthrough invoice, or None."""
    context = record["ramp_context"]
    amount = context.get("amount") or {}
    total = _decimal(invoice.total)
    if (context.get("vendor_name") != invoice.vendor or context.get("invoice_number") != invoice.id
            or amount.get("currency") != invoice.currency or total is None
            or _decimal(amount.get("amount")) != total):
        return None
    workflow = view["workflow"]
    ledger, claim = workflow["ledger"], workflow["claim"]
    month = next((m for m in workflow["months"] if m["month"] == claim["month"]), {})
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
    clause, citation = _clause(month)
    offers = workflow.get("next_actions") or []
    return {"basis": ["vendor_name", "invoice_number", "amount"],
            "invoice": {"id": invoice.id, "vendor": invoice.vendor, "total": str(invoice.total),
                        "currency": invoice.currency},
            "credit": {"amount": credit, "currency": ledger.get("currency") or invoice.currency,
                       "service_month": claim["month"], "stage": stage},
            "agreement": {"id": agreement, "clause": clause, "citation": citation},
            "inputs": _inputs(month),
            "balance": {"invoice": str(invoice.total), "credit_applied": applied, "remaining": remaining},
            "next_action": {"label": offers[0]["label"]} if offers else None,
            "route": "overview"}


# --- Note text --------------------------------------------------------------------------

def _money(currency, value):
    number = _decimal(value)
    if number is None:
        return None
    return f"{currency} {number:,.2f}"


def note_text(kind, match):
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


# --- Provider -----------------------------------------------------------------------------

def sandbox_provider(business_id):
    """The live sandbox comment provider, from this server's own environment only."""
    from .ramp import SandboxRampProvider
    if os.environ.get("RAMP_ENV") != "sandbox":
        raise NoteRefused("This server was not started with RAMP_ENV=sandbox, so Uptime cannot post to Ramp.")
    try:
        ramp = SandboxRampProvider()
    except RampError:
        raise NoteRefused("No Ramp sandbox credential is available to this server; start it with "
                          "UPTIME_RAMP_CREDENTIAL_FILE set to the credential file.") from None
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


# --- Notes --------------------------------------------------------------------------------

class RampDemo:
    def __init__(self, app, bench, *, record_dirs=(), provider_factory=None):
        self.app, self.bench, self.path, self.tenant = app, bench, bench.path, bench.tenant
        self.record_dirs = tuple(Path(d) for d in record_dirs)
        self.provider_factory = provider_factory
        with database(self.path) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS ramp_demo_note (
                tenant TEXT NOT NULL, bill_id TEXT NOT NULL, kind TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('POSTING','UNCONFIRMED','POSTED')),
                text TEXT NOT NULL, comment_id TEXT, at TEXT, PRIMARY KEY(tenant,bill_id,kind))""")

    def _notes(self):
        with database(self.path) as db:
            return [dict(r) for r in db.execute("SELECT * FROM ramp_demo_note WHERE tenant=?", (self.tenant,))]

    def _view(self, principal):
        workflow = getattr(self.app.state, "workflow", None)
        if workflow is None:
            return None, None, None
        return workflow.view(principal), workflow.settlement["invoice"], workflow.package["overlay"]["agreement"]

    def records(self, principal):
        view, invoice, agreement = self._view(principal)
        posted = {(n["bill_id"], n["comment_id"]): n for n in self._notes() if n["comment_id"]}
        result = []
        for record in load_verified_records(self.record_dirs):
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
            match = invoice_match(record, invoice, view, agreement) if view is not None else None
            result.append({**record, "match": match, "notes": notes})
        return result

    def post_note(self, principal, bill_id, kind):
        if self.provider_factory is None:
            raise NoteRefused("Posting notes to Ramp is not turned on for this server.", 404)
        if kind not in NOTE_KINDS:
            raise NoteRefused("The note kind must be possible_credit or credit_applied.", 400)
        record = next((r for r in self.records(principal) if r["ramp_context"]["object_id"] == bill_id), None)
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
            if row is not None:
                # An earlier attempt did not finish: adopt it if Ramp has it, otherwise post again.
                found = self._find(provider, bill_id, text, row["comment_id"])
                if found is not None:
                    return self._mark_posted(bill_id, kind, found)
                if row["status"] == "UNCONFIRMED":
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


def register_ramp_notes(app, demo, auth):
    """``POST /api/ramp/notes``: mounted only when the server is started with notes turned on."""
    from typing import Literal

    from fastapi import Depends
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, ConfigDict

    class Note(BaseModel):
        model_config = ConfigDict(extra="forbid")
        bill_id: str
        kind: Literal["possible_credit", "credit_applied"]

    @app.post("/api/ramp/notes")
    def post_note(body: Note, principal=Depends(auth.reviewer)):
        demo.bench.require_tenant(principal)
        if not re.fullmatch(r"[0-9a-f-]{36}", body.bill_id):
            return JSONResponse({"detail": "The bill id must be a Ramp bill id."}, 400)
        try:
            return demo.post_note(principal, body.bill_id, body.kind)
        except NoteRefused as refused:
            return JSONResponse({"detail": str(refused)}, refused.status)
