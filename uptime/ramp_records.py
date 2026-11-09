"""Bounded, sanitized Ramp observations. No contract inference or provider mutations.

The provider is injected; only the operator CLI constructs a live sandbox transport.
The checksum detects local corruption, not authenticity, identity or entitlement.
"""
import hashlib
import hmac
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .contracts import Source
from .ramp import (ORIGIN, NATIVE_READ_SCOPES, RampError, RampHTTPError, _bounds,
                   _capability, _enum, _optional_id, _quantity, _timestamp, money,
                   now, uuid_text)

SCHEMA = "uptime-ramp-records/1"
RESOURCE_SCOPES = {
    "bills": "bills:read", "vendors": "vendors:read", "transactions": "transactions:read",
    "agreements": "vendors:read", "purchase_orders": "purchase_orders:read",
    "credits": "vendors:read", "approvals": "approvals:read", "comments": "bills:read",
}
STATUSES = {"COMPLETE", "EMPTY", "PARTIAL", "TRUNCATED", "UNAVAILABLE", "FORBIDDEN", "NOT_REQUESTED"}
MAX_SNAPSHOT_BYTES = 32_000_000
SOURCE = [Source.RAMP.value]
_ERRORS = (RampError, ValueError, TypeError, KeyError, AttributeError, OverflowError)


def native_ui_url(value, ident, kind):
    """Retain an actual provider URL only; never construct a link from an ID."""
    if not isinstance(value, str) or len(value) > 250:
        return None
    # Literal comparison also excludes ports, credentials, encoding tricks and empty ?/#.
    prefixes = {"bill": ("/bill-pay/bills/", "/s/bill-pay/bills/"),
                "purchase_order": ("/s/procurement/purchase-orders/",)}
    return value if any(value == "https://demo.ramp.com" + p + uuid_text(ident)
                        for p in prefixes[kind]) else None


def _money(value):
    if value is None:
        return None
    if isinstance(value, dict) and value.get("minor_unit_conversion_rate") is None:
        if (type(value.get("amount")) is not int or abs(value["amount"]) > 10**24
                or not isinstance(value.get("currency_code"), str)
                or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,7}", value["currency_code"])):
            raise RampError("Invalid unscaled provider money")
        return {"amount": None, "currency": value["currency_code"], "amount_minor": value["amount"],
                "minor_unit_conversion_rate": None}
    result = money(value)
    return {**result, "amount_minor": value["amount"],
            "minor_unit_conversion_rate": value["minor_unit_conversion_rate"]}


def _date(value):
    if value is None:
        return None
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise RampError("Invalid material date")
    return value


def _bool(value):
    if value is not None and type(value) is not bool:
        raise RampError("Invalid provider boolean")
    return value


def _ids(value):
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 10000:
        raise RampError("Invalid associations")
    ids = [uuid_text(v) for v in value]
    if len(ids) != len(set(ids)):
        raise RampError("Duplicate associations")
    return ids


def _base(row):
    return {"id": uuid_text(row["id"]), "sources": SOURCE.copy()}


def _fields(row, keys, converter):
    return {k: converter(row.get(k)) for k in keys.split()}


def _links(row, key, source_key, target_key):
    if row.get(key) is None:
        return None
    values = row[key]
    if not isinstance(values, list) or len(values) > 10000:
        raise RampError("Invalid monetary associations")
    result = [{target_key: uuid_text(v[source_key]), "amount": _money(v.get("amount"))} for v in values]
    if len({v[target_key] for v in result}) != len(result):
        raise RampError("Duplicate monetary associations")
    return result


def _lines(row, groups):
    result, seen = [], set()
    for key in groups:
        if row.get(key) is None:
            continue
        if not isinstance(row[key], list) or len(row[key]) > 10000:
            raise RampError("Invalid native lines")
        for line in row[key]:
            ident = _optional_id(line.get("id"))
            if ident is not None:
                if ident in seen:
                    raise RampError("Duplicate native line")
                seen.add(ident)
            quantity = _quantity(line.get("unit_quantity") if key == "credit_inventory" else line.get("quantity"))
            amount, rate = _money(line.get("amount")), _money(line.get("unit_price"))
            check = "UNAVAILABLE"
            if (quantity is not None and amount is not None and rate is not None
                    and amount["amount"] is not None and rate["amount"] is not None):
                with localcontext() as ctx:
                    ctx.prec = 80
                    check = "MATCH" if (amount["currency"] == rate["currency"] and
                        Decimal(quantity) * Decimal(rate["amount"]) == Decimal(amount["amount"])) else "MISMATCH"
            result.append({"id": ident, "kind": key, "amount": amount, "unit_price": rate,
                           "quantity": quantity, "quantity_rate_check": check,
                           "unit": None, "service_date": None, "sku": None,
                           "purchase_order_line_item_id": _optional_id(line.get("purchase_order_line_item_id")),
                           "item_receipt_line_item_ids": _ids(line.get("item_receipt_line_item_ids")),
                           **_fields(line, "start_date end_date", _date)})
    return result


DISPLAY_MAX = 160


def _display(value):
    """Exact display text for the worklist (vendor name, invoice number), or None.

    Kept byte-for-byte when present: never trimmed, normalized or case-folded. Values
    with control characters, URL schemes or more than DISPLAY_MAX characters are
    not retained. Display text identifies nothing: native UUIDs remain the only
    identities, and these fields are never compared or sent to a model.
    """
    if (not isinstance(value, str) or not value or len(value) > DISPLAY_MAX or "://" in value
            or any(unicodedata.category(c).startswith("C") for c in value)):
        return None
    return value


def sanitize_bill(row, kind="bill"):
    status = _enum(row.get("status"))
    if status not in ({"OPEN", "PAID"} if kind == "bill" else {"DRAFT"}):
        raise RampError("Invalid native bill state")
    vendor = _optional_id((row.get("vendor") or {}).get("id"))
    entity = _optional_id(row.get("entity_id"))
    if kind == "bill" and (vendor is None or entity is None):
        raise RampError("Missing native bill identity")
    return {**_base(row), "kind": kind, "vendor_id": vendor, "entity_id": entity,
            "account_id": None, "account_identity": "UNAVAILABLE_IN_BILL_API", "status": status,
            **_fields(row, "approval_status status_summary sync_status", _enum),
            **_fields(row, "created_at issued_at due_at paid_at archived_at accounting_date posting_date", _timestamp),
            **_fields(row, "draft_bill_id purchase_order_id", _optional_id),
            "item_receipt_ids": _ids(row.get("item_receipt_ids")),
            "amount": _money(row.get("amount")), "lines": _lines(row, ("line_items", "inventory_line_items")),
            "applied_credits": _links(row, "applied_vendor_credits", "id", "credit_id"),
            "deep_link_url": native_ui_url(row.get("deep_link_url"), row["id"], "bill") if kind == "bill" else None,
            "vendor_name": _display((row.get("vendor") or {}).get("name")),
            "invoice_number": _display(row.get("invoice_number"))}


def sanitize_vendor(row):
    return {**_base(row), **_fields(row, "parent_vendor_id default_entity_id merchant_id", _optional_id),
            "status": _enum(row.get("approval_status")), "is_active": _bool(row.get("is_active")),
            **_fields(row, "created_at updated_at", _timestamp), "name": _display(row.get("name"))}


def _signed_money(value, scale):
    if value is None:
        return None
    # SignedAmount has no scale. Only the explicitly reported entity scale applies.
    return _money({"amount": value["value"], "currency_code": value["currency"],
                   "minor_unit_conversion_rate": scale})


def sanitize_transaction(row):
    return {**_base(row), "vendor_id": None,
            **_fields(row, "entity_id merchant_id card_id spend_program_id original_transaction_id", _optional_id),
            "amount": _signed_money(row.get("entity_amount"), row.get("minor_unit_conversion_rate")),
            "merchant_amount": _signed_money(row.get("merchant_amount"), None),
            "original_amount": _money(row.get("original_transaction_amount")),
            "status": _enum(row.get("state")), "sync_status": _enum(row.get("sync_status")),
            "all_requirements_met_and_approved": _bool(row.get("all_requirements_met_and_approved")),
            **_fields(row, "user_transaction_time settlement_date accounting_date updated_at", _timestamp),
            "lines": _lines(row, ("line_items",))}


def sanitize_agreement(row):
    vendor = _optional_id((row.get("payee") or {}).get("uuid"))
    if vendor is None:
        raise RampError("Missing agreement vendor identity")
    currency = row.get("currency")
    if currency is not None and (not isinstance(currency, str) or not re.fullmatch("[A-Z]{3}", currency)):
        raise RampError("Invalid agreement currency")
    return {**_base(row), "vendor_id": vendor, "currency": currency,
            "amount": _money(row.get("total_value")), "renewal_status": _enum(row.get("renewal_status")),
            **_fields(row, "is_active auto_renewal", _bool),
            **_fields(row, "created_at updated_at archived_at deleted_at", _timestamp),
            **_fields(row, "start_date end_date last_date_to_terminate", _date),
            "purchase_order_ids": None if row.get("purchase_orders") is None else _ids([p["id"] for p in row["purchase_orders"]]),
            "lines": None}  # line_items is an untyped object array; no guessed contract terms.


def sanitize_purchase_order(row):
    return {**_base(row), **_fields(row, "vendor_id entity_id spend_program_id spend_request_id", _optional_id),
            "status": _enum(row.get("billing_status")),
            **_fields(row, "receipt_status creation_source", _enum),
            **_fields(row, "amount spend_total_amount", _money),
            **_fields(row, "created_at archived_at promise_date spend_start_date spend_end_date", _timestamp),
            **_fields(row, "bill_ids transaction_ids item_receipt_ids", _ids),
            "three_way_match_enabled": _bool(row.get("three_way_match_enabled")),
            "lines": _lines(row, ("line_items",)), "reciprocal_bill_ids": [], "discovery": [],
            "ramp_url": native_ui_url(row.get("ramp_url"), row["id"], "purchase_order")}


def sanitize_credit(row):
    line_row = {"expense_line_items": row.get("expense_line_items"), "credit_inventory": row.get("inventory_line_items")}
    return {**_base(row), "vendor_id": uuid_text(row["vendor_id"]),
            **_fields(row, "entity_id reference_bill_id", _optional_id),
            "accounting_date": _date(row.get("accounting_date")),
            **_fields(row, "created_at archived_at", _timestamp),
            "total": _money(row.get("total_amount")), "remaining": _money(row.get("remaining_amount")),
            "total_applied": _money(row.get("total_applied_amount")),
            "applied_bills": _links(row, "applied_bills", "bill_id", "bill_id"),
            "applied_drafts": _links(row, "applied_draft_bills", "bill_id", "bill_id"),
            "lines": _lines(line_row, ("expense_line_items", "credit_inventory"))}


def sanitize_approval(row, object_type, object_id):
    if row.get("entity_type") != object_type or uuid_text(row["entity_id"]) != object_id:
        raise RampError("Approval parent mismatch")
    if row.get("status") not in {"APPROVED", "INITIALIZED", "PENDING", "REJECTED", "TERMINATED"}:
        raise RampError("Invalid approval status")
    history = row.get("approval_history")
    if not isinstance(history, list) or len(history) > 10000 or not isinstance(row.get("next_approvers"), list):
        raise RampError("Invalid approval shape")
    # step_status is free text in OpenAPI. Retain known state tokens only, never refuse a
    # valid parent because a step has a new/nonapplicable value. No user identities needed.
    known = {"APPROVED", "INITIALIZED", "PENDING", "REJECTED", "TERMINATED", "SKIPPED", "NOT_APPLICABLE"}
    return {"id": object_id, "id_kind": "parent_resource", "object_id": object_id,
            "object_type": object_type, "entity_id": object_id, "entity_type": object_type,
            "status": row["status"], "sources": SOURCE.copy(),
            "approval_history": [{"action_at": _timestamp(h.get("action_at")),
                                   "step_status": h.get("step_status") if h.get("step_status") in known else None} for h in history],
            "next_approver_count": len(row["next_approvers"])}


def sanitize_comment(row, object_type, object_id):
    # Comment IDs are documented strings, not necessarily UUIDs.
    ident = row["id"]
    if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", ident):
        raise RampError("Invalid native comment ID")
    return {"id": ident, "object_id": uuid_text(object_id), "object_type": object_type,
            "created_at": _timestamp(row.get("created_at")), "sources": SOURCE.copy()}


def _issue(exc, **context):
    result = {"code": "INVALID_OR_UNAVAILABLE_RESPONSE", **context}
    if isinstance(exc, RampHTTPError):
        result.update(code="HTTP_ERROR", http_status=exc.status)
    return result


def _grant(provider, scope):
    try:
        token = provider.token({scope})
        if token.expected != frozenset({scope}):
            raise RampError("Token request metadata mismatch")
        grant = _capability(token)
        return (token if token.exact else None), grant
    except _ERRORS as exc:
        return None, {"requested": [scope], "granted": [], "state": "UNAVAILABLE", **_issue(exc)}


def scope_probe(provider):
    return {"schema": "uptime-ramp-records-scopes/1", "origin": ORIGIN, "observed_at": now(),
            "requests": [_grant(provider, scope)[1] for scope in sorted(NATIVE_READ_SCOPES)],
            "records_read": False, "writes_attempted": False,
            "app_allowed_scopes": "NOT_OBSERVABLE_FROM_TOKEN_RESPONSE"}


def _resource(grant):
    return {"status": "NOT_REQUESTED", "records": [], "complete": False,
            "grant": grant, "issues": [], "coverage": {}}


def _cursor(value, path, initial):
    if not isinstance(value, str) or len(value) > 4096 or any(c in value for c in '\r\n\t'):
        raise RampError("Invalid next page")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc != "demo-api.ramp.com" or
            parsed.path != "/developer/v1/" + path or "#" in value):
        raise RampError("Unsafe next page")
    pairs = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    if set(pairs) - (set(initial) | {"start"}) or "start" not in pairs or len(pairs["start"]) != 1:
        raise RampError("Unexpected next-page filters")
    for key, val in initial.items():
        expected = [str(v) for v in val] if isinstance(val, list) else [str(val)]
        if key in pairs and pairs[key] != expected:
            raise RampError("Changed next-page filters")
    value = pairs["start"][0]
    if not re.fullmatch(r"[A-Za-z0-9_=-]{1,512}", value):
        raise RampError("Invalid cursor")
    return value


def _pages(provider, token, path, page_size, max_pages, *, query=None, method="GET"):
    initial = {"page_size": page_size, **(query or {})}
    params, rows, cursors = initial.copy(), [], set()
    coverage = {"pages_read": 0, "listed": 0, "list_complete": False, "has_next": None,
                "page_size": page_size, "max_pages": max_pages, "issues": []}
    for _ in range(max_pages):
        try:
            if method == "POST":
                response = provider.request(token, method, path, data=params)
            else:
                response = provider.request(token, method, path, query=params)
            if not isinstance(response, dict) or not isinstance(response.get("data"), list):
                raise RampError("Invalid page")
            batch = response["data"]
            if len(batch) > page_size or any(not isinstance(r, dict) for r in batch):
                raise RampError("Invalid page bound")
            page = response.get("page")
            if not isinstance(page, dict) or "next" not in page:
                raise RampError("Missing page metadata")
            rows.extend(batch)
            coverage.update(pages_read=coverage["pages_read"] + 1, listed=len(rows), has_next=page["next"] is not None)
            if page["next"] is None:
                coverage["list_complete"] = True
                break
            cursor = _cursor(page["next"], path, initial)
            if cursor in cursors:
                raise RampError("Repeated cursor")
            cursors.add(cursor)
            params = {**initial, "start": cursor}
        except _ERRORS as exc:
            coverage["issues"].append(_issue(exc))
            break
    return rows, coverage


def _finish(resource, *, attempted=True):
    covs = [v for v in resource["coverage"].values() if isinstance(v, dict) and "list_complete" in v]
    if resource["grant"].get("state") != "GRANTED":
        resource["status"] = "FORBIDDEN" if resource["grant"].get("http_status") == 403 else "UNAVAILABLE"
        return
    if not attempted:
        return
    complete = bool(covs) and all(c["list_complete"] and c.get("detail_complete", True) for c in covs)
    resource["complete"] = complete and not resource["issues"]
    if resource["issues"]:
        resource["status"] = "PARTIAL" if resource["records"] else (
            "FORBIDDEN" if any(i.get("http_status") == 403 for i in resource["issues"]) else "UNAVAILABLE")
    elif not resource["complete"]:
        resource["status"] = "TRUNCATED"
    else:
        resource["status"] = "COMPLETE" if resource["records"] else "EMPTY"


def _details(provider, token, resource, path, rows, sanitizer, budget, coverage):
    unique, seen = [], set()
    valid_ids = True
    for row in rows:
        try:
            ident = uuid_text(row["id"])
            if ident in seen:
                raise RampError("Duplicate list ID")
            seen.add(ident)
            unique.append(ident)
        except _ERRORS as exc:
            valid_ids = False
            issue = _issue(exc)
            coverage.setdefault("issues", []).append(issue)
            resource["issues"].append(issue)
    coverage.update(details_attempted=0, details_read=0, detail_complete=valid_ids and len(unique) <= budget)
    for ident in unique[:budget]:
        coverage["details_attempted"] += 1
        try:
            raw = provider.request(token, "GET", path + "/" + ident)
            record = sanitizer(raw)
            if record["id"] != ident:
                raise RampError("Detail identity mismatch")
            resource["records"].append(record)
            coverage["details_read"] += 1
        except _ERRORS as exc:
            coverage["detail_complete"] = False
            issue = _issue(exc, object_id=ident)
            coverage.setdefault("issues", []).append(issue)
            resource["issues"].append(issue)
    return coverage["details_attempted"]


def _vendor_capture(provider, token, resource, bills, page_size, max_pages, budget):
    """Prioritize exact captured bill references within one vendor detail budget.

    Linked coverage describes captured parents only, never the business inventory.
    The injected provider owns business authentication; reuse its exact vendors grant.
    Default entity and parent vendor IDs are observations, not bill ownership rules.
    """
    linked = sorted({b["vendor_id"] for b in bills if b["vendor_id"] is not None})
    cov = {"listed": len(linked), "list_complete": True,
           "parent_scope": "captured_native_records", "details_attempted": 0,
           "details_read": 0, "detail_complete": False, "issues": []}
    resource["coverage"]["LINKED_VENDORS"] = cov
    if token is None:
        _finish(resource)
        cov["status"] = resource["status"]
        return
    budget -= _details(provider, token, resource, "vendors", [{"id": i} for i in linked],
                       sanitize_vendor, budget, cov)
    # Derive linked status before inventory errors can affect it.
    linked_result = {**resource, "coverage": {"LINKED_VENDORS": cov}}
    _finish(linked_result)
    cov["status"] = linked_result["status"]
    rows, inventory = _pages(provider, token, "vendors", page_size, max_pages)
    resource["coverage"]["vendors"] = inventory
    resource["issues"].extend(inventory["issues"])
    independent, seen = [], set()
    for row in rows:
        try:
            ident = uuid_text(row["id"])
            if ident in seen:
                raise RampError("Duplicate vendor list ID")
            seen.add(ident)
            # Never retry failed linked reads or allow a list payload to replace them.
            if ident not in linked:
                independent.append(row)
        except _ERRORS as exc:
            issue = _issue(exc)
            inventory["issues"].append(issue)
            resource["issues"].append(issue)
    _details(provider, token, resource, "vendors", independent, sanitize_vendor, budget, inventory)
    inventory["detail_complete"] = (inventory["detail_complete"] and not inventory["issues"]
        and all(i in {r["id"] for r in resource["records"]} for i in seen))
    _finish(resource)


def sync_records(provider, *, page_size=10, max_pages=1, detail_limit=10,
                 include_unlinked_purchase_orders=False, include_linked_vendors=True):
    """Read a bounded observation, prioritizing native bill vendor references.

    Vendor linked + inventory detail attempts together never exceed detail_limit.
    Set include_linked_vendors=False to retain historical inventory-only behavior.
    """
    _bounds(page_size, max_pages, detail_limit)
    if type(include_linked_vendors) is not bool:
        raise RampError("Invalid linked vendor option")
    if type(include_unlinked_purchase_orders) is not bool:
        raise RampError("Invalid independent PO option")
    observed = now()
    grants = {s: _grant(provider, s) for s in sorted(NATIVE_READ_SCOPES)}
    resources = {k: _resource(grants[s][1]) for k, s in RESOURCE_SCOPES.items()}
    plans = {
        "bills": [("bills", sanitize_bill), ("bills/drafts", lambda r: sanitize_bill(r, "draft"))],
        "vendors": [("vendors", sanitize_vendor)], "transactions": [("transactions", sanitize_transaction)],
        "agreements": [("vendors/agreements", sanitize_agreement)], "credits": [("vendors/credits", sanitize_credit)],
    }
    for name, entries in plans.items():
        resource, budget = resources[name], detail_limit
        token = grants[RESOURCE_SCOPES[name]][0]
        if name == "vendors" and include_linked_vendors:
            _vendor_capture(provider, token, resource, resources["bills"]["records"],
                            page_size, max_pages, budget)
            continue
        if token is not None:
            for path, sanitizer in entries:
                rows, coverage = _pages(provider, token, path, page_size, max_pages,
                    method="POST" if name == "agreements" else "GET",
                    query={"include_fully_used": "true"} if name == "credits" else None)
                resource["coverage"][path] = coverage
                resource["issues"].extend(coverage["issues"])
                budget -= _details(provider, token, resource, path, rows, sanitizer, budget, coverage)
        _finish(resource)

    resource = resources["purchase_orders"]
    token = grants["purchase_orders:read"][0]
    linked = sorted({b["purchase_order_id"] for b in resources["bills"]["records"] if b["purchase_order_id"]} |
                    {p for a in resources["agreements"]["records"] for p in (a["purchase_order_ids"] or [])})
    # No claim that lack of sampled links establishes lack of purchase orders.
    parent_complete = resources["bills"]["complete"] and resources["agreements"]["complete"]
    linked_cov = {"listed": len(linked), "list_complete": parent_complete, "parent_scope": "captured_bills_and_agreements"}
    resource["coverage"]["LINKED"] = linked_cov
    resource["coverage"]["INDEPENDENT_POs"] = {"status": "NOT_REQUESTED"}
    if token is not None:
        budget = detail_limit
        budget -= _details(provider, token, resource, "purchase-orders", [{"id": p} for p in linked],
                           sanitize_purchase_order, budget, linked_cov)
        for row in resource["records"]:
            row["discovery"] = ["LINKED"]
        if include_unlinked_purchase_orders:
            rows, cov = _pages(provider, token, "purchase-orders", page_size, max_pages)
            resource["coverage"]["INDEPENDENT_POs"] = cov
            resource["issues"].extend(cov["issues"])
            # De-duplicate overlap with linked details, but retry neither failures nor ambiguous IDs.
            independent, listed_ids = [], set()
            for row in rows:
                try:
                    ident = uuid_text(row["id"])
                    if ident in listed_ids:
                        raise RampError("Duplicate independent PO")
                    listed_ids.add(ident)
                    if ident not in linked:
                        independent.append(row)
                except _ERRORS as exc:
                    issue = _issue(exc)
                    cov["issues"].append(issue)
                    resource["issues"].append(issue)
            _details(provider, token, resource, "purchase-orders", independent, sanitize_purchase_order, budget, cov)
            for row in resource["records"]:
                if row["id"] in listed_ids:
                    row["discovery"].append("INDEPENDENT_POs")
            cov["status"] = "PARTIAL" if cov["issues"] else ("TRUNCATED" if not cov["list_complete"] or not cov["detail_complete"] else "COMPLETE" if listed_ids else "EMPTY")
        bills = {b["id"]: b for b in resources["bills"]["records"] if b["kind"] == "bill"}
        for row in resource["records"]:
            row["reciprocal_bill_ids"] = [i for i in (row["bill_ids"] or []) if i in bills
                and bills[i]["purchase_order_id"] == row["id"]
                and bills[i]["vendor_id"] == row["vendor_id"] and bills[i]["entity_id"] == row["entity_id"]]
    _finish(resource, attempted=bool(linked) or include_unlinked_purchase_orders)

    for name in ("approvals", "comments"):
        resource, token = resources[name], grants[RESOURCE_SCOPES[name]][0]
        parents = [("bill", b["id"]) for b in resources["bills"]["records"] if b["kind"] == "bill"]
        if name == "approvals":
            parents += [("transaction", t["id"]) for t in resources["transactions"]["records"]]
        else:
            parents += [("draft", b["id"]) for b in resources["bills"]["records"] if b["kind"] == "draft"]
        parent_complete = resources["bills"]["complete"] and (name == "comments" or resources["transactions"]["complete"])
        resource["coverage"]["parents"] = {"listed": len(parents), "list_complete": parent_complete,
                                                "detail_complete": len(parents) <= detail_limit,
                                                "parent_scope": "captured_native_records"}
        if token is not None:
            seen = set()
            for kind, ident in parents[:detail_limit]:
                obj = {"bill": "bills", "draft": "draft-bills", "transaction": "transactions"}[kind]
                path = "approvals" if name == "approvals" else f"comments/{obj}/{ident}"
                rows, cov = _pages(provider, token, path, page_size, max_pages,
                    query={"entity_type": kind.upper(), "entity_ids": [ident]} if name == "approvals" else None)
                resource["coverage"][kind + ":" + ident] = cov
                resource["issues"].extend({**i, "object_id": ident} for i in cov["issues"])
                for raw in rows:
                    try:
                        row = sanitize_approval(raw, kind, ident) if name == "approvals" else sanitize_comment(raw, obj, ident)
                        key = (row["object_type"], row["object_id"], row["id"])
                        if key in seen:
                            raise RampError("Duplicate child record")
                        seen.add(key)
                        resource["records"].append(row)
                    except _ERRORS as exc:
                        resource["issues"].append(_issue(exc, object_id=ident))
        _finish(resource, attempted=bool(parents))
    return seal_snapshot({"schema": SCHEMA, "origin": ORIGIN, "observed_at": observed,
                          "completed_at": now(), "resources": resources})


def _digest(snapshot):
    payload = {k: v for k, v in snapshot.items() if k not in {"checksum", "snapshot_status"}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def seal_snapshot(snapshot):
    return {**snapshot, "checksum": _digest(snapshot)}

# Explicit saved-record schema: no permissive blobs can reintroduce private text/URLs.
_COMMON = {"id", "sources"}
_RECORD_KEYS = {
    "bills": set("kind vendor_id entity_id account_id account_identity status approval_status status_summary sync_status created_at issued_at due_at paid_at archived_at accounting_date posting_date draft_bill_id purchase_order_id item_receipt_ids amount lines applied_credits deep_link_url vendor_name invoice_number".split()),
    "vendors": set("parent_vendor_id default_entity_id merchant_id status is_active created_at updated_at name".split()),
    "transactions": set("vendor_id entity_id merchant_id card_id spend_program_id original_transaction_id amount merchant_amount original_amount status sync_status all_requirements_met_and_approved user_transaction_time settlement_date accounting_date updated_at lines".split()),
    "agreements": set("vendor_id currency amount renewal_status is_active auto_renewal created_at updated_at archived_at deleted_at start_date end_date last_date_to_terminate purchase_order_ids lines".split()),
    "purchase_orders": set("vendor_id entity_id spend_program_id spend_request_id status receipt_status creation_source amount spend_total_amount created_at archived_at promise_date spend_start_date spend_end_date bill_ids transaction_ids item_receipt_ids three_way_match_enabled lines reciprocal_bill_ids discovery ramp_url".split()),
    "credits": set("vendor_id entity_id reference_bill_id accounting_date created_at archived_at total remaining total_applied applied_bills applied_drafts lines".split()),
    "approvals": set("id_kind object_id object_type entity_id entity_type status approval_history next_approver_count".split()),
    "comments": set("object_id object_type created_at".split()),
}
_MONEY_KEYS = {"amount", "unit_price", "merchant_amount", "original_amount", "spend_total_amount", "total", "remaining", "total_applied"}
_TIME_KEYS = set("created_at updated_at issued_at due_at paid_at archived_at deleted_at posting_date user_transaction_time settlement_date promise_date spend_start_date spend_end_date action_at".split())
_DATE_KEYS = {"start_date", "end_date", "last_date_to_terminate", "service_date"}
_BOOL_KEYS = {"is_active", "auto_renewal", "three_way_match_enabled", "all_requirements_met_and_approved"}
_LINE_KEYS = set("id kind amount unit_price quantity quantity_rate_check unit service_date sku purchase_order_line_item_id item_receipt_line_item_ids start_date end_date".split())


def _validate_money(value):
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"amount", "currency", "amount_minor", "minor_unit_conversion_rate"}:
        raise RampError("Invalid saved money")
    expected = _money({"amount": value["amount_minor"], "currency_code": value["currency"],
                       "minor_unit_conversion_rate": value["minor_unit_conversion_rate"]})
    if value != expected:
        raise RampError("Saved monetary units disagree")


def _validate_record(name, row):
    # Display fields were added on 2026-11-09; earlier saved captures remain valid without them.
    optional = {"bills": {"deep_link_url", "vendor_name", "invoice_number"}, "vendors": {"name"},
                "purchase_orders": {"ramp_url", "discovery", "reciprocal_bill_ids"}}.get(name, set())
    allowed = _COMMON | _RECORD_KEYS[name]
    if (not isinstance(row, dict) or set(row) - allowed or (allowed - optional) - set(row)
            or row["sources"] != SOURCE):
        raise RampError("Invalid saved record schema")
    if name == "comments":
        if not isinstance(row["id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", row["id"]):
            raise RampError("Invalid saved comment identity")
    else:
        uuid_text(row["id"])
    for key, value in row.items():
        if key in _MONEY_KEYS:
            _validate_money(value)
        elif key.endswith("_ids"):
            _ids(value)
        elif key.endswith("_id"):
            _optional_id(value)
        elif key in _TIME_KEYS:
            _timestamp(value)
        elif key in _DATE_KEYS:
            _date(value)
        elif key == "accounting_date":
            (_date if name == "credits" else _timestamp)(value)
        elif key in _BOOL_KEYS:
            _bool(value)
        elif key in {"status", "approval_status", "status_summary", "sync_status", "renewal_status", "receipt_status", "creation_source"}:
            _enum(value)
        elif key in {"vendor_name", "invoice_number", "name"}:
            if value is not None and _display(value) != value:
                raise RampError("Invalid saved display text")
    if "lines" in row:
        if name == "agreements":
            if row["lines"] is not None:
                raise RampError("Untyped agreement lines unavailable")
        else:
            if not isinstance(row["lines"], list):
                raise RampError("Invalid saved lines")
            seen = set()
            for line in row["lines"]:
                if not isinstance(line, dict) or set(line) != _LINE_KEYS:
                    raise RampError("Invalid saved line fields")
                ident = _optional_id(line["id"])
                if ident is not None and ident in seen:
                    raise RampError("Duplicate saved line")
                seen.add(ident)
                if line["kind"] not in {"line_items", "inventory_line_items", "expense_line_items", "credit_inventory"}:
                    raise RampError("Invalid line kind")
                if any(line[k] is not None for k in ("unit", "sku", "service_date")):
                    raise RampError("Unsupported line units")
                _validate_money(line["amount"])
                _validate_money(line["unit_price"])
                _quantity(line["quantity"])
                _date(line["start_date"])
                _date(line["end_date"])
                _optional_id(line["purchase_order_line_item_id"])
                _ids(line["item_receipt_line_item_ids"])
                check = "UNAVAILABLE"
                amount, rate, quantity = line["amount"], line["unit_price"], line["quantity"]
                if quantity is not None and amount and rate and amount["amount"] is not None and rate["amount"] is not None:
                    with localcontext() as ctx:
                        ctx.prec = 80
                        check = "MATCH" if (amount["currency"] == rate["currency"] and Decimal(quantity) * Decimal(rate["amount"]) == Decimal(amount["amount"])) else "MISMATCH"
                if line["quantity_rate_check"] != check:
                    raise RampError("Invalid saved quantity check")
    for key, id_key in (("applied_credits", "credit_id"), ("applied_bills", "bill_id"), ("applied_drafts", "bill_id")):
        if key not in row or row[key] is None:
            continue
        if not isinstance(row[key], list):
            raise RampError("Invalid saved monetary links")
        seen = set()
        for link in row[key]:
            if not isinstance(link, dict) or set(link) != {id_key, "amount"}:
                raise RampError("Invalid saved monetary link")
            ident = uuid_text(link[id_key])
            if ident in seen:
                raise RampError("Duplicate saved monetary link")
            seen.add(ident)
            _validate_money(link["amount"])
    if name == "bills":
        if row["kind"] not in {"bill", "draft"} or row["status"] not in ({"OPEN", "PAID"} if row["kind"] == "bill" else {"DRAFT"}):
            raise RampError("Invalid saved bill state")
        if row["kind"] == "bill" and (row["vendor_id"] is None or row["entity_id"] is None):
            raise RampError("Missing saved bill identity")
        if row["account_id"] is not None or row["account_identity"] != "UNAVAILABLE_IN_BILL_API":
            raise RampError("Unsupported account binding")
        if row.get("deep_link_url") is not None and (row["kind"] != "bill" or native_ui_url(row["deep_link_url"], row["id"], "bill") is None):
            raise RampError("Invalid saved bill link")
    if name == "transactions" and row["vendor_id"] is not None:
        raise RampError("Unsupported merchant-vendor inference")
    if name in {"agreements", "credits"}:
        uuid_text(row["vendor_id"])
    if name == "agreements" and row["currency"] is not None and not re.fullmatch("[A-Z]{3}", row["currency"]):
        raise RampError("Invalid saved agreement currency")
    if name == "purchase_orders":
        if row.get("ramp_url") is not None and native_ui_url(row["ramp_url"], row["id"], "purchase_order") is None:
            raise RampError("Invalid saved PO link")
        if "discovery" in row and (not isinstance(row["discovery"], list) or not row["discovery"] or set(row["discovery"]) - {"LINKED", "INDEPENDENT_POs"}):
            raise RampError("Invalid PO discovery")
    if name == "approvals":
        if (row["id_kind"] != "parent_resource" or row["object_type"] not in {"bill", "transaction"}
                or row["entity_type"] != row["object_type"] or row["id"] != row["object_id"] or row["id"] != row["entity_id"]
                or row["status"] not in {"APPROVED", "INITIALIZED", "PENDING", "REJECTED", "TERMINATED"}
                or type(row["next_approver_count"]) is not int or row["next_approver_count"] < 0):
            raise RampError("Invalid saved approval identity")
        if not isinstance(row["approval_history"], list):
            raise RampError("Invalid approval history")
        for item in row["approval_history"]:
            if set(item) != {"action_at", "step_status"}:
                raise RampError("Invalid approval history fields")
            _timestamp(item["action_at"])
            if item["step_status"] not in {None, "APPROVED", "INITIALIZED", "PENDING", "REJECTED", "TERMINATED", "SKIPPED", "NOT_APPLICABLE"}:
                raise RampError("Invalid saved approval step")
    if name == "comments" and row["object_type"] not in {"bills", "draft-bills"}:
        raise RampError("Invalid saved comment parent")


def _validate_issues(issues):
    if not isinstance(issues, list):
        raise RampError("Invalid issue list")
    for issue in issues:
        if (not isinstance(issue, dict) or set(issue) - {"code", "http_status", "object_id"}
                or issue.get("code") not in {"HTTP_ERROR", "INVALID_OR_UNAVAILABLE_RESPONSE"}):
            raise RampError("Invalid saved issue")
        _optional_id(issue.get("object_id"))
        if "http_status" in issue and (type(issue["http_status"]) is not int or not 100 <= issue["http_status"] <= 599):
            raise RampError("Invalid saved HTTP status")


def _validate_coverage(resource):
    allowed = {"status", "listed", "list_complete", "parent_scope", "details_attempted", "details_read",
               "detail_complete", "pages_read", "has_next", "page_size", "max_pages", "issues"}
    counts = {"listed", "details_attempted", "details_read", "pages_read", "page_size", "max_pages"}
    for key, cov in resource["coverage"].items():
        if key not in {"bills", "bills/drafts", "vendors", "transactions", "vendors/agreements", "vendors/credits",
                       "LINKED", "LINKED_VENDORS", "INDEPENDENT_POs", "parents"}:
            kind, ident = key.split(":", 1)
            if kind not in {"bill", "transaction", "draft"}:
                raise RampError("Invalid coverage parent")
            uuid_text(ident)
        if not isinstance(cov, dict) or set(cov) - allowed:
            raise RampError("Invalid saved coverage")
        for k, value in cov.items():
            if k in counts and (type(value) is not int or not 0 <= value <= 100000):
                raise RampError("Invalid coverage count")
            if k in {"list_complete", "detail_complete"} and type(value) is not bool:
                raise RampError("Invalid coverage completeness")
        if "has_next" in cov and cov["has_next"] is not None and type(cov["has_next"]) is not bool:
            raise RampError("Invalid next-page coverage")
        if "status" in cov and cov["status"] not in STATUSES:
            raise RampError("Invalid coverage status")
        if "parent_scope" in cov and cov["parent_scope"] not in {"captured_native_records", "captured_bills_and_agreements"}:
            raise RampError("Invalid coverage scope")
        _validate_issues(cov.get("issues", []))
        if cov.get("list_complete") and cov.get("has_next"):
            raise RampError("Contradictory page coverage")
        if cov.get("details_read", 0) > cov.get("details_attempted", 0):
            raise RampError("Contradictory detail coverage")
        if cov.get("detail_complete") and cov.get("details_read", 0) != cov.get("details_attempted", 0):
            raise RampError("Incomplete detail reads")
        if resource["complete"] and (cov.get("list_complete") is False or cov.get("detail_complete") is False or cov.get("issues")):
            raise RampError("Contradictory completed coverage")
    if resource["complete"] and not any(c.get("list_complete") is True for c in resource["coverage"].values()):
        raise RampError("No successful read coverage")


def _validate_snapshot(snapshot):
    """Validate a local observation; does not authorize financial use or provider access."""
    try:
        if (not isinstance(snapshot, dict) or set(snapshot) - {"schema", "origin", "observed_at", "completed_at", "resources", "checksum", "snapshot_status"}
                or snapshot.get("schema") != SCHEMA or snapshot.get("origin") != ORIGIN
                or not isinstance(snapshot.get("checksum"), str) or not hmac.compare_digest(snapshot["checksum"], _digest(snapshot))):
            raise RampError("Invalid snapshot checksum or schema")
        observed, completed = _timestamp(snapshot["observed_at"]), _timestamp(snapshot["completed_at"])
        if observed is None or completed is None or datetime.fromisoformat(completed) < datetime.fromisoformat(observed):
            raise RampError("Invalid observation interval")
        resources = snapshot["resources"]
        if not isinstance(resources, dict) or set(resources) != set(RESOURCE_SCOPES):
            raise RampError("Invalid resource set")
        if len(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()) > MAX_SNAPSHOT_BYTES:
            raise RampError("Snapshot exceeded size bound")
        for name, res in resources.items():
            if (not isinstance(res, dict) or set(res) != {"status", "records", "complete", "grant", "issues", "coverage"}
                    or res["status"] not in STATUSES or type(res["complete"]) is not bool
                    or not isinstance(res["records"], list) or not isinstance(res["issues"], list)
                    or not isinstance(res["coverage"], dict) or not isinstance(res["grant"], dict)):
                raise RampError("Invalid resource schema")
            grant = res["grant"]
            if set(grant) - {"granted", "requested", "missing", "unexpected", "scope_reported", "diagnosis", "state", "sources", "code", "http_status"}:
                raise RampError("Invalid saved grant fields")
            for field in ("granted", "requested", "missing", "unexpected"):
                if field in grant and (not isinstance(grant[field], list) or any(
                        not isinstance(s, str) or not re.fullmatch(r"[a-z][a-z0-9_]*:(?:read|write)", s) for s in grant[field])):
                    raise RampError("Invalid saved scopes")
            exact = (grant.get("granted") == [RESOURCE_SCOPES[name]] and grant.get("requested") == [RESOURCE_SCOPES[name]]
                     and grant.get("scope_reported") is True and grant.get("state") == "GRANTED")
            if res["complete"] != (res["status"] in {"COMPLETE", "EMPTY"}):
                raise RampError("Contradictory resource completeness")
            if (res["records"] or res["complete"]) and not exact:
                raise RampError("Records without exact scope evidence")
            if res["status"] in {"EMPTY", "NOT_REQUESTED", "FORBIDDEN", "UNAVAILABLE"} and res["records"]:
                raise RampError("Contradictory resource availability")
            if res["status"] == "COMPLETE" and not res["records"]:
                raise RampError("Contradictory completed records")
            if res["complete"] and res["issues"]:
                raise RampError("Complete resource contains errors")
            _validate_issues(res["issues"])
            _validate_coverage(res)
            seen = set()
            for row in res["records"]:
                _validate_record(name, row)
                key = (row.get("kind"), row.get("object_type"), row.get("object_id"), row["id"])
                if key in seen:
                    raise RampError("Duplicate saved record")
                seen.add(key)
        bills = {b["id"]: b for b in resources["bills"]["records"] if b["kind"] == "bill"}
        for po in resources["purchase_orders"]["records"]:
            expected = [i for i in (po["bill_ids"] or []) if i in bills and bills[i]["purchase_order_id"] == po["id"]
                        and bills[i]["vendor_id"] == po["vendor_id"] and bills[i]["entity_id"] == po["entity_id"]]
            if "reciprocal_bill_ids" in po and po["reciprocal_bill_ids"] != expected:
                raise RampError("Invalid reciprocal association")
    except _ERRORS:
        raise RampError("Invalid Ramp records snapshot") from None


def load_snapshot(path, *, at=None, max_age_seconds=86400):
    try:
        path = Path(path)
        with path.open("rb") as handle:
            raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise RampError("Snapshot exceeded limit")
        snapshot = json.loads(raw)
        _validate_snapshot(snapshot)
        current = at or datetime.now(timezone.utc)
        if current.tzinfo is None or type(max_age_seconds) is not int or max_age_seconds <= 0:
            raise RampError("Invalid observation age policy")
        age = (current - datetime.fromisoformat(snapshot["observed_at"])).total_seconds()
        if age < 0 or current < datetime.fromisoformat(snapshot["completed_at"]):
            raise RampError("Future observation")
        snapshot["snapshot_status"] = {"integrity": "CHECKSUM_VERIFIED", "freshness": "FRESH" if age <= max_age_seconds else "STALE",
                                       "age_seconds": int(age), "provider_attestation": False,
                                       "usable_for_evaluation": False, "requires_contract_mapping": True}
        return snapshot
    except (*_ERRORS, OSError):
        return {"schema": SCHEMA, "origin": ORIGIN, "observed_at": None, "completed_at": None,
                "resources": {name: {**_resource({}), "status": "UNAVAILABLE"} for name in RESOURCE_SCOPES},
                "snapshot_status": {"integrity": "INVALID", "freshness": "UNKNOWN", "usable_for_evaluation": False}}
