"""Source-authenticated resource evidence and independently verified supplemental documents."""
from copy import deepcopy
from datetime import UTC,datetime,timedelta
from hashlib import sha256
import json

import pytest

from uptime.contracts import fingerprint
from uptime.vendor_model import MODEL
from test_v4_routes_integration import App
from test_vendor_resource import ROWS, OVERLAY, FACTS

OBSERVED = "2026-07-01T06:00:00Z"
MONTH = dict(start="2026-06-01T00:00:00Z",end="2026-07-01T00:00:00Z",complete=True)


def install(env, tmp_path, monkeypatch, *, cycles=False, whole_day=False, conditions=False, extra_terms=(), shadow=None, expected="12.51", overlay_override=None, installation="altitude-service"):
    rows=deepcopy(ROWS) + list(extra_terms)
    facts=deepcopy(shadow if shadow is not None else FACTS)
    overlay = deepcopy(overlay_override if overlay_override is not None else OVERLAY)
    if cycles:
        overlay.pop("billing_period", None)
        rows[3]=("Each station has its own availability measurement over each UTC calendar month.",
                 {"period":"resource_utc_calendar_month"})
        rows[9]=("Credit requests are due by the close of the second full billing cycle after the service month.",
                 {"filing":{"kind":"billing_cycles","count":2,"utc_time":None,"endpoint":"whole_cycle"}})
        facts["billing_cycles"] = [dict(ref="c1",start="2026-07-01T00:00:00Z",end="2026-07-19T00:00:00Z"),
                                   dict(ref="c2",start="2026-07-19T00:00:00Z",end="2026-08-18T00:00:00Z")]
    if whole_day:
        rows[9]=("Credit requests must be received by the end of the tenth calendar day after the service month.",
                 {"filing":{"kind":"calendar_days","count":10,"utc_time":None,"endpoint":"whole_day"}})
    if conditions:
        rows.append(("Customers in breach of their agreement are ineligible to file a claim.",
                     {"account_conditions":[dict(op="contract_noncompliance", effect="filing_precondition",
                                                 phrase="breach of their agreement")]}))
        facts["condition_evidence"] = [dict(agreement=OVERLAY["agreement"], account=OVERLAY["account"],
            resource_id=OVERLAY["resource_id"], month="2026-06", verified=True, finding="clear", affected_refs=[],
            op="contract_noncompliance", ref="status-reviewed", terms_reviewed=True, terms_ref="clause-3",
            terms_sha256=sha256(b"local customer terms").hexdigest())]
    proposal=[{"quote":quote,"field":"resource_terms","value":v} for quote,v in rows]
    text="\n".join(q for q,_ in rows)
    digest=sha256(text.encode()).hexdigest()
    capture=dict(model=MODEL,source_sha256=digest,session="synthetic-test-resource-join",at=OBSERVED,
                 proposal=proposal,proposal_sha256=fingerprint(proposal))
    (tmp_path/(digest+".json")).write_text(json.dumps(capture))
    monkeypatch.setenv("UPTIME_PUBLIC_EXTRACTIONS",str(tmp_path))
    monkeypatch.setenv("UPTIME_MODEL_PROPOSITIONS","1")
    base="/api/vendors/" + installation
    s=env.post(base+"/candidates",dict(document=dict(name="Synthetic station SLA",uri="urn:synthetic:weather",
                    classification="synthetic_public",text=text),overlay=overlay))
    assert s["state"]=="SHADOW",s
    from test_vendor_semantic_bindings import review_submission
    s=env.post(base+'/semantic-bindings',dict(revision=s['revision'],
        review=review_submission(s['manifest'],s['overlay'],text)))
    negative = deepcopy(facts)
    negative["intervals"] = []
    if "provider_telemetry" in negative:
        negative["provider_telemetry"].update(records=[], no_events_verified=True)
    tests=[dict(name="verified scoped outage",facts=facts,expected=dict(outcome="ELIGIBLE",amount=expected)),
           dict(name="no incident",facts=negative,expected=dict(outcome="INELIGIBLE"))]
    s=env.post(base+"/tests",dict(revision=s["revision"],tests=tests))
    for op in ("interpret","approve","activate"):
        action=next(a["id"] for a in s["actions"] if a["operation"]==op)
        s=env.post(base+"/actions/"+action,{})
    return s


@pytest.fixture
def env(tmp_path):
    e=App(tmp_path/"resource.db")
    e.now=datetime(2026,7,4,tzinfo=UTC)
    e.scope.update(vendor="Copper Mesa Networks",account=OVERLAY["account"],contract=OVERLAY["agreement"],
                   service=OVERLAY["product"],component=OVERLAY["resource_id"],month="2026-06",
                   invoice="inv-614",incident="sig-133")
    e.provision(); e.create()
    yield e
    e.client.close()


def reports():
    symptom=[{k:r[k] for k in ("ref","resource_id","start","end","symptom")} for r in FACTS["intervals"]]
    causes=[{k:r[k] for k in ("ref","resource_id","start","end","cause")} for r in FACTS["intervals"]]
    exclusions=[{k:r[k] for k in ("ref","resource_id","start","end","cause")} for r in FACTS["exclusions"]]
    fees=[{k:v for k,v in line.items() if k!="account"} for line in FACTS["fee_lines"] if line["resource_id"]==OVERLAY["resource_id"]]
    return [
        ("status-fixture",dict(kind="resource_status",source_ref="status-111",observed_at=OBSERVED,intervals=symptom,**MONTH)),
        ("customer-fixture",dict(kind="resource_attribution",source_ref="ledger-18",observed_at=OBSERVED,causes=causes,exclusions=exclusions,**MONTH)),
        ("billing-fixture",dict(kind="resource_invoice",source_ref="dated-billing",observed_at=OBSERVED,itemized_complete=True,lines=fees)),
        ("customer-fixture",dict(kind="filing_material",source_ref="filing-contents",observed_at=OBSERVED,channel="claims@example.invalid",
                           fields=[dict(name="station identifier",refs=[OVERLAY["resource_id"]]),dict(name="log references",refs=["n1","n2"])])),
    ]


def deliver(e, rows):
    for source,body in rows:
        result=e.source(source,body)
        assert result.status_code==200,result.text


def setup_filed(e, tmp_path, monkeypatch):
    install(e,tmp_path,monkeypatch)
    deliver(e,reports())
    assert e.read()["amount"]=="12.51"
    e.action("approve-claim")
    return e.action("submit-claim")["submissions"][0]


def message(e,receipt,text):
    response=e.source("vendor-fixture",dict(kind="message",receipt_id=receipt["id"],text=text),event_id="vendor-reply")
    assert response.status_code==200,response.text
    return e.read()


def artifact_records(content, *, ref="RL-84", kind="resource_log", linked="n1"):
    digest=sha256(content.encode()).hexdigest()
    common=dict(artifact_type=kind,artifact_ref=ref,body_sha256=digest,observed_at=OBSERVED)
    return [("customer-fixture",dict(kind="artifact",source_ref="archive-copy",content=content,**common)),
            ("billing-fixture" if kind=="invoice_detail" else "status-fixture",
             dict(kind="billing_verification" if kind=="invoice_detail" else "status_verification",
                  source_ref="verified-export",linked_ref=linked,**common))]


def test_real_resource_join_and_local_packet(env,tmp_path,monkeypatch):
    rec=setup_filed(env,tmp_path,monkeypatch)
    assert rec["requested"]=="12.51"
    assert rec["packet"]["filing_cutoff"]=="2026-07-10T18:00:00.000001+00:00"
    assert rec["packet"]["filing_material"]["fields"]["log references"]==["n1","n2"]
    assert rec["packet"]["destination"]=="isolated-local-simulator"
    row=message(env,rec,"We have approved a service credit of USD 9.00.")
    assert row["ledger"]["awarded"]=="9.00" and row["ledger"]["disputed_remainder"]=="3.51"


def test_region_alias_without_separate_contractual_coverage_cannot_create_another_intake(env, tmp_path, monkeypatch):
    install(env, tmp_path, monkeypatch)
    env.scope["region"] = "another-region"
    env.provision()
    result = env.human.post("/api/correspondence/claims", dict(claim_id="inbox-region-alias", scope=env.scope))
    assert result.status_code == 409


@pytest.mark.parametrize("fault",["wrong-cause-scope","wrong-fee-resource","unknown-cause","unmapped-packet","incomplete-fees"])
def test_conflicting_raw_source_stops_before_claim(env,tmp_path,monkeypatch,fault):
    install(env,tmp_path,monkeypatch)
    rows=reports()
    if fault=="wrong-cause-scope":
        rows[1][1]["causes"][0]["start"]="2026-06-06T00:00:00Z"
    elif fault=="wrong-fee-resource":
        rows[2][1]["lines"][0]["resource_id"]="station-22"
    elif fault=="unknown-cause":
        rows[1][1]["causes"][0]["cause"]="unsubstantiated"
    elif fault=="unmapped-packet":
        rows[3][1]["fields"][0]["refs"]=["wrong-station"]
    else:
        rows[2][1]["itemized_complete"]=False
    deliver(env,rows)
    assert env.read()["outcome"]=="INSUFFICIENT_EVIDENCE" and not env.read()["actions"]


def test_noncalendar_billing_cycles_require_signed_contiguous_schedule(env,tmp_path,monkeypatch):
    install(env,tmp_path,monkeypatch,cycles=True)
    deliver(env,reports())
    assert env.read()["outcome"]=="INSUFFICIENT_EVIDENCE"
    deliver(env,[("billing-fixture",dict(kind="billing_calendar",source_ref="schedule-u",observed_at=OBSERVED,
                    cycles=[dict(ref="c1",start="2026-07-01T00:00:00Z",end="2026-07-19T00:00:00Z"),
                            dict(ref="c2",start="2026-07-19T00:00:00Z",end="2026-08-18T00:00:00Z")]))])
    assert env.read()["amount"]=="12.51"
    assert env.read()["filing_cutoff"]=="2026-08-18T00:00:00+00:00"


@pytest.mark.parametrize("vendor_text,kind,ref,linked",[
    ("Please furnish the dated service log, document RL-84.","resource_log","RL-84","n1"),
    ("We lack the itemized invoice. Please supply record FE-21.","invoice_detail","FE-21","line-weather"),
    ("We need attachment SH-355.","scope_mapping","SH-355","status-111"),
])
def test_named_and_typed_supporting_artifacts_require_two_sources(env,tmp_path,monkeypatch,vendor_text,kind,ref,linked):
    rec=setup_filed(env,tmp_path,monkeypatch)
    assert message(env,rec,vendor_text)["stage"]=="NEEDS_EVIDENCE"
    content="Private customer support notes. SENTINEL-NEVER-DISCLOSE-11."
    rows=artifact_records(content,ref=ref,kind=kind,linked=linked)
    deliver(env,rows[:1])
    assert not env.read()["actions"]
    deliver(env,rows[1:])
    assert env.read()["stage"]=="RESPONSE_DRAFTED"
    env.action("approve-response")
    env.now+=timedelta(days=1)
    row=env.action("submit-response")
    doc=row["submissions"][1]["packet"]["disclosed_artifact"]
    assert doc["ref"]==ref and doc["sha256"]==sha256(content.encode()).hexdigest()
    assert "SENTINEL" not in json.dumps(row["submissions"]) and len(row["submissions"])==2


def test_vendor_wrong_explicit_identifier_rechecked_against_filed_scope(env,tmp_path,monkeypatch):
    rec=setup_filed(env,tmp_path,monkeypatch)
    row=message(env,rec,"We declined the claim because this invoice belongs to account AC-991.")
    assert row["stage"]=="RESPONSE_DRAFTED"
    env.action("approve-response")
    env.now+=timedelta(days=1)
    packet=env.action("submit-response")["submissions"][1]["packet"]
    assert packet["verified_scope_field"]=="account" and "AC-991" not in json.dumps(packet)


def test_private_content_digest_and_independent_verifier_scope(env,tmp_path,monkeypatch):
    rec=setup_filed(env,tmp_path,monkeypatch)
    message(env,rec,"We need service logs.")
    doc,proof=artifact_records("actual local bytes")
    bad=doc[1]|{"content":"changed caller body"}
    assert env.source(doc[0],bad).status_code==409
    deliver(env,[doc])
    assert env.source("customer-fixture",proof[1]).status_code==403
    deliver(env,[(proof[0],proof[1]|{"linked_ref":"unrelated-ref"})])
    assert not env.read()["actions"]


def test_independent_resource_vendor_rechecks_private_records_and_verified_attachment(env,tmp_path,monkeypatch):
    from dataclasses import replace
    from decimal import Decimal
    from uptime.correspondence_vendor import ResourceVendorRecord, adjudicate_resource
    from uptime.correspondence_types import Scope

    rec=setup_filed(env,tmp_path,monkeypatch)
    content="Synthetically archived station logs; confidential operator annotations."
    private=ResourceVendorRecord("bears",Scope.model_validate(env.scope),"altitude service schedule","2026-07-10T18:00:00.000001Z",
        (("2026-06-05T00:00:00Z","2026-06-05T08:20:00Z"),("2026-06-05T06:40:00Z","2026-06-05T10:00:00Z")),
        (("2026-06-05T01:40:00Z","2026-06-05T04:27:00Z"),),(("service",10004),("tax",1200)),
        frozenset({"service"}),((Decimal(98),Decimal(45)),(Decimal(99),Decimal("12.5"))),True,
        "RL-84","resource_log",sha256(content.encode()).hexdigest())
    assert message(env,rec,adjudicate_resource(rec["packet"],private,env.now))["stage"]=="NEEDS_EVIDENCE"
    deliver(env,artifact_records(content))
    env.action("approve-response");env.now+=timedelta(days=1)
    final=env.action("submit-response")["submissions"][1]
    assert "cannot verify" in adjudicate_resource(final["packet"],replace(private,trusted_body_sha256="0"*64),env.now)
    answer=adjudicate_resource(final["packet"],private,env.now)
    response=env.source("vendor-fixture",dict(kind="message",receipt_id=final["id"],text=answer),event_id="outcome-2")
    assert response.status_code==200
    assert env.read()["stage"]=="AWARDED" and env.read()["ledger"]["awarded"]=="12.51"


def test_date_only_contract_keeps_full_last_day_open(env,tmp_path,monkeypatch):
    install(env,tmp_path,monkeypatch,whole_day=True)
    deliver(env,reports())
    env.now=datetime(2026,7,10,23,59,59,999999,tzinfo=UTC)
    assert env.read()["amount"]=="12.51" and env.read()["filing_cutoff"]=="2026-07-11T00:00:00+00:00"
    env.action("approve-claim")
    env.now+=timedelta(microseconds=1)
    assert env.read()["outcome"]=="INELIGIBLE" and not env.read()["actions"]
    assert env.human.post(env.url+"/actions/submit-claim",{}).status_code==409


def test_mixed_attachment_identifiers_escalate(env,tmp_path,monkeypatch):
    rec=setup_filed(env,tmp_path,monkeypatch)
    assert message(env,rec,"Please furnish document AC-111 and attachment AC-112.")["stage"]=="HUMAN_REVIEW"

def test_swapping_existing_resource_and_billing_refs_cannot_satisfy_filing_fields(env, tmp_path, monkeypatch):
    install(env, tmp_path, monkeypatch)
    rows = reports()
    rows[-1][1]["fields"][0]["refs"] = ["line-weather"]
    rows[-1][1]["fields"][1]["refs"] = [OVERLAY["resource_id"]]
    deliver(env, rows)
    assert env.read()["outcome"] == "INSUFFICIENT_EVIDENCE" and not env.read()["actions"]


@pytest.mark.parametrize("finding,expected", [("clear", "ELIGIBLE"), ("applies", "INELIGIBLE"),
                                              ("unresolved", "INSUFFICIENT_EVIDENCE")])
def test_scoped_customer_finding_and_pinned_terms_control_active_filing(env, tmp_path, monkeypatch, finding, expected):
    install(env, tmp_path, monkeypatch, conditions=True)
    deliver(env, reports())
    assert env.read()["outcome"] == "INSUFFICIENT_EVIDENCE"
    content = "Local customer terms. PRIVATE-DO-NOT-SEND-1729"
    terms = dict(ref="governing-packet-17", sha256=sha256(content.encode()).hexdigest(), content=content)
    record = dict(op="contract_noncompliance", ref="local-finding", finding=finding, affected_refs=[], reviewed_terms=terms)
    body = dict(kind="account_conditions", observed_at=OBSERVED, source_ref="customer-admin", findings=[record])
    assert env.source("vendor-fixture", body).status_code == 403
    bad = deepcopy(body)
    bad["findings"][0]["reviewed_terms"]["content"] = "different bytes"
    assert env.source("customer-fixture", bad).status_code == 409
    deliver(env, [("customer-fixture", body)])
    assert env.read()["outcome"] == expected
    if expected == "ELIGIBLE":
        env.action("approve-claim")
        packet = env.action("submit-claim")["submissions"][0]["packet"]
        assert content not in json.dumps(packet)
    else:
        assert not env.read()["actions"]


def test_availability_denial_rebuttal_contains_independently_measured_countable_time(env, tmp_path, monkeypatch):
    initial = setup_filed(env, tmp_path, monkeypatch)
    row = message(env, initial, "Our measured availability exceeded the contractual target. We decline the claim.")
    assert row["stage"] == "RESPONSE_DRAFTED"
    assert len(row["submissions"]) == 1 and row["ledger"]["awarded"] == "0.00"
    env.action("approve-response")
    env.now += timedelta(days=1)
    packet = env.action("submit-response")["submissions"][1]["packet"]
    assert packet["verified_measurement"] == dict(downtime_microseconds=433*60_000_000,
                                                   total_microseconds=30*86400*1_000_000)
    assert packet["in_reply_to"] == initial["id"]


@pytest.mark.parametrize("additional,stage", [
    ("", "RESPONSE_DRAFTED"),
    (" Thank you for your patience.", "RESPONSE_DRAFTED"),
    (" You waived all service credit claims in a separate settlement agreement.", "HUMAN_REVIEW"),
    (" A separate commercial condition prevents this remedy.", "HUMAN_REVIEW"),
    (" Your subscription was cancelled before this month.", "HUMAN_REVIEW"),
])
def test_signed_compound_denial_requires_every_substantive_ground_to_be_understood(env, tmp_path, monkeypatch, additional, stage):
    initial = setup_filed(env, tmp_path, monkeypatch)
    text = "We denied your claim because we measured 5 minutes of downtime." + additional
    row = message(env, initial, text)
    assert row["stage"] == stage
    assert row["replies"][-1]["text"] == text
    if stage == "HUMAN_REVIEW":
        assert row["replies"][-1]["reason"] == "unknown" and row["actions"] == []
        assert env.human.post(env.url + "/actions/approve-response", {}).status_code == 409
    assert len(row["submissions"]) == 1 and row["ledger"]["awarded"] == "0.00"


def test_conditional_statements_require_complete_matching_history():
    from uptime.correspondence_resource import append_monthly_reports
    from uptime.correspondence_types import Scope, instant

    scope = Scope.model_validate(dict(account="account-71", vendor="Utility", contract="terms-a",
        service="Network", component="station-21", invoice="inv-1", incident="n1",
        currency="USD", month="2026-06", region="east"))
    credit = dict(ref="bill-line-2", credit_id="credit-17", agreement=scope.contract, account=scope.account,
                  resource_id=scope.component, month=scope.month, currency=scope.currency, amount_cents=180, state="issued")
    notice = dict(ref="advisory-4", account=scope.account, resource_id=scope.component,
                  start="2026-06-17T01:00:00Z", end="2026-06-17T04:00:00Z", announced_at="2026-06-15T01:00:00Z")
    report = dict(complete=True, observed_at=OBSERVED, source_ref="private-op")
    groups = dict(maintenance_evidence=dict(body=report | {"records":[notice]}),
                  prior_credit_evidence=dict(body=report | {"records":[credit]}))
    manifest = dict(maintenance={"basis":"within_announced_window"}, prior_credit="subtract_issued_same_resource_month")
    facts = {}
    append_monthly_reports(facts, groups, manifest, scope, instant(MONTH["end"]))
    assert facts["maintenance_evidence"]["records"] == [notice]
    assert facts["prior_credit_evidence"]["records"] == [credit]
    for bad in [[credit | {"account":"other"}], [credit, credit | {"ref": "alias", "amount_cents": 181}]]:
        groups["prior_credit_evidence"]["body"]["records"] = bad
        with pytest.raises(ValueError):
            append_monthly_reports({}, groups, manifest, scope, instant(MONTH["end"]))


def install_statements(env, tmp_path, monkeypatch):
    from test_vendor_resource_operators import EXTENSION, readings
    facts = readings()
    install(env, tmp_path, monkeypatch, extra_terms=EXTENSION, shadow=facts, expected="10.44")
    rows = reports()
    rows[0][1]["intervals"] = [{k:r[k] for k in ("ref","resource_id","start","end","symptom")} for r in facts["intervals"]]
    rows[1][1]["causes"] = [{k:r[k] for k in ("ref","resource_id","start","end","cause")} for r in facts["intervals"]]
    rows[1][1]["exclusions"] = []
    rows[2][1]["lines"] = [{k:v for k,v in r.items() if k != "account"} for r in facts["fee_lines"]]
    rows[3][1]["fields"][1]["refs"] = ["reader-A", "reader-B"]
    deliver(env, rows)
    assert env.read()["outcome"] == "INSUFFICIENT_EVIDENCE"
    notice, prior = (dict(kind=k, source_ref=facts[k]["ref"], observed_at=OBSERVED, complete=True,
                          records=facts[k]["records"]) for k in ("maintenance_evidence", "prior_credit_evidence"))
    prior["records"] = [r for r in prior["records"] if r["resource_id"] == env.scope["component"] and r["month"] == env.scope["month"]]
    deliver(env, [("customer-fixture", notice)])
    assert env.read()["outcome"] == "INSUFFICIENT_EVIDENCE"
    deliver(env, [("billing-fixture", prior)])
    assert env.read()["amount"] == "10.44"


@pytest.mark.parametrize("credit_id,expected", [(None,"HUMAN_REVIEW"), ("credit-A", "HUMAN_REVIEW"),
                                               ("fresh-resource-award", "PARTIAL_AWARD_REVIEW")])
def test_signed_previous_issuance_and_maintenance_control_residual_and_new_award(env, tmp_path, monkeypatch, credit_id, expected):
    install_statements(env, tmp_path, monkeypatch)
    env.action("approve-claim")
    rec = env.action("submit-claim")["submissions"][0]
    assert rec["requested"] == "10.44"
    body = dict(kind="message", receipt_id=rec["id"], text="We have approved a service credit of USD 2.31.")
    if credit_id:
        body["credit_id"] = credit_id
    deliver(env, [("vendor-fixture", body)])
    result = env.read()
    assert result["stage"] == expected
    assert result["ledger"]["awarded"] == ("2.31" if expected == "PARTIAL_AWARD_REVIEW" else "0.00")


def test_mistaken_resource_maintenance_denial_uses_only_residual_counted_time(env, tmp_path, monkeypatch):
    install_statements(env, tmp_path, monkeypatch)
    env.action("approve-claim")
    initial = env.action("submit-claim")["submissions"][0]
    assert message(env, initial, "Claim denied because this was scheduled maintenance.")["stage"] == "RESPONSE_DRAFTED"
    env.action("approve-response")
    env.now += timedelta(days=1)
    rec = env.action("submit-response")["submissions"][1]
    assert rec["packet"]["verified_measurement"]["downtime_microseconds"] == 530*60_000_000
    assert env.read()["preflight"]["outcome"] == "ELIGIBLE"
    assert env.read()["ledger"]["claimed"] == "10.44"


@pytest.mark.parametrize("when,expected", [("2026-07-10T18:00:00Z", "ELIGIBLE"),
                                            ("2026-07-10T18:00:00.000001Z", "INELIGIBLE")])
def test_historical_incomplete_filing_and_independently_arriving_supplement(env, tmp_path, monkeypatch, when, expected):
    install_statements(env, tmp_path, monkeypatch)
    env.now = datetime(2026, 7, 12, tzinfo=UTC)
    destination = "claims@example.invalid"
    common = dict(observed_at=env.now.isoformat(), submitted_to=destination)
    supplement = dict(kind="supplement_filing_receipt", source_ref="mailbox-entry-b", receipt_id="vendor-supp-2",
                      original_ref="vendor-intake-1", received_at=when,
                      fields=[dict(name="log references", refs=["reader-A", "reader-B"])], **common)
    original = dict(kind="original_filing_receipt", source_ref="mailbox-entry-a", receipt_id="vendor-intake-1",
                    received_at="2026-07-02T03:00:00Z", fields=[dict(name="station identifier", refs=[OVERLAY["resource_id"]])], **common)
    assert env.source("customer-fixture", original).status_code == 403
    deliver(env, [("vendor-fixture", supplement)])
    first = env.read()
    assert first["stage"] == "HISTORICAL_FILING" and first["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert first["actions"] == [] and first["submissions"] == []
    deliver(env, [("vendor-fixture", original)])
    joined = env.read()
    assert joined["preflight"]["outcome"] == expected
    assert joined["stage"] == "HISTORICAL_FILING" and joined["actions"] == [] and joined["submissions"] == []
    assert joined["ledger"]["claimed"] == joined["ledger"]["awarded"] == "0.00"
    assert env.human.post(env.url + "/actions/approve-claim", {}).status_code == 409


def test_counterparty_independently_measures_bulletins_and_net_remaining_issuance():
    from dataclasses import replace
    from decimal import Decimal
    from uptime.correspondence_types import Scope, instant
    from uptime.correspondence_vendor import ResourceVendorRecord, adjudicate_resource

    scope = Scope(account="buyer-219", vendor="Provider", contract="governing-A", service="API",
                  component="cell-1", invoice="statement-one", incident="obs-12", currency="USD", month="2026-06", region="east")
    vendor = ResourceVendorRecord("bears", scope, "public-A", "2026-07-10T18:00:00.000001Z",
        (("2026-06-05T00:00:00Z","2026-06-05T10:50:00Z"), ("2026-06-05T02:05:00Z","2026-06-05T05:00:00Z")),
        (), (("net-service",10201), ("support",12299)), frozenset({"net-service"}),
        ((Decimal(98), Decimal(45)), (Decimal(99), Decimal("12.5"))), True, "ref-284", "resource_log", "a"*64,
        maintenance_lead=timedelta(hours=2), bulletins=(("2026-06-05T00:30:00Z","2026-06-05T02:30:00Z","2026-06-04T22:30:00Z"),),
        issued_credits_cents=(("memo-31",231),("memo-31",231)))
    packet = dict(tenant="bears", scope=scope.model_dump(), agreement_id="public-A", destination="isolated-local-simulator",
                  requested="999.00", disclosed_artifact=dict(ref="ref-284", type="resource_log", sha256="a"*64))
    filed_at = instant("2026-07-08T13:00:00Z")
    assert adjudicate_resource(packet, vendor, filed_at) == "We approved a service credit of USD 10.44."
    assert "requires verification" in adjudicate_resource(packet, replace(vendor, issued_credits_cents=None), filed_at)
    assert "conflicting records" in adjudicate_resource(packet, replace(vendor, issued_credits_cents=(("x",12),("x",13))), filed_at)
    covered = replace(vendor, bulletins=(("2026-06-05T00:00:00Z","2026-06-05T10:50:00Z","2026-06-04T22:00:00Z"),))
    assert "meet the contract threshold" in adjudicate_resource(packet, covered, filed_at)


def test_replies_are_bound_to_latest_observed_filing_and_exact_predecessor(env, tmp_path, monkeypatch):
    install_statements(env, tmp_path, monkeypatch)
    common = dict(observed_at=env.now.isoformat(), submitted_to="claims@example.invalid")
    original = dict(kind="original_filing_receipt", receipt_id="history-812", source_ref="mail-source-a",
                    received_at="2026-07-02T10:00:00Z", fields=[], **common)
    supplement = dict(kind="supplement_filing_receipt", receipt_id="history-823", source_ref="mail-source-b",
                      original_ref="history-812", received_at="2026-07-03T10:00:00Z", fields=[], **common)
    deliver(env, [("vendor-fixture", original)])
    def note(receipt, text="Please supply the incident journal.", event_id="note-A"):
        return env.source("vendor-fixture", dict(kind="message", text=text, receipt_id=receipt), event_id=event_id)
    assert note("another-id").status_code == 409
    assert note("history-812").status_code == 200
    assert note("history-812").status_code == 200
    assert len(env.read()["replies"]) == 1 and env.read()["submissions"] == []
    assert env.source("vendor-fixture", original | {"source_ref":"equivocation"}, event_id="another-original").status_code == 409
    assert env.source("vendor-fixture", supplement | {"original_ref":"different"}).status_code == 409
    deliver(env, [("vendor-fixture", supplement)])
    assert note("history-812", "The filing window expired.", "stale").status_code == 409
    assert note("history-823", "We approved a service credit of USD 3.00.", "note-B").status_code == 200
    assert len(env.read()["replies"]) == 2 and env.read()["ledger"]["awarded"] == "0.00"


def test_observed_missing_item_can_be_cured_without_claiming_an_incomplete_month(env, tmp_path, monkeypatch):
    from test_vendor_resource_operators import EXTENSION, readings
    install(env, tmp_path, monkeypatch, extra_terms=EXTENSION, shadow=readings(), expected="10.44")
    rows = reports()
    rows[0][1]["complete"] = False  # event evidence only, no month completeness assertion
    rows[1][1]["complete"] = False
    original = dict(kind="original_filing_receipt", receipt_id="original-292", source_ref="vendor-received-inbox",
                    received_at="2026-07-02T12:30:00Z", observed_at=env.now.isoformat(),
                    submitted_to="claims@example.invalid", fields=[dict(name="station identifier", refs=[env.scope["component"]])])
    deliver(env, [("vendor-fixture", original), ("customer-fixture", rows[3][1])])
    note = dict(kind="message", receipt_id="original-292", text="Our desk cannot complete review without the station logs. Please supply log references.")
    deliver(env, [("vendor-fixture", note)])
    assert env.read()["stage"] == "NEEDS_EVIDENCE"
    assert env.read()["actions"] == []
    deliver(env, rows[:2])
    ready = env.read()
    assert ready["stage"] == "RESPONSE_DRAFTED" and ready["preflight"]["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert ready["historical_procedure"]["missing"] == ["log references"]
    assert ready["historical_procedure"]["available"]["log references"] == ["n1", "n2"]
    env.action("approve-response")
    assert env.human.post(env.url + "/actions/submit-response", {}).status_code == 409
    env.now += timedelta(days=1)
    submitted = env.action("submit-response")
    assert len(submitted["submissions"]) == 1
    rec = submitted["submissions"][0]
    assert rec["action"] == "submit-response" and rec["requested"] == "0.00"
    assert rec["packet"]["purpose"] == "procedural_evidence_only" and rec["packet"]["in_reply_to"] == original["receipt_id"]
    assert rec["packet"]["filing_material"]["fields"] == {"log references":["n1","n2"]}
    assert submitted["ledger"]["claimed"] == submitted["ledger"]["awarded"] == "0.00"
    assert env.read()["preflight"]["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert len(env.action("submit-response")["submissions"]) == 1
    second = dict(kind="message", receipt_id=rec["id"], text="We approved a service credit of USD 12.51.")
    assert env.source("vendor-fixture", second, event_id="award-receipt").status_code == 200
    assert env.read()["ledger"]["awarded"] == "0.00" and env.read()["actions"] == []


def test_distinct_filing_items_reference_only_their_provenance():
    from uptime.correspondence_resource import filing_refs
    from uptime.correspondence_types import Scope
    from test_vendor_resource import compiled
    scope = Scope(account="buyer-1", vendor="Green", contract="governing-a", service="App",
                  component=OVERLAY["resource_id"], invoice="inv-83", incident="obs-4", currency="USD",
                  month="2026-06", region="east")
    span = dict(ref="error-4", resource_id=scope.component, start="2026-06-01T11:00:00Z", end="2026-06-01T12:00:00Z",
                symptom="rejected samples", cause="instrument gateway failure")
    witness = dict(ref="probe-74", resource_id=scope.component, interval_ref=span["ref"], requested_at=span["start"],
                   valid=True, failed=True)
    groups = dict(resource_status=dict(event_id="stat",body=dict(source_ref="stat-ledger")),
                  resource_invoice=dict(event_id="bill",body=dict(source_ref="invoice-ledger")),
                  request_evidence=dict(body=dict(observed_at=OBSERVED,records=[witness])))
    from test_vendor_resource import extend_source
    from test_vendor_semantic_bindings import reviewed_context
    fields=['the measured month','covered instrument failure','evidence that valid requests failed',
            'billing evidence tying the charge to that endpoint']
    document,proposal=extend_source([('Required claim items: '+', '.join(fields)+'.',{'request_fields':fields})])
    terms=compiled(document,proposal)
    context=reviewed_context(terms,OVERLAY,source=document['text'])
    def references(field):
        return filing_refs(field, terms, OVERLAY, scope, groups, [span], [], context)
    assert references("the measured month") == {scope.month}
    assert references("covered instrument failure") == {"error-4"}
    assert references("evidence that valid requests failed") == {"probe-74"}
    witness["interval_ref"] = "unrelated"
    assert not references("evidence that valid requests failed")
    assert not references("billing evidence tying the charge to that endpoint")
