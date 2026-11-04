"""The entire data exchange allowed between the claimant and the offline counterparty."""
from calendar import monthrange
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from uptime.contracts import EvidenceFact, Source, fingerprint

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "disputes"
TERMS = "https://www.twilio.com/en-us/legal/service-level-agreement/twilio-apis"
VERSION = "2026-04-09"
CENT = Decimal("0.01")


def deadline(month: str) -> datetime:
    """First instant outside 30 days from month end, UTC demo convention."""
    year, number = map(int, month.split("-"))
    last_day = datetime(year, number, monthrange(year, number)[1], tzinfo=UTC)
    return last_day + timedelta(days=31)


@dataclass(frozen=True)
class Document:
    fact: EvidenceFact
    body: dict

    @classmethod
    def from_archive(cls, tenant: str, body: dict) -> "Document":
        return cls(EvidenceFact(body["ref"], tenant, body["kind"], Source.REPLAY,
                                fingerprint(body), body["end"]), body)


@dataclass(frozen=True)
class Ticket:
    tenant: str
    account: str
    month: str
    product: str
    region: str
    subject: str
    channel: str
    start: str
    end: str
    requested: str
    documents: tuple[Document, ...]

    @property
    def digest(self) -> str:
        return fingerprint(asdict(self))


@dataclass(frozen=True)
class Reply:
    code: str
    reason: str
    clause: str
    awarded: str = "0.00"
    needed_kind: str | None = None
