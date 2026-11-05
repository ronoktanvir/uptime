"""Join independently signed monthly resource telemetry, customer cause attribution and charges."""
from datetime import timedelta
import re

from .correspondence_artifacts import SUPPLEMENTS
from .correspondence_types import SOURCE, instant
from .twilio import calendar_bounds


def filing_refs(name, manifest, overlay, scope, groups, intervals, fees):
    # Ground source-defined labels using the reviewed clause, not a user-supplied
    # field type. Keep log, billing and identity evidence in separate namespaces.
    label = manifest.get("label_bindings", {}).get("request_fields", {}).get(name, {}).get("phrase", name)
    words = set(re.findall(r"[a-z0-9]+", label.casefold()))
    status = groups["resource_status"]
    invoice = groups["resource_invoice"]
    matches = []
    if words & {"logs", "log", "timestamps", "times", "intervals", "timeline", "telemetry"}:
        matches.append({status["event_id"], status["body"]["source_ref"], *(r["ref"] for r in intervals)})
    if words & {"invoice", "charges", "fees", "billing", "bill"}:
        matches.append({scope.invoice, invoice["event_id"], invoice["body"]["source_ref"], *(r["ref"] for r in fees)})
    if words & {"account", "tenant", "subscriber"}:
        matches.append({scope.account})
    if words & {"incident", "outage", "ticket"}:
        matches.append({scope.incident})
    if words & {"region", "location"}:
        matches.append({scope.region})
    resource_words = {"resource", "station", "component", "endpoint", "instance", "cluster", "zone"}
    resource_words.update(str(overlay.get("resource_label", "")).casefold().split())
    if words & resource_words:
        matches.append({scope.component})
    return matches[0] if len(matches) == 1 else set()


def join_resource(scope, events, manifest, overlay, filed):
    groups = {}
    for event in events:
        kind = event["kind"]
        if kind in SUPPLEMENTS:
            continue
        if SOURCE.get(kind) != event["source"] or kind in groups:
            raise ValueError("Conflicting or unauthenticated resource evidence.")
        groups[kind] = event
    required = {"resource_status","resource_attribution","resource_invoice"}
    if missing := required - groups.keys():
        raise ValueError("Awaiting signed " + ", ".join(sorted(missing)) + ".")
    if groups.keys() - required - {"billing_calendar","filing_material","account_conditions"}:
        raise ValueError("Evidence outside the active resource profile requires review.")
    if overlay["resource_id"] != scope.component:
        raise ValueError("Resource differs from the reviewed customer and contract mapping.")
    status, attribution, invoice = (groups[k]["body"] for k in ("resource_status","resource_attribution","resource_invoice"))
    first, following = calendar_bounds(instant(scope.month+"-01T00:00:00Z").date(), "UTC")
    for report in (status, attribution):
        if (not report["complete"] or instant(report["start"]) != first or instant(report["end"]) != following
                or instant(report["observed_at"]) < following):
            raise ValueError("Each signed resource report must attest the completed service month.")
    if instant(invoice["observed_at"]) < following:
        raise ValueError("An invoice observed before month end cannot attest complete monthly charges.")
    by_ref = {r["ref"]:r for r in attribution["causes"]}
    if len(by_ref) != len(attribution["causes"]) or len({r["ref"] for r in status["intervals"]}) != len(status["intervals"]):
        raise ValueError("Duplicate or conflicting resource observation identities.")
    intervals = []
    for row in status["intervals"]:
        cause = by_ref.pop(row["ref"], None)
        if (not cause or row["resource_id"] != scope.component
                or any(row[k] != cause[k] for k in ("resource_id","start","end"))
                or instant(row["end"]) <= instant(row["start"]) or instant(row["end"]) > instant(status["observed_at"])):
            raise ValueError("A dated service observation and customer cause must identify the same resource and interval.")
        intervals.append({**row, "account":scope.account, "cause":cause["cause"]})
    if by_ref:
        raise ValueError("An attribution refers to an unverified service observation.")
    exclusions = []
    for row in attribution["exclusions"]:
        if (row["resource_id"] != scope.component or instant(row["end"]) <= instant(row["start"])
                or instant(row["end"]) > instant(attribution["observed_at"])):
            raise ValueError("An exclusion is outside the scoped resource or observation clock.")
        exclusions.append({**row, "account":scope.account})
    fees = []
    for row in invoice["lines"]:
        if manifest.get("fee_exclusions") and row["kind"] == "resource_service" and not row.get("category"):
            raise ValueError("A cited fee exclusion requires classified resource-service charges.")
        if row["resource_id"] != scope.component or row["month"] != scope.month or row["currency"] != scope.currency:
            raise ValueError("An itemized charge contradicts the scoped resource, month or currency.")
        fees.append({**row, "account":scope.account})
    facts = dict(agreement=scope.contract, account=scope.account, product=scope.service, plan=overlay["plan"],
                 resource_id=scope.component, month=scope.month, received_at=filed.isoformat(),
                 monitor_source="simulated_vendor",monitor_ref=groups["resource_status"]["digest"],
                 month_complete=status["complete"] and attribution["complete"],intervals=intervals,exclusions=exclusions,
                 fee_lines=fees, fee_line_ref=overlay["fee_line_ref"],itemized_complete=invoice["itemized_complete"],
                 fee_ref=groups["resource_invoice"]["digest"])
    if "account_conditions" in groups:
        report = groups["account_conditions"]["body"]
        required = {c["op"] for c in manifest.get("account_conditions", [])}
        supplied = [c["op"] for c in report["findings"]]
        if set(supplied) != required or len(supplied) != len(required) or instant(report["observed_at"]) < following:
            raise ValueError("Account condition findings must cover each published predicate and complete service month.")
        facts["condition_evidence"] = []
        for finding in report["findings"]:
            row = dict(agreement=scope.contract, account=scope.account, resource_id=scope.component, month=scope.month,
                       verified=True, **{k:finding[k] for k in ("op","ref","finding","affected_refs")})
            terms = finding.get("reviewed_terms")
            if terms:
                row.update(terms_reviewed=True, terms_ref=terms["ref"], terms_sha256=terms["sha256"])
            facts["condition_evidence"].append(row)
    if "billing_calendar" in groups:
        cycles = groups["billing_calendar"]["body"]["cycles"]
        if len({r["ref"] for r in cycles}) != len(cycles):
            raise ValueError("Billing cycle references must be distinct.")
        facts["billing_cycles"] = cycles
    filing = None
    if manifest.get("request_fields") or manifest.get("submission_channel"):
        material = groups.get("filing_material")
        if not material:
            raise ValueError("The published request fields and local filing channel require signed filing material.")
        body = material["body"]
        channel = manifest.get("submission_channel")
        if channel and body["channel"] != channel:
            raise ValueError("The local packet channel differs from the reviewed contract.")
        fields = {r["name"]:r["refs"] for r in body["fields"]}
        if (set(fields) != set(manifest.get("request_fields", [])) or len(fields) != len(body["fields"])):
            raise ValueError("Every required filing field must appear exactly once.")
        for name, values in fields.items():
            allowed = filing_refs(name, manifest, overlay, scope, groups, intervals, fees)
            if not allowed or len(values) != len(set(values)) or set(values) - allowed:
                raise ValueError("Filing field references must match the kind of scoped evidence its clause requires.")
        # This is a checked prospective local packet. The inbox records actual
        # submission only after approval; no provider receipt is synthesized.
        filing = dict(channel=channel, fields=fields, material_digest=material["digest"])
        facts["filing_proof"] = dict(verified=True, ref=material["digest"], account=scope.account, resource_id=scope.component,
                                     submitted_to=channel, fields={k:", ".join(v) for k,v in fields.items()})
    return facts, filing


def exclusive_cutoff(result):
    if not result.get("claim_cutoff"):
        return None
    cutoff = instant(result["claim_cutoff"])
    return cutoff + timedelta(microseconds=1) if result.get("cutoff_inclusive") else cutoff
