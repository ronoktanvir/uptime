"""Resolve named supplemental evidence against an independent verifier and the original filing."""
from hashlib import sha256

from .correspondence_types import instant

SUPPLEMENTS = {"artifact", "status_verification", "billing_verification"}
VERIFY = {"resource_log": "status_verification", "invoice_detail": "billing_verification", "scope_mapping": "status_verification"}


def validate_arrival(body, now):
    if "observed_at" in body and instant(body["observed_at"]) > now:
        raise ValueError("A source report cannot be known before it is observed.")
    if body["kind"] in {"resource_status","resource_attribution"} and instant(body["observed_at"]) < instant(body["end"]):
        raise ValueError("A completed measurement cannot be observed before the reporting period ends.")
    if body["kind"] == "artifact" and sha256(body["content"].encode()).hexdigest() != body["body_sha256"]:
        raise ValueError("Local artifact bytes do not match their declared content digest.")
    if body["kind"] in {"status_verification","billing_verification"} and VERIFY[body["artifact_type"]] != body["kind"]:
        raise ValueError("This verifier is not authorized for the artifact type.")


def artifact_conflict(state):
    request = state.get("requested_artifact") or {}
    relevant = [e for e in state["evidence"] if e["kind"] in SUPPLEMENTS and
                (not request.get("type") or e["body"]["artifact_type"] == request["type"]) and
                (not request.get("ref") or e["body"]["artifact_ref"] == request["ref"])]
    by_ref = {}
    for e in relevant:
        b = e["body"]
        by_ref.setdefault(b["artifact_ref"], set()).add((b["artifact_type"],b["body_sha256"]))
    if any(len(values)>1 for values in by_ref.values()):
        return True
    return (any(e["kind"]=="artifact" for e in relevant) and any(e["kind"]!="artifact" for e in relevant)
            and approved_artifact(state) is None)


def approved_artifact(state):
    request = state.get("requested_artifact") or {}
    if not request or not state["submissions"]:
        return None
    facts = state["evidence"]
    candidates = [e for e in facts if e["kind"] == "artifact" and
                  (not request.get("type") or e["body"]["artifact_type"] == request["type"]) and
                  (not request.get("ref") or e["body"]["artifact_ref"] == request["ref"])]
    if len(candidates) != 1:
        return None
    item = candidates[0]
    body = item["body"]
    verification = [e for e in facts if e["kind"] == VERIFY[body["artifact_type"]] and e["body"]["artifact_ref"] == body["artifact_ref"]]
    if len(verification) != 1:
        return None
    proof = verification[0]
    if (proof["subject"] == item["subject"] or any(proof["body"][k] != body[k] for k in ("artifact_type","body_sha256"))
            or sha256(body["content"].encode()).hexdigest() != body["body_sha256"]):
        return None
    old = set(state["submissions"][0]["evidence_digests"])
    if proof["digest"] in old and item["digest"] in old:
        return None
    link = proof["body"]["linked_ref"]
    families = {"invoice_detail": {"invoice","resource_invoice"}, "scope_mapping": {"status","resource_status"},
                "resource_log": {"status","resource_status"}}[body["artifact_type"]]
    records = [e for e in facts if e["kind"] in families and
               (e["event_id"] == link or e["body"].get("source_ref") == link or
                any(r.get("ref",r.get("id")) == link for r in e["body"].get("intervals",[]) + e["body"].get("lines",[])))]
    if len(records) != 1:
        return None
    observed = records[0]["body"].get("observed_at") or records[0]["body"].get("end")
    if observed and instant(proof["body"]["observed_at"]) < instant(observed):
        return None
    return dict(ref=body["artifact_ref"], type=body["artifact_type"], sha256=body["body_sha256"],
                verifier_digest=proof["digest"], record_digest=records[0]["digest"])
