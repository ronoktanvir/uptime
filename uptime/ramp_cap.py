"""Exact-object, synthetic gross invoice caps. No transport or financial authority.

Checksums prove internal consistency, not provider authenticity. The trusted local
importer owns capture custody; an operator signature binds a rehearsal selection,
not a customer agreement. Real agreement ingestion is deliberately unsupported.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .contracts import Source
from .ramp import ORIGIN, RampError, uuid_text


VERSION = "uptime-invoice-cap/1"
TERMS_SCHEMA = "uptime-synthetic-invoice-cap/1"
BINDING_SCHEMA = "uptime-invoice-cap-binding/1"
MAX_AGE = timedelta(hours=24)
RESOURCES = {"bills", "vendors", "transactions", "agreements", "purchase_orders",
             "credits", "approvals", "comments"}
TERMS_FIELDS = {"schema", "terms_id", "source", "label", "clause", "basis", "date_basis",
                "cap", "effective_from", "effective_until", "revision", "supersedes",
                "superseded_by", "amendments"}


@dataclass(frozen=True)
class InvoiceCapScope:
    tenant_id: str
    binding: dict
    trusted_operator_keys: Mapping[str, Ed25519PublicKey]


class InvoiceCapRefusal(ValueError):
    """Stable safe code; never echo provider data or private input values."""


def _require(condition, reason):
    if not condition:
        raise InvoiceCapRefusal(reason)


def _canonical(value):
    # Reject float/Decimal/bool-as-money at the monetary boundary as well.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return sha256(_canonical(value)).hexdigest()


def _timestamp(value):
    _require(isinstance(value, str), "INVALID_TIMESTAMP")
    parsed = datetime.fromisoformat(value)
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "INVALID_TIMESTAMP")
    return parsed.astimezone(timezone.utc)


def _date(value):
    _require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
             "INVALID_EFFECTIVE_DATE")
    return date.fromisoformat(value)


def _money(value):
    _require(isinstance(value, dict), "MISSING_GROSS_AMOUNT")
    _require(value.get("currency") == "USD", "UNSUPPORTED_CURRENCY")
    minor, scale, major = (value.get(k) for k in
                           ("amount_minor", "minor_unit_conversion_rate", "amount"))
    _require(type(minor) is int and 0 <= minor <= 10**24 and type(scale) is int and scale == 100,
             "INVALID_MINOR_UNITS")
    # Examine raw text before Decimal conversion: no rounding, exponent, or subcent input.
    _require(isinstance(major, str) and re.fullmatch(r"[0-9]{1,25}(?:\.[0-9]{1,2})?", major),
             "RAW_SUBCENT_OR_INVALID_AMOUNT")
    whole, _, fraction = major.partition(".")
    _require(int(whole) * 100 + int(fraction.ljust(2, "0")) == minor,
             "AMOUNT_METADATA_MISMATCH")
    return minor


def _terms(terms):
    _require(isinstance(terms, dict), "INVALID_TERMS")
    _require(terms.get("source") == Source.CUSTOMER.value, "AUTHENTICATED_CUSTOMER_TERMS_REQUIRED")
    _require(set(terms) == TERMS_FIELDS and terms.get("schema") == TERMS_SCHEMA, "UNSUPPORTED_TERMS_SCHEMA")
    _require(terms["supersedes"] is None and terms["superseded_by"] is None
             and terms["amendments"] == [] and type(terms["revision"]) is int
             and terms["revision"] == 1, "AMENDED_OR_SUPERSEDED_TERMS")
    _require(terms["basis"] == "ENTIRE_INVOICE_INCLUSIVE_TAX_AND_FEES", "AMBIGUOUS_TOTAL_BASIS")
    _require(terms["date_basis"] == "INVOICE_ISSUED_DATE_UTC", "UNSUPPORTED_DATE_BASIS")
    _require(all(isinstance(terms[k], str) and 0 < len(terms[k]) <= 1000
                 for k in ("terms_id", "label", "clause")), "INVALID_TERMS")
    start, end = _date(terms["effective_from"]), _date(terms["effective_until"])
    _require(start < end, "INVALID_EFFECTIVE_DATE")
    return _money(terms["cap"]), start, end


def _snapshot(snapshot, as_of):
    _require(isinstance(snapshot, dict) and snapshot.get("schema") == "uptime-ramp-records/1",
             "INVALID_SNAPSHOT_SCHEMA")
    _require(snapshot.get("origin") == ORIGIN, "UNSUPPORTED_ORIGIN")
    body = {k: v for k, v in snapshot.items() if k not in {"checksum", "snapshot_status"}}
    _require(snapshot.get("checksum") == _digest(body), "SNAPSHOT_CHECKSUM_MISMATCH")
    _require(isinstance(as_of, datetime) and as_of.tzinfo is not None
             and as_of.utcoffset() is not None, "INVALID_AS_OF")
    observed, completed = _timestamp(snapshot["observed_at"]), _timestamp(snapshot["completed_at"])
    _require(observed <= completed <= as_of, "FUTURE_OR_REVERSED_CAPTURE")
    _require(as_of - observed <= MAX_AGE, "STALE_SNAPSHOT")
    resources = snapshot.get("resources")
    _require(isinstance(resources, dict) and set(resources) == RESOURCES, "INVALID_RESOURCES")
    bills = resources["bills"]
    _require(isinstance(bills, dict) and bills.get("status") == "COMPLETE"
             and bills.get("complete") is True and isinstance(bills.get("records"), list)
             and bills.get("issues") == [], "INCOMPLETE_BILL_CAPTURE")
    grant = bills.get("grant")
    _require(isinstance(grant, dict) and grant.get("requested") == ["bills:read"]
             and grant.get("granted") == ["bills:read"]
             and grant.get("scope_reported") is True and grant.get("missing") == []
             and grant.get("unexpected") == [] and grant.get("diagnosis") == "EXACT_GRANT"
             and grant.get("state") == "GRANTED", "EXACT_BILLS_GRANT_REQUIRED")
    seen = set()
    for row in bills["records"]:
        _require(isinstance(row, dict), "INVALID_BILL_ROW")
        ident = uuid_text(row["id"])
        _require(ident not in seen, "DUPLICATE_OR_AMBIGUOUS_BILL")
        seen.add(ident)
    return bills


def _bill(bills, bill_id):
    uuid_text(bill_id)
    matches = [r for r in bills["records"] if r["id"] == bill_id]
    _require(len(matches) == 1, "EXACT_BILL_NOT_FOUND")
    row = matches[0]
    _require(row.get("kind") == "bill", "NATIVE_BILL_REQUIRED")
    _require(row.get("status") == "OPEN" and row.get("approval_status") == "PENDING",
             "BILL_NOT_OPEN_PENDING")
    _require("archived_at" in row and row["archived_at"] is None, "ARCHIVED_OR_UNKNOWN_BILL")
    _require(row.get("sources") == [Source.RAMP.value], "UNVERIFIED_BILL_PROVENANCE")
    uuid_text(row["vendor_id"])
    uuid_text(row["entity_id"])
    _timestamp(row["issued_at"])
    _money(row.get("amount"))
    return row


def _payload(snapshot, row, terms, *, tenant_id, operator_id):
    _require(all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", x)
                 for x in (tenant_id, operator_id)), "INVALID_OPERATOR_SCOPE")
    return {
        "schema": BINDING_SCHEMA, "purpose": "SYNTHETIC_REHEARSAL_ONLY",
        "evaluator_version": VERSION,
        "tenant_id": tenant_id, "operator_id": operator_id,
        "capture_digest": snapshot["checksum"], "bill_id": row["id"],
        "vendor_id": row["vendor_id"], "entity_id": row["entity_id"],
        "currency": row["amount"]["currency"], "issued_at": row["issued_at"],
        "effective_from": terms["effective_from"], "effective_until": terms["effective_until"],
        "expected_content_digest": _digest(row), "terms_digest": _digest(terms),
        "grant_digest": _digest(snapshot["resources"]["bills"]["grant"]),
        "observed_at": snapshot["observed_at"], "completed_at": snapshot["completed_at"],
        "native_status": row["status"], "native_approval_status": row["approval_status"],
        "sources": [Source.RAMP.value, Source.CUSTOMER.value],
    }


def make_synthetic_binding(snapshot, bill_id, *, tenant_id, operator_id, terms=None):
    """Prepare an unsigned local selection; never selects an arbitrary first bill.

    Freshness at decision time is checked by evaluate_invoice_cap. This helper
    validates the capture at its completed_at time, without reading a clock.
    Returns only hashes and exact join metadata, never the raw invoice content.
    """
    if terms is None:
        terms = json.loads((Path(__file__).resolve().parents[1]
                            / "fixtures/ramp/native-cap-terms.json").read_text())
    try:
        _, start, end = _terms(terms)
        bills = _snapshot(snapshot, _timestamp(snapshot["completed_at"]))
        row = _bill(bills, bill_id)
        _require(start <= _timestamp(row["issued_at"]).date() < end, "OUTSIDE_ISSUED_DATE_TERM")
        return _payload(snapshot, row, terms, tenant_id=tenant_id, operator_id=operator_id)
    except InvoiceCapRefusal:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RampError, OverflowError):
        raise InvoiceCapRefusal("MALFORMED_INPUT") from None


def sign_synthetic_binding(payload, private_key):
    """Explicit caller-controlled rehearsal signing; does not confer commercial authority."""
    message = BINDING_SCHEMA.encode() + b"\0" + _canonical(payload)
    # Round trip separates the returned envelope from caller-owned mutable data.
    return {"payload": json.loads(_canonical(payload)), "signature": private_key.sign(message).hex()}


def evaluate_invoice_cap(snapshot, bill_row, terms, *, as_of, scope):
    """Return a workbench case or a safe specific refusal. Never publish or mutate."""
    try:
        # Evaluate a detached JSON view, including the grant inside the checksum.
        snapshot, bill_row, terms = json.loads(_canonical([snapshot, bill_row, terms]))
        cap, start, end = _terms(terms)
        bills = _snapshot(snapshot, as_of)
        _require(isinstance(bill_row, dict), "INVALID_BILL_ROW")
        row = _bill(bills, bill_row["id"])
        _require(_canonical(row) == _canonical(bill_row), "BILL_CONTENT_MISMATCH")
        _require(isinstance(scope, InvoiceCapScope), "OPERATOR_SCOPE_REQUIRED")
        envelope = json.loads(_canonical(scope.binding))
        _require(isinstance(envelope, dict) and set(envelope) == {"payload", "signature"},
                 "SIGNED_BINDING_REQUIRED")
        payload, signature = envelope["payload"], envelope["signature"]
        _require(isinstance(payload, dict) and isinstance(signature, str)
                 and re.fullmatch(r"[a-f0-9]{128}", signature), "INVALID_BINDING_SIGNATURE")
        key = scope.trusted_operator_keys.get(payload.get("operator_id"))
        _require(isinstance(key, Ed25519PublicKey), "UNTRUSTED_OPERATOR")
        try:
            key.verify(bytes.fromhex(signature), BINDING_SCHEMA.encode() + b"\0" + _canonical(payload))
        except InvalidSignature:
            raise InvoiceCapRefusal("INVALID_BINDING_SIGNATURE") from None
        expected = _payload(snapshot, row, terms, tenant_id=scope.tenant_id,
                            operator_id=payload["operator_id"])
        _require(payload == expected, "BINDING_SCOPE_OR_CONTENT_MISMATCH")
        _require(start <= _timestamp(row["issued_at"]).date() < end, "OUTSIDE_ISSUED_DATE_TERM")
        gross = _money(row["amount"])
        delta = max(0, gross - cap)
        money = lambda cents: f"{cents // 100}.{cents % 100:02d}"
        case = {
            "kind": "case", "id": "rehearsal-cap-" + row["id"],
            "title": "Synthetic gross invoice cap rehearsal",
            "vendor": row["vendor_id"], "stage": "SIMULATION_ONLY",
            "outcome": "ELIGIBLE" if delta else "INELIGIBLE",
            "reason": "SYNTHETIC_CAP_EXCESS" if delta else "NO_CAP_EXCESS",
            "amount": money(delta), "currency": "USD",
            "sources": [Source.RAMP.value, Source.CUSTOMER.value],
            "provider_object_type": "bills", "provider_id": row["id"], "provider_uri": None,
            "native_status": row["status"], "native_approval_status": row["approval_status"],
            "native_amount": dict(row["amount"]), "finding_kind": "SYNTHETIC_INVOICE_CAP",
            "data_provenance": "MIXED", "actual_recovery": None,
            "actual_money_prevented": None, "publishable": False,
            "hypothetical_discrepancy": money(delta), "cap_amount": money(cap),
            "evaluator_version": VERSION, "evaluated_at": as_of.astimezone(timezone.utc).isoformat(),
            "trace": ["Constructed synthetic terms over an operator-designated sandbox bill.",
                      "Entire invoice gross total includes all taxes and fees; no units inferred.",
                      "Effective dates use invoice issued date in UTC; end is exclusive, not usage date.",
                      f"Hypothetical USD {money(gross)} gross minus USD {money(cap)} cap: USD {money(delta)} excess.",
                      "No actual prevention, recovery, vendor claim, or external action established."],
            "clauses": [{"document": terms["terms_id"], "version": "1", "section": terms["basis"]}],
            "evidence": {"capture_digest": snapshot["checksum"], "bill_digest": _digest(row),
                         "terms_digest": _digest(terms), "binding_digest": _digest(envelope),
                         "grant_digest": expected["grant_digest"]},
            "missing": [], "actions": [],
            "workflow_recommendation": {"status": "SIMULATION_ONLY", "delivery": "NOT_SENT",
                                        "real_financial_claim_allowed": False},
        }
        case["finding_digest"] = _digest(case)
        return case
    except InvoiceCapRefusal as exc:
        reason = str(exc)
    except (ValueError, TypeError, KeyError, AttributeError, RampError, OverflowError):
        reason = "MALFORMED_INPUT"
    return {"kind": "refusal", "reason": reason, "outcome": "INSUFFICIENT_EVIDENCE",
            "amount": None, "publishable": False, "actual_recovery": None,
            "actual_money_prevented": None, "evaluator_version": VERSION}
