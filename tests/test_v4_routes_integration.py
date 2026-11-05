"""Exercise onboarding and independent inbox intake through the real listener's proof gates."""
from datetime import UTC, datetime
import json
import secrets

import pytest
from fastapi.testclient import TestClient

from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient, service_headers
from uptime.server import create_app

SCOPE = dict(account="north-612", vendor="Boreal Relay", contract="BR-74", service="Message Store",
             component="store-east", invoice="oct-inv-3", incident="inc-612", currency="USD", month="2026-10", region="east")
INTERVAL = dict(start="2026-10-14T01:01:00Z", end="2026-10-14T01:46:00Z")
SMALL = dict(agreement="BR-74", account="north-612", product="Message Store", plan="Team", month="2026-10",
             eligible_downtime_minutes=45, monitor_source="simulated_vendor", month_complete=True,
             exclusions_removed=True, monthly_fee_cents=41736, fee_line_ref="monthly-store", received_at="2026-11-03T00:00:00Z")
TEXT = """Synthetic public test contract
Vendor: Boreal Relay
Agreement: BR-74
Effective: 2026-01-01 through 2026-12-31
Availability is measured over each UTC calendar month.
For Message Store on the Team plan, monthly availability below 99.9% earns a 12.5% service credit.
Claims must be received within 13 calendar days after month end.
Service credits apply to affected monthly fees on a future invoice."""


class App:
    def __init__(self, path):
        key = secrets.token_urlsafe(32)
        self.keys = {source + "-fixture":secrets.token_hex(32) for source in ("status", "customer", "billing", "vendor")}
        self.app = create_app(path, rehearsal=True, rehearsal_secret=key, approvals_enabled=True, service_credentials=self.keys)
        self.client = TestClient(self.app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 4510))
        self.human = ReviewerClient(self.client, DEFAULT_ORIGIN, SCRIPT, key)
        self.inbox = self.app.state.correspondence
        self.now = datetime(2026,11,3,tzinfo=UTC)
        self.inbox.clock = lambda: self.now
        self.scope = dict(SCOPE)
        self.id = "inbox-north-612"
        self.url = "/api/correspondence/claims/" + self.id

    def provision(self):
        self.inbox.provision("bears", *(self.scope[k] for k in ("account", "vendor", "contract", "service", "component", "region")))
        for subject in self.keys:
            self.inbox.bind_sender("bears", self.scope["account"], subject.removesuffix("-fixture"), subject, scope=self.scope)

    def post(self, path, payload):
        result = self.human.post(path,payload)
        assert result.status_code == 200, result.text
        return result.json()

    def create(self):
        return self.post("/api/correspondence/claims", dict(claim_id=self.id, scope=self.scope))

    def read(self):
        response = self.client.get(self.url, headers=self.human.headers)
        assert response.status_code == 200
        return response.json()

    def source(self, subject, body, event_id=None):
        target = self.url + "/events"
        raw = json.dumps(dict(event_id=event_id or body["kind"], scope=self.scope, body=body)).encode()
        headers = service_headers(instance=self.app.state.auth.instance, origin=DEFAULT_ORIGIN, subject=subject,
                                  key=self.keys[subject], path=target, body=raw)
        return self.client.post(target, content=raw, headers=headers)

    def evidence(self, line_ref="monthly-store", include_coverage=True, **coverage_changes):
        bodies = [("status-fixture", dict(kind="status", **INTERVAL)),
                  ("customer-fixture", dict(kind="impact", affected=True, exclusion="none", **INTERVAL)),
                  ("billing-fixture", dict(kind="invoice", lines=[dict(id=line_ref, kind="affected_api", amount="417.36"),
                                                                dict(id="tax-11",kind="tax",amount="1.00")]))]
        if include_coverage and self.scope["vendor"]!="Twilio":
            bodies.append(("status-fixture",dict(kind="coverage",start="2026-10-01T00:00:00Z",end="2026-11-01T00:00:00Z",
                complete=True,exclusions_removed=True,incident_ids=[self.scope["incident"]],total_eligible_minutes=45)|coverage_changes))
        for source, body in bodies:
            response = self.source(source,body)
            assert response.status_code == 200, response.text

    def action(self, action):
        return self.post(self.url+"/actions/"+action,{})

    def catalog_action(self,state,operation):
        action = next(a["id"] for a in state["actions"] if a["operation"]==operation)
        return self.post("/api/vendors/north-install/actions/"+action,{})

    def activate(self, text=TEXT, expected="52.17", facts=None):
        facts = facts or SMALL
        base = "/api/vendors/north-install"
        overlay = {k:SMALL[k] for k in ("agreement","account","product","plan","fee_line_ref")}
        overlay.update(currency="USD", effective_from="2026-01-01", effective_until="2026-12-31")
        state = self.post(base+"/candidates",dict(
            document=dict(name="Boreal availability agreement",uri="urn:synthetic:boreal-agreement",classification="synthetic_public",text=text),
            overlay=overlay))
        assert state["state"] == "SHADOW", state
        checks = [dict(name="Above trigger duration",facts=facts,expected=dict(outcome="ELIGIBLE",amount=expected)),
                  dict(name="Below trigger duration",facts=facts|{"eligible_downtime_minutes":44},expected=dict(outcome="INELIGIBLE"))]
        state = self.post(base+"/tests",dict(revision=state["revision"], tests=checks))
        return self.catalog_action(self.catalog_action(state,"approve"),"activate")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("UPTIME_PUBLIC_EXTRACTIONS", raising=False)
    app = App(tmp_path/"authority.db")
    yield app
    app.client.close()


def test_active_rules_join_independent_evidence_and_historical_receipt(env):
    env.provision()
    assert env.create()["outcome"]=="UNSUPPORTED_RULE"
    env.evidence()
    active = env.activate()
    assert active["active_version"]
    ready = env.read()
    assert ready["amount"]=="52.17" and ready["preflight"]["outcome"]=="ELIGIBLE"
    assert ready["filing_cutoff"]=="2026-11-14T00:00:00+00:00"
    assert active["active_version"] in ready["clauses"][0]["label"]
    assert any("status-fixture" in clause["label"] for clause in ready["clauses"])
    receipt = env.action("approve-claim")["approval"]
    assert {i["subject"] for i in receipt["evidence_authorities"]} == {"status-fixture","customer-fixture","billing-fixture"}
    submitted=env.action("submit-claim")["submissions"][0]
    assert submitted["digest"]==receipt["digest"] and submitted["packet"]["agreement_id"]=="BR-74"
    env.now=datetime(2026,11,19,tzinfo=UTC)
    delivered=env.source("vendor-fixture", dict(kind="message",receipt_id=submitted["id"],text="We approved a service credit of USD 44.10."))
    assert delivered.status_code==200
    row=env.read()
    assert (row["stage"],row["ledger"]["disputed_remainder"])==("PARTIAL_AWARD_REVIEW","8.07")


def test_rollback_invalidates_existing_inbox_approval(env):
    env.provision(); env.create(); env.evidence()
    active=env.activate()
    env.action("approve-claim")
    assert env.catalog_action(active,"rollback")["active_version"] is None
    assert env.read()["outcome"]=="UNSUPPORTED_RULE"
    assert env.human.post(env.url+"/actions/submit-claim",{}).status_code==409
    assert not env.read()["submissions"]


def test_active_overlay_requires_exact_authenticated_fee_line(env):
    env.provision(); env.create(); env.activate(); env.evidence(line_ref="other-line")
    row=env.read()
    assert row["outcome"]=="INSUFFICIENT_EVIDENCE" and "fee line" in row["trace"][0]
    assert not row["actions"] and row["amount"] is None


def test_twilio_real_mounted_router_requires_distinct_named_and_inbound_proofs(env):
    env.scope.update(vendor="Twilio",service="Twilio Messaging API")
    assert env.human.post("/api/correspondence/claims",dict(claim_id=env.id,scope=env.scope)).status_code==403
    env.provision()
    env.create()
    assert env.client.get(env.url).status_code==401
    assert env.client.post(env.url+"/actions/approve-claim",headers=env.human.headers,json={}).status_code==403
    assert env.source("billing-fixture", dict(kind="status",**INTERVAL)).status_code==403
    env.evidence()
    assert env.read()["amount"]=="41.736"
    env.action("approve-claim"); sent=env.action("submit-claim")
    assert sent["stage"]=="AWAITING_VENDOR" and sent["ledger"]["claimed"]=="41.736"
    assert env.app.state.bench.inbox is env.inbox


@pytest.mark.parametrize("coverage", [None, {"complete":False}, {"exclusions_removed":False}, {"total_eligible_minutes":88},
                                      {"incident_ids":["other-incident"]}, {"start":"2026-10-03T00:00:00Z"}])
def test_monthly_tier_requires_complete_signed_month_reconciled_to_incident(env, coverage):
    env.provision(); env.create(); env.activate()
    env.evidence(include_coverage=coverage is not None, **(coverage or {}))
    row = env.read()
    assert row["outcome"]=="INSUFFICIENT_EVIDENCE" and not row["actions"]


def test_overlapping_active_history_cannot_reprice_existing_measurement_month(env):
    env.provision(); env.create(); env.evidence(); env.activate()
    env.action("approve-claim")
    env.activate(TEXT.replace("12.5% service credit", "25% service credit"), expected="104.34")
    assert env.read()["outcome"]=="UNSUPPORTED_RULE"
    assert env.human.post(env.url+"/actions/submit-claim",{}).status_code==409


def test_active_effective_dates_must_cover_entire_measurement_month(env):
    env.provision(); env.create(); env.evidence()
    # Installation is active under a February-to-December source. A future
    # service period outside that scope has no authorized remedy.
    env.activate()
    env.scope.update(month="2027-01", invoice="next-invoice", incident="next-event")
    env.id="inbox-future"
    env.url="/api/correspondence/claims/"+env.id
    env.provision()
    assert env.create()["outcome"]=="UNSUPPORTED_RULE"


def test_active_installation_with_midmonth_effective_date_abstains(env):
    env.provision(); env.create(); env.evidence()
    env.activate(TEXT.replace("Effective: 2026-01-01","Effective: 2026-10-15"),
                 facts=SMALL|{"month":"2026-12","received_at":"2027-01-04T00:00:00Z"})
    assert env.read()["outcome"]=="UNSUPPORTED_RULE"


def test_conflicting_duplicate_month_record_invalidates_approval(env):
    env.provision(); env.create(); env.evidence(); env.activate(); env.action("approve-claim")
    r = env.source("status-fixture",dict(kind="coverage",start="2026-10-01T00:00:00Z",end="2026-11-01T00:00:00Z",
                        complete=True,exclusions_removed=True,incident_ids=[SCOPE["incident"]],total_eligible_minutes=208),
                   event_id="revised-coverage")
    assert r.status_code==200
    row = env.read()
    assert row["approval"] is None and row["outcome"]=="INSUFFICIENT_EVIDENCE"
    assert env.human.post(env.url+"/actions/submit-claim",{}).status_code==409

@pytest.mark.parametrize("field,other", [("incident", "invented"), ("month", "2025-01"),
                                         ("invoice", "other-invoice"), ("currency", "EUR")])
def test_exact_source_binding_prevents_early_registration_of_invented_claim(env, field, other):
    env.provision()
    assert env.human.post("/api/correspondence/claims", dict(
        claim_id="inbox-wrong", scope=env.scope | {field: other})).status_code == 403
    assert env.create()["id"] == env.id
    assert env.source("status-fixture", dict(kind="status", **INTERVAL)).status_code == 200
