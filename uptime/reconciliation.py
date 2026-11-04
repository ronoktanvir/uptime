"""Match a confirmed award to posted credits and to applications on identified bills.

Inputs are an award-specific set of records selected by trusted server code.
A memo reference must agree explicitly. Never match by amount, date, or name.
"""
from decimal import Decimal, InvalidOperation

from .contracts import Source


def _amount(value):
    try:
        if not isinstance(value, (str, Decimal)):
            raise ValueError("Decimal text required")
        value = Decimal(value)
        if not value.is_finite() or value < 0 or value != value.quantize(Decimal(".01")):
            raise ValueError("Invalid USD amount")
    except InvalidOperation as exc:
        raise ValueError("Invalid USD amount") from exc
    return value


def _required(record, field):
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {field}")
    return value


def _documented_source(row):
    source = Source(row["source"])
    if source not in (Source.VENDOR, Source.REPLAY, Source.CUSTOMER, Source.RAMP):
        raise ValueError("Financial record requires financial evidence")
    return source.value


def _index(records, tenant, vendor):
    by_id = {}
    for row in records:
        ident = _required(row, "id")
        if row.get("tenant") != tenant or row.get("vendor_id") != vendor or row.get("currency") != "USD":
            raise ValueError("Mismatched tenant, vendor or currency")
        if ident in by_id and by_id[ident] != row:
            raise ValueError("Conflicting duplicate record")
        by_id[ident] = row
    return by_id


def reconcile(tenant, award, credits, applications, bills):
    """Validate a single award. Return JSON-safe totals and record-level provenance."""
    vendor = _required(award, "vendor_id")
    award_id = _required(award, "id")
    memo = _required(award, "memo_ref")
    if (not tenant or award.get("tenant") != tenant or award.get("currency") != "USD"
            or award.get("confirmed") is not True):
        raise ValueError("Confirmed in-tenant USD award required")
    limit = _amount(award["amount"])
    credits = _index(credits, tenant, vendor)
    bills = _index(bills, tenant, vendor)
    apps = _index(applications, tenant, vendor)
    posted_by_credit = {}
    applied_by_credit = {}
    applied_by_bill = {}
    pairs = set()
    sources = {_documented_source(award)}
    for ident, credit in credits.items():
        if credit.get("award_id") != award_id or credit.get("memo_ref") != memo:
            raise ValueError("Unmatched credit record")
        posted_by_credit[ident] = _amount(credit["amount"])
        sources.add(_documented_source(credit))
    for app in apps.values():
        credit_id, bill_id = _required(app, "credit_id"), _required(app, "bill_id")
        if credit_id not in credits or bill_id not in bills:
            raise ValueError("Unverified credit or bill")
        if (credit_id, bill_id) in pairs:
            raise ValueError("Duplicate credit/bill application pair")
        pairs.add((credit_id, bill_id))
        amount = _amount(app["amount"])
        applied_by_credit[credit_id] = applied_by_credit.get(credit_id, Decimal(0)) + amount
        applied_by_bill[bill_id] = applied_by_bill.get(bill_id, Decimal(0)) + amount
        if (applied_by_credit[credit_id] > posted_by_credit[credit_id]
                or applied_by_bill[bill_id] > _amount(bills[bill_id]["amount"])):
            raise ValueError("Application exceeds credit or bill")
        sources.update((_documented_source(app), _documented_source(bills[bill_id])))
    posted = sum(posted_by_credit.values(), Decimal(0))
    applied = sum(applied_by_credit.values(), Decimal(0))
    if posted > limit:
        raise ValueError("Posted credit exceeds award")
    totals = {"awarded": limit, "posted": posted, "applied": applied,
              "outstanding": limit - applied, "unposted": limit - posted,
              "unapplied_posted": posted - applied}
    return {**{k: f"{v:.2f}" for k, v in totals.items()}, "currency": "USD",
            "award_id": award_id, "memo_ref": memo, "credit_ids": sorted(credits),
            "application_ids": sorted(apps), "bill_ids": sorted(applied_by_bill), "sources": sorted(sources)}


def demo_reconciliation(award_amount, stage, *, tenant="demo", case_id="twilio"):
    """Project persisted case stage onto simulated records; never draw on sandbox IDs."""
    stages = ("NONE", "AWARDED", "POSTED", "PARTIALLY_APPLIED", "APPLIED")
    if stage not in stages:
        raise ValueError("Unknown reconciliation stage")
    if stage == "NONE":
        if _amount(award_amount) != 0:
            raise ValueError("Confirmed award required")
        return {**{k: "0.00" for k in ("awarded", "posted", "applied", "outstanding", "unposted",
                                          "unapplied_posted")}, "currency": "USD", "award_id": None,
                "memo_ref": None, "credit_ids": [], "application_ids": [], "bill_ids": [],
                "sources": [Source.REPLAY.value], "stage": stage}
    amount = _amount(award_amount)
    base = {"tenant": tenant, "vendor_id": "fixture-vendor:" + case_id, "currency": "USD"}
    key = "sim:" + case_id + ":"
    award = {**base, "id": key + "award", "memo_ref": key + "memo", "amount": str(amount),
             "source": Source.VENDOR.value, "confirmed": True}
    credits, applications, bills = [], [], []
    if stage in stages[2:]:
        credits.append({**base, "id": key + "credit", "amount": str(amount), "award_id": award["id"],
                        "memo_ref": award["memo_ref"], "source": Source.REPLAY.value})
    if stage in stages[3:]:
        applied = amount if stage == "APPLIED" else (amount / 2).quantize(Decimal(".01"), rounding="ROUND_DOWN")
        bills.append({**base, "id": key + "bill", "amount": str(amount), "source": Source.CUSTOMER.value})
        applications.append({**base, "id": key + "application", "credit_id": credits[0]["id"],
                             "bill_id": bills[0]["id"], "amount": str(applied), "source": Source.REPLAY.value})
    return {**reconcile(tenant, award, credits, applications, bills), "stage": stage}
