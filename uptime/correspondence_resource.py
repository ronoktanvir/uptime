"""Join independently signed monthly resource telemetry, customer cause attribution and charges."""
from datetime import timedelta

from .correspondence_artifacts import SUPPLEMENTS
from .correspondence_types import SOURCE, instant
from .twilio import calendar_bounds


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
    if groups.keys() - required - {"billing_calendar","filing_material"}:
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
        refs = {scope.component,scope.account,scope.invoice,scope.incident}
        refs.update(e["event_id"] for e in groups.values() if e is not material)
        refs.update(e["body"]["source_ref"] for e in groups.values() if e is not material)
        refs.update(r["ref"] for r in intervals+exclusions+fees)
        fields = {r["name"]:r["refs"] for r in body["fields"]}
        if (set(fields) != set(manifest.get("request_fields", [])) or len(fields) != len(body["fields"])
                or any(set(values)-refs for values in fields.values())):
            raise ValueError("Every required field must reference a verified resource, source or line in this case.")
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
