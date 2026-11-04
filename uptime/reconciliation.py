"""Match a confirmed award to posted credits and to applications on identified bills.

Inputs are an award-specific set of records selected by trusted server code.
A memo reference must agree explicitly. Never match by amount, date, or name.
"""
from decimal import Decimal, InvalidOperation
from uuid import UUID

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
    if (not isinstance(value, str) or not value or value != value.strip()
            or not value.isprintable()):
        raise ValueError(f"Missing or noncanonical {field}")
    return value


def _source(row, allowed):
    source = Source(row.get("source"))
    if source not in allowed:
        raise ValueError("Source cannot substantiate this record type")
    return source


def _provider_id(value):
    # Reject alternative spellings of one Ramp UUID before using it as a ledger key.
    if value != str(UUID(value)):
        raise ValueError("Noncanonical Ramp UUID")
    return value


def _index(records, tenant, vendor, role):
    allowed = {Source.RAMP, Source.REPLAY}
    if role == "bill":
        allowed.add(Source.CUSTOMER)
    by_id = {}
    for row in records:
        ident = _required(row, "id")
        if row.get("tenant") != tenant or row.get("vendor_id") != vendor or row.get("currency") != "USD":
            raise ValueError("Mismatched tenant, vendor or currency")
        if _source(row, allowed) == Source.RAMP:
            _provider_id(vendor)
            if role == "application":
                # Ramp exposes a cumulative amount per credit/bill pair, with no
                # independent application ID. Name the pair consistently across both GETs.
                pair = (_provider_id(_required(row, "credit_id")), _provider_id(_required(row, "bill_id")))
                if ident != f"ramp:{pair[0]}:{pair[1]}":
                    raise ValueError("Unmatched provider application identifier")
            else:
                _provider_id(ident)
        if ident in by_id and by_id[ident] != row:
            raise ValueError("Conflicting duplicate record")
        by_id[ident] = row
    return by_id


def _provenance(award, posted, applied):
    def labels(values):
        return sorted(values) or [Source.UNAVAILABLE.value]
    return {"awarded": labels(award), "posted": labels(posted), "applied": labels(applied),
            "outstanding": labels(award | applied), "unposted": labels(award | posted),
            "unapplied_posted": labels(posted | applied)}


def reconcile(tenant, award, credits, applications, bills):
    """Reconcile a confirmed simulated memo against one isolated settlement evidence set.

    All rows must have been observed by a trusted adapter. Sandbox utilization
    can establish a sandbox result only. No source here certifies customer recovery.
    """
    vendor = _required(award, "vendor_id")
    award_id = _required(award, "id")
    memo = _required(award, "memo_ref")
    if (_required(award, "tenant") != tenant or award.get("currency") != "USD"
            or award.get("confirmed") is not True):
        raise ValueError("Confirmed in-tenant USD award required")
    award_sources = {_source(award, {Source.VENDOR}).value}
    limit = _amount(award["amount"])
    credits = _index(credits, tenant, vendor, "credit")
    bills = _index(bills, tenant, vendor, "bill")
    apps = _index(applications, tenant, vendor, "application")
    settlement_sources = {row["source"] for group in (credits, bills, apps) for row in group.values()}
    if Source.RAMP in settlement_sources and settlement_sources != {Source.RAMP}:
        raise ValueError("Sandbox and fixture settlement records cannot be combined")
    posted_by_credit = {}
    applied_by_credit = {}
    applied_by_bill = {}
    pairs = set()
    posted_sources = set()
    applied_sources = set()
    for ident, credit in credits.items():
        if credit.get("award_id") != award_id or credit.get("memo_ref") != memo:
            raise ValueError("Unmatched credit record")
        posted_by_credit[ident] = _amount(credit["amount"])
        posted_sources.add(credit["source"])
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
        applied_sources.update((app["source"], bills[bill_id]["source"], credits[credit_id]["source"]))
    posted = sum(posted_by_credit.values(), Decimal(0))
    applied = sum(applied_by_credit.values(), Decimal(0))
    if posted > limit:
        raise ValueError("Posted credit exceeds award")
    totals = {"awarded": limit, "posted": posted, "applied": applied,
              "outstanding": limit - applied, "unposted": limit - posted,
              "unapplied_posted": posted - applied}
    return {**{k: f"{v:.2f}" for k, v in totals.items()}, "currency": "USD",
            "award_id": award_id, "memo_ref": memo, "credit_ids": sorted(credits),
            "application_ids": sorted(apps), "bill_ids": sorted(applied_by_bill),
            "stage_sources": _provenance(award_sources, posted_sources, applied_sources),
            "sources": sorted(award_sources | posted_sources | applied_sources),
            "actual_recovery": None}


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
                "sources": [Source.REPLAY.value], "stage": stage,
                "stage_sources": _provenance(set(), set(), set()), "actual_recovery": None}
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
