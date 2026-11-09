"""Signed filing contents cite present scoped records, never display-name guesses.

New synthetic cases extend the committed Compass agreement. They contain no
private witness fixture, expected response, source signature or human authority.
"""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json

import pytest

from uptime.contracts import fingerprint
from uptime.storage import database
from uptime.vendor_model import MODEL
from test_v4_routes_integration import App
from test_vendor_service_month import ROWS, DOC, OVERLAY, facts
from test_correspondence_service import reports
from test_correspondence_resource import deliver


FIELDS = ["service", "subscription fee", "any compass installation charge"]
REFERENCES = {"service":["invoice-7"], "subscription fee":["compass-subscription"],
              "any compass installation charge":["compass-install"]}
CHANNEL = "claims@example.invalid"


@pytest.fixture
def filing(tmp_path, monkeypatch, request):
    env = App(tmp_path / "filing-references.db")
    env.now = datetime(2027, 3, 3, tzinfo=UTC)
    env.scope.update(vendor="Heliograph Navigation", account=OVERLAY["account"], contract=OVERLAY["agreement"],
                     service=OVERLAY["product"], month="2027-02")
    env.provision()
    env.create()
    rows = deepcopy(ROWS) + [("Send the claim to " + CHANNEL + ". Include service, subscription fee and any compass installation charge.",
                             {"submission_channel":CHANNEL, "request_fields":FIELDS})]
    plan_field = getattr(request, "param", None) in {"plan", "spaced-plan"}
    plan = "Marine Plus" if getattr(request, "param", None) == "spaced-plan" else OVERLAY["plan"]
    if plan != OVERLAY["plan"]:
        rows[1] = ("The Compass Feed service uses the Marine Plus plan.",
                   {"scope":{"product":"Compass Feed", "plan":plan}})
    if plan_field:
        rows[-1] = ("Send the claim to " + CHANNEL + ". Include service, plan, subscription fee and any compass installation charge.",
                    {"submission_channel":CHANNEL, "request_fields":[*FIELDS, "plan"]})
    if getattr(request, "param", None) == "ambiguous-categories":
        rows[6] = ("Exclude compass installation charges and compass installation fees.",
                   {"fee_exclusions":["compass installation charges", "compass installation fees"]})
    document = DOC | {"text":"\n".join(q for q, _ in rows)}
    proposal = [dict(quote=q, field="resource_terms", value=v) for q, v in rows]
    digest = sha256(document["text"].encode()).hexdigest()
    env.contract_source_hash = digest
    capture = dict(model=MODEL, source_sha256=digest, session="synthetic-filing-reference-regression",
                   at=env.now.isoformat(), proposal=proposal, proposal_sha256=fingerprint(proposal))
    (tmp_path / (digest + ".json")).write_text(json.dumps(capture))
    monkeypatch.setenv("UPTIME_PUBLIC_EXTRACTIONS", str(tmp_path))
    monkeypatch.setenv("UPTIME_MODEL_PROPOSITIONS", "1")
    prefix = "/api/vendors/filing-reference-control"
    from governing_binding_89 import reviewed_binding  # F5 (2026-11-09): unnamed-agreement source binding
    from test_vendor_service_month import manifest as compass_manifest
    state = env.post(prefix + "/candidates", dict(document=document,
                                                    overlay=reviewed_binding(compass_manifest(rows), OVERLAY | {"plan":plan})))
    assert state["state"] == "SHADOW", state
    from test_vendor_semantic_bindings import review_submission
    state=env.post(prefix+'/semantic-bindings',dict(revision=state['revision'],
        review=review_submission(state['manifest'],state['overlay'],document['text'])))
    positive = facts()
    positive["plan"] = plan
    for kind in ("service_invoice", "service_monitor", "filing_proof"):
        positive[kind]["plan"] = plan
    positive["filing_proof"]["fields"] = {k:", ".join(v) for k, v in REFERENCES.items()}
    if plan_field:
        positive["filing_proof"]["fields"]["plan"] = "invoice-7"
    negative = deepcopy(positive)
    negative["service_monitor"]["content"]["unavailable_minutes"] = 504
    negative["service_monitor"]["content_sha256"] = fingerprint(negative["service_monitor"]["content"])
    state = env.post(prefix + "/tests", dict(revision=state["revision"], tests=[
        dict(name="Complete recurring fee and separate excluded line", facts=positive, expected=dict(outcome="ELIGIBLE", amount="20.99")),
        dict(name="Exact monthly threshold equality", facts=negative, expected=dict(outcome="INELIGIBLE"))]))
    for operation in ("interpret", "approve", "activate"):
        action = next(a["id"] for a in state["actions"] if a["operation"] == operation)
        state = env.post(prefix + "/actions/" + action, {})
    yield env
    env.client.close()


def material(references=None):
    return dict(kind="filing_material", source_ref="prepared-contents", observed_at="2027-03-03T00:00:00Z",
                channel=CHANNEL, fields=[dict(name=name, refs=refs) for name, refs in (references or REFERENCES).items()])


def assert_unestablished_fields_cannot_accept_a_denial(env, references):
    current = env.read()
    original = dict(kind="original_filing_receipt", source_ref="rejected-field-original", receipt_id="rejected-field-original",
        observed_at="2027-03-03T00:00:00Z", received_at="2027-03-02T13:00:00Z", submitted_to=CHANNEL,
        fields=material(references)["fields"], contract_version=current["contract_version"],
        contract_source_sha256=current["contract_source_sha256"])
    deliver(env, [("vendor-fixture", original)])
    deliver(env, [("vendor-fixture", dict(kind="message", receipt_id=original["receipt_id"],
                                         text="Denied. Service availability met the threshold."))])
    row = env.read()
    assert row["stage"] == "HUMAN_REVIEW" and row["actions"] == []
    assert row["ledger"]["claimed"] == row["ledger"]["awarded"] == "0.00"


def original_record(env):
    with database(env.inbox.path) as db:
        raw = db.execute("SELECT state FROM inbox_claim WHERE tenant=? AND id=?", ("bears", env.id)).fetchone()[0]
    return next(event for event in json.loads(raw)["evidence"] if event["kind"] == "original_filing_receipt")


@pytest.mark.parametrize("references", [REFERENCES,
    {"service":["status-7"], "subscription fee":["invoice-7"], "any compass installation charge":["invoice-7"]},
    {"service":["service_monitor"], "subscription fee":["service_invoice"], "any compass installation charge":["compass-install"]},
])
def test_signed_source_and_matching_line_refs_support_actual_original_and_denial(filing, references):
    deliver(filing, reports())
    deliver(filing, [("customer-fixture", material(references))])
    assert filing.read()["amount"] == "20.99", filing.read()["trace"]
    filing.action("approve-claim")
    original = filing.action("submit-claim")["submissions"][0]
    assert original["packet"]["filing_material"]["fields"] == references
    response = filing.source("vendor-fixture", dict(kind="message", receipt_id=original["id"],
                              text="Denied. We counted 500 minutes of downtime."), event_id="independent-denial")
    assert response.status_code == 200, response.text
    assert filing.read()["stage"] == "RESPONSE_DRAFTED"
    filing.action("approve-response")
    filing.now += timedelta(days=1)
    row = filing.action("submit-response")
    assert row["stage"] == "AWAITING_VENDOR" and len(row["submissions"]) == 2
    assert row["submissions"][1]["packet"]["in_reply_to"] == original["id"]


@pytest.mark.parametrize("field,reference", [
    ("service", "unknown-source"), ("service", "compass-install"),
    ("subscription fee", "status-7"), ("subscription fee", "compass-install"),
    ("any compass installation charge", "compass-subscription"),
    ("any compass installation charge", "absent-row"),
])
def test_unrelated_same_scope_or_unknown_refs_cannot_complete_a_field(filing, field, reference):
    deliver(filing, reports())
    refs = REFERENCES | {field:[reference]}
    deliver(filing, [("customer-fixture", material(refs))])
    row = filing.read()
    assert row["amount"] is None and row["actions"] == []
    assert row["outcome"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.parametrize("fault", ["missing-excluded-row", "wrong-excluded-category", "missing-recurring-row", "missing-invoice"])
def test_a_real_invoice_reference_cannot_supply_an_absent_matching_fee(filing, fault):
    rows = reports()
    invoice = rows[1][1]
    if fault == "missing-excluded-row":
        invoice["content"]["lines"].pop(1)
    elif fault == "wrong-excluded-category":
        invoice["content"]["lines"][1]["category"] = "other unrelated charge"
    elif fault == "missing-recurring-row":
        invoice["content"]["lines"].pop(0)
    else:
        rows.pop(1)
    invoice["content_sha256"] = fingerprint(invoice["content"])
    deliver(filing, rows)
    refs = {field:["invoice-7"] for field in FIELDS}
    deliver(filing, [("customer-fixture", material(refs))])
    assert filing.read()["amount"] is None and filing.read()["actions"] == []
    assert_unestablished_fields_cannot_accept_a_denial(filing, refs)


def test_display_name_does_not_relax_wire_id_or_signed_source_scope(filing):
    body = reports()[1][1]
    assert filing.source("status-fixture", body).status_code == 403
    original = dict(filing.scope)
    filing.scope["service"] = "Unrelated Display Service"
    assert filing.source("billing-fixture", body).status_code == 403
    filing.scope = original
    assert filing.read()["evidence"] == []
    deliver(filing, reports())
    spaced = material(REFERENCES | {"service":[filing.scope["service"]]})
    assert filing.source("customer-fixture", spaced).status_code == 422
    assert len(filing.read()["evidence"]) == 2


def test_signed_original_retains_exact_fields_and_pins_through_valid_threshold_denial(filing):
    rows = reports()
    rows[0][1]["content"]["unavailable_minutes"] = 504
    rows[0][1]["content_sha256"] = fingerprint(rows[0][1]["content"])
    deliver(filing, rows)
    deliver(filing, [("customer-fixture", material())])
    reviewed = filing.read()
    assert reviewed["contract_source_sha256"] == filing.contract_source_hash
    original = dict(kind="original_filing_receipt", source_ref="outside-source-receipt", receipt_id="outside-original",
        observed_at="2027-03-03T00:00:00Z", received_at="2027-03-02T13:00:00Z", submitted_to=CHANNEL,
        fields=material()["fields"], contract_version=reviewed["contract_version"], contract_source_sha256=reviewed["contract_source_sha256"])
    deliver(filing, [("vendor-fixture", original)])
    before = filing.read()["evidence"][-1]
    immutable = original_record(filing)
    deliver(filing, [("vendor-fixture", dict(kind="message", receipt_id="outside-original",
                                           text="Denied. Service availability met the threshold."))])
    after = filing.read()
    assert after["stage"] == "DENIAL_ACCEPTED" and after["actions"] == []
    assert after["evidence"][-2] == before
    assert original_record(filing) == immutable
    assert after["ledger"]["claimed"] == after["ledger"]["awarded"] == "0.00"


@pytest.mark.parametrize("original_fields", [[], [dict(name="service", refs=["status-7"])]])
def test_current_complete_sources_cannot_reconstruct_missing_original_filing_contents(filing, original_fields):
    rows = reports()
    rows[0][1]["content"]["unavailable_minutes"] = 504
    rows[0][1]["content_sha256"] = fingerprint(rows[0][1]["content"])
    deliver(filing, rows)
    deliver(filing, [("customer-fixture", material())])
    reviewed = filing.read()
    original = dict(kind="original_filing_receipt", source_ref="incomplete-original-record", receipt_id="incomplete-original",
        observed_at="2027-03-03T00:00:00Z", received_at="2027-03-02T13:00:00Z", submitted_to=CHANNEL,
        fields=original_fields, contract_version=reviewed["contract_version"], contract_source_sha256=reviewed["contract_source_sha256"])
    deliver(filing, [("vendor-fixture", original)])
    deliver(filing, [("vendor-fixture", dict(kind="message", receipt_id="incomplete-original",
                                           text="Denied. Service availability met the threshold."))])
    after = filing.read()
    assert after["stage"] == "HUMAN_REVIEW" and after["actions"] == []
    assert after["amount"] is None and after["submissions"] == []


@pytest.mark.parametrize("fault", ["reinstallation", "installation-credit", "credit-kind", "voided-kind", "reversed-kind", "multiple-matches"])
def test_related_or_reversed_or_ambiguous_fee_rows_cannot_satisfy_the_declared_field(filing, fault):
    rows = reports()
    invoice = rows[1][1]
    line = invoice["content"]["lines"][1]
    if fault == "reinstallation":
        line["category"] = "compass reinstallation charges"
    elif fault == "installation-credit":
        line["category"] = "compass installation credit"
    elif fault.endswith("-kind"):
        line["kind"] = fault.removesuffix("-kind")
    else:
        invoice["content"]["lines"].append(line | {"ref":"another-installation"})
    invoice["content_sha256"] = fingerprint(invoice["content"])
    deliver(filing, rows)
    deliver(filing, [("customer-fixture", material({field:["invoice-7"] for field in FIELDS}))])
    row = filing.read()
    assert row["amount"] is None and row["actions"] == []
    assert row["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert_unestablished_fields_cannot_accept_a_denial(filing, {field:["invoice-7"] for field in FIELDS})


@pytest.mark.parametrize("field", ["any compass reinstallation fee", "any compass installation credit", "any undeclared coaching fee"])
def test_filing_material_cannot_choose_an_unreviewed_category(filing, field):
    deliver(filing, reports())
    refs = dict(REFERENCES)
    refs[field] = refs.pop("any compass installation charge")
    deliver(filing, [("customer-fixture", material(refs))])
    row = filing.read()
    assert row["amount"] is None and row["actions"] == []
    assert row["trace"] == ["Source-defined filing fields must each appear once."]


@pytest.mark.parametrize("change", [{"amount_cents":-1}, {"voided":True}, {"reversed":True},
                                    {"service":"Unrelated Service"}, {"service_id":"another-service"}])
def test_strict_signed_invoice_schema_rejects_unsupported_line_state_and_multiservice_fields(filing, change):
    invoice = reports()[1][1]
    invoice["content"]["lines"][1].update(change)
    invoice["content_sha256"] = fingerprint(invoice["content"])
    result = filing.source("billing-fixture", invoice)
    assert result.status_code == 422
    assert filing.read()["evidence"] == []


@pytest.mark.parametrize("filing", ["ambiguous-categories"], indirect=True)
def test_overlapping_declared_category_phrases_do_not_choose_a_fee(filing):
    deliver(filing, reports())
    deliver(filing, [("customer-fixture", material())])
    assert filing.read()["amount"] is None and filing.read()["actions"] == []
    assert_unestablished_fields_cannot_accept_a_denial(filing, REFERENCES)


def test_duplicate_signed_field_cannot_override_the_reviewed_reference(filing):
    deliver(filing, reports())
    body = material()
    body["fields"].append(dict(name="subscription fee", refs=["compass-install"]))
    deliver(filing, [("customer-fixture", body)])
    assert filing.read()["amount"] is None and filing.read()["actions"] == []
