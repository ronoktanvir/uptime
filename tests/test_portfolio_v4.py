"""Workbench contracts exercised through isolated stores and the real signed router.

All inputs below are synthetic test records. No provider, customer document,
private adjudicator record or holdout oracle is opened by these tests.
"""
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
import secrets
import socket

from fastapi.testclient import TestClient
import pytest

from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.contracts import Principal, Source
from uptime.correspondence import CorrespondenceDesk
from uptime.correspondence_types import Claim, Delivery, Scope
from uptime.intelligence import explain
from uptime.server import create_app
from uptime.storage import case_versions, save_cases, settlement_events
from uptime.workbench import Workbench, _metrics

P = Principal("bears", "portfolio-test", "reviewer")
NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)
SCOPE = Scope(account="portfolio-account", vendor="Twilio", contract="test-agreement",
              service="Twilio Messaging API", component="test-component", invoice="test-oct-invoice",
              incident="test-incident", currency="USD", month="2026-10", region="test-region")
INTERVAL = dict(start="2026-10-18T13:00:00Z", end="2026-10-18T13:30:00Z")
BODIES = dict(status=dict(kind="status", **INTERVAL),
              impact=dict(kind="impact", **INTERVAL, affected=True, exclusion="none"),
              invoice=dict(kind="invoice", lines=[dict(id="fee-line", kind="affected_api", amount="100.00")]))
ROLES = dict(status="status", impact="customer", invoice="billing", message="vendor")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Portfolio integration must not open a network connection")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)


@pytest.fixture
def bench(tmp_path):
    return Workbench(tmp_path / "portfolio.sqlite", "replay")


def entered(ident="entered-evaluation", amount="10.00", **extra):
    return dict(id=ident, vendor="Synthetic entered vendor", title="Entered evaluation", outcome="ELIGIBLE",
                stage="EVALUATED", amount=amount, currency="USD", sources=[Source.CUSTOMER.value, Source.REPLAY.value],
                trace=["Synthetic explicitly entered evaluation"], clauses=[], evidence=[], timeline=[], actions=[],
                financials=[dict(label="Estimate", value=amount, sources=[Source.CUSTOMER.value])], **extra)


def metric(dashboard, key, cohort=None):
    rows=dashboard["cohorts"][cohort]["metrics"] if cohort else dashboard["metrics"]
    return next(r for r in rows if r["key"]==key)


def inbox(bench, ident="inbox-entered-claim", account=None, fee="100.00"):
    if not hasattr(bench, "inbox"):
        bench.inbox=CorrespondenceDesk(bench.path, clock=lambda: NOW)
    scope=SCOPE.model_copy(update={"account":account}) if account else SCOPE
    desk=bench.inbox
    desk.provision(P.tenant, scope.account, scope.vendor, scope.contract, scope.service, scope.component, scope.region)
    for role in set(ROLES.values()):
        desk.bind_sender(P.tenant, scope.account, role, role+"-test")
    desk.create(P, Claim(claim_id=ident, scope=scope))
    for kind, body in BODIES.items():
        if kind=="invoice":
            body=dict(kind="invoice", lines=[dict(id="fee-line", kind="affected_api", amount=fee)])
        desk.receive(Principal(P.tenant, ROLES[kind]+"-test", "service"), ident,
                     Delivery(event_id=ident+"-"+kind, scope=scope, body=body))
    return ident


def award(bench, ident, amount="10.00"):
    bench.act(P, ident, "approve-claim")
    row=bench.act(P, ident, "submit-claim")
    bench.inbox.receive(Principal(P.tenant,"vendor-test","service"), ident,
                        Delivery(event_id=ident+"-award", scope=row["scope"],
                                 body=dict(kind="message", receipt_id=row["submissions"][0]["id"],
                                           text="We have approved a service credit of USD "+amount+".")))
    return bench.case(P, ident)


def test_cohorts_revision_heads_and_restart(bench):
    initial=bench.dashboard(P)
    assert not initial["cohorts"]["portfolio"]["cases"]
    assert metric(initial,"exposure","portfolio")["value"]=="Not verified"
    assert metric(initial,"estimated","portfolio")["amount"] is None
    save_cases(bench.path, P.tenant, [entered()])
    save_cases(bench.path, P.tenant, [entered(amount="25.00")])
    # A revised seeded example is preserved as well, instead of reset at startup.
    seed=next(c for c in bench.dashboard(P)["cases"] if c["id"].startswith("price-"))
    revised=bench.case(P, seed["id"])
    revised["note"]="Preserve a later stored evaluation"
    save_cases(bench.path, P.tenant, [revised])
    restarted=Workbench(bench.path, "replay")
    dashboard=restarted.dashboard(P)
    assert [r["id"] for r in dashboard["cohorts"]["portfolio"]["cases"]]==["entered-evaluation"]
    assert metric(dashboard,"estimated","portfolio")["amount"]=="25.00"
    assert restarted.case(P, seed["id"])["note"]==revised["note"]
    detail=restarted.case(P,"entered-evaluation")
    assert detail["revision"]==2 and len(detail["versions"])==2
    assert detail["financial_refs"] and detail["note"]
    assert len(case_versions(bench.path,P.tenant,"entered-evaluation"))==2
    assert dashboard["actual_applied"] is None
    assert metric(dashboard,"estimated","seeded")["amount"] is None


def test_only_exact_pending_prepayment_contributes(bench):
    rows=[entered("paid-premium", "9999.00", payment_status="paid"),
          entered("pending-estimate", "7.00", payment_status="pending")]
    rows[0].update(title="Premium prepayment review", stage="RETROSPECTIVE_REVIEW")
    rows[1]["stage"]="PREPAYMENT_REVIEW"
    save_cases(bench.path,P.tenant,rows)
    exposure=metric(bench.dashboard(P), "exposure", "portfolio")
    assert exposure["amount"]=="7.00" and exposure["case_ids"]==["pending-estimate"]


def test_all_recorded_partial_awards_are_counted_once(bench):
    a=inbox(bench,"inbox-entered-a")
    b=inbox(bench,"inbox-entered-b",account="second-account")
    award(bench,a,"6.00")
    award(bench,b,"8.00")
    row=bench.dashboard(P)
    assert metric(row,"claimed")["amount"]=="20.00"
    assert metric(row,"awarded")["amount"]=="14.00"
    assert metric(row,"awarded")["case_ids"]==[a,b]
    assert metric(row,"awarded")["case_id"] is None
    assert all(c["references"] and Source.VENDOR.value in c["sources"] for c in metric(row,"awarded")["contributions"])
    assert metric(row,"posted")["amount"]=="0.00"
    # Retry filing does not add another initial claim or change its total.
    bench.act(P,a,"submit-claim")
    assert metric(bench.dashboard(P),"claimed")["amount"]=="20.00"
    assert bench.case(P,a)["stage"]=="PARTIAL_AWARD_REVIEW"


def test_correspondence_credit_requires_scoped_existing_eligible_bill(bench):
    ident=inbox(bench)
    row=award(bench,ident,"6.00")
    assert {a["id"] for a in row["actions"]}=={"record-credit"}
    row=bench.act(P,ident,"record-credit")
    assert row["ledger"]["posted"]=="6.00" and row["ledger"]["applied"]=="0.00"
    assert row["reconciliation"]["stage"]=="POSTED"
    assert not row["actions"] and not bench.allocations.list_bills(P.tenant)
    record=bench.allocations.list_awards(P.tenant,case_id=ident)[0]
    assert record["scope"]["account_id"]==SCOPE.account
    assert record["scope"]["contract_id"]==SCOPE.contract
    wrong=dict(record["scope"], id="wrong-bill", source_ref="wrong-bill",
               source=Source.CUSTOMER.value, amount_cents=1000, eligible_cents=1000,
               effective_date="2026-11-03", account_id="unrelated")
    bench.allocations.record_bill(P.tenant,wrong)
    assert not bench.case(P,ident)["actions"]
    with pytest.raises(ValueError):
        bench.act(P,ident,"apply-balance")
    valid={**wrong,"id":"verified-bill","source_ref":"verified-bill","account_id":SCOPE.account}
    bench.allocations.record_bill(P.tenant,valid)
    row=bench.act(P,ident,"apply-balance")
    assert row["ledger"]["applied"]=="6.00" and row["stage"]=="PARTIAL_AWARD_REVIEW"
    assert row["reconciliations"][0]["bill_ids"]==["verified-bill"]
    assert row["reconciliation"]["stage"]=="APPLIED"
    assert bench.allocations.bill_balance(P.tenant,"verified-bill")["remaining_eligible"]=="4.00"
    before=bench.allocations.history(P.tenant)
    bench.act(P,ident,"record-credit"); bench.act(P,ident,"apply-balance")
    assert bench.allocations.history(P.tenant)==before
    restarted=Workbench(bench.path,"replay")
    restarted.inbox=CorrespondenceDesk(bench.path,clock=lambda:NOW)
    assert metric(restarted.dashboard(P),"applied","portfolio")["amount"]=="6.00"
    assert restarted.dashboard(P)["actual_applied"] is None


def test_subcent_candidate_can_file_but_cannot_post(bench):
    ident=inbox(bench,fee="0.01")
    row=bench.case(P,ident)
    assert row["ledger"]["estimated"]=="0.001"
    assert metric(bench.dashboard(P),"estimated","portfolio")["value"]=="$0.001"
    bench.act(P,ident,"approve-claim")
    row=bench.act(P,ident,"submit-claim")
    assert row["ledger"]["claimed"]=="0.001"
    assert metric(bench.dashboard(P),"estimated","portfolio")["amount"]=="0.001"
    with pytest.raises(ValueError):
        bench.act(P,ident,"record-credit")
    assert not bench.allocations.list_awards(P.tenant)


def test_legacy_reconciliation_uses_persisted_ledger_and_cent_actions(bench, monkeypatch):
    # An independently supplied local desk view isolates the workbench boundary.
    row=entered("legacy-cent","0.01")
    row.update(stage="AWARDED",ledger=dict(estimated="0.01",claimed="0.01",awarded="0.01",
                                          posted="0.00",applied="0.00",disputed_remainder="0.00"),
               preflight=dict(outcome="ELIGIBLE"))
    monkeypatch.setattr(bench.desk,"case",lambda p,ident:deepcopy(row))
    monkeypatch.setattr(bench.desk,"cases",lambda p:[deepcopy(row)])
    bench.act(P,row["id"],"record-credit")
    assert [a["id"] for a in bench.case(P,row["id"])["actions"]]==["apply-balance"]
    bench.act(P,row["id"],"apply-balance")
    detail=bench.case(P,row["id"])
    assert detail["reconciliation"]["origins"]==["INTAKE"]
    assert detail["reconciliation"]["applied"]=="0.01"
    assert [r["action"] for r in settlement_events(bench.path,P.tenant,row["id"])]==["record-credit","apply-balance"]


def test_duplicate_economic_activity_and_comparison_estimates():
    a=entered("a","10.00",cohort="seeded",obligation_id="same",ledger=dict(claimed="10.00",awarded="4.00"))
    b=entered("b","10.00",cohort="seeded",obligation_id="same",ledger=dict(claimed="10.00",awarded="4.00"))
    rows={r["key"]:r for r in _metrics([a,b])}
    assert rows["estimated"]["amount"] is None
    assert rows["claimed"]["amount"]=="10.00" and rows["awarded"]["amount"]=="4.00"
    assert rows["awarded"]["case_ids"]==["a","b"]


@pytest.mark.parametrize("status",[None,{},[],42,"Premium"])
def test_saved_ramp_facts_and_malformed_status_are_safe(bench,monkeypatch,status):
    bench.mode="sandbox"
    line=dict(id="line-1",amount=dict(amount="20.00",currency="USD"),quantity="2",
              unit_price=dict(amount="10.00",currency="USD"),sku="product-1",service_date="2026-10-01",
              quantity_rate_check="MATCH")
    capture=dict(freshness="STALE",integrity="CHECKSUM_VERIFIED",usable_for_evaluation=False,
                 age_seconds=90000,max_age_seconds=86400,reasons=["capture is stale"])
    data=dict(sources=[Source.RAMP.value,Source.REPLAY.value],observed_at="2026-11-01T12:00:00Z",
              capture_status=capture,bills=[dict(id="bill-1",status=status,amount=line["amount"],lines=[line],
                                               vendor_id="vendor-1",entity_id="entity-1",account_id=None)])
    monkeypatch.setattr(bench,"ramp",lambda:data)
    row=bench.case(P,"ramp-bill-1")
    assert row["payment_status"]=="UNKNOWN"
    assert row["provider_lines"][0]["quantity"]=="2"
    assert row["provider_identity"]["vendor_id"]=="vendor-1"
    assert not any("Missing:" in t and ("unit price" in t or "quantity" in t) for t in row["trace"])
    assert any("STALE" in t for t in row["trace"])
    assert any("capture is stale" in t for t in row["trace"])
    assert bench.dashboard(P)["cohorts"]["portfolio"]["cases"][0]["id"]==row["id"]


@pytest.mark.parametrize("question,intent",[("Show the profile", "basis"),("file this claim", "next"),
                                           ("Which file?", "next"),("pay", "next"),
                                           ("profile evidence", "proof")])
def test_guide_file_intent_is_a_word(question,intent):
    assert explain(entered(),question)["intent"]==intent


def test_normal_entrypoints_attach_inbox_and_preserve_signed_actions(tmp_path):
    secret=secrets.token_urlsafe(36)
    path=tmp_path/"app.db"
    app=create_app(path,mode="replay",rehearsal=True,rehearsal_secret=secret,approvals_enabled=True)
    bench=app.state.bench
    assert bench.inbox is app.state.correspondence
    bench.inbox.clock=lambda:NOW
    ident=inbox(bench)
    with TestClient(app,base_url=DEFAULT_ORIGIN,client=("127.0.0.1",50000)) as client:
        signer=ReviewerClient(client,DEFAULT_ORIGIN,SCRIPT,secret)
        client.headers.update(signer.headers)
        url="/api/cases/"+ident
        assert client.get(url).json()["stage"]=="DRAFTED"
        assert ident in {c["id"] for c in client.get("/api/dashboard").json()["cohorts"]["portfolio"]["cases"]}
        unsigned=client.post(url+"/actions/approve-claim",json={},
                             headers={"Origin":DEFAULT_ORIGIN,"X-Uptime-Action":"1"})
        assert unsigned.status_code==403
        assert signer.post(url+"/actions/approve-claim",{}).json()["stage"]=="CLAIM_APPROVED"
        issued=signer.post(url+"/actions/submit-claim",{}).json()
        assert issued["stage"]=="AWAITING_VENDOR" and len(issued["submissions"])==1
        assert client.get("/api/correspondence/claims/"+ident).json()["submissions"]==issued["submissions"]
        assert signer.post("/api/policy",dict(mode="OBSERVE",cap="0.00")).status_code==200
        assert not client.get(url).json()["actions"]
        assert signer.post(url+"/actions/record-credit",{}).status_code==403


def test_nonprimary_legacy_partial_award_contributes_to_activity(bench):
    bench.act(P,"dispute-partial","approve-claim")
    partial=bench.act(P,"dispute-partial","submit-claim")
    assert partial["stage"]=="PARTIAL_AWARD_REVIEW"
    ident=inbox(bench)
    entered_award=award(bench,ident,"6.00")
    row=metric(bench.dashboard(P),"awarded")
    assert Decimal(row["amount"])==Decimal(partial["ledger"]["awarded"])+Decimal(entered_award["ledger"]["awarded"])
    assert set(row["case_ids"])=={"dispute-partial",ident}
    bench.act(P,"dispute-partial","record-credit")
    assert metric(bench.dashboard(P),"posted")["amount"]==partial["ledger"]["awarded"]


def test_later_contradiction_preserves_recorded_award_but_freezes_application(bench):
    ident=inbox(bench)
    award(bench,ident,"6.00")
    row=bench.act(P,ident,"record-credit")
    record=row["reconciliations"][0]
    bench.allocations.record_bill(P.tenant,dict(record["scope"],id="eligible",source_ref="eligible",
        source=Source.CUSTOMER.value,amount_cents=600,eligible_cents=600,effective_date="2026-11-03"))
    bench.inbox.receive(Principal(P.tenant,"customer-test","service"),ident,
        Delivery(event_id="contradictory-impact",scope=SCOPE,body={**BODIES["impact"],"affected":False}))
    row=bench.case(P,ident)
    assert row["stage"]=="HUMAN_REVIEW" and row["actions"]==[]
    assert row["ledger"]["awarded"]==row["ledger"]["posted"]=="6.00"
    with pytest.raises(ValueError):
        bench.act(P,ident,"apply-balance")
    assert bench.allocations.reconcile(P.tenant,record["award_id"])["applied"]=="0.00"


def test_normal_vendor_intake_exposes_latest_case_revision(tmp_path):
    # Hand-computed independent inputs: June has 43,200 minutes; 109 lost minutes
    # exceed 0.25%, while exactly 108 do not. 12.5% of $100 is $12.50.
    source="""Synthetic public test contract
Vendor: Portfolio Cloud
Agreement: PORTFOLIO-TEST
Effective: 2026-01-01 through 2026-12-31
Availability is measured over each UTC calendar month.
| Product | Plan | Monthly uptime below | Service credit |
| --- | --- | --- | --- |
| Compute Tables | Team | 98% | 50% |
| Compute Tables | Team | 99.75% | 12.5% |
Claims must be received within 12 calendar days after month end.
Service credits apply to affected monthly fees on a future invoice."""
    doc=dict(name="Portfolio synthetic SLA",uri="urn:synthetic:portfolio-sla",classification="synthetic_public",text=source)
    overlay=dict(account="portfolio-account",agreement="PORTFOLIO-TEST",product="Compute Tables",plan="Team",currency="USD",
                 effective_from="2026-01-01",effective_until="2026-12-31",fee_line_ref="portfolio-fee")
    facts=dict(account=overlay["account"],agreement=overlay["agreement"],product=overlay["product"],plan="Team",month="2026-06",
               eligible_downtime_minutes=109,monitor_source="simulated_vendor",month_complete=True,exclusions_removed=True,
               monthly_fee_cents=10000,fee_line_ref="portfolio-fee",monitor_ref="synthetic-monitor",fee_ref="synthetic-fee",
               received_at="2026-07-12T23:59:59Z")
    rows=[dict(name="breach",facts=facts,expected=dict(outcome="ELIGIBLE",amount="12.50")),
          dict(name="equality",facts={**facts,"eligible_downtime_minutes":108},expected=dict(outcome="INELIGIBLE")),
          dict(name="public-only",facts={**facts,"monitor_source":"public_status"},expected=dict(outcome="INSUFFICIENT_EVIDENCE"))]
    secret=secrets.token_urlsafe(36)
    app=create_app(tmp_path/"vendor.db",mode="replay",rehearsal=True,rehearsal_secret=secret,approvals_enabled=True)
    with TestClient(app,base_url=DEFAULT_ORIGIN,client=("127.0.0.1",50000)) as client:
        signer=ReviewerClient(client,DEFAULT_ORIGIN,SCRIPT,secret)
        client.headers.update(signer.headers)
        base="/api/vendors/portfolio-cloud"
        def post(url,body):
            response=signer.post(url,body)
            assert response.status_code==200,response.text
            return response.json()
        state=post(base+"/candidates",dict(document=doc,overlay=overlay))
        state=post(base+"/tests",dict(revision=state["revision"],tests=rows))
        for operation in ("approve","activate"):
            action=next(a["id"] for a in state["actions"] if a["operation"]==operation)
            state=post(base+"/actions/"+action,{})
        case=post(base+"/evaluate",dict(facts=facts))
        assert case["amount"]=="12.50"
        post(base+"/evaluate",dict(facts={**facts,"monthly_fee_cents":20000,"fee_ref":"synthetic-fee-revision"}))
        detail=client.get("/api/cases/"+case["id"]).json()
        assert detail["amount"]=="25.00" and detail["revision"]==2
        assert len(detail["versions"])==2 and detail["financial_refs"]
        dashboard=client.get("/api/dashboard").json()
        assert [c["id"] for c in dashboard["cohorts"]["portfolio"]["cases"]]==[case["id"]]
        assert metric(dashboard,"estimated","portfolio")["amount"]=="25.00"
        assert metric(dashboard,"claimed","portfolio")["amount"]=="0.00"
