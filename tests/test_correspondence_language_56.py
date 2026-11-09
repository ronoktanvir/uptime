"""Preregistered public language controls and unchanged signed domain authority."""
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

import pytest

from uptime.correspondence_reason import propose
from test_correspondence_service import service, reports, filed
from test_correspondence_resource import deliver
from test_correspondence_filing_refs import original_record


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "correspondence"
INITIAL = json.loads((FIXTURES / "response-coverage-56.json").read_text())
REVIEW = json.loads((FIXTURES / "response-coverage-56-review.json").read_text())
LEGACY = json.loads((FIXTURES / "response-coverage-56-legacy.json").read_text())
CASES = INITIAL["cases"] + REVIEW["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_preregistered_complete_propositions(case):
    expected = REVIEW["overrides"].get(case["id"], case["expected"])
    actual = asdict(propose(case["text"], claimed=Decimal(case["claimed"]), scope_month=case["scope_month"]))
    assert {key:actual[key] for key in expected if key != "why"} == {key:value for key,value in expected.items() if key != "why"}


@pytest.mark.parametrize("case", LEGACY["cases"], ids=lambda case: case["text"])
def test_existing_successful_proposal_outputs_remain_identical(case):
    actual = json.loads(json.dumps(asdict(propose(case["text"], claimed=Decimal(case["claimed"])))))
    assert actual == case["expected"]


def test_period_requires_server_context_and_generic_target_is_not_availability():
    assert propose(INITIAL["cases"][0]["text"]).reason == "unknown"
    assert propose("The target was met. Claim denied.", scope_month="2027-02").reason == "unknown"


@pytest.mark.parametrize("text", [
    "For February 2027, our measured availability was 99.6%, above the 99.4% commitment. We denied your claim.",
    "Availability of 0.2% met the 0.1% threshold for 2027-02. Claim denied.",
    "The 99.4% service availability target was met for the service month. Claim denied.",
])
def test_vendor_percentages_cannot_change_verified_money_or_measurement(service, text):
    original = filed(service)
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=original["id"], text=text))])
    assert service.read()["stage"] == "RESPONSE_DRAFTED"
    service.action("approve-response")
    service.now += timedelta(days=1)
    reply = service.action("submit-response")["submissions"][1]
    assert reply["requested"] == "20.99"
    assert reply["packet"]["verified_measurement"]["downtime_microseconds"] == 505 * 60_000_000
    assert "99.6" not in json.dumps(reply["packet"]) and "0.2%" not in json.dumps(reply["packet"])


@pytest.mark.parametrize("period", ["March 2027", "2027-03", "the trailing 30 days", "Q1 2027"])
def test_unmatched_period_cannot_trigger_a_same_source_correction(service, period):
    original = filed(service)
    text = f"Availability met the threshold for {period}. Claim denied."
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=original["id"], text=text))])
    assert service.read()["stage"] == "HUMAN_REVIEW" and service.read()["actions"] == []
    assert service.read()["ledger"]["awarded"] == "0.00"


@pytest.mark.parametrize("late", [False, True])
def test_claim_bound_lateness_uses_actual_original_receipt(service, late):
    if not late:
        original = filed(service)
    else:
        deliver(service, reports())
        service.now = datetime(2027, 3, 8, tzinfo=UTC)
        current = service.read()
        original = dict(kind="original_filing_receipt", source_ref="signed-late-original", receipt_id="signed-late-original",
            observed_at=service.now.isoformat(), received_at="2027-03-07T00:00:00.000001Z", submitted_to="local-support", fields=[],
            contract_version=current["contract_version"], contract_source_sha256=current["contract_source_sha256"])
        deliver(service, [("vendor-fixture", original)])
    receipt = original.get("id", original.get("receipt_id"))
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=receipt,
        text="We declined your claim because it was received after the filing deadline."))])
    if late:
        accept_explicitly(service)
    row = service.read()
    assert row["stage"] == ("DENIAL_ACCEPTED" if late else "RESPONSE_DRAFTED")
    if late:
        assert row["actions"] == [] and row["ledger"]["claimed"] == row["ledger"]["awarded"] == "0.00"


def test_correct_availability_denial_comes_from_signed_measurements_not_percent_claim(service):
    rows = reports()
    rows[0][1]["content"]["unavailable_minutes"] = 504
    from uptime.contracts import fingerprint
    rows[0][1]["content_sha256"] = fingerprint(rows[0][1]["content"])
    deliver(service, rows)
    current = service.read()
    original = dict(kind="original_filing_receipt", source_ref="exact-boundary-original", receipt_id="exact-boundary-original",
        observed_at=service.now.isoformat(), received_at="2027-03-02T23:00:00Z", submitted_to="local-support", fields=[],
        contract_version=current["contract_version"], contract_source_sha256=current["contract_source_sha256"])
    deliver(service, [("vendor-fixture", original)])
    saved = original_record(service)
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=original["receipt_id"],
        text="Availability was 99.6%, above the 99.4% target for 2027-02. Claim denied."))])
    accept_explicitly(service)
    row = service.read()
    assert row["stage"] == "DENIAL_ACCEPTED" and row["actions"] == []
    assert original_record(service) == saved
    assert row["ledger"]["claimed"] == row["ledger"]["awarded"] == "0.00"


def test_missing_declaration_and_request_still_require_independent_exact_artifact_proof(service):
    original = filed(service)
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=original["id"],
        text="The itemized invoice, document BILL-204, is missing. Please provide that document."))])
    assert service.read()["stage"] == "NEEDS_EVIDENCE" and service.read()["actions"] == []
    service.now += timedelta(minutes=1)
    content = "Synthetic signed itemized invoice extract; reference BILL-204."
    common = dict(artifact_type="invoice_detail", artifact_ref="BILL-204", body_sha256=sha256(content.encode()).hexdigest(),
                  observed_at=service.now.isoformat())
    deliver(service, [("customer-fixture", dict(kind="artifact", source_ref="independent-copy", content=content, **common))])
    assert service.read()["actions"] == []
    proof = dict(kind="billing_verification", source_ref="independent-verifier", linked_ref="invoice-7", **common)
    assert service.source("status-fixture", proof).status_code == 403
    deliver(service, [("billing-fixture", proof)])
    assert service.read()["stage"] == "RESPONSE_DRAFTED"
    service.action("approve-response")
    service.now += timedelta(days=1)
    row = service.action("submit-response")
    artifact = row["submissions"][1]["packet"]["disclosed_artifact"]
    assert artifact["ref"] == "BILL-204" and artifact["type"] == "invoice_detail"


@pytest.mark.parametrize("text", [
    "We approved a partial service credit of USD 12.00, and the remaining USD 8.99 is denied.",
    "Of your USD 20.99 claim, we approve a service credit of USD 12.00 and decline the remaining USD 8.99.",
    "We approved a partial service credit of USD 12.00.",
])
def test_partial_credit_retains_unawarded_balance_and_never_authorizes_settlement(service, text):
    original = filed(service)
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=original["id"], text=text))])
    row = service.read()
    assert row["stage"] == "PARTIAL_AWARD_REVIEW" and row["actions"] == []
    assert row["ledger"]["claimed"] == "20.99" and row["ledger"]["awarded"] == "12.00"
    assert row["ledger"]["disputed_remainder"] == "8.99"
    assert row["ledger"]["posted"] == row["ledger"]["applied"] == "0.00"
    assert row["submissions"] == [original]


@pytest.mark.parametrize("text", [
    "We approved a partial service credit of USD 12.00, and the remaining USD 9.00 is denied.",
    "We approved a partial service credit of USD 12.00, and the remaining EUR 8.99 is denied.",
    "We approved a partial service credit of USD 12.00. You must waive the remaining claim.",
    "We will approve a partial service credit of USD 12.00 and deny the remaining USD 8.99.",
])
def test_unknown_or_unconserved_award_text_cannot_create_money(service, text):
    original = filed(service)
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=original["id"], text=text))])
    row = service.read()
    assert row["stage"] == "HUMAN_REVIEW" and row["actions"] == []
    assert row["ledger"]["awarded"] == row["ledger"]["posted"] == row["ledger"]["applied"] == "0.00"


def test_overlapping_family_grammars_refuse_instead_of_choosing_a_parse(monkeypatch):
    from uptime import correspondence_language as language
    # A future template overlap must not introduce an arbitrary family priority.
    text = "Availability met the threshold."
    assert language.interpret_factual(text).reason == "availability"
    monkeypatch.setitem(language.PATTERNS, "time_bar", r"Availability met the threshold")
    assert language.interpret_factual(text) is None


@pytest.mark.parametrize("text", [
    "The itemized invoice is missing. Please provide the resource log.",
    "Document BILL-204 is missing. Please provide document BILL-205.",
    "The itemized invoice, document BILL-204, is missing. Please provide the resource log, document BILL-204.",
])
def test_artifact_unification_rejects_type_or_reference_conflicts(text):
    from uptime.correspondence_language import interpret_factual
    assert interpret_factual(text) is None
    assert propose(text).reason == "unknown"


def test_composition_is_order_sensitive_and_refuses_duplicate_or_unknown_assertions():
    claim = "The itemized invoice is missing."
    request = "Please provide that document."
    assert propose(claim + " " + request).reason == "artifact"
    for text in [request + " " + claim, claim + " " + claim + " " + request,
                 claim + " Your matter is final. " + request,
                 "Availability met the threshold. Your filing arrived after the deadline.",
                 "Availability met the threshold. You accepted a settlement waiver."]:
        assert propose(text).reason == "unknown"
    assert propose(claim).reason == "unknown"
    assert propose(request).reason == "unknown"


def test_preregistered_fixture_bytes_and_reviewed_override_are_preserved():
    expected = {
        "response-coverage-56.json": "2dc8a13a6b68ee0149d4dbc1983676668cbc7993e87b344322737bfbd7b25841",
        "response-coverage-56-review.json": "f9b56e43e84a72d90100bac496516053498ac0f079ea5e0594b768faf7ef6e8d",
    }
    for filename, digest in expected.items():
        assert sha256((FIXTURES / filename).read_bytes()).hexdigest() == digest
    assert INITIAL["cases"][next(i for i, case in enumerate(INITIAL["cases"]) if case["id"] == "late_bound_prior_claim")]["expected"]["reason"] == "time_bar"
    assert REVIEW["overrides"]["late_bound_prior_claim"]["reason"] == "unknown"


@pytest.mark.parametrize("text", [
    "Availability of 98.1% met the 99.4% commitment.",
    "Availability was 99.4%, above the 99.4% target.",
    "Availability exceeded the 99.4% threshold of 98.1%.",
    "Availability of 100.1% met the 99.4% commitment.",
])
def test_internally_contradictory_or_duplicate_percentage_roles_refuse(text):
    assert propose(text, scope_month="2027-02").reason == "unknown"


def test_percentage_comparison_is_only_internal_consistency_not_contract_authority():
    # The real contract may use a completely different target; the text only
    # states one coherent claim for the domain to check against signed evidence.
    assert propose("Availability was 99.4%, at or above the 99.4% target.").reason == "availability"
    assert propose("Availability of 0.2% met the 0.1% commitment.").reason == "availability"


def accept_explicitly(app):
    """D06 (Q2 option A): a substantiated denial closes only through the explicit reviewer action."""
    pending = app.read()
    assert pending["stage"] == "DENIAL_REVIEW" and [a["id"] for a in pending["actions"]] == ["accept-denial"]
    return app.post(app.url + "/denial-acceptance", dict(basis_digest=pending["actions"][0]["basis_digest"]))
