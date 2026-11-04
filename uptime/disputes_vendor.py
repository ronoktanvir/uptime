"""Isolated deterministic vendor. Receives a submitted ticket, never a case or oracle.

Simulates the ordinary Twilio Services APIs availability branch only. The vendor
ledger is synthetic, not a live status export. No transport or credentials.
"""
import json
from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal

from uptime.contracts import Source, fingerprint
from uptime.disputes_wire import CENT, FIXTURES, Reply, Ticket, deadline


def _valid_attachment(ticket, document, record):
    body = document.body
    return (
        document.fact.tenant == ticket.tenant
        and document.fact.source == Source.REPLAY
        and document.fact.ref == body.get("ref")
        and document.fact.kind == body.get("kind")
        and document.fact.observed_at == body.get("end")
        and record["document_registry"].get(document.fact.ref) == document.fact.digest
        and fingerprint(body) == document.fact.digest
        and all(body.get(key) == getattr(ticket, key)
                for key in ("account", "month", "product", "region", "start", "end"))
    )


def decide(ticket: Ticket, record: dict, at: datetime) -> Reply:
    """Evaluate a ticket against the vendor's private record for this account."""
    if at >= deadline(ticket.month):
        return Reply("WINDOW_CLOSED", "The local UTC filing window has closed.", "§3")
    if ticket.channel != "Twilio Customer Support (simulation)" or ticket.subject != "SLA Claim":
        return Reply("INCORRECT_FILING", "Check the support channel and ticket subject.", "§3")
    if record["plan"] != "standard" or any(
        record[key] != getattr(ticket, key) for key in ("month", "product", "region", "start", "end")
    ):
        return Reply("CONTESTED_SCOPE", "Account, edition or incident scope needs review.", "§§1, 3")
    if any(not _valid_attachment(ticket, doc, record) for doc in ticket.documents):
        return Reply("UNVERIFIED_DOCUMENT", "A submitted artifact does not match the scoped archive.", "§3")
    kinds = {doc.fact.kind for doc in ticket.documents}
    if not {"status_summary", "component_record"} <= kinds:
        missing = "status_summary" if "status_summary" not in kinds else "component_record"
        return Reply("DOCUMENTATION_NEEDED",
                     "The submitted record does not yet document the affected component and interval.",
                     "§3", needed_kind=missing)

    start = datetime.fromisoformat(record["start"])
    end = datetime.fromisoformat(record["end"])
    if record["incident_class"] == "maintenance":
        notice = record["notice_sent_at"]
        if notice and datetime.fromisoformat(notice) <= start - timedelta(hours=24):
            return Reply("MAINTENANCE_EXCLUDED",
                         "Scheduled maintenance was announced at least 24 hours in advance.", "§4(d)")
        if not notice:
            return Reply("CONTESTED_SCOPE", "Notice timing is unverified.", "§4(d)")
    elif record["incident_class"] != "outage":
        return Reply("CONTESTED_SCOPE", "The vendor cannot substantiate when maintenance notice was given.", "§4(d)")

    # Records cover one whole-minute interval. Unsupported period/timing stays unresolved.
    length = end - start
    if (length <= timedelta() or length.microseconds or length.seconds % 60
            or start.strftime("%Y-%m") != ticket.month
            or (end - timedelta(microseconds=1)).strftime("%Y-%m") != ticket.month):
        return Reply("CONTESTED_SCOPE", "The fixture cannot establish a covered whole-minute interval.", "§1")
    minutes = length // timedelta(minutes=1)
    total = monthrange(start.year, start.month)[1] * 24 * 60
    if minutes < 5 or Decimal(total - minutes) * 100 >= Decimal("99.95") * total:
        return Reply("THRESHOLD_MET", "Countable minutes do not breach the ordinary API threshold.", "§§1, 3, 4(g)")

    basis = sum((Decimal(line["usd"]) for line in record["lines"] if line["kind"] == "affected_api"), Decimal(0))
    requested = Decimal(ticket.requested)
    ceiling = (basis * Decimal("0.10")).quantize(CENT)
    if requested <= 0 or ceiling <= 0:
        return Reply("CONTESTED_SCOPE", "No positive covered fee basis is confirmed.", "§§1, 3")
    amount = min(requested, ceiling)
    if amount < requested:
        return Reply("PARTIAL_AWARD", f"Only USD {basis:.2f} of affected charges is substantiated.", "§§1, 3", f"{amount:.2f}")
    return Reply("AWARD", f"Confirmed affected charges of USD {basis:.2f} support a future service credit.", "§§1, 3", f"{amount:.2f}")


def review(ticket: Ticket, at: datetime) -> Reply:
    records = json.loads((FIXTURES / "simulator" / "records.json").read_text())
    record = records.get(ticket.account)
    if record is None:
        return Reply("CONTESTED_SCOPE", "The vendor cannot map this account.", "§1")
    return decide(ticket, record, at)
