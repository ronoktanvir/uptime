"""Input adapters for the independent witness. No gold or oracle imports.

Synthetic promotion controls are authored here from ordinary public arithmetic;
they are never used to fill missing heldout evidence.
"""
from calendar import monthrange
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import re


def public_identity(public):
    """Read the operator-staged public proposal only; intake validates it again."""
    import json
    import os
    from hashlib import sha256
    from pathlib import Path
    root = os.environ.get("UPTIME_PUBLIC_EXTRACTIONS")
    path = Path(root) / (sha256(public).hexdigest() + ".json") if root else None
    if not path or not path.is_file():
        return {}
    artifact = json.loads(path.read_bytes())
    if artifact.get("source_sha256") != sha256(public).hexdigest():
        return {}
    result = {}
    for row in artifact.get("proposal", []):
        if row.get("field") == "resource_terms":
            result.update(row["value"])
    return result


def promotion_scenarios(public, manifest, overlay):
    """Half-percent loss of a $100 fee; zero loss; cure; late cure.

    The independent arithmetic reads the public percentage table, never the
    compiler's tiers or evaluator. These deliberately invented controls carry
    complete evidence; that claim does not extend to any heldout records.
    """
    tiers = [(Decimal(a), Decimal(b)) for a, b in re.findall(
        r"\|\s*Below\s+([0-9.]+)%\s*\|\s*([0-9.]+)%\s*\|", public.decode(), re.I)]
    if not tiers:
        raise ValueError("PUBLIC_CONTROL_TABLE_UNSUPPORTED")
    availability = Decimal("99.5")
    rate = max((rate for threshold, rate in tiers if availability < threshold), default=Decimal(0))
    alternate = Decimal("99.995")
    if rate <= 0 or any(alternate < threshold for threshold, _ in tiers):
        raise ValueError("PUBLIC_CONTROL_NOT_DISTINGUISHING")
    start = datetime.fromisoformat(max(overlay["effective_from"], manifest["effective"][0])).replace(tzinfo=UTC)
    start = start.replace(day=1) + timedelta(days=32)
    start = start.replace(day=1)
    end = start + timedelta(days=monthrange(start.year, start.month)[1])
    month = start.strftime("%Y-%m")
    received = end + timedelta(days=1)
    scoped = {k: overlay[k] for k in ("agreement", "account", "product", "plan", "resource_id", "fee_line_ref")}
    interval = dict(ref="independent-outage", account=overlay["account"], resource_id=overlay["resource_id"],
                    start=start.isoformat(), end=(start + (end-start)/200).isoformat(),
                    symptom=manifest["symptoms"][0], cause=manifest["provider_causes"][0])
    line = dict(ref=overlay["fee_line_ref"], account=overlay["account"], resource_id=overlay["resource_id"],
                month=month, kind="resource_service", amount_cents=10000, currency="USD", category="monthly_recurring")
    if manifest.get("fee_adjustment"):
        line.update(discount_ref="independent-zero-discount", gross_cents=10000, discount_cents=0)
    proof = dict(verified=True, ref="independent-original", account=overlay["account"],
                 resource_id=overlay["resource_id"], submitted_to=manifest.get("submission_channel"),
                 fields={name: "independent-control-reference" for name in manifest.get("request_fields", [])})
    facts = dict(scoped, month=month, received_at=received.isoformat(), monitor_source="synthetic_customer",
                 monitor_ref="independent-complete-month", month_complete=True, itemized_complete=True,
                 intervals=[interval], exclusions=[], fee_lines=[line], filing_proof=proof)
    for key in ("maintenance", "prior_credit"):
        if manifest.get(key):
            facts[key + "_evidence"] = dict(verified=True, complete=True, ref="independent-empty-" + key,
                agreement=overlay["agreement"], account=overlay["account"], resource_id=overlay["resource_id"],
                month=month, records=[])
    amount = format((Decimal(100) * rate / 100).quantize(Decimal(".01"), rounding=ROUND_HALF_UP), ".2f")
    tests = [dict(name="SCRIPTED independent half-percent loss", facts=facts,
                  expected=dict(outcome="ELIGIBLE", amount=amount)),
             dict(name="SCRIPTED independent zero-loss refusal", facts=facts | {"intervals": []},
                  expected=dict(outcome="INELIGIBLE"))]
    # A supplement fills an actually missing field, using the original clock.
    if manifest.get("supplement") and proof["fields"]:
        field = next(iter(proof["fields"]))
        partial = deepcopy(facts)
        del partial["filing_proof"]["fields"][field]
        tests.append(dict(name="SCRIPTED missing original item", facts=partial,
                          expected=dict(outcome="INSUFFICIENT_EVIDENCE")))
        supplement = dict(verified=True, ref="independent-supplement", original_ref=proof["ref"],
                          agreement=overlay["agreement"], account=overlay["account"],
                          resource_id=overlay["resource_id"], month=month,
                          submitted_to=proof["submitted_to"], received_at=(received+timedelta(days=1)).isoformat(),
                          fields={field: proof["fields"][field]})
        cured = deepcopy(partial)
        cured["filing_proof"]["supplements"] = [supplement]
        tests.append(dict(name="SCRIPTED timely cure", facts=cured, expected=dict(outcome="ELIGIBLE", amount=amount)))
        late = deepcopy(cured)
        late["filing_proof"]["supplements"][0]["received_at"] = (end+timedelta(days=366)).isoformat()
        tests.append(dict(name="SCRIPTED late cure refusal", facts=late, expected=dict(outcome="INELIGIBLE")))
    return tests


def cents(value):
    result = Decimal(value) * 100
    if result != result.to_integral_value():
        raise ValueError("SUBCENT_INPUT_UNREPRESENTABLE")
    return int(result)


def invoice_report(invoice, mapping, scope):
    """Only a matching billing attestation can allocate a discount to a resource."""
    if not mapping or any(mapping[k] != v for k, v in {
        "account_id": scope["account"], "resource_id": scope["component"], "invoice_id": invoice["invoice_id"]}.items()):
        return None
    lines = {r["line_id"]: r for r in invoice["lines"]}
    if len(lines) != len(invoice["lines"]):
        return None
    gross, discount = lines.get(mapping["recurring_line_id"]), lines.get(mapping["discount_line_id"])
    if not gross or not discount or gross["resource_id"] != scope["component"]:
        return None
    if (gross["type"] != "monthly_recurring" or discount["type"] != "allocated_discount"
            or discount["resource_id"] not in (None, scope["component"])):
        return None
    net, gross_cents, discount_cents = cents(mapping["net_recurring"]), cents(gross["amount"]), -cents(discount["amount"])
    if not 0 <= discount_cents <= gross_cents or gross_cents-discount_cents != net:
        return None
    return dict(kind="resource_invoice", source_ref=mapping["source_locator"], observed_at=mapping["available_at"],
                itemized_complete=True, lines=[dict(ref=gross["line_id"], resource_id=scope["component"],
                month=scope["month"], currency=invoice["currency"], kind="resource_service", category="monthly_recurring",
                amount_cents=net, gross_cents=gross_cents, discount_cents=discount_cents,
                discount_ref=discount["line_id"])])
