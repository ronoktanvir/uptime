"""Read-only Ramp context for the interface: capture completeness and per-record identity.

Builds the fields published in docs/v4/submission/ramp.md from a validated records
snapshot. Nothing here reads Ramp, writes anything or computes money: amounts are
Ramp's own values, and credit applications come from the both-sided D09 read-back.

Rules this module enforces:
- A partial capture is never presented as a complete account (``account_complete``).
- A Ramp link is shown only when Ramp supplied it for that exact record, or when a
  person observed that exact URL and the API confirmed the same bill. It is never
  constructed from a pattern.
- A contract finding may be shown on a record only when business, vendor, bill and
  agreement are all bound exactly (``finding_attachable``).
- A comment is attributed to a person only when it matches the committed read-back
  receipt of the person-posted note. A local ledger receipt never appears here.
"""
from __future__ import annotations

import json
from pathlib import Path

from .ramp_case_lineage import credit_links
from .ramp_findings import _link

ROOT = Path(__file__).resolve().parents[1]
HUMAN_NOTE = ROOT / "docs/v4/evidence/demo-path-87/human-ramp-note.json"
LIST_KEYS = ("listed", "list_complete", "has_next", "pages_read", "page_size", "max_pages")
WORKLIST = ("bills", "transactions", "purchase_orders")


def _human_note():
    try:
        receipt = json.loads(HUMAN_NOTE.read_text())
    except (OSError, ValueError):
        return None
    required = ("business_id", "bill_id", "comment_id", "created_at")
    if (receipt.get("status") != "VERIFIED_READBACK" or receipt.get("write_attempted") is not False
            or any(not isinstance(receipt.get(k), str) for k in required)):
        return None
    return {k: receipt[k] for k in required}


def _coverage(resource):
    """Aggregate list coverage; per-parent entries (``bill:<id>``) describe children only."""
    lists = [c for key, c in resource["coverage"].items() if ":" not in key and "listed" in c]
    if not lists:
        return {k: None for k in LIST_KEYS} | {"detail_budget_reached": None}
    return {"listed": sum(c["listed"] for c in lists if isinstance(c.get("listed"), int)),
            "list_complete": all(c.get("list_complete") is True for c in lists),
            "has_next": any(c.get("has_next") is True for c in lists),
            "pages_read": sum(c.get("pages_read") or 0 for c in lists),
            "page_size": max((c.get("page_size") or 0 for c in lists), default=None) or None,
            "max_pages": max((c.get("max_pages") or 0 for c in lists), default=None) or None,
            "detail_budget_reached": any(c.get("detail_complete") is False for c in lists)}


def capture_summary(snapshot, *, business_id, custody, freshness):
    resources = []
    for name, resource in snapshot["resources"].items():
        resources.append({"name": name, "status": resource["status"], "complete": resource["complete"],
                          "retained": len(resource["records"]), **_coverage(resource)})
    requested = [r for r in resources if r["name"] in WORKLIST and r["status"] != "NOT_REQUESTED"]
    return {"business_id": business_id, "custody": custody, "observed_at": snapshot["observed_at"],
            "completed_at": snapshot["completed_at"], "freshness": freshness,
            "capture_checksum": snapshot["checksum"], "resources": resources,
            "account_complete": bool(requested) and all(r["complete"] for r in requested),
            "incomplete_lists": sorted(r["name"] for r in requested if not r["complete"])}


def ramp_link(record, object_type, *, association=None):
    """Exact Ramp URL for this record, with its basis; never constructed."""
    provider = _link(record, object_type)
    if provider:
        return {"url": provider, "basis": "PROVIDER_DEEP_LINK"}
    if (association and object_type == "bills" and association.get("status") == "ONE_BILL_READ_VERIFIED"
            and association.get("bill_id") == record.get("id")
            and association.get("browser_url") == "https://demo.ramp.com/bill-pay/bills/list/" + record["id"]):
        return {"url": association["browser_url"], "basis": "OPERATOR_OBSERVED_URL"}
    return None


def _binding(case, row, business_id, agreements):
    """A finding attaches only through a reviewed binding for this exact record.

    The price evaluator already refuses a binding whose agreement vendor or customer
    differs from the native bill. Here the business must also be verified and the
    reviewed binding must be one the workspace holds for this capture.
    """
    provenance = case.get("data_provenance") if isinstance(case.get("data_provenance"), dict) else {}
    bound = provenance.get("binding_digest")
    hypothetical = (provenance.get("terms_mode") == "SYNTHETIC_NEGOTIATED"
                    or any(s in (case.get("sources") or []) for s in ("SYNTHETIC_CUSTOMER", "SIMULATED_VENDOR"))
                    or case.get("finding_kind") == "SYNTHETIC_INVOICE_CAP")
    if hypothetical:
        return {"status": "HYPOTHETICAL", "contract_id": None, "binding_digest": bound}, False
    if not bound:
        return {"status": "NONE", "contract_id": None, "binding_digest": None}, False
    contract = (agreements or {}).get(bound)
    exact = (business_id is not None and row is not None and contract is not None
             and row.get("vendor_id") is not None and row.get("entity_id") is not None)
    return {"status": "BOUND" if exact else "CONFLICT", "contract_id": contract, "binding_digest": bound}, exact


def record_context(snapshot, case, *, business_id, association=None, agreements=None):
    """Ramp context for one worklist row or record detail."""
    object_type, object_id = case.get("provider_object_type"), case.get("provider_id")
    resource = {"bills": "bills", "draft-bills": "bills", "transactions": "transactions",
                "purchase-orders": "purchase_orders"}.get(object_type)
    row = None
    if resource:
        row = next((r for r in snapshot["resources"][resource]["records"] if r["id"] == object_id), None)
    vendors = {v["id"]: v for v in snapshot["resources"]["vendors"]["records"]}
    vendor_id = (row or {}).get("vendor_id")
    vendor_name = (row or {}).get("vendor_name") or (vendors.get(vendor_id) or {}).get("name")
    binding, attachable = _binding(case, row, business_id, agreements)
    discussion, note = [], _human_note()
    for comment in snapshot["resources"]["comments"]["records"]:
        if comment["object_type"] == object_type and comment["object_id"] == object_id:
            person = (note is not None and business_id == note["business_id"] and object_id == note["bill_id"]
                      and comment["id"] == note["comment_id"] and comment["created_at"] == note["created_at"])
            discussion.append({"comment_id": comment["id"], "created_at": comment["created_at"],
                               "attribution": "PERSON_POSTED_VERIFIED_READBACK" if person else "UNATTRIBUTED"})
    credits = None
    if object_type == "bills" and row is not None:
        if business_id is None:
            credits = {"status": "UNKNOWN", "reasons": ["BUSINESS_UNVERIFIED"], "applied_verified_minor": None}
        else:
            # The workspace view adds a local "status" key; the read-back validates the capture itself.
            capture = {k: v for k, v in snapshot.items() if k != "status"}
            links = credit_links(capture, provider_business_id=business_id, bill_id=object_id)
            credits = {k: links[k] for k in ("status", "reasons", "applied_verified_minor", "links")}
    amount = (row or {}).get("amount")
    return {"business_id": business_id, "object_type": object_type, "object_id": object_id,
            "vendor_id": vendor_id, "vendor_name": vendor_name, "entity_id": (row or {}).get("entity_id"),
            "invoice_number": (row or {}).get("invoice_number"),
            "amount": None if amount is None else {"currency": amount["currency"], "amount": amount["amount"]},
            "status": (row or {}).get("status"), "status_summary": (row or {}).get("status_summary"),
            "approval_status": (row or {}).get("approval_status"),
            "issued_at": (row or {}).get("issued_at"), "due_at": (row or {}).get("due_at"),
            "observed_at": snapshot["observed_at"], "capture_checksum": snapshot["checksum"],
            "ramp_link": ramp_link(row, object_type, association=association) if row else None,
            "agreement_binding": binding, "finding_attachable": attachable,
            "discussion": discussion, "credit_links": credits,
            "native_confirmation": "RAMP_READ_ONLY", "actual_recovery": None}
