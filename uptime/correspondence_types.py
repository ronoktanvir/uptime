"""Local, authenticated inbox inputs. Content never supplies a sender, approval or outcome."""
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Id = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}$", max_length=96)]
Name = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._/-]{0,94}[A-Za-z0-9]$|^[A-Za-z0-9]$", max_length=96)]
Amount = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]{0,11})(\.[0-9]{1,2})?$", max_length=15)]


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Scope(Strict):
    account: Id
    vendor: Name
    contract: Id
    service: Name
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
    account: Id | None = None
    vendor: Name | None = None
    contract: Id | None = None
    service: Name | None = None
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


class ResourceInvoice(Report):
    kind: Literal["resource_invoice"]
    itemized_complete: bool
    lines: list[ResourceLine] = Field(min_length=1, max_length=300)


class Cycle(Interval):
    ref: Id


class BillingCalendar(Report):
    kind: Literal["billing_calendar"]
    cycles: list[Cycle] = Field(min_length=1, max_length=36)


class FilingField(Strict):
    name: Name
    refs: list[Id] = Field(min_length=1, max_length=32)


class FilingMaterial(Report):
    kind: Literal["filing_material"]
    channel: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    fields: list[FilingField] = Field(max_length=32)


ArtifactType = Literal["resource_log", "invoice_detail", "scope_mapping"]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


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
    text: Annotated[str, StringConstraints(min_length=1, max_length=3000)]


class Delivery(Strict):
    event_id: Id
    scope: Scope
    body: Annotated[Status | Coverage | Impact | Component | Notice | Invoice | Message | ResourceStatus
                    | ResourceAttribution | ResourceInvoice | BillingCalendar | FilingMaterial | AccountConditions | Artifact | Verification, Field(discriminator="kind")]


class Empty(Strict):
    pass


SOURCE = dict(status="status", coverage="status", impact="customer", component="customer", notice="customer",
              invoice="billing", message="vendor", resource_status="status", resource_attribution="customer",
              resource_invoice="billing", billing_calendar="billing", account_conditions="customer", filing_material="customer", artifact="customer",
              status_verification="status", billing_verification="billing")
