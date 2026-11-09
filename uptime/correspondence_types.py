"""Local, authenticated inbox inputs. Content never supplies a sender, approval or outcome."""
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from .source_identity import SourceIdentity

Id = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}$", max_length=96)]
Name = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._/-]{0,94}[A-Za-z0-9]$|^[A-Za-z0-9]$", max_length=96)]
Amount = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]{0,11})(\.[0-9]{1,2})?$", max_length=15)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Scope(Strict):
    account: SourceIdentity
    vendor: SourceIdentity
    contract: SourceIdentity
    service: SourceIdentity
    component: Id
    invoice: Id
    incident: Id
    currency: Annotated[str, StringConstraints(pattern="^[A-Z]{3}$")]
    month: Annotated[str, StringConstraints(pattern=r"^20[0-9]{2}-(0[1-9]|1[0-2])$")]
    region: Id


class Claim(Strict):
    claim_id: Annotated[str, StringConstraints(pattern=r"^inbox-[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")]
    scope: Scope


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("An offset-aware timestamp is required.")
    return parsed.astimezone(UTC)


class Interval(Strict):
    start: Annotated[str, StringConstraints(max_length=40)]
    end: Annotated[str, StringConstraints(max_length=40)]

    @field_validator("start", "end")
    @classmethod
    def utc(cls, value):
        return instant(value).isoformat()


class Status(Interval):
    kind: Literal["status"]


class Coverage(Interval):
    """A scoped service source attests the full measurement and its exclusions."""
    kind: Literal["coverage"]
    complete: bool
    exclusions_removed: bool
    incident_ids: list[Id] = Field(min_length=1, max_length=80)
    total_eligible_minutes: int = Field(ge=0, le=44640)


class Impact(Interval):
    kind: Literal["impact"]
    affected: bool
    exclusion: Literal["none", "unknown", "customer"]


class Component(Interval):
    kind: Literal["component"]
    component_id: Id


class Notice(Interval):
    kind: Literal["notice"]
    issued_at: Annotated[str, StringConstraints(max_length=40)]

    @field_validator("issued_at")
    @classmethod
    def issued(cls, value):
        return instant(value).isoformat()


class Line(Strict):
    id: Id
    kind: Literal["affected_api", "carrier", "tax", "unaffected_api", "third_party"]
    amount: Amount
    # Omitted fields inherit the authenticated invoice envelope. An explicit
    # contradictory identity cannot be silently replaced with case scope.
    account: SourceIdentity | None = None
    vendor: SourceIdentity | None = None
    contract: SourceIdentity | None = None
    service: SourceIdentity | None = None
    component: Id | None = None
    invoice: Id | None = None
    incident: Id | None = None
    region: Id | None = None
    month: str | None = None
    currency: str | None = None


class Invoice(Strict):
    kind: Literal["invoice"]
    lines: list[Line] = Field(min_length=1, max_length=80)


class Report(Strict):
    source_ref: Id
    observed_at: Annotated[str, StringConstraints(max_length=40)]

    @field_validator("observed_at")
    @classmethod
    def observed(cls, value):
        return instant(value).isoformat()


class ResourceSpan(Interval):
    ref: Id
    resource_id: Id


class Symptom(ResourceSpan):
    symptom: Name


class Cause(ResourceSpan):
    cause: Name


class ResourceStatus(Report, Interval):
    kind: Literal["resource_status"]
    complete: bool
    intervals: list[Symptom] = Field(max_length=300)


class ResourceAttribution(Report, Interval):
    kind: Literal["resource_attribution"]
    complete: bool
    causes: list[Cause] = Field(max_length=300)
    exclusions: list[Cause] = Field(max_length=300)


class ResourceLine(Strict):
    ref: Id
    resource_id: Id
    month: Annotated[str, StringConstraints(pattern=r"^20[0-9]{2}-(0[1-9]|1[0-2])$")]
    currency: Annotated[str, StringConstraints(pattern="^[A-Z]{3}$")]
    kind: Literal["resource_service", "tax", "support", "one_time", "other"]
    amount_cents: int = Field(ge=0, le=10**15)
    fee_line_ref: Id | None = None
    category: Name | None = None
    amount_basis: Literal["net_after_discounts"] | None = None
    gross_cents: int | None = Field(default=None, ge=0, le=10**15)
    discount_cents: int | None = Field(default=None, ge=0, le=10**15)
    discount_ref: Id | None = None
    product: SourceIdentity | None = None
    region: Id | None = None
    recurring: bool | None = None
    payment_state: Literal["paid","voided","unpaid"] | None = None
    refund_ref: Id | None = None
    refund_cents: int | None = Field(default=None, ge=0, le=10**15)


class MonitorRow(Interval):
    ref: Id
    account: SourceIdentity
    product: SourceIdentity
    region: Id
    resource_id: Id
    status: Name


class MonitorReport(Report, Interval):
    source_id: Id
    complete: bool
    no_events_verified: bool = False
    records: list[MonitorRow] = Field(max_length=300)


class ProviderTelemetry(MonitorReport):
    kind: Literal["provider_telemetry"]


class ExcludedSpan(Cause):
    sole_cause: bool | None = None
    root_cause_ref: Id | None = None


class CustomerTelemetry(MonitorReport):
    kind: Literal["customer_telemetry"]
    exclusions_complete: bool = False
    exclusions: list[ExcludedSpan] = Field(default_factory=list, max_length=300)


class CustodianAttestation(Report):
    kind: Literal["custodian_attestation"]
    source_id: Id
    monitor_ref: Id


class ResourceInvoice(Report):
    kind: Literal["resource_invoice"]
    itemized_complete: bool
    lines: list[ResourceLine] = Field(min_length=1, max_length=300)


class ServiceRecord(Report):
    plan: Name
    complete: bool
    recorded_at: Annotated[str, StringConstraints(max_length=40)]
    content_sha256: Digest

    @field_validator("recorded_at")
    @classmethod
    def record_time(cls, value):
        return instant(value).isoformat()


class AggregateMonitor(Strict):
    source: Literal["simulated_vendor"]
    unavailable_minutes: int | float | str

    @field_validator("unavailable_minutes", mode="before")
    @classmethod
    def exact_duration(cls, value):
        from .vendor_service_month import minute_microseconds
        minute_microseconds(value)
        return value  # Preserve the signed JSON scalar and its content hash.


class ServiceMonitor(ServiceRecord):
    kind: Literal["service_monitor"]
    content: AggregateMonitor


class ServiceFee(Strict):
    ref: Id
    kind: Name
    category: Name
    amount_cents: int = Field(ge=0, le=10**15)


class PaidServiceInvoice(Strict):
    currency: Annotated[str, StringConstraints(pattern="^[A-Z]{3}$")]
    paid: bool
    lines: list[ServiceFee] = Field(min_length=1, max_length=300)


class ServiceInvoice(ServiceRecord):
    kind: Literal["service_invoice"]
    content: PaidServiceInvoice


class MaintenanceRecord(Interval):
    ref: Id
    account: SourceIdentity
    resource_id: Id
    state: Literal["announced", "confirmed_unannounced"] = "announced"
    announced_at: Annotated[str, StringConstraints(max_length=40)] | None = None

    @field_validator("announced_at")
    @classmethod
    def announcement_time(cls, value):
        return instant(value).isoformat() if value is not None else None


class MaintenanceEvidence(Report):
    kind: Literal["maintenance_evidence"]
    complete: bool
    records: list[MaintenanceRecord] = Field(max_length=300)


class IssuedCredit(Strict):
    ref: Id
    credit_id: Id
    agreement: SourceIdentity
    account: SourceIdentity
    resource_id: Id
    month: Annotated[str, StringConstraints(pattern=r"^20[0-9]{2}-(0[1-9]|1[0-2])$")]
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    amount_cents: int = Field(ge=0, le=10**15)
    state: Literal["issued"]


class PriorCreditEvidence(Report):
    kind: Literal["prior_credit_evidence"]
    complete: bool
    records: list[IssuedCredit] = Field(max_length=300)


class Cycle(Interval):
    ref: Id


class RequestWitness(Strict):
    ref: Id
    resource_id: Id
    interval_ref: Id
    requested_at: Annotated[str, StringConstraints(max_length=40)]
    valid: bool
    failed: bool

    @field_validator("requested_at")
    @classmethod
    def request_time(cls, value):
        return instant(value).isoformat()


class RequestEvidence(Report):
    kind: Literal["request_evidence"]
    records: list[RequestWitness] = Field(min_length=1, max_length=300)


class BillingCalendar(Report):
    kind: Literal["billing_calendar"]
    cycles: list[Cycle] = Field(min_length=1, max_length=36)


class FilingField(Strict):
    name: Name
    refs: list[Id] = Field(min_length=1, max_length=32)


class HistoricalReceipt(Report):
    kind: Literal["original_filing_receipt", "supplement_filing_receipt"]
    receipt_id: Id
    contract_version: Id | None = None
    contract_source_sha256: Digest | None = None
    original_ref: Id | None = None
    ticket_id: Id | None = None
    response_ref: Id | None = None
    received_at: Annotated[str, StringConstraints(max_length=40)]
    submitted_to: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    fields: list[FilingField] = Field(max_length=32)

    @field_validator("received_at")
    @classmethod
    def filing_time(cls, value):
        return instant(value).isoformat()


class PortalResponse(Report):
    kind: Literal["portal_response_receipt"]
    response_kind: Literal["evidence_request","denial"]
    original_ref: Id
    ticket_id: Id
    message_ref: Id
    delivered_at: Annotated[str, StringConstraints(max_length=40)]

    @field_validator("delivered_at")
    @classmethod
    def delivery_time(cls, value):
        return instant(value).isoformat()


class FilingMaterial(Report):
    kind: Literal["filing_material"]
    channel: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    fields: list[FilingField] = Field(max_length=32)


ArtifactType = Literal["resource_log", "invoice_detail", "scope_mapping"]


class ReviewedTerms(Strict):
    ref: Id
    sha256: Digest
    content: Annotated[str, StringConstraints(min_length=1, max_length=10000)]


class AccountFinding(Strict):
    op: Literal["account_restriction", "contract_noncompliance"]
    ref: Id
    finding: Literal["clear", "applies", "unresolved"]
    affected_refs: list[Id] = Field(max_length=300)
    reviewed_terms: ReviewedTerms | None = None


class AccountConditions(Report):
    kind: Literal["account_conditions"]
    findings: list[AccountFinding] = Field(min_length=1, max_length=2)


class ArtifactDescriptor(Report):
    artifact_ref: Id
    artifact_type: ArtifactType
    body_sha256: Digest


class Artifact(ArtifactDescriptor):
    kind: Literal["artifact"]
    content: Annotated[str, StringConstraints(min_length=1, max_length=10000)]


class Verification(ArtifactDescriptor):
    kind: Literal["status_verification","billing_verification"]
    linked_ref: Id


class Message(Strict):
    kind: Literal["message"]
    receipt_id: Id
    credit_id: Id | None = None
    text: Annotated[str, StringConstraints(min_length=1, max_length=3000)]


class Delivery(Strict):
    event_id: Id
    scope: Scope
    body: Annotated[Status | Coverage | Impact | Component | Notice | Invoice | Message | ResourceStatus
                    | ResourceAttribution | ResourceInvoice | ServiceMonitor | ServiceInvoice | BillingCalendar | ProviderTelemetry | CustomerTelemetry | CustodianAttestation | PortalResponse
                    | FilingMaterial | RequestEvidence | HistoricalReceipt | AccountConditions | MaintenanceEvidence | PriorCreditEvidence | Artifact | Verification, Field(discriminator="kind")]


class Empty(Strict):
    pass


SOURCE = dict(status="status", coverage="status", impact="customer", component="customer", notice="customer",
              invoice="billing", message="vendor", original_filing_receipt="vendor", supplement_filing_receipt="vendor", resource_status="status", resource_attribution="customer", customer_telemetry="customer", provider_telemetry="status",
              custodian_attestation="customer", portal_response_receipt="vendor",
              service_monitor="status", service_invoice="billing",
              resource_invoice="billing", billing_calendar="billing", maintenance_evidence="customer", prior_credit_evidence="billing", account_conditions="customer", filing_material="customer", request_evidence="customer", artifact="customer",
              status_verification="status", billing_verification="billing")
