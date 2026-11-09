"""Decision 89: novel vendor wording through ordinary intake, explicit denial acceptance and the dispute trace.

The case texts and expectations were frozen in fixtures/correspondence/novel-89 before
implementation. Test principals are scripted (SCRIPTED_NOT_ACTUAL_HUMAN).
"""
import ast
from types import SimpleNamespace
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from uptime import correspondence_vendor
from uptime.contracts import Principal
from uptime.correspondence import CorrespondenceDesk
from uptime.correspondence_disposition import dispute_trace
from uptime.correspondence_interpretation import Entry, Interpretation, Prepare, Review
from uptime.correspondence_reason import propose
from uptime.correspondence_review import InterpretationDesk
from uptime.correspondence_types import Delivery, Scope
from uptime.correspondence_vendor import VendorRecord, decide_claim, render
from test_correspondence import BODIES, ID, REVIEWER, VIEWER, env  # noqa: F401  (fixture)
from test_correspondence_service import service  # noqa: F401  (fixture)
from test_correspondence_interpretation import meaning

ROOT = Path(__file__).resolve().parents[1]
FROZEN = json.loads((ROOT / "fixtures/correspondence/novel-89/cases.json").read_text())
CASES = {case["id"]: case for case in FROZEN["cases"]}
PHRASING = {k: v for k, v in FROZEN["counterparty_phrasing"].items() if k != "purpose"}
LATE_NOTICE = dict(BODIES["notice"], issued_at=BODIES["status"]["start"])


def record(**changes):
    # D04-C input mapping (2026-11-09): the counterparty record is aligned in the harness only; the fixture
    # bytes, frozen cases and every expected outcome stay unchanged (see test_correspondence.counterparty_record).
    from test_correspondence import counterparty_record
    return replace(counterparty_record(), **changes)


def reading(case):
    text, spec = case["text"], case["reading"]
    if "propositions" in spec:
        propositions, segments, cursor = [], [], 0
        for item in spec["propositions"]:
            at = text.index(item["quote"], cursor)
            if at > cursor:
                gap = dict(start=len(text[:cursor].encode()), end=len(text[:at].encode()), quote=text[cursor:at])
                segments.append(dict(source=gap, role="courtesy"))
            source = dict(start=len(text[:at].encode()), end=len(text[:at + len(item["quote"])].encode()), quote=item["quote"])
            segments.append(dict(source=source, role="substantive"))
            propositions.append(dict(family=item["family"], source=source, polarity="positive", modality="asserted",
                                     referent="current_claim", conditions=[], slots=[], artifact_type=None,
                                     scope_field=None, filing_fields=[]))
            cursor = at + len(item["quote"])
        return Interpretation.model_validate(dict(propositions=propositions, segments=segments))
    extra = {"scope_field": spec["scope_field"]} if "scope_field" in spec else {}
    return meaning(text, spec["family"], slots=list(spec.get("slots", {}).items()), **extra)


def open_case(env, case):
    for kind in case["initial_evidence"]:
        env.send(kind)
    env.act("approve-claim")
    receipt = env.act("submit-claim")["submissions"][0]
    row = env.message(case["text"])
    assert row["stage"] == "HUMAN_REVIEW" and row["replies"][-1]["reason"] == "unknown"
    return receipt


def reviewed(env, interpretation, principal=REVIEWER):
    desk = InterpretationDesk(env.desk)
    context = desk.view(principal, ID)["context"]
    desk.blind(principal, ID, Entry(context_digest=context["digest"], interpretation=interpretation))
    count = len(interpretation.propositions)
    body = Review(context_digest=context["digest"], interpretation=interpretation, candidate_id=None,
                  resolutions=[dict(proposition=i, verdict="accept", explanation="Scripted reading of the complete signed reply.")
                               for i in range(count)], residuals_reviewed=True, complete_meaning_reviewed=True)
    rid = desk.review(principal, ID, body)["id"]
    return desk, rid, desk.preview(principal, ID, rid)


def prepare(desk, rid, preview):
    return desk.prepare(REVIEWER, ID, Prepare(review_id=rid, preview_digest=preview["digest"]))


def trace(env, principal=REVIEWER):
    return dispute_trace(env.desk, InterpretationDesk(env.desk), principal, ID)


def actions(row):
    return [a["id"] for a in row["actions"]]


def accept(env, principal=REVIEWER):
    """Accept with the exact offered basis digest, or a digest that matches nothing when none is offered."""
    offered = [a for a in env.desk.case(REVIEWER, ID)["actions"] if a["id"] == "accept-denial"]
    return env.desk.accept_denial(principal, ID, offered[0]["basis_digest"] if offered else "0" * 64)


UNAVAILABLE = "Action unavailable"
COVERAGE = dict(kind="coverage", start="2026-10-01T00:00:00Z", end="2026-11-01T00:00:00Z", complete=True,
                exclusions_removed=True, incident_ids=["evt-411"], total_eligible_minutes=29)


def test_frozen_vendor_texts_are_outside_the_finite_grammar():
    texts = [c["text"] for c in FROZEN["cases"]] + list(PHRASING.values())
    for text in texts:
        assert propose(text.format(amount="62.13"), claimed=Decimal(FROZEN["filed_request"]),
                       scope_month=FROZEN["base_scope"]["month"]).reason == "unknown", text


def test_n89_cure_endpoint_preserves_original_filing(env):
    case = CASES["n89-cure-endpoint"]
    original = open_case(env, case)
    desk, rid, preview = reviewed(env, reading(case))
    assert preview["disposition"] == "NEEDS_EVIDENCE" and preview["prepare_allowed"]
    assert preview["assertions"]["category"] == "MISSING_EVIDENCE"
    assert prepare(desk, rid, preview)["stage"] == "NEEDS_EVIDENCE"
    assert (trace(env)["category"], trace(env)["disposition"]) == ("MISSING_EVIDENCE", "AWAIT_CURE_EVIDENCE")
    env.now += timedelta(hours=1)
    env.send("component")
    row = env.get()
    expected = case["expected"]
    assert row["stage"] == expected["stage"] and actions(row) == ["approve-response"]
    assert trace(env)["disposition"] == expected["disposition"]
    env.act("approve-response")
    env.now += timedelta(days=1)
    supplement = env.act("submit-response")["submissions"][1]
    assert supplement["packet"]["in_reply_to"] == original["id"]
    assert supplement["packet"]["filing_cutoff"] == original["packet"]["filing_cutoff"]
    assert supplement["requested"] == expected["supplement"]["requested"]
    final = trace(env)
    check = next(c for c in final["deterministic_checks"] if c["check"] == "follow_ups_preserve_original_filing")
    assert check["result"] is True and final["governing"]["original_filed_at"] == original["at"]
    assert {k: final["ledger"][k] for k in expected["ledger"]} == expected["ledger"]


def test_n89_cure_unavailable_never_extends_the_window(env):
    case = CASES["n89-cure-unavailable"]
    open_case(env, case)
    desk, rid, preview = reviewed(env, reading(case))
    before = prepare(desk, rid, preview)
    assert before["stage"] == "NEEDS_EVIDENCE" and not before["actions"]
    env.now = datetime(2026, 12, 15, tzinfo=UTC)
    after = env.get()
    assert after["stage"] == "NEEDS_EVIDENCE" and after["actions"] == []
    assert after["filing_cutoff"] == before["filing_cutoff"] and len(after["submissions"]) == 1
    env.send("component")
    late = env.get()
    assert late["actions"] == [] and len(late["submissions"]) == 1


def test_n89_cure_inapplicable_escalates(env):
    case = CASES["n89-cure-inapplicable"]
    open_case(env, case)
    desk, rid, preview = reviewed(env, reading(case))
    prepare(desk, rid, preview)
    env.now += timedelta(hours=1)
    with pytest.raises(ValueError, match="outside the granted claim scope"):
        env.send("component", data={**BODIES["component"], "component_id": "api-west"})
    assert env.get()["stage"] == "HUMAN_REVIEW" and trace(env)["disposition"] == "ESCALATE"
    assert trace(env)["contradicting_deliveries"][0]["kind"] == "component"
    assert len(env.get()["submissions"]) == 1


def test_n89_cure_unauthorized_source_is_refused(env):
    case = CASES["n89-cure-unauthorized"]
    open_case(env, case)
    desk, rid, preview = reviewed(env, reading(case))
    before = prepare(desk, rid, preview)
    with pytest.raises(PermissionError):
        env.send("component", principal=Principal("bears", "unbound-sender", "service"))
    assert env.get() == before


@pytest.mark.parametrize("order", ["notice_then_review", "review_then_notice"])
def test_n89_denial_maintenance_is_order_independent_and_explicit(env, order):
    case = CASES["n89-denial-maintenance"]
    expected = case["expected"]
    open_case(env, case)
    env.now += timedelta(minutes=5)
    if order == "notice_then_review":
        env.send("notice")
        desk, rid, preview = reviewed(env, reading(case))
        assert preview["disposition"] == "DENIAL_REVIEW" and preview["prepare_allowed"] and preview["closure_suggested"]
        assert preview["assertions"]["category"] == "CONTRACTUAL_DENIAL" and preview["ledger_unchanged"]
        prepare(desk, rid, preview)
    else:
        desk, rid, preview = reviewed(env, reading(case))
        assert preview["disposition"] == "AWAITING_NOTICE"
        prepare(desk, rid, preview)
        env.send("notice")
    pending = env.get()
    assert pending["stage"] == expected["before_acceptance"]["stage"]
    assert actions(pending) == [expected["explicit_action"]]
    assert pending["ledger"]["disputed_remainder"] == "62.13"
    summary = trace(env)
    assert (summary["category"], summary["disposition"]) == ("CONTRACTUAL_DENIAL", "DENIAL_SUBSTANTIATED")
    with pytest.raises(PermissionError):
        accept(env, VIEWER)
    with pytest.raises(ValueError, match="exact reviewed basis digest"):
        env.act("accept-denial")
    final = accept(env)
    assert final["stage"] == expected["stage"] and final["actions"] == []
    assert {k: final["ledger"][k] for k in expected["ledger"]} == expected["ledger"]
    assert len(final["submissions"]) == expected["submissions"]
    assert final["denial_acceptance"]["actor"] == REVIEWER.subject
    assert final["denial_acceptance"]["basis"]["review_id"] == rid
    assert accept(env) == final
    closed = trace(env)
    assert (closed["category"], closed["disposition"], closed["final"]) == ("CONTRACTUAL_DENIAL", "ACCEPT_DENIAL", True)
    assert closed["correspondence"][-1]["interpretation"]["origin"] == "reviewed_interpretation"
    assert closed["correspondence"][-1]["interpretation"]["source"]["quote"] == case["text"]
    assert closed["governing"]["clauses"] and closed["governing"]["contract_version"]


def test_n89_short_notice_makes_the_maintenance_assertion_incorrect(env):
    case = CASES["n89-denial-short-notice"]
    open_case(env, case)
    env.now += timedelta(minutes=5)
    env.send("notice", data=LATE_NOTICE)
    desk, rid, preview = reviewed(env, reading(case))
    assert preview["disposition"] == case["expected"]["stage"] and preview["prepare_allowed"]
    assert preview["assertions"]["category"] == case["expected"]["category"]
    prepare(desk, rid, preview)
    assert trace(env)["disposition"] == "REBUT" and actions(env.get()) == ["approve-response"]
    with pytest.raises(ValueError, match=UNAVAILABLE):
        accept(env)


def test_n89_unverified_maintenance_waits_and_cannot_be_accepted(env):
    case = CASES["n89-denial-no-notice"]
    open_case(env, case)
    desk, rid, preview = reviewed(env, reading(case))
    assert preview["assertions"]["category"] == "UNRESOLVED_DENIAL"
    prepare(desk, rid, preview)
    assert env.get()["stage"] == "AWAITING_NOTICE" and trace(env)["disposition"] == "AWAIT_EVIDENCE"
    with pytest.raises(ValueError, match=UNAVAILABLE):
        accept(env)


@pytest.mark.parametrize("case_id", ["n89-escalate-legal", "n89-injection"])
def test_n89_legal_and_injected_grounds_escalate_without_effect(env, case_id):
    case = CASES[case_id]
    open_case(env, case)
    before = env.get()
    desk, rid, preview = reviewed(env, reading(case))
    assert not preview["prepare_allowed"] and preview["assertions"]["category"] == "AMBIGUOUS_GROUNDS"
    with pytest.raises(ValueError):
        prepare(desk, rid, preview)
    with pytest.raises(ValueError, match=UNAVAILABLE):
        accept(env)
    assert env.get() == before
    summary = trace(env)
    assert (summary["category"], summary["disposition"]) == ("AMBIGUOUS_GROUNDS", "ESCALATE")
    assert summary["ledger"]["awarded"] == "0.00" and summary["ledger"]["disputed_remainder"] == "62.13"


def test_n89_compound_ground_cannot_erase_unresolved_condition(env):
    case = CASES["n89-escalate-compound"]
    open_case(env, case)
    env.now += timedelta(minutes=5)
    env.send("notice")
    desk, rid, preview = reviewed(env, reading(case))
    assert not preview["prepare_allowed"] and not preview["closure_suggested"]
    categories = [row["category"] for row in preview["assertions"]["propositions"]]
    assert categories == ["UNRESOLVED_DENIAL", "AMBIGUOUS_GROUNDS"]
    assert preview["assertions"]["category"] == "AMBIGUOUS_GROUNDS"
    with pytest.raises(ValueError, match=UNAVAILABLE):
        accept(env)
    assert env.get()["stage"] == "HUMAN_REVIEW" and trace(env)["disposition"] == "ESCALATE"


def test_n89_partial_award_is_classified_and_never_booked(env):
    case = CASES["n89-partial"]
    open_case(env, case)
    desk, rid, preview = reviewed(env, reading(case))
    expected = case["expected"]
    assert preview["reported_award"] == expected["reported_award"] and not preview["prepare_allowed"]
    primary = preview["assertions"]["propositions"][0]
    assert (preview["assertions"]["category"], primary["contested_remainder"]) == ("PARTIAL_AWARD", expected["contested_remainder"])
    row = env.get()
    assert row["stage"] == "HUMAN_REVIEW" and {k: row["ledger"][k] for k in expected["ledger"]} == expected["ledger"]
    assert trace(env)["category"] == "PARTIAL_AWARD"
    assert trace(env, VIEWER)["category"] == "AMBIGUOUS_GROUNDS" and trace(env, VIEWER)["reviewed_readings"] == []


@pytest.mark.parametrize("case_id", ["n89-incorrect-availability", "n89-incorrect-scope"])
def test_n89_contradicted_assertions_prepare_a_rebuttal(env, case_id):
    case = CASES[case_id]
    open_case(env, case)
    desk, rid, preview = reviewed(env, reading(case))
    assert preview["disposition"] == "RESPONSE_DRAFTED" and preview["prepare_allowed"]
    assert preview["assertions"]["category"] == "INCORRECT_FACTUAL_ASSERTION"
    row = prepare(desk, rid, preview)
    assert row["stage"] == "RESPONSE_DRAFTED" and trace(env)["disposition"] == "REBUT"
    assert trace(env)["category"] == "INCORRECT_FACTUAL_ASSERTION"


def test_n89_changed_scope_award_escalates(env):
    case = CASES["n89-changed-scope"]
    open_case(env, case)
    desk, rid, preview = reviewed(env, reading(case))
    assert not preview["prepare_allowed"] and preview["assertions"]["category"] == "CHANGED_SCOPE"
    assert env.get()["ledger"]["awarded"] == "0.00"
    assert (trace(env)["category"], trace(env)["disposition"]) == ("CHANGED_SCOPE", "ESCALATE")


def test_loop_cure_with_novel_counterparty_wording(env):
    loop = next(item for item in FROZEN["loops"] if item["id"] == "n89-loop-cure")["expected"]
    private = record()
    env.build()
    env.act("approve-claim")
    first = env.act("submit-claim")["submissions"][0]
    decision = decide_claim(first["packet"], private, env.now)
    assert decision.code == loop["first_decision"]
    row = env.message(render(decision, PHRASING))
    assert row["stage"] == "HUMAN_REVIEW"
    desk, rid, preview = reviewed(env, meaning(row["replies"][-1]["text"], "component"))
    assert prepare(desk, rid, preview)["stage"] == loop["claimant_after_review"]
    env.now += timedelta(hours=1)
    env.send("component")
    env.act("approve-response")
    env.now += timedelta(days=1)
    sent = env.act("submit-response")
    assert sent["stage"] == loop["after_component_and_supplement"]
    second = decide_claim(sent["submissions"][1]["packet"], private, env.now)
    assert (second.code, second.amount) == (loop["second_decision"], loop["second_decision_amount"])
    reply = render(second, PHRASING)
    row = env.message(reply, "closing")
    awarded = loop["claimant_after_novel_award"]
    assert row["stage"] == awarded["stage"] and row["ledger"]["awarded"] == awarded["ledger_awarded"]
    desk, rid, preview = reviewed(env, meaning(reply, "award", slots=[("award", "USD 62.13")]))
    assert preview["reported_award"] == "62.13" and not preview["prepare_allowed"]
    assert preview["assertions"]["category"] == awarded["category"]
    assert env.get()["ledger"]["awarded"] == "0.00"


def test_loop_denial_with_novel_counterparty_wording(env):
    loop = next(item for item in FROZEN["loops"] if item["id"] == "n89-loop-denial")["expected"]
    private = record(maintenance_notice=BODIES["notice"]["issued_at"])
    env.build()
    env.send("component")
    env.act("approve-claim")
    first = env.act("submit-claim")["submissions"][0]
    decision = decide_claim(first["packet"], private, env.now)
    assert decision.code == loop["first_decision"]
    row = env.message(render(decision, PHRASING))
    desk, rid, preview = reviewed(env, meaning(row["replies"][-1]["text"], "maintenance"))
    prepare(desk, rid, preview)
    env.now += timedelta(minutes=5)
    env.send("notice")
    assert env.get()["stage"] == loop["claimant_after_review_and_notice"]
    final = accept(env)
    assert final["stage"] == loop["after_accept_denial"]
    assert len(final["submissions"]) - 1 == loop["follow_up_submissions"]


def test_counterparty_decides_from_its_records_not_claimant_outcome_or_step(env):
    env.build()
    env.act("approve-claim")
    packet = env.act("submit-claim")["submissions"][0]["packet"]
    private = record()
    insisted = dict(packet, expected_outcome="AWARD", step="final", argument="The claimant is entitled to the full credit.",
                    in_reply_to=packet["claim"])
    assert decide_claim(insisted, private, env.now) == decide_claim(packet, private, env.now)
    assert decide_claim(insisted, private, env.now).code == "DOCUMENTATION_NEEDED"
    withheld = dict(packet, artifacts=packet["artifacts"] + [dict(kind="component", digest="0" * 64)])
    assert decide_claim(withheld, private, env.now).code == "DOCUMENT_UNVERIFIED"
    tree = ast.parse(Path(correspondence_vendor.__file__).read_text())
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imported <= {"dataclasses", "datetime", "decimal", "correspondence_types", "disputes_wire"}


def test_existing_counterparty_wording_is_unchanged(env):
    env.build()
    env.act("approve-claim")
    packet = env.act("submit-claim")["submissions"][0]["packet"]
    assert correspondence_vendor.adjudicate(packet, record(), env.now) == \
        "Please supply the affected endpoint identifier and its supporting record."


def _accepted(env):
    case = CASES["n89-denial-maintenance"]
    open_case(env, case)
    env.now += timedelta(minutes=5)
    env.send("notice")
    desk, rid, preview = reviewed(env, reading(case))
    prepare(desk, rid, preview)
    return accept(env)


def test_repeated_and_conflicting_replies_after_acceptance(env):
    accepted = _accepted(env)
    receipt = accepted["submissions"][0]["id"]
    text = CASES["n89-denial-maintenance"]["text"]
    env.send("message", data=dict(kind="message", text=text, receipt_id=receipt), event_id="reply")
    assert env.get()["stage"] == "DENIAL_ACCEPTED"
    env.send("message", data=dict(kind="message", text="On reflection a credit may be possible.", receipt_id=receipt),
             event_id="second-thoughts")
    row = env.get()
    assert row["stage"] == "HUMAN_REVIEW" and row["denial_acceptance"] is None and row["actions"] == []
    assert len(row["submissions"]) == 1


def test_contradictory_evidence_reopens_an_accepted_denial(env):
    accepted = _accepted(env)
    env.send("notice", data=LATE_NOTICE, event_id="second-notice")
    row = env.get()
    assert row["stage"] == "HUMAN_REVIEW" and row["denial_acceptance"] is None
    assert row["ledger"]["awarded"] == "0.00" and len(row["submissions"]) == len(accepted["submissions"])
    assert trace(env)["disposition"] == "ESCALATE"


def test_stale_authority_cannot_accept(env, monkeypatch):
    from uptime import policy
    case = CASES["n89-denial-maintenance"]
    open_case(env, case)
    env.now += timedelta(minutes=5)
    env.send("notice")
    desk, rid, preview = reviewed(env, reading(case))
    prepare(desk, rid, preview)
    with pytest.raises(KeyError):
        accept(env, Principal("elsewhere", "operator", "reviewer"))
    original = env.desk._assess
    monkeypatch.setattr(env.desk, "_assess", lambda *a, **k: replace(original(*a, **k), version="changed-reviewed-terms"))
    assert env.get()["actions"] == []
    with pytest.raises(ValueError, match=UNAVAILABLE):
        accept(env)
    stale = trace(env)
    assert stale["stale_denial_review"] and stale["disposition"] == "ESCALATE"
    assert stale["category"] == "UNRESOLVED_DENIAL" and stale["ledger"]["disputed_remainder"] == "62.13"
    assert next(c for c in stale["deterministic_checks"] if c["check"] == "denial_ground_substantiated")["result"] is False
    monkeypatch.setattr(env.desk, "_assess", original)
    policy.setup(env.path)
    policy.configure(env.path, REVIEWER, "OBSERVE", "0.00")
    assert env.get()["actions"] == []
    with pytest.raises(PermissionError):
        accept(env)
    assert env.get()["stage"] == "DENIAL_REVIEW"


def test_new_evidence_after_preview_stales_the_review(env):
    case = CASES["n89-denial-maintenance"]
    open_case(env, case)
    env.now += timedelta(minutes=5)
    env.send("notice")
    desk, rid, preview = reviewed(env, reading(case))
    env.send("notice", data=LATE_NOTICE, event_id="another-notice")
    with pytest.raises(ValueError):
        prepare(desk, rid, preview)
    assert env.get()["stage"] == "HUMAN_REVIEW"


def test_model_candidate_or_confidence_cannot_authorize_scope_or_money(env):
    case = CASES["n89-denial-maintenance"]
    open_case(env, case)
    env.now += timedelta(minutes=5)
    env.send("notice")
    desk = InterpretationDesk(env.desk)
    context = desk.view(REVIEWER, ID)["context"]
    candidate = reading(case).model_dump()
    with pytest.raises(ValidationError):
        Interpretation.model_validate(dict(candidate, confidence=0.99))
    desk.blind(REVIEWER, ID, Entry(context_digest=context["digest"], interpretation=reading(case)))
    stored = desk.store_model_result(REVIEWER, ID, context["digest"],
                                     dict(interpretation=candidate, provenance=dict(request_sha256="0" * 64)))
    with pytest.raises(ValueError):
        desk.prepare(REVIEWER, ID, Prepare(review_id=stored, preview_digest="0" * 64))
    with pytest.raises(ValueError):
        desk.preview(REVIEWER, ID, stored)
    with pytest.raises(ValueError, match=UNAVAILABLE):
        accept(env)
    assert env.get()["stage"] == "HUMAN_REVIEW" and env.get()["ledger"]["awarded"] == "0.00"


def test_out_of_order_replies_are_refused(env):
    with pytest.raises(ValueError):
        env.send("message", data=dict(kind="message", text="Your claim is approved.", receipt_id="LOCAL-unknown"))
    case = CASES["n89-cure-endpoint"]
    original = open_case(env, case)
    desk, rid, preview = reviewed(env, reading(case))
    prepare(desk, rid, preview)
    env.now += timedelta(hours=1)
    env.send("component")
    env.act("approve-response")
    env.now += timedelta(days=1)
    env.act("submit-response")
    with pytest.raises(ValueError):
        env.send("message", data=dict(kind="message", text="Regarding your first filing, it is approved.",
                                      receipt_id=original["id"]), event_id="stale-thread")
    assert env.get()["stage"] == "AWAITING_VENDOR"


def test_uncertain_delivery_has_no_automatic_resend(env):
    env.build()
    env.act("approve-claim")
    first = env.act("submit-claim")
    assert env.act("submit-claim")["submissions"] == first["submissions"]
    env.now = datetime(2026, 12, 15, tzinfo=UTC)
    silent = env.get()
    assert silent["stage"] == "AWAITING_VENDOR" and silent["actions"] == [] and len(silent["submissions"]) == 1
    assert trace(env)["disposition"] == "AWAIT_RESPONSE"
    env.now = datetime(2026, 11, 20, tzinfo=UTC)
    row = env.message("We may not have the earlier submission on file; can you confirm whether it was actually sent?")
    assert row["stage"] == "HUMAN_REVIEW" and row["actions"] == [] and len(row["submissions"]) == 1
    env.desk = CorrespondenceDesk(env.path, clock=lambda: env.now)
    assert env.get()["submissions"] == first["submissions"]


def test_contradictory_evidence_withdraws_a_drafted_rebuttal(env):
    env.file()
    row = env.message("Your claim is denied because availability met the contractual threshold.")
    assert row["stage"] == "RESPONSE_DRAFTED"
    env.act("approve-response")
    env.send("impact", data={**BODIES["impact"], "affected": False}, event_id="correction")
    row = env.get()
    assert row["stage"] == "HUMAN_REVIEW" and row["approval"] is None and row["actions"] == []
    assert trace(env)["disposition"] == "ESCALATE"


def test_trace_is_read_only_and_digest_bound(env):
    _accepted(env)
    before = env.get()
    first, second = trace(env), trace(env, VIEWER)
    assert env.get() == before and first["digest"] == trace(env)["digest"]
    assert first["authority"].startswith("Read-only") and second["claim"]["state_sha256"] == before["state_sha256"]
    with pytest.raises(PermissionError):
        dispute_trace(env.desk, None, Principal("bears", "", "viewer"), ID)
    assert [c["check"] for c in first["deterministic_checks"]][:2] == ["governing_evaluation", "original_filing_within_window"]
    assert {e["kind"] for e in first["evidence"]} == {"status", "impact", "invoice", "component", "notice"}
    basis = next(c for c in first["deterministic_checks"] if c["check"] == "month_coverage_basis")
    assert basis["result"] == "PROVISIONED_SINGLE_INCIDENT_RECORD"


def test_mounted_routes_accept_denial_and_return_trace(tmp_path, monkeypatch):
    from test_v4_routes_integration import App, INTERVAL
    monkeypatch.delenv("UPTIME_PUBLIC_EXTRACTIONS", raising=False)
    app = App(tmp_path / "routes.db")
    try:
        app.scope.update(vendor="Twilio", service="Twilio Messaging API")
        app.provision()
        app.create()
        app.evidence()
        app.action("approve-claim")
        sent = app.action("submit-claim")["submissions"][0]
        text = CASES["n89-denial-maintenance"]["text"]
        assert app.source("vendor-fixture", dict(kind="message", receipt_id=sent["id"], text=text)).status_code == 200
        app.now += timedelta(minutes=5)
        assert app.source("customer-fixture", dict(kind="notice", **INTERVAL, issued_at="2026-10-13T01:01:00Z")).status_code == 200
        base = app.url + "/interpretation"
        context = app.client.get(base, headers=app.human.headers).json()["context"]
        body = dict(context_digest=context["digest"], interpretation=meaning(text, "maintenance").model_dump())
        app.post(base + "/blind-entry", body)
        rid = app.post(base + "/reviews", dict(**body, candidate_id=None, resolutions=[dict(
            proposition=0, verdict="accept", explanation="Scripted reading of the complete signed reply.")],
            residuals_reviewed=True, complete_meaning_reviewed=True))["id"]
        preview = app.client.get(base + "/reviews/" + rid + "/preview", headers=app.human.headers).json()
        assert preview["disposition"] == "DENIAL_REVIEW"
        assert app.post(base + "/prepare-response", dict(review_id=rid, preview_digest=preview["digest"]))["stage"] == "DENIAL_REVIEW"
        assert app.client.post(app.url + "/denial-acceptance", json=dict(basis_digest="0" * 64)).status_code in {401, 403}
        assert app.human.post(app.url + "/actions/accept-denial", {}).status_code == 409
        offered = app.read()["actions"][0]
        assert offered["id"] == "accept-denial" and offered["route"] == "denial-acceptance"
        assert app.human.post(app.url + "/denial-acceptance", dict(basis_digest="0" * 64)).status_code == 409
        closed = app.post(app.url + "/denial-acceptance", dict(basis_digest=offered["basis_digest"]))
        assert closed["stage"] == "DENIAL_ACCEPTED" and closed["ledger"]["awarded"] == "0.00"
        assert app.client.get(app.url + "/trace").status_code == 401
        summary = app.client.get(app.url + "/trace", headers=app.human.headers).json()
        assert (summary["disposition"], summary["category"]) == ("ACCEPT_DENIAL", "CONTRACTUAL_DENIAL")
    finally:
        app.client.close()


@pytest.mark.parametrize("late", [True, False])
def test_historical_original_reviewed_denial_requires_explicit_acceptance(service, late):
    """Whole-service profile: an independently witnessed original filing and a novel denial reply."""
    from test_correspondence_resource import deliver
    from test_correspondence_service import reports
    from uptime.contracts import fingerprint as digest
    rows = reports()
    if not late:
        rows[0][1]["content"]["unavailable_minutes"] = 504
        rows[0][1]["content_sha256"] = digest(rows[0][1]["content"])
    deliver(service, rows)
    service.now = datetime(2027, 3, 8, tzinfo=UTC)
    original = dict(kind="original_filing_receipt", source_ref="portal-intake-89", receipt_id="outside-original-89",
                    observed_at=service.now.isoformat(), received_at="2027-03-07T00:00:00.000001Z" if late else "2027-03-06T09:00:00Z",
                    submitted_to="local-support", fields=[])
    deliver(service, [("vendor-fixture", original)])
    text = ("Our intake timestamp fell outside the permitted filing interval." if late
            else "Our tooling shows the API stayed inside its committed availability for that month, so nothing is owed.")
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=original["receipt_id"], text=text))])
    assert service.read()["stage"] == "HUMAN_REVIEW"
    desk = InterpretationDesk(service.inbox)
    context = desk.view(REVIEWER, service.id)["context"]
    annotation = meaning(text, "time_bar" if late else "availability")
    desk.blind(REVIEWER, service.id, Entry(context_digest=context["digest"], interpretation=annotation))
    rid = desk.review(REVIEWER, service.id, Review(context_digest=context["digest"], interpretation=annotation, resolutions=[dict(
        proposition=0, verdict="accept", explanation="Scripted reading of the complete signed reply.")],
        residuals_reviewed=True, complete_meaning_reviewed=True))["id"]
    preview = desk.preview(REVIEWER, service.id, rid)
    assert preview["disposition"] == "DENIAL_REVIEW" and preview["assertions"]["category"] == "CONTRACTUAL_DENIAL"
    desk.prepare(REVIEWER, service.id, Prepare(review_id=rid, preview_digest=preview["digest"]))
    pending = service.read()
    assert pending["stage"] == "DENIAL_REVIEW" and [a["id"] for a in pending["actions"]] == ["accept-denial"]
    closed = service.post(service.url + "/denial-acceptance", dict(basis_digest=pending["actions"][0]["basis_digest"]))
    assert closed["stage"] == "DENIAL_ACCEPTED" and closed["submissions"] == [] and closed["actions"] == []
    assert closed["ledger"]["claimed"] == closed["ledger"]["awarded"] == "0.00"


def test_historical_timely_original_rebuts_a_novel_time_bar(service):
    from test_correspondence_resource import deliver
    from test_correspondence_service import reports
    deliver(service, reports())
    service.now = datetime(2027, 3, 8, tzinfo=UTC)
    original = dict(kind="original_filing_receipt", source_ref="portal-intake-89t", receipt_id="outside-original-89t",
                    observed_at=service.now.isoformat(), received_at="2027-03-06T09:00:00Z", submitted_to="local-support", fields=[])
    deliver(service, [("vendor-fixture", original)])
    text = "Our intake timestamp fell outside the permitted filing interval."
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=original["receipt_id"], text=text))])
    desk = InterpretationDesk(service.inbox)
    context = desk.view(REVIEWER, service.id)["context"]
    annotation = meaning(text, "time_bar")
    desk.blind(REVIEWER, service.id, Entry(context_digest=context["digest"], interpretation=annotation))
    rid = desk.review(REVIEWER, service.id, Review(context_digest=context["digest"], interpretation=annotation, resolutions=[dict(
        proposition=0, verdict="accept", explanation="Scripted reading of the complete signed reply.")],
        residuals_reviewed=True, complete_meaning_reviewed=True))["id"]
    preview = desk.preview(REVIEWER, service.id, rid)
    assert preview["disposition"] != "DENIAL_REVIEW" and not preview["closure_suggested"]
    assert preview["assertions"]["category"] != "CONTRACTUAL_DENIAL"


def _pending(env):
    case = CASES["n89-denial-maintenance"]
    open_case(env, case)
    env.now += timedelta(minutes=5)
    env.send("notice")
    desk, rid, preview = reviewed(env, reading(case))
    prepare(desk, rid, preview)
    assert env.get()["stage"] == "DENIAL_REVIEW"


def test_mandated_principal_cannot_accept_until_a_closure_decision_type_exists(env):
    """Critique 89 #1/#2: view and action agree, and no mandate can yet bind a closure."""
    _pending(env)
    mandated = SimpleNamespace(tenant="bears", subject="operator", role="reviewer", mandate_id="mandate-89", claim_decision=None)
    assert env.desk.case(mandated, ID)["actions"] == []
    digest = env.get()["actions"][0]["basis_digest"]
    with pytest.raises(PermissionError):
        env.desk.accept_denial(mandated, ID, digest)
    assert env.get()["stage"] == "DENIAL_REVIEW" and env.get()["denial_acceptance"] is None


def test_acceptance_is_bound_to_the_basis_the_reviewer_saw(env):
    """Critique 89 #3: new evidence that still substantiates the ground changes the basis digest."""
    _pending(env)
    seen = env.get()["actions"][0]["basis_digest"]
    env.desk.receive(Principal("bears", "status-fixture", "service"), ID,
                     Delivery(event_id="month-report", scope=env.scope, body=COVERAGE))
    row = env.get()
    assert row["stage"] == "DENIAL_REVIEW" and row["actions"][0]["basis_digest"] != seen
    with pytest.raises(ValueError, match="basis changed"):
        env.desk.accept_denial(REVIEWER, ID, seen)
    closed = accept(env)
    assert closed["stage"] == "DENIAL_ACCEPTED"
    assert closed["denial_acceptance"]["basis_digest"] == row["actions"][0]["basis_digest"]


def test_explicit_acceptance_reopens_when_its_own_ground_fails(env, monkeypatch):
    """Critique 89 #5: the claim may stay INELIGIBLE, but the accepted ground must still hold."""
    _pending(env)
    accept(env)
    monkeypatch.setattr(type(env.desk), "_maintenance_substantiated", staticmethod(lambda *a: False))
    env.desk.receive(Principal("bears", "status-fixture", "service"), ID,
                     Delivery(event_id="month-report", scope=env.scope, body=COVERAGE))
    row = env.get()
    assert row["preflight"]["outcome"] == "INELIGIBLE"
    assert row["stage"] == "HUMAN_REVIEW" and row["denial_acceptance"] is None and row["actions"] == []
    with database_state(env) as state:
        assert len(state["superseded_denial_acceptances"]) == 1


def test_trace_headline_uses_only_the_requesters_own_reading(env):
    """Critique 89 #6: another reviewer's later reading cannot set my headline."""
    case = CASES["n89-partial"]
    open_case(env, case)
    reviewed(env, reading(case))
    other = Principal("bears", "second-reviewer", "reviewer")
    reviewed(env, meaning(case["text"], "unsupported"), other)
    mine, theirs = trace(env), trace(env, other)
    assert mine["category"] == "PARTIAL_AWARD" and theirs["category"] == "AMBIGUOUS_GROUNDS"
    assert {r["reviewer"] for r in mine["reviewed_readings"]} == {REVIEWER.subject, other.subject}


class database_state:
    def __init__(self, env):
        self.env = env

    def __enter__(self):
        from uptime.storage import database
        with database(self.env.path) as db:
            return self.env.desk._read(db, "bears", ID)[1]

    def __exit__(self, *exc):
        return False
