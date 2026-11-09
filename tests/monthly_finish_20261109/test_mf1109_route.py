"""Focused route checks for the opt-in strict whole-month join and legacy invariance.

Part A calls the unchanged legacy joins directly. Part B uses the real mounted listener and its proof gates,
following the pattern of tests/test_v4_routes_integration.py; this file's own App class edits no helper.
The strict end-to-end case requires the source-derived onboarding compiler marker and never skips
that integration requirement. All terms and records are authored here.
"""
from datetime import UTC, datetime
from hashlib import sha256
import json
import secrets

import pytest
from fastapi.testclient import TestClient

from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient, service_headers
from uptime.claim_scope import COMPLETE_SERVICE_MONTH, complete_service_month
from uptime.contracts import Outcome
from uptime.correspondence_rules import assess
from uptime.correspondence_types import SOURCE, Delivery, Scope
from uptime.server import create_app
from uptime.v4_routes import _grounded_basis, _joined_observation
from uptime.vendor_terms import Document, compile_terms

WHOLE = dict(account="north-612", vendor="Boreal Relay", contract="BR-74", service="Message Store",
             currency="USD", month="2026-10")
INCIDENT = WHOLE | dict(invoice="oct-inv-3", incident="inc-612")
TWILIO = WHOLE | dict(vendor="Twilio", service="Twilio Messaging API", contract="twilio-apis",
                      component="api", incident="INC-1")
OVERLAY = dict(agreement="BR-74", account="north-612", product="Message Store", plan="Team",
               fee_line_ref="monthly-store", currency="USD", effective_from="2026-01-01", effective_until="2026-12-31")
SMALL = dict(agreement="BR-74", account="north-612", product="Message Store", plan="Team", month="2026-10",
             eligible_downtime_minutes=45, monitor_source="simulated_vendor", month_complete=True,
             exclusions_removed=True, monthly_fee_cents=41736, fee_line_ref="monthly-store",
             received_at="2026-11-03T00:00:00Z")
INTERVAL = dict(start="2026-10-14T01:01:00Z", end="2026-10-14T01:46:00Z")
OCTOBER = dict(start="2026-10-01T00:00:00Z", end="2026-11-01T00:00:00Z")
TEXT = """Synthetic public test contract
Vendor: Boreal Relay
Agreement: BR-74
Effective: 2026-01-01 through 2026-12-31
Availability is measured over each UTC calendar month.
For Message Store on the Team plan, monthly availability below 99.9% earns a 12.5% service credit.
Claims must be received within 13 calendar days after month end.
Service credits apply to affected monthly fees on a future invoice."""
# Exact source clause supported by the shared deterministic basis validator.
BASIS_CLAUSE = ("Claims are based on a complete UTC calendar-month report for the entire service; "
                "incident identifiers are not required.")
STRICT_TEXT = TEXT + "\n" + BASIS_CLAUSE
LEGACY_EVIDENCE = [("status-fixture", dict(kind="status", **INTERVAL)),
                   ("customer-fixture", dict(kind="impact", affected=True, exclusion="none", **INTERVAL)),
                   ("billing-fixture", dict(kind="invoice", lines=[dict(id="monthly-store", kind="affected_api", amount="417.36"),
                                                                   dict(id="tax-11", kind="tax", amount="1.00")])),
                   ("status-fixture", dict(kind="coverage", complete=True, exclusions_removed=True,
                                           incident_ids=["inc-612"], total_eligible_minutes=45, **OCTOBER))]


def month_report(kind, minutes=45):
    return dict(kind=kind, source_ref=kind + "-oct", observed_at="2026-11-01T06:00:00Z", plan="Team", complete=True,
                exclusions_removed=True, gaps=[], unresolved_exclusions=[], eligible_downtime_minutes=minutes, **OCTOBER)


STRICT_EVIDENCE = [("status-fixture", month_report("monthly_coverage")),
                   ("customer-fixture", month_report("monthly_attribution")),
                   ("billing-fixture", dict(kind="invoice", lines=[dict(id="monthly-store", kind="affected_api", amount="417.36"),
                                                                   dict(id="tax-11", kind="tax", amount="0.00")]))]


def stored_fact(scope, raw, subject=None):
    kind = raw["kind"]
    source = SOURCE[kind]
    subject = subject or source + "-fixture"
    body = Delivery.model_validate(dict(event_id="evt-1", scope=scope, body=raw)).body.model_dump(exclude_unset=True)
    return dict(event_id=kind, source=source, subject=subject, kind=kind, body=body,
                digest=sha256(json.dumps([kind, body], sort_keys=True).encode()).hexdigest(),
                source_key_id="fixture-hmac:" + subject, source_grant_id="grant:" + subject,
                received_at="2026-11-02T00:00:00+00:00", known_at="2026-11-02T00:00:00+00:00")


# Part A: the unchanged legacy joins never accept strict month records ------------------------------------

def test_legacy_incident_join_is_unchanged_and_refuses_a_strict_record_mixed_in():
    scope = Scope(**INCIDENT)
    legacy = [stored_fact(INCIDENT, raw) for _, raw in LEGACY_EVIDENCE]
    filed = datetime(2026, 11, 3, tzinfo=UTC)
    observation = _joined_observation(scope, legacy, OVERLAY, filed)
    assert (observation["eligible_downtime_minutes"], observation["monthly_fee_cents"]) == (45, 41736)
    for raw in (month_report("monthly_coverage"), month_report("monthly_attribution")):
        with pytest.raises(ValueError, match="does not establish"):
            _joined_observation(scope, legacy + [stored_fact(INCIDENT, raw)], OVERLAY, filed)


def test_builtin_twilio_profile_is_unchanged_and_refuses_strict_month_records():
    scope = Scope(**TWILIO)
    events = [stored_fact(TWILIO, raw) for _, raw in LEGACY_EVIDENCE[:3]]
    at = datetime(2026, 11, 3, tzinfo=UTC)
    assert assess("bears", scope, events, at).evaluation.outcome == Outcome.ELIGIBLE
    mixed = assess("bears", scope, events + [stored_fact(TWILIO, month_report("monthly_coverage"))], at)
    assert mixed.evaluation.outcome == Outcome.MISSING and "ordinary API profile" in mixed.evaluation.trace[0]


def test_route_grounding_accepts_unmarked_terms_and_refuses_an_ungrounded_marker():
    manifest = compile_terms(Document(name="Boreal availability agreement", uri="urn:synthetic:boreal-agreement",
                                      classification="synthetic_public", text=TEXT))
    assert manifest.get("evidence_basis") is None and _grounded_basis(manifest, TEXT)
    forged = manifest | {"evidence_basis": COMPLETE_SERVICE_MONTH, "citations": manifest["citations"] + [
        {"id": len(manifest["citations"]) + 1, "start": 0, "end": 5, "quote": "Forge", "field": "evidence_basis"}]}
    assert not _grounded_basis(forged, TEXT)


# Part B: the real mounted listener ------------------------------------------------------------------------

class App:
    def __init__(self, path):
        key = secrets.token_urlsafe(32)
        self.keys = {source + "-fixture": secrets.token_hex(32) for source in ("status", "customer", "billing", "vendor")}
        self.app = create_app(path, rehearsal=True, rehearsal_secret=key, approvals_enabled=True, service_credentials=self.keys)
        self.client = TestClient(self.app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 4510))
        self.human = ReviewerClient(self.client, DEFAULT_ORIGIN, SCRIPT, key)  # scripted reviewer, not a person
        self.inbox = self.app.state.correspondence
        self.now = datetime(2026, 11, 3, tzinfo=UTC)
        self.inbox.clock = lambda: self.now
        self.id = "inbox-north-612"
        self.url = "/api/correspondence/claims/" + self.id

    def provision(self, scope):
        self.inbox.provision("bears", *(scope.get(k) for k in ("account", "vendor", "contract", "service", "component", "region")))
        for subject in self.keys:
            self.inbox.bind_sender("bears", scope["account"], subject.removesuffix("-fixture"), subject, scope=scope)

    def post(self, path, payload):
        result = self.human.post(path, payload)
        assert result.status_code == 200, result.text
        return result.json()

    def create(self, scope):
        return self.human.post("/api/correspondence/claims", dict(claim_id=self.id, scope=scope))

    def read(self):
        response = self.client.get(self.url, headers=self.human.headers)
        assert response.status_code == 200
        return response.json()

    def source(self, subject, body, scope, event_id=None):
        target = self.url + "/events"
        raw = json.dumps(dict(event_id=event_id or body["kind"], scope=scope, body=body)).encode()
        headers = service_headers(instance=self.app.state.auth.instance, origin=DEFAULT_ORIGIN, subject=subject,
                                  key=self.keys[subject], path=target, body=raw)
        return self.client.post(target, content=raw, headers=headers)

    def deliver(self, evidence, scope):
        for subject, body in evidence:
            response = self.source(subject, body, scope)
            assert response.status_code == 200, response.text

    def catalog_action(self, state, operation):
        action = next(a["id"] for a in state["actions"] if a["operation"] == operation)
        return self.post("/api/vendors/north-install/actions/" + action, {})

    def install(self, text):
        overlay = {k: SMALL[k] for k in ("agreement", "account", "product", "plan", "fee_line_ref")}
        overlay.update(currency="USD", effective_from="2026-01-01", effective_until="2026-12-31")
        state = self.post("/api/vendors/north-install/candidates", dict(
            document=dict(name="Boreal availability agreement", uri="urn:synthetic:boreal-agreement",
                          classification="synthetic_public", text=text), overlay=overlay))
        assert state["state"] == "SHADOW", state
        return state

    def activate(self, state):
        checks = [dict(name="Above trigger duration", facts=SMALL, expected=dict(outcome="ELIGIBLE", amount="52.17")),
                  dict(name="Below trigger duration", facts=SMALL | {"eligible_downtime_minutes": 44},
                       expected=dict(outcome="INELIGIBLE"))]
        state = self.post("/api/vendors/north-install/tests", dict(revision=state["revision"], tests=checks))
        return self.catalog_action(self.catalog_action(state, "approve"), "activate")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("UPTIME_PUBLIC_EXTRACTIONS", raising=False)
    app = App(tmp_path / "authority.db")
    yield app
    app.client.close()


def test_unmarked_terms_still_refuse_a_whole_service_month_at_intake(env):
    env.install(TEXT)
    env.provision(WHOLE)
    refused = env.create(WHOLE)
    assert refused.status_code == 409 and "requires incident" in refused.text


def test_unmarked_active_terms_refuse_strict_records_mixed_into_the_incident_join(env):
    shadow = env.install(TEXT)
    env.provision(INCIDENT)
    assert env.create(INCIDENT).status_code == 200
    env.deliver(LEGACY_EVIDENCE, INCIDENT)
    env.activate(shadow)
    ready = env.read()
    assert ready["amount"] == "52.17" and ready["preflight"]["outcome"] == "ELIGIBLE"  # legacy control
    env.deliver(STRICT_EVIDENCE[:1], INCIDENT)
    mixed = env.read()
    assert mixed["outcome"] == "INSUFFICIENT_EVIDENCE" and mixed["amount"] is None and not mixed["actions"]


def _strict_terms():
    manifest = compile_terms(Document(name="Boreal availability agreement", uri="urn:synthetic:boreal-agreement",
                                      classification="synthetic_public", text=STRICT_TEXT))
    assert manifest.get("evidence_basis") == COMPLETE_SERVICE_MONTH
    assert complete_service_month(manifest, STRICT_TEXT) is True


def test_strict_whole_service_month_end_to_end(env):
    _strict_terms()
    shadow = env.install(STRICT_TEXT)
    env.provision(INCIDENT)
    invented = env.create(INCIDENT)
    assert invented.status_code == 409 and "not applicable" in invented.text  # no incident under strict terms
    env.provision(WHOLE)
    created = env.create(WHOLE)
    assert created.status_code == 200 and created.json()["scope"] == WHOLE
    env.deliver(STRICT_EVIDENCE[:1], WHOLE)
    env.activate(shadow)
    assert env.read()["outcome"] == "INSUFFICIENT_EVIDENCE"  # billing record still missing
    env.deliver(STRICT_EVIDENCE[2:], WHOLE)
    ready = env.read()
    assert ready["amount"] == "52.17" and ready["preflight"]["outcome"] == "ELIGIBLE"
    assert ready["filing_cutoff"] == "2026-11-14T00:00:00+00:00" and ready["scope"] == WHOLE
    env.deliver(STRICT_EVIDENCE[1:2], WHOLE)  # optional independent corroboration
    assert env.read()["amount"] == "52.17"
    env.deliver(LEGACY_EVIDENCE[:1], WHOLE)  # a legacy status record mixed into strict evidence
    mixed = env.read()
    assert mixed["outcome"] == "INSUFFICIENT_EVIDENCE" and mixed["amount"] is None and not mixed["actions"]


def test_overlapping_activation_cannot_silently_change_evidence_basis(env):
    from uptime.storage import database
    from uptime.v4_routes import _active_publication

    env.activate(env.install(TEXT))
    env.activate(env.install(STRICT_TEXT))
    with database(env.inbox.path) as db:
        assert _active_publication(db, "bears", Scope(**WHOLE)) is None


def test_evidence_basis_does_not_mint_a_new_economic_obligation():
    from uptime.claim_identity import claim_key, vendor_economic_identity

    document = dict(name="Boreal availability agreement", uri="urn:synthetic:boreal-agreement",
                    classification="synthetic_public")
    old = compile_terms(Document(**document, text=TEXT))
    new = compile_terms(Document(**document, text=STRICT_TEXT))
    left = vendor_economic_identity("bears", old, OVERLAY, "2026-10", "old-version")
    right = vendor_economic_identity("bears", new, OVERLAY, "2026-10", "new-version")
    assert claim_key(**left) == claim_key(**right)
