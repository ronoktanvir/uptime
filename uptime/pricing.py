"""Read-only negotiated pricing for explicit synthetic agreements (ADR 07).

Public API: evaluate_price(agreement, invoice) -> PricingResult;
bind_sandbox_bill(provider, mapping) -> Invoice; demo_cases() -> list[dict].
Inputs belong to trusted server adapters, never caller-supplied browser amounts.
No provider I/O, payment mutation, commercial authorization or claim submission.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext

from uptime.contracts import Citation, EvaluationResult, Money, Outcome, Source


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Tier:
    """Graduated units: previous upper < quantity <= upper; None is unbounded."""

    upper: Decimal | None
    rate: Decimal


@dataclass(frozen=True)
class Rate:
    product: str
    unit: str
    tiers: tuple[Tier, ...]
    mode: str = "graduated"
    quantity_scope: str = "complete_performance_slice"
    boundary: str = "upper_inclusive"


@dataclass(frozen=True)
class ContractVersion:
    id: str
    effective_at: datetime
    signed_at: datetime | None
    signatories: tuple[str, ...]
    supersedes: str | None
    rates: tuple[Rate, ...]
    excluded_products: tuple[str, ...]
    citation: Citation
    currency: str = "USD"
    tax_treatment: str = "separate_excluded"
    rounding: str = "line_half_up_cent"


@dataclass(frozen=True)
class Agreement:
    id: str
    customer: str
    vendor: str
    expires_at: datetime
    versions: tuple[ContractVersion, ...]
    source: Source = Source.CUSTOMER


@dataclass(frozen=True)
class InvoiceLine:
    id: str
    product: str | None
    quantity: Decimal | None
    unit: str | None
    start: datetime | None
    end: datetime | None
    net: Decimal
    tax: Decimal | None
    allocation_ref: str | None
    allocation_complete: bool = True


@dataclass(frozen=True)
class ProviderLine:
    """Only fields actually verified in a provider read; None means unavailable."""

    id: str
    net: Decimal | None = None
    tax: Decimal | None = None
    product: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    start: datetime | None = None
    end: datetime | None = None


@dataclass(frozen=True)
class ProviderBill:
    """Trusted W1 read attestation, not a network verifier or user assertion.

    W1 must populate exact bill ID/amount/currency/status and verification_ref
    from an authenticated sandbox read. A source tag alone is not verification.
    Optional lines, when present, are the COMPLETE provider line set.
    """

    id: str
    amount: Decimal
    currency: str
    payment_status: str
    vendor_id: str
    source: Source
    verified: bool
    verification_ref: str
    observed_at: datetime
    base_url: str
    lines: tuple[ProviderLine, ...] = ()


@dataclass(frozen=True)
class Invoice:
    id: str
    customer: str
    vendor: str
    issued_at: datetime
    payment_status: str
    currency: str
    total: Decimal
    lines: tuple[InvoiceLine, ...]
    source: Source = Source.CUSTOMER
    provider_vendor_id: str | None = None
    provider: ProviderBill | None = None


@dataclass(frozen=True)
class LineFinding:
    line_id: str
    product: str
    version: str
    billed: Decimal
    expected: Decimal | None
    delta: Decimal | None
    direction: str


@dataclass(frozen=True)
class PricingResult:
    evaluation: EvaluationResult
    lines: tuple[LineFinding, ...]
    overcharge: Decimal | None
    undercharge: Decimal | None
    stage: str
    sources: tuple[Source, ...]


class PricingInputError(ValueError):
    def __init__(self, outcome: Outcome, detail: str):
        super().__init__(detail)
        self.outcome = outcome


def _require(condition: bool, detail: str, outcome: Outcome = Outcome.MISSING):
    if not condition:
        raise PricingInputError(outcome, detail)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _number(value: object) -> bool:
    # Bounded fixed-point domain keeps arithmetic exact under our local context.
    return (isinstance(value, Decimal) and value.is_finite()
            and abs(value) <= Decimal("1e15") and value.as_tuple().exponent >= -6)


def _money(value: object) -> bool:
    with localcontext() as ctx:
        ctx.prec = 60
        return _number(value) and value >= 0 and value == value.quantize(CENT)


def _validate_binding(provider: ProviderBill, mapping: Invoice):
    _require(provider.verified is True and provider.source == Source.RAMP
             and bool(provider.verification_ref.strip()), "Verified live sandbox read reference required")
    _require(provider.base_url == "https://demo-api.ramp.com", "Only sandbox provider binding supported", Outcome.UNSUPPORTED)
    _require(_aware(provider.observed_at), "Provider read timestamp with timezone required")
    _require(bool(provider.id.strip()) and provider.id == mapping.id, "Provider bill ID conflicts with synthetic mapping")
    _require(bool(provider.vendor_id) and provider.vendor_id == mapping.provider_vendor_id,
             "Provider vendor ID conflicts with explicit synthetic mapping")
    _require(provider.currency == mapping.currency == "USD", "Provider currency/FX unsupported", Outcome.UNSUPPORTED)
    _require(_money(provider.amount) and _money(mapping.total) and provider.amount == mapping.total,
             "Provider bill amount conflicts with synthetic allocation; no fee substitution")
    _require(provider.payment_status == mapping.payment_status,
             "Provider payment status conflicts with mapping")
    _require(mapping.source == Source.CUSTOMER, "Service/quantity/date mapping must remain synthetic")
    _require(isinstance(provider.lines, tuple), "Immutable provider line evidence required")
    _require(isinstance(mapping.lines, tuple) and bool(mapping.lines)
             and all(_money(line.net) and _money(line.tax) for line in mapping.lines),
             "Itemized synthetic allocation with separate tax required")
    with localcontext() as ctx:
        ctx.prec = 60
        _require(sum((line.net + line.tax for line in mapping.lines), ZERO) == provider.amount,
                 "Synthetic line allocation does not equal verified provider total")
    _require(len({line.id for line in mapping.lines}) == len(mapping.lines), "Duplicate synthetic line IDs")
    if provider.lines:
        _require(len({line.id for line in provider.lines}) == len(provider.lines), "Duplicate provider line IDs")
        mapped = {line.id: line for line in mapping.lines}
        _require(set(mapped) == {line.id for line in provider.lines}, "Provider line scope conflicts with mapping")
        for line in provider.lines:
            for name in ("net", "tax", "product", "quantity", "unit", "start", "end"):
                value = getattr(line, name)
                if value is not None:
                    if name in ("net", "tax", "quantity"):
                        _require(_number(value), f"Invalid provider {name}")
                    if name in ("start", "end"):
                        _require(_aware(value), f"Provider {name} timezone required")
                    _require(value == getattr(mapped[line.id], name), f"Provider line {line.id} {name} conflicts with mapping")


def bind_sandbox_bill(provider: ProviderBill, mapping: Invoice) -> Invoice:
    """Bind exact verified money/identity to a separately synthetic allocation.

    Raises PricingInputError on conflicts. Never rescales fees or fabricates
    provider itemization. The evaluator revalidates binding to prevent bypass.
    """
    _validate_binding(provider, mapping)
    return replace(mapping, provider=provider)


def _validate_agreement(agreement: Agreement):
    _require(agreement.source == Source.CUSTOMER, "Only synthetic agreements supported", Outcome.UNSUPPORTED)
    _require(bool(agreement.id) and bool(agreement.customer) and bool(agreement.vendor)
             and agreement.customer != agreement.vendor, "Agreement parties and identity required")
    _require(isinstance(agreement.versions, tuple) and bool(agreement.versions), "Immutable version history required")
    _require(_aware(agreement.expires_at), "Contract expiration timezone required")
    previous = None
    seen = set()
    for version in agreement.versions:
        _require(bool(version.id) and version.id not in seen, "Unique version identity required")
        seen.add(version.id)
        _require(_aware(version.effective_at) and _aware(version.signed_at), "Effective and signed timestamps with timezone required")
        _require(version.signed_at <= version.effective_at,
                 "Retroactive or late-signed terms require commercial interpretation", Outcome.UNSUPPORTED)
        _require(isinstance(version.signatories, tuple)
                 and set(version.signatories) == {agreement.customer, agreement.vendor}, "Both party signatures required")
        _require(version.effective_at < agreement.expires_at, "Version effective after agreement expiration")
        _require(version.supersedes == (previous.id if previous else None), "Broken or ambiguous amendment chain")
        if previous:
            _require(previous.effective_at < version.effective_at, "Amendments must have strictly increasing effective dates")
            _require(previous.signed_at <= version.signed_at, "Amendment signed before predecessor")
        _require(bool(version.citation.uri) and bool(version.citation.section)
                 and bool(version.citation.document) and version.citation.version == version.id,
                 "Exact version clause citation required")
        _require(version.currency == "USD", "FX/non-USD agreement unsupported", Outcome.UNSUPPORTED)
        _require(version.tax_treatment == "separate_excluded", "Tax interpretation unsupported", Outcome.UNSUPPORTED)
        _require(version.rounding == "line_half_up_cent", "Rounding rule unsupported", Outcome.UNSUPPORTED)
        _require(isinstance(version.rates, tuple) and isinstance(version.excluded_products, tuple), "Immutable product scope required")
        products = [rate.product for rate in version.rates]
        _require(len(products) == len(set(products)) and not set(products).intersection(version.excluded_products),
                 "Ambiguous covered/excluded product scope")
        for rate in version.rates:
            _require(bool(rate.product) and bool(rate.unit), "Identified product and unit required")
            _require(rate.mode == "graduated" and rate.quantity_scope == "complete_performance_slice"
                     and rate.boundary == "upper_inclusive", "Tier mode, allocation scope or threshold boundaries unsupported", Outcome.UNSUPPORTED)
            _require(isinstance(rate.tiers, tuple) and bool(rate.tiers), "Immutable tiers required")
            lower = ZERO
            for index, tier in enumerate(rate.tiers):
                _require(_number(tier.rate) and tier.rate >= 0, "Finite nonnegative decimal rate required")
                if tier.upper is None:
                    _require(index == len(rate.tiers) - 1, "Unbounded tier must be last", Outcome.UNSUPPORTED)
                else:
                    _require(_number(tier.upper) and tier.upper > lower and tier.upper == tier.upper.to_integral_value(),
                             "Invalid or ambiguous tier boundary", Outcome.UNSUPPORTED)
                    lower = tier.upper
            _require(rate.tiers[-1].upper is None, "Open-ended final tier required", Outcome.UNSUPPORTED)
        previous = version


def _evaluate(agreement: Agreement, invoice: Invoice, trace: list[str]) -> tuple[LineFinding, ...]:
    _validate_agreement(agreement)
    _require(invoice.source == Source.CUSTOMER, "Invoice service mapping must be labeled synthetic")
    if invoice.provider:
        trace.append(f"Verified sandbox bill {invoice.provider.id}, gross {invoice.provider.amount} USD; "
                     f"read {invoice.provider.verification_ref}; service/quantity/date mapping remains synthetic; "
                     "no real commercial relationship established.")
    else:
        trace.append("Synthetic invoice only; no live Ramp bill bound.")
    _require(invoice.customer == agreement.customer and invoice.vendor == agreement.vendor,
             "Invoice parties do not match synthetic agreement", Outcome.INELIGIBLE)
    _require(bool(invoice.id) and _aware(invoice.issued_at), "Invoice identity and issue timestamp required")
    _require(invoice.currency == "USD", "FX/non-USD invoice unsupported", Outcome.UNSUPPORTED)
    _require(invoice.payment_status in ("pending", "paid"), "Payment state unsupported", Outcome.UNSUPPORTED)
    _require(isinstance(invoice.lines, tuple) and bool(invoice.lines), "Itemized invoice required")
    _require(_money(invoice.total), "Finite nonnegative cent-precision invoice total required")
    _require(len({line.id for line in invoice.lines}) == len(invoice.lines), "Duplicate invoice line IDs")
    for line in invoice.lines:
        _require(bool(line.id) and _money(line.net) and _money(line.tax), "Itemized net fees and separate tax required")
    _require(sum((line.net + line.tax for line in invoice.lines), ZERO) == invoice.total,
             "Invoice net lines plus tax do not reconcile to gross amount")
    findings: list[LineFinding] = []
    allocations = set()
    for line in invoice.lines:
        _require(bool(line.product), f"Line {line.id}: unidentified product scope")
        _require(_aware(line.start) and _aware(line.end), f"Line {line.id}: performance dates with timezone required")
        _require(line.start < line.end, f"Line {line.id}: nonempty half-open performance interval required")
        _require(line.start >= agreement.versions[0].effective_at and line.end <= agreement.expires_at,
                 f"Line {line.id}: outside agreement performance period", Outcome.INELIGIBLE)
        _require(line.end <= invoice.issued_at, f"Line {line.id}: future performance requires separate advance-billing rules", Outcome.UNSUPPORTED)
        version = max((v for v in agreement.versions if v.effective_at <= line.start), key=lambda v: v.effective_at)
        _require(not any(line.start < v.effective_at < line.end for v in agreement.versions),
                 f"Line {line.id}: cross-amendment quantity allocation unknown; split with documented complete allocations")
        trace.append(f"[{version.citation.uri} #{version.citation.section}] Line {line.id}: performance "
                     f"[{line.start.isoformat()}, {line.end.isoformat()}); effective version {version.id}, "
                     f"signed {version.signed_at.isoformat()}, effective {version.effective_at.isoformat()}, "
                     f"supersedes {version.supersedes or 'none'}; invoice date does not choose rate.")
        if line.product in version.excluded_products:
            trace.append(f"Line {line.id}: {line.product} explicitly non-covered; {line.net} USD excluded from discrepancy; tax {line.tax} excluded.")
            findings.append(LineFinding(line.id, line.product, version.id, line.net, None, None, "NON_COVERED"))
            continue
        rate = next((r for r in version.rates if r.product == line.product), None)
        _require(rate is not None, f"Line {line.id}: product {line.product} lacks identified contractual scope")
        _require(line.unit == rate.unit, f"Line {line.id}: quantity unit missing or conflicting")
        _require(_number(line.quantity) and line.quantity > 0 and line.quantity == line.quantity.to_integral_value(),
                 f"Line {line.id}: positive whole-unit decimal quantity required")
        _require(line.allocation_complete is True and bool(line.allocation_ref),
                 f"Line {line.id}: complete performance-slice quantity allocation required")
        _require(line.allocation_ref not in allocations, f"Line {line.id}: duplicate allocation reference")
        allocations.add(line.allocation_ref)
        _require(not any(other.product == line.product and other.id != line.id
                         and _aware(other.start) and _aware(other.end)
                         and line.start < other.end and other.start < line.end for other in invoice.lines),
                 f"Line {line.id}: overlapping product allocations make tier attainment ambiguous")
        trace.append(f"Line {line.id}: allocation {line.allocation_ref}; complete quantity {line.quantity} {line.unit}; "
                     "graduated tiers reset for this complete performance slice; thresholds upper-inclusive.")
        expected = ZERO
        lower = ZERO
        for tier in rate.tiers:
            units = max(ZERO, min(line.quantity, tier.upper if tier.upper is not None else line.quantity) - lower)
            subtotal = units * tier.rate
            expected += subtotal
            trace.append(f"Line {line.id}: tier ({lower}, {tier.upper if tier.upper is not None else 'unbounded'}] "
                         f"{units} × {tier.rate} USD = {subtotal} USD.")
            if tier.upper is not None:
                lower = tier.upper
        expected = expected.quantize(CENT, rounding=ROUND_HALF_UP)
        delta = line.net - expected
        direction = "OVERCHARGE" if delta > 0 else "UNDERCHARGE" if delta < 0 else "MATCH"
        trace.append(f"Line {line.id}: billed net {line.net} - expected {expected} = {delta} USD ({direction}); "
                     f"line HALF_UP to cents; tax {line.tax} separately excluded and not adjudicated.")
        findings.append(LineFinding(line.id, line.product, version.id, line.net, expected, delta, direction))
    return tuple(findings)


def evaluate_price(agreement: Agreement, invoice: Invoice) -> PricingResult:
    """Fail closed for the whole invoice; preserve both discrepancy directions.

    ELIGIBLE amounts are provisional overcharge findings, never money prevented,
    awarded or recovered. Undercharges are exposed separately without netting.
    """
    trace: list[str] = []
    clauses = tuple(v.citation for v in agreement.versions) or (
        Citation("Missing agreement", "unknown", "required terms", "fixture:pricing/missing"),)
    sources = (Source.CUSTOMER, Source.REPLAY)
    stage = "RETROSPECTIVE_REVIEW" if invoice.payment_status == "paid" else "PREPAYMENT_REVIEW"
    try:
        with localcontext() as ctx:
            ctx.prec = 60
            if invoice.provider:
                _validate_binding(invoice.provider, invoice)
                sources = (Source.RAMP, Source.CUSTOMER)
            lines = _evaluate(agreement, invoice, trace)
            over = sum((max(ZERO, line.delta) for line in lines if line.delta is not None), ZERO)
            under = sum((max(ZERO, -line.delta) for line in lines if line.delta is not None), ZERO)
        trace.append(f"Provisional overcharge {over} USD; undercharge {under} USD; no automatic netting. "
                     f"Payment status remains {invoice.payment_status}; prevented, claimed, awarded and recovered amounts are 0.00.")
        outcome = Outcome.ELIGIBLE if over > 0 else Outcome.INELIGIBLE
        evaluation = EvaluationResult(outcome, clauses, tuple(trace), amount=Money(over) if over > 0 else None)
        return PricingResult(evaluation, lines, over, under, stage, sources)
    except PricingInputError as error:
        trace.append(f"FAIL CLOSED: {error}")
        evaluation = EvaluationResult(error.outcome, clauses, tuple(trace),
                                      missing=(str(error),) if error.outcome == Outcome.MISSING else ())
        return PricingResult(evaluation, (), None, None, "NEEDS_REVIEW", sources)


def demo_cases() -> list[dict]:
    """Full CP1 case details; stable price-* IDs; exclusively synthetic replay."""
    from uptime.pricing_demo import demo_cases as load_cases
    return load_cases()
