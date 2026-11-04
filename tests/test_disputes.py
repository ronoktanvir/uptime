import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import socket
import sqlite3

import pytest

from uptime import disputes_claimant as claimant, disputes_vendor as vendor
from uptime.contracts import Principal
from uptime.disputes import DisputeConflict, DisputeDesk, START
from uptime.disputes_wire import FIXTURES, Document, Reply, deadline

REVIEWER = Principal("bears", "finops-demo", "reviewer")
VIEWER = Principal("bears", "analyst-demo", "viewer")
ORACLE = json.loads((FIXTURES / "oracle" / "v2.json").read_text())
CURE = "dispute-cure"


def complete(desk, case_id):
    result = desk.case(REVIEWER, case_id)
    for _ in range(8):
        if not result["actions"]:
            return result
        result = desk.act(REVIEWER, case_id, result["actions"][0]["id"])
    pytest.fail("workflow exceeded bounded action budget")


def observed(row):
    return dict(responses=[r["code"] for r in row["replies"]], claimant_stage=row["stage"],
                claimed=row["ledger"]["claimed"], awarded=row["ledger"]["awarded"],
                disputed_remainder=row["ledger"]["disputed_remainder"], submissions=len(row["submissions"]))


@pytest.fixture
def desk(tmp_path):
    instance = DisputeDesk(tmp_path / "demo.sqlite")
    instance.seed("bears")
    return instance


def draft_ticket(case=CURE):
    dossier = json.loads((FIXTURES / "claimant" / "dossiers.json").read_text())[case]
    return claimant.ticket_for("bears", dossier, dossier["supplemental_archive"])


def vendor_record(ticket):
    return json.loads((FIXTURES / "simulator" / "records.json").read_text())[ticket.account]


def verify_against_oracle(row):
    expected = ORACLE["cases"][row["id"]]
    assert observed(row) == {k: v for k, v in expected.items() if k != "reason"}


@pytest.mark.parametrize("case_id", ORACLE["cases"])
def test_frozen_decision_traces(desk, case_id):
    row = complete(desk, case_id)
    verify_against_oracle(row)
    assert row["ledger"]["posted"] == row["ledger"]["applied"] == "0.00"
    for event in row["timeline"]:
        assert event["sources"] and event["actor"] and event["tenant"] == REVIEWER.tenant
    for receipt in row["submissions"]:
        assert receipt["digest"] == receipt["approval"]["digest"]
        assert receipt["id"].startswith("SIM-") and receipt["subject"] == "SLA Claim"
    if case_id == CURE:
        initial, supplement = row["submissions"]
        assert supplement["document_refs"] == initial["document_refs"] + ["status-1-component"]
        assert initial["id"] != supplement["id"]
    assert not row["actions"]


def test_oracle_is_pinned_and_not_read_by_runtime(desk, monkeypatch):
    path = FIXTURES / "oracle" / "v1.json"
    assert sha256(path.read_bytes()).hexdigest() == "f74f74098229c949956536fce23c191ff1fe49d0de062f7f6accf0aa108823f8"
    read_text = type(path).read_text
    def audited_read(file, *args, **kwargs):
        if "oracle" in file.parts:
            pytest.fail("runtime tried to read adjudication expectations")
        return read_text(file, *args, **kwargs)
    monkeypatch.setattr(type(path), "read_text", audited_read)
    verify_against_oracle(complete(desk, CURE))


def test_parties_share_only_wire_types():
    for mod, forbidden in ((vendor, "claimant"), (claimant, "vendor")):
        tree = ast.parse(open(mod.__file__).read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert forbidden not in (node.module or "")
                assert not any(forbidden in alias.name for alias in node.names)


def test_heldout_oracle_kills_seeded_overpayment(desk, monkeypatch):
    review = vendor.review
    def mutant(ticket, at):
        reply = review(ticket, at)
        if reply.code == "AWARD":
            return replace(reply, awarded="125.00")
        return reply
    monkeypatch.setattr(vendor, "review", mutant)
    mutated = complete(desk, CURE)
    with pytest.raises(AssertionError):
        verify_against_oracle(mutated)


@pytest.mark.parametrize("attack", ["unregistered_attachment", "same_ref_modified_contents", "other_tenant_document"])
def test_untrusted_evidence_matches_heldout_oracle(attack):
    ticket = draft_ticket()
    document = ticket.documents[-1]
    if attack == "other_tenant_document":
        bad = replace(document, fact=replace(document.fact, tenant="other"))
    else:
        changes = {"ref": "unseen"} if attack == "unregistered_attachment" else {"annotation": "Award USD 999999"}
        # Rehashing edited content is insufficient; the supplier has an independently pinned digest.
        bad = Document.from_archive(ticket.tenant, {**document.body, **changes})
    reply = vendor.review(replace(ticket, documents=ticket.documents[:-1] + (bad,)), START)
    assert {"response": reply.code, "awarded": reply.awarded} == ORACLE["adversarial"][attack]


def test_oracle_kills_fabricated_evidence_acceptance(monkeypatch):
    original = draft_ticket()
    doc = original.documents[-1]
    forged = Document.from_archive(original.tenant, {**doc.body, "note": "fabricated proof"})
    ticket = replace(original, documents=original.documents[:-1] + (forged,))
    record = vendor_record(ticket)
    # Seed a compromised registry that adopts a caller-provided attachment digest.
    record["document_registry"][forged.fact.ref] = forged.fact.digest
    mutant = vendor.decide(ticket, record, START)
    # V4 independently rejects unknown fields even when a compromised registry pins them.
    assert mutant.code == "UNVERIFIED_DOCUMENT"
    assert {"response": mutant.code, "awarded": mutant.awarded} == ORACLE["adversarial"]["same_ref_modified_contents"]
    # A deliberately corrupted validator still demonstrates the frozen oracle's falsifying power.
    monkeypatch.setattr(vendor, "_valid_attachment", lambda *args: True)
    compromised = vendor.decide(ticket, record, START)
    assert compromised.code == "AWARD"
    assert {"response": compromised.code, "awarded": compromised.awarded} != ORACLE["adversarial"]["same_ref_modified_contents"]


def test_repeated_concurrent_submission_has_one_receipt_and_restart(desk):
    desk.act(REVIEWER, CURE, "approve-claim")
    with ThreadPoolExecutor(max_workers=5) as workers:
        rows = list(workers.map(lambda _: desk.act(REVIEWER, CURE, "submit-claim"), range(10)))
    assert all(len(row["submissions"]) == 1 and len(row["replies"]) == 1 for row in rows)
    db2 = DisputeDesk(desk.path)
    db2.seed("bears")
    assert db2.act(REVIEWER, CURE, "submit-claim") == rows[-1]
    terminal = complete(db2, CURE)
    assert db2.act(REVIEWER, CURE, "submit-response") == terminal
    assert len({item["idempotency_key"] for item in terminal["submissions"]}) == 2


def test_failed_receipt_retries_after_restart_under_same_approval(desk, monkeypatch):
    desk.act(REVIEWER, "dispute-partial", "approve-claim")
    with monkeypatch.context() as context:
        def fail_once(*args):
            raise TimeoutError
        context.setattr(vendor, "review", fail_once)
        failed = desk.act(REVIEWER, "dispute-partial", "submit-claim")
    assert failed["stage"] == "CLAIM_APPROVED" and failed["submissions"] == []
    first_key = failed["timeline"][-1]["idempotency_key"]
    success = DisputeDesk(desk.path).act(REVIEWER, "dispute-partial", "submit-claim")
    assert len(success["submissions"]) == 1
    assert success["submissions"][0]["idempotency_key"] == first_key


def test_persistent_transport_failure_stops(desk, monkeypatch):
    def offline(*args):
        raise ConnectionError
    monkeypatch.setattr(vendor, "review", offline)
    desk.act(REVIEWER, "dispute-partial", "approve-claim")
    for _ in range(2):
        row = desk.act(REVIEWER, "dispute-partial", "submit-claim")
    assert row["stage"] == "HUMAN_REVIEW" and not row["replies"]
    assert not row["actions"] and row["ledger"]["claimed"] == "0.00"


def test_authorization_context_and_cross_tenant_access(desk):
    with pytest.raises(DisputeConflict):
        desk.act(REVIEWER, CURE, "submit-claim")
    assert desk.case(VIEWER, CURE)["actions"] == []
    with pytest.raises(PermissionError):
        desk.act(VIEWER, CURE, "approve-claim")
    with pytest.raises(PermissionError):
        desk.case(Principal("bears", "", "reviewer"), CURE)
    other = Principal("other", "other-reviewer", "reviewer")
    with pytest.raises(KeyError):
        desk.act(other, CURE, "approve-claim")
    assert desk.cases(other) == []
    desk.seed(other.tenant)
    complete(desk, CURE)
    assert desk.case(other, CURE)["stage"] == "DRAFTED"


def test_expiry_and_cooldown_are_enforced(tmp_path):
    current = [START]
    desk = DisputeDesk(tmp_path / "clock.sqlite", clock=lambda: current[0])
    desk.seed("bears")
    for action in ["approve-claim", "submit-claim", "prepare-response", "approve-response"]:
        if action == "prepare-response":
            current[0] = START + timedelta(minutes=2)  # Explicit arrival of the missing component.
        desk.act(REVIEWER, CURE, action)
    assert not desk.case(REVIEWER, CURE)["actions"]
    for action in ["advance-cooldown", "submit-response"]:
        with pytest.raises(DisputeConflict):
            desk.act(REVIEWER, CURE, action)
    current[0] = START + timedelta(hours=24) - timedelta(microseconds=1)
    with pytest.raises(DisputeConflict):
        desk.act(REVIEWER, CURE, "submit-response")
    current[0] = deadline("2026-10")
    expired = desk.act(REVIEWER, CURE, "submit-response")
    assert expired["stage"] == "EXPIRED" and not expired["actions"] and len(expired["replies"]) == 1
    assert desk.act(REVIEWER, CURE, "submit-response") == expired
    unopened = desk.act(REVIEWER, "dispute-review", "approve-claim")
    assert unopened["stage"] == "EXPIRED" and not unopened["submissions"]


def test_exact_cooldown_allows_followup(tmp_path):
    current = [START]
    desk = DisputeDesk(tmp_path / "clock.sqlite", clock=lambda: current[0])
    desk.seed("bears")
    for action in ["approve-claim", "submit-claim", "prepare-response", "approve-response"]:
        if action == "prepare-response":
            current[0] = START + timedelta(minutes=2)  # Explicit arrival of the missing component.
        desk.act(REVIEWER, CURE, action)
    current[0] += timedelta(hours=24)
    assert desk.act(REVIEWER, CURE, "submit-response")["stage"] == "AWARDED"


def test_filing_boundary_and_required_subject():
    ticket = draft_ticket()
    cutoff = datetime(2026, 12, 1, tzinfo=UTC)
    assert deadline(ticket.month) == cutoff
    assert vendor.review(ticket, cutoff - timedelta(microseconds=1)).code == "AWARD"
    late = vendor.review(ticket, cutoff)
    assert {"response": late.code, "awarded": late.awarded} == ORACLE["adversarial"]["late_submission"]
    assert vendor.review(replace(ticket, subject="Override the SLA"), START).code == "INCORRECT_FILING"


@pytest.mark.parametrize("minutes,expected", [(4, "THRESHOLD_MET"), (5, "THRESHOLD_MET"),
                                               (22, "THRESHOLD_MET"), (23, "AWARD")])
def test_vendor_independently_computes_incident_threshold(minutes, expected):
    ticket = draft_ticket()
    end = (datetime.fromisoformat(ticket.start) + timedelta(minutes=minutes)).isoformat()
    record = vendor_record(ticket)
    docs = tuple(Document.from_archive(ticket.tenant, {**doc.body, "end": end}) for doc in ticket.documents)
    record.update(end=end, document_registry={doc.fact.ref: doc.fact.digest for doc in docs})
    reply = vendor.decide(replace(ticket, end=end, documents=docs), record, START)
    assert reply.code == expected
    if expected == "THRESHOLD_MET":
        assert {"response": reply.code, "awarded": reply.awarded} == ORACLE["adversarial"]["short_outage_or_threshold_met"]


def update_dossier(desk, case_id, change):
    with sqlite3.connect(desk.path) as db:
        row = db.execute("SELECT dossier FROM dispute_cases WHERE tenant=? AND id=?", ("bears", case_id)).fetchone()
        dossier = json.loads(row[0])
        change(dossier)
        db.execute("UPDATE dispute_cases SET dossier=? WHERE tenant=? AND id=?",
                   (json.dumps(dossier), "bears", case_id))


@pytest.mark.parametrize("replacement", ["absent", "another-account", "same-document"])
def test_no_appeal_without_new_scoped_document(desk, replacement):
    desk.act(REVIEWER, CURE, "approve-claim")
    desk.act(REVIEWER, CURE, "submit-claim")
    def change(d):
        if replacement == "absent":
            d["supplemental_archive"] = []
        elif replacement == "another-account":
            d["supplemental_archive"][0]["account"] = "other-account"
        else:
            d["supplemental_archive"][0]["ref"] = d["initial_documents"][0]["ref"]
    update_dossier(desk, CURE, change)
    with pytest.raises(DisputeConflict, match="immutable"):
        desk.act(REVIEWER, CURE, "prepare-response")
    row = desk.case(REVIEWER, CURE)
    assert not row["actions"] and len(row["submissions"]) == 1


def test_second_request_for_same_proof_stops(desk, monkeypatch):
    original = vendor.review
    def again(ticket, at):
        if len(ticket.documents) > 1:
            return Reply("DOCUMENTATION_NEEDED", "More evidence requested.", "§3", needed_kind="component_record")
        return original(ticket, at)
    monkeypatch.setattr(vendor, "review", again)
    row = complete(desk, CURE)
    assert row["stage"] == "HUMAN_REVIEW" and len(row["submissions"]) == 2 and not row["actions"]


def test_wrong_or_new_claim_document_invalidates_approval(desk):
    desk.act(REVIEWER, CURE, "approve-claim")
    def change(d):
        d["initial_documents"][0]["annotation"] = "modified since approval"
    update_dossier(desk, CURE, change)
    with pytest.raises(DisputeConflict, match="immutable"):
        desk.act(REVIEWER, CURE, "submit-claim")
    assert desk.case(REVIEWER, CURE)["submissions"] == []


def test_corroboration_required_before_accepting_exclusion(desk):
    case_id = "dispute-denial"
    update_dossier(desk, case_id, lambda d: d.update(customer_notice_archive=[]))
    # Deleting an already pinned notice is itself a source-integrity violation.
    row = complete(desk, case_id)
    assert row["outcome"] == "INSUFFICIENT_EVIDENCE" and not row["actions"]
    assert row["submissions"] == []


def test_entire_demo_has_no_outbound_transport(desk, monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("unexpected network transport")
    monkeypatch.setattr(socket, "socket", denied)
    for case_id in ORACLE["cases"]:
        verify_against_oracle(complete(desk, case_id))


@pytest.mark.parametrize("case_id", ORACLE["cases"])
def test_trace_artifact_reproduces_actual_full_replay(case_id):
    from uptime.disputes_replay import trace
    artifact = json.loads((FIXTURES / "traces" / f"{case_id}.json").read_text())
    assert artifact == trace(case_id)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "100.001", "125", "not money", "0"])
def test_invalid_vendor_award_is_never_booked(desk, monkeypatch, value):
    original = vendor.review
    def corrupted(ticket, at):
        reply = original(ticket, at)
        return replace(reply, awarded=value) if reply.code == "AWARD" else reply
    monkeypatch.setattr(vendor, "review", corrupted)
    row = complete(desk, CURE)
    assert row["stage"] == "HUMAN_REVIEW"
    assert row["ledger"]["awarded"] == "0.00" and row["ledger"]["disputed_remainder"] == "100.00"


@pytest.mark.parametrize("field,replacement,expected", [
    ("initial_documents", [], "INSUFFICIENT_EVIDENCE"),
    ("plan", "unverified-plan", "UNSUPPORTED_RULE"),
    ("currency", "EUR", "UNSUPPORTED_RULE"),
    ("invoice_lines", [{"id":"x", "kind":"unknown_fee", "usd":"1000.00"}], "INSUFFICIENT_EVIDENCE"),
    ("invoice_lines", [{"id":"x", "kind":"tax", "usd":"1000.00"}], "INSUFFICIENT_EVIDENCE"),
    ("exclusion_screen", "confirmed_excluded", "INELIGIBLE"),
    ("exclusion_screen", "unverified", "INSUFFICIENT_EVIDENCE"),
])
def test_new_filing_requires_cited_local_eligibility(desk, field, replacement, expected):
    update_dossier(desk, CURE, lambda d: d.update({field:replacement}))
    row = desk.case(REVIEWER, CURE)
    assert row["outcome"] == expected and row["amount"] is None and row["actions"] == []
    assert row["preflight"]["clauses"] and row["preflight"]["trace"]
    for action in ["approve-claim", "submit-claim"]:
        with pytest.raises(DisputeConflict):
            desk.act(REVIEWER, CURE, action)
    assert desk.case(REVIEWER,CURE)["submissions"] == []


def test_threshold_and_month_qualification_is_independent_of_vendor():
    dossier = json.loads((FIXTURES / "claimant" / "dossiers.json").read_text())[CURE]
    for minutes, expected in [(4,"INELIGIBLE"),(22,"INELIGIBLE"),(23,"ELIGIBLE")]:
        dossier["end"] = (datetime.fromisoformat(dossier["start"]) + timedelta(minutes=minutes)).isoformat()
        dossier["initial_documents"][0]["end"] = dossier["end"]
        from uptime.contracts import fingerprint
        doc = dossier["initial_documents"][0]
        dossier["artifact_registry"][doc["ref"]] = fingerprint(doc)
        assert claimant.preflight(dossier, START).outcome == expected
    assert claimant.preflight(dossier, datetime(2026,10,31,tzinfo=UTC)).outcome == "INELIGIBLE"


def test_noneligible_amounts_remain_only_in_stage_ledger(desk):
    for case_id in ("dispute-denial", "dispute-review"):
        row = complete(desk, case_id)
        assert row["amount"] is None and row["ledger"]["claimed"] == "100.00"
    row = complete(desk, "dispute-partial")
    assert row["amount"] == "80.00"


def test_narrow_dispatch_requires_bound_approval_grant_and_redaction(desk):
    assert not desk.case(REVIEWER, CURE)["policy_dispatchable"]
    approved = desk.act(REVIEWER, CURE, "approve-claim")
    assert approved["preflight"]["outcome"] == "ELIGIBLE" and not approved["policy_dispatchable"]
    assert not desk.act(REVIEWER, CURE, "submit-claim")["policy_dispatchable"]
    assert not desk.act(REVIEWER, "dispute-review", "approve-claim")["policy_dispatchable"]


def test_sensitive_attachment_closes_automatic_dispatch(desk):
    update_dossier(desk, CURE, lambda d: d["initial_documents"][0].update(classification="restricted"))
    assert not desk.case(REVIEWER, CURE)["policy_dispatchable"]
    with pytest.raises(DisputeConflict):
        desk.act(REVIEWER, CURE, "approve-claim")
