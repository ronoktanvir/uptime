"""Versioned, minimized data exchanged with the offline counterparty."""
from calendar import monthrange
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import re

from uptime.contracts import EvidenceFact, Source, fingerprint

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "disputes"
TERMS = "https://www.twilio.com/en-us/legal/service-level-agreement/twilio-apis"
VERSION = "2026-04-09"
CENT = Decimal("0.01")
DOCUMENT_FIELDS = frozenset({"ref", "kind", "account", "month", "product", "region", "source",
                             "start", "end", "origin", "classification", "component_id", "observed_at"})


def canonical(value) -> bool:
    return (isinstance(value, str) and bool(value) and value == value.strip()
            and not any(ord(char) < 32 or ord(char) == 127 for char in value))


def instant(value: str) -> datetime:
    at = datetime.fromisoformat(value)
    if at.utcoffset() is None:
        raise ValueError("An aware instant is required.")
    return at.astimezone(UTC)


def deadline(month: str) -> datetime:
    """First instant outside 30 days from month end, UTC replay convention."""
    if not isinstance(month, str) or not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("A canonical YYYY-MM period is required.")
    year, number = map(int, month.split("-"))
    last_day = datetime(year, number, monthrange(year, number)[1], tzinfo=UTC)
    return last_day + timedelta(days=31)


class FrozenBody(dict):
    """JSON-native immutable scalar mapping; construction copies the source."""
    def _deny(self, *args, **kwargs):
        raise TypeError("Archived documents are immutable.")
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _deny

    def __deepcopy__(self, memo):
        return self


@dataclass(frozen=True)
class Document:
    fact: EvidenceFact
    body: dict

    def __post_init__(self):
        if any(not isinstance(value, (str, type(None))) for value in self.body.values()):
            raise ValueError("Archive document fields must be scalar text.")
        object.__setattr__(self, "body", FrozenBody(self.body))

    @classmethod
    def from_archive(cls, tenant: str, body: dict) -> "Document":
        return cls(EvidenceFact(body["ref"], tenant, body["kind"], Source.REPLAY,
                                fingerprint(body), body.get("observed_at", body["end"])), body)

    @classmethod
    def minimized(cls, tenant: str, body: dict) -> "Document":
        return cls.from_archive(tenant, {key: value for key, value in body.items() if key in DOCUMENT_FIELDS})


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
    vendor: str = "Twilio"
    governing_version: str = VERSION
    obligation: str = "monthly_api_availability"

    @property
    def digest(self) -> str:
        return fingerprint(asdict(self))

    @property
    def obligation_key(self) -> str:
        """Monthly right, independent of case aliases, payload revisions and incidents."""
        return fingerprint([self.tenant, self.vendor, self.account, self.governing_version,
                            self.obligation, self.product, self.region, self.month, self.channel])


@dataclass(frozen=True)
class Reply:
    code: str
    reason: str
    clause: str
    awarded: str = "0.00"
    needed_kind: str | None = None
    received_at: str | None = None
