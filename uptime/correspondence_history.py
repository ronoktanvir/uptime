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
