"""CP1 wire vocabulary. Domain modules own their versioned input types."""
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json


class Source(StrEnum):
    RAMP = "LIVE_RAMP_SANDBOX"
    PUBLIC = "LIVE_VENDOR_PUBLIC"
    CUSTOMER = "SYNTHETIC_CUSTOMER"
    VENDOR = "SIMULATED_VENDOR"
    REPLAY = "DETERMINISTIC_REPLAY"
    UNAVAILABLE = "UNAVAILABLE"


class Outcome(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    MISSING = "INSUFFICIENT_EVIDENCE"
    UNSUPPORTED = "UNSUPPORTED_RULE"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "USD"

    def __post_init__(self):
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise ValueError("finite Decimal amount required")
        if self.currency != "USD":
            raise ValueError("this prototype supports USD only")


@dataclass(frozen=True)
class Citation:
    document: str
    version: str
    section: str
    uri: str


@dataclass(frozen=True)
class EvidenceFact:
    ref: str
    tenant: str
    kind: str
    source: Source
    digest: str
    observed_at: str


@dataclass(frozen=True)
class EvaluationResult:
    outcome: Outcome
    clauses: tuple[Citation, ...]
    trace: tuple[str, ...]
    missing: tuple[str, ...] = ()
    amount: Money | None = None

    def __post_init__(self):
        if not self.clauses or not self.trace:
            raise ValueError("clause and trace required")
        if self.outcome == Outcome.MISSING and not self.missing:
            raise ValueError("missing proof must be named")
        if self.outcome != Outcome.ELIGIBLE and self.amount is not None:
            raise ValueError("only an eligible result can carry claimable value")
        if self.amount is not None and self.amount.amount < 0:
            raise ValueError("claimable amount cannot be negative")


@dataclass(frozen=True)
class Principal:
    tenant: str
    subject: str
    role: str


def fingerprint(value: object) -> str:
    """Stable for JSON-native, float-free replay fixtures."""
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
