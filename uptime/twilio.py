"""Offline evaluator for the April 9, 2026 Twilio API SLA.

No I/O, account lookup, claim submission, or commercial authority. Inputs are
qualified evidence supplied by a trusted adapter, not arbitrary browser fields.
See fixtures/twilio/README.md for source provenance and interpretation boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from enum import StrEnum
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from uptime.contracts import Citation, EvaluationResult, Money, Outcome

TERMS_VERSION = "2026-04-09"
TERMS_URL = "https://www.twilio.com/en-us/legal/service-level-agreement/twilio-apis"
ADMIN_CUTOFF = date(2024, 10, 24)
CREDIT_RATE = Decimal("0.10")
UTC = timezone.utc


class ServiceFamily(StrEnum):
    TWILIO = "twilio_api"
    SENDGRID = "sendgrid_mail_send"
    SEGMENT = "segment"
    STYTCH = "stytch"
    FLEX_CRITICAL = "flex_critical_scenarios"
    OTHER = "other"


class Plan(StrEnum):
    BASE = "base"
    ENTERPRISE = "enterprise"
    ADMINISTRATION = "administration"
    EMAIL_DELIVERABILITY = "email_deliverability"
    EMAIL_EXPERTS = "email_experts_as_a_service"
    EMAIL_MANAGEMENT = "email_program_management"
    EMAIL_MANAGEMENT_STRATEGY = "email_program_management_and_strategy"
    EMAIL_STRATEGY_GOLD = "email_strategy_gold"


EMAIL_PLANS = frozenset({Plan.EMAIL_DELIVERABILITY, Plan.EMAIL_EXPERTS,
                         Plan.EMAIL_MANAGEMENT, Plan.EMAIL_MANAGEMENT_STRATEGY,
                         Plan.EMAIL_STRATEGY_GOLD})


class ClaimBasis(StrEnum):
    AVAILABILITY = "availability"
    CONNECTION_RATE = "successful_connection_rate"


class Exclusion(StrEnum):
    NONE = "none"
    UNKNOWN = "unknown"
    OUTSIDE_CONTROL = "outside_twilio_control"
    CUSTOMER_OR_THIRD_PARTY = "customer_or_third_party_except_twilio_agents"
    CUSTOMER_TECHNOLOGY = "customer_technology_except_twilio_controlled"
    SCHEDULED_MAINTENANCE = "scheduled_maintenance"
    EMERGENCY_MAINTENANCE = "emergency_maintenance"
    PREVIEW = "alpha_beta_preview_not_generally_available"


class FeeKind(StrEnum):
    API = "api_service"
    EMAIL_PACKAGE = "email_package"
    TAX = "tax_levy_duty"
    CARRIER = "carrier_fee_surcharge"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


def _aware(value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")


def _decimal(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("finite Decimal required; floats are not accepted")


def _reference(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and value.isprintable()


def _boolean(value: bool | None, *, optional: bool = True) -> None:
    if type(value) is not bool and not (optional and value is None):
        raise ValueError("boolean required; strings and integers are not evidence")


@dataclass(frozen=True)
class Coverage:
    """Attested coverage, expressed as a half-open interval [start, end)."""
    start: datetime
    end: datetime
    complete: bool
    evidence_ref: str

    def __post_init__(self):
        _boolean(self.complete, optional=False)
        _aware(self.start)
        _aware(self.end)
        if self.end.astimezone(UTC) <= self.start.astimezone(UTC):
            raise ValueError("coverage end must follow start")


@dataclass(frozen=True)
class ServiceScope:
    api_id: str
    family: ServiceFamily
    supported: bool | None
    generally_available: bool | None
    evidence_ref: str

    def __post_init__(self):
        _boolean(self.supported)
        _boolean(self.generally_available)
        if not isinstance(self.family, ServiceFamily):
            raise ValueError("typed ServiceFamily required")


@dataclass(frozen=True)
class StatusInterval:
    start: datetime
    end: datetime
    api_id: str
    status_url: str
    documentation_refs: tuple[str, ...]
    customer_affected: bool | None
    attribution_ref: str
    exclusion: Exclusion
    exclusion_ref: str
    scheduled_notice_hours: Decimal | None = None

    def __post_init__(self):
        _boolean(self.customer_affected)
        _aware(self.start)
        _aware(self.end)
        if self.end.astimezone(UTC) <= self.start.astimezone(UTC):
            raise ValueError("incident end must follow start")
        if not isinstance(self.exclusion, Exclusion):
            raise ValueError("typed Exclusion required")
        if self.scheduled_notice_hours is not None:
            _decimal(self.scheduled_notice_hours)
            if self.scheduled_notice_hours < 0:
                raise ValueError("notice hours cannot be negative")


@dataclass(frozen=True)
class FeeLine:
    id: str
    api_id: str | None
    month: date
    kind: FeeKind
    amount: Decimal
    currency: str
    actually_incurred: bool | None
    evidence_ref: str
    mapping_ref: str

    def __post_init__(self):
        _boolean(self.actually_incurred)
        _decimal(self.amount)
        if not isinstance(self.kind, FeeKind):
            raise ValueError("typed FeeKind required")
        if self.month.day != 1:
            raise ValueError("fee month must be its first day")


@dataclass(frozen=True)
class TwilioInput:
    month: date
    timezone: str | None
    timezone_ref: str
    service: ServiceScope
    plan: Plan | None
    plan_ref: str
    subscription_coverage: Coverage | None
    status_coverage: Coverage | None
    intervals: tuple[StatusInterval, ...]
    fees: tuple[FeeLine, ...]
    fees_complete: bool
    fees_ref: str
    as_of: datetime
    agreement_ref: str
    terms_version: str = TERMS_VERSION
    administration_purchased_on: date | None = None
    basis: ClaimBasis = ClaimBasis.AVAILABILITY
    currency: str = "USD"
    submitted_at: datetime | None = None
    submission_ref: str = ""
    claim_subject: str = "SLA Claim"
    connection_rate_met: bool | None = None
    connection_rate_ref: str = ""

    def __post_init__(self):
        _boolean(self.fees_complete, optional=False)
        _boolean(self.connection_rate_met)
        if self.month.day != 1:
            raise ValueError("month must be its first day")
        _aware(self.as_of)
        if self.submitted_at is not None:
            _aware(self.submitted_at)
        if self.plan is not None and not isinstance(self.plan, Plan):
            raise ValueError("typed Plan required")
        if not isinstance(self.basis, ClaimBasis):
            raise ValueError("typed ClaimBasis required")


def _citation(section: str) -> Citation:
    return Citation("Twilio API SLA", TERMS_VERSION, section, TERMS_URL)


def calendar_bounds(month: date, zone: str) -> tuple[datetime, datetime]:
    """Calendar boundaries in a caller-evidenced IANA timezone, returned in UTC."""
    if month.day != 1:
        raise ValueError("month must be its first day")
    tz = ZoneInfo(zone)
    following = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return (datetime.combine(month, datetime.min.time(), tz).astimezone(UTC),
            datetime.combine(following, datetime.min.time(), tz).astimezone(UTC))


def claim_deadline(month: date) -> date:
    """Inclusive local calendar date: last day of the service month + 30 days."""
    following = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return following - timedelta(days=1) + timedelta(days=30)


def _seconds(start: datetime, end: datetime) -> Decimal:
    delta = end - start
    return Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / Decimal(1000000)


def _merge(spans: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _subtract(spans: list[tuple[datetime, datetime]], excluded: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    for ex_start, ex_end in _merge(excluded):
        remaining = []
        for start, end in spans:
            if ex_end <= start or ex_start >= end:
                remaining.append((start, end))
            else:
                if start < ex_start:
                    remaining.append((start, ex_start))
                if ex_end < end:
                    remaining.append((ex_end, end))
        spans = remaining
    return spans


def evaluate(data: TwilioInput) -> EvaluationResult:
    """Return a cited CP1 outcome; ELIGIBLE means a candidate credit, never an award."""
    # Isolate calculations from the caller's ambient decimal precision/rounding.
    with localcontext() as context:
        # Sum and percentage multiplication must preserve even sub-cent fees;
        # size precision to the fixed-point inputs instead of rounding at 50 digits.
        amounts = [line.amount for line in data.fees]
        highest = max((amount.adjusted() for amount in amounts), default=0)
        lowest = min((amount.as_tuple().exponent for amount in amounts), default=0)
        context.prec = max(50, highest - min(lowest, 0) + len(str(len(amounts) + 1)) + 5)
        return _evaluate(data)


def _evaluate(data: TwilioInput) -> EvaluationResult:
    trace = [f"Twilio API SLA version={TERMS_VERSION}; agreement_ref={data.agreement_ref or 'MISSING'}."]

    def result(outcome: Outcome, reason: str, section: str, missing: tuple[str, ...] = (), amount: Decimal | None = None) -> EvaluationResult:
        return EvaluationResult(outcome, tuple(_citation(s) for s in dict.fromkeys(("1. Definitions", "3. API Service Credits", section))),
                                tuple(trace + [f"[{section}] {reason}"]), missing,
                                Money(amount) if amount is not None else None)

    def missing(reason: str, section: str = "3. API Service Credits") -> EvaluationResult:
        return result(Outcome.MISSING, reason, section, (reason,))

    if data.terms_version != TERMS_VERSION:
        return result(Outcome.UNSUPPORTED, "Agreement version is not implemented.", "6. Updates")
    if data.month < date(2026, 4, 1):
        return result(Outcome.UNSUPPORTED, "This dated rule cannot establish historical agreement applicability.", "6. Updates")
    if not _reference(data.agreement_ref):
        return missing("Governing agreement and whole-month applicability evidence required.", "6. Updates")
    if data.currency != "USD":
        return result(Outcome.UNSUPPORTED, "Prototype supports USD only; no currency conversion.", "1. Definitions")
    if data.basis == ClaimBasis.CONNECTION_RATE:
        return result(Outcome.UNSUPPORTED, "Successful Connection Rate requires request origin, 202 response throughput, sufficient concurrency, bandwidth and DNS TTL evidence; this branch is not implemented.", "1. Definitions — Successful Connection Rate")
    scope = data.service
    if scope.family in {ServiceFamily.SEGMENT, ServiceFamily.STYTCH, ServiceFamily.FLEX_CRITICAL}:
        return result(Outcome.INELIGIBLE, "This service is expressly outside the API SLA; its separate agreement is not evaluated.", "4. Exclusions")
    if scope.family == ServiceFamily.OTHER:
        return result(Outcome.UNSUPPORTED, "Unrecognized service family; no inferred API coverage.", "1. Definitions")
    if not _reference(scope.api_id) or not _reference(scope.evidence_ref) or scope.supported is None or scope.generally_available is None:
        return missing("Service API scope, support and general-availability evidence required.", "4. Exclusions")
    if not scope.supported or not scope.generally_available:
        return result(Outcome.INELIGIBLE, "Unsupported/discontinued or preview API is excluded.", "4. Exclusions")
    if data.plan is None or not _reference(data.plan_ref):
        return missing("Customer plan and purchase evidence required.", "1. Definitions — thresholds")
    threshold = Decimal("99.95")
    if scope.family == ServiceFamily.TWILIO:
        if data.plan in EMAIL_PLANS:
            return result(Outcome.UNSUPPORTED, "SendGrid package cannot establish a Twilio API plan.", "1. Definitions — thresholds")
        if data.plan == Plan.ENTERPRISE:
            threshold = Decimal("99.99")
        if data.plan == Plan.ADMINISTRATION:
            if data.administration_purchased_on is None:
                return missing("Administration purchase date required to test the strict 2024-10-24 cutoff.", "1. Definitions — thresholds")
            if data.administration_purchased_on > data.month:
                return missing("Administration purchase date conflicts with attested whole-month plan coverage.", "1. Definitions — thresholds")
            if data.administration_purchased_on < ADMIN_CUTOFF:
                threshold = Decimal("99.99")
    elif data.plan in EMAIL_PLANS:
        threshold = Decimal("99.99")
    elif data.plan != Plan.BASE:
        return result(Outcome.UNSUPPORTED, "Twilio edition cannot establish a SendGrid package.", "1. Definitions — thresholds")
    if not data.timezone or not _reference(data.timezone_ref):
        return missing("Explicit calendar timezone and evidence/assumption reference required; SLA specifies no timezone.", "1. Definitions — Total Monthly API Time")
    try:
        start, end = calendar_bounds(data.month, data.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return missing("Valid IANA calendar timezone required.", "1. Definitions — Total Monthly API Time")
    for name, coverage in (("subscription/plan", data.subscription_coverage), ("status-page", data.status_coverage)):
        if (coverage is None or not coverage.complete or not _reference(coverage.evidence_ref)
                or coverage.start.astimezone(UTC) > start or coverage.end.astimezone(UTC) < end):
            return missing(f"Complete {name} coverage of the calendar month required.")
        trace.append(f"{name} coverage_ref={coverage.evidence_ref}; [{start.isoformat()}, {end.isoformat()}).")
    if data.as_of.astimezone(UTC) < end:
        return missing("Calendar month is not complete; final monthly availability/fees cannot be established.")
    when = data.submitted_at or data.as_of
    if data.submitted_at is not None:
        if not _reference(data.submission_ref):
            return missing("Submission receipt required to use a historical submission timestamp.")
        if when.astimezone(UTC) > data.as_of.astimezone(UTC) or when.astimezone(UTC) < end:
            return missing("Submission timestamp must follow the completed month and not be in the future.")
    deadline = claim_deadline(data.month)
    trace.append(f"[3] Deadline={deadline.isoformat()} inclusive in {data.timezone}; clock={'receipt ' + data.submission_ref if data.submitted_at else 'evaluation/planned filing'}; timezone_ref={data.timezone_ref}.")
    if when.astimezone(ZoneInfo(data.timezone)).date() > deadline:
        return result(Outcome.INELIGIBLE, "30-day submission window has elapsed.", "3. API Service Credits")
    if data.claim_subject != "SLA Claim":
        return missing('Claim package must use subject "SLA Claim".')
    included: list[tuple[datetime, datetime]] = []
    excluded: list[tuple[datetime, datetime]] = []
    host = "status.twilio.com" if scope.family == ServiceFamily.TWILIO else "status.sendgrid.com"
    # Select connected same-service components before validating evidence. An
    # adjacent historical chain can establish five continuous minutes at a month
    # boundary; disconnected history cannot change this month's entitlement.
    components = _merge([(i.start.astimezone(UTC), i.end.astimezone(UTC))
                         for i in data.intervals if i.api_id == scope.api_id])
    relevant = [(left, right) for left, right in components if left < end and right > start]
    for incident in data.intervals:
        left, right = incident.start.astimezone(UTC), incident.end.astimezone(UTC)
        if incident.api_id != scope.api_id:
            trace.append(f"Ignored interval for different API {incident.api_id}.")
            continue
        if not any(begin <= left and right <= finish for begin, finish in relevant):
            trace.append("Ignored disconnected interval outside the billing month.")
            continue
        if right > data.as_of.astimezone(UTC):
            return missing("Future incident end cannot establish observed continuous unavailability.")
        try:
            parsed = urlsplit(incident.status_url)
        except ValueError:
            return missing("Valid vendor status URL required.")
        if (parsed.scheme != "https" or parsed.hostname != host or parsed.username or parsed.password
                or not isinstance(incident.documentation_refs, tuple) or not incident.documentation_refs or not all(_reference(ref) for ref in incident.documentation_refs)):
            return missing(f"Dates/times calculated from https://{host} and supporting documentation required; generic telemetry is insufficient.")
        if incident.customer_affected is None or not _reference(incident.attribution_ref):
            return missing("Affected-customer/service mapping required; a public incident alone is only a lead.")
        if not incident.customer_affected:
            trace.append(f"Not customer-affected: {incident.attribution_ref}.")
            continue
        if incident.exclusion == Exclusion.UNKNOWN or not _reference(incident.exclusion_ref):
            return missing("Exclusion assessment and evidence required for each relevant interval.", "4. Exclusions")
        is_excluded = incident.exclusion != Exclusion.NONE
        if incident.exclusion == Exclusion.SCHEDULED_MAINTENANCE:
            if incident.scheduled_notice_hours is None:
                return missing("Scheduled maintenance notice duration required (at least 24 hours).", "4(d). Exclusions")
            is_excluded = incident.scheduled_notice_hours >= Decimal(24)
        (excluded if is_excluded else included).append((left, right))
        trace.append(f"[3,4] {'Excluded' if is_excluded else 'Candidate'} {left.isoformat()}..{right.isoformat()}; status={incident.status_url}; docs={','.join(incident.documentation_refs)}; attribution={incident.attribution_ref}; exclusion={incident.exclusion.value}; assessment={incident.exclusion_ref}.")
    # An excluded span cannot count through a second overlapping incident record.
    continuous = _subtract(_merge(included), excluded)
    seconds = Decimal(0)
    for left, right in continuous:
        duration = _seconds(left, right)
        if duration < Decimal(300):
            trace.append(f"[4(g)] Excluded continuous interval of {duration} seconds (<300).")
            continue
        bounded_start, bounded_end = max(left, start), min(right, end)
        if bounded_start < bounded_end:
            seconds += _seconds(bounded_start, bounded_end)
    total_seconds = _seconds(start, end)
    minutes = seconds / Decimal(60)
    total_minutes = total_seconds / Decimal(60)
    availability = (total_seconds - seconds) / total_seconds * Decimal(100)
    trace.append(f"[1,3,4(g)] Union, subtract exclusions, minimum 300 continuous seconds, then clip to month: B={minutes} minutes; A={total_minutes} minutes; (A-B)/A*100={availability}%; threshold={threshold}%; credit rate=10%.")
    # Compare integer-microsecond-derived decimals, not a rounded percentage.
    breached = seconds * Decimal(100) > total_seconds * (Decimal(100) - threshold)
    if not breached:
        if scope.family == ServiceFamily.SENDGRID and data.plan in EMAIL_PLANS:
            if data.connection_rate_met is not True or not _reference(data.connection_rate_ref):
                return result(Outcome.UNSUPPORTED, "Availability threshold met, but enhanced SendGrid has an independent Successful Connection Rate remedy; failure evaluation is unsupported and cannot be silently denied.", "3. API Service Credits — Successful Connection Rate")
            trace.append(f"Successful Connection Rate met per {data.connection_rate_ref}.")
        return result(Outcome.INELIGIBLE, "Availability is at or above the strict less-than threshold.", "3. API Service Credits")
    if not data.fees_complete or not _reference(data.fees_ref):
        return missing("Complete affected-service monthly invoice/fee allocation required; vendor total is not an eligible fee basis.", "1. Definitions — API Service Credit")
    basis = Decimal(0)
    seen: set[str] = set()
    desired_kind = FeeKind.API if scope.family == ServiceFamily.TWILIO else FeeKind.EMAIL_PACKAGE
    for line in data.fees:
        if not _reference(line.id) or line.id in seen:
            return missing("Unique invoice line IDs required; duplicate fee lines cannot be counted.", "1. Definitions — API Service Credit")
        seen.add(line.id)
        if line.month != data.month:
            trace.append(f"Fee {line.id} omitted: different calendar month.")
            continue
        if not _reference(line.evidence_ref) or not _reference(line.mapping_ref):
            return missing(f"Fee {line.id}: invoice and classification/mapping evidence required.", "1. Definitions — API Service Credit")
        if line.kind in {FeeKind.TAX, FeeKind.CARRIER, FeeKind.THIRD_PARTY}:
            trace.append(f"[1] Fee {line.id} excluded: {line.kind.value}; ref={line.evidence_ref}; mapping={line.mapping_ref}.")
            continue
        if not _reference(line.api_id):
            return missing(f"Fee {line.id}: affected API mapping unknown.", "1. Definitions — API Service Credit")
        if line.api_id != scope.api_id:
            trace.append(f"Fee {line.id} omitted: different API; mapping={line.mapping_ref}.")
            continue
        if line.kind != desired_kind or line.actually_incurred is None:
            return missing(f"Fee {line.id}: eligible fee classification/actually-incurred evidence unresolved.", "1. Definitions — API Service Credit")
        if not line.actually_incurred:
            trace.append(f"Fee {line.id} omitted: not actually incurred.")
            continue
        if line.currency != "USD" or line.amount < 0:
            return result(Outcome.UNSUPPORTED, "Non-USD fees or negative adjustments need a separately reviewed allocation rule.", "1. Definitions — API Service Credit")
        basis += line.amount
        trace.append(f"[1] Fee {line.id}: +{line.amount} USD; ref={line.evidence_ref}; mapping={line.mapping_ref}.")
    amount = basis * CREDIT_RATE
    trace.append(f"[1,3] Eligible fees={basis} USD; {basis} * 0.10 = {amount} USD (exact Decimal, no invented monetary rounding rule); fees_ref={data.fees_ref}.")
    if basis == 0:
        return result(Outcome.INELIGIBLE, "No actually-incurred affected-service fees yield a credit.", "1. Definitions — API Service Credit")
    channel = "https://help.twilio.com" if scope.family == ServiceFamily.TWILIO else "https://support.sendgrid.com"
    return result(Outcome.ELIGIBLE, f"Candidate future-service credit only, not a refund or award. Filing channel={channel}; subject=SLA Claim; no submission performed.", "3. API Service Credits", amount=amount)


def demo_cases() -> list[dict]:
    """Lazy import keeps the deterministic evaluator independent of fixture I/O."""
    from uptime.twilio_demo import demo_cases as build_cases
    return build_cases()
