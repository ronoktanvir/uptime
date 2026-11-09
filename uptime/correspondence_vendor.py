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


@dataclass(frozen=True)
class Decision:
    """The counterparty's structured decision from its own records; wording is rendered separately."""
    code: str
    amount: str | None = None


# Historical wording, unchanged byte for byte. Other renderings may be supplied by
# a caller; they never change what the counterparty decided.
WORDING = {
    "SCOPE_UNVERIFIED": "We cannot reconcile the account, governing terms or destination.",
    "TERMS_UNVERIFIED": "The applicable agreement for the complete service month is unverified.",
    "WINDOW_CLOSED": "We received this claim outside the filing window.",
    "DOCUMENT_UNVERIFIED": "We cannot establish the authenticity of the submitted documentation.",
    "COVERAGE_UNVERIFIED": "We cannot verify the coverage record.",
    "DOCUMENTATION_NEEDED": "Please supply the affected endpoint identifier and its supporting record.",
    "MAINTENANCE_EXCLUDED": "This interruption falls within scheduled maintenance announced in advance.",
    "THRESHOLD_MET": "Our measured service availability satisfies the applicable threshold.",
    "FEES_UNVERIFIED": "Covered charges require further verification.",
    "PRECISION_UNVERIFIED": "Settlement precision or covered charges require further verification.",
    "AWARD": "We have approved a service credit of USD {amount}.",
}


def render(decision: Decision, wording=None):
    return (wording or WORDING)[decision.code].format(amount=decision.amount)


def decide_claim(packet, record: VendorRecord, filed_at) -> Decision:
    """Isolated decision from the private record and the approved packet only.

    It reads no claimant event store, oracle, expected outcome or step number. Any
    extra packet field (for example an asserted outcome) is ignored.
    """
    scope = record.scope
    if (packet.get("tenant") != record.tenant or packet.get("scope") != scope.model_dump()
            or scope.vendor.casefold() != "twilio" or scope.service != "Twilio Messaging API" or scope.currency != "USD"
            or packet.get("version") != VERSION or packet.get("destination") != "isolated-local-simulator"
            or packet.get("subject") != "SLA Claim"):
        return Decision("SCOPE_UNVERIFIED")
    if scope.month < VERSION[:7] or scope.month == VERSION[:7]:
        return Decision("TERMS_UNVERIFIED")
    if filed_at >= deadline(scope.month):
        return Decision("WINDOW_CLOSED")
    if any((a["kind"], a["digest"]) not in record.attachments for a in packet["artifacts"]):
        return Decision("DOCUMENT_UNVERIFIED")
    kinds = {a["kind"] for a in packet["artifacts"]}
    if not {"status", "impact", "invoice"} <= kinds:
        return Decision("COVERAGE_UNVERIFIED")
    if "component" not in kinds:
        return Decision("DOCUMENTATION_NEEDED")
    start, end = instant(record.start), instant(record.end)
    if record.maintenance_notice and instant(record.maintenance_notice) <= start - timedelta(hours=24):
        return Decision("MAINTENANCE_EXCLUDED")
    import calendar
    month = start.strftime("%Y-%m")
    duration = end - start
    total = timedelta(days=calendar.monthrange(start.year, start.month)[1])
    if (month != scope.month or (end - timedelta(microseconds=1)).strftime("%Y-%m") != month or
            duration < timedelta(minutes=5) or duration * 2000 <= total):
        return Decision("THRESHOLD_MET")
    if not record.affected_fees.is_finite() or record.affected_fees < 0:
        return Decision("FEES_UNVERIFIED")
    with localcontext() as ctx:
        ctx.prec = 50
        amount = min(Decimal(packet["requested"]), record.affected_fees * Decimal("0.10"))
        if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
            return Decision("PRECISION_UNVERIFIED")
        return Decision("AWARD", f"{amount:.2f}")


def adjudicate(packet, record: VendorRecord, filed_at, wording=None):
    return render(decide_claim(packet, record, filed_at), wording)


@dataclass(frozen=True)
class ResourceVendorRecord:
    """Private counterparty ledger for a scoped monthly resource and its settlement policy."""
    tenant: str
    scope: Scope
    agreement_id: str
    cutoff_exclusive: str
    # Internally verified account-specific intervals, exclusions and bill charges.
    outage_spans: tuple[tuple[str, str], ...]
    excluded_spans: tuple[tuple[str, str], ...]
    fee_lines: tuple[tuple[str, int], ...]
    eligible_fee_kinds: frozenset[str]
    tiers: tuple[tuple[Decimal, Decimal], ...]  # strict upper availability %, credit %
    round_half_up: bool
    requested_ref: str
    requested_type: str
    trusted_body_sha256: str
    # The operator supplies the counterparty's own scoped bulletin and issuance
    # registers. None for a required register means its evidence is unavailable.
    maintenance_lead: timedelta | None = None
    bulletins: tuple[tuple[str, str, str], ...] | None = None  # start, end, announced
    issued_credits_cents: tuple[tuple[str, int], ...] | None = ()


def adjudicate_resource(packet, record: ResourceVendorRecord, filed_at):
    """Isolated simulator. No claimant events, staged rules or oracle enter this decision."""
    import calendar
    from decimal import ROUND_HALF_UP
    if (packet.get("tenant") != record.tenant or packet.get("scope") != record.scope.model_dump()
            or packet.get("agreement_id") != record.agreement_id or packet.get("destination") != "isolated-local-simulator"):
        return "We cannot verify the governing account and resource."
    if filed_at >= instant(record.cutoff_exclusive):
        return "This request reached us outside the filing window."
    proof = packet.get("disclosed_artifact")
    if not proof:
        return f"Please provide attachment {record.requested_ref}."
    if (proof.get("ref"),proof.get("type"),proof.get("sha256")) != (
            record.requested_ref,record.requested_type,record.trusted_body_sha256):
        return "We cannot verify the authenticity of the referenced supporting document."
    first = instant(record.scope.month+"-01T00:00:00Z")
    end = first+timedelta(days=calendar.monthrange(first.year,first.month)[1])
    if filed_at < end:
        return "We cannot reconcile a completed service month to this filing."
    exclusions = list(record.excluded_spans)
    if record.maintenance_lead is not None:
        if record.bulletins is None or record.maintenance_lead < timedelta():
            return "Our maintenance bulletin register has not been verified."
        for left, right, announced in record.bulletins:
            start, stop, notice = instant(left), instant(right), instant(announced)
            if start >= stop:
                return "Our maintenance bulletin register contains inconsistent dates."
            if notice < start and start - notice >= record.maintenance_lead:
                exclusions.append((left, right))
    previous_credits = {}
    if record.issued_credits_cents is None:
        return "Our previously issued credit statement requires verification."
    for credit_id, cents in record.issued_credits_cents:
        if not credit_id or type(cents) is not int or cents < 0 or previous_credits.setdefault(credit_id, cents) != cents:
            return "Our previously issued credits contain conflicting records."
    # Independently sweep change points instead of using the claimant's union
    # and subtraction implementation. Exclusions override covered spans.
    changes = {}
    for group,spans in enumerate((record.outage_spans,exclusions)):
        for left,right in spans:
            a,b = max(instant(left),first),min(instant(right),end)
            if a >= b:
                continue
            for point,change in ((a,1),(b,-1)):
                changes.setdefault(point,[0,0])[group] += change
    previous,counts,down = first,[0,0],timedelta()
    for point in sorted(changes):
        if counts[0] > 0 and counts[1] == 0:
            down += point-previous
        for i in (0,1):
            counts[i] += changes[point][i]
        previous = point
    total_us = (end-first)//timedelta(microseconds=1)
    available_us = total_us - down//timedelta(microseconds=1)
    with localcontext() as ctx:
        ctx.prec=50
        rate = next((r for threshold,r in sorted(record.tiers) if available_us*100 < threshold*total_us), Decimal(0))
        if not rate:
            return "Our scoped service records meet the contract threshold."
        if any(type(cents) is not int or cents<0 for _,cents in record.fee_lines):
            return "We cannot verify the period's charge basis."
        fee = sum(cents for kind,cents in record.fee_lines if kind in record.eligible_fee_kinds)
        amount = Decimal(fee)*rate/Decimal(10000)
        if record.round_half_up:
            amount=amount.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        amount -= Decimal(sum(previous_credits.values())) / 100
        if amount <= 0:
            return "Previously issued credits cover the full amount for this resource and month."
        amount=min(Decimal(packet["requested"]),amount)
        if not amount.is_finite() or amount<=0 or amount!=amount.quantize(Decimal(".01")):
            return "We need to review the settlement precision or fee basis."
        return f"We approved a service credit of USD {amount:.2f}."
