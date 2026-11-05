"""Signed independently arriving regional monitors and portal-delivery correction clocks."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from test_correspondence_resource import install, deliver, MONTH, OBSERVED
from test_v4_routes_integration import App
from test_vendor_resource import OVERLAY
from test_vendor_resource_scoped import ROW, subscription, facts


@pytest.fixture
def regional(tmp_path, monkeypatch):
    env = App(tmp_path / "regional.db", extra_roles={"custody-fixture":"customer"})
    env.scope.update(vendor="Copper Mesa Networks", account=OVERLAY["account"], contract=OVERLAY["agreement"],
                     service=OVERLAY["product"], component=OVERLAY["resource_id"], month="2026-06", region="North")
    env.now = datetime(2026, 7, 14, 19, tzinfo=UTC)
    env.provision()
    env.create()
    install(env, tmp_path, monkeypatch, extra_terms=ROW, shadow=facts(), expected="15.03", overlay_override=subscription())
    yield env
    env.client.close()


def regional_reports(*, complete=True):
    data = facts()
    rows = []
    for role, kind in (("customer", "customer_telemetry"), ("status", "provider_telemetry")):
        report = data[kind]
        body = dict(kind=kind, source_ref=report["ref"], source_id=report["source_id"], records=report["records"],
                    observed_at=OBSERVED, **(MONTH | {"complete":complete}))
        if role == "customer":
            body.update(exclusions_complete=True, exclusions=[])
        rows.append((role + "-fixture", body))
    rows.append(("custody-fixture", dict(kind="custodian_attestation", source_ref="custody-record",
                 source_id=data["customer_telemetry"]["source_id"], monitor_ref=data["customer_telemetry"]["ref"], observed_at=OBSERVED)))
    rows.append(("billing-fixture", dict(kind="resource_invoice", source_ref="statement-regional", observed_at=OBSERVED,
                 itemized_complete=True, lines=[{k:v for k,v in line.items() if k != "account"} for line in data["fee_lines"]])))
    rows.append(("customer-fixture", dict(kind="filing_material", source_ref="prepared-evidence", observed_at=OBSERVED,
                 channel="claims@example.invalid", fields=[dict(name="station identifier", refs=[OVERLAY["resource_id"]]),
                                                           dict(name="log references", refs=["local-radio-0"])])))
    return rows


def original(*, complete=False, late=False):
    fields = [dict(name="station identifier", refs=[OVERLAY["resource_id"]])]
    if complete:
        fields.append(dict(name="log references", refs=["local-radio-0"]))
    return dict(kind="original_filing_receipt", source_ref="portal-intake", receipt_id="historical-ticket",
                ticket_id="ticket-654", received_at="2026-07-10T18:00:01Z" if late else "2026-07-10T18:00:00Z",
                observed_at="2026-07-14T18:01:00Z", submitted_to="claims@example.invalid", fields=fields)


def portal_reply(env, text="Please attach the missing logs.", **changes):
    message = dict(kind="message", receipt_id="historical-ticket", text=text)
    result = env.source("vendor-fixture", message, event_id="independent-note")
    assert result.status_code == 200, result.text
    receipt = dict(kind="portal_response_receipt", source_ref="portal-delivery", original_ref="historical-ticket",
                   ticket_id="ticket-654", message_ref="independent-note", response_kind="evidence_request",
                   delivered_at="2026-07-14T18:01:00Z", observed_at="2026-07-14T18:02:00Z")
    receipt.update(changes)
    deliver(env, [("vendor-fixture", receipt)])


def test_independent_monitors_price_actual_intersection_and_paid_net_fees(regional):
    deliver(regional, regional_reports())
    assert regional.read()["preflight"]["outcome"] == "INSUFFICIENT_EVIDENCE"
    deliver(regional, [("vendor-fixture", original(complete=True))])
    row = regional.read()
    assert row["amount"] == "15.03", row
    assert row["stage"] == "HISTORICAL_FILING" and row["submissions"] == []
    assert row["ledger"]["claimed"] == row["ledger"]["awarded"] == "0.00"


@pytest.mark.parametrize("complete", [False, True])
def test_short_reply_and_separate_delivery_cure_on_original_ticket(regional, complete):
    deliver(regional, [("vendor-fixture", original())])
    deliver(regional, regional_reports(complete=complete))
    portal_reply(regional)
    row = regional.read()
    assert row["stage"] == "RESPONSE_DRAFTED", row
    assert row["historical_procedure"]["response_cutoff"] == "2026-07-18T18:01:00.000001+00:00"
    regional.action("approve-response")
    regional.now = datetime(2026, 7, 18, 18, 1, tzinfo=UTC)
    row = regional.action("submit-response")
    packet = row["submissions"][0]["packet"]
    assert packet["ticket_id"] == "ticket-654" and packet["response_ref"] == "portal-delivery"
    assert packet["filing_material"]["fields"] == {"log references":["local-radio-0"]}
    assert row["preflight"]["outcome"] == ("ELIGIBLE" if complete else "INSUFFICIENT_EVIDENCE"), row["trace"]
    assert row["ledger"]["claimed"] == row["ledger"]["awarded"] == "0.00"
    assert len(regional.action("submit-response")["submissions"]) == 1


@pytest.mark.parametrize("fault", ["late-original", "wrong-ticket", "wrong-message", "ambiguous", "expired", "wrong-custodian", "wrong-region", "unpaid"])
def test_incomplete_contradictory_or_expired_evidence_cannot_authorize_cure(regional, fault):
    rows = deepcopy(regional_reports())
    if fault == "wrong-custodian":
        rows[2] = ("customer-fixture", rows[2][1])
    if fault == "wrong-region":
        rows[1][1]["records"][0]["region"] = "South"
    if fault == "unpaid":
        rows[3][1]["lines"][0]["payment_state"] = "unpaid"
    deliver(regional, [("vendor-fixture", original(late=fault == "late-original"))])
    deliver(regional, rows)
    changes = {"ticket_id":"different-ticket"} if fault == "wrong-ticket" else {"message_ref":"another-note"} if fault == "wrong-message" else {}
    portal_reply(regional, "We are still reviewing." if fault == "ambiguous" else "Please attach the missing logs.", **changes)
    if fault == "expired":
        regional.now = datetime(2026, 7, 18, 18, 1, 0, 1, tzinfo=UTC)
    row = regional.read()
    if fault == "unpaid":
        assert row["preflight"]["outcome"] == "INSUFFICIENT_EVIDENCE"
    else:
        assert row["actions"] == [], row
    assert row["ledger"]["claimed"] == row["ledger"]["awarded"] == "0.00"
