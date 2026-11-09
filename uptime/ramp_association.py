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
    """Exact source identity: kept byte-for-byte, never slugged, trimmed, normalized or case-folded.

    D03 (decided 2026-11-09, "bounded exact source IDs"): exact values are accepted
    consistently end to end. Internal spaces and any Unicode form are kept as given.
    The bounds match the existing ``claim_identity`` rule (non-empty, no surrounding
    whitespace, no control characters) plus a 512-character limit, so the two layers
    cannot disagree. The shared D03 identity contract replaces this adapter when it lands.
    """
    if (not isinstance(value, str) or not value or value != value.strip() or len(value) > 512
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
