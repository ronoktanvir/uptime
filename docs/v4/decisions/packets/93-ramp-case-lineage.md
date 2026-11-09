# Decision 93 packet: one Ramp case identity from record to reconciliation

Sanitized design packet. No customer data, credentials, provider captures or evaluation answers.

## Problem

Uptime enforces contract pricing and SLA remedies around Ramp records; Ramp stays the financial system of record. Existing modules read Ramp records, evaluate record-bound findings, verify a person-posted bill note by read-back, journal vendor-credit observations and keep a simulated-award allocation ledger. Nothing joins one case across those stages, so a demo could combine unrelated screens or receipt IDs. Team decisions D02 (which Ramp vendor/bill carries a contract case), D03 (identity representation) and D09 (credit creation/application) are still pending.

## Verified platform facts (official OpenAPI refetched 2026-11-09, same 277 operations as the 2026-11-05 pin)

- Vendor credits: only GET list/detail under `vendors:read`. Default list excludes archived credits; archived credits cannot be applied. `reference_number` carries the vendor memo number.
- Bill `applied_vendor_credits` and credit `applied_bills`/`applied_draft_bills` are both readable.
- Comments: POST/GET on bills, draft-bills, transactions, spend-requests; resource write scope.
- `POST bills/{id}/hold` (bills:write) "blocks all payment rails"; Bill `status_summary` includes `ON_HOLD`.
- `POST approvals/{entity_type}/{entity_id}/add-step` needs `approval_chains:write` and is published as in development. Blank Canvas decisions apply to a configured procurement trigger instance, not a bill.
- Ramp's help article: credits are created only in the UI (from a paid bill or vendor profile); no API/CSV import. "Apply available vendor credits → Split payment" lets a person choose a specific credit and amount; the legacy "Apply vendor credits" toggle applies credits by accounting date, so it cannot target one credit. A person can remove a credit from a bill.

## Preferred implementation

1. `ramp_association.associate(snapshot, ContractScope, NativeAssociation, provider_business_id)` classifies every observed bill, transaction, PO, agreement and vendor for one contract using only reviewed native IDs. Results: APPLICABLE, NOT_APPLICABLE (verified mismatch), UNKNOWN (missing provider fact or unreviewed card transaction), CONFLICT (reviewed allowlist contradicts the provider record). Contract identity values are exact (internal spaces kept; surrounding whitespace/control/non-NFC refused), mirroring the existing claim-identity rule until D03 lands; the contract's vendor name is never compared with Ramp data.
2. `ramp_case_lineage.build_lineage` checks seven stages in order: financial record, applicability, finding, surface, award, credit, application. The first identity disagreement stops the chain; later stages are NOT_EVALUATED; money is null.
3. Money fields are separate (finding estimate, awarded, recorded credit, remaining credit, applied, draft reserved) with no total. `actual_recovery` is always null. Applied value is the sum of credit→bill applications that both sides report with equal amounts on bills that are applicable to the contract. If any pair is unverifiable, applied is null.
4. Across chronological read-backs: a decreased pair amount, a linked credit absent from a later complete list, changed credit identity, or a credit larger than the award (needs the separate attribution store) yields REVIEW_REQUIRED with applied null. Duplicate captures (same checksum) count once.
5. Surfaces are classified: the approved person-posted evidence-gap note is INFORMATIONAL_COMMENT with no payment effect and is accepted only on an INSUFFICIENT_EVIDENCE finding for the same business and bill; a verified note makes the plan NONE (no duplicate). A payment hold counts only if a later read shows `ON_HOLD` after the recorded request time. Approval-step or Blank Canvas surfaces are never credited here (no configured integration). An uncertain Uptime outbox delivery is read back in the same thread, never resent.
6. `prepare_operator_application` only prepares a person-operated UI step with expected post-state. It requires a clean lineage, a VERIFIED_VENDOR_AWARD (never a simulated award), a usable bound credit with enough remaining balance and an unpaid applicable bill without over-application. `confirm_operator_application` classifies a later read: CONFIRMED_BY_READBACK, NOT_YET_OBSERVED, ONE_SIDED_UNCERTAIN, DIFFERENT_AMOUNT_APPLIED, OTHER_CREDIT_APPLIED (legacy toggle chose another credit), APPLICATION_DECREASED, UNVERIFIABLE. It never retries.
7. The real demo bill (no governing agreement) produces: OBSERVED → NO_GOVERNING_AGREEMENT → INSUFFICIENT_EVIDENCE → human note VERIFIED_READBACK (comment re-observed in a fresh read) → no award/credit; the bill's applied credits observed as zero; all case money null.

## Alternatives rejected

- Extend RampCreditSync/AllocationLedger: the ledger accepts only simulated awards and D09 is pending; changing shared settlement tables is a larger reviewed change.
- Link credits to awards by `reference_number` or equal amounts: the records sync does not retain reference text, and equal amounts are not identity. An explicit reviewed CreditBinding is required.
- Treat a decrease as an automatic reversal and show the lower amount: Ramp permits removal, but silently lowering or keeping the higher amount both misstate attributable money.
- Credit a configured approval from a request payload: no configured integration or read-back exists.

## Rollback

Two new modules, one offline CLI and one test file; no existing module, table or test changes. Revert the commit.

## Question

Give one concise critique. Is anything here likely to misstate money, identity or authority? What is the strongest objection and which test would falsify the design?

## Source under review

### uptime/ramp_association.py
```python
"""Explicit applicability of one governing agreement to native Ramp records.

A reviewed ``NativeAssociation`` is the only bridge between a contract identity and
Ramp's native vendor, entity, bill, transaction, purchase-order and agreement IDs.
Nothing here matches by display name, amount, date proximity, merchant text or a
vendor-name label written in the contract. Missing provider facts are ``UNKNOWN``
(missing evidence), which stays distinct from ``NOT_APPLICABLE`` (a verified
mismatch). A provider record that contradicts a reviewed allowlist is ``CONFLICT``.

Offline and read-only: no provider transport, no write, no money. Applicability does
not establish entitlement; the deterministic evaluators still decide that.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
import re
import unicodedata
from uuid import UUID

from .contracts import fingerprint

SCHEMA = "uptime-ramp-association/1"
APPLICABLE, NOT_APPLICABLE, UNKNOWN, CONFLICT = "APPLICABLE", "NOT_APPLICABLE", "UNKNOWN", "CONFLICT"
LINKED_CONTEXT, NOT_LINKED = "LINKED_CONTEXT", "NOT_LINKED"
READABLE = frozenset({"COMPLETE", "EMPTY", "PARTIAL", "TRUNCATED"})
COMPLETE = frozenset({"COMPLETE", "EMPTY"})
_SHA = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/#-]{0,255}")


class AssociationError(ValueError):
    """Fixed reason codes only; never provider bodies or private source values."""


def _fail(code):
    raise AssociationError(code)


def exact_identity(value, code="INVALID_IDENTITY"):
    """Exact source identity: kept byte-for-byte, never slugged, trimmed or case-folded.

    Internal spaces are valid source identity (D03). Surrounding whitespace, control
    characters or non-NFC text are refused rather than silently rewritten, matching
    the existing ``claim_identity`` rule so the two layers cannot disagree.
    """
    if (not isinstance(value, str) or not value or value != value.strip() or len(value) > 512
            or unicodedata.normalize("NFC", value) != value
            or any(unicodedata.category(c).startswith("C") for c in value)):
        _fail(code)
    return value


def native_id(value, code="INVALID_NATIVE_ID"):
    """Canonical nonzero lowercase UUID as Ramp returns it; no reformatting."""
    try:
        if not isinstance(value, str) or str(UUID(value)) != value or UUID(value).int == 0:
            raise ValueError
    except (ValueError, AttributeError):
        _fail(code)
    return value


@dataclass(frozen=True)
class ContractScope:
    """Exact contract identity supplied by the trusted identity layer.

    This is the adapter boundary for the shared identity contract. ``vendor_label``
    is retained only for audit display; it is never compared with Ramp data.
    The effective period is the half-open interval [effective_start, effective_end).
    """
    tenant: str
    contract_id: str
    contract_version: str
    account_id: str
    vendor_label: str
    currency: str
    effective_start: date
    effective_end: date | None = None

    def validated(self):
        for name in ("tenant", "contract_id", "contract_version", "account_id", "vendor_label"):
            exact_identity(getattr(self, name), "INVALID_CONTRACT_IDENTITY")
        if not (isinstance(self.currency, str) and re.fullmatch(r"[A-Z]{3}", self.currency)):
            _fail("INVALID_CURRENCY")
        if type(self.effective_start) is not date or (
                self.effective_end is not None and (type(self.effective_end) is not date
                                                    or self.effective_end <= self.effective_start)):
            _fail("INVALID_EFFECTIVE_PERIOD")
        return self


def scope_from_claim_identity(identity, *, currency, effective_start, effective_end=None):
    """Map the existing claim-identity field names onto ContractScope without rewriting values.

    ``identity`` uses the ``claim_identity`` vocabulary (tenant, vendor, account,
    agreement_id, agreement_version). Service, month and remedy belong to the claim,
    not to agreement applicability, and are ignored here.
    """
    if not isinstance(identity, dict):
        _fail("INVALID_CONTRACT_IDENTITY")
    try:
        return ContractScope(tenant=identity["tenant"], contract_id=identity["agreement_id"],
                             contract_version=identity["agreement_version"], account_id=identity["account"],
                             vendor_label=identity["vendor"], currency=currency,
                             effective_start=effective_start, effective_end=effective_end).validated()
    except KeyError:
        _fail("INCOMPLETE_CONTRACT_IDENTITY")


@dataclass(frozen=True)
class NativeAssociation:
    """Reviewed mapping from one contract to native Ramp identities. Trusted server input only.

    ``bill_ids`` None applies the vendor/entity/currency/effective-date rule to every
    observed bill; a tuple restricts applicability to that reviewed allowlist.
    Card transactions use Ramp's merchant namespace, which is never a bill-pay vendor:
    only explicitly reviewed ``transaction_ids`` can apply.
    """
    tenant: str
    contract_id: str
    contract_version: str
    provider_business_id: str
    vendor_id: str
    entity_ids: tuple[str, ...]
    evidence_ref: str
    evidence_digest: str
    agreement_id: str | None = None
    purchase_order_ids: tuple[str, ...] = ()
    transaction_ids: tuple[str, ...] = ()
    bill_ids: tuple[str, ...] | None = None

    def validated(self, scope: ContractScope):
        if (self.tenant, self.contract_id, self.contract_version) != (
                scope.tenant, scope.contract_id, scope.contract_version):
            _fail("ASSOCIATION_CONTRACT_MISMATCH")
        native_id(self.provider_business_id, "INVALID_BUSINESS")
        native_id(self.vendor_id, "INVALID_VENDOR")
        if not isinstance(self.entity_ids, tuple) or not self.entity_ids:
            _fail("ENTITY_SCOPE_REQUIRED")
        for group in (self.entity_ids, self.purchase_order_ids, self.transaction_ids, self.bill_ids or ()):
            if not isinstance(group, tuple) or len(set(group)) != len(group):
                _fail("INVALID_NATIVE_ID_SET")
            for ident in group:
                native_id(ident)
        if self.bill_ids is not None and not self.bill_ids:
            _fail("EMPTY_BILL_ALLOWLIST")
        if self.agreement_id is not None:
            native_id(self.agreement_id)
        if not (isinstance(self.evidence_ref, str) and _REF.fullmatch(self.evidence_ref)
                and self.evidence_ref.startswith(("urn:", "sha256:", "fixture:"))):
            _fail("OPAQUE_EVIDENCE_REFERENCE_REQUIRED")
        if not (isinstance(self.evidence_digest, str) and _SHA.fullmatch(self.evidence_digest)):
            _fail("EVIDENCE_DIGEST_REQUIRED")
        return self


def association_digest(scope: ContractScope, association: NativeAssociation) -> str:
    def plain(value):
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: plain(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(v) for v in value]
        return value
    return fingerprint({"scope": plain(asdict(scope)), "association": plain(asdict(association))})


def _day(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _within(day, scope):
    return day >= scope.effective_start and (scope.effective_end is None or day < scope.effective_end)


def _bill(row, scope, association):
    reasons = []
    listed = association.bill_ids is None or row["id"] in association.bill_ids
    vendor, entity = row.get("vendor_id"), row.get("entity_id")
    amount = row.get("amount") or {}
    issued = _day(row.get("issued_at"))
    if association.bill_ids is not None and row["id"] in association.bill_ids:
        # A reviewed allowlist entry must agree with the provider record; never override it.
        if vendor is not None and vendor != association.vendor_id:
            return CONFLICT, ["ALLOWLISTED_BILL_VENDOR_CONFLICT"]
        if entity is not None and entity not in association.entity_ids:
            return CONFLICT, ["ALLOWLISTED_BILL_ENTITY_CONFLICT"]
    if vendor is None:
        reasons.append("VENDOR_ID_UNAVAILABLE")
    elif vendor != association.vendor_id:
        return NOT_APPLICABLE, ["DIFFERENT_VENDOR"]
    if entity is None:
        reasons.append("ENTITY_ID_UNAVAILABLE")
    elif entity not in association.entity_ids:
        return NOT_APPLICABLE, ["DIFFERENT_ENTITY"]
    if not listed:
        return NOT_APPLICABLE, ["NOT_IN_REVIEWED_ALLOWLIST"]
    if amount.get("currency") is None:
        reasons.append("CURRENCY_UNAVAILABLE")
    elif amount["currency"] != scope.currency:
        return NOT_APPLICABLE, ["CURRENCY_MISMATCH"]
    if issued is None:
        reasons.append("ISSUE_DATE_UNAVAILABLE")
    elif not _within(issued, scope):
        return NOT_APPLICABLE, ["OUTSIDE_EFFECTIVE_PERIOD"]
    if row.get("archived_at"):
        reasons.append("ARCHIVED_RECORD_REQUIRES_REVIEW")
    return (UNKNOWN, reasons) if reasons else (APPLICABLE, [])


def _transaction(row, association):
    if row["id"] not in association.transaction_ids:
        # Merchant namespace is not a vendor; absence of review is missing evidence.
        return UNKNOWN, ["NO_REVIEWED_TRANSACTION_ASSOCIATION"]
    if row.get("entity_id") is None:
        return UNKNOWN, ["ENTITY_ID_UNAVAILABLE"]
    if row["entity_id"] not in association.entity_ids:
        return CONFLICT, ["ALLOWLISTED_TRANSACTION_ENTITY_CONFLICT"]
    return APPLICABLE, []


def _context(row, listed, vendor_id, code):
    if not listed:
        return NOT_LINKED, []
    if row.get("vendor_id") is None:
        return UNKNOWN, ["VENDOR_ID_UNAVAILABLE"]
    if row["vendor_id"] != vendor_id:
        return CONFLICT, [code]
    return LINKED_CONTEXT, []


def associate(snapshot: dict, scope: ContractScope, association: NativeAssociation, *,
              provider_business_id: str) -> dict:
    """Classify every observed record for this one contract.

    ``provider_business_id`` is the installation-verified business of this capture
    (for example ``ramp_installation.current_business``); it must equal the reviewed
    association. A records snapshot carries no business identity of its own.
    """
    from .ramp_records import _validate_snapshot
    _validate_snapshot(snapshot)
    scope = scope.validated()
    association = association.validated(scope)
    if native_id(provider_business_id, "INVALID_BUSINESS") != association.provider_business_id:
        _fail("BUSINESS_MISMATCH")
    resources = snapshot["resources"]
    records, coverage = [], {}

    def add(kind, row, status, reasons):
        records.append({"object_type": kind, "id": row["id"], "status": status, "reasons": reasons,
                        "record_digest": fingerprint(row)})

    for resource in ("bills", "transactions", "purchase_orders", "agreements", "vendors"):
        group = resources[resource]
        coverage[resource] = {"status": group["status"], "complete": group["complete"]}
        if group["status"] not in READABLE:
            continue
        for row in group["records"]:
            if resource == "bills":
                kind = "draft-bills" if row.get("kind") == "draft" else "bills"
                add(kind, row, *_bill(row, scope, association))
            elif resource == "transactions":
                add("transactions", row, *_transaction(row, association))
            elif resource == "purchase_orders":
                add("purchase-orders", row, *_context(row, row["id"] in association.purchase_order_ids,
                                                      association.vendor_id, "PURCHASE_ORDER_VENDOR_CONFLICT"))
            elif resource == "agreements":
                status, reasons = _context(row, row["id"] == association.agreement_id,
                                           association.vendor_id, "AGREEMENT_VENDOR_CONFLICT")
                if status == LINKED_CONTEXT:
                    reasons = ["NATIVE_AGREEMENT_METADATA_IS_NOT_GOVERNING_TERMS"]
                add("vendor-agreements", row, status, reasons)
            elif row["id"] == association.vendor_id:
                add("vendors", row, LINKED_CONTEXT, [])

    findings = []

    def missing(resource, wanted, kind):
        seen = {r["id"] for r in records if r["object_type"] == kind}
        for ident in wanted:
            if ident not in seen:
                complete = resources[resource]["status"] in COMPLETE
                findings.append({"object_type": kind, "id": ident,
                                 "status": "ABSENT_FROM_COMPLETE_LIST" if complete else "NOT_OBSERVED",
                                 "reasons": ["REVIEWED_ID_NOT_IN_PROVIDER_LIST" if complete
                                             else "PROVIDER_LIST_INCOMPLETE"]})

    missing("bills", association.bill_ids or (), "bills")
    missing("transactions", association.transaction_ids, "transactions")
    missing("purchase_orders", association.purchase_order_ids, "purchase-orders")
    missing("agreements", (association.agreement_id,) if association.agreement_id else (), "vendor-agreements")
    missing("vendors", (association.vendor_id,), "vendors")
    counts = {}
    for row in records:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"schema": SCHEMA, "tenant": scope.tenant, "contract_id": scope.contract_id,
            "contract_version": scope.contract_version, "account_id": scope.account_id,
            "provider_business_id": association.provider_business_id, "vendor_id": association.vendor_id,
            "entity_ids": list(association.entity_ids), "currency": scope.currency,
            "capture_checksum": snapshot["checksum"], "association_digest": association_digest(scope, association),
            "records": sorted(records, key=lambda r: (r["object_type"], r["id"])),
            "reviewed_ids_not_observed": findings, "coverage": coverage, "counts": counts,
            "entitlement_established": False, "writes_attempted": False}


def applicability(result: dict, object_type: str, object_id: str) -> tuple[str, list[str]]:
    """Look up one record's classification; an unobserved record is UNKNOWN, never applicable."""
    for row in result["records"]:
        if row["object_type"] == object_type and row["id"] == object_id:
            return row["status"], list(row["reasons"])
    return UNKNOWN, ["RECORD_NOT_OBSERVED"]
```

### uptime/ramp_case_lineage.py
```python
"""One case's identity from an evaluated Ramp record through finding, surface and reconciliation.

Every stage must name the same tenant, Ramp business, vendor, entity, financial record,
contract and claim. The first disagreement stops the chain with a fixed reason code;
later stages are reported as NOT_EVALUATED rather than guessed. Money stages stay
separate: a finding estimate, an award, a recorded Ramp credit and an applied credit
are never added together, and ``actual_recovery`` is always null.

Applied value comes only from read-back application records that Ramp reports on both
sides (credit ``applied_bills`` and bill ``applied_credits``) with the same amount.
Draft-bill reservations are reported separately and never count as applied.

Offline and deterministic: no provider transport, no writes, no model. Inputs are
records snapshots from ``ramp_records``, a finding from ``ramp_findings``, optional
read-back receipts and reviewed bindings supplied by trusted server code.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import re

from .contracts import fingerprint
from .ramp_association import (APPLICABLE, AssociationError, applicability, exact_identity,
                               native_id)

SCHEMA = "uptime-ramp-case-lineage/1"
HUMAN_NOTE_SCHEMA = "uptime-human-ramp-note-readback/1"
# The team-approved person-posted evidence-gap note (docs/v4/DEMO-PATH-87.md).
EVIDENCE_GAP_NOTE = ("Uptime review: governing agreement or usage evidence is missing for this bill. "
                     "Unable to verify charges against contract terms. Please attach the signed agreement "
                     "or usage records.")
COMPLETE = frozenset({"COMPLETE", "EMPTY"})
READABLE = frozenset({"COMPLETE", "EMPTY", "PARTIAL", "TRUNCATED"})
OBJECT_TYPES = frozenset({"bills", "draft-bills", "transactions"})
AWARD_PROVENANCE = frozenset({"SIMULATED_VENDOR", "VERIFIED_VENDOR_AWARD"})
_SHA = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/#-]{0,255}")

# Supported native surfaces, from the published OpenAPI (SHA-256 29571a47…, fetched
# 2026-11-09). A comment informs a reviewer; only a hold or a configured approval
# changes what Ramp will do with the payment. None of these is executed here.
SURFACES = {
    "INFORMATIONAL_COMMENT": {
        "operation": "POST /developer/v1/comments/{object_type}/{object_id}",
        "scope": "{resource}:write", "payment_effect": "NONE", "approval_effect": "NONE",
        "readback": "GET /developer/v1/comments/{object_type}/{object_id} ({resource}:read)"},
    "PAYMENT_HOLD": {
        "operation": "POST /developer/v1/bills/{bill_id}/hold", "scope": "bills:write",
        "payment_effect": "BLOCKS_ALL_PAYMENT_RAILS", "approval_effect": "NONE",
        "readback": "GET /developer/v1/bills/{bill_id} status_summary == ON_HOLD (bills:read)",
        "release": "POST /developer/v1/bills/{bill_id}/release"},
    "APPROVAL_STEP": {
        "operation": "POST /developer/v1/approvals/{entity_type}/{entity_id}/add-step",
        "scope": "approval_chains:write", "payment_effect": "WAITS_FOR_ADDED_APPROVER",
        "approval_effect": "ADDS_APPROVER", "note": "Published as still in development; scope not granted here."},
    "BLANK_CANVAS_DECISION": {
        "operation": "POST /developer/v1/blank-canvas-approvals/{approval_trigger_instance_id}",
        "scope": "blank_canvas:write", "payment_effect": "WORKFLOW_DECISION",
        "approval_effect": "APPROVES_OR_REJECTS_CONFIGURED_STEP",
        "note": "Applies to a configured procurement trigger instance, not to a bill ID."},
}


class LineageError(ValueError):
    """Fixed reason codes only."""


def _fail(code):
    raise LineageError(code)


@dataclass(frozen=True)
class CaseIdentity:
    """The identity every stage must preserve. Contract fields are all present or all absent.

    Without contract fields the case can only be an evidence-gap case: no governing
    agreement is associated, so no monetary finding, award or credit may attach.
    """
    tenant: str
    provider_business_id: str
    vendor_id: str
    entity_id: str
    object_type: str
    object_id: str
    currency: str
    contract_id: str | None = None
    contract_version: str | None = None
    account_id: str | None = None
    claim_id: str | None = None

    @property
    def has_contract(self):
        return self.contract_id is not None

    def validated(self):
        exact_identity(self.tenant, "INVALID_CASE_IDENTITY")
        for name in ("provider_business_id", "vendor_id", "entity_id", "object_id"):
            native_id(getattr(self, name), "INVALID_CASE_IDENTITY")
        if self.object_type not in OBJECT_TYPES:
            _fail("UNSUPPORTED_FINANCIAL_RECORD")
        if not (isinstance(self.currency, str) and re.fullmatch(r"[A-Z]{3}", self.currency)):
            _fail("INVALID_CURRENCY")
        contract = (self.contract_id, self.contract_version, self.account_id)
        if any(v is None for v in contract) and any(v is not None for v in contract):
            _fail("PARTIAL_CONTRACT_IDENTITY")
        for value in (*contract, self.claim_id):
            if value is not None:
                exact_identity(value, "INVALID_CASE_IDENTITY")
        if self.claim_id is not None and not self.has_contract:
            _fail("CLAIM_WITHOUT_CONTRACT")
        return self


@dataclass(frozen=True)
class AwardRecord:
    """An award already confirmed by the award workflow; this module never creates one."""
    award_id: str
    claim_id: str
    contract_id: str
    contract_version: str
    account_id: str
    vendor_id: str
    currency: str
    amount_minor: int
    minor_unit_conversion_rate: int
    provenance: str
    memo_ref: str
    evidence_digest: str


@dataclass(frozen=True)
class CreditBinding:
    """Reviewed link from one native vendor credit to one award. Never inferred."""
    credit_id: str
    award_id: str
    claim_id: str
    evidence_ref: str
    evidence_digest: str


def _opaque(ref, digest, code):
    if not (isinstance(ref, str) and _REF.fullmatch(ref) and ref.startswith(("urn:", "sha256:", "fixture:"))
            and isinstance(digest, str) and _SHA.fullmatch(digest)):
        _fail(code)


def _instant(value):
    return datetime.fromisoformat(value)


def _record(snapshot, identity):
    resource = "transactions" if identity.object_type == "transactions" else "bills"
    group = snapshot["resources"][resource]
    if group["status"] not in READABLE:
        return None
    for row in group["records"]:
        kind = ("draft-bills" if row.get("kind") == "draft" else "bills") if resource == "bills" else "transactions"
        if kind == identity.object_type and row["id"] == identity.object_id:
            return row
    return None


def _stable_finding_digest(finding):
    stable = {k: v for k, v in finding.items() if k != "finding_digest"}
    stable["data_provenance"] = {k: v for k, v in finding["data_provenance"].items() if k != "evaluated_at"}
    return fingerprint(stable)


class _Chain:
    def __init__(self, identity):
        self.identity, self.stages, self.refusals, self.review = identity, [], [], []
        self.broken = False

    def add(self, stage, status, **facts):
        self.stages.append({"stage": stage, "status": status, **facts})

    def refuse(self, stage, code, **facts):
        self.refusals.append(code)
        self.broken = True
        self.add(stage, "IDENTITY_BROKEN", reason=code, **facts)

    def skip(self, *stages):
        for stage in stages:
            self.add(stage, "NOT_EVALUATED")


def _record_stage(chain, snapshot, business_id):
    identity = chain.identity
    if business_id != identity.provider_business_id:
        return chain.refuse("FINANCIAL_RECORD", "BUSINESS_MISMATCH")
    row = _record(snapshot, identity)
    if row is None:
        return chain.refuse("FINANCIAL_RECORD", "RECORD_NOT_IN_CAPTURE")
    if row.get("vendor_id") != identity.vendor_id and identity.object_type != "transactions":
        return chain.refuse("FINANCIAL_RECORD", "RECORD_VENDOR_MISMATCH")
    if row.get("entity_id") != identity.entity_id:
        return chain.refuse("FINANCIAL_RECORD", "RECORD_ENTITY_MISMATCH")
    amount = row.get("amount")
    if amount is not None and amount.get("currency") != identity.currency:
        return chain.refuse("FINANCIAL_RECORD", "RECORD_CURRENCY_MISMATCH")
    chain.add("FINANCIAL_RECORD", "OBSERVED", capture_checksum=snapshot["checksum"],
              observed_at=snapshot["observed_at"], record_digest=fingerprint(row),
              native_status=row.get("status"), native_status_summary=row.get("status_summary"),
              native_approval_status=row.get("approval_status"), native_amount=amount)
    return row


def _applicability_stage(chain, association, snapshot):
    identity = chain.identity
    if not identity.has_contract:
        if association is not None:
            return chain.refuse("APPLICABILITY", "ASSOCIATION_WITHOUT_CONTRACT_IDENTITY")
        chain.add("APPLICABILITY", "NO_GOVERNING_AGREEMENT", reason="NO_REVIEWED_ASSOCIATION")
        return True
    if association is None:
        return chain.refuse("APPLICABILITY", "REVIEWED_ASSOCIATION_REQUIRED")
    expected = {"tenant": identity.tenant, "contract_id": identity.contract_id,
                "contract_version": identity.contract_version, "account_id": identity.account_id,
                "provider_business_id": identity.provider_business_id, "vendor_id": identity.vendor_id,
                "currency": identity.currency, "capture_checksum": snapshot["checksum"]}
    for key, value in expected.items():
        if association.get(key) != value:
            return chain.refuse("APPLICABILITY", "ASSOCIATION_" + key.upper() + "_MISMATCH")
    if identity.entity_id not in association.get("entity_ids", []):
        return chain.refuse("APPLICABILITY", "ASSOCIATION_ENTITY_MISMATCH")
    status, reasons = applicability(association, identity.object_type, identity.object_id)
    if status != APPLICABLE:
        # NOT_APPLICABLE/CONFLICT: these terms do not govern this record. UNKNOWN: missing
        # evidence. Either way nothing contractual may attach to this record.
        return chain.refuse("APPLICABILITY", "TERMS_" + status + "_FOR_RECORD", reasons=reasons)
    chain.add("APPLICABILITY", APPLICABLE, association_digest=association["association_digest"])
    return True


def _finding_stage(chain, finding, snapshot, row, binding):
    identity = chain.identity
    try:
        provenance = finding["data_provenance"]
        if (finding["provider_object_type"], finding["provider_id"]) != (identity.object_type, identity.object_id):
            return chain.refuse("FINDING", "FINDING_RECORD_MISMATCH")
        if provenance["capture_digest"] != snapshot["checksum"]:
            return chain.refuse("FINDING", "FINDING_CAPTURE_MISMATCH")
        if provenance["record_digest"] != fingerprint(row):
            return chain.refuse("FINDING", "FINDING_RECORD_DIGEST_MISMATCH")
        if finding.get("finding_digest") != _stable_finding_digest(finding):
            return chain.refuse("FINDING", "FINDING_DIGEST_MISMATCH")
        bound = provenance.get("binding_digest")
    except (KeyError, TypeError, AttributeError):
        return chain.refuse("FINDING", "INVALID_FINDING")
    amount = finding.get("amount")
    if bound is not None:
        if not identity.has_contract or binding is None:
            return chain.refuse("FINDING", "PRICE_BINDING_WITHOUT_CASE_CONTRACT")
        from .ramp_findings import binding_digest
        if binding_digest(binding) != bound:
            return chain.refuse("FINDING", "PRICE_BINDING_DIGEST_MISMATCH")
        agreement = binding.agreement
        # Never attach one contract's terms to another vendor, entity or record.
        if agreement.id != identity.contract_id:
            return chain.refuse("FINDING", "PRICE_TERMS_CONTRACT_MISMATCH")
        if (agreement.vendor, agreement.customer) != (identity.vendor_id, identity.entity_id):
            return chain.refuse("FINDING", "PRICE_TERMS_PARTY_MISMATCH")
        if (binding.object_type, binding.object_id) != (identity.object_type, identity.object_id):
            return chain.refuse("FINDING", "PRICE_TERMS_RECORD_MISMATCH")
    elif binding is not None:
        return chain.refuse("FINDING", "UNUSED_PRICE_BINDING")
    elif amount is not None:
        return chain.refuse("FINDING", "MONETARY_FINDING_WITHOUT_BOUND_TERMS")
    chain.add("FINDING", finding.get("outcome"), finding_kind=finding.get("finding_kind"),
              finding_digest=finding["finding_digest"], estimate=amount,
              estimate_currency=finding.get("currency") if amount is not None else None,
              missing=list(finding.get("missing") or []))
    return True


def _surface_stage(chain, surface, finding, snapshots):
    identity = chain.identity
    if surface is None:
        chain.add("SURFACE", "NOT_SURFACED", kind=None, payment_effect="NONE", approval_effect="NONE")
        return
    reobserved = []
    if surface.get("schema") == HUMAN_NOTE_SCHEMA:
        if (surface.get("business_id"), surface.get("bill_id")) != (identity.provider_business_id, identity.object_id):
            return chain.refuse("SURFACE", "NOTE_OBJECT_MISMATCH")
        if identity.object_type != "bills":
            return chain.refuse("SURFACE", "NOTE_OBJECT_MISMATCH")
        if surface.get("status") != "VERIFIED_READBACK" or surface.get("write_attempted") is not False:
            return chain.refuse("SURFACE", "NOTE_NOT_VERIFIED")
        if surface.get("body") != EVIDENCE_GAP_NOTE:
            return chain.refuse("SURFACE", "NOTE_BODY_NOT_APPROVED")
        # The approved note asserts missing evidence; it must not sit on a monetary finding.
        if finding.get("outcome") != "INSUFFICIENT_EVIDENCE" or finding.get("amount") is not None:
            return chain.refuse("SURFACE", "NOTE_CONTRADICTS_FINDING")
        for snapshot in snapshots:
            for comment in snapshot["resources"]["comments"]["records"]:
                if (comment["id"], comment["object_type"], comment["object_id"]) == (
                        surface.get("comment_id"), "bills", identity.object_id):
                    if comment["created_at"] != surface.get("created_at"):
                        return chain.refuse("SURFACE", "NOTE_TIMESTAMP_CHANGED")
                    reobserved.append(snapshot["observed_at"])
        chain.add("SURFACE", "VERIFIED_READBACK", kind="INFORMATIONAL_COMMENT", origin="HUMAN_POSTED",
                  comment_id=surface.get("comment_id"), created_at=surface.get("created_at"),
                  receipt_observed_at=surface.get("observed_at"), reobserved_at=sorted(set(reobserved)),
                  payment_effect="NONE", approval_effect="NONE", api_write_proven=False,
                  authorship_proven=False, duplicate_post_allowed=False)
        return
    kind = surface.get("kind")
    if kind == "PAYMENT_HOLD":
        if (surface.get("object_type"), surface.get("object_id")) != ("bills", identity.object_id) \
                or identity.object_type != "bills":
            return chain.refuse("SURFACE", "HOLD_OBJECT_MISMATCH")
        if surface.get("finding_digest") != finding.get("finding_digest"):
            return chain.refuse("SURFACE", "HOLD_FINDING_MISMATCH")
        try:
            requested = _instant(surface["requested_at"])
            if requested.utcoffset() is None:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return chain.refuse("SURFACE", "HOLD_REQUEST_TIME_REQUIRED")
        # ON_HOLD before the request, or with no hold receipt, is not attributed to this case.
        held = [s["observed_at"] for s in snapshots if (r := _record(s, identity)) is not None
                and r.get("status_summary") == "ON_HOLD" and _instant(s["observed_at"]) >= requested]
        chain.add("SURFACE", "HOLD_VERIFIED_BY_READBACK" if held else "HOLD_NOT_OBSERVED", kind="PAYMENT_HOLD",
                  origin=surface.get("origin"), payment_effect="BLOCKS_ALL_PAYMENT_RAILS" if held else "UNKNOWN",
                  approval_effect="NONE", reobserved_at=held)
        return
    if kind in ("APPROVAL_STEP", "BLANK_CANVAS_DECISION"):
        # No configured approval integration exists in this installation; never credit one.
        chain.add("SURFACE", "INTERVENTION_NOT_VERIFIED", kind=kind, reason="NO_CONFIGURED_APPROVAL_INTEGRATION",
                  payment_effect="UNKNOWN", approval_effect="UNKNOWN")
        return
    if kind == "UPTIME_COMMENT_OUTBOX":
        if (surface.get("object_type"), surface.get("object_id")) != (identity.object_type, identity.object_id):
            return chain.refuse("SURFACE", "OUTBOX_OBJECT_MISMATCH")
        if surface.get("finding_digest") != finding.get("finding_digest"):
            return chain.refuse("SURFACE", "OUTBOX_FINDING_MISMATCH")
        status = surface.get("status")
        remote = surface.get("remote_id")
        seen = [s["observed_at"] for s in snapshots for c in s["resources"]["comments"]["records"]
                if remote is not None and (c["id"], c["object_type"], c["object_id"]) == (remote, identity.object_type, identity.object_id)]
        state = ("VERIFIED_READBACK" if status == "DELIVERED" and seen else
                 "DELIVERED_NOT_REOBSERVED" if status == "DELIVERED" else
                 "OUTCOME_UNCERTAIN" if status in ("DISPATCHING", "UNCERTAIN") else
                 "NOT_SENT" if status in ("PREPARED", "REVIEWED") else None)
        if state is None:
            return chain.refuse("SURFACE", "INVALID_OUTBOX_STATE")
        # An uncertain delivery is reconciled by same-thread read-back, never by resending.
        chain.add("SURFACE", state, kind="INFORMATIONAL_COMMENT", origin="UPTIME_API", comment_id=remote,
                  reobserved_at=seen, payment_effect="NONE", approval_effect="NONE",
                  resend_allowed=False)
        return
    chain.refuse("SURFACE", "UNSUPPORTED_SURFACE")


def _award_stage(chain, award, binding):
    identity = chain.identity
    if award is None and binding is None:
        chain.add("AWARD", "NONE", amount_minor=None)
        return None
    if not identity.has_contract or identity.claim_id is None:
        return chain.refuse("AWARD", "AWARD_WITHOUT_CLAIM_IDENTITY")
    if award is None:
        return chain.refuse("AWARD", "CREDIT_BINDING_WITHOUT_AWARD")
    try:
        exact_identity(award.award_id, "INVALID_AWARD")
        if award.provenance not in AWARD_PROVENANCE:
            _fail("UNSUPPORTED_AWARD_PROVENANCE")
        if (type(award.amount_minor) is not int or award.amount_minor <= 0
                or type(award.minor_unit_conversion_rate) is not int or award.minor_unit_conversion_rate <= 0):
            _fail("INVALID_AWARD_AMOUNT")
        exact_identity(award.memo_ref, "INVALID_AWARD")
        if not _SHA.fullmatch(award.evidence_digest or ""):
            _fail("INVALID_AWARD")
    except (LineageError, AssociationError) as exc:
        return chain.refuse("AWARD", str(exc))
    expected = (identity.claim_id, identity.contract_id, identity.contract_version, identity.account_id,
                identity.vendor_id, identity.currency)
    actual = (award.claim_id, award.contract_id, award.contract_version, award.account_id,
              award.vendor_id, award.currency)
    if actual != expected:
        return chain.refuse("AWARD", "AWARD_SCOPE_MISMATCH")
    chain.add("AWARD", award.provenance, award_id=award.award_id, amount_minor=award.amount_minor,
              minor_unit_conversion_rate=award.minor_unit_conversion_rate, memo_ref=award.memo_ref)
    return award


def _credit_view(snapshot, credit_id):
    group = snapshot["resources"]["credits"]
    for row in group["records"] if group["status"] in READABLE else []:
        if row["id"] == credit_id:
            return "PRESENT", row
    return ("ABSENT" if group["status"] in COMPLETE else "NOT_OBSERVED"), None


def _reciprocal(snapshot, credit, identity, association):
    """Applied amounts verified on both sides; None when any pair cannot be verified."""
    bills = {r["id"]: r for r in snapshot["resources"]["bills"]["records"] if r.get("kind") == "bill"} \
        if snapshot["resources"]["bills"]["status"] in READABLE else {}
    pairs, problems = {}, []
    for link in credit["applied_bills"] or []:
        bill = bills.get(link["bill_id"])
        if bill is None:
            problems.append("APPLIED_BILL_NOT_OBSERVED")
            continue
        if (bill.get("vendor_id"), bill.get("entity_id")) != (identity.vendor_id, identity.entity_id):
            problems.append("APPLIED_BILL_SCOPE_CONFLICT")
            continue
        if association is not None and applicability(association, "bills", bill["id"])[0] != APPLICABLE:
            problems.append("APPLIED_BILL_OUTSIDE_CONTRACT_SCOPE")
            continue
        mirrored = [a for a in bill.get("applied_credits") or [] if a["credit_id"] == credit["id"]]
        if len(mirrored) != 1 or mirrored[0]["amount"]["amount_minor"] != link["amount"]["amount_minor"]:
            problems.append("RECIPROCAL_APPLICATION_CONFLICT")
            continue
        pairs[bill["id"]] = link["amount"]["amount_minor"]
    return pairs, problems


def _credit_stage(chain, binding, award, snapshots, association):
    """Walk chronological read-backs of the bound credit. Returns (money facts, status)."""
    identity = chain.identity
    if binding is None:
        chain.add("CREDIT", "NO_BOUND_CREDIT", credit_id=None)
        chain.add("APPLICATION", "NOT_APPLICABLE", applied_minor=None)
        return
    try:
        native_id(binding.credit_id, "INVALID_CREDIT_BINDING")
        _opaque(binding.evidence_ref, binding.evidence_digest, "INVALID_CREDIT_BINDING")
    except (LineageError, AssociationError) as exc:
        chain.refuse("CREDIT", str(exc))
        return chain.skip("APPLICATION")
    if (binding.award_id, binding.claim_id) != (award.award_id, identity.claim_id):
        chain.refuse("CREDIT", "CREDIT_BINDING_AWARD_MISMATCH")
        return chain.skip("APPLICATION")
    history, last_present, issues = [], None, []
    previous_pairs, credit_facts = {}, None
    for snapshot in snapshots:
        state, row = _credit_view(snapshot, binding.credit_id)
        entry = {"observed_at": snapshot["observed_at"], "capture_checksum": snapshot["checksum"], "state": state}
        if row is not None:
            total, remaining, applied = row["total"], row["remaining"], row["total_applied"]
            facts = (row["vendor_id"], row.get("entity_id"), total["currency"], total["minor_unit_conversion_rate"],
                     total["amount_minor"])
            if row["vendor_id"] != identity.vendor_id:
                chain.refuse("CREDIT", "CREDIT_VENDOR_MISMATCH", credit_id=binding.credit_id)
                return chain.skip("APPLICATION")
            if row.get("entity_id") is not None and row["entity_id"] != identity.entity_id:
                chain.refuse("CREDIT", "CREDIT_ENTITY_MISMATCH", credit_id=binding.credit_id)
                return chain.skip("APPLICATION")
            if {total["currency"], remaining["currency"], applied["currency"]} != {identity.currency}:
                chain.refuse("CREDIT", "CREDIT_CURRENCY_MISMATCH", credit_id=binding.credit_id)
                return chain.skip("APPLICATION")
            if total["minor_unit_conversion_rate"] != award.minor_unit_conversion_rate:
                chain.refuse("CREDIT", "CREDIT_MINOR_UNIT_MISMATCH", credit_id=binding.credit_id)
                return chain.skip("APPLICATION")
            if credit_facts is not None and credit_facts != facts:
                issues.append("CREDIT_IDENTITY_CHANGED")
            credit_facts = facts
            drafts = None if row["applied_drafts"] is None else sum(d["amount"]["amount_minor"] for d in row["applied_drafts"])
            links = None if row["applied_bills"] is None else sum(b["amount"]["amount_minor"] for b in row["applied_bills"])
            if (remaining["amount_minor"] + applied["amount_minor"] != total["amount_minor"]
                    or (links is not None and drafts is not None and links + drafts != applied["amount_minor"])):
                issues.append("CREDIT_TOTAL_CONFLICT")
            pairs, problems = ({}, ["APPLIED_BILLS_UNAVAILABLE"]) if row["applied_bills"] is None else \
                _reciprocal(snapshot, row, identity, association)
            for bill_id, amount in previous_pairs.items():
                if pairs.get(bill_id, 0) < amount and not problems:
                    # Ramp lets a person remove a credit from a bill; that is a real event
                    # needing review, never a silent reduction or a retained higher value.
                    issues.append("APPLICATION_DECREASED")
            if not problems:
                previous_pairs = pairs
            entry.update(total_minor=total["amount_minor"], remaining_minor=remaining["amount_minor"],
                         provider_applied_minor=applied["amount_minor"], draft_reserved_minor=drafts,
                         verified_applications=dict(sorted(pairs.items())), problems=problems,
                         archived=row.get("archived_at") is not None, reference_bill_id=row.get("reference_bill_id"))
            last_present = entry
        elif last_present is not None and state == "ABSENT":
            # The default credit list excludes archived credits; absence is not a reversal.
            issues.append("CREDIT_ABSENT_FROM_LATER_COMPLETE_LIST")
        history.append(entry)
    latest = history[-1] if history else None
    if last_present is None:
        status = "NOT_OBSERVED" if not history or latest["state"] == "NOT_OBSERVED" else "ABSENT_FROM_COMPLETE_LIST"
        chain.add("CREDIT", status, credit_id=binding.credit_id, history=history)
        chain.add("APPLICATION", "UNKNOWN", applied_minor=None, reason="CREDIT_NOT_OBSERVED")
        return
    if last_present["total_minor"] > award.amount_minor:
        issues.append("CREDIT_EXCEEDS_AWARD_REQUIRES_ATTRIBUTION_REVIEW")
    unique = sorted(set(issues))
    credit_status = ("REVIEW_REQUIRED" if unique else "ARCHIVED" if last_present["archived"] else
                     "RECORDED" if last_present["total_minor"] == award.amount_minor else "PARTIALLY_CREDITED")
    chain.add("CREDIT", credit_status, credit_id=binding.credit_id, total_minor=last_present["total_minor"],
              remaining_minor=last_present["remaining_minor"],
              remaining_usable=not last_present["archived"] and not unique,
              reference_bill_relation=("NONE" if last_present["reference_bill_id"] is None else
                                       "EVALUATED_RECORD" if last_present["reference_bill_id"] == identity.object_id
                                       else "OTHER_BILL"),
              issues=unique, history=history)
    if unique:
        chain.review.extend(unique)
        chain.add("APPLICATION", "REVIEW_REQUIRED", applied_minor=None, reasons=unique)
        return
    if latest is not last_present or last_present["problems"]:
        reasons = last_present["problems"] or ["LATEST_READ_DID_NOT_OBSERVE_CREDIT"]
        chain.add("APPLICATION", "UNKNOWN", applied_minor=None, reasons=reasons,
                  draft_reserved_minor=last_present["draft_reserved_minor"])
        return
    applied = sum(last_present["verified_applications"].values())
    status = ("NOT_APPLIED" if applied == 0 else
              "FULLY_APPLIED" if applied == last_present["total_minor"] else "PARTIALLY_APPLIED")
    chain.add("APPLICATION", status, applied_minor=applied,
              applications=last_present["verified_applications"],
              draft_reserved_minor=last_present["draft_reserved_minor"], observed_at=last_present["observed_at"])


def _bill_applied_observed(snapshot, identity):
    row = _record(snapshot, identity)
    if row is None or identity.object_type == "transactions" or row.get("applied_credits") is None:
        return None
    return sum(a["amount"]["amount_minor"] for a in row["applied_credits"])


def build_lineage(identity: CaseIdentity, *, snapshot: dict, provider_business_id: str, finding: dict,
                  association: dict | None = None, price_binding=None, surface: dict | None = None,
                  award: AwardRecord | None = None, credit_binding: CreditBinding | None = None,
                  readbacks: tuple[tuple[str, dict], ...] = ()) -> dict:
    """Assemble and check one case. ``readbacks`` are later (business_id, snapshot) reads.

    ``provider_business_id`` must come from an installation-verified business read for
    ``snapshot``; every read-back carries its own verified business ID.
    """
    from .ramp_records import _validate_snapshot
    identity = identity.validated()
    chain = _Chain(identity)
    stages = ("FINANCIAL_RECORD", "APPLICABILITY", "FINDING", "SURFACE", "AWARD", "CREDIT", "APPLICATION")
    _validate_snapshot(snapshot)
    reads = {snapshot["checksum"]: snapshot}
    for business, later in readbacks:
        _validate_snapshot(later)
        if business != identity.provider_business_id:
            chain.refuse("FINANCIAL_RECORD", "READBACK_BUSINESS_MISMATCH")
            chain.skip(*stages[1:])
            return _result(chain, identity, snapshot, award)
        if later["origin"] != snapshot["origin"]:
            chain.refuse("FINANCIAL_RECORD", "READBACK_ORIGIN_MISMATCH")
            chain.skip(*stages[1:])
            return _result(chain, identity, snapshot, award)
        reads[later["checksum"]] = later  # Duplicate imports of one capture count once.
    ordered = sorted(reads.values(), key=lambda s: (_instant(s["observed_at"]), s["checksum"]))
    if len({s["observed_at"] for s in ordered}) != len(ordered):
        chain.review.append("SAME_TIME_DIFFERENT_CAPTURES")
    row = _record_stage(chain, snapshot, provider_business_id)
    steps = (lambda: _applicability_stage(chain, association, snapshot),
             lambda: _finding_stage(chain, finding, snapshot, row, price_binding),
             lambda: _surface_stage(chain, surface, finding, ordered))
    for index, step in enumerate(steps):
        if chain.broken:
            chain.skip(*stages[index + 1:])
            return _result(chain, identity, snapshot, award)
        step()
    if chain.broken:
        chain.skip(*stages[4:])
        return _result(chain, identity, snapshot, award)
    award = _award_stage(chain, award, credit_binding)
    if chain.broken:
        chain.skip("CREDIT", "APPLICATION")
        return _result(chain, identity, snapshot, None)
    if award is None:
        chain.add("CREDIT", "NO_BOUND_CREDIT", credit_id=None)
        chain.add("APPLICATION", "NOT_APPLICABLE", applied_minor=None, reason="NO_AWARD",
                  record_applied_credits_observed_minor=_bill_applied_observed(ordered[-1], identity))
        return _result(chain, identity, snapshot, None)
    _credit_stage(chain, credit_binding, award, ordered, association)
    return _result(chain, identity, snapshot, award)


def _stage(chain, name):
    return next((s for s in chain.stages if s["stage"] == name), {})


def _result(chain, identity, snapshot, award):
    finding, credit, application = (_stage(chain, n) for n in ("FINDING", "CREDIT", "APPLICATION"))
    surface = _stage(chain, "SURFACE")
    money = {"currency": identity.currency,
             "finding_estimate": finding.get("estimate"),
             "claimed_minor": None,
             "awarded_minor": award.amount_minor if award is not None and not chain.broken else None,
             "award_provenance": award.provenance if award is not None and not chain.broken else None,
             "recorded_credit_minor": credit.get("total_minor") if not chain.broken else None,
             "remaining_credit_minor": credit.get("remaining_minor") if not chain.broken else None,
             "applied_minor": application.get("applied_minor") if not chain.broken else None,
             "draft_reserved_minor": application.get("draft_reserved_minor") if not chain.broken else None,
             "actual_recovery": None,
             "stages_are_not_additive": True}
    if chain.broken:
        status = "IDENTITY_BROKEN"
    elif chain.review:
        status = "REVIEW_REQUIRED"
    elif application.get("status") in ("FULLY_APPLIED", "PARTIALLY_APPLIED", "NOT_APPLIED"):
        status = "CREDIT_" + application["status"]
    elif award is not None:
        status = "AWARDED_" + credit.get("status", "NO_BOUND_CREDIT")
    elif surface.get("status") in ("VERIFIED_READBACK", "HOLD_VERIFIED_BY_READBACK"):
        status = "FINDING_SURFACED"
    else:
        status = "FINDING_ONLY"
    identity_view = {k: v for k, v in asdict(identity).items()}
    body = {"schema": SCHEMA, "status": status, "identity": identity_view,
            "case_key": fingerprint(identity_view), "capture_checksum": snapshot["checksum"],
            "stages": chain.stages, "refusals": chain.refusals, "review_required": sorted(set(chain.review)),
            "money": money, "surfaces_supported": SURFACES, "writes_attempted": False}
    return {**body, "lineage_digest": fingerprint(body)}


def surface_plan(lineage: dict) -> dict:
    """What, if anything, a person may still do to surface this finding. Never executes.

    A verified human evidence-gap note on the same bill is final for that finding:
    posting it again would duplicate the record. The agent-run native posting route is
    disabled and is never offered.
    """
    surface = next((s for s in lineage["stages"] if s["stage"] == "SURFACE"), {})
    if lineage["status"] == "IDENTITY_BROKEN":
        return {"action": "NONE", "reason": "IDENTITY_BROKEN"}
    if surface.get("status") == "VERIFIED_READBACK":
        return {"action": "NONE", "reason": "ALREADY_SURFACED_AND_VERIFIED", "comment_id": surface.get("comment_id")}
    if surface.get("status") in ("OUTCOME_UNCERTAIN", "DELIVERED_NOT_REOBSERVED"):
        return {"action": "READ_BACK_SAME_THREAD", "reason": "UNCERTAIN_DELIVERY_NEVER_RESENT"}
    finding = next((s for s in lineage["stages"] if s["stage"] == "FINDING"), {})
    if finding.get("status") == "INSUFFICIENT_EVIDENCE" and lineage["identity"]["object_type"] == "bills":
        return {"action": "PERSON_POSTS_NOTE_IN_RAMP_UI", "body": EVIDENCE_GAP_NOTE,
                "object_id": lineage["identity"]["object_id"], "kind": "INFORMATIONAL_COMMENT",
                "payment_effect": "NONE", "readback": "scripts/verify_ramp_comment.py"}
    return {"action": "TEAM_DECISION_REQUIRED", "reason": "NO_APPROVED_SURFACE_FOR_THIS_FINDING",
            "options": sorted(SURFACES)}


OPERATOR_SCHEMA = "uptime-ramp-operator-credit-application/1"
# Ramp publishes no vendor-credit create/apply API (OpenAPI 29571a47…). Its help article
# "Vendor credits / Credit memos on Ramp Bill Pay" (HTML SHA-256 6ac21805…, 2026-11-09)
# describes the person-operated route. The legacy "Apply vendor credits" toggle chooses
# credits by accounting date, so it cannot target one awarded credit.
OPERATOR_STEPS = (
    "Open the target bill in Ramp Bill Pay before any payment starts or is batched.",
    "Choose Apply available vendor credits, then Split payment; set Payment method to Vendor credit.",
    "Select exactly the prepared vendor credit ID and enter exactly the prepared amount.",
    "Cover any remaining invoice balance with another payment method and submit.",
    "If only the legacy Apply vendor credits toggle appears, stop: it may apply a different credit.",
    "Record who acted and when, then run a fresh read-only records sync for confirmation.",
)


def _latest_bill(snapshot, bill_id):
    group = snapshot["resources"]["bills"]
    if group["status"] not in READABLE:
        return None
    return next((r for r in group["records"] if r.get("kind") == "bill" and r["id"] == bill_id), None)


def _pair(bill, credit, credit_id, bill_id):
    on_bill = [a["amount"]["amount_minor"] for a in bill.get("applied_credits") or [] if a["credit_id"] == credit_id]
    on_credit = [b["amount"]["amount_minor"] for b in credit["applied_bills"] or [] if b["bill_id"] == bill_id]
    return (on_bill[0] if on_bill else 0), (on_credit[0] if on_credit else 0)


def prepare_operator_application(lineage: dict, *, snapshot: dict, provider_business_id: str,
                                 association: dict | None, target_bill_id: str, amount_minor: int,
                                 prepared_by: str, prepared_at: str) -> dict:
    """Prepare (never perform) a person-operated credit application in Ramp's UI.

    Deterministic gates decide whether the money may move: an unbroken lineage with
    no review flags, a verified (not simulated) award, a usable bound credit with
    enough remaining balance, and an unpaid, applicable bill of the same vendor,
    entity and currency with enough unapplied balance.
    """
    from .ramp_records import _validate_snapshot
    _validate_snapshot(snapshot)
    identity = lineage["identity"]
    stages = {s["stage"]: s for s in lineage["stages"]}
    if lineage["status"] == "IDENTITY_BROKEN" or lineage["review_required"]:
        _fail("LINEAGE_NOT_CLEAN")
    if provider_business_id != identity["provider_business_id"]:
        _fail("BUSINESS_MISMATCH")
    award, credit_stage = stages.get("AWARD", {}), stages.get("CREDIT", {})
    if award.get("status") != "VERIFIED_VENDOR_AWARD":
        # A walkthrough or simulated award must never drive a native financial action.
        _fail("VERIFIED_AWARD_REQUIRED")
    if credit_stage.get("status") not in ("RECORDED", "PARTIALLY_CREDITED") or not credit_stage.get("remaining_usable"):
        _fail("USABLE_BOUND_CREDIT_REQUIRED")
    if type(amount_minor) is not int or amount_minor <= 0:
        _fail("POSITIVE_MINOR_AMOUNT_REQUIRED")
    exact_identity(prepared_by, "PREPARER_IDENTITY_REQUIRED")
    when = _instant(prepared_at)
    if when.utcoffset() is None:
        _fail("AWARE_PREPARATION_TIME_REQUIRED")
    credit_id = credit_stage["credit_id"]
    state, credit = _credit_view(snapshot, credit_id)
    if credit is None or _instant(snapshot["observed_at"]) < _instant(credit_stage["history"][-1]["observed_at"]):
        _fail("CURRENT_CREDIT_READ_REQUIRED")
    if credit.get("archived_at") is not None or credit["remaining"]["amount_minor"] < amount_minor:
        _fail("INSUFFICIENT_USABLE_CREDIT")
    if credit["remaining"]["currency"] != identity["currency"]:
        _fail("CREDIT_CURRENCY_MISMATCH")
    native_id(target_bill_id, "INVALID_TARGET_BILL")
    bill = _latest_bill(snapshot, target_bill_id)
    if bill is None:
        _fail("TARGET_BILL_NOT_OBSERVED")
    if (bill.get("vendor_id"), bill.get("entity_id")) != (identity["vendor_id"], identity["entity_id"]):
        _fail("TARGET_BILL_SCOPE_MISMATCH")
    if association is None or applicability(association, "bills", target_bill_id)[0] != APPLICABLE:
        _fail("TARGET_BILL_NOT_APPLICABLE")
    if bill.get("status") != "OPEN" or bill.get("archived_at") is not None or bill.get("paid_at") is not None:
        _fail("TARGET_BILL_NOT_UNPAID")
    amount = bill.get("amount") or {}
    if amount.get("currency") != identity["currency"] or bill.get("applied_credits") is None:
        _fail("TARGET_BILL_AMOUNT_UNVERIFIED")
    already = sum(a["amount"]["amount_minor"] for a in bill["applied_credits"])
    if already + amount_minor > amount["amount_minor"]:
        _fail("TARGET_BILL_OVER_APPLICATION")
    on_bill, on_credit = _pair(bill, credit, credit_id, target_bill_id)
    if on_bill != on_credit:
        _fail("RECIPROCAL_APPLICATION_CONFLICT")
    body = {"schema": OPERATOR_SCHEMA, "status": "PREPARED_NOT_EXECUTED", "case_key": lineage["case_key"],
            "lineage_digest": lineage["lineage_digest"], "provider_business_id": provider_business_id,
            "credit_id": credit_id, "target_bill_id": target_bill_id, "amount_minor": amount_minor,
            "currency": identity["currency"], "prepared_by": prepared_by, "prepared_at": when.isoformat(),
            "before": {"capture_checksum": snapshot["checksum"], "observed_at": snapshot["observed_at"],
                       "pair_minor": on_bill, "credit_remaining_minor": credit["remaining"]["amount_minor"],
                       "bill_credit_ids": sorted(a["credit_id"] for a in bill["applied_credits"])},
            "expected_after": {"pair_minor": on_bill + amount_minor,
                               "credit_remaining_minor": credit["remaining"]["amount_minor"] - amount_minor},
            "procedure": list(OPERATOR_STEPS), "executor": "PERSON_IN_RAMP_UI", "writes_attempted": False}
    return {**body, "instruction_digest": fingerprint(body)}


def confirm_operator_application(instruction: dict, *, provider_business_id: str, snapshot: dict) -> dict:
    """Classify a later read-only observation against a prepared instruction.

    Never retries or repairs anything. A one-sided or different change is reported
    for a person to investigate; only both-sided exact agreement confirms.
    """
    from .ramp_records import _validate_snapshot
    _validate_snapshot(snapshot)
    body = {k: v for k, v in instruction.items() if k != "instruction_digest"}
    if instruction.get("schema") != OPERATOR_SCHEMA or fingerprint(body) != instruction.get("instruction_digest"):
        _fail("INVALID_INSTRUCTION")
    result = {"instruction_digest": instruction["instruction_digest"], "observed_at": snapshot["observed_at"],
              "capture_checksum": snapshot["checksum"], "retry_allowed": False, "writes_attempted": False}
    if provider_business_id != instruction["provider_business_id"]:
        return {**result, "status": "BUSINESS_MISMATCH"}
    if _instant(snapshot["observed_at"]) <= _instant(instruction["before"]["observed_at"]):
        return {**result, "status": "READ_NOT_AFTER_PREPARATION"}
    credit_id, bill_id = instruction["credit_id"], instruction["target_bill_id"]
    state, credit = _credit_view(snapshot, credit_id)
    bill = _latest_bill(snapshot, bill_id)
    if credit is None or bill is None or bill.get("applied_credits") is None or credit["applied_bills"] is None:
        # A fully used credit can leave the default list; archived credits always do.
        return {**result, "status": "UNVERIFIABLE", "credit_state": state, "bill_observed": bill is not None}
    on_bill, on_credit = _pair(bill, credit, credit_id, bill_id)
    expected, before = instruction["expected_after"]["pair_minor"], instruction["before"]["pair_minor"]
    new_others = sorted({a["credit_id"] for a in bill["applied_credits"]} - {credit_id}
                        - set(instruction["before"]["bill_credit_ids"]))
    facts = {"bill_side_minor": on_bill, "credit_side_minor": on_credit,
             "credit_remaining_minor": credit["remaining"]["amount_minor"], "other_new_credit_ids": new_others}
    if on_bill != on_credit:
        status = "ONE_SIDED_UNCERTAIN"
    elif on_bill == expected and credit["remaining"]["amount_minor"] == instruction["expected_after"]["credit_remaining_minor"]:
        status = "CONFIRMED_BY_READBACK" if not new_others else "CONFIRMED_WITH_OTHER_CREDITS_ON_BILL"
    elif on_bill == before:
        status = "OTHER_CREDIT_APPLIED" if new_others else "NOT_YET_OBSERVED"
    elif on_bill < before:
        status = "APPLICATION_DECREASED"
    else:
        status = "DIFFERENT_AMOUNT_APPLIED"
    return {**result, "status": status, **facts}
```
