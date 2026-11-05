"""Join independently signed monthly resource telemetry, customer cause attribution and charges."""
from datetime import timedelta
import re

from pydantic import TypeAdapter, ValidationError

from .correspondence_artifacts import HISTORICAL, SUPPLEMENTS
from .correspondence_types import Id, SOURCE, instant
from .twilio import calendar_bounds

_WIRE_ID = TypeAdapter(Id)
_BILLING_WORDS = {"invoice", "charges", "charge", "fees", "fee", "billing", "bill"}
_FEE_GRAMMAR = _BILLING_WORDS | {"a", "an", "any", "the", "of", "for", "amount", "amounts", "record", "records",
                                 "evidence", "details", "detail", "affected", "itemized", "paid", "monthly", "line", "lines"}


def _record_refs(event):
    return {event["event_id"], event["body"]["source_ref"]} if event else set()


def _fee_description(phrase):
    return set(re.findall(r"[a-z0-9]+", phrase.casefold())) - _FEE_GRAMMAR


def _aggregate_fee_refs(words, manifest, overlay, event, bindings):
    """A named fee requires its present row even when citing the whole invoice.

    The caller already verifies the signed event's scope, plan and commitment.
    Row categories retain the same exact declared semantics as the evaluator.
    """
    if not event:
        return set()
    description = words - _FEE_GRAMMAR
    excluded = {category: manifest.get("label_bindings", {}).get("fee_exclusions", {}).get(category, {}).get("phrase", category)
                for category in manifest.get("fee_exclusions", [])}
    recurring_request = bool(description & {"subscription", "recurring"}) and description <= {"subscription", "recurring", "service"}
    matches = {category for category, phrase in excluded.items() if description == _fee_description(phrase)}
    if description and not recurring_request and len(matches) != 1:
        return set()
    lines = set()
    for row in event["body"]["content"].get("lines", []):
        categories = bindings.targets('fee_exclusions', row['category']) if bindings else frozenset()
        inclusion = not excluded or bindings and bindings.targets('fee_inclusions',row['category'])
        recurring = row["ref"] == overlay["fee_line_ref"] and row["kind"] == "recurring_subscription" and not categories and inclusion
        if (not description and (recurring or categories)
                or recurring_request and recurring
                or description and not recurring_request and categories & matches):
            if re.search(r"\b(?:credit\w*|refund\w*|void\w*|revers\w*|cancel\w*)\b", row["kind"], re.I):
                return set()  # A reversal cannot establish the requested charge.
            lines.add(row["ref"])
    if description and len(lines) != 1:
        return set()  # A specific fee field does not authorize choosing a row.
    return lines | _record_refs(event) if lines else set()


def bound_filing_fields(fields, manifest, bindings):
    """Validate meaning without changing the original signed field names."""
    required = set(manifest.get('request_fields', []))
    targets = []
    for name in fields:
        meanings = bindings.resolve('request_fields', name) if bindings else frozenset()
        if len(meanings) != 1:
            raise ValueError('Filing field needs one reviewed source definition.')
        targets.extend(meanings)
    if len(targets) != len(set(targets)) or set(targets) != required:
        raise ValueError('Every required filing field must have one reviewed literal representation.')


def filing_refs(name, manifest, overlay, scope, groups, intervals, fees, bindings):
    # Ground source-defined labels using the reviewed clause, not a user-supplied
    # field type. Keep log, billing and identity evidence in separate namespaces.
    targets = bindings.resolve('request_fields', name) if bindings else frozenset()
    if len(targets) != 1:
        return set()
    target = next(iter(targets))
    label = manifest.get("label_bindings", {}).get("request_fields", {}).get(target, {}).get("phrase", target)
    words = set(re.findall(r"[a-z0-9]+", label.casefold()))
    status = groups.get("resource_status")
    invoice = groups.get("resource_invoice")
    if manifest.get("aggregate_monitor"):
        if words & _BILLING_WORDS:
            return _aggregate_fee_refs(words, manifest, overlay, groups.get("service_invoice"), bindings)
        if words & {"logs", "log", "status", "monitor", "telemetry"}:
            return _record_refs(groups.get("service_monitor"))
        if words & {"service", "product"}:
            refs = _record_refs(groups.get("service_monitor")) | _record_refs(groups.get("service_invoice"))
            # Preserve a previously usable literal ID, but do not invent an ID
            # from a display Name that the signed public wire cannot carry.
            try:
                refs.add(_WIRE_ID.validate_python(scope.service))
            except ValidationError:
                pass
            return refs
        if words & {"plan", "edition"}:
            # These are only the reports consumed by this claim's join, after
            # both signed plans have been compared exactly with the overlay.
            refs = _record_refs(groups.get("service_monitor")) | _record_refs(groups.get("service_invoice"))
            try:
                refs.add(_WIRE_ID.validate_python(overlay["plan"]))
            except ValidationError:
                pass
            return refs
    if words & _BILLING_WORDS:
        if invoice is None:
            return set()
        lines = {r["ref"] for r in fees if r.get("kind") == "resource_service"
                 and r.get("fee_line_ref") == overlay["fee_line_ref"] and r["amount_cents"] > 0}
        return lines | {scope.invoice, invoice["event_id"], invoice["body"]["source_ref"]} if lines else set()
    if words & {"valid", "validity"} and words & {"requests", "request"}:
        report = groups.get("request_evidence")
        times = {r["ref"]:r for r in intervals}
        # A scoped status witness may itself explicitly attest that valid
        # requests failed. A generic error or availability percentage cannot.
        refs = {r["ref"] for r in intervals if bindings.targets('symptoms', r['symptom']) and re.search(r"\bvalid requests?\b", r["symptom"], re.I)
                and re.search(r"\b(?:fail(?:ed|ure)?|reject(?:ed|ion)?)\b", r["symptom"], re.I)
                and not re.search(r"\b(?:no|not|never|uncertain|maybe)\b", r["symptom"], re.I)}
        for item in report["body"]["records"] if report else ():
            span = times.get(item["interval_ref"])
            observed = instant(item["requested_at"])
            if (item["resource_id"] == scope.component and span and item["valid"] and item["failed"]
                    and instant(span["start"]) <= observed < instant(span["end"])
                    and observed <= instant(report["body"]["observed_at"])):
                refs.add(item["ref"])
        return refs
    if words & {"cause", "failure", "attribution"}:
        return {r["ref"] for r in intervals if bindings.targets('provider_causes', r.get('cause', ''))}
    if words & {"logs", "log", "timestamps", "times", "intervals", "timeline", "telemetry"}:
        refs = {r["ref"] for r in intervals} | ({status["event_id"], status["body"]["source_ref"]} if status else set())
        for kind in ("customer_telemetry","provider_telemetry"):
            event = groups.get(kind)
            if event:
                refs.update(r["ref"] for r in event["body"]["records"])
        return refs
    if words & {"month", "period"}:
        return {scope.month}
    if words & {"account", "tenant", "subscriber"}:
        return {scope.account}
    if words & {"incident", "outage", "ticket"}:
        return {scope.incident}
    if words & {"region", "location"}:
        return {scope.region}
    resource_words = {"resource", "station", "component", "endpoint", "instance", "cluster", "zone"}
    resource_words.update(str(overlay.get("resource_label", "")).casefold().split())
    if words & resource_words:
        return {scope.component}
    return set()


def append_monthly_reports(facts, groups, manifest, scope, following):
    for kind, operator in (("maintenance_evidence", "maintenance"), ("prior_credit_evidence", "prior_credit")):
        if kind not in groups:
            continue
        if not manifest.get(operator):
            raise ValueError("The published contract does not define this extra monthly report.")
        report = groups[kind]["body"]
        if not report["complete"] or instant(report["observed_at"]) < following:
            raise ValueError("A complete scoped monthly statement observed after month end is required.")
        expected = dict(account=scope.account, resource_id=scope.component)
        if kind == "prior_credit_evidence":
            expected.update(agreement=scope.contract, month=scope.month, currency=scope.currency)
        refs = set()
        credit_amounts = {}
        for row in report["records"]:
            if row["ref"] in refs or any(row[k] != value for k, value in expected.items()):
                raise ValueError("Repeated or out-of-scope row on signed monthly statement.")
            refs.add(row["ref"])
            if kind == "maintenance_evidence":
                announced = row.get("announced_at")
                if ((row.get("state", "announced") == "announced") != (announced is not None)
                        or instant(row["start"]) >= instant(row["end"])
                        or announced is not None and instant(announced) > instant(report["observed_at"])
                        or instant(row["end"]) > instant(report["observed_at"])):
                    raise ValueError("Maintenance statement contains an unobserved or invalid interval.")
            else:
                previous = credit_amounts.setdefault(row["credit_id"], row["amount_cents"])
                if previous != row["amount_cents"]:
                    raise ValueError("Conflicting amounts for the same credit issuance.")
        facts[kind] = dict(verified=True, complete=True, ref=report["source_ref"], agreement=scope.contract,
                           account=scope.account, resource_id=scope.component, month=scope.month, records=report["records"])


def incident_reports(scope, groups, first, following):
    status, attribution = (groups[k]["body"] for k in ("resource_status","resource_attribution"))
    for report in (status, attribution):
        if (not report["complete"] or instant(report["start"]) != first or instant(report["end"]) != following
                or instant(report["observed_at"]) < following):
            raise ValueError("Each signed resource report must attest the completed service month.")
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
    return dict(monitor_source="simulated_vendor", monitor_ref=groups["resource_status"]["digest"],
                month_complete=True, intervals=intervals, exclusions=exclusions)


def dual_reports(scope, groups, manifest, first, following):
    identity = dict(account=scope.account, product=scope.service, region=scope.region, resource_id=scope.component)
    audience = dict(**identity, agreement=scope.contract, month=scope.month)
    facts = dict(region=scope.region, intervals=[], exclusions=[])
    customer, provider = (groups[k] for k in ("customer_telemetry","provider_telemetry"))
    if customer["subject"] == provider["subject"]:
        raise ValueError("The two telemetry reports require independent signing identities.")
    for event in (customer, provider):
        body = event["body"]
        if (not body["complete"] or instant(body["start"]) != first or instant(body["end"]) != following
                or instant(body["observed_at"]) < following):
            raise ValueError("Each independent monitor must attest the complete service month.")
        for row in body["records"]:
            if (any(row[k] != value for k,value in identity.items()) or instant(row["start"]) >= instant(row["end"])
                    or instant(row["end"]) > instant(body["observed_at"])):
                raise ValueError("Unscoped, reversed, or future monitor observation.")
        facts[event["kind"]] = dict(**audience, verified=True, complete=True, ref=body["source_ref"], source_id=body["source_id"],
                                    records=body["records"], no_events_verified=body.get("no_events_verified",False))
    body = customer["body"]
    if manifest.get("exclusions") and not body.get("exclusions_complete"):
        raise ValueError("Customer must attest the relevant cause exclusions before pricing the intersecting monitors.")
    for row in body.get("exclusions", []):
        if row["resource_id"] != scope.component or instant(row["end"]) > instant(body["observed_at"]):
            raise ValueError("Unverified exclusion scope or timing.")
        facts["exclusions"].append(dict(row, **audience, verified=True))
    if manifest["telemetry"].get("custodian"):
        custodian = groups.get("custodian_attestation")
        if (not custodian or custodian["subject"] in {customer["subject"], provider["subject"]}
                or custodian["body"]["source_id"] != body["source_id"] or custodian["body"]["monitor_ref"] != body["source_ref"]
                or instant(custodian["body"]["observed_at"]) < instant(body["observed_at"])):
            raise ValueError("A separately signed custodian attestation must identify the actual customer monitoring system and report.")
        facts["customer_telemetry"]["custodian"] = dict(**identity, verified=True, signed=True,
                                                        source_id=body["source_id"], ref=custodian["body"]["source_ref"])
    return facts


def join_resource(scope, events, manifest, overlay, filed, receipts=(), *, bindings=None):
    groups = {}
    for event in events:
        kind = event["kind"]
        if kind in SUPPLEMENTS:
            continue
        if SOURCE.get(kind) != event["source"] or kind in groups:
            raise ValueError("Conflicting or unauthenticated resource evidence.")
        groups[kind] = event
    dual = bool(manifest.get("telemetry"))
    required = {"customer_telemetry","provider_telemetry","resource_invoice"} if dual else {"resource_status","resource_attribution","resource_invoice"}
    if missing := required - groups.keys():
        raise ValueError("Awaiting signed " + ", ".join(sorted(missing)) + ".")
    if groups.keys() - required - HISTORICAL - {"billing_calendar","filing_material","request_evidence","custodian_attestation","portal_response_receipt","account_conditions","maintenance_evidence","prior_credit_evidence"}:
        raise ValueError("Evidence outside the active resource profile requires review.")
    if overlay["resource_id"] != scope.component:
        raise ValueError("Resource differs from the reviewed customer and contract mapping.")
    first, following = calendar_bounds(instant(scope.month+"-01T00:00:00Z").date(), "UTC")
    telemetry = dual_reports(scope, groups, manifest, first, following) if dual else incident_reports(scope, groups, first, following)
    intervals = telemetry["intervals"]
    invoice = groups["resource_invoice"]["body"]
    if instant(invoice["observed_at"]) < following:
        raise ValueError("An invoice observed before month end cannot attest complete monthly charges.")
    fees = []
    for row in invoice["lines"]:
        if manifest.get("fee_exclusions") and row["kind"] == "resource_service" and not row.get("category"):
            raise ValueError("A cited fee exclusion requires classified resource-service charges.")
        if (row["resource_id"] != scope.component or row["month"] != scope.month or row["currency"] != scope.currency
                or row.get("region",scope.region) != scope.region or row.get("product",scope.service) != scope.service):
            raise ValueError("An itemized charge contradicts the scoped resource, month or currency.")
        fees.append({**row, "account":scope.account})
    facts = dict(agreement=scope.contract, account=scope.account, product=scope.service, plan=overlay["plan"],
                 resource_id=scope.component, month=scope.month, received_at=filed.isoformat(),
                 **telemetry,
                 fee_lines=fees, fee_line_ref=overlay["fee_line_ref"],itemized_complete=invoice["itemized_complete"],
                 fee_ref=groups["resource_invoice"]["digest"])
    append_monthly_reports(facts, groups, manifest, scope, following)
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
        if len(fields) != len(body["fields"]):
            raise ValueError("Every required filing field must appear exactly once.")
        bound_filing_fields(fields, manifest, bindings)
        for name, values in fields.items():
            allowed = filing_refs(name, manifest, overlay, scope, groups, intervals, fees, bindings)
            if not allowed or len(values) != len(set(values)) or set(values) - allowed:
                raise ValueError("Filing field references must match the kind of scoped evidence its clause requires.")
        # This is a checked prospective local packet. The inbox records actual
        # submission only after approval; no provider receipt is synthesized.
        filing = dict(channel=channel, fields=fields, material_digest=material["digest"])
        facts["filing_proof"] = dict(verified=True, ref=material["digest"], account=scope.account, resource_id=scope.component,
                                     submitted_to=channel, fields={k:", ".join(v) for k,v in fields.items()})
        historical = groups.keys() & HISTORICAL
        if historical:
            if receipts and (len(receipts) != 1 or receipts[0]["packet"].get("purpose") != "procedural_evidence_only"):
                raise ValueError("Local original filings conflict with imported existing submission receipts.")
            initial = groups.get("original_filing_receipt")
            if not initial:
                raise ValueError("Awaiting the independently observed original filing receipt.")
            def corroborate(event):
                item = event["body"]
                listed = {field["name"]:field["refs"] for field in item["fields"]}
                if (len(listed) != len(item["fields"]) or item["submitted_to"] != channel
                        or any(fields.get(name) != refs for name,refs in listed.items())):
                    raise ValueError("Receipt contents and prior customer filing material do not agree.")
                return dict(verified=True, ref=item["receipt_id"], submitted_to=channel,
                            fields={name:", ".join(refs) for name,refs in listed.items()},
                            account=scope.account, resource_id=scope.component, agreement=scope.contract, product=scope.service,
                            region=scope.region, month=scope.month, ticket_id=item.get("ticket_id"), received_at=item["received_at"])
            facts["filing_proof"] = corroborate(initial)
            facts["received_at"] = initial["body"]["received_at"]
            if followup := groups.get("supplement_filing_receipt"):
                item = followup["body"]
                facts["filing_proof"]["supplements"] = [dict(corroborate(followup), original_ref=item["original_ref"],
                    month=scope.month, agreement=scope.contract, received_at=item["received_at"], response_ref=item.get("response_ref"))]
        if historical and receipts:
            response = receipts[0]
            packet = response["packet"]
            if followup or packet.get("in_reply_to") != initial["body"]["receipt_id"]:
                raise ValueError("Competing follow-ups or a mismatched original require review.")
            if (manifest.get("supplement") or manifest.get("cure_clock")) and (response_material := packet.get("filing_material")):
                facts["filing_proof"]["supplements"] = [dict(verified=True, ref=response["id"], original_ref=packet["in_reply_to"],
                    month=scope.month, agreement=scope.contract, received_at=response["at"], account=scope.account,
                    resource_id=scope.component, product=scope.service, region=scope.region, submitted_to=response_material["channel"],
                    ticket_id=packet.get("ticket_id"), response_ref=packet.get("response_ref"),
                    fields={k:", ".join(v) for k,v in response_material["fields"].items()})]
        if receipts and not historical:
            original = receipts[0]
            original_material = original["packet"].get("filing_material")
            if not original_material or original_material != filing:
                raise ValueError("The signed filing material differs from the original approved submission.")
            facts["filing_proof"]["ref"] = original["id"]
            if len(receipts) > 1 and manifest.get("supplement"):
                response = receipts[1]
                response_material = response["packet"].get("filing_material")
                if not response_material or response["packet"].get("in_reply_to") != original["id"]:
                    raise ValueError("Supplement lacks its scoped original filing chain.")
                facts["filing_proof"]["supplements"] = [dict(
                    verified=True, ref=response["id"], original_ref=original["id"], agreement=scope.contract,
                    account=scope.account, resource_id=scope.component, month=scope.month, received_at=response["at"],
                    submitted_to=response_material["channel"], fields={k:", ".join(v) for k,v in response_material["fields"].items()})]
    if manifest.get("original_receipt") and not groups.get("original_filing_receipt"):
        raise ValueError("A separately signed provider portal arrival receipt is required for this contract.")
    if portal := groups.get("portal_response_receipt"):
        item = portal["body"]
        original = groups.get("original_filing_receipt")
        if (not original or item["original_ref"] != original["body"]["receipt_id"]
                or item["ticket_id"] != original["body"].get("ticket_id")
                or instant(item["delivered_at"]) < instant(original["body"]["received_at"])):
            raise ValueError("The provider response does not belong to the original ticket and chronology.")
        facts["filing_proof"]["response_receipt"] = dict(verified=True, ref=item["source_ref"], account=scope.account,
            agreement=scope.contract, product=scope.service, region=scope.region, resource_id=scope.component,
            month=scope.month, ticket_id=item["ticket_id"], kind=item["response_kind"], delivered_at=item["delivered_at"])
    return facts, filing


def exclusive_cutoff(result):
    if not result.get("claim_cutoff"):
        return None
    cutoff = instant(result["claim_cutoff"])
    return cutoff + timedelta(microseconds=1) if result.get("cutoff_inclusive") else cutoff
