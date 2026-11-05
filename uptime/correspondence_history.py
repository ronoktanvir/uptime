"""Corroborate an independently observed filing without manufacturing a local initial submission."""
from .correspondence_artifacts import HISTORICAL
from .correspondence_types import instant


def receipts_by_kind(state):
    result = {}
    for event in state["evidence"]:
        kind = event["kind"]
        if kind in HISTORICAL:
            if kind in result:
                raise ValueError("Conflicting historical receipts require manual review.")
            result[kind] = event
    return result


def receipt_chain(state):
    receipts = receipts_by_kind(state)
    initial = receipts.get("original_filing_receipt")
    supplement = receipts.get("supplement_filing_receipt")
    if not initial:
        return None
    first = initial["body"]
    if supplement:
        following = supplement["body"]
        if (following["original_ref"] != first["receipt_id"] or following["submitted_to"] != first["submitted_to"]
                or instant(following["received_at"]) < instant(first["received_at"])):
            raise ValueError("Historical supplement conflicts with the original receipt, channel or chronology.")
    return initial, supplement


def historical_reply(state, fact, now, proposal):
    # The original packet was independently observed. Only the local dispatch
    # path may write a submission, and only independent financial evidence can
    # establish an award. An internal interpretation carries neither authority.
    chain = receipt_chain(state)
    if not chain:
        raise ValueError("Awaiting the independently observed original before processing its reply.")
    original, _ = chain
    state["reason"] = proposal.reason
    state["stage"] = "HUMAN_REVIEW"
    return dict(reason=proposal.reason, span=proposal.span, event_id=fact["event_id"],
                digest=fact["digest"], receipt=fact["body"]["receipt_id"], original_receipt=original["body"]["receipt_id"],
                received_at=now.isoformat(), filing_source="observed")


def procedure(scope, events, manifest, overlay):
    """Establish only receipt chronology and concrete filed/missing items, never month coverage or price."""
    from datetime import timedelta
    from .correspondence_resource import filing_refs
    from .correspondence_types import SOURCE
    from .twilio import calendar_bounds
    from .vendor_resource_eval import deadline
    groups = {}
    relevant = HISTORICAL | {"filing_material","request_evidence","resource_invoice","resource_status",
                             "resource_attribution","billing_calendar","customer_telemetry","provider_telemetry","custodian_attestation","portal_response_receipt"}
    for event in events:
        kind = event["kind"]
        if kind not in relevant:
            continue
        if kind in groups or SOURCE[kind] != event["source"]:
            raise ValueError("Conflicting procedural evidence.")
        groups[kind] = event
    chain = receipt_chain({"evidence":events})
    if not chain:
        return None
    original, supplement = chain
    first, following = calendar_bounds(instant(scope.month + "-01T00:00:00Z").date(), "UTC")
    calendar = groups.get("billing_calendar")
    cutoff, inclusive = deadline({"billing_cycles":calendar["body"]["cycles"]} if calendar else {}, overlay, manifest, following)
    cutoff += timedelta(microseconds=int(inclusive))
    channel = manifest.get("submission_channel")
    if not channel or original["body"]["submitted_to"] != channel or instant(original["body"]["received_at"]) < following:
        raise ValueError("Historical receipt does not establish the reviewed destination or completed service period.")
    expected = set(manifest.get("request_fields", []))
    if manifest.get("subscription"):
        from .vendor_resource_scopes import subscription
        subscription(dict(region=scope.region), overlay, manifest, first, following)
    received = {}
    initial_fields = {field["name"] for field in original["body"]["fields"]}
    if manifest.get("cure_clock") and not set(manifest["cure_clock"]["initial_fields"]) <= initial_fields:
        raise ValueError("Required original ticket fields were missing at the initial deadline.")
    response = groups.get("portal_response_receipt")
    response_cutoff = None
    if manifest.get("cure_clock"):
        if response:
            from .vendor_resource_scopes import supplement_clock
            original_body, reply = original["body"], response["body"]
            if reply["original_ref"] != original_body["receipt_id"]:
                raise ValueError("Portal response belongs to a different original filing.")
            identity = dict(account=scope.account, agreement=scope.contract, product=scope.service, region=scope.region,
                            resource_id=scope.component, month=scope.month)
            verified = dict(**identity, verified=True, ref=reply["source_ref"], ticket_id=reply["ticket_id"],
                            kind=reply["response_kind"], delivered_at=reply["delivered_at"])
            proof = dict(ticket_id=original_body.get("ticket_id"), ref=original_body["receipt_id"], response_receipt=verified)
            followup = dict(ticket_id=proof["ticket_id"], response_ref=reply["source_ref"], received_at=reply["delivered_at"])
            value, inclusive = supplement_clock(dict(region=scope.region,month=scope.month), overlay, manifest, proof,
                                                 followup, instant(original_body["received_at"]))
            response_cutoff = (value + timedelta(microseconds=int(inclusive))).isoformat()
        elif supplement:
            raise ValueError("Portal supplement requires the separate response-delivery receipt.")
    received = {}
    for event in filter(None, (original, supplement)):
        if len({f["name"] for f in event["body"]["fields"]}) != len(event["body"]["fields"]):
            raise ValueError("A receipt contains repeated field names.")
        for field in event["body"]["fields"]:
            name, refs = field["name"], field["refs"]
            if name not in expected or name in received and received[name] != refs:
                raise ValueError("Unexpected or contradictory filing item in a historical receipt.")
            received[name] = refs
    material = groups.get("filing_material")
    available = {}
    if material:
        candidate = material["body"]
        if candidate["channel"] != channel or len({f["name"] for f in candidate["fields"]}) != len(candidate["fields"]):
            raise ValueError("Customer filing material contradicts the active procedure.")
        status = groups.get("resource_status",{}).get("body",{}).get("intervals", [])
        causes = groups.get("resource_attribution",{}).get("body",{}).get("causes", [])
        by_ref = {r["ref"]:r for r in causes}
        if len(by_ref) != len(causes) or len({r["ref"] for r in status}) != len(status):
            raise ValueError("Duplicate incident evidence prevents a factual cure.")
        intervals = []
        for row in status:
            cause = by_ref.get(row["ref"])
            if (row["resource_id"] != scope.component or not first <= instant(row["start"]) < instant(row["end"]) <= following):
                raise ValueError("Event-level service records mismatch the account, resource or period.")
            if cause and any(cause[k] != row[k] for k in ("start","end","resource_id")):
                raise ValueError("Customer attribution conflicts with the status incident.")
            intervals.append(dict(row, cause=cause["cause"] if cause else ""))
        for kind in ("customer_telemetry","provider_telemetry"):
            report = groups.get(kind)
            if report:
                body = report["body"]
                if any(r["account"] != scope.account or r["product"] != scope.service or r["region"] != scope.region
                       or r["resource_id"] != scope.component or instant(r["end"]) > instant(body["observed_at"])
                       or not first <= instant(r["start"]) < instant(r["end"]) <= following for r in body["records"]):
                    raise ValueError("Monitor records do not support the filing's source scope.")
                if kind == "customer_telemetry" and manifest.get("telemetry",{}).get("custodian"):
                    custody = groups.get("custodian_attestation")
                    if (not custody or custody["subject"] == report["subject"]
                            or custody["body"]["monitor_ref"] != body["source_ref"]
                            or custody["body"]["source_id"] != body["source_id"]
                            or instant(custody["body"]["observed_at"]) < instant(body["observed_at"])):
                        raise ValueError("Customer logs require the signed independent custodian.")
        invoice = groups.get("resource_invoice",{}).get("body",{})
        fees = invoice.get("lines", [])
        if any(r["resource_id"] != scope.component or r["currency"] != scope.currency or r["month"] != scope.month for r in fees):
            raise ValueError("Statement does not corroborate the contemplated filing resource.")
        for field in candidate["fields"]:
            name, refs = field["name"], field["refs"]
            if name not in expected or name in received and received[name] != refs:
                raise ValueError("Signed customer and vendor statements conflict about an item.")
            if len(set(refs)) == len(refs) and set(refs) <= filing_refs(name, manifest, overlay, scope, groups, intervals, fees):
                available[name] = refs
    return dict(original=original["body"]["receipt_id"], original_digest=original["digest"], filed_at=original["body"]["received_at"],
                last=(supplement or original)["body"]["receipt_id"], supplemented=bool(supplement), channel=channel,
                cutoff=cutoff.isoformat(), response_cutoff=response_cutoff, response_ref=response["body"]["source_ref"] if response else None,
                response_message_ref=response["body"]["message_ref"] if response else None,
                ticket_id=original["body"].get("ticket_id"), can_supplement=bool(response_cutoff) or manifest.get("supplement") == "same_filing_deadline",
                missing=sorted(expected - received.keys()), available=available,
                source_digests=sorted(e["digest"] for e in groups.values()))


def response_material(state, current):
    """A verified procedural correction can carry evidence; its monetary request is always zero."""
    info = current.procedure
    if (not info or not state["replies"] or state["submissions"] or info["supplemented"]
            or not info["can_supplement"] or instant(info["filed_at"]) >= instant(info["cutoff"])):
        return None
    reply = state["replies"][-1]
    if (reply["receipt"] != info["last"]
            or info.get("response_cutoff") and info["response_message_ref"] != reply["event_id"]):
        return None
    if reply["reason"] == "time_bar":
        return dict(argument="The independently authenticated original filing receipt predates the published cutoff.",
                    verified_original_at=info["filed_at"])
    requested = set(reply.get("requested_fields", []))
    if requested and requested <= info["available"].keys():
        return dict(argument="Source records corroborate the requested filing items for this resource and month.",
                    filing_material=dict(channel=info["channel"], fields={k:info["available"][k] for k in sorted(requested)}))
    return None


def apply_response_state(state, current):
    reply = state["replies"][-1]
    if current.procedure and reply["reason"] in {"component", "artifact", "unknown"}:
        from .correspondence_reason import requested_filing_fields
        message = next(e["body"]["text"] for e in state["evidence"] if e["digest"] == reply["digest"])
        requested = requested_filing_fields(message, current.procedure["missing"])
        if requested:
            reply.update(reason="filing_fields", requested_fields=requested)
            state["reason"] = "filing_fields"
    state["approval"] = None
    if state["submissions"] or not current.procedure:
        state["stage"] = "HUMAN_REVIEW"
    elif response_material(state, current):
        state["stage"] = "RESPONSE_DRAFTED"
    elif reply.get("requested_fields") and not current.procedure["supplemented"]:
        state["stage"] = "NEEDS_EVIDENCE"
    elif reply["reason"] == "time_bar" and instant(current.procedure["filed_at"]) >= instant(current.procedure["cutoff"]):
        state["stage"] = "DENIAL_ACCEPTED"
    elif reply["reason"] == "availability" and current.procedure.get("threshold_met"):
        state["stage"] = "DENIAL_ACCEPTED"
    else:
        state["stage"] = "HUMAN_REVIEW"
