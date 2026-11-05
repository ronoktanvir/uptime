"""Offline, issuer-signed pricing evidence scoped to the current installed Ramp bill capture."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from typing import Annotated, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, model_validator

from .contracts import Citation, Outcome, fingerprint
from .correspondence_types import instant
from .mandates import ObjectID
from .pricing import Agreement, ContractVersion, Rate, Tier, evaluate_price
from .ramp import RampError
from .ramp_findings import PriceBinding, ServiceMapping, VERSION, _bound_invoice, line_digest
from .ramp_records import _validate_snapshot
from .source_config import EdVerifier, Key, Strict, Subject, _check_file, _protected_path
from .storage import database

Ref = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/#-]{0,127}$")]
Date = Annotated[str, Field(min_length=10, max_length=40)]
Number = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,14})(\.[0-9]{1,6})?$")]
Mode = Literal["SYNTHETIC_NEGOTIATED", "OPERATOR_ATTESTED"]
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_EVIDENCE_BYTES = 32 * 1024 * 1024


class EvidenceError(ValueError):
    """Only messages from this exception may enter an operator or application receipt."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def evaluator_digest():
    directory = Path(__file__).parent
    # Bind behavior, including normalization and transport classes, not just a self-declared version.
    files = ("ramp_terms_store.py","pricing.py","ramp_findings.py","ramp_records.py","contracts.py")
    return fingerprint([VERSION, [(name,sha256((directory/name).read_bytes()).hexdigest()) for name in files]])


class FinanceKey(Strict):
    subject: Subject
    public_key: EdVerifier
    tenant: Ref
    workspace_id: Key
    business_id: ObjectID
    vendor_id: ObjectID
    entity_id: ObjectID
    mode: Mode


class PriceTier(Strict):
    upper: Number | None
    rate: Number


class RateTerms(Strict):
    product: Ref
    unit: Ref
    tiers: list[PriceTier] = Field(min_length=1,max_length=30)


class VersionTerms(Strict):
    version: Ref
    effective_at: Date
    signed_at: Date
    signatories: list[ObjectID] = Field(min_length=2,max_length=16)
    supersedes: Ref | None
    rates: list[RateTerms] = Field(min_length=1,max_length=32)
    excluded_products: list[Ref] = Field(max_length=32)
    contract_sha256: Key
    section: Ref


class Mapping(Strict):
    line_id: ObjectID
    line_digest: Key
    product: Ref
    unit: Ref
    start: Date
    end: Date
    evidence_sha256: Key
    quantity_source: Literal["BILL_INVENTORY","ATTESTED_FULL_PO_LINE"]
    purchase_order_id: ObjectID | None = None
    purchase_order_line_id: ObjectID | None = None
    purchase_order_line_digest: Key | None = None


class TermsPacket(Strict):
    schema_version: Literal["uptime-ramp-price-evidence/1"]
    package_id: ObjectID
    tenant: Ref
    workspace_id: Key
    business_id: ObjectID
    issuer: Subject
    mode: Mode
    issued_at: int
    expires_at: int
    evaluator_sha256: Key
    capture_digest: Key
    bill_id: ObjectID
    bill_digest: Key
    vendor_id: ObjectID
    entity_id: ObjectID
    agreement_id: Ref
    agreement_expires: Date
    versions: list[VersionTerms] = Field(min_length=1,max_length=12)
    mappings: list[Mapping] = Field(min_length=1,max_length=100)
    currency: Literal["USD"]
    economic_basis: Literal["graduated-whole-units/complete-service-slice/net-of-tax/line-half-up-cent"]
    attestation: Literal["reviewed-entire-governing-chain-and-line-evidence-for-exact-bill"]

    @model_validator(mode="after")
    def complete(self):
        if self.entity_id == self.vendor_id:
            raise ValueError("Separate customer entity and vendor are required")
        if not 0 < self.expires_at - self.issued_at <= 86400:
            raise ValueError("Price evidence approval expires within one day")
        for values in ([v.version for v in self.versions],[m.line_id for m in self.mappings]):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate version or mapped bill line")
        return self

    def signing_bytes(self):
        return canonical(["uptime:ramp-price-evidence:ed25519:v1",self.model_dump(mode="json")])

    def digests(self):
        return sorted({v.contract_sha256 for v in self.versions} | {m.evidence_sha256 for m in self.mappings})

    def _binding(self, verified_key):
        versions = []
        for v in self.versions:
            rates = tuple(Rate(r.product,r.unit,tuple(Tier(Decimal(t.upper) if t.upper is not None else None, Decimal(t.rate))
                                                    for t in r.tiers)) for r in v.rates)
            citation = Citation("Reviewed agreement evidence",v.version,v.section,"sha256:"+v.contract_sha256)
            versions.append(ContractVersion(v.version,instant(v.effective_at),instant(v.signed_at),tuple(v.signatories),
                                             v.supersedes,rates,tuple(v.excluded_products),citation))
        agreement = Agreement(self.agreement_id,self.entity_id,self.vendor_id,instant(self.agreement_expires),tuple(versions))
        mappings = tuple(ServiceMapping(m.line_id,m.line_digest,m.purchase_order_id,m.purchase_order_line_id,
                          m.purchase_order_line_digest,m.product,m.unit,instant(m.start),instant(m.end),
                          "sha256:"+m.evidence_sha256,m.evidence_sha256,True,True,m.quantity_source) for m in self.mappings)
        approval = sha256(self.signing_bytes()).hexdigest()
        key_id = sha256(bytes.fromhex(verified_key.public_key)).hexdigest()
        return PriceBinding("bills",self.bill_id,self.capture_digest,"urn:finance-key:"+self.issuer+":"+key_id,agreement,mappings,
                            verified_key.mode,"sha256:"+approval,approval,verified_key.mode=="OPERATOR_ATTESTED")


def private_bytes(path, cap):
    path = _protected_path(path)
    with os.fdopen(os.open(path,os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK),"rb") as handle:
        _check_file(handle.fileno())
        data = handle.read(cap+1)
    if not data or len(data)>cap:
        raise EvidenceError("Private evidence is empty or exceeds its permitted size")
    return data


def verify_evidence(directory, packet):
    total = 0
    try:
        for digest in packet.digests():
            data = private_bytes(Path(directory)/digest, min(MAX_DOCUMENT_BYTES,MAX_EVIDENCE_BYTES-total))
            if sha256(data).hexdigest() != digest:
                raise EvidenceError("Evidence bytes differ from the signed digest")
            total += len(data)
    except (OSError,ValueError):
        raise EvidenceError("Protected contract or line evidence missing, changed or oversized") from None


def _schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS price_finance_key(
               subject TEXT PRIMARY KEY,public_key TEXT NOT NULL UNIQUE,registration TEXT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS price_signed_package(
               id TEXT PRIMARY KEY,tenant TEXT NOT NULL,business_id TEXT NOT NULL,capture TEXT NOT NULL,bill TEXT NOT NULL,
               signed_packet TEXT NOT NULL,signature BLOB NOT NULL,evidence_dir TEXT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0)""")
    db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_price_package_per_bill ON price_signed_package(tenant,business_id,capture,bill)
               WHERE revoked=0""")


def _installation(db, tenant, business):
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"authority_workspace","mandate_workspace","native_installation","native_capture"} <= tables:
        raise EvidenceError("An installed sandbox workspace and completed provider import are required")
    row = db.execute("""SELECT m.realm FROM native_installation i JOIN authority_workspace a ON i.tenant=a.tenant
                        JOIN mandate_workspace m ON m.id=a.id WHERE a.id=1 AND a.mode='sandbox' AND a.rehearsal=0
                        AND i.tenant=? AND i.business_id=?""",(tenant,business)).fetchone()
    if not row:
        raise EvidenceError("Installation, tenant or sandbox business does not match")
    return row[0]


def _latest(db, tenant, business, at):
    realm = _installation(db, tenant, business)
    head = db.execute("""SELECT snapshot FROM native_capture WHERE tenant=? AND status='ready'
                         ORDER BY observed_at DESC,rowid DESC LIMIT 1""",(tenant,)).fetchone()
    if not head:
        raise EvidenceError("Current installed capture unavailable")
    try:
        snap = json.loads(head[0])
        _validate_snapshot(snap)
        observed, completed = instant(snap["observed_at"]), instant(snap["completed_at"])
    except (ValueError,TypeError,KeyError,RampError):
        raise EvidenceError("Current capture failed validation") from None
    if not observed <= completed <= at <= observed+timedelta(hours=24):
        raise EvidenceError("Current installed capture is stale or future-dated")
    return realm,snap


def _bill(snapshot, ident):
    matches = [b for b in snapshot["resources"]["bills"]["records"] if b["kind"]=="bill" and b["id"]==ident]
    if len(matches)!=1:
        raise EvidenceError("No unique installed bill matches the signed identifier")
    return matches[0]


def _verified(db, packet, signature, directory, realm, snapshot, at):
    if (packet.workspace_id != realm or packet.capture_digest != snapshot["checksum"] or
            not instant(snapshot["completed_at"]).timestamp()-1 < packet.issued_at <= at.timestamp() < packet.expires_at or
            packet.evaluator_sha256 != evaluator_digest()):
        raise EvidenceError("Packet capture, clock, installation or evaluator binding is obsolete")
    row = db.execute("SELECT registration FROM price_finance_key WHERE subject=? AND revoked=0",(packet.issuer,)).fetchone()
    if not row:
        raise EvidenceError("No active registered finance verifier")
    key = FinanceKey.model_validate_json(row[0])
    if not independent_key(db,key):
        raise EvidenceError("Finance verifier overlaps another authority purpose")
    if any(getattr(key,f)!=getattr(packet,f) for f in ("workspace_id","tenant","business_id","entity_id","vendor_id","mode")):
        raise EvidenceError("Finance verifier scope does not authorize this package")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key.public_key)).verify(signature,packet.signing_bytes())
    except (InvalidSignature,ValueError):
        raise EvidenceError("Finance signature rejected") from None
    bill = _bill(snapshot,packet.bill_id)
    if packet.bill_digest != fingerprint(bill) or (bill["vendor_id"],bill["entity_id"]) != (packet.vendor_id,packet.entity_id):
        raise EvidenceError("Bill digest or verified native parties differ")
    verify_evidence(directory,packet)
    try:
        bound = packet._binding(key)
        completed = instant(snapshot["completed_at"])
        if instant(bill["issued_at"]) > completed or any(m.end > completed for m in bound.mappings):
            raise EvidenceError("Future bill or incomplete service period")
        if any(v.signed_at > at or v.signed_at.timestamp() > packet.issued_at or
               not {packet.entity_id,packet.vendor_id} <= set(v.signatories) or
               any(t.rate <= 0 for r in v.rates for t in r.tiers) for v in bound.agreement.versions):
            raise EvidenceError("Unattested, future or incomplete contract version")
        invoice = _bound_invoice(snapshot,bill,bound)
        result = evaluate_price(bound.agreement,invoice)
        if result.evaluation.outcome not in {Outcome.ELIGIBLE,Outcome.INELIGIBLE}:
            raise EvidenceError("Terms cannot be applied to the complete scoped bill")
    except (ValueError,KeyError,TypeError,ArithmeticError,OverflowError):
        raise EvidenceError("Line evidence or governing terms cannot support this bill") from None
    return bound


def independent_key(db, key):
    for table in ("mandate_issuer","source_key_history"):
        if db.execute(f"SELECT 1 FROM {table} WHERE subject=? OR public_key=?", (key.subject,key.public_key)).fetchone():
            return False
    return not db.execute("SELECT 1 FROM authority_user WHERE subject=?", (key.subject,)).fetchone()


class RampTermsStore:
    def __init__(self, db_path):
        self.path = Path(db_path)

    def describe(self, tenant, business, bill_id=None):
        with database(self.path) as db:
            db.execute("BEGIN")
            realm,snapshot = _latest(db,tenant,business,datetime.now(UTC))
            summary = dict(tenant=tenant,business_id=business,workspace_id=realm,evaluator_sha256=evaluator_digest(),
                           capture_digest=snapshot["checksum"],observed_at=snapshot["observed_at"])
            if bill_id:
                b = _bill(snapshot,bill_id)
                summary.update(bill_id=bill_id,bill_digest=fingerprint(b),vendor_id=b["vendor_id"],entity_id=b["entity_id"],
                               lines=[{"id":line["id"],"kind":line["kind"],"sha256":line_digest(line)} for line in b["lines"] or []])
                summary["purchase_orders"] = [{"id":p["id"],"lines":[{"id":line["id"],"sha256":line_digest(line)}
                     for line in p["lines"] or []]} for p in snapshot["resources"]["purchase_orders"]["records"] if p["id"]==b["purchase_order_id"]]
            return summary

    def register(self, key):
        key=FinanceKey.model_validate(key)
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if _installation(db,key.tenant,key.business_id) != key.workspace_id:
                raise EvidenceError("Finance key belongs to another installation")
            _schema(db)
            if not independent_key(db,key):
                raise EvidenceError("Finance verifier must be independent from intake and mandate keys")
            try:
                db.execute("INSERT INTO price_finance_key(subject,public_key,registration) VALUES(?,?,?)",
                           (key.subject,key.public_key,key.model_dump_json()))
            except sqlite3.IntegrityError:
                raise EvidenceError("Finance verifier subject or key already registered") from None

    def install(self, packet, signature, directory):
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            at=datetime.now(UTC)
            realm,snapshot = _latest(db,packet.tenant,packet.business_id,at)
            _schema(db)
            _verified(db,packet,signature,directory,realm,snapshot,at)
            args=(packet.package_id,packet.tenant,packet.business_id,packet.capture_digest,packet.bill_id,
                  packet.model_dump_json(),signature,str(directory))
            old = db.execute("SELECT signed_packet,signature,evidence_dir,revoked FROM price_signed_package WHERE id=?",(packet.package_id,)).fetchone()
            if old and tuple(old)==(*args[-3:],0):
                return packet.package_id
            try:
                db.execute("INSERT INTO price_signed_package VALUES(?,?,?,?,?,?,?,?,0)",args)
            except sqlite3.IntegrityError:
                raise EvidenceError("Duplicate package identity or competing active binding. Revoke before replacement.") from None
            return packet.package_id

    def revoke(self, kind, identity, tenant, business):
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            _installation(db,tenant,business)
            _schema(db)
            if kind=="key":
                query="""UPDATE price_finance_key SET revoked=1 WHERE subject=? AND json_extract(registration,'$.tenant')=?
                         AND json_extract(registration,'$.business_id')=?"""
            elif kind=="package":
                query="UPDATE price_signed_package SET revoked=1 WHERE id=? AND tenant=? AND business_id=?"
            else:
                raise EvidenceError("Unsupported revocation target")
            if db.execute(query,(identity,tenant,business)).rowcount != 1:
                raise EvidenceError("Unknown revocation target")

    def resolve(self, tenant, business_id, snapshot):
        rows, omitted = [], []
        try:
            with database(self.path) as db:
                db.execute("BEGIN")
                at=datetime.now(UTC)
                realm,latest=_latest(db,tenant,business_id,at)
                if not isinstance(snapshot,dict) or snapshot.get("checksum")!=latest["checksum"]:
                    raise EvidenceError("Only the latest installed provider capture can carry a price binding")
                _validate_snapshot(snapshot)
                if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='price_signed_package'").fetchone():
                    return (),[]
                previous = db.execute("""SELECT COUNT(*) FROM price_signed_package WHERE tenant=? AND business_id=?
                   AND capture<>? AND revoked=0""", (tenant,business_id,latest["checksum"])).fetchone()[0]
                if previous:
                    omitted.append({"count":previous,"reason":"Earlier capture packages require new finance authorization"})
                active = db.execute("""SELECT id,bill,signed_packet,signature,evidence_dir FROM price_signed_package
                    WHERE tenant=? AND business_id=? AND capture=? AND revoked=0""", (tenant,business_id,latest["checksum"]))
                for row in active:
                    try:
                        packet=TermsPacket.model_validate_json(row["signed_packet"])
                        if (packet.tenant,packet.business_id,packet.package_id,packet.bill_id)!=(tenant,business_id,row["id"],row["bill"]):
                            raise EvidenceError("Stored package scope differs from its signed target")
                        rows.append(_verified(db,packet,row["signature"],row["evidence_dir"],realm,latest,at))
                    except (ValueError,TypeError,OSError) as exc:
                        omitted.append({"package_id":row["id"],"reason":str(exc) if isinstance(exc,EvidenceError) else "Package failed validation"})
        except (ValueError,RampError,sqlite3.Error,OSError) as exc:
            return (),[{"reason":str(exc) if isinstance(exc,EvidenceError) else "Installation or capture unavailable"}]
        return tuple(rows),omitted

    def status(self, tenant, business_id):
        with database(self.path) as db:
            db.execute("BEGIN")
            _,snapshot = _latest(db,tenant,business_id,datetime.now(UTC))
        bindings, omissions = self.resolve(tenant,business_id,snapshot)
        return {"capture_digest":snapshot["checksum"],"bindings":[{"bill_id":b.object_id,"mode":b.terms_mode,
                "authority_digest":b.terms_evidence_digest} for b in bindings],"omissions":omissions}

    def bindings(self, tenant, business_id, snapshot):
        return self.resolve(tenant,business_id,snapshot)[0]
