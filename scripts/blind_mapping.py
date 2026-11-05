"""Input adapters for the independent witness. No gold or oracle imports.

Synthetic promotion controls are authored here from ordinary public arithmetic;
they are never used to fill missing heldout evidence.
"""
from calendar import monthrange
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import re


def wire_ref(value):
    """Represent an opaque locator losslessly by digest when it is not a wire ID."""
    from hashlib import sha256
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}", value):
        return value
    return "sha256:" + sha256(value.encode()).hexdigest()


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


def event_plan(records, scope, manifest):
    """Project typed records into supported wires without adding missing proof.

    A report assembled from bounded incidents is explicitly incomplete. Original
    and supplement references retain the frozen IDs and original receive clocks.
    Every derived delivery is delayed until all of its source records are known.
    """
    from hashlib import sha256
    from datetime import datetime
    events, gaps = [], set()
    by_id = {r["id"]: r for r in records}

    def enqueue(role, body, sources, identifier=None):
        body["source_ref"] = wire_ref(body["source_ref"])
        available = max((r["available_at"] for r in sources), key=datetime.fromisoformat)
        events.append(dict(role=role, body=body, id=identifier or "mapped-" + sha256(
            (body["kind"] + "|" + "|".join(sorted(r["id"] for r in sources))).encode()).hexdigest()[:40],
            available_at=available, source_ids=[r["id"] for r in sources],
            source_locators=[r["source_locator"] for r in sources]))

    scoped = [r for r in records if r.get("account_id") == scope["account"]]
    mappings = [r for r in scoped if r["kind"] == "provider_resource_attestation"
                and r.get("resource_id") == scope["component"]]
    intervals, status_sources = [], []
    for row in scoped:
        if row["kind"] != "provider_incident":
            continue
        resource = row.get("resource_id")
        sources = [row]
        if resource is None:
            candidates = [m for m in mappings if m.get("incident_id") == row.get("incident_id")
                          and all(m[k] == row[k] for k in ("start", "end_exclusive"))]
            if len(candidates) != 1:
                gaps.add("PROVIDER_RESOURCE_MAPPING_MISSING")
                continue
            sources += candidates
            resource = candidates[0]["resource_id"]
        if resource != scope["component"]:
            continue
        # Provider cause does not itself establish valid customer requests.
        symptom = manifest["symptoms"][0] if row.get("all_valid_enqueue_requests_failed") is True else "unverified"
        intervals.append(dict(ref=row.get("incident_id", row["id"]), resource_id=resource,
                              start=row["start"], end=row["end_exclusive"], symptom=symptom))
        status_sources.extend(sources)
    if intervals:
        body = dict(kind="resource_status", source_ref="bounded-status-" + sha256(
            "|".join(sorted(r["id"] for r in status_sources)).encode()).hexdigest()[:32],
            observed_at=max((r["available_at"] for r in status_sources), key=datetime.fromisoformat), complete=False,
            start=min((r["start"] for r in intervals), key=datetime.fromisoformat),
            end=max((r["end"] for r in intervals), key=datetime.fromisoformat), intervals=intervals)
        enqueue("status", body, status_sources)
        gaps.add("COMPLETE_MONTH_STATUS_MISSING")
    else:
        gaps.add("SCOPED_PROVIDER_OBSERVATION_MISSING")
    probes = [r for r in scoped if r["kind"] == "customer_probe" and r.get("resource_id") == scope["component"]]
    if probes:
        causes = [dict(ref=r.get("incident_id", r["id"]), resource_id=scope["component"],
                       start=r["start"], end=r["end_exclusive"], cause="unverified") for r in probes]
        enqueue("customer", dict(kind="resource_attribution", source_ref=probes[0]["source_locator"],
            observed_at=max((r["available_at"] for r in probes), key=datetime.fromisoformat), complete=False,
            start=min((r["start"] for r in probes), key=datetime.fromisoformat),
            end=max((r["end_exclusive"] for r in probes), key=datetime.fromisoformat), causes=causes, exclusions=[]), probes)
        gaps.update({"COMPLETE_MONTH_ATTRIBUTION_MISSING", "CUSTOMER_CAUSE_ATTESTATION_MISSING"})
    else:
        gaps.add("CUSTOMER_REQUEST_PROOF_MISSING")
    invoices = [r for r in scoped if r["kind"] == "invoice"]
    billmaps = [r for r in scoped if r["kind"] == "billing_resource_attestation" and r.get("resource_id") == scope["component"]]
    if len(invoices) == 1:
        invoice = invoices[0]
        mapping = billmaps[0] if len(billmaps) == 1 else None
        body = invoice_report(invoice, mapping, scope)
        if body:
            enqueue("billing", body, [invoice, mapping])
        else:
            gaps.add("SCOPED_NET_BILLING_MAPPING_MISSING")
            # Preserve identifiable positive lines while refusing a complete net base.
            lines = [dict(ref=r["line_id"], resource_id=scope["component"], month=scope["month"],
                          currency=invoice["currency"], kind="resource_service" if r["type"] == "monthly_recurring" else "other",
                          category=r["type"], amount_cents=cents(r["amount"])) for r in invoice["lines"]
                     if r.get("resource_id") == scope["component"] and cents(r["amount"]) >= 0]
            if lines:
                enqueue("billing", dict(kind="resource_invoice", source_ref=invoice["source_locator"],
                    observed_at=invoice["available_at"], itemized_complete=False, lines=lines), [invoice])
        # An aggregate previously granted amount is not an issued-credit ID or a signed history.
        if manifest.get("prior_credit"):
            gaps.add("PRIOR_ISSUANCE_IDS_AND_COMPLETE_HISTORY_MISSING")
    else:
        gaps.add("SCOPED_BILLING_MISSING")
    if manifest.get("maintenance"):
        gaps.add("COMPLETE_MAINTENANCE_HISTORY_MISSING")

    originals = [r for r in scoped if r["kind"] == "historical_customer_filing_receipt"
                 and r.get("resource_id") == scope["component"]]

    def fields(receipt):
        attachments = [by_id[r] for r in receipt["attachments"] if r in by_id]
        result = []
        for name in manifest.get("request_fields", []):
            words = set(re.findall(r"[a-z]+", name.casefold()))
            refs = []
            if "month" in words and receipt.get("measured_month") == scope["month"]:
                refs = [scope["month"]]
            elif words & {"intervals", "timestamps", "logs"}:
                refs = [r.get("incident_id", r["id"]) for r in attachments if r["kind"] in {"provider_incident", "customer_probe"}]
            elif words & {"cause", "controller"}:
                refs = [r["id"] for r in attachments if r["kind"] in {"provider_incident", "provider_resource_attestation"} and r.get("cause")]
            elif words & {"requests", "valid"}:
                refs = [r["id"] for r in attachments if r["kind"] == "customer_probe"
                        and r.get("credentials_valid") is True and r.get("rate_limit_exhausted") is False
                        and r.get("all_valid_enqueue_requests_failed") is True]
            elif words & {"billing", "invoice", "charges", "fees"}:
                refs = [r["recurring_line_id"] for r in attachments if r["kind"] == "billing_resource_attestation"]
            elif words & {"endpoint", "resource"} and receipt.get("resource_id") == scope["component"]:
                refs = [scope["component"]]
            if refs:
                result.append(dict(name=name, refs=sorted(set(refs))))
        return result

    for row in scoped:
        if row["kind"] not in {"historical_customer_filing_receipt", "historical_customer_supplement_receipt"}:
            continue
        if row.get("resource_id") != scope["component"]:
            continue
        supplement = row["kind"] == "historical_customer_supplement_receipt"
        if supplement and len(originals) != 1:
            gaps.add("SUPPLEMENT_ORIGINAL_RECEIPT_MISSING")
            continue
        body = dict(kind="supplement_filing_receipt" if supplement else "original_filing_receipt",
                    source_ref=row["source_locator"], observed_at=row["available_at"], receipt_id=row["id"],
                    received_at=row["received_at"], submitted_to=row["channel"], fields=fields(row))
        if supplement:
            body["original_ref"] = originals[0]["id"]
        enqueue("vendor", body, [row], row["id"])
    return sorted(events, key=lambda r: datetime.fromisoformat(r["available_at"])), sorted(gaps)


def bounded_input_diagnostic(records, scope, manifest):
    """Independent local lower-bound arithmetic, explicitly not an app result.

    It cannot establish exact monthly availability, an award, complete exclusions
    or issued-credit history. No synthetic evidence is sent back to the app.
    """
    def words(text):
        return set(re.findall(r"[a-z]+", text.casefold()))

    def interval(row):
        return datetime.fromisoformat(row["start"]), datetime.fromisoformat(row["end_exclusive"])

    def seconds(spans):
        merged = []
        for start, end in sorted(spans):
            if start >= end:
                continue
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        microseconds = sum((b-a)//timedelta(microseconds=1) for a, b in merged)
        return str(Decimal(microseconds)/1_000_000)

    rows = [r for r in records if r.get("account_id") == scope["account"]]
    maps = [r for r in rows if r["kind"] == "provider_resource_attestation" and r.get("resource_id") == scope["component"]]
    probes = [r for r in rows if r["kind"] == "customer_probe" and r.get("resource_id") == scope["component"]
              and r.get("credentials_valid") is True and r.get("rate_limit_exhausted") is False
              and r.get("all_valid_enqueue_requests_failed") is True]
    covered, excluded, unresolved = [], [], []
    for row in rows:
        if row["kind"] != "provider_incident":
            continue
        resolved = row.get("resource_id") == scope["component"]
        if row.get("resource_id") is None:
            matching = [m for m in maps if m.get("incident_id") == row.get("incident_id") and interval(m) == interval(row)]
            resolved = len(matching) == 1
        if not resolved:
            unresolved.append(interval(row))
            continue
        cause = words(row.get("cause", ""))
        if any(words(label) <= cause for label in manifest.get("exclusions", [])):
            excluded.append(interval(row))
            continue
        # This semantic bridge is restricted to the ordinary public controller
        # failure rule. Other cause families remain ambiguous.
        provider = any({"provider", "dispatch", "controller"} <= words(label) for label in manifest.get("provider_causes", []))
        qualifies = provider and {"provider", "dispatch", "controller"} <= cause and bool(cause & {"failed", "failure", "fails"})
        if not qualifies or row.get("planned_maintenance") is not False:
            unresolved.append(interval(row))
            continue
        left, right = interval(row)
        if row.get("all_valid_enqueue_requests_failed") is True:
            covered.append((left, right))
        else:
            matches = [p for p in probes if p.get("incident_id") == row.get("incident_id") and p.get("incident_id") is not None
                       or interval(p) == interval(row)]
            for probe in matches:
                a, b = interval(probe)
                covered.append((max(a, left), min(b, right)))
            if not matches:
                unresolved.append((left, right))
    invoices = [r for r in rows if r["kind"] == "invoice"]
    billmaps = [r for r in rows if r["kind"] == "billing_resource_attestation" and r.get("resource_id") == scope["component"]]
    net = invoice_report(invoices[0], billmaps[0], scope) if len(invoices) == len(billmaps) == 1 else None
    return dict(status="OBSERVED_INTERVAL_FLOOR", product_result=False, exact_month=False,
                covered_seconds=seconds(covered), excluded_seconds=seconds(excluded), unresolved_seconds=seconds(unresolved),
                scoped_net_base_supported=net is not None,
                prior_amount_supported=bool(net and invoices[0].get("previously_granted_credit") == billmaps[0].get("previously_granted_credit")),
                prior_history_complete=False)
