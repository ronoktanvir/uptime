"""Isolated offline counterparty for the inbox wire protocol.

An operator/test supplies this simulator's independent account ledger, incident
and authentic attachment digests. It sees only the approved outbound packet,
has no access to the claimant's event store, and never delivers its own reply.
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, localcontext

from .correspondence_types import Scope, instant
from .disputes_wire import VERSION, deadline

@dataclass(frozen=True)
class VendorRecord:
    tenant: str
    scope: Scope
    start: str
    end: str
    affected_fees: Decimal
    attachments: frozenset[tuple[str, str]]
    maintenance_notice: str | None = None


def adjudicate(packet, record: VendorRecord, filed_at):
    scope = record.scope
    if (packet.get("tenant") != record.tenant or packet.get("scope") != scope.model_dump()
            or scope.vendor.casefold() != "twilio" or scope.service != "Twilio Messaging API" or scope.currency != "USD"
            or packet.get("version") != VERSION or packet.get("destination") != "isolated-local-simulator"
            or packet.get("subject") != "SLA Claim"):
        return "We cannot reconcile the account, governing terms or destination."
    if scope.month < VERSION[:7] or scope.month == VERSION[:7]:
        return "The applicable agreement for the complete service month is unverified."
    if filed_at >= deadline(scope.month):
        return "We received this claim outside the filing window."
    if any((a["kind"], a["digest"]) not in record.attachments for a in packet["artifacts"]):
        return "We cannot establish the authenticity of the submitted documentation."
    kinds = {a["kind"] for a in packet["artifacts"]}
    if not {"status", "impact", "invoice"} <= kinds:
        return "We cannot verify the coverage record."
    if "component" not in kinds:
        return "Please supply the affected endpoint identifier and its supporting record."
    start, end = instant(record.start), instant(record.end)
    if record.maintenance_notice and instant(record.maintenance_notice) <= start - timedelta(hours=24):
        return "This interruption falls within scheduled maintenance announced in advance."
    import calendar
    month = start.strftime("%Y-%m")
    duration = end - start
    total = timedelta(days=calendar.monthrange(start.year, start.month)[1])
    if (month != scope.month or (end - timedelta(microseconds=1)).strftime("%Y-%m") != month or
            duration < timedelta(minutes=5) or duration * 2000 <= total):
        return "Our measured service availability satisfies the applicable threshold."
    if not record.affected_fees.is_finite() or record.affected_fees < 0:
        return "Covered charges require further verification."
    with localcontext() as ctx:
        ctx.prec = 50
        amount = min(Decimal(packet["requested"]), record.affected_fees * Decimal("0.10"))
        if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
            return "Settlement precision or covered charges require further verification."
        return f"We have approved a service credit of USD {amount:.2f}."
