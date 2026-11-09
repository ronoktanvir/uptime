"""Independent deterministic counterparty; no claimant imports or transport.

Private source records bind tenant/account/vendor and pinned minimized artifacts.
The component requirement is a simulator policy, not a universal SLA clause.
"""
import json
from calendar import monthrange
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext

from uptime.contracts import Source, fingerprint
from uptime.disputes_wire import CENT, DOCUMENT_FIELDS, FIXTURES, VERSION, Reply, Ticket, account_identity, canonical, deadline, instant


def _valid_attachment(ticket, document, record):
    try:
        return _attachment_fields_match(ticket, document, record)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return False


def _attachment_fields_match(ticket, document, record):
    body = document.body
    return (
        set(body) <= DOCUMENT_FIELDS
        and canonical(document.fact.ref)
        and document.fact.tenant == ticket.tenant
        and document.fact.source == Source.REPLAY
        and document.fact.ref == body.get("ref")
        and document.fact.kind == body.get("kind")
        and body.get("kind") in {"status_summary", "component_record"}
        and body.get("source") == Source.REPLAY
        and body.get("classification") == "redacted_replay"
        and body.get("origin") == "synthetic_status_archive"
        and document.fact.observed_at == body.get("observed_at", body.get("end"))
        and record["document_registry"].get(document.fact.ref) == document.fact.digest
        and fingerprint(body) == document.fact.digest
        and all(body.get(key) == getattr(ticket, key)
                for key in ("account", "month", "product", "region"))
        and all(instant(body[key]) == instant(getattr(ticket, key)) for key in ("start", "end"))
        and (body["kind"] != "component_record" or canonical(body.get("component_id"))
             and body["component_id"] == record.get("component_id"))
    )


def decide(ticket: Ticket, record: dict, at: datetime) -> Reply:
    """Adjudicate using independently provisioned vendor evidence."""
    if (any(not canonical(getattr(ticket, key)) for key in ("tenant", "account", "vendor", "product", "region"))
            or not all(account_identity(getattr(ticket, key)) for key in ("account", "vendor", "product"))
            or any(record.get(key) != getattr(ticket, key) for key in ("tenant", "account", "vendor", "governing_version"))
            or ticket.vendor != "Twilio" or ticket.governing_version != VERSION
            or ticket.obligation != "monthly_api_availability"):
        return Reply("CONTESTED_SCOPE", "Tenant, account, vendor or agreement binding is not established.", "§§1, 3")
    try:
        cutoff = deadline(ticket.month)
        first = datetime.strptime(ticket.month, "%Y-%m").replace(tzinfo=UTC)
        following = first + timedelta(days=monthrange(first.year, first.month)[1])
        start, end = instant(record["start"]), instant(record["end"])
        instant(ticket.start), instant(ticket.end)
        if first < datetime(2026, 4, 9, tzinfo=UTC) or not first <= start < end <= following or at.utcoffset() is None:
            raise ValueError
    except (ValueError, KeyError, TypeError, OverflowError):
        return Reply("CONTESTED_SCOPE", "Governing dates or supported period cannot be established.", "§1")
    if at >= cutoff:
        return Reply("WINDOW_CLOSED", "The local UTC filing window has closed.", "§3")
    if at < following:
        return Reply("INCORRECT_FILING", "The monthly filing period has not opened.", "§3")
    if ticket.channel != "Twilio Customer Support (simulation)" or ticket.subject != "SLA Claim":
        return Reply("INCORRECT_FILING", "Check the support channel and ticket subject.", "§3")
    if record["plan"] != "standard" or any(
        record[key] != getattr(ticket, key) for key in ("month", "product", "region")
    ) or any(instant(record[key]) != instant(getattr(ticket, key)) for key in ("start", "end")):
        return Reply("CONTESTED_SCOPE", "Account, edition or incident scope needs review.", "§§1, 3")
    if (len({doc.fact.ref for doc in ticket.documents}) != len(ticket.documents)
            or any(not _valid_attachment(ticket, doc, record) for doc in ticket.documents)):
        return Reply("UNVERIFIED_DOCUMENT", "A submitted artifact does not match the scoped archive.", "§3")
    kinds = {doc.fact.kind for doc in ticket.documents}
    if not {"status_summary", "component_record"} <= kinds:
        missing = "status_summary" if "status_summary" not in kinds else "component_record"
        return Reply("DOCUMENTATION_NEEDED", "The submitted record does not yet document the affected component and interval.",
                     "§3", needed_kind=missing)
    if record["incident_class"] == "maintenance":
        notice = record["notice_sent_at"]
        if notice and instant(notice) <= start - timedelta(hours=24):
            return Reply("MAINTENANCE_EXCLUDED", "Scheduled maintenance was announced at least 24 hours in advance.", "§4(d)")
        return Reply("CONTESTED_SCOPE", "Notice timing is unverified.", "§4(d)")
    if record["incident_class"] != "outage":
        return Reply("CONTESTED_SCOPE", "The vendor cannot substantiate when maintenance notice was given.", "§4(d)")
    length = end - start
    if length % timedelta(minutes=1):
        return Reply("CONTESTED_SCOPE", "The fixture cannot establish a covered whole-minute interval.", "§1")
    if length < timedelta(minutes=5) or length * 2000 <= following - first:
        return Reply("THRESHOLD_MET", "Countable minutes do not breach the ordinary API threshold.", "§§1, 3, 4(g)")
    try:
        with localcontext() as context:
            context.prec = 80
            lines = record["lines"]
            if (len({line["id"] for line in lines}) != len(lines)
                    or len({line["evidence_ref"] for line in lines}) != len(lines)):
                raise ValueError
            for line in lines:
                value = Decimal(line["usd"])
                if (not canonical(line["id"]) or not canonical(line["evidence_ref"])
                        or not isinstance(line["usd"], str) or len(line["usd"]) > 40
                        or not value.is_finite() or value < 0 or value != value.quantize(CENT)
                        or any(line.get(key) != getattr(ticket, key) for key in ("account", "month", "product", "region"))
                        or line.get("currency") != "USD" or line.get("invoice_id") != record.get("invoice_id")):
                    raise ValueError
            basis = sum((Decimal(line["usd"]) for line in lines if line["kind"] == "affected_api"), Decimal(0))
            requested = Decimal(ticket.requested)
            ceiling = basis / Decimal(10)
            if (not requested.is_finite() or requested <= 0 or ceiling <= 0
                    or requested != requested.quantize(CENT) or ceiling != ceiling.quantize(CENT)):
                raise ValueError
            amount = min(requested, ceiling)
    except (ValueError, KeyError, TypeError, InvalidOperation):
        return Reply("CONTESTED_SCOPE", "Verified scoped fees or a cent-expressible settlement are not established.", "§§1, 3")
    if amount < requested:
        return Reply("PARTIAL_AWARD", f"Only USD {basis:.2f} of affected charges is substantiated.", "§§1, 3", f"{amount:.2f}")
    return Reply("AWARD", f"Confirmed affected charges of USD {basis:.2f} support a future service credit.", "§§1, 3", f"{amount:.2f}")


def review(ticket: Ticket, at: datetime) -> Reply:
    records = json.loads((FIXTURES / "simulator" / "records.json").read_text())
    record = records.get(ticket.account)
    if record is None:
        return Reply("CONTESTED_SCOPE", "The vendor cannot map this account.", "§1", received_at=at.isoformat())
    reply = decide(ticket, record, at)
    # Explicit synthetic receipt latency permits evidence to arrive after submission.
    received = at + timedelta(seconds=record.get("reply_delay_seconds", 0))
    return replace(reply, received_at=received.isoformat())
