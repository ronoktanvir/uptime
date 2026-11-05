"""Offline, signed observations of vendor awards and native Ramp credit usage.

No provider transport, credentials, API routes, or AllocationLedger writes. A
signature authenticates a registered witness, not the truth of a source. Office
review must establish that truth/authority outside this module and outside API.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import stat
from typing import Annotated, Literal
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

from . import claim_identity
from .claim_identity import claim_key
from .contracts import fingerprint

MAX_MINOR = 10**15
MAX_AGE = timedelta(hours=24)
DOMAIN = "uptime-ramp-award-attribution/1"


class AttributionError(ValueError):
    """Public reason codes only; no source contents in exceptions."""


def fail(code):
    raise AttributionError(code)


def canonical_json(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return sha256(canonical_json(value).encode()).hexdigest()


def _id(value):
    if not value or value != value.strip() or not value.isprintable():
        raise ValueError("Canonical identifier required")
    return value


def _uuid(value):
    if str(UUID(value)) != value or UUID(value).int == 0:
        raise ValueError("Canonical native UUID required")
    return value


def _known(value):
    if value.upper() in {"UNKNOWN", "UNAVAILABLE", "UNSPECIFIED", "NONE", "NULL", "N/A", "ANY", "*", "?"}:
        raise ValueError("Known exact scope required")
    return value


def _time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("Timezone required")
    return parsed.astimezone(timezone.utc).isoformat()


def _key(value):
    # Reject canonical small-order points, including their sign-bit variants.
    p = 2**255 - 19
    y = int.from_bytes(bytes.fromhex(value), "little") & (2**255 - 1)
    eighth = 2707385501144840649318225287225658788936804267575313519463743609750303402022
    if y >= p or y in {0, 1, p-1, eighth, p-eighth}:
        raise ValueError("Nontrivial canonical Ed25519 verifier required")
    return value


def _rate(value):
    if type(value) is not int or value not in (1, 10, 100, 1000, 10000):
        raise ValueError("Exact native minor-unit rate required")
    return value


Id = Annotated[str, Field(min_length=1, max_length=256), AfterValidator(_id)]
KnownId = Annotated[Id, AfterValidator(_known)]
NativeID = Annotated[str, AfterValidator(_uuid)]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
PublicKey = Annotated[Hash, AfterValidator(_key)]
Instant = Annotated[str, AfterValidator(_time)]
Minor = Annotated[int, Field(ge=0, le=MAX_MINOR)]
Positive = Annotated[int, Field(gt=0, le=MAX_MINOR)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Rate = Annotated[int, BeforeValidator(_rate)]
Role = Literal["claim_registrar", "vendor_verifier", "finance_approver", "ramp_observer"]


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)


class Evidence(Strict):
    reference: Id
    sha256: Hash
    method: Id


class ClaimScope(Strict):
    vendor_id: NativeID
    vendor_name: Id
    account_id: KnownId
    beneficiary_id: KnownId
    contract_id: KnownId
    contract_version: KnownId
    product_id: KnownId
    service_name: Id
    month: Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
    remedy: Id
    currency: Currency
    minor_unit_conversion_rate: Rate


class SourceIdentity(Strict):
    subject: Id
    public_key: PublicKey


class Witness(SourceIdentity):
    role: Role
    operator_id: Id
    operator_key_sha256: Hash
    association: Evidence
    source_verification: Evidence
    valid_from: Instant
    valid_until: Instant
    scopes: list[ClaimScope]


class OfficeConfig(Strict):
    version: Literal["uptime-ramp-award-office/1"]
    installation_id: Id
    tenant: Id
    business_id: NativeID
    environment: Literal["sandbox"]
    evidence_mode: Literal["ACTUAL_NATIVE", "MOCK"]
    review: Evidence
    witnesses: list[Witness] = Field(min_length=4, max_length=64)
    # Review exports the existing inbound-source allowlists, including retired keys.
    authority_sources: list[SourceIdentity]


class Statement(Strict):
    version: Literal["uptime-ramp-award-attribution/1"]
    installation_id: Id
    tenant: Id
    business_id: NativeID
    environment: Literal["sandbox"]
    evidence_mode: Literal["ACTUAL_NATIVE", "MOCK"]
    kind: Literal["filed_claim", "vendor_award", "native_snapshot", "attribution"]
    id: Id
    issued_at: Instant
    expires_at: Instant
    body: dict


class Endorsement(Strict):
    subject: Id
    signature: Annotated[str, Field(pattern=r"^[a-f0-9]{128}$")]


class SignedStatement(Strict):
    statement: Statement
    endorsements: list[Endorsement] = Field(min_length=1, max_length=2)


class BillScope(Strict):
    bill_id: NativeID
    eligible_minor: Positive
    evidence: Evidence  # explicitly binds this bill to the claim's beneficiary/contract


class ExternalFilingWitness(Strict):
    """Independent custody attestation, never an inbound service's source label."""
    evidence_mode: Literal["ACTUAL_EXTERNAL", "MOCK"]
    receipt_id: Id
    receipt_sha256: Hash
    received_at: Instant
    submitted_to: Id
    channel: Literal["VENDOR_PORTAL", "VENDOR_SIGNED_DOCUMENT", "VENDOR_AUTHENTICATED_CORRESPONDENCE"]
    verification: Evidence
    authority_verification: Evidence
    independence_verification: Evidence


class FiledClaim(Strict):
    claim_id: Id
    dispatch_sha256: Hash
    local_contract_id: Id
    claimant_operator_id: Id
    scope: ClaimScope
    scope_verification: Evidence
    bills: list[BillScope] = Field(min_length=1, max_length=128)
    external_filing: ExternalFilingWitness | None = None


class VendorConfirmation(Evidence):
    channel: Literal["VENDOR_PORTAL", "VENDOR_SIGNED_DOCUMENT", "VENDOR_AUTHENTICATED_CORRESPONDENCE"]
    authority_verification: Evidence
    independence_verification: Evidence


class VendorAward(Strict):
    claim_id: Id
    claim_sha256: Hash
    scope: ClaimScope
    vendor_award_ref: Id
    amount_minor: Positive
    confirmation: VendorConfirmation


class Money(Strict):
    amount: Minor
    currency_code: Currency
    minor_unit_conversion_rate: Rate


class CreditApplication(Strict):
    bill_id: NativeID
    amount: Money | None = None


class BillApplication(Strict):
    id: NativeID
    amount: Money | None = None


class Credit(Strict):
    id: NativeID
    vendor_id: NativeID | None = None
    entity_id: NativeID | None = None
    reference_bill_id: NativeID | None = None
    accounting_date: str | None = None
    archived_at: Instant | Literal["UNKNOWN"] | None = "UNKNOWN"
    total_amount: Money | None = None
    remaining_amount: Money | None = None
    total_applied_amount: Money | None = None
    applied_bills: list[CreditApplication] | None = None
    applied_draft_bills: list[CreditApplication] | None = None


class Vendor(Strict):
    id: NativeID | None = None


class Bill(Strict):
    id: NativeID
    vendor: Vendor | None = None
    entity_id: NativeID | None = None
    issued_at: str | None = None
    archived_at: Instant | Literal["UNKNOWN"] | None = "UNKNOWN"
    status: str | None = None
    amount: Money | None = None
    applied_vendor_credits: list[BillApplication] | None = None


class NativeSnapshot(Strict):
    # Same sanitized record fields as RampCreditSync / credit_observation().
    id: Id
    observed_at: Instant
    source: Literal["LIVE_RAMP_SANDBOX", "DETERMINISTIC_REPLAY"]
    provenance_ref: Id
    capture: Evidence
    scopes: list[str] | None = None
    available: bool | None = None
    list_complete: bool | None = None
    credits: list[Credit] | None = None
    bills: list[Bill] | None = None


class BillShare(Strict):
    bill_id: NativeID
    amount_minor: Minor  # explicitly attested cumulative share, never a cap/min()


class Attribution(Strict):
    award_id: Id
    claim_sha256: Hash
    snapshot_sha256: Hash
    credit_id: NativeID
    posted_minor: Positive
    currency: Currency
    minor_unit_conversion_rate: Rate
    applications: list[BillShare] = Field(min_length=1, max_length=128)
    basis: Literal["EXACT_EXPLICIT_ALLOCATION"]
    scope_verification: Evidence


def _parse(model, value):
    try:
        return model.model_validate(value.model_dump(mode="json") if isinstance(value, BaseModel) else value)
    except (ValidationError, TypeError, ValueError):
        fail("INVALID_" + model.__name__.upper())


def signing_bytes(config, statement, subject):
    """Offline signer helper. No private key is accepted or generated here."""
    config, statement = _parse(OfficeConfig, config), _parse(Statement, statement)
    witness = next((w for w in config.witnesses if w.subject == subject), None)
    if witness is None:
        fail("UNREGISTERED_WITNESS")
    return canonical_json([DOMAIN, digest(config), witness.role, subject, witness.public_key,
                           statement.model_dump(mode="json")]).encode()


def load_office_config(path):
    """Only explicit operator-owned public configuration; never searches for keys."""
    path = Path(path)
    if not path.is_absolute() or path != path.resolve():
        fail("ABSOLUTE_NON_SYMLINK_CONFIG_REQUIRED")
    parent = path.parent.stat()
    if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o022:
        fail("PROTECTED_CONFIG_DIRECTORY_REQUIRED")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as handle:
        meta = os.fstat(handle.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_nlink != 1):
            fail("PROTECTED_CONFIG_REQUIRED")
        raw = handle.read(262145)
    if len(raw) > 262144:
        fail("CONFIG_TOO_LARGE")
    try:
        return _parse(OfficeConfig, json.loads(raw))
    except (ValueError, UnicodeError):
        fail("INVALID_OFFICE_CONFIG")


def _unit(money):
    return (money.currency_code, money.minor_unit_conversion_rate) if money else None


def _links(rows, key):
    if rows is None or any(r.amount is None for r in rows):
        return None
    result = {getattr(r, key): r.amount.amount for r in rows}
    if len(result) != len(rows):
        fail("DUPLICATE_APPLICATION")
    return result


def _unique(rows, key):
    if len({getattr(r, key) for r in rows}) != len(rows):
        fail("DUPLICATE_RECORD")


def _facts(snapshot):
    """Partial evidence stays observable. Only contradictory known facts conflict."""
    credits = {c.id: c for c in snapshot.credits or []}
    bills = {b.id: b for b in snapshot.bills or []}
    _unique(snapshot.credits or [], "id")
    _unique(snapshot.bills or [], "id")
    for c in credits.values():
        monies = [m for m in (c.total_amount, c.remaining_amount, c.total_applied_amount) if m]
        monies += [a.amount for a in (c.applied_bills or []) + (c.applied_draft_bills or []) if a.amount]
        if len({_unit(m) for m in monies}) > 1:
            fail("CROSS_CURRENCY")
        links, drafts = _links(c.applied_bills, "bill_id"), _links(c.applied_draft_bills, "bill_id")
        if links is not None and drafts is not None and set(links) & set(drafts):
            fail("DRAFT_POSTED_OVERLAP")
        if c.total_amount and c.remaining_amount and c.total_applied_amount:
            if c.total_amount.amount != c.remaining_amount.amount + c.total_applied_amount.amount:
                fail("CREDIT_TOTAL_CONFLICT")
        if links is not None and drafts is not None and c.total_applied_amount:
            if sum(links.values()) + sum(drafts.values()) != c.total_applied_amount.amount:
                fail("CREDIT_APPLICATION_CONFLICT")
    for b in bills.values():
        links = _links(b.applied_vendor_credits, "id")
        if b.amount:
            if links is not None and sum(links.values()) > b.amount.amount:
                fail("BILL_OVERCAPACITY")
            if any(a.amount and _unit(a.amount) != _unit(b.amount) for a in b.applied_vendor_credits or []):
                fail("CROSS_CURRENCY")
        for a in b.applied_vendor_credits or []:
            c = credits.get(a.id)
            if c is None:
                continue
            if c.vendor_id and b.vendor and b.vendor.id and c.vendor_id != b.vendor.id:
                fail("VENDOR_CONFLICT")
            if c.entity_id and b.entity_id and c.entity_id != b.entity_id:
                fail("ENTITY_CONFLICT")
            if c.total_amount and b.amount and _unit(c.total_amount) != _unit(b.amount):
                fail("CROSS_CURRENCY")
            left = _links(c.applied_bills, "bill_id")
            if left is not None and a.amount and left.get(b.id, 0) != a.amount.amount:
                fail("RECIPROCAL_CONFLICT")
    for c in credits.values():
        for a in c.applied_bills or []:
            b = bills.get(a.bill_id)
            right = _links(b.applied_vendor_credits, "id") if b else None
            if right is not None and a.amount and right.get(c.id, 0) != a.amount.amount:
                fail("RECIPROCAL_CONFLICT")
    return credits, bills


def _fresh(observed_at, now):
    age = datetime.fromisoformat(now) - datetime.fromisoformat(observed_at)
    return timedelta(0) <= age <= MAX_AGE


def _scope_owner(scope):
    return digest({k: getattr(scope, k) for k in ("vendor_id", "account_id", "beneficiary_id",
        "contract_id", "contract_version", "product_id", "currency", "minor_unit_conversion_rate")})


class AwardAttributionStore:
    """An offline observation journal, independently callable by RampWorkspace.

    Constructor configuration is trusted operator input, never request content.
    Use the same DB as the claim identity registry (or an exact reviewed copy).
    All tables owned here have the `award_observation_` prefix.
    """

    def __init__(self, path, office_config):
        self.path = Path(path)
        self._config = _parse(OfficeConfig, office_config)
        self._validate_office()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db(write=True, check=False) as db:
            self._schema(db)
            encoded = canonical_json(self._config)
            old = db.execute("SELECT payload FROM award_observation_office").fetchone()
            if old and old[0] != encoded:
                fail("OFFICE_CONFIGURATION_CHANGED_REVIEW_REQUIRED")
            db.execute("INSERT OR IGNORE INTO award_observation_office VALUES(1,?)", (encoded,))
            self._check_authority(db)

    def _validate_office(self):
        cfg = self._config
        for field in ("subject", "public_key", "operator_id", "operator_key_sha256"):
            if len({getattr(w, field) for w in cfg.witnesses}) != len(cfg.witnesses):
                fail("INDEPENDENT_WITNESSES_REQUIRED")
        if set(w.role for w in cfg.witnesses) != {"claim_registrar", "vendor_verifier", "finance_approver", "ramp_observer"}:
            fail("ALL_WITNESS_ROLES_REQUIRED")
        for w in cfg.witnesses:
            if w.valid_until <= w.valid_from or (w.role != "ramp_observer" and not w.scopes):
                fail("INVALID_WITNESS_GRANT")
            if any(w.subject == s.subject or w.public_key == s.public_key for s in cfg.authority_sources):
                fail("API_SOURCE_CANNOT_BECOME_AWARD_AUTHORITY")

    @contextmanager
    def _db(self, *, write=False, check=True):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if check:
                self._check_authority(db)
            yield db
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            fail("IMMUTABILITY_OR_CAPACITY_CONFLICT")
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _check_authority(self, db):
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cfg = self._config
        if "authority_workspace" in tables:
            row = db.execute("SELECT * FROM authority_workspace WHERE id=1").fetchone()
            if not row or row["mode"] != "sandbox" or row["rehearsal"]:
                fail("WORKSPACE_AUTHORITY_CONFLICT")
            if "tenant" in row.keys() and row["tenant"] != cfg.tenant:
                fail("WORKSPACE_TENANT_CONFLICT")
        if "native_installation" in tables:
            row = db.execute("SELECT business_id FROM native_installation WHERE tenant=?", (cfg.tenant,)).fetchone()
            if not row or row[0] != cfg.business_id:
                fail("WORKSPACE_BUSINESS_CONFLICT")
        # Existing source allowlists are narrower authority, not an award grant.
        for table in ("authority_source", "source_key_history"):
            if table not in tables:
                continue
            columns = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
            if not {"subject", "public_key"} <= columns:
                fail("UNSUPPORTED_AUTHORITY_SOURCE_SCHEMA")
            for w in cfg.witnesses:
                if db.execute(f"SELECT 1 FROM {table} WHERE subject=? OR public_key=? OR public_key=?",
                              (w.subject, w.public_key, bytes.fromhex(w.public_key))).fetchone():
                    fail("API_SOURCE_CANNOT_BECOME_AWARD_AUTHORITY")
        if "authority_user" in tables:
            for w in cfg.witnesses:
                if w.role != "finance_approver":
                    continue
                row = db.execute("SELECT role,public_key FROM authority_user WHERE subject=?", (w.operator_id,)).fetchone()
                if not row or row[0] != "reviewer":
                    fail("ENROLLED_HUMAN_FINANCE_OPERATOR_REQUIRED")
                key = row[1].encode() if isinstance(row[1], str) else row[1]
                if sha256(key).hexdigest() != w.operator_key_sha256:
                    fail("FINANCE_OPERATOR_ASSOCIATION_CHANGED")

    @staticmethod
    def _schema(db):
        schemas = {
            "office": "id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL",
            "event": "sequence INTEGER PRIMARY KEY, kind TEXT NOT NULL, id TEXT NOT NULL, digest TEXT NOT NULL UNIQUE, signed TEXT NOT NULL, recorded_at TEXT NOT NULL, UNIQUE(kind,id)",
            "claim": "id TEXT PRIMARY KEY, digest TEXT NOT NULL UNIQUE, dispatch_sha256 TEXT NOT NULL, payload TEXT NOT NULL",
            "external_receipt": "source_key TEXT PRIMARY KEY, claim_id TEXT NOT NULL UNIQUE REFERENCES award_observation_claim(id)",
            "award": "id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES award_observation_claim(id), source_key TEXT NOT NULL UNIQUE, amount INTEGER NOT NULL, payload TEXT NOT NULL",
            "snapshot": "digest TEXT PRIMARY KEY, observed_at TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, issues TEXT NOT NULL",
            "conflict": "digest TEXT PRIMARY KEY, reason TEXT NOT NULL",
            "credit_owner": "credit_id TEXT PRIMARY KEY, scope TEXT NOT NULL",
            "bill_owner": "bill_id TEXT PRIMARY KEY, scope TEXT NOT NULL",
            "credit_capacity": "snapshot TEXT NOT NULL, credit_id TEXT NOT NULL, amount INTEGER NOT NULL, PRIMARY KEY(snapshot,credit_id)",
            "pair_capacity": "snapshot TEXT NOT NULL, credit_id TEXT NOT NULL, bill_id TEXT NOT NULL, amount INTEGER NOT NULL, PRIMARY KEY(snapshot,credit_id,bill_id)",
            "bill_capacity": "snapshot TEXT NOT NULL, bill_id TEXT NOT NULL, amount INTEGER NOT NULL, PRIMARY KEY(snapshot,bill_id)",
            "allocation": f"digest TEXT PRIMARY KEY, snapshot TEXT NOT NULL, award_id TEXT NOT NULL REFERENCES award_observation_award(id), credit_id TEXT NOT NULL, amount INTEGER NOT NULL CHECK(typeof(amount)='integer' AND amount BETWEEN 1 AND {MAX_MINOR}), UNIQUE(snapshot,award_id,credit_id), FOREIGN KEY(snapshot,credit_id) REFERENCES award_observation_credit_capacity(snapshot,credit_id)",
            "application": f"binding TEXT NOT NULL REFERENCES award_observation_allocation(digest), bill_id TEXT NOT NULL, amount INTEGER NOT NULL CHECK(typeof(amount)='integer' AND amount BETWEEN 0 AND {MAX_MINOR}), PRIMARY KEY(binding,bill_id)",
        }
        for suffix, fields in schemas.items():
            table = "award_observation_" + suffix
            db.execute(f"CREATE TABLE IF NOT EXISTS {table} ({fields})")
            for operation in ("UPDATE", "DELETE"):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation} BEFORE {operation} ON {table} "
                           "BEGIN SELECT RAISE(ABORT,'Immutable award observation'); END")
        db.execute("""CREATE TRIGGER IF NOT EXISTS award_observation_allocation_cap BEFORE INSERT ON award_observation_allocation BEGIN
          SELECT CASE WHEN NEW.amount + COALESCE((SELECT SUM(amount) FROM award_observation_allocation WHERE snapshot=NEW.snapshot AND award_id=NEW.award_id),0) > (SELECT amount FROM award_observation_award WHERE id=NEW.award_id)
            THEN RAISE(ABORT,'Award capacity') END;
          SELECT CASE WHEN NEW.amount + COALESCE((SELECT SUM(amount) FROM award_observation_allocation WHERE snapshot=NEW.snapshot AND credit_id=NEW.credit_id),0) > (SELECT amount FROM award_observation_credit_capacity WHERE snapshot=NEW.snapshot AND credit_id=NEW.credit_id)
            THEN RAISE(ABORT,'Credit capacity') END;
        END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS award_observation_application_cap BEFORE INSERT ON award_observation_application BEGIN
          SELECT CASE WHEN NEW.amount + COALESCE((SELECT SUM(amount) FROM award_observation_application WHERE binding=NEW.binding),0) > (SELECT amount FROM award_observation_allocation WHERE digest=NEW.binding)
            THEN RAISE(ABORT,'Allocation capacity') END;
          SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM award_observation_pair_capacity p JOIN award_observation_allocation a ON a.snapshot=p.snapshot AND a.credit_id=p.credit_id WHERE a.digest=NEW.binding AND p.bill_id=NEW.bill_id)
            THEN RAISE(ABORT,'Unknown native pair') END;
          SELECT CASE WHEN NEW.amount + COALESCE((SELECT SUM(x.amount) FROM award_observation_application x JOIN award_observation_allocation a ON a.digest=x.binding JOIN award_observation_allocation n ON n.digest=NEW.binding WHERE a.snapshot=n.snapshot AND a.credit_id=n.credit_id AND x.bill_id=NEW.bill_id),0) > (SELECT p.amount FROM award_observation_pair_capacity p JOIN award_observation_allocation a ON a.snapshot=p.snapshot AND a.credit_id=p.credit_id WHERE a.digest=NEW.binding AND p.bill_id=NEW.bill_id)
            THEN RAISE(ABORT,'Native pair capacity') END;
          SELECT CASE WHEN NEW.amount + COALESCE((SELECT SUM(x.amount) FROM award_observation_application x JOIN award_observation_allocation a ON a.digest=x.binding JOIN award_observation_allocation n ON n.digest=NEW.binding WHERE a.snapshot=n.snapshot AND x.bill_id=NEW.bill_id),0) > (SELECT p.amount FROM award_observation_bill_capacity p JOIN award_observation_allocation a ON a.snapshot=p.snapshot WHERE a.digest=NEW.binding AND p.bill_id=NEW.bill_id)
            THEN RAISE(ABORT,'Native bill capacity') END;
        END""")

    def _verified(self, signed, kind, roles, now, scope=None):
        signed = _parse(SignedStatement, signed)
        s, cfg = signed.statement, self._config
        for field in ("installation_id", "tenant", "business_id", "environment", "evidence_mode"):
            if getattr(s, field) != getattr(cfg, field):
                fail("SIGNATURE_AUDIENCE_CONFLICT")
        if s.kind != kind:
            fail("SIGNATURE_PURPOSE_CONFLICT")
        if not s.issued_at <= now <= s.expires_at or s.expires_at <= s.issued_at:
            fail("EXPIRED_OR_FUTURE_SIGNATURE")
        if datetime.fromisoformat(s.expires_at) - datetime.fromisoformat(s.issued_at) > MAX_AGE:
            fail("SIGNATURE_WINDOW_TOO_LONG")
        found = {}
        for endorsement in signed.endorsements:
            w = next((w for w in cfg.witnesses if w.subject == endorsement.subject), None)
            if not w or w.role not in roles or w.role in found:
                fail("UNREGISTERED_OR_WRONG_PURPOSE_WITNESS")
            if not w.valid_from <= s.issued_at <= now <= w.valid_until:
                fail("EXPIRED_WITNESS_GRANT")
            if scope is not None and scope not in w.scopes:
                fail("WITNESS_SCOPE_CONFLICT")
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(w.public_key)).verify(
                    bytes.fromhex(endorsement.signature), signing_bytes(cfg, s, w.subject))
            except (InvalidSignature, ValueError):
                fail("INVALID_SIGNATURE")
            found[w.role] = w
        if set(found) != set(roles):
            fail("REQUIRED_INDEPENDENT_SIGNATURE_MISSING")
        return signed, found

    @staticmethod
    def _now(at):
        try:
            return _time(at or datetime.now(timezone.utc).isoformat())
        except (TypeError, ValueError):
            fail("INVALID_CLOCK")

    @staticmethod
    def _event(db, signed, now):
        s, hashed = signed.statement, digest(signed.statement)
        old = db.execute("SELECT digest FROM award_observation_event WHERE kind=? AND id=?", (s.kind, s.id)).fetchone()
        if old:
            if old[0] != hashed:
                fail("EVENT_ID_CONFLICT")
            return hashed, False
        db.execute("INSERT INTO award_observation_event(kind,id,digest,signed,recorded_at) VALUES(?,?,?,?,?)",
                   (s.kind, s.id, hashed, canonical_json(signed), now))
        return hashed, True

    def _local_filing(self, db, row, tables):
        """Resolve original persisted evidence, without current fixtures or rules."""
        tenant, case = self._config.tenant, row["case_id"]
        route, local = row["route"], json.loads(row["scope"])
        if route in {"correspondence", "historical-receipt"}:
            if "inbox_claim" not in tables:
                fail("PREEXISTING_LOCAL_FILING_REQUIRED")
            saved = db.execute("SELECT scope,state FROM inbox_claim WHERE tenant=? AND id=?", (tenant, case)).fetchone()
            if not saved or json.loads(saved["scope"]) != local:
                fail("LOCAL_FILING_SCOPE_CONFLICT")
            state = json.loads(saved["state"])
            if route == "historical-receipt":
                originals = [e for e in state["evidence"] if e["kind"] == "original_filing_receipt"]
                if len(originals) != 1 or state["submissions"]:
                    fail("ORIGINAL_EXTERNAL_RECEIPT_REQUIRED")
                fact = originals[0]
                body = fact["body"]
                expected = fingerprint([tenant, case, local, "vendor", body])
                lock = fingerprint([tenant, local, body["receipt_id"]])
                if (fact["source"] != "vendor" or body["kind"] != "original_filing_receipt"
                        or body.get("original_ref") is not None or fact["digest"] != expected
                        or row["packet_digest"] != lock or row["receipt_id"] != "HIST-" + lock):
                    fail("EXTERNAL_RECEIPT_CONFLICT")
                delivery = db.execute("SELECT claim,digest,received FROM inbox_delivery WHERE tenant=? AND account=? AND source='vendor' AND event_id=?",
                                      (tenant, local["account"], fact["event_id"])).fetchone()
                if not delivery or tuple(delivery) != (case, expected, fact["received_at"]):
                    fail("EXTERNAL_RECEIPT_DELIVERY_REQUIRED")
                if not _time(body["received_at"]) <= _time(body["observed_at"]) <= _time(fact["received_at"]):
                    fail("EXTERNAL_RECEIPT_TIME_CONFLICT")
                # The historical registry retains lineage, not the agreement version.
                # That version must be independently attested; never use today's rules.
                return None, fact
            originals = [r for r in state["submissions"] if r["action"] == "submit-claim"]
            if len(originals) != 1:
                fail("PREEXISTING_LOCAL_FILING_REQUIRED")
            receipt = originals[0]
            packet = receipt["packet"]
            if packet["tenant"] != tenant or packet["claim"] != case or packet["scope"] != local:
                fail("LOCAL_FILING_SCOPE_CONFLICT")
            identity = dict(tenant=tenant, vendor=local["vendor"], account=local["account"],
                            agreement_id=packet["agreement_id"], agreement_version=packet["version"],
                            service=local["service"], month=local["month"])
            if "identity" in row:
                identity["remedy"] = json.loads(row["identity"])[-1]
            else:
                remedies = ["availability", "resource-month/" + local["component"]]
                matches = [r for r in remedies if claim_identity._v1_key(identity | {"remedy": r}) == row["obligation"]]
                if len(matches) != 1:
                    fail("HISTORICAL_REMEDY_UNRESOLVED")
                identity["remedy"] = matches[0]
        elif route == "legacy":
            receipts = []
            if "dispute_receipts" in tables:
                receipts += [json.loads(r[0]) for r in db.execute(
                    "SELECT body FROM dispute_receipts WHERE tenant=? AND case_id=? AND action='submit-claim'", (tenant, case))]
            if "dispute_cases" in tables:
                saved = db.execute("SELECT state FROM dispute_cases WHERE tenant=? AND id=?", (tenant, case)).fetchone()
                if saved:
                    receipts += [r for r in json.loads(saved[0])["submissions"] if r["action"] == "submit-claim"]
            unique = {canonical_json(r): r for r in receipts}
            if len(unique) != 1:
                fail("PREEXISTING_LOCAL_FILING_REQUIRED")
            receipt = next(iter(unique.values()))
            packet = receipt["payload"]
            identity, expected_scope = claim_identity._legacy(packet)
            if identity["tenant"] != tenant or local != expected_scope:
                fail("LOCAL_FILING_SCOPE_CONFLICT")
        else:
            # An opaque reservation is useful for MOCK capacity tests only. It
            # never establishes delivery, regardless of its route/status spelling.
            if "identity" not in row:
                fail("HISTORICAL_FILING_UNRESOLVED")
            return None, None
        proof = claim_identity._receipt(receipt, packet)
        if (receipt["action"] != "submit-claim" or proof["receipt_id"] != row["receipt_id"]
                or proof["packet_digest"] != row["packet_digest"] or _time(proof["at"]) != _time(row["at"])):
            fail("LOCAL_RECEIPT_CONFLICT")
        return identity, receipt

    def _dispatch(self, db, claim_id):
        """Read both physical schemas; v1 versioned hashes are never v2 keys.

        Normalize proven history in memory only. A migrated copy coalesces with
        its original; different owners of one canonical obligation fail closed.
        No registry tables, receipts, locks, or migrations are written here.
        """
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        filings = {}
        try:
            for table in (claim_identity.TABLE, "claim_dispatch_identity"):
                if table not in tables:
                    continue
                for saved in db.execute(f"SELECT * FROM {table} WHERE step='initial'"):
                    row = dict(saved)
                    economic = json.loads(row["identity"]) if table == claim_identity.TABLE else None
                    if economic is not None:
                        if not isinstance(economic, list) or len(economic) != 7:
                            fail("INVALID_LOCAL_FILING")
                        if economic[0] != self._config.tenant:
                            continue
                    else:
                        # v1 omitted tenant; resolve it from the stored scope/case.
                        local = json.loads(row["scope"])
                        owner = local.get("tenant")
                        if row["route"] == "correspondence" and "inbox_claim" in tables:
                            owners = [r[0] for r in db.execute("SELECT tenant,scope FROM inbox_claim WHERE id=?", (row["case_id"],))
                                      if json.loads(r[1]) == local]
                            if len(owners) != 1:
                                fail("HISTORICAL_FILING_UNRESOLVED")
                            owner = owners[0]
                        if owner is None:
                            fail("HISTORICAL_FILING_UNRESOLVED")
                        if owner != self._config.tenant:
                            continue
                    identity, receipt = self._local_filing(db, row, tables)
                    if identity is not None:
                        proven = claim_identity._economic(**identity)
                        if economic is not None and economic != proven:
                            fail("LOCAL_FILING_SCOPE_CONFLICT")
                        if economic is None and row["obligation"] != claim_identity._v1_key(identity):
                            fail("LOCAL_FILING_SCOPE_CONFLICT")
                        economic = proven
                    if economic is None:
                        fail("HISTORICAL_FILING_UNRESOLVED")
                    identity_check = dict(tenant=economic[0], vendor=economic[1], account=economic[2],
                        agreement_id=economic[3], service=economic[4], month=economic[5], remedy=economic[6],
                        agreement_version="excluded-from-v2-identity")
                    if claim_identity._economic(**identity_check) != economic:
                        fail("INVALID_LOCAL_FILING")
                    key = claim_key(**identity_check)
                    if table == claim_identity.TABLE and row["obligation"] != key:
                        fail("LOCAL_FILING_SCOPE_CONFLICT")
                    normalized = {k: row[k] for k in ("step", "route", "case_id", "packet_digest", "receipt_id")}
                    normalized.update(obligation=key, scope=canonical_json(json.loads(row["scope"])),
                                      at=_time(row["at"]), identity=economic, receipt=receipt,
                                      contract_version=identity["agreement_version"] if identity else None)
                    old = filings.get(key)
                    if old is not None and old != normalized:
                        fail("CANONICAL_FILING_CONFLICT")
                    filings[key] = normalized
            # An older writer may append receipts after the v2 migration. Do
            # not overlook an unindexed second filing just because v2 exists.
            indexed = {(r["route"], r["case_id"], r["receipt_id"]) for r in filings.values()}
            for table, route in (("inbox_claim", "correspondence"), ("dispute_cases", "legacy")):
                if table in tables:
                    for case, raw in db.execute(f"SELECT id,state FROM {table} WHERE tenant=?", (self._config.tenant,)):
                        for receipt in json.loads(raw)["submissions"]:
                            if receipt["action"] == "submit-claim" and (route, case, receipt["id"]) not in indexed:
                                fail("UNINDEXED_HISTORICAL_FILING")
            if "dispute_receipts" in tables:
                for case, rid in db.execute("SELECT case_id,id FROM dispute_receipts WHERE tenant=? AND action='submit-claim'",
                                            (self._config.tenant,)):
                    if ("legacy", case, rid) not in indexed:
                        fail("UNINDEXED_HISTORICAL_FILING")
            rows = [r for r in filings.values() if r["case_id"] == claim_id]
            if len(rows) != 1:
                fail("PREEXISTING_LOCAL_FILING_REQUIRED")
            return rows[0]
        except AttributionError:
            raise
        except (sqlite3.DatabaseError, KeyError, TypeError, ValueError, IndexError):
            fail("INVALID_LOCAL_FILING")

    def _filing_scope(self, dispatch, body, issued_at):
        s = body.scope
        try:
            expected = claim_key(tenant=self._config.tenant, vendor=s.vendor_name, account=s.account_id,
                                 agreement_id=s.contract_id, agreement_version=s.contract_version,
                                 service=s.service_name, month=s.month, remedy=s.remedy)
        except ValueError:
            fail("LOCAL_FILING_SCOPE_CONFLICT")
        local = json.loads(dispatch["scope"])
        required = dict(account=s.account_id, vendor=s.vendor_name, contract=body.local_contract_id,
                        service=s.service_name, currency=s.currency, month=s.month)
        if dispatch["route"] == "legacy":
            # This historical wire format has no local contract alias or currency.
            required = dict(account=s.account_id, vendor=s.vendor_name, product=s.service_name, month=s.month)
            if body.local_contract_id != s.contract_id or s.currency != "USD" or s.minor_unit_conversion_rate != 100:
                fail("LOCAL_FILING_SCOPE_CONFLICT")
        # Human-readable labels share the registry's NFC/casefold semantics.
        for k in ("vendor", "service", "product"):
            if k in required and k in local:
                local[k], required[k] = claim_identity._label(local[k]), claim_identity._label(required[k])
        if (dispatch["obligation"] != expected or any(local.get(k) != v for k, v in required.items())
                or dispatch["contract_version"] not in (None, s.contract_version)):
            fail("LOCAL_FILING_SCOPE_CONFLICT")
        if dispatch["at"] > issued_at:
            fail("FILING_MUST_PREEXIST_REGISTRATION")
        if self._config.evidence_mode == "ACTUAL_NATIVE":
            witness = body.external_filing
            if dispatch["route"] != "historical-receipt" or witness is None or witness.evidence_mode != "ACTUAL_EXTERNAL":
                fail("ACTUAL_EXTERNAL_FILING_REQUIRED")
            fact = dispatch["receipt"]
            receipt = fact["body"]
            if (witness.receipt_id != receipt["receipt_id"] or witness.receipt_sha256 != digest(fact)
                    or witness.received_at != _time(receipt["received_at"])
                    or witness.submitted_to != receipt["submitted_to"]):
                fail("EXTERNAL_FILING_WITNESS_CONFLICT")
            if _time(fact["received_at"]) > issued_at:
                fail("FILING_MUST_PREEXIST_REGISTRATION")

    def filing_identity(self, claim_id):
        """Read-only review aid. An applicant-supplied digest is never sufficient."""
        with self._db() as db:
            return digest(self._dispatch(db, claim_id))

    def _filing_roles(self):
        return {"claim_registrar", "vendor_verifier"} if self._config.evidence_mode == "ACTUAL_NATIVE" else {"claim_registrar"}

    def _dispatch_matches(self, db, dispatch, hashed):
        if digest(dispatch) == hashed:
            return True
        # Pre-upgrade MOCK registrations signed the physical v1 row. Retain
        # that signature only while the original row AND its proven history
        # still exist. Old ACTUAL registrations without external proof close.
        if self._config.evidence_mode == "MOCK" and db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='claim_dispatch_identity'").fetchone():
            rows = db.execute("SELECT * FROM claim_dispatch_identity WHERE case_id=? AND receipt_id=? AND step='initial'",
                              (dispatch["case_id"], dispatch["receipt_id"])).fetchall()
            return len(rows) == 1 and digest(dict(rows[0])) == hashed
        return False

    def register_claim(self, envelope, *, at=None):
        now = self._now(at)
        body = _parse(FiledClaim, _parse(SignedStatement, envelope).statement.body)
        signed, witnesses = self._verified(envelope, "filed_claim", self._filing_roles(), now, body.scope)
        _unique(body.bills, "bill_id")
        if body.claimant_operator_id in {w.operator_id for w in witnesses.values()}:
            fail("CLAIMANT_CANNOT_REGISTER_SCOPE")
        with self._db(write=True) as db:
            dispatch = self._dispatch(db, body.claim_id)
            if not self._dispatch_matches(db, dispatch, body.dispatch_sha256):
                fail("LOCAL_FILING_IDENTITY_CONFLICT")
            self._filing_scope(dispatch, body, signed.statement.issued_at)
            s = body.scope
            old = db.execute("SELECT payload FROM award_observation_claim WHERE id=?", (body.claim_id,)).fetchone()
            if old and _parse(FiledClaim, json.loads(old[0])) != body:
                fail("IMMUTABLE_CLAIM_SCOPE_CONFLICT")
            owner = _scope_owner(s)
            for bill in body.bills:
                prior = db.execute("SELECT scope FROM award_observation_bill_owner WHERE bill_id=?", (bill.bill_id,)).fetchone()
                if prior and prior[0] != owner:
                    fail("IMMUTABLE_BILL_SCOPE_CONFLICT")
            hashed, created = self._event(db, signed, now)
            if created and old:
                fail("CLAIM_ALREADY_REGISTERED")
            if created:
                db.execute("INSERT INTO award_observation_claim VALUES(?,?,?,?)",
                           (body.claim_id, hashed, body.dispatch_sha256, canonical_json(body)))
                if self._config.evidence_mode == "ACTUAL_NATIVE":
                    db.execute("INSERT INTO award_observation_external_receipt VALUES(?,?)",
                               (digest([s.vendor_id, body.external_filing.receipt_id]), body.claim_id))
                for bill in body.bills:
                    db.execute("INSERT OR IGNORE INTO award_observation_bill_owner VALUES(?,?)", (bill.bill_id, owner))
        return dict(status="REGISTERED", claim_sha256=hashed, duplicate=not created)

    def _evidence_authority(self, db, hashed, kind, roles, scope, now):
        event = db.execute("SELECT signed,recorded_at FROM award_observation_event WHERE digest=?", (hashed,)).fetchone()
        if not event:
            fail("SIGNED_EVIDENCE_REQUIRED")
        _, witnesses = self._verified(json.loads(event["signed"]), kind, roles, event["recorded_at"], scope)
        if any(not w.valid_from <= now <= w.valid_until for w in witnesses.values()):
            fail("EXPIRED_WITNESS_GRANT")

    def _claim(self, db, claim_id, hashed, issued_at, now):
        row = db.execute("SELECT * FROM award_observation_claim WHERE id=?", (claim_id,)).fetchone()
        if not row or row["digest"] != hashed:
            fail("PREEXISTING_CLAIM_SCOPE_REQUIRED")
        registered = db.execute("SELECT recorded_at FROM award_observation_event WHERE digest=?", (hashed,)).fetchone()[0]
        if registered > issued_at:
            fail("CLAIM_MUST_PREEXIST_SIGNATURE")
        dispatch = self._dispatch(db, claim_id)
        if not self._dispatch_matches(db, dispatch, row["dispatch_sha256"]):
            fail("LOCAL_FILING_CHANGED")
        claim = _parse(FiledClaim, json.loads(row["payload"]))
        self._filing_scope(dispatch, claim, registered)
        self._evidence_authority(db, hashed, "filed_claim", self._filing_roles(), claim.scope, now)
        return claim

    def import_award(self, envelope, *, at=None):
        now = self._now(at)
        body = _parse(VendorAward, _parse(SignedStatement, envelope).statement.body)
        signed, witnesses = self._verified(envelope, "vendor_award", {"vendor_verifier", "finance_approver"}, now, body.scope)
        with self._db(write=True) as db:
            claim = self._claim(db, body.claim_id, body.claim_sha256, signed.statement.issued_at, now)
            if body.scope != claim.scope:
                fail("AWARD_CLAIM_SCOPE_CONFLICT")
            if claim.claimant_operator_id in {w.operator_id for w in witnesses.values()}:
                fail("CLAIMANT_CANNOT_CONFIRM_AWARD")
            source_key = digest([body.scope.vendor_id, body.vendor_award_ref])
            old = db.execute("SELECT id,payload FROM award_observation_award WHERE id=? OR source_key=?",
                             (signed.statement.id, source_key)).fetchone()
            if old and (old[0] != signed.statement.id or old[1] != canonical_json(body)):
                db.execute("INSERT OR IGNORE INTO award_observation_conflict VALUES(?,?)", (digest(signed), "CONFLICTING_VENDOR_AWARD"))
                return dict(status="QUARANTINED", issues=["CONFLICTING_VENDOR_AWARD"], actual_recovered_cash=None)
            hashed, created = self._event(db, signed, now)
            if created:
                db.execute("INSERT INTO award_observation_award VALUES(?,?,?,?,?)",
                           (signed.statement.id, body.claim_id, source_key, body.amount_minor, canonical_json(body)))
        return dict(status="VERIFIED_AWARD", award_id=signed.statement.id, sha256=hashed, duplicate=not created,
                    evidence_mode=self._config.evidence_mode, actual_recovered_cash=None)

    @staticmethod
    def _history_conflicts(db, snapshot):
        """Compare in observation-time order, including late-arriving reversals."""
        issues = set()
        current, current_bills = _facts(snapshot)
        for row in db.execute("SELECT payload FROM award_observation_snapshot"):
            previous = _parse(NativeSnapshot, json.loads(row[0]))
            prior = {c.id: c for c in previous.credits or []}
            prior_bills = {b.id: b for b in previous.bills or []}
            before, after = (previous, snapshot) if previous.observed_at <= snapshot.observed_at else (snapshot, previous)
            if after.available is True and after.list_complete is True and after.credits is not None:
                if {c.id for c in before.credits or []} - {c.id for c in after.credits}:
                    issues.add("CREDIT_DISAPPEARED")
            for ident in set(prior) & set(current):
                left, right = prior[ident], current[ident]
                if previous.observed_at > snapshot.observed_at:
                    left, right = right, left
                for field in ("vendor_id", "entity_id", "reference_bill_id", "accounting_date", "total_amount"):
                    a, b = getattr(left, field), getattr(right, field)
                    if a is not None and b is not None and a != b:
                        issues.add("CREDIT_IDENTITY_CHANGED")
                if left.remaining_amount and right.remaining_amount and right.remaining_amount.amount > left.remaining_amount.amount:
                    issues.add("UNAPPLICATION")
                if left.total_applied_amount and right.total_applied_amount and right.total_applied_amount.amount < left.total_applied_amount.amount:
                    issues.add("UNAPPLICATION")
                earlier, later = _links(left.applied_bills, "bill_id"), _links(right.applied_bills, "bill_id")
                if earlier is not None and later is not None and any(v > later.get(k, 0) for k, v in earlier.items()):
                    issues.add("UNAPPLICATION")
                if previous.observed_at == snapshot.observed_at and left != right:
                    issues.add("SAME_TIME_CONFLICT")
            for ident in set(prior_bills) & set(current_bills):
                left, right = prior_bills[ident], current_bills[ident]
                if previous.observed_at > snapshot.observed_at:
                    left, right = right, left
                for field in ("vendor", "entity_id", "amount"):
                    a, b = getattr(left, field), getattr(right, field)
                    if a is not None and b is not None and a != b:
                        issues.add("BILL_IDENTITY_CHANGED")
                earlier, later = _links(left.applied_vendor_credits, "id"), _links(right.applied_vendor_credits, "id")
                if earlier is not None and later is not None and any(v > later.get(k, 0) for k, v in earlier.items()):
                    issues.add("BILL_UNAPPLICATION")
                if previous.observed_at == snapshot.observed_at and left != right:
                    issues.add("SAME_TIME_CONFLICT")
        if any(c.archived_at not in (None, "UNKNOWN") for c in current.values()):
            issues.add("ARCHIVED_CREDIT_REVIEW")
        if any(b.archived_at not in (None, "UNKNOWN") or b.status in {"VOIDED", "CANCELED", "CANCELLED", "DELETED"}
               for b in current_bills.values()):
            issues.add("VOIDED_OR_ARCHIVED_BILL_REVIEW")
        return sorted(issues)

    def observe(self, envelope, *, at=None):
        now = self._now(at)
        signed, _ = self._verified(envelope, "native_snapshot", {"ramp_observer"}, now)
        body = _parse(NativeSnapshot, signed.statement.body)
        expected = "LIVE_RAMP_SANDBOX" if self._config.evidence_mode == "ACTUAL_NATIVE" else "DETERMINISTIC_REPLAY"
        if body.source != expected:
            fail("MOCK_AND_NATIVE_PROVENANCE_CONFLICT")
        if body.observed_at > signed.statement.issued_at:
            fail("CAPTURE_MUST_PREEXIST_SIGNATURE")
        with self._db(write=True) as db:
            old = db.execute("SELECT digest FROM award_observation_event WHERE kind='native_snapshot' AND id=?", (signed.statement.id,)).fetchone()
            hashed = digest(signed.statement)
            if old and old[0] != hashed:
                db.execute("INSERT OR IGNORE INTO award_observation_conflict VALUES(?,?)", (hashed, "OBSERVATION_ID_CONFLICT"))
                return dict(status="QUARANTINED", issues=["OBSERVATION_ID_CONFLICT"], actual_recovered_cash=None)
            hashed, created = self._event(db, signed, now)
            if created:
                issues = []
                try:
                    _facts(body)
                    issues = self._history_conflicts(db, body)
                except AttributionError as exc:
                    issues = [str(exc)]
                status = "RECORDED"
                if body.available is not True or body.credits is None:
                    status = "UNAVAILABLE"
                elif body.scopes is None or "vendors:read" not in body.scopes:
                    status = "SCOPE_UNCONFIRMED"
                elif body.list_complete is not True:
                    status = "PARTIAL"
                elif not body.credits:
                    status = "EMPTY"
                if issues:
                    status = "QUARANTINED"
                    db.execute("INSERT OR IGNORE INTO award_observation_conflict VALUES(?,?)", (hashed, ",".join(issues)))
                db.execute("INSERT INTO award_observation_snapshot VALUES(?,?,?,?,?)",
                           (hashed, body.observed_at, canonical_json(body), status, canonical_json(issues)))
            row = db.execute("SELECT status,issues FROM award_observation_snapshot WHERE digest=?", (hashed,)).fetchone()
            quarantined = bool(db.execute("SELECT 1 FROM award_observation_conflict LIMIT 1").fetchone())
        return dict(status="QUARANTINED" if quarantined else row["status"], snapshot_sha256=hashed,
                    issues=json.loads(row["issues"]), duplicate=not created, actual_recovered_cash=None)

    def _binding_facts(self, db, binding, scope, now):
        latest = db.execute("SELECT * FROM award_observation_snapshot ORDER BY observed_at DESC,rowid DESC LIMIT 1").fetchone()
        if not latest or latest["digest"] != binding.snapshot_sha256:
            fail("CURRENT_EXACT_SNAPSHOT_REQUIRED")
        if latest["status"] != "RECORDED":
            fail("COMPLETE_NATIVE_OBSERVATION_REQUIRED")
        snapshot = _parse(NativeSnapshot, json.loads(latest["payload"]))
        if not _fresh(snapshot.observed_at, now):
            fail("STALE_OR_FUTURE_OBSERVATION")
        if not {"vendors:read", "bills:read"} <= set(snapshot.scopes or []):
            fail("SCOPE_UNCONFIRMED")
        credits, bills = _facts(snapshot)
        credit = credits.get(binding.credit_id)
        if credit is None:
            fail("EXACT_NATIVE_CREDIT_REQUIRED")
        if any(m is None for m in (credit.total_amount, credit.remaining_amount, credit.total_applied_amount)):
            fail("UNKNOWN_CREDIT_AMOUNTS")
        if credit.archived_at is not None:
            fail("ACTIVE_CREDIT_UNCONFIRMED")
        unit = (scope.currency, scope.minor_unit_conversion_rate)
        if _unit(credit.total_amount) != unit or (binding.currency, binding.minor_unit_conversion_rate) != unit:
            fail("CROSS_CURRENCY")
        if credit.vendor_id != scope.vendor_id:
            fail("VENDOR_SCOPE_UNCONFIRMED")
        links, drafts = _links(credit.applied_bills, "bill_id"), _links(credit.applied_draft_bills, "bill_id")
        if links is None or drafts is None:
            fail("UNKNOWN_APPLICATION_COVERAGE")
        for share in binding.applications:
            bill = bills.get(share.bill_id)
            if not bill or not bill.amount or bill.applied_vendor_credits is None:
                fail("BILL_READBACK_MISSING")
            if not bill.vendor or bill.vendor.id != scope.vendor_id:
                fail("BILL_VENDOR_SCOPE_UNCONFIRMED")
            if _unit(bill.amount) != unit:
                fail("CROSS_CURRENCY")
            if bill.archived_at is not None or bill.status not in {"OPEN", "PAID", "PARTIALLY_PAID", "SCHEDULED", "APPROVED", "PAYMENT_PENDING"}:
                fail("BILL_PAYABLE_STATUS_UNCONFIRMED")
            reverse = _links(bill.applied_vendor_credits, "id")
            if reverse is None or links.get(bill.id, 0) != reverse.get(credit.id, 0):
                fail("RECIPROCAL_CONFLICT")
            if bill.id in drafts:
                fail("DRAFT_APPLICATION_UNSUPPORTED")
            if share.amount_minor > links.get(bill.id, 0):
                fail("NATIVE_PAIR_AMOUNT_EXCEEDED")
        return snapshot, credit, bills, links

    def attribute(self, envelope, *, at=None):
        """One signed cumulative award-credit allocation at one exact snapshot.

        Multiple rows implement N:M. New snapshots require new explicit signatures;
        no old binding is replayed, delta-added, prorated, or blindly retried.
        """
        now = self._now(at)
        raw = _parse(SignedStatement, envelope)
        if raw.statement.body.get("basis") != "EXACT_EXPLICIT_ALLOCATION":
            fail("SPLIT_BASIS_REQUIRED")
        body = _parse(Attribution, raw.statement.body)
        _unique(body.applications, "bill_id")
        with self._db(write=True) as db:
            if db.execute("SELECT 1 FROM award_observation_conflict LIMIT 1").fetchone():
                fail("QUARANTINED_REVIEW_REQUIRED")
            award_row = db.execute("SELECT payload FROM award_observation_award WHERE id=?", (body.award_id,)).fetchone()
            if not award_row:
                fail("INDEPENDENT_VERIFIED_AWARD_REQUIRED")
            award = _parse(VendorAward, json.loads(award_row[0]))
            signed, witnesses = self._verified(raw, "attribution", {"finance_approver"}, now, award.scope)
            claim = self._claim(db, award.claim_id, body.claim_sha256, signed.statement.issued_at, now)
            if claim.scope != award.scope or body.claim_sha256 != award.claim_sha256:
                fail("ATTRIBUTION_CLAIM_CONFLICT")
            if witnesses["finance_approver"].operator_id == claim.claimant_operator_id:
                fail("CLAIMANT_CANNOT_APPROVE_ATTRIBUTION")
            snapshot, credit, bills, links = self._binding_facts(db, body, claim.scope, now)
            snapshot_event = db.execute("SELECT recorded_at FROM award_observation_event WHERE digest=?", (body.snapshot_sha256,)).fetchone()
            award_event = db.execute("SELECT recorded_at,digest FROM award_observation_event WHERE kind='vendor_award' AND id=?", (body.award_id,)).fetchone()
            if max(snapshot_event[0], award_event[0]) > signed.statement.issued_at:
                fail("EVIDENCE_MUST_PREEXIST_APPROVAL")
            self._evidence_authority(db, award_event["digest"], "vendor_award",
                                     {"vendor_verifier", "finance_approver"}, award.scope, now)
            self._evidence_authority(db, body.snapshot_sha256, "native_snapshot", {"ramp_observer"}, None, now)
            allowed = {b.bill_id: b for b in claim.bills}
            for share in body.applications:
                if share.bill_id not in allowed:
                    fail("PREEXISTING_BILL_SCOPE_REQUIRED")
                used = db.execute("""SELECT COALESCE(SUM(x.amount),0) FROM award_observation_application x
                    JOIN award_observation_allocation a ON a.digest=x.binding JOIN award_observation_award w ON w.id=a.award_id
                    WHERE a.snapshot=? AND w.claim_id=? AND x.bill_id=? AND a.digest<>?""",
                    (body.snapshot_sha256, award.claim_id, share.bill_id, digest(signed.statement))).fetchone()[0]
                if used + share.amount_minor > allowed[share.bill_id].eligible_minor:
                    fail("CLAIM_BILL_CAP_EXCEEDED")
            if sum(s.amount_minor for s in body.applications) > body.posted_minor:
                fail("ALLOCATION_APPLICATION_CAP_EXCEEDED")
            # A real attribution never appropriates a credit used by the simulation.
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='allocation_credit'").fetchone():
                if db.execute("SELECT 1 FROM allocation_credit WHERE tenant=? AND id=?", (self._config.tenant, credit.id)).fetchone():
                    fail("SIMULATED_LEDGER_CREDIT_RESERVED")
            owner = _scope_owner(claim.scope)
            prior = db.execute("SELECT scope FROM award_observation_credit_owner WHERE credit_id=?", (credit.id,)).fetchone()
            if prior and prior[0] != owner:
                fail("CROSS_ACCOUNT_OR_CONTRACT_FANOUT")
            hashed, created = self._event(db, signed, now)
            if created:
                db.execute("INSERT OR IGNORE INTO award_observation_credit_owner VALUES(?,?)", (credit.id, owner))
                db.execute("INSERT OR IGNORE INTO award_observation_credit_capacity VALUES(?,?,?)", (body.snapshot_sha256, credit.id, credit.total_amount.amount))
                for share in body.applications:
                    db.execute("INSERT OR IGNORE INTO award_observation_pair_capacity VALUES(?,?,?,?)", (body.snapshot_sha256, credit.id, share.bill_id, links.get(share.bill_id, 0)))
                    db.execute("INSERT OR IGNORE INTO award_observation_bill_capacity VALUES(?,?,?)", (body.snapshot_sha256, share.bill_id, bills[share.bill_id].amount.amount))
                db.execute("INSERT INTO award_observation_allocation VALUES(?,?,?,?,?)", (hashed, body.snapshot_sha256, body.award_id, credit.id, body.posted_minor))
                for share in body.applications:
                    db.execute("INSERT INTO award_observation_application VALUES(?,?,?)", (hashed, share.bill_id, share.amount_minor))
        return dict(status="ATTRIBUTED_OBSERVATION", sha256=hashed, duplicate=not created,
                    evidence_mode=self._config.evidence_mode, actual_recovered_cash=None)

    def summary(self, tenant, business_id, *, at=None):
        """Safe complementary summary. Never combine these amounts with the demo ledger."""
        if (tenant, business_id) != (self._config.tenant, self._config.business_id):
            fail("SUMMARY_AUDIENCE_CONFLICT")
        now = self._now(at)
        with self._db() as db:
            row = db.execute("SELECT * FROM award_observation_snapshot ORDER BY observed_at DESC,rowid DESC LIMIT 1").fetchone()
            conflicts = sorted({r[0] for r in db.execute("SELECT reason FROM award_observation_conflict")})
            result = dict(status="UNAVAILABLE", evidence_mode=self._config.evidence_mode,
                          environment="sandbox", actual_recovered_cash=None, actual_recovery=None,
                          external_writes=False, captured_credits=None, inventory_complete=None,
                          snapshot_sha256=None, observed_at=None, issues=conflicts, credits=[],
                          verified_award_count=db.execute("SELECT COUNT(*) FROM award_observation_award").fetchone()[0],
                          historical_binding_count=db.execute("SELECT COUNT(*) FROM award_observation_allocation").fetchone()[0],
                          active_binding_count=0, awards_are_historical=True,
                          attribution_suspended=bool(conflicts), attribution_status="NO_VERIFIED_ATTRIBUTION")
            if not row:
                return result
            snapshot = _parse(NativeSnapshot, json.loads(row["payload"]))
            result.update(status="QUARANTINED" if conflicts else row["status"],
                          snapshot_sha256=row["digest"], observed_at=snapshot.observed_at,
                          inventory_complete=snapshot.list_complete,
                          captured_credits=len(snapshot.credits) if snapshot.available is True and snapshot.credits is not None else None,
                          freshness="FRESH" if _fresh(snapshot.observed_at, now) else "STALE_OR_FUTURE")
            active = not conflicts and row["status"] == "RECORDED" and _fresh(snapshot.observed_at, now)
            bindings = db.execute("SELECT * FROM award_observation_allocation WHERE snapshot=?", (row["digest"],)).fetchall() if active else []
            valid = []
            for binding in bindings:
                event = db.execute("SELECT signed FROM award_observation_event WHERE digest=?", (binding["digest"],)).fetchone()
                signed = _parse(SignedStatement, json.loads(event[0]))
                award_row = db.execute("SELECT payload FROM award_observation_award WHERE id=?", (binding["award_id"],)).fetchone()
                award = _parse(VendorAward, json.loads(award_row[0]))
                try:
                    self._verified(signed, "attribution", {"finance_approver"}, now, award.scope)
                    self._claim(db, award.claim_id, award.claim_sha256, signed.statement.issued_at, now)
                    award_hash = db.execute("SELECT digest FROM award_observation_event WHERE kind='vendor_award' AND id=?", (binding["award_id"],)).fetchone()[0]
                    self._evidence_authority(db, award_hash, "vendor_award", {"vendor_verifier", "finance_approver"}, award.scope, now)
                    self._evidence_authority(db, row["digest"], "native_snapshot", {"ramp_observer"}, None, now)
                except AttributionError as exc:
                    result["issues"].append(str(exc))
                    continue
                valid.append(binding)
            result["active_binding_count"] = len(valid)
            if valid:
                result["attribution_status"] = "VERIFIED_NATIVE_OBSERVATION" if self._config.evidence_mode == "ACTUAL_NATIVE" else "MOCK_ATTRIBUTION_ONLY"
            elif result["historical_binding_count"]:
                result["attribution_status"] = "HISTORICAL_APPROVAL_NOT_CURRENT"
            for credit in snapshot.credits or []:
                posted = sum(b["amount"] for b in valid if b["credit_id"] == credit.id)
                applied = sum(db.execute("SELECT COALESCE(SUM(amount),0) FROM award_observation_application WHERE binding=?", (b["digest"],)).fetchone()[0]
                              for b in valid if b["credit_id"] == credit.id)
                def observed_sum(rows):
                    return sum(a.amount.amount for a in rows) if rows is not None and all(a.amount is not None for a in rows) else None
                observed = observed_sum(credit.applied_bills)
                total = credit.total_amount.amount if credit.total_amount else None
                stage = "APPLIED_UNATTRIBUTED" if observed is not None and observed > 0 else "POSTED_UNATTRIBUTED" if total is not None else "OBSERVED_UNATTRIBUTED"
                if applied:
                    stage = "RAMP_APPLIED_ATTRIBUTED" if self._config.evidence_mode == "ACTUAL_NATIVE" else "MOCK_APPLIED_ATTRIBUTED"
                elif posted:
                    stage = "POSTED_ATTRIBUTED"
                result["credits"].append(dict(credit_id=credit.id, stage=stage,
                    currency=credit.total_amount.currency_code if credit.total_amount else None,
                    minor_unit_conversion_rate=credit.total_amount.minor_unit_conversion_rate if credit.total_amount else None,
                    observed_total_minor=total,
                    observed_remaining_minor=credit.remaining_amount.amount if credit.remaining_amount else None,
                    observed_provider_applied_minor=credit.total_applied_amount.amount if credit.total_applied_amount else None,
                    observed_applied_bills_minor=observed,
                    observed_applied_drafts_minor=observed_sum(credit.applied_draft_bills),
                    attributed_posted_minor=posted, attributed_applied_minor=applied,
                    unattributed_posted_minor=total-posted if total is not None else None,
                    unattributed_applied_minor=observed-applied if observed is not None else None,
                    allocation_basis="EXACT_EXPLICIT_ALLOCATION" if posted else "NO_VERIFIED_BASIS",
                    actual_recovered_cash=None))
        return result

    def history(self):
        """Metadata only; exact signed evidence remains in the protected local DB."""
        with self._db() as db:
            return [dict(row) for row in db.execute("SELECT sequence,kind,id,digest,recorded_at FROM award_observation_event ORDER BY sequence")]
