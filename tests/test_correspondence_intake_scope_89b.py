"""W5 findings F1/F2/F8 applied to the embedded and HMAC channels (decision 89b)."""
from datetime import timedelta

import pytest

from uptime.contracts import Principal
from uptime.correspondence import CorrespondenceDesk
from uptime.correspondence_disposition import dispute_trace
from uptime.correspondence_review import InterpretationDesk
from test_correspondence import BODIES, ID, REVIEWER, env  # noqa: F401  (fixture)

SEPTEMBER = dict(kind="status", start="2026-09-18T13:11:00Z", end="2026-09-18T13:40:00Z")


def refusals(env):
    return [e for e in env.get()["timeline"] if e["event"].startswith("Refused an out-of-scope")]


def test_wrong_period_record_is_refused_without_poisoning_the_claim(env):
    with pytest.raises(ValueError, match="outside service month 2026-10"):
        env.send("status", data=SEPTEMBER, event_id="september")
    env.build()
    row = env.get()
    assert row["preflight"]["outcome"] == "ELIGIBLE" and row["amount"] == "62.13"
    assert [e["label"] for e in row["evidence"]] == ["status", "impact", "invoice"]
    assert [(c["event_id"], c["kind"]) for c in row["contradicting_deliveries"]] == [("september", "status")]
    assert len(refusals(env)) == 1


def test_refusal_is_committed_idempotent_and_survives_restart(env):
    env.build()
    env.act("approve-claim")
    with pytest.raises(ValueError):
        env.send("status", data=SEPTEMBER, event_id="september")
    assert env.get()["approval"] is None
    env.act("approve-claim")
    env.desk = CorrespondenceDesk(env.path, clock=lambda: env.now)
    with pytest.raises(ValueError, match="outside service month"):
        env.send("status", data=SEPTEMBER, event_id="september")
    row = env.get()
    assert row["approval"] is not None and len(row["contradicting_deliveries"]) == 1 and len(refusals(env)) == 1
    with pytest.raises(ValueError, match="reused with different content"):
        env.send("status", data=dict(SEPTEMBER, end="2026-09-18T13:41:00Z"), event_id="september")
    assert env.act("submit-claim")["stage"] == "AWAITING_VENDOR"


def test_foreign_row_during_pending_rebuttal_goes_to_a_person(env):
    env.file()
    assert env.message("Your claim is denied because availability met the contractual threshold.")["stage"] == "RESPONSE_DRAFTED"
    env.act("approve-response")
    with pytest.raises(ValueError, match="outside the granted claim scope"):
        env.send("invoice", data=dict(kind="invoice", lines=[dict(id="z", kind="affected_api", amount="1.00",
                                                                  invoice="another-invoice")]), event_id="late-invoice")
    row = env.get()
    assert row["stage"] == "HUMAN_REVIEW" and row["approval"] is None and row["actions"] == []
    assert len(row["submissions"]) == 1 and row["ledger"]["awarded"] == "0.00"


def test_unbound_source_is_still_refused_before_scope_checks(env):
    with pytest.raises(PermissionError):
        env.send("status", data=SEPTEMBER, principal=Principal("bears", "unbound-sender", "service"))
    assert env.get()["contradicting_deliveries"] == []


def test_trace_labels_status_origin_as_enrolled_not_verified(env):
    env.build()
    check = next(c for c in dispute_trace(env.desk, InterpretationDesk(env.desk), REVIEWER, ID)["deterministic_checks"]
                 if c["check"] == "status_origin")
    assert check["result"] == "ENROLLED_SOURCE_NOT_ORIGIN_VERIFIED"
    assert [e["subject"] for e in check["enrolled"]] == ["status-fixture"]
    assert check["profile_assumed_origin"] == "https://status.twilio.com"


def test_mounted_channel_returns_409_after_committing_the_refusal(tmp_path, monkeypatch):
    from test_v4_routes_integration import App
    monkeypatch.delenv("UPTIME_PUBLIC_EXTRACTIONS", raising=False)
    app = App(tmp_path / "scope.db")
    try:
        app.scope.update(vendor="Twilio", service="Twilio Messaging API")
        app.provision()
        app.create()
        body = dict(kind="status", start="2026-09-14T01:01:00Z", end="2026-09-14T01:46:00Z")
        first = app.source("status-fixture", body, event_id="sep")
        assert first.status_code == 409 and "outside service month" in first.text
        assert app.source("status-fixture", body, event_id="sep").status_code == 409
        row = app.read()
        assert len(row["contradicting_deliveries"]) == 1 and row["evidence"] == []
    finally:
        app.client.close()


def test_identity_contradiction_holds_actions_but_a_misroute_does_not(env):
    env.build()
    with pytest.raises(ValueError, match="outside service month"):
        env.send("status", data=SEPTEMBER, event_id="september")
    assert [a["id"] for a in env.get()["actions"]] == ["approve-claim"]
    with pytest.raises(ValueError, match="outside the granted claim scope"):
        env.send("invoice", data=dict(kind="invoice", lines=[dict(id="r", kind="affected_api", amount="5.00", region="west")]),
                 event_id="other-region")
    row = env.get()
    assert row["preflight"]["outcome"] == "ELIGIBLE" and row["actions"] == []
    assert [c["blocking"] for c in row["contradicting_deliveries"]] == [False, True]
    check = next(c for c in dispute_trace(env.desk, InterpretationDesk(env.desk), REVIEWER, ID)["deterministic_checks"]
                 if c["check"] == "contradicting_deliveries_unresolved")
    assert check["result"] is True
