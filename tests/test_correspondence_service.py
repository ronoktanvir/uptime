"""Public signed whole-service entry point and ordinary separately received vendor replies."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json

import pytest

from uptime.contracts import fingerprint
from uptime.vendor_model import MODEL
from test_v4_routes_integration import App
from test_vendor_service_month import ROWS, DOC, OVERLAY, facts
from test_correspondence_resource import deliver


@pytest.fixture
def service(tmp_path, monkeypatch):
    env = App(tmp_path / "whole-service.db")
    env.now = datetime(2027, 3, 3, tzinfo=UTC)
    env.scope.update(vendor="Heliograph Navigation", account=OVERLAY["account"], contract=OVERLAY["agreement"],
                     service=OVERLAY["product"], month="2027-02")
    env.provision()
    env.create()
    proposal = [dict(quote=q, field="resource_terms", value=v) for q,v in ROWS]
    digest = sha256(DOC["text"].encode()).hexdigest()
    capture = dict(model=MODEL, source_sha256=digest, session="synthetic-aggregate-connector-regression",
                   at=env.now.isoformat(), proposal=proposal, proposal_sha256=fingerprint(proposal))
    (tmp_path / (digest + ".json")).write_text(json.dumps(capture))
    monkeypatch.setenv("UPTIME_PUBLIC_EXTRACTIONS", str(tmp_path))
    monkeypatch.setenv("UPTIME_MODEL_PROPOSITIONS", "1")
    base = "/api/vendors/aggregate-connector"
    from governing_binding_89 import reviewed_binding  # F5 (2026-11-09): unnamed-agreement source binding
    from test_vendor_service_month import manifest as compass_manifest
    state = env.post(base + "/candidates", dict(document=DOC, overlay=reviewed_binding(compass_manifest(), OVERLAY)))
    assert state["state"] == "SHADOW", state
    from test_vendor_semantic_bindings import review_submission
    state=env.post(base+'/semantic-bindings',dict(revision=state['revision'],
        review=review_submission(state['manifest'],state['overlay'],DOC['text'])))
    negative = deepcopy(facts())
    negative["service_monitor"]["content"]["unavailable_minutes"] = 504
    negative["service_monitor"]["content_sha256"] = fingerprint(negative["service_monitor"]["content"])
    state = env.post(base + "/tests", dict(revision=state["revision"], tests=[
        dict(name="505 verified minutes", facts=facts(), expected=dict(outcome="ELIGIBLE", amount="20.99")),
        dict(name="504 equality", facts=negative, expected=dict(outcome="INELIGIBLE"))]))
    for op in ("interpret", "approve", "activate"):
        action = next(a["id"] for a in state["actions"] if a["operation"] == op)
        state = env.post(base + "/actions/" + action, {})
    yield env
    env.client.close()


def reports():
    observations = facts()
    rows = []
    for role, kind in (("status", "service_monitor"), ("billing", "service_invoice")):
        source = observations[kind]
        rows.append((role + "-fixture", dict(kind=kind, source_ref=source["ref"], observed_at=source["recorded_at"],
                    plan=source["plan"], complete=source["complete"], recorded_at=source["recorded_at"],
                    content=source["content"], content_sha256=source["content_sha256"])))
    return rows


def filed(env):
    deliver(env, reports())
    row = env.read()
    assert row["amount"] == "20.99", row["trace"]
    env.action("approve-claim")
    return env.action("submit-claim")["submissions"][0]


@pytest.mark.parametrize("minutes", [504.5, "504.5", "5.045e2"])
def test_fractional_signed_status_preserves_hash_and_exact_measurement(service, minutes):
    rows = reports()
    content = rows[0][1]["content"]
    content["unavailable_minutes"] = minutes
    rows[0][1]["content_sha256"] = fingerprint(content)
    deliver(service, rows)
    assert service.read()["amount"] == "20.99"
    service.action("approve-claim")
    submitted = service.action("submit-claim")["submissions"][0]
    assert submitted["requested"] == "20.99"
    response = service.source("vendor-fixture", dict(kind="message", receipt_id=submitted["id"],
                              text="Denied. We counted 500 minutes of downtime."))
    assert response.status_code == 200, response.text
    service.action("approve-response")
    service.now += timedelta(days=1)
    supplement = service.action("submit-response")["submissions"][1]
    assert supplement["packet"]["verified_measurement"]["downtime_microseconds"] == 30_270_000_000


@pytest.mark.parametrize("minutes", [True, "NaN", "Infinity", -0.1, "0.000000001", 44640.1])
def test_invalid_signed_duration_is_rejected_before_eligibility(service, minutes):
    _, body = reports()[0]
    body["content"]["unavailable_minutes"] = minutes
    body["content_sha256"] = fingerprint(body["content"])
    response = service.source("status-fixture", body)
    assert response.status_code == 422
    assert service.read()["amount"] is None


@pytest.mark.parametrize("text,stage,awarded", [
    ("Our service records met the availability threshold. Claim denied.", "RESPONSE_DRAFTED", "0.00"),
    ("Denied. We counted 500 minutes of downtime.", "RESPONSE_DRAFTED", "0.00"),
    ("We approved a service credit of USD 17.00.", "PARTIAL_AWARD_REVIEW", "17.00"),
    ("We are checking the amount and may issue a credit.", "HUMAN_REVIEW", "0.00"),
])
def test_separately_delivered_response_uses_approved_scope_and_preserves_partial_ambiguity(service, text, stage, awarded):
    initial = filed(service)
    body = dict(kind="message", receipt_id=initial["id"], text=text)
    result = service.source("vendor-fixture", body, event_id="separate-inbound-reply")
    assert result.status_code == 200, result.text
    row = service.read()
    assert row["stage"] == stage and row["ledger"]["awarded"] == awarded, row
    assert service.source("vendor-fixture", body, event_id="replayed-alias").status_code == 200
    assert len(service.read()["replies"]) == 1
    if stage == "RESPONSE_DRAFTED":
        service.action("approve-response")
        service.now += timedelta(days=1)
        row = service.action("submit-response")
        reply = row["submissions"][1]
        assert reply["packet"]["in_reply_to"] == initial["id"]
        assert reply["packet"]["verified_measurement"]["downtime_microseconds"] == 505 * 60_000_000
        assert reply["requested"] == "20.99"
    else:
        assert row["actions"] == []


@pytest.mark.parametrize("fault", ["missing-monitor", "wrong-plan", "incomplete", "unpaid", "bad-hash", "before-month-end"])
def test_aggregate_source_gaps_never_authorize_a_claim(service, fault):
    rows = reports()
    if fault == "missing-monitor":
        rows.pop(0)
    elif fault == "wrong-plan":
        rows[0][1]["plan"] = "Another plan"
    elif fault == "incomplete":
        rows[0][1]["complete"] = False
    elif fault == "unpaid":
        rows[1][1]["content"]["paid"] = False
        rows[1][1]["content_sha256"] = fingerprint(rows[1][1]["content"])
    elif fault == "before-month-end":
        rows[0][1]["recorded_at"] = rows[0][1]["observed_at"] = "2027-02-28T10:00:00Z"
    elif fault == "bad-hash":
        rows[0][1]["content_sha256"] = "0" * 64
        assert service.source(*rows[0]).status_code == 409
        rows.pop(0)
    deliver(service, rows)
    row = service.read()
    assert row["outcome"] == "INSUFFICIENT_EVIDENCE" and row["actions"] == [], row


def test_fixed_cutoff_uses_actual_local_receipt_and_whole_service_obligation(service):
    deliver(service, reports())
    service.now = datetime(2027, 3, 7, tzinfo=UTC)
    service.action("approve-claim")
    first = service.action("submit-claim")["submissions"][0]
    assert first["at"] == "2027-03-07T00:00:00+00:00"
    assert first["packet"]["filing_cutoff"] == "2027-03-07T00:00:00.000001+00:00"
    # A component alias is still the same whole-service obligation. Once filed,
    # canonical reservation ownership now refuses it before another draft exists.
    original_id, original_url = service.id, service.url
    service.scope.update(component="another-label", invoice="another-statement")
    service.id = "inbox-component-alias"
    service.url = "/api/correspondence/claims/" + service.id
    service.provision()
    response = service.human.post("/api/correspondence/claims", dict(claim_id=service.id, scope=service.scope))
    assert response.status_code == 409 and "already reserved" in response.text
    assert service.client.get(service.url, headers=service.human.headers).status_code == 404
    service.id, service.url = original_id, original_url
    assert service.read()["submissions"] == [first]


@pytest.mark.parametrize("late", [False, True])
def test_correct_denial_of_independently_witnessed_original_requires_actual_signed_ground(service, late):
    rows = reports()
    if not late:
        rows[0][1]["content"]["unavailable_minutes"] = 504
        rows[0][1]["content_sha256"] = fingerprint(rows[0][1]["content"])
    deliver(service, rows)
    service.now = datetime(2027, 3, 8, tzinfo=UTC)
    original = dict(kind="original_filing_receipt", source_ref="portal-intake-27", receipt_id="outside-original",
                    observed_at=service.now.isoformat(), received_at="2027-03-07T00:00:00.000001Z" if late else "2027-03-06T09:00:00Z",
                    submitted_to="local-support", fields=[])
    deliver(service, [("vendor-fixture", original)])
    text = "Denied. Your filing arrived after the deadline." if late else "Denied. Service availability met the threshold."
    deliver(service, [("vendor-fixture", dict(kind="message", receipt_id=original["receipt_id"], text=text))])
    accept_explicitly(service)
    row = service.read()
    assert row["stage"] == "DENIAL_ACCEPTED", row
    assert row["actions"] == [] and row["submissions"] == []
    assert row["ledger"]["claimed"] == row["ledger"]["awarded"] == "0.00"


def accept_explicitly(app):
    """D06 (Q2 option A): a substantiated denial closes only through the explicit reviewer action."""
    pending = app.read()
    assert pending["stage"] == "DENIAL_REVIEW" and [a["id"] for a in pending["actions"]] == ["accept-denial"]
    return app.post(app.url + "/denial-acceptance", dict(basis_digest=pending["actions"][0]["basis_digest"]))
