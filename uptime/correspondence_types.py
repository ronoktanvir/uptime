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


class Message(Strict):
    kind: Literal["message"]
    receipt_id: Id
    text: Annotated[str, StringConstraints(min_length=1, max_length=3000)]


class Delivery(Strict):
    event_id: Id
    scope: Scope
    body: Annotated[Status | Coverage | Impact | Component | Notice | Invoice | Message, Field(discriminator="kind")]


class Empty(Strict):
    pass


SOURCE = dict(status="status", coverage="status", impact="customer", component="customer", notice="customer",
              invoice="billing", message="vendor")
