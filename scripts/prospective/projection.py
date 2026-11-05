"""Lossless local witness mappings, independent of the application evaluator.

An input hash proves frozen byte integrity, not provider confirmation. Missing
completeness and filing attestations stay missing. All generated references are
local aliases; none are presented as provider identifiers.
"""
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
import re


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode())


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("An explicit UTC timestamp is required")
    return parsed


def exact_number(value, scale=1):
    """Never truncate fractional minutes or round invoice amounts to fit a schema."""
    number = Decimal(str(value)) * scale
    if not number.is_finite():
        raise ValueError("Nonfinite evidence number")
    return int(number) if number == number.to_integral_value() else str(number)


def public_join(private, text, receipt):
    """Map a version to its exact public title, never invent a private contract ID."""
    if receipt.get("source_sha256") != sha(text.encode()):
        raise ValueError("Public receipt/source digest mismatch")
    if receipt.get("proposal_sha256") != fingerprint(receipt.get("proposal")):
        raise ValueError("Public proposal digest mismatch")
    versions = re.findall(r"(?im)^\s*(?:Version|Revision)\s+([A-Za-z0-9][A-Za-z0-9_.-]*?)[.]?(?=\s|$)", text)
    if versions != [private["public_sla_version"]]:
        raise ValueError("Supplied agreement version does not join one exact public source version")
    values = {}
    for row in receipt["proposal"]:
        quote = row.get("quote", "")
        if not quote or text.count(quote) != 1:
            raise ValueError("Public proposition must identify one exact source span")
        for key in ("agreement", "scope", "fixed_period"):
            if not isinstance(row.get("value"), dict) or key not in row["value"]:
                continue
            value = row["value"][key]
            if key in values and values[key]["value"] != value:
                raise ValueError("Conflicting public identity propositions")
            values[key] = {"value": value, "quote": quote, "start": text.index(quote)}
    if not values.get("agreement") or values["agreement"]["value"] not in values["agreement"]["quote"]:
        raise ValueError("No exact public agreement title")
    scope = values.get("scope", {}).get("value", {})
    if scope != {"product": private["service"], "plan": private["plan"]}:
        raise ValueError("Private service/plan differs from the public scope")
    if any(v not in values["scope"]["quote"] for v in scope.values()):
        raise ValueError("Public service/plan is not literal source text")
    period = values.get("fixed_period", {}).get("value", {})
    if any(instant(private["period"][k]) != instant(period[k]) for k in ("start", "end")):
        raise ValueError("Private period differs from the exact public service month")
    duration = (instant(period["end"]) - instant(period["start"])).total_seconds() / 60
    if Decimal(private["period"]["minutes"]) != Decimal(str(duration)):
        raise ValueError("Frozen input denominator contradicts its service period")
    return {"public_agreement": values["agreement"]["value"],
            "source_version": versions[0], "source_sha256": receipt["source_sha256"],
            "evidence": values, "kind": "EXACT_PUBLIC_VERSION_TITLE_JOIN",
            "provider_confirmed_private_identity": False}


def overlay_for(private, join):
    return {"agreement": private["public_sla_version"], "public_agreement": join["public_agreement"],
            "account": private["account_id"], "product": private["service"], "plan": private["plan"],
            "effective_from": instant(private["period"]["start"]).date().isoformat(),
            "effective_until": (instant(private["period"]["end"]) - timedelta(days=1)).date().isoformat(),
            "fee_line_ref": "witness-subscription-line", "currency": "USD"}


def category_key(value):
    # Only fee/charge suffix morphology is normalized. No semantic synonym table.
    return " ".join(re.sub(r"\b(?:fees?|charges?)\b", "", value.casefold()).split())


def project_case(base, case, overlay, manifest, frozen_files):
    scope = {key: overlay[key] for key in ("agreement", "account", "product", "plan")}
    scope["month"] = case["period"]["start"][:7]
    facts = dict(scope, fee_line_ref=overlay["fee_line_ref"], received_at=case["filing_at"])
    issues, provenance = [], []
    period = manifest["fixed_period"]
    duration = (instant(case["period"]["end"]) - instant(case["period"]["start"])).total_seconds() / 60
    if (any(instant(case["period"][k]) != instant(period[k]) for k in ("start", "end"))
            or Decimal(case["period"]["minutes"]) != Decimal(str(duration))):
        raise ValueError("Case period/denominator does not join the public month")
    for name, field in (("service_monitor", "status_path"), ("service_invoice", "invoice_path")):
        relative = case.get(field)
        if not relative:
            issues.append({"record": name, "code": "MISSING_ORIGINAL_RECORD"})
            continue
        path = (base / relative).resolve()
        if not path.is_relative_to(base.resolve()) or relative not in frozen_files:
            raise ValueError("Record is outside the frozen input manifest")
        raw = path.read_bytes()
        if sha(raw) != frozen_files[relative]:
            raise ValueError("Frozen source record changed")
        original = json.loads(raw)
        verifiable = bool(original.get("source_id") and original.get("recorded_at"))
        complete = original.get("complete", original.get("itemized_complete") if name == "service_invoice"
                                else original.get("month_complete"))
        if complete is not True:
            issues.append({"record": name, "code": "MISSING_COMPLETE_ATTESTATION" if complete is None else "INCOMPLETE_RECORD"})
        # Preserve contradictory source identities instead of laundering them through the overlay.
        record_scope = {"agreement": original.get("agreement", overlay["agreement"]),
                        "account": original.get("account_id"), "product": original.get("service"),
                        "plan": original.get("plan"), "month": original.get("period", {}).get("start", "")[:7]}
        if (record_scope != scope or any(original.get("period", {}).get(k) != case["period"][k]
                                         for k in ("start", "end", "minutes"))):
            issues.append({"record": name, "code": "SOURCE_SCOPE_MISMATCH"})
            verifiable = False
        try:
            if not instant(period["end"]) <= instant(original["recorded_at"]) <= instant(case["filing_at"]):
                raise ValueError("Record unavailable at the stated filing time")
        except (KeyError, TypeError, ValueError):
            issues.append({"record": name, "code": "SOURCE_CHRONOLOGY_GAP"})
            verifiable = False
        if name == "service_monitor":
            down = exact_number(original["unavailable_minutes"])
            content = {"source": "simulated_vendor", "unavailable_minutes": down}
            if not isinstance(down, int):
                issues.append({"record": name, "code": "FRACTIONAL_MINUTES_UNSUPPORTED"})
        else:
            lines = []
            subscription_count = 0
            for index, line in enumerate(original["lines"]):
                recurring = (line.get("service") == overlay["product"]
                             and re.search(r"\bsubscription\b", line.get("description", ""), re.I))
                category = line.get("category", line.get("description", ""))
                exclusions = [v for v in manifest.get("fee_exclusions", []) if category_key(v) == category_key(category)]
                if len(exclusions) == 1:
                    category = exclusions[0]
                subscription_count += bool(recurring)
                ref = overlay["fee_line_ref"] if recurring and subscription_count == 1 else f"witness-line-{index + 1}"
                amount = exact_number(line["amount_usd"], 100)
                lines.append({"ref": line.get("ref", ref), "kind": line.get("kind", "recurring_subscription" if recurring else "unclassified"),
                              "category": "subscription" if recurring and "category" not in line else category,
                              "amount_cents": amount})
                if not recurring and not exclusions:
                    issues.append({"record": name, "code": "UNCLASSIFIED_FEE", "line_index": index})
                if not isinstance(amount, int):
                    issues.append({"record": name, "code": "FRACTIONAL_CENT_UNSUPPORTED", "line_index": index})
            if subscription_count != 1 or sum(line["ref"] == overlay["fee_line_ref"] for line in lines) != 1:
                issues.append({"record": name, "code": "AMBIGUOUS_SUBSCRIPTION_LINE"})
                verifiable = False
            if len({line["ref"] for line in lines}) != len(lines):
                issues.append({"record": name, "code": "DUPLICATE_LINE_REF"})
                verifiable = False
            subscription_total = sum(Decimal(str(line["amount_cents"])) for line in lines
                                     if line["kind"] == "recurring_subscription")
            if ("monthly_subscription_usd" in original
                    and Decimal(original["monthly_subscription_usd"]) * 100 != subscription_total):
                issues.append({"record": name, "code": "SOURCE_FEE_SUMMARY_MISMATCH"})
                verifiable = False
            content = {"paid": original.get("paid"), "currency": original.get("currency", "USD"), "lines": lines}
        # The flag authenticates the frozen local record only. Completeness remains separate.
        facts[name] = dict(record_scope, ref=original.get("source_id"), recorded_at=original.get("recorded_at"),
                           verified=verifiable, complete=complete is True,
                           content=content, content_sha256=fingerprint(content))
        provenance.append({"record": name, "original_path": str(path), "original_sha256": sha(raw),
                           "projected_content_sha256": fingerprint(content), "local_aliases_only": True,
                           "verification": "FROZEN_LOCAL_SYNTHETIC_BYTE_INTEGRITY", "provider_confirmed": False})
    if case.get("filing_proof"):
        facts["filing_proof"] = case["filing_proof"]
    else:
        issues.append({"record": "filing_proof", "code": "MISSING_ORIGINAL_FILING_RECEIPT"})
    return {"facts": facts, "issues": issues, "provenance": provenance,
            "denominator_minutes": case["period"]["minutes"], "original_scenario": True}
