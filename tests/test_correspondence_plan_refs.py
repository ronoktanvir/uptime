"""Public synthetic plan fields retain exact signed report and source authority."""
from datetime import timedelta
from copy import deepcopy
import json

import pytest

from uptime.auth import DEFAULT_ORIGIN
from uptime.auth_client import service_headers
from test_correspondence_filing_refs import filing, material, REFERENCES, CHANNEL, original_record
from test_correspondence_service import reports
from test_correspondence_resource import deliver


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
@pytest.mark.parametrize("reference", ["Marine", "invoice-7", "status-7", "service_invoice", "service_monitor"])
def test_declared_plan_can_cite_literal_or_existing_signed_plan_record(filing, reference):
    refs = REFERENCES | {"plan":[reference]}
    deliver(filing, reports())
    deliver(filing, [("customer-fixture", material(refs))])
    assert filing.read()["amount"] == "20.99", filing.read()["trace"]
    filing.action("approve-claim")
    original = filing.action("submit-claim")["submissions"][0]
    assert original["packet"]["filing_material"]["fields"] == refs
    deliver(filing, [("vendor-fixture", dict(kind="message", receipt_id=original["id"],
                                           text="Denied. We counted 500 minutes of downtime."))])
    assert filing.read()["stage"] == "RESPONSE_DRAFTED"
    filing.action("approve-response")
    filing.now += timedelta(days=1)
    row = filing.action("submit-response")
    assert row["stage"] == "AWAITING_VENDOR" and len(row["submissions"]) == 2


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
@pytest.mark.parametrize("reference", ["another-plan", "unknown-source", "compass-subscription", "compass-install"])
def test_plan_field_cannot_borrow_an_unrelated_or_line_only_reference(filing, reference):
    deliver(filing, reports())
    deliver(filing, [("customer-fixture", material(REFERENCES | {"plan":[reference]}))])
    assert filing.read()["amount"] is None and filing.read()["actions"] == []


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
@pytest.mark.parametrize("source_index", [0, 1])
@pytest.mark.parametrize("fault", ["wrong-plan", "missing-plan", "wrong-issuer", "wrong-scope", "missing-source"])
def test_plan_reference_requires_complete_exact_plan_and_scope_from_the_right_source(filing, source_index, fault):
    rows = reports()
    issuer, body = rows.pop(source_index)
    deliver(filing, rows)
    if fault == "wrong-plan":
        body["plan"] = "Different Plan"
        assert filing.source(issuer, body).status_code == 200
    elif fault == "missing-plan":
        body.pop("plan")
        assert filing.source(issuer, body).status_code == 422
    elif fault == "wrong-issuer":
        assert filing.source("customer-fixture", body).status_code == 403
    elif fault == "wrong-scope":
        scope = dict(filing.scope)
        for field, value in (("service", "Unrelated Feed"), ("account", "another-account"),
                             ("contract", "another-agreement"), ("month", "2027-01")):
            filing.scope = scope | {field:value}
            assert filing.source(issuer, body).status_code == 403
        filing.scope = scope
    deliver(filing, [("customer-fixture", material(REFERENCES | {"plan":[body["source_ref"]]}))])
    row = filing.read()
    assert row["amount"] is None and row["actions"] == []
    assert row["submissions"] == []


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
def test_unreviewed_edition_field_does_not_replace_the_declared_plan(filing):
    deliver(filing, reports())
    deliver(filing, [("customer-fixture", material(REFERENCES | {"edition":["invoice-7"]}))])
    assert filing.read()["amount"] is None and filing.read()["actions"] == []
    assert filing.read()["trace"] == ["Source-defined filing fields must each appear once."]


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
def test_missing_historical_plan_is_not_filled_by_the_current_signed_invoice(filing):
    deliver(filing, reports())
    refs = REFERENCES | {"plan":["invoice-7"]}
    deliver(filing, [("customer-fixture", material(refs))])
    current = filing.read()
    original = dict(kind="original_filing_receipt", source_ref="historical-plan-missing", receipt_id="historical-plan-missing",
        observed_at="2027-03-03T00:00:00Z", received_at="2027-03-02T13:00:00Z", submitted_to=CHANNEL,
        fields=material(REFERENCES)["fields"], contract_version=current["contract_version"],
        contract_source_sha256=current["contract_source_sha256"])
    deliver(filing, [("vendor-fixture", original)])
    saved = original_record(filing)
    deliver(filing, [("vendor-fixture", dict(kind="message", receipt_id=original["receipt_id"],
                                           text="Denied. Service availability met the threshold."))])
    after = filing.read()
    assert after["stage"] == "HUMAN_REVIEW" and after["actions"] == []
    assert original_record(filing) == saved
    assert after["ledger"]["claimed"] == after["ledger"]["awarded"] == "0.00"


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
@pytest.mark.parametrize("value,status", [("marine", 200), ("Marine  Plus", 200), ("Marine ", 422),
                                         (" Marine", 422), ("Marin\u00e9", 422), ("Marine\u0301", 422)])
def test_signed_plan_bytes_are_never_trimmed_casefolded_or_unicode_normalized(filing, value, status):
    rows = reports()
    source, body = rows.pop(1)
    body["plan"] = value
    deliver(filing, rows)
    assert filing.source(source, body).status_code == status
    deliver(filing, [("customer-fixture", material(REFERENCES | {"plan":["invoice-7"]}))])
    assert filing.read()["amount"] is None and filing.read()["actions"] == []


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
@pytest.mark.parametrize("different_plan", [False, True])
def test_literal_source_id_collision_cannot_manufacture_a_different_plan(filing, different_plan):
    rows = reports()
    rows[1][1]["source_ref"] = "Marine"
    if different_plan:
        rows[1][1]["plan"] = "Different Plan"
    deliver(filing, rows)
    refs = REFERENCES | {"service":["status-7"], "plan":["Marine"]}
    deliver(filing, [("customer-fixture", material(refs))])
    if different_plan:
        assert filing.read()["amount"] is None and filing.read()["actions"] == []
    else:
        assert filing.read()["amount"] == "20.99"
        filing.action("approve-claim")
        receipt = filing.action("submit-claim")["submissions"][0]
        assert receipt["packet"]["filing_material"]["fields"]["plan"] == ["Marine"]


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
@pytest.mark.parametrize("conflicting_plan", [False, True])
def test_citing_an_older_statement_does_not_choose_among_duplicate_kind_reports(filing, conflicting_plan):
    rows = reports()
    deliver(filing, rows)
    source, later = deepcopy(rows[1])
    later["source_ref"] = "newer-invoice"
    if conflicting_plan:
        later["plan"] = "Different Plan"
    assert filing.source(source, later, event_id="newer-invoice-event").status_code == 200
    deliver(filing, [("customer-fixture", material(REFERENCES | {"plan":["invoice-7"]}))])
    assert filing.read()["amount"] is None and filing.read()["actions"] == []
    assert filing.read()["trace"] == ["Contradictory or unauthenticated whole-service records."]


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
def test_plan_source_reference_cannot_outlive_its_signed_body_commitment(filing):
    source, body = reports()[1]
    path = filing.url + "/events"
    payload = dict(event_id="signed-plan-body", scope=filing.scope, body=body)
    original = json.dumps(payload).encode()
    headers = service_headers(instance=filing.app.state.auth.instance, origin=DEFAULT_ORIGIN, subject=source,
                              key=filing.keys[source], path=path, body=original)
    payload["body"] = body | {"plan":"Different Plan"}
    assert filing.client.post(path, content=json.dumps(payload).encode(), headers=headers).status_code == 403
    assert filing.read()["evidence"] == []
    deliver(filing, reports())
    deliver(filing, [("customer-fixture", material(REFERENCES | {"plan":["prepared-contents"]}))])
    assert filing.read()["amount"] is None and filing.read()["actions"] == []


@pytest.mark.parametrize("filing", ["plan"], indirect=True)
def test_valid_source_in_another_claim_is_not_a_plan_reference_for_this_join(filing):
    scope, claim_id, url = dict(filing.scope), filing.id, filing.url
    filing.scope = scope | {"account":"another-account"}
    filing.id = "inbox-another-plan-source"
    filing.url = "/api/correspondence/claims/" + filing.id
    # D04-C (2026-11-09): no terms are installed for the other account, so this test double declares the same
    # whole-service family for it; the assertion under test (no cross-claim plan reference) is unchanged.
    from unittest.mock import patch
    from uptime import claim_scope
    with patch.object(claim_scope, "_installed", lambda db, t, s: [{"manifest": {"family": "resource-month/1",
                                                                              "aggregate_monitor": True}, "overlay": {}}]):
        filing.provision()
        filing.create()
        source, body = reports()[1]
        body["source_ref"] = "other-account-source"
        assert filing.source(source, body).status_code == 200
    filing.scope, filing.id, filing.url = scope, claim_id, url
    deliver(filing, reports())
    deliver(filing, [("customer-fixture", material(REFERENCES | {"plan":["other-account-source"]}))])
    assert filing.read()["amount"] is None and filing.read()["actions"] == []


@pytest.mark.parametrize("filing", ["spaced-plan"], indirect=True)
def test_reviewed_display_plan_uses_existing_source_id_without_widening_wire_type(filing):
    rows = reports()
    for _, body in rows:
        body["plan"] = "Marine Plus"
    deliver(filing, rows)
    assert filing.source("customer-fixture", material(REFERENCES | {"plan":["Marine Plus"]})).status_code == 422
    refs = REFERENCES | {"plan":["invoice-7"]}
    deliver(filing, [("customer-fixture", material(refs))])
    assert filing.read()["amount"] == "20.99"
    filing.action("approve-claim")
    original = filing.action("submit-claim")["submissions"][0]
    assert original["packet"]["filing_material"]["fields"]["plan"] == ["invoice-7"]
