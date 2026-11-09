"""Offline trust roots and single-use reviewer mandates for an exact local request and optional native effect."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, localcontext
from hashlib import sha256
import json
import re
from secrets import token_hex
import sqlite3
from time import time
from typing import Annotated, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, field_validator, model_validator

from .contracts import fingerprint
from .correspondence_types import Id
from .source_config import EdVerifier, Key, Mode, Strict, Subject
from .storage import database

NATIVE_ACTIONS = {"bill.comment.create": "bill", "blank_canvas.metadata.update": "approval_trigger_instance"}
NativeAction = Literal["bill.comment.create", "blank_canvas.metadata.update"]
ObjectID = Annotated[str, Field(pattern=r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")]
DENIED = "A current, independently registered mandate for this exact action is required"


def native_effect_digest(method, path, body_bytes):
    """Hash the actual prepared API method, absolute API path and exact HTTP content bytes."""
    if method not in {"POST", "PATCH"} or not isinstance(body_bytes, bytes):
        raise ValueError("Use the final native request method, API path and encoded bytes")
    return fingerprint(["uptime-native-effect/1", method, path, sha256(body_bytes).hexdigest()])


class Effect(Strict):
    business_id: ObjectID
    resource_type: Literal["bill", "approval_trigger_instance"]
    resource_id: ObjectID
    action: NativeAction
    payload_sha256: Key

    @model_validator(mode="after")
    def valid_target(self):
        if self.resource_type != NATIVE_ACTIONS[self.action]:
            raise ValueError("Native operation and resource type do not match")
        return self


def native_effect_from_request(business_id, method, path, body_bytes):
    """Derive resource identity from the prepared provider request instead of trusting an object's label."""
    patterns = {
        "POST": (r"/developer/v1/comments/bills/([^/]+)", "bill.comment.create"),
        "PATCH": (r"/developer/v1/blank-canvas-approvals/([^/]+)/metadata", "blank_canvas.metadata.update"),
    }
    if method not in patterns:
        raise PermissionError(DENIED)
    pattern, action = patterns[method]
    match = re.fullmatch(pattern, path)
    if not match:
        raise PermissionError(DENIED)
    try:
        return Effect(business_id=business_id, resource_id=match[1], resource_type=NATIVE_ACTIONS[action],
                      action=action, payload_sha256=native_effect_digest(method, path, body_bytes))
    except ValueError:
        raise PermissionError(DENIED) from None


class Issuer(Strict):
    subject: Subject
    public_key: EdVerifier
    # Empty business scope allows only local actions. Native permissions are enumerated.
    business_id: ObjectID | None = None
    native_actions: tuple[NativeAction, ...] = ()
    local_purposes: tuple[Literal["workspace", "claim-filing", "vendor-promotion", "policy-change", "credit-allocation"], ...] = ("workspace",)

    @model_validator(mode="after")
    def bounded(self):
        if bool(self.business_id) != bool(self.native_actions) or len(set(self.native_actions)) != len(self.native_actions):
            raise ValueError("Native issuer registration requires an exact business and distinct allowed actions")
        return self


class ClaimDecision(Strict):
    claim_id: str = Field(pattern=r"^inbox-[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
    action: Literal["approve-claim", "submit-claim", "approve-response", "submit-response"]
    scope_sha256: Key
    packet_sha256: Key
    currency: Literal["USD"]
    max_amount_cents: int = Field(ge=0, le=10**17)


def claim_preview(action, scope, packet):
    # A sub-cent claim must still fit under the explicit integer-cent ceiling.
    amount = Decimal(packet["requested"])
    if not amount.is_finite() or amount < 0 or packet["scope"] != scope:
        raise ValueError("Invalid claim amount or scope")
    with localcontext() as context:
        context.prec = max(context.prec, len(amount.as_tuple().digits) + 2)
        required_cents = int((amount * 100).to_integral_value(rounding=ROUND_CEILING))
    return ClaimDecision(claim_id=packet["claim"], action=action, scope_sha256=fingerprint(scope),
                         packet_sha256=fingerprint(packet), currency=scope["currency"],
                         max_amount_cents=required_cents)


def check_claim_decision(principal, action, scope, packet, db):
    decision = getattr(principal, "claim_decision", None)
    if decision is None:
        if principal.tenant == "bears" and not getattr(principal, "mandate_id", None):
            return
        raise PermissionError(DENIED)
    recheck_financial_mandate(db, principal)
    actual = claim_preview(action, scope, packet)
    if (decision.max_amount_cents < actual.max_amount_cents or
            decision.model_dump(exclude={"max_amount_cents"}) != actual.model_dump(exclude={"max_amount_cents"})):
        raise PermissionError(DENIED)


class CreditDecision(Strict):
    claim_id: str = Field(pattern=r"^inbox-[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
    action: Literal["record-credit", "apply-balance"]
    scope_sha256: Key
    contract_version: str = Field(min_length=1,max_length=512)
    claim_state_sha256: Key
    journal_sequence: int = Field(ge=0)
    award_id: str = Field(min_length=1,max_length=512)
    credit_id: str = Field(min_length=1,max_length=512)
    bill_id: str | None = Field(default=None,min_length=1,max_length=512)
    currency: Literal["USD"]
    plan_sha256: Key
    amount_cents: int = Field(gt=0,le=10**15)
    max_amount_cents: int = Field(ge=0,le=10**15)

    @model_validator(mode="after")
    def bounded(self):
        if (self.action == "apply-balance") != bool(self.bill_id):
            raise ValueError("A credit application must identify its actual bill")
        return self


def recheck_financial_mandate(db, principal):
    row = db.execute("SELECT signed FROM reviewer_mandate WHERE id=? AND reviewer=? AND used=1 AND revoked=0",
                     (getattr(principal, "mandate_id", None), principal.subject)).fetchone()
    if not row:
        raise PermissionError(DENIED)
    signed = SignedMandate.model_validate_json(row[0])
    _verified(db, signed, time())
    if (signed.mandate.claim != getattr(principal, "claim_decision", None)
            or signed.mandate.credit != getattr(principal, "credit_decision", None)):
        raise PermissionError(DENIED)


def check_credit_decision(db, principal, actual):
    """Check the exact authorized allocation and both mutable ledger versions under the SQL write lock."""
    decision = getattr(principal, "credit_decision", None)
    if decision is None:
        if principal.tenant == "bears" and not getattr(principal, "mandate_id", None):
            return
        raise PermissionError(DENIED)
    recheck_financial_mandate(db, principal)
    if (decision.amount_cents > decision.max_amount_cents or decision.model_dump(exclude={"max_amount_cents"})
            != actual.model_dump(exclude={"max_amount_cents"})):
        raise PermissionError(DENIED)
    row = db.execute("SELECT scope,state FROM inbox_claim WHERE tenant=? AND id=?", (principal.tenant, actual.claim_id)).fetchone()
    if (not row or fingerprint([json.loads(row["scope"]),json.loads(row["state"])]) != actual.claim_state_sha256
            or db.execute("SELECT COALESCE(MAX(sequence),0) FROM allocation_journal").fetchone()[0] != actual.journal_sequence):
        raise PermissionError("Claim or allocation journal changed after the mandate was issued")


def local_purpose(path):
    if path == "/api/policy":
        return "policy-change"
    if "/actions/" in path:
        action = path.rsplit("/",1)[-1]
        if path.startswith(("/api/vendors/", "/api/onboarding/")):
            return "vendor-promotion"
        if action in {"approve-claim","submit-claim","approve-response","submit-response"}:
            return "claim-filing"
        if path.startswith("/api/cases/inbox-") and action in {"record-credit","apply-balance"}:
            return "credit-allocation"
        if path.startswith("/api/cases/"):
            # Legacy allocation writes omit the final provider bill and credit plan from their signed bodies.
            return "unsupported-legacy-case-action"
    return "workspace"


@dataclass(frozen=True)
class ClaimedMandate:
    mandate_id: str
    ticket: str | None
    claim_decision: ClaimDecision | None
    credit_decision: CreditDecision | None


class Mandate(Strict):
    schema_version: Literal["uptime-reviewer-mandate/1"]
    mandate_id: ObjectID
    workspace_id: Key
    tenant: Id
    mode: Mode
    issuer: Subject
    reviewer: Subject
    reviewer_key_sha256: Key
    valid_from: int
    valid_until: int
    path: str = Field(pattern=r"^/api/[a-zA-Z0-9_./~-]+$", max_length=1024)
    body_sha256: Key
    effect: Effect | None = None
    claim: ClaimDecision | None = None
    credit: CreditDecision | None = None

    @field_validator("path")
    @classmethod
    def exact_path(cls, path):
        if path.startswith("/api/auth/") or any(p in {"", ".", ".."} for p in path[1:].split("/")):
            raise ValueError("Choose an exact local API mutation path")
        return path

    @model_validator(mode="after")
    def bounded(self):
        if self.issuer == self.reviewer or not 0 < self.valid_until - self.valid_from <= 86400:
            raise ValueError("An independent issuer and a validity window of at most one day are required")
        if self.claim:
            c = self.claim
            if self.credit or self.effect or self.path not in {f"/api/cases/{c.claim_id}/actions/{c.action}",
                                               f"/api/correspondence/claims/{c.claim_id}/actions/{c.action}"}:
                raise ValueError("Claim decision does not match the exact local action")
        elif local_purpose(self.path) == "claim-filing":
            raise ValueError("A filing needs a signed estimate and exact scope")
        if self.credit:
            c = self.credit
            if self.effect or self.claim or self.path != f"/api/cases/{c.claim_id}/actions/{c.action}":
                raise ValueError("Credit decision does not match the exact local action")
        elif local_purpose(self.path) == "credit-allocation":
            raise ValueError("A credit mutation requires an exact allocation plan")
        return self

    def signing_bytes(self):
        data = self.model_dump(mode="json")
        if data["credit"] is None:
            del data["credit"]
        if data["claim"] is None:
            del data["claim"]  # Preserve signing bytes of version-one non-claim mandates.
        return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class SignedMandate(Strict):
    mandate: Mandate
    signature: Annotated[str, Field(pattern=r"^[0-9a-f]{128}$")]


def setup(db):
    db.execute("CREATE TABLE IF NOT EXISTS mandate_workspace(id INTEGER PRIMARY KEY CHECK(id=1), realm TEXT NOT NULL UNIQUE)")
    db.execute("INSERT OR IGNORE INTO mandate_workspace VALUES(1,?)", (token_hex(32),))
    db.execute("""CREATE TABLE IF NOT EXISTS mandate_issuer(subject TEXT PRIMARY KEY, public_key TEXT NOT NULL UNIQUE,
               registration TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS source_key_history(public_key TEXT PRIMARY KEY, subject TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS reviewer_mandate(id TEXT PRIMARY KEY, issuer TEXT NOT NULL, reviewer TEXT NOT NULL,
               path TEXT NOT NULL, body TEXT NOT NULL, signed TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
               used INTEGER NOT NULL DEFAULT 0, ticket TEXT, ticket_until REAL, instance TEXT,
               FOREIGN KEY(issuer) REFERENCES mandate_issuer(subject))""")
    db.execute("CREATE INDEX IF NOT EXISTS reviewer_mandate_lookup ON reviewer_mandate(reviewer,path,body,used,revoked)")


def _workspace(db):
    row = db.execute("""SELECT a.mode,a.tenant,a.rehearsal,m.realm FROM authority_workspace a,mandate_workspace m
                        WHERE a.id=1 AND m.id=1""").fetchone()
    if not row or row["rehearsal"]:
        raise PermissionError("A named, non-rehearsal installation is required")
    return row


def describe(path, reviewer):
    with database(path) as db:
        workspace = _workspace(db)
        row = db.execute("SELECT public_key FROM authority_user WHERE subject=? AND role='reviewer'", (reviewer,)).fetchone()
        if not row:
            raise ValueError("Reviewer has no enrolled public key")
        return {"workspace_id":workspace["realm"], "tenant":workspace["tenant"], "mode":workspace["mode"],
                "reviewer":reviewer, "reviewer_key_sha256":sha256(row["public_key"]).hexdigest()}


def remember_source_keys(path, bindings):
    """Source keys stay purpose-bound after rotation so retiring one cannot turn it into an issuer key."""
    if not bindings:
        return
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        for subject, public in bindings:
            if db.execute("SELECT 1 FROM mandate_issuer WHERE subject=? OR public_key=?", (subject, public)).fetchone():
                raise PermissionError("Mandate issuer identities and keys cannot sign intake")
            db.execute("INSERT OR IGNORE INTO source_key_history VALUES(?,?)", (public,subject))
            row = db.execute("SELECT subject FROM source_key_history WHERE public_key=?", (public,)).fetchone()
            if row[0] != subject:
                raise PermissionError("A source key cannot transfer to a different identity")


def register_issuer(path, issuer):
    """Trust an externally verified public key offline. Installed keys and revocations cannot be overwritten."""
    issuer = Issuer.model_validate(issuer)
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        _workspace(db)
        if db.execute("SELECT 1 FROM source_key_history WHERE subject=? OR public_key=?",
                      (issuer.subject,issuer.public_key)).fetchone():
            raise PermissionError("Source identities and keys cannot issue reviewer mandates")
        if db.execute("SELECT 1 FROM authority_user WHERE subject=?", (issuer.subject,)).fetchone():
            raise PermissionError("A reviewer account cannot be a mandate issuer")
        try:
            db.execute("INSERT INTO mandate_issuer(subject,public_key,registration) VALUES(?,?,?)",
                       (issuer.subject, issuer.public_key, issuer.model_dump_json()))
        except sqlite3.IntegrityError:
            raise ValueError("Issuer subject or public key was previously registered") from None


def _verified(db, signed, at):
    m = signed.mandate
    realm = _workspace(db)
    row = db.execute("SELECT registration FROM mandate_issuer WHERE subject=? AND revoked=0", (m.issuer,)).fetchone()
    account = db.execute("SELECT public_key FROM authority_user WHERE subject=? AND role='reviewer'", (m.reviewer,)).fetchone()
    if (m.workspace_id != realm["realm"] or m.tenant != realm["tenant"] or m.mode != realm["mode"]
            or not row or not account or sha256(account["public_key"]).hexdigest() != m.reviewer_key_sha256
            or not m.valid_from <= at < m.valid_until):
        raise PermissionError(DENIED)
    issuer = Issuer.model_validate_json(row[0])
    if local_purpose(m.path) not in issuer.local_purposes:
        raise PermissionError(DENIED)
    if m.effect and (m.effect.business_id != issuer.business_id or m.effect.action not in issuer.native_actions):
        raise PermissionError(DENIED)
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(issuer.public_key)).verify(bytes.fromhex(signed.signature), m.signing_bytes())
    except (ValueError, InvalidSignature):
        raise PermissionError(DENIED) from None


def install(path, signed):
    signed = SignedMandate.model_validate(signed)
    m = signed.mandate
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        _verified(db, signed, time())
        try:
            db.execute("INSERT INTO reviewer_mandate(id,issuer,reviewer,path,body,signed) VALUES(?,?,?,?,?,?)",
                       (m.mandate_id, m.issuer, m.reviewer, m.path, m.body_sha256, signed.model_dump_json()))
        except sqlite3.IntegrityError:
            raise ValueError("Mandate identifier was previously registered") from None


def revoke(path, kind, identity):
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        _workspace(db)
        if kind == "issuer":
            changed = db.execute("UPDATE mandate_issuer SET revoked=1 WHERE subject=?", (identity,))
        elif kind == "mandate":
            changed = db.execute("UPDATE reviewer_mandate SET revoked=1 WHERE id=?", (identity,))
        else:
            raise ValueError("Choose issuer or mandate")
        if changed.rowcount != 1:
            raise ValueError("Unrecognized authority identifier")


def claim(path, principal, request_path, body_digest, instance, required):
    """Atomically consume an exact local grant. A native ticket stays private to this authenticated request."""
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute("""SELECT signed FROM reviewer_mandate WHERE reviewer=? AND path=? AND body=?
                             AND revoked=0 AND used=0""", (principal.subject, request_path, body_digest))
        valid = []
        at = time()
        for row in rows:
            signed = SignedMandate.model_validate_json(row["signed"])
            try:
                _verified(db, signed, at)
            except PermissionError:
                continue
            valid.append(signed.mandate)
        if not valid and not required:
            return None
        if len(valid) != 1:
            raise PermissionError(DENIED)
        m = valid[0]
        ticket = token_hex(32) if m.effect else None
        db.execute("UPDATE reviewer_mandate SET used=1,ticket=?,ticket_until=?,instance=? WHERE id=?",
                   (sha256(ticket.encode()).hexdigest() if ticket else None, min(at+60, m.valid_until), instance, m.mandate_id))
        return ClaimedMandate(m.mandate_id, ticket, m.claim, m.credit)


def consume_native(path, principal, instance, ticket, effect):
    if not ticket:
        raise PermissionError(DENIED)
    at = time()
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT signed FROM reviewer_mandate WHERE reviewer=? AND ticket=? AND instance=?
                            AND ticket_until>? AND revoked=0 AND used=1""",
                         (principal.subject, sha256(ticket.encode()).hexdigest(), instance, at)).fetchone()
        if not row:
            raise PermissionError(DENIED)
        signed = SignedMandate.model_validate_json(row["signed"])
        _verified(db, signed, at)
        m = signed.mandate
        if m.effect != effect or m.tenant != principal.tenant:
            raise PermissionError(DENIED)
        db.execute("UPDATE reviewer_mandate SET ticket=NULL WHERE id=?", (m.mandate_id,))
        return m.mandate_id
