"""Join signed whole-service records only under the reviewed aggregate service-month profile."""
from datetime import timedelta

from .contracts import fingerprint
from .correspondence_artifacts import HISTORICAL, SUPPLEMENTS
from .correspondence_types import SOURCE, instant
from .correspondence_resource import filing_refs


def join_service(scope, events, manifest, overlay, filed, receipts):
    groups = {}
    for event in events:
        kind = event["kind"]
        if kind in SUPPLEMENTS:
            continue
        if SOURCE.get(kind) != event["source"] or kind in groups:
            raise ValueError("Contradictory or unauthenticated whole-service records.")
        groups[kind] = event
    if groups.keys() - {"service_monitor", "service_invoice", "filing_material"} - HISTORICAL:
        raise ValueError("The aggregate contract does not establish how to use these extra records.")
    facts = {k:overlay[k] for k in ("account", "agreement", "product", "plan", "fee_line_ref")}
    facts["month"] = scope.month
    for kind in ("service_monitor", "service_invoice"):
        event = groups.get(kind)
        if not event:
            raise ValueError("Awaiting independently signed " + kind + ".")
        body = event["body"]
        if (body["plan"] != overlay["plan"] or not body["complete"]
                or instant(body["recorded_at"]) < instant(manifest["fixed_period"]["end"])
                or instant(body["recorded_at"]) > instant(body["observed_at"])
                or fingerprint(body["content"]) != body["content_sha256"]):
            raise ValueError("A complete matching-plan report with its actual post-month content commitment is required.")
        facts[kind] = {k:overlay[k] for k in ("account", "agreement", "product", "plan")}
        facts[kind].update(verified=True, complete=True, month=scope.month, ref=body["source_ref"],
                           recorded_at=body["recorded_at"], content=body["content"], content_sha256=body["content_sha256"])
    invoice = facts["service_invoice"]["content"]
    if invoice["currency"] != scope.currency:
        raise ValueError("Service statement currency differs from its signed claim scope.")
    filing = None
    fields = {}
    required = set(manifest.get("request_fields", []))
    if required:
        material = groups.get("filing_material")
        if not material:
            raise ValueError("Awaiting signed source-defined filing contents.")
        body = material["body"]
        fields = {row["name"]:row["refs"] for row in body["fields"]}
        if len(fields) != len(body["fields"]) or set(fields) != required:
            raise ValueError("Source-defined filing fields must each appear once.")
        for name, refs in fields.items():
            allowed = filing_refs(name, manifest, overlay, scope, groups, [], [])
            if not allowed or set(refs) - allowed or len(set(refs)) != len(refs):
                raise ValueError("Each filing field must identify its independently supported source record.")
        if body["channel"] != manifest.get("submission_channel", body["channel"]):
            raise ValueError("Filing destination differs from the published channel.")
        filing = dict(channel=body["channel"], fields=fields, material_digest=material["digest"])
    original = groups.get("original_filing_receipt")
    if groups.get("supplement_filing_receipt"):
        raise ValueError("This published aggregate profile has no supplemental filing-clock operator.")
    proof_ref = fingerprint([scope.model_dump(), fields])
    if original:
        if receipts:
            raise ValueError("Independent existing and local original filings conflict.")
        body = original["body"]
        recorded = {row["name"]:row["refs"] for row in body["fields"]}
        if recorded != fields or len(recorded) != len(body["fields"]):
            raise ValueError("Actual original receipt and checked filing material differ.")
        if manifest.get("submission_channel") and body["submitted_to"] != manifest["submission_channel"]:
            raise ValueError("The historical filing destination differs from the published channel.")
        proof_ref, filed = body["receipt_id"], instant(body["received_at"])
    elif receipts:
        proof_ref, filed = receipts[0]["id"], instant(receipts[0]["at"])
        if receipts[0]["packet"].get("filing_material") != filing:
            raise ValueError("The original approved filing contents differ from the current source material.")
    # A draft uses the local evaluation time. Dispatch replaces this prospective
    # timestamp with the actual immutable local receipt, or an observed original.
    facts["filing_proof"] = {k:overlay[k] for k in ("account", "agreement", "product", "plan")}
    facts["filing_proof"].update(verified=True, ref=proof_ref, month=scope.month, received_at=filed.isoformat(),
                                 fields={k:", ".join(v) for k,v in fields.items()})
    return facts, filing


def service_procedure(events, manifest, raw):
    originals = [e for e in events if e["kind"] == "original_filing_receipt"]
    if len(originals) != 1 or any(e["kind"] == "supplement_filing_receipt" for e in events):
        return None
    original = originals[0]
    body = original["body"]
    channel = manifest.get("submission_channel")
    if (instant(body["received_at"]) < instant(manifest["fixed_period"]["end"])
            or channel and body["submitted_to"] != channel):
        return None
    cutoff = instant(manifest["fixed_filing"]["at"])
    cutoff += timedelta(microseconds=int(manifest["fixed_filing"]["endpoint"] == "inclusive"))
    return dict(original=body["receipt_id"], original_digest=original["digest"], filed_at=body["received_at"],
                last=body["receipt_id"], supplemented=False, channel=channel, cutoff=cutoff.isoformat(),
                response_cutoff=None, response_ref=None, response_message_ref=None, ticket_id=body.get("ticket_id"),
                can_supplement=False, missing=[], available={}, source_digests=sorted(e["digest"] for e in events),
                threshold_met=bool(raw and raw.get("rate_units") == 0 and raw.get("filing_status") == "TIMELY"))
