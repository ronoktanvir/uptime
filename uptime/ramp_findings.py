"""Offline, record-bound Ramp findings; neither legal authority nor a write adapter.

Only normalized ramp_records snapshots enter this module. Explicit operator bindings
are trusted server inputs, never browser claims. No provider/model I/O or incident
fixtures are loaded. The V3 pricing engine remains unchanged.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
import re
from typing import Literal

from .contracts import Source, fingerprint
from .evidence import instant
from .pricing import Agreement, Invoice, InvoiceLine, evaluate_price

VERSION = "ramp-findings/1"
OBJECTS = {"bills": "bills", "vendors": "vendors", "transactions": "transactions",
           "purchase_orders": "purchase-orders", "agreements": "vendor-agreements"}
READABLE = {"COMPLETE", "EMPTY", "PARTIAL", "TRUNCATED"}


@dataclass(frozen=True)
class ServiceMapping:
    """Operator-reviewed service scope on this exact bill line.

    evidence_ref/digest identify reviewed service/allocation/tax evidence. In the
    optional PO lane, PO spending dates are not service dates by themselves: the
    operator must establish that interpretation and full PO quantity billing.
    No caller-supplied quantity or amount exists in this interface.
    """
    line_id: str
    line_digest: str
    purchase_order_id: str | None
    purchase_order_line_id: str | None
    purchase_order_line_digest: str | None
    product: str
    unit: str
    start: datetime
    end: datetime
    evidence_ref: str
    evidence_digest: str
    complete_quantity_attested: bool = False
    net_without_tax_attested: bool = False
    quantity_source: Literal["BILL_INVENTORY", "ATTESTED_FULL_PO_LINE"] = "BILL_INVENTORY"


@dataclass(frozen=True)
class PriceBinding:
    object_type: str
    object_id: str
    capture_digest: str
    operator_ref: str
    agreement: Agreement
    mappings: tuple[ServiceMapping, ...]
    # The old pricing types call all customer inputs SYNTHETIC_CUSTOMER. The
    # wrapper separates provenance from arithmetic; no source enum is changed.
    terms_mode: Literal["SYNTHETIC_NEGOTIATED", "OPERATOR_ATTESTED"] = "SYNTHETIC_NEGOTIATED"
    terms_evidence_ref: str = ""
    terms_evidence_digest: str = ""
    signed_terms_attested: bool = False


def _json(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    return value


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _ref(value):
    # References, not private document text or downloadable URLs.
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/#-]{0,255}", value) is not None


def _evidence_ref(value):
    return _ref(value) and value.startswith(("urn:", "sha256:", "fixture:"))


def line_digest(line: dict) -> str:
    """Pin the exact normalized provider line, not an extracted display label."""
    return fingerprint(line)


def binding_digest(binding: PriceBinding) -> str:
    return fingerprint(_json(asdict(binding)))


def _money(value):
    if value is None:
        return None
    amount = Decimal(value["amount"])
    if (not amount.is_finite() or type(value["amount_minor"]) is not int
            or type(value["minor_unit_conversion_rate"]) is not int
            or value["minor_unit_conversion_rate"] <= 0
            or amount != Decimal(value["amount_minor"]) / value["minor_unit_conversion_rate"]):
        raise ValueError("Invalid normalized money")
    return amount


def _link(record, object_type):
    value = record.get("deep_link_url") or record.get("ramp_url")
    if not isinstance(value, str):
        return None
    paths = {"bills": ("/bill-pay/bills/", "/s/bill-pay/bills/"),
             "purchase-orders": ("/s/procurement/purchase-orders/",)}
    # Only accept a provider-supplied path. Never manufacture detail URLs.
    if any(value == "https://demo.ramp.com" + path + record["id"] for path in paths.get(object_type, ())):
        return value
    return None


def _stage(record, object_type):
    if record.get("archived_at") or record.get("deleted_at"):
        return "NEEDS_REVIEW"
    status = record.get("status")
    if object_type == "bills":
        return {"OPEN": "PREPAYMENT_REVIEW", "PAID": "RETROSPECTIVE_REVIEW"}.get(status, "NEEDS_REVIEW")
    if object_type == "draft-bills":
        return "PREPAYMENT_REVIEW"
    if object_type == "transactions":
        # A card transaction is not an unpaid AP bill. Cleared spend is reviewed
        # retrospectively; authorizations cannot be represented as blocked spend.
        return "RETROSPECTIVE_REVIEW" if status == "CLEARED" else "NEEDS_REVIEW"
    return "NEEDS_REVIEW"


def _workflow(case):
    obj, ident = case["provider_object_type"], case["provider_id"]
    supported = obj in {"bills", "draft-bills", "transactions"}
    simulated = case["data_provenance"]["classification"] == "MIXED"
    return {"object_type": obj, "object_id": ident,
            "kind": "NATIVE_COMMENT_REVIEW" if supported else "COMPANION_EVIDENCE_REVIEW",
            "status": "SIMULATION_ONLY" if simulated else "REVIEW_REQUIRED" if supported else "NO_DISCUSSION_ENDPOINT",
            "method": "POST" if supported else None,
            "path": f"/developer/v1/comments/{obj}/{ident}" if supported else None,
            "required_scope": ("transactions:write" if obj == "transactions" else "bills:write") if supported else None,
            "granted": None, "delivery": "NOT_SENT", "approval_trigger_instance_id": None,
            "recommendation": "Review the evidence and current native record before any authorized workflow action.",
            "actual_money_prevented": None, "actual_recovery": None}


def _case(snapshot, resource, row, at, fresh):
    obj = "draft-bills" if resource == "bills" and row["kind"] == "draft" else OBJECTS[resource]
    amount = row.get("amount") or row.get("total_value")
    stage = _stage(row, obj)
    missing = ["Record-specific governing terms and service/line evidence are not bound."]
    if not fresh:
        missing.append("Snapshot is stale or after the evaluation clock; a current provider read is required.")
    case = dict(id=f"ramp-{obj}-{row['id']}", title=f"{obj}: evidence review", vendor=row.get("vendor_id") or row["id"],
                stage=stage, outcome="INSUFFICIENT_EVIDENCE", amount=None,
                currency=amount.get("currency") if amount else row.get("currency"), sources=[Source.RAMP.value],
                provider_object_type=obj, provider_id=row["id"], provider_uri=_link(row, obj),
                native_status=row.get("status"), native_approval_status=row.get("approval_status"), native_amount=dict(amount) if amount else None,
                native_renewal_status=row.get("renewal_status"), payment_timing=stage,
                finding_kind="UNBOUND_RECORD", actual_recovery=None, actual_money_prevented=None, publishable=False,
                data_provenance={"classification": "PROVIDER_OBSERVATION", "capture_digest": snapshot["checksum"],
                                 "record_digest": fingerprint(row), "observed_at": snapshot["observed_at"],
                                 "evaluated_at": at.isoformat(), "freshness": "FRESH" if fresh else "STALE_OR_FUTURE",
                                 "resource_status": snapshot["resources"][resource]["status"],
                                 "resource_complete": snapshot["resources"][resource]["complete"], "evaluator": VERSION},
                trace=["Provider financial state is preserved; spend, PO metadata and agreement metadata alone establish no entitlement."],
                missing=missing, clauses=[], evidence=[{"label": "Captured provider record",
                    "ref": f"sha256:{snapshot['checksum']}:{obj}:{row['id']}", "digest": fingerprint(row),
                    "detail": "Minimized structured observation; original documents are not included.", "sources": [Source.RAMP.value]}],
                actions=[], timeline=[], financials=[], line_findings=[], linked_records=[])
    return case


def _index(snapshot, resource):
    group = snapshot["resources"][resource]
    return {r["id"]: r for r in group["records"]} if group["status"] in READABLE else {}


def _context(case, row, snapshot):
    """Exact native joins only; matching vendor names never establishes a join."""
    vendors, pos, agreements = (_index(snapshot, r) for r in ("vendors", "purchase_orders", "agreements"))
    vendor_id = row["id"] if case["provider_object_type"] == "vendors" else row.get("vendor_id")
    if vendor_id in vendors:
        case["linked_records"].append({"object_type": "vendors", "id": vendor_id, "relationship": "provider_vendor_id"})
    po = pos.get(row.get("purchase_order_id"))
    if po:
        case["linked_records"].append({"object_type": "purchase-orders", "id": po["id"], "relationship": "provider_purchase_order_id"})
        case["trace"].append("Linked PO is procurement context; its quantity and budget do not prove billed service or legally binding terms.")
        if po.get("vendor_id") != vendor_id:
            case["missing"].append("Linked PO vendor identity conflicts with the bill.")
        else:
            po_lines = {line["id"]: line for line in po.get("lines") or []}
            for line in row.get("lines") or []:
                target = po_lines.get(line.get("purchase_order_line_item_id"))
                left, right = line.get("amount"), target.get("amount") if target else None
                if left and right and left["currency"] == right["currency"]:
                    delta = _money(left) - _money(right)
                    case["line_findings"].append({"line_id": line["id"], "purchase_order_line_id": target["id"],
                        "kind": "PO_LINE_AMOUNT_COMPARISON", "billed": left["amount"], "po_amount": right["amount"],
                        "difference": str(delta), "currency": left["currency"], "legal_entitlement": False})
                    if delta > 0:
                        case["finding_kind"] = "PO_VARIANCE"
                        case["trace"].append("A bill line exceeds its linked PO line amount; partial billing, tax and scope require review. No claim amount established.")
    # Vendor equality supplies context, not governing legal scope.
    for agreement in agreements.values():
        if vendor_id and agreement.get("vendor_id") == vendor_id:
            case["linked_records"].append({"object_type": "vendor-agreements", "id": agreement["id"],
                                            "relationship": "same_vendor_context_only"})
    if case["provider_object_type"] == "vendor-agreements":
        case["trace"].append("Agreement metadata and renewal status do not establish signed clauses, service coverage or a remedy.")
        for po_id in row.get("purchase_order_ids") or []:
            if po_id in pos:
                case["linked_records"].append({"object_type": "purchase-orders", "id": po_id,
                                                "relationship": "provider_agreement_purchase_order_id"})
    if case["provider_object_type"] == "purchase-orders":
        for bill_id in row.get("reciprocal_bill_ids") or []:
            case["linked_records"].append({"object_type": "bills", "id": bill_id,
                                            "relationship": "reciprocal_provider_bill_id"})
    approvals = snapshot["resources"]["approvals"]
    for approval in approvals["records"] if approvals["status"] in READABLE else []:
        if approval.get("object_id") == row["id"] and approval.get("object_type") == {
                "bills": "bill", "transactions": "transaction"}.get(case["provider_object_type"]):
            case["evidence"].append({"label": "Native approval observation", "status": approval["status"],
                                     "ref": f"sha256:{snapshot['checksum']}:approvals:{row['id']}",
                                     "digest": fingerprint(approval), "sources": [Source.RAMP.value]})
    if case["provider_object_type"] == "transactions":
        case["trace"].append("Settlement amount can be negative or unavailable. Merchant identity is not inferred to be a bill-pay vendor.")


class BindingError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise BindingError(message)


def _bound_invoice(snapshot, row, binding):
    _require(binding.object_type == "bills" and row["kind"] == "bill", "Only itemized bills support negotiated pricing.")
    _require(binding.object_id == row["id"], "Binding provider record ID mismatch.")
    _require(binding.capture_digest == snapshot["checksum"], "Binding capture digest does not match this observation.")
    _require(_ref(binding.operator_ref), "Explicit operator reference required.")
    _require(binding.terms_mode in {"SYNTHETIC_NEGOTIATED", "OPERATOR_ATTESTED"}, "Unknown terms provenance.")
    _require(_evidence_ref(binding.terms_evidence_ref) and _sha(binding.terms_evidence_digest), "Opaque terms evidence reference and digest required.")
    _require(all(_ref(v.id) and _ref(v.citation.section) and _ref(v.citation.uri)
                 and v.citation.uri.startswith(("urn:", "sha256:", "fixture:"))
                 for v in binding.agreement.versions),
             "Terms citations must use opaque clause references, not private text or document URLs.")
    if binding.terms_mode == "OPERATOR_ATTESTED":
        _require(binding.signed_terms_attested is True, "Operator must attest reviewed signed governing terms.")
    _require(row.get("status") in {"OPEN", "PAID"} and not row.get("archived_at"), "Unsupported or archived native bill state.")
    _require(row.get("vendor_id") == binding.agreement.vendor, "Agreement vendor must equal the actual provider vendor ID.")
    _require(row.get("entity_id") == binding.agreement.customer, "Agreement customer must equal the actual provider entity ID.")
    amount = row.get("amount")
    _require(amount and amount["currency"] == "USD", "USD bill amount required; no currency conversion is inferred.")
    lines = row.get("lines") or []
    mappings = {m.line_id: m for m in binding.mappings}
    _require(lines and len(mappings) == len(binding.mappings) == len(lines)
             and set(mappings) == {line["id"] for line in lines}, "Exact complete bill line mapping required.")
    pos = _index(snapshot, "purchase_orders")
    invoices, used = [], set()
    for line in lines:
        m = mappings[line["id"]]
        _require(m.line_digest == line_digest(line), "Bill line evidence digest mismatch.")
        _require(_evidence_ref(m.evidence_ref) and _sha(m.evidence_digest), "Opaque service evidence reference and digest required.")
        _require(m.complete_quantity_attested is True and m.net_without_tax_attested is True,
                 "Reviewed evidence must establish full quantity billed, service dates and net fees with no tax.")
        _require(_ref(m.product) and _ref(m.unit), "Explicit service SKU and unit required.")
        _require(m.start.tzinfo is not None and m.end.tzinfo is not None and m.start < m.end,
                 "Explicit timezone-aware service interval required.")
        for field, expected in (("sku", m.product), ("unit", m.unit),
                                ("start_date", m.start.date().isoformat()), ("end_date", m.end.date().isoformat())):
            _require(line.get(field) is None or line[field] == expected, "Native service fact conflicts with mapping.")
        if m.quantity_source == "BILL_INVENTORY":
            _require(line.get("kind") == "inventory_line_items", "Native inventory quantity required.")
            _require(all(value is None for value in (m.purchase_order_id, m.purchase_order_line_id,
                                                     m.purchase_order_line_digest)),
                     "Inventory quantity bindings must not assert unused PO evidence.")
            quantity_line = line
        elif m.quantity_source == "ATTESTED_FULL_PO_LINE":
            _require(row.get("purchase_order_id") == m.purchase_order_id, "Bill/PO association mismatch.")
            po = pos.get(m.purchase_order_id)
            _require(po is not None and po.get("vendor_id") == row.get("vendor_id")
                     and po.get("entity_id") == row.get("entity_id"), "Verified PO parties must match the bill.")
            _require(not po.get("archived_at"), "Archived PO requires renewed evidence review.")
            _require(line.get("purchase_order_line_item_id") == m.purchase_order_line_id, "Native bill/PO line association mismatch.")
            quantity_line = next((p for p in po.get("lines") or [] if p["id"] == m.purchase_order_line_id), None)
            _require(quantity_line is not None and line_digest(quantity_line) == m.purchase_order_line_digest,
                     "PO line evidence digest mismatch.")
            key = (m.purchase_order_id, m.purchase_order_line_id)
            _require(key not in used, "A PO quantity cannot be allocated twice.")
            used.add(key)
            _require(quantity_line.get("start_date") == m.start.date().isoformat()
                     and quantity_line.get("end_date") == m.end.date().isoformat(),
                     "Service dates must match structured PO dates with reviewed interval semantics.")
            _require(quantity_line.get("sku") is None or quantity_line["sku"] == m.product,
                     "Native SKU conflicts with service mapping.")
        else:
            raise BindingError("Unsupported quantity evidence source.")
        quantity = quantity_line.get("quantity")
        _require(isinstance(quantity, str), "Authoritative structured quantity required.")
        quantity = Decimal(quantity)
        _require(quantity.is_finite() and 0 < quantity <= Decimal("1e15")
                 and quantity == quantity.to_integral_value(), "Positive whole-unit quantity required.")
        unit_price, source_amount, billed = quantity_line.get("unit_price"), quantity_line.get("amount"), line.get("amount")
        _require(all(v and v["currency"] == "USD" for v in (unit_price, source_amount, billed)),
                 "Structured USD rate and line amounts required.")
        with localcontext() as ctx:
            ctx.prec = 60
            _require(_money(unit_price) > 0 and quantity * _money(unit_price) == _money(source_amount),
                     "Native quantity and positive unit rate must reconcile exactly to line amount.")
        if line.get("quantity") is not None:
            _require(Decimal(line["quantity"]) == quantity, "Native billed quantity conflicts with allocation.")
        invoices.append(InvoiceLine(line["id"], m.product, quantity, m.unit, m.start, m.end,
                                    _money(billed), Decimal("0.00"), f"{m.evidence_ref}:{m.line_id}"))
    _require(sum((line.net for line in invoices), Decimal(0)) == _money(amount), "Mapped native bill amounts must reconcile to bill total.")
    return Invoice(row["id"], row["entity_id"], row["vendor_id"], instant(row["issued_at"]),
                   "paid" if row["status"] == "PAID" else "pending", "USD", _money(amount), tuple(invoices))


def _price(case, snapshot, row, binding, fresh):
    case["data_provenance"]["binding_digest"] = binding_digest(binding)
    synthetic = binding.terms_mode == "SYNTHETIC_NEGOTIATED"
    case["data_provenance"].update(classification="MIXED" if synthetic else "PROVIDER_WITH_OPERATOR_EVIDENCE",
                                    terms_mode=binding.terms_mode)
    case["sources"].append(Source.CUSTOMER.value if synthetic else "OPERATOR_ATTESTED_CUSTOMER")
    case["finding_kind"] = "SYNTHETIC_NEGOTIATED_PRICE" if synthetic else "OPERATOR_PRICE_REVIEW"
    if synthetic:
        case["id"] = f"ramp-synthetic-price-{case['provider_object_type']}-{row['id']}"
    case["evidence"].append({"label": "Explicit terms binding",
                             "ref": binding.terms_evidence_ref if _evidence_ref(binding.terms_evidence_ref) else None,
                             "digest": binding.terms_evidence_digest if _sha(binding.terms_evidence_digest) else None,
                             "sources": case["sources"][1:]})
    try:
        _require(fresh, "Stale or future observations cannot support a current monetary finding.")
        invoice = _bound_invoice(snapshot, row, binding)
        _require(all(v.signed_at is not None and v.signed_at <= instant(case["data_provenance"]["evaluated_at"])
                     for v in binding.agreement.versions), "Terms signature date is missing or after the evaluation clock.")
        _require(all(tier.rate > 0 for version in binding.agreement.versions
                     for rate in version.rates for tier in rate.tiers), "Negotiated price caps must be positive.")
        result = evaluate_price(binding.agreement, invoice)
        case["outcome"] = result.evaluation.outcome.value
        case["amount"] = str(result.overcharge) if result.evaluation.amount else None
        case["stage"] = result.stage
        case["missing"] = list(result.evaluation.missing)
        case["trace"].append("Decimal pricing uses operator-reviewed service allocation and separately supplied terms; PO variance is not contractual entitlement.")
        # These two V3 narrative lines describe fixture custody. The wrapper
        # supplies actual custody above; all arithmetic/date/error traces remain.
        case["trace"].extend(t for t in result.evaluation.trace if t != "Synthetic invoice only; no live Ramp bill bound.")
        case["clauses"] = [{"label": f"Governing clause: {c.section} ({c.version})", "uri": None,
                            "ref": c.uri} for c in result.evaluation.clauses]
        case["line_findings"] = [_json(asdict(line)) for line in result.lines]
        for mapping in binding.mappings:
            case["evidence"].append({"label": "Reviewed service/quantity/tax allocation", "ref": mapping.evidence_ref,
                                     "digest": mapping.evidence_digest, "line_id": mapping.line_id,
                                     "sources": ["OPERATOR_ATTESTED_CUSTOMER"]})
        case["trace"].append("Hypothetical negotiated overlay; no real entitlement or savings." if synthetic else
                             "Provisional calculation based on operator-attested terms; legal enforceability and external action require separate review.")
    except BindingError as exc:
        case.update(outcome="INSUFFICIENT_EVIDENCE", amount=None, stage="NEEDS_REVIEW")
        case["missing"] = [str(exc)]  # Only fixed local reason strings, no provider bodies.
        case["trace"].append("FAIL CLOSED: " + str(exc))
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        # Never echo arbitrary exception content or private source values.
        case.update(outcome="INSUFFICIENT_EVIDENCE", amount=None, stage="NEEDS_REVIEW")
        case["missing"] = ["Binding failed: verify capture/line digests, parties, signed terms, structured SKU/rate/quantity, service dates, complete allocation and tax evidence."]
        case["trace"].append("FAIL CLOSED: explicit binding is incomplete, conflicting or unsupported; no amount established.")


def evaluate_snapshot(snapshot: dict, *, as_of: datetime | None = None,
                      bindings: tuple[PriceBinding, ...] = ()) -> list[dict]:
    """Return a workbench case per observed bill/card/vendor/PO/agreement.

    Integrity validation does not authenticate organization identity; the root
    importer owns trusted capture custody and tenant isolation. No automatic
    binding or fallback to synthetic incidents occurs. Unknown target bindings
    are rejected rather than attached to another record.
    """
    from .ramp_records import _validate_snapshot
    _validate_snapshot(snapshot)
    at = as_of or datetime.now(UTC)
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Timezone-aware evaluation clock required")
    observed, completed = instant(snapshot["observed_at"]), instant(snapshot["completed_at"])
    fresh = observed <= completed <= at and timedelta(0) <= at - observed <= timedelta(hours=24)
    keyed = {}
    for binding in bindings:
        key = (binding.object_type, binding.object_id)
        if key in keyed:
            raise ValueError("Ambiguous multiple bindings for one provider record")
        keyed[key] = binding
    cases, seen = [], set()
    for resource in OBJECTS:
        group = snapshot["resources"][resource]
        if group["status"] not in READABLE:
            continue
        for row in group["records"]:
            case = _case(snapshot, resource, row, at, fresh)
            _context(case, row, snapshot)
            key = (case["provider_object_type"], row["id"])
            seen.add(key)
            if key in keyed:
                _price(case, snapshot, row, keyed[key], fresh)
            case["workflow_recommendation"] = _workflow(case)
            case["finding_digest"] = fingerprint(case)
            cases.append(case)
    if set(keyed) - seen:
        raise ValueError("Binding target is absent from readable provider records")
    return cases
