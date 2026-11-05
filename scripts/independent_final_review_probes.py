"""Independent frozen-source probes; synthetic fixtures and disposable SQLite only.

Run with the existing project Python, from the repository root. No dependencies
are installed, no provider transport is used, and no application file is edited.
Assertions describe the observed defect, so PASS means reproduced, not fixed.
"""
from copy import deepcopy
import argparse
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import socket
import sys
from tempfile import TemporaryDirectory
from time import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
for name in tuple(os.environ):
    if name.startswith(("UPTIME_", "RAMP_")):
        os.environ.pop(name)


def no_network(*args, **kwargs):
    raise RuntimeError("Independent review prohibits network access")


socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network
socket.getaddrinfo = no_network

from fastapi.testclient import TestClient
from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient, service_headers
from uptime.auth_keys import generate_reviewer_key
from uptime.contracts import fingerprint
from uptime.server import create_app
from uptime import ramp_workspace
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from uptime.auth_keys import public_bytes
from uptime import mandates
from uptime.correspondence_types import Scope
from uptime.source_config import SourceConfig, SourceGrant, SenderCredential
from uptime.ramp_award_attribution import AwardAttributionStore, AttributionError, signing_bytes, digest
from uptime.ramp_records import sync_records
from test_ramp_records_v4 import Reader, BILL, VENDOR, ENTITY, CREDIT, uid, money as native_money

# Do not inspect the saved native capture, including when a replay dashboard asks
# for its companion worklist. All native records below are locally constructed.
ramp_workspace.PACKAGED = Path("/nonexistent-independent-review-capture")
ramp_workspace.PROOF = Path("/nonexistent-independent-review-receipt")

# Only explicitly synthetic committed input declarations are imported.
from test_vendor_resource import ROWS, OVERLAY, FACTS
from test_vendor_catalog import DOC as SIMPLE_DOC, OVERLAY as SIMPLE_OVERLAY, TESTS as SIMPLE_TESTS


class App:
    def __init__(self, path, *, enabled=True):
        self.path = path
        self.key = generate_reviewer_key()
        self.subject = "independent-reviewer"
        enroll(path, self.subject, self.key)
        self.services = {f"{role}-fixture": secrets.token_hex(32)
                         for role in ("status", "customer", "billing", "vendor")}
        self.app = create_app(path, approvals_enabled=enabled, service_credentials=self.services)
        self.client = TestClient(self.app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 12480))
        self.reviewer = ReviewerClient(self.client, DEFAULT_ORIGIN, self.subject, self.key)
        self.now = datetime(2026, 7, 4, tzinfo=UTC)
        self.desk = self.app.state.correspondence
        self.desk.clock = lambda: self.now

    def post(self, url, body):
        response = self.reviewer.post(url, body)
        assert response.status_code == 200, (url, response.status_code, response.text)
        return response.json()

    def get(self, url):
        response = self.client.get(url, headers=self.reviewer.headers)
        assert response.status_code == 200, (url, response.status_code, response.text)
        return response.json()

    def action(self, vendor, state, operation):
        action = next(a["id"] for a in state["actions"] if a["operation"] == operation)
        return self.post(f"/api/vendors/{vendor}/actions/{action}", {})

    def provision(self, scope):
        self.desk.provision("bears", *(scope[k] for k in
                            ("account", "vendor", "contract", "service", "component", "region")))
        for subject in self.services:
            self.desk.bind_sender("bears", scope["account"], subject.removesuffix("-fixture"), subject, scope=scope)

    def source(self, claim, scope, role, body, event_id=None):
        url = f"/api/correspondence/claims/{claim}/events"
        raw = json.dumps(dict(event_id=event_id or body["kind"], scope=scope, body=body)).encode()
        subject = role + "-fixture"
        headers = service_headers(instance=self.app.state.auth.instance, origin=DEFAULT_ORIGIN,
                                  subject=subject, key=self.services[subject], path=url, body=raw)
        response = self.client.post(url, content=raw, headers=headers)
        assert response.status_code == 200, (response.status_code, response.text)
        return response.json()

    def close(self):
        self.client.close()


class SandboxApp(App):
    """Fresh sandbox installation with generated Ed25519 sources and exact mandates."""
    def __init__(self, path, sc):
        self.path, self.tenant, self.subject = path, "independent-native", "independent-reviewer"
        self.key = generate_reviewer_key()
        self.now = datetime(2026, 7, 4, tzinfo=UTC)
        enroll(path, self.subject, self.key, tenant=self.tenant, mode="sandbox")
        self.issuer = Ed25519PrivateKey.generate()
        mandates.register_issuer(path, mandates.Issuer(subject="independent-issuer",
            public_key=self.issuer.public_key().public_bytes_raw().hex(),
            local_purposes=("workspace", "vendor-promotion", "claim-filing")))
        grants, self.services = [], {}
        for role in ("status", "customer", "billing", "vendor"):
            subject = role + "-fixture"
            key = Ed25519PrivateKey.generate()
            grants.append(SourceGrant(subject=subject, source=role, scope=Scope(**sc),
                                      public_key=key.public_key().public_bytes_raw().hex()))
            self.services[subject] = SenderCredential(version=1, channel="LOCAL_SYNTHETIC", tenant=self.tenant,
                mode="sandbox", origin=DEFAULT_ORIGIN, subject=subject, source=role, scope=Scope(**sc),
                private_key=key.private_bytes_raw().hex())
        self.sources = SourceConfig(version=1, channel="LOCAL_SYNTHETIC", tenant=self.tenant,
                                    mode="sandbox", origin=DEFAULT_ORIGIN, services=grants)
        self.reopen()

    def reopen(self, office=None):
        if hasattr(self, "client"):
            self.client.close()
        self.app = create_app(self.path, tenant=self.tenant, mode="sandbox", approvals_enabled=True,
                             service_credentials=self.sources.credentials("sandbox", DEFAULT_ORIGIN, self.tenant),
                             award_office=office)
        self.sources.bind(self.app.state.correspondence)
        self.desk = self.app.state.correspondence
        self.desk.clock = lambda: self.now
        self.client = TestClient(self.app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 12481))
        self.reviewer = ReviewerClient(self.client, DEFAULT_ORIGIN, self.subject, self.key)

    def post(self, url, body):
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        claim = None
        if url.startswith("/api/correspondence/claims/") and "/actions/" in url:
            detail, action = url.split("/actions/")
            offer = next(a for a in self.get(detail)["actions"] if a["id"] == action)
            claim = offer["mandate_claim"]
        stamp = int(time())
        values = dict(mandates.describe(self.path, self.subject), schema_version="uptime-reviewer-mandate/1",
                      mandate_id=str(uuid4()), valid_from=stamp-1, valid_until=stamp+300,
                      issuer="independent-issuer", path=url, body_sha256=sha256(raw).hexdigest(), effect=None,
                      claim=claim)
        mandate = mandates.Mandate.model_validate(values)
        mandates.install(self.path, mandates.SignedMandate(mandate=mandate,
                         signature=self.issuer.sign(mandate.signing_bytes()).hex()))
        return super().post(url, body)


def evidence(name):
    return dict(reference="fixture:" + name, sha256=sha256(name.encode()).hexdigest(), method="SYNTHETIC_REVIEW")


class Office:
    def __init__(self, env, folder, sc, version):
        self.env, self.business = env, uid(900)
        self.when = datetime.now(UTC)
        self.scope = dict(vendor_id=VENDOR, vendor_name=sc["vendor"], account_id=sc["account"], beneficiary_id=ENTITY,
            contract_id="altitude service schedule", contract_version=version, product_id="survey", service_name=sc["service"],
            month=sc["month"], remedy="resource-month/" + sc["component"], currency="USD", minor_unit_conversion_rate=100)
        reader = Reader()
        capture = sync_records(reader)
        env.app.state.ramp_workspace.import_observation(capture, self.business)
        self.keys = {r:Ed25519PrivateKey.generate() for r in
                     ("claim_registrar", "vendor_verifier", "finance_approver", "ramp_observer")}
        finance = generate_reviewer_key()
        enroll(env.path, "review-finance", finance, tenant=env.tenant, mode="sandbox")
        witnesses = []
        for role, key in self.keys.items():
            witnesses.append(dict(subject="office-"+role, role=role,
                public_key=key.public_key().public_bytes_raw().hex(), operator_id="review-finance" if role=="finance_approver" else "operator-"+role,
                operator_key_sha256=sha256(public_bytes(finance)).hexdigest() if role=="finance_approver" else digest(role),
                association=evidence("association-"+role), source_verification=evidence("verification-"+role),
                valid_from=(self.when-timedelta(hours=1)).isoformat(), valid_until=(self.when+timedelta(hours=3)).isoformat(),
                scopes=[] if role=="ramp_observer" else [self.scope]))
        self.config = dict(version="uptime-ramp-award-office/1", installation_id="independent-office", tenant=env.tenant,
            business_id=self.business, environment="sandbox", evidence_mode="ACTUAL_NATIVE", review=evidence("office"),
            witnesses=witnesses, authority_sources=[dict(subject=g.subject, public_key=g.public_key) for g in env.sources.services])
        config_path = folder / "office-public.json"
        config_path.write_text(json.dumps(self.config))
        config_path.chmod(0o600)
        env.reopen(config_path)
        self.store = env.app.state.ramp_workspace.awards

    def signed(self, kind, ident, body, roles):
        stamp = datetime.now(UTC)
        statement = {k:self.config[k] for k in ("installation_id", "tenant", "business_id", "environment", "evidence_mode")}
        statement.update(version="uptime-ramp-award-attribution/1", kind=kind, id=ident,
                         issued_at=stamp.isoformat(), expires_at=(stamp+timedelta(hours=1)).isoformat(), body=body)
        return dict(statement=statement, endorsements=[dict(subject="office-"+r,
            signature=self.keys[r].sign(signing_bytes(self.config, statement, "office-"+r)).hex()) for r in roles])

    def register(self, claim, sc):
        # Read synthetic retained evidence solely to construct the separate exact
        # external custody attestation; no table or resolver is replaced.
        from uptime.storage import database
        with database(self.env.path) as db:
            row = db.execute("SELECT state FROM inbox_claim WHERE tenant=? AND id=?", (self.env.tenant, claim)).fetchone()
        fact = next(e for e in json.loads(row[0])["evidence"] if e["kind"]=="original_filing_receipt")
        body = dict(claim_id=claim, dispatch_sha256=self.store.filing_identity(claim), local_contract_id=sc["contract"],
            claimant_operator_id=self.env.subject, scope=self.scope, scope_verification=evidence("scope"),
            bills=[dict(bill_id=BILL, eligible_minor=100, evidence=evidence("bill"))], external_filing=dict(
                evidence_mode="ACTUAL_EXTERNAL", receipt_id=fact["body"]["receipt_id"], receipt_sha256=digest(fact),
                received_at=fact["body"]["received_at"], submitted_to=fact["body"]["submitted_to"], channel="VENDOR_PORTAL",
                verification=evidence("custody"), authority_verification=evidence("authority"), independence_verification=evidence("independence")))
        bad = deepcopy(body)
        bad["external_filing"]["receipt_sha256"] = "0" * 64
        try:
            self.store.register_claim(self.signed("filed_claim", "bad-receipt", bad, ["claim_registrar", "vendor_verifier"]))
        except AttributionError as exc:
            assert str(exc) == "EXTERNAL_FILING_WITNESS_CONFLICT"
        else:
            raise AssertionError("A substituted receipt must be rejected")
        self.claim, self.claim_hash = claim, self.store.register_claim(self.signed("filed_claim", "registered", body,
            ["claim_registrar", "vendor_verifier"]))["claim_sha256"]

    def award(self, ident):
        body = dict(claim_id=self.claim, claim_sha256=self.claim_hash, scope=self.scope, vendor_award_ref=ident,
            amount_minor=100, confirmation=dict(**evidence("award"), channel="VENDOR_SIGNED_DOCUMENT",
            authority_verification=evidence("award-authority"), independence_verification=evidence("award-independence")))
        return self.store.import_award(self.signed("vendor_award", ident, body, ["vendor_verifier", "finance_approver"]))

    def attribute(self, award):
        stamp = datetime.now(UTC).isoformat()
        snapshot = dict(id="review-snapshot", observed_at=stamp, source="LIVE_RAMP_SANDBOX",
            provenance_ref="fixture:generated-native-observation", capture=evidence("native-capture"),
            scopes=["vendors:read", "bills:read"], available=True, list_complete=True,
            credits=[dict(id=CREDIT, vendor_id=VENDOR, entity_id=ENTITY, reference_bill_id=BILL,
                accounting_date="2026-07-05", archived_at=None, total_amount=native_money(100),
                remaining_amount=native_money(50), total_applied_amount=native_money(50),
                applied_bills=[dict(bill_id=BILL, amount=native_money(50))], applied_draft_bills=[])],
            bills=[dict(id=BILL, vendor=dict(id=VENDOR), entity_id=ENTITY, archived_at=None, status="OPEN",
                amount=native_money(100), applied_vendor_credits=[dict(id=CREDIT, amount=native_money(50))])])
        receipt = self.store.observe(self.signed("native_snapshot", "review-snapshot", snapshot, ["ramp_observer"]))
        binding = dict(award_id=award, claim_sha256=self.claim_hash, snapshot_sha256=receipt["snapshot_sha256"],
            credit_id=CREDIT, posted_minor=100, currency="USD", minor_unit_conversion_rate=100,
            applications=[dict(bill_id=BILL, amount_minor=50)], basis="EXACT_EXPLICIT_ALLOCATION", scope_verification=evidence("allocation"))
        try:
            self.store.attribute(self.signed("attribution", "over-capacity", binding | {"posted_minor":101}, ["finance_approver"]))
        except AttributionError as exc:
            assert str(exc) == "IMMUTABILITY_OR_CAPACITY_CONFLICT"
        else:
            raise AssertionError("An extra minor unit must not exceed the signed award or credit")
        self.store.attribute(self.signed("attribution", "review-binding", binding, ["finance_approver"]))


def resource_inputs(resource):
    overlay = deepcopy(OVERLAY)
    overlay["resource_id"] = resource
    facts = deepcopy(FACTS)
    facts["resource_id"] = resource
    for group in ("intervals", "exclusions", "fee_lines"):
        for row in facts[group]:
            if row["resource_id"] == OVERLAY["resource_id"]:
                row["resource_id"] = resource
    facts["filing_proof"]["resource_id"] = resource
    facts["filing_proof"]["fields"]["station identifier"] = resource
    return overlay, facts


def install_resource(env, folder, vendor, *, resource="station-21", extra_terms=(), overlay_override=None,
                     facts_override=None, expected="12.51", semantic_review=None):
    rows = deepcopy(ROWS) + list(extra_terms)
    text = "\n".join(q for q, _ in rows)
    digest = sha256(text.encode()).hexdigest()
    proposal = [dict(quote=q, field="resource_terms", value=v) for q, v in rows]
    capture = dict(model="claude-opus-5-5", source_sha256=digest, session="SYNTHETIC-INDEPENDENT-REVIEW",
                   at="2026-07-01T06:00:00Z", proposal=proposal, proposal_sha256=fingerprint(proposal))
    # This is a local synthetic parser input, never evidence of a model invocation.
    (folder / (digest + ".json")).write_text(json.dumps(capture))
    os.environ["UPTIME_PUBLIC_EXTRACTIONS"] = str(folder)
    os.environ["UPTIME_MODEL_PROPOSITIONS"] = "1"
    overlay, facts = resource_inputs(resource)
    overlay = deepcopy(overlay_override) if overlay_override is not None else overlay
    facts = deepcopy(facts_override) if facts_override is not None else facts
    url = f"/api/vendors/{vendor}"
    state = env.post(url + "/candidates", dict(document=dict(name="Synthetic review terms",
        uri="urn:synthetic:independent-review", classification="synthetic_public", text=text), overlay=overlay))
    assert state["state"] == "SHADOW", state
    if semantic_review is not None:
        state = env.post(url + "/semantic-bindings", dict(revision=state["revision"],
                         review=semantic_review(state, text)))
    negative = deepcopy(facts) | {"intervals": []}
    if "provider_telemetry" in negative:
        negative["provider_telemetry"].update(records=[], no_events_verified=True)
    state = env.post(url + "/tests", dict(revision=state["revision"], tests=[
        dict(name="independent positive", facts=facts, expected=dict(outcome="ELIGIBLE", amount=expected)),
        dict(name="independent negative", facts=negative, expected=dict(outcome="INELIGIBLE"))]))
    for action in ("interpret", "approve", "activate"):
        state = env.action(vendor, state, action)
    return state, facts


def scope(resource="station-21", region="west"):
    return dict(account=OVERLAY["account"], vendor="Copper Mesa Networks", contract=OVERLAY["agreement"],
                service=OVERLAY["product"], component=resource, region=region, invoice="review-invoice",
                incident="review-incident", currency="USD", month="2026-06")


def deliver_resource(env, claim, sc):
    _, facts = resource_inputs(sc["component"])
    month = dict(start="2026-06-01T00:00:00Z", end="2026-07-01T00:00:00Z", complete=True)
    observed = "2026-07-01T06:00:00Z"
    status = [{k:r[k] for k in ("ref", "resource_id", "start", "end", "symptom")} for r in facts["intervals"]]
    causes = [{k:r[k] for k in ("ref", "resource_id", "start", "end", "cause")} for r in facts["intervals"]]
    excluded = [{k:r[k] for k in ("ref", "resource_id", "start", "end", "cause")} for r in facts["exclusions"]]
    fees = [{k:v for k,v in r.items() if k != "account"} for r in facts["fee_lines"] if r["resource_id"] == sc["component"]]
    rows = [("status", dict(kind="resource_status", source_ref="status", observed_at=observed, intervals=status, **month)),
            ("customer", dict(kind="resource_attribution", source_ref="cause", observed_at=observed, causes=causes, exclusions=excluded, **month)),
            ("billing", dict(kind="resource_invoice", source_ref="invoice", observed_at=observed, itemized_complete=True, lines=fees)),
            ("customer", dict(kind="filing_material", source_ref="material", observed_at=observed, channel="claims@example.invalid",
                              fields=[dict(name="station identifier", refs=[sc["component"]]), dict(name="log references", refs=["n1", "n2"])]))]
    for role, body in rows:
        env.source(claim, sc, role, body, event_id=claim + "-" + body["kind"])


def probe_resource_totals(folder):
    env = App(folder / "resources.sqlite")
    records = []
    for index in (21, 22):
        vendor = f"station-{index}"
        _, facts = install_resource(env, folder, vendor, resource=vendor)
        row = env.post(f"/api/vendors/{vendor}/evaluate", dict(facts=facts))
        assert row["amount"] == "12.51"
        records.append(row["id"])
    dashboard = env.get("/api/dashboard")
    metric = next(m for m in dashboard["cohorts"]["portfolio"]["metrics"] if m["key"] == "estimated")
    contributions = [c for c in metric["contributions"] if c["case_id"] in records]
    assert len(contributions) == 2
    assert len({c["obligation_id"] for c in contributions}) == 1
    assert metric["amount"] == "12.51"
    env.close()
    return dict(two_distinct_cases=records, expected_total="25.02", observed_metric=metric)


def probe_region_intake(folder):
    from test_vendor_resource_scoped import ROW, subscription, facts as regional_facts
    env = App(folder / "regions.sqlite")
    def regional(value, region):
        if isinstance(value, dict):
            return {k:(region if k == "region" else regional(v, region)) for k,v in value.items()}
        if isinstance(value, list):
            return [regional(v, region) for v in value]
        return value
    estimates = {}
    for region in ("North", "South"):
        facts = regional(regional_facts(), region)
        vendor = "regional-" + region.lower()
        install_resource(env, folder, vendor, extra_terms=ROW,
                         overlay_override=regional(subscription(), region), facts_override=facts, expected="15.03")
        estimates[region] = env.post(f"/api/vendors/{vendor}/evaluate", dict(facts=facts))["amount"]
    north, south = scope(region="North"), scope(region="South")
    for sc in (north, south):
        env.provision(sc)
    first = env.post("/api/correspondence/claims", dict(claim_id="inbox-north", scope=north))
    response = env.reviewer.post("/api/correspondence/claims", dict(claim_id="inbox-south", scope=south))
    assert first["scope"]["region"] == "North" and response.status_code == 409
    env.close()
    return dict(independent_regional_estimates=estimates, first_region=first["scope"]["region"],
                second_http=response.status_code, error=response.json())


def probe_compound_denial(folder):
    sc, claim = scope(), "inbox-compound-denial"
    env = SandboxApp(folder / "denial.sqlite", sc)
    install_resource(env, folder, "denial-service")
    url = "/api/correspondence/claims/" + claim
    env.post("/api/correspondence/claims", dict(claim_id=claim, scope=sc))
    deliver_resource(env, claim, sc)
    assert env.get(url)["amount"] == "12.51"
    env.post(url + "/actions/approve-claim", {})
    filed = env.post(url + "/actions/submit-claim", {})["submissions"][0]
    text = ("We denied your claim because we measured 5 minutes of downtime. "
            "You waived all service credit claims in a separate settlement agreement.")
    env.source(claim, sc, "vendor", dict(kind="message", receipt_id=filed["id"], text=text))
    row = env.get(url)
    assert row["stage"] == "RESPONSE_DRAFTED" and row["replies"][-1]["reason"] == "downtime"
    env.post(url + "/actions/approve-response", {})
    env.now += timedelta(days=1)
    sent = env.post(url + "/actions/submit-response", {})["submissions"][-1]
    assert "waiv" not in json.dumps(sent["packet"]).lower()
    env.close()
    return dict(signed_text=text, observed_stage=row["stage"], classified_reason=row["replies"][-1]["reason"],
                offered_actions=[a["id"] for a in row["actions"]], submitted_argument=sent["packet"]["argument"],
                disposition="local simulator only; human signing still required")


def probe_historical_native_join(folder):
    sc, claim = scope(), "inbox-native-history"
    env = SandboxApp(folder / "native.sqlite", sc)
    extension = [("An incomplete claim may supplement its missing fields by the same deadline.",
                  {"supplement":"same_filing_deadline"})]
    state, _ = install_resource(env, folder, "native-history", extra_terms=extension)
    url = "/api/correspondence/claims/" + claim
    env.post("/api/correspondence/claims", dict(claim_id=claim, scope=sc))
    deliver_resource(env, claim, sc)
    original = dict(kind="original_filing_receipt", receipt_id="independent-original", source_ref="vendor-custody",
        received_at="2026-07-02T12:30:00Z", observed_at="2026-07-03T00:00:00Z", submitted_to="claims@example.invalid",
        fields=[dict(name="station identifier", refs=[sc["component"]])])
    env.source(claim, sc, "vendor", original)
    office = Office(env, folder, sc, state["active_version"])
    office.register(claim, sc)
    office.award("first-award")
    office.attribute("first-award")
    def summary():
        return env.get("/api/ramp/workspace")["credit_sync"]["verified_award_attribution"]
    before = summary()
    assert before["active_binding_count"] == 1
    env.source(claim, sc, "vendor", dict(kind="message", receipt_id=original["receipt_id"],
        text="Please supply the missing log references."))
    assert env.get(url)["stage"] == "RESPONSE_DRAFTED"
    env.post(url + "/actions/approve-response", {})
    env.now += timedelta(days=1)
    sent = env.post(url + "/actions/submit-response", {})
    assert sent["submissions"][0]["action"] == "submit-response"
    after = summary()
    assert after["active_binding_count"] == 0 and "ORIGINAL_EXTERNAL_RECEIPT_REQUIRED" in after["issues"]
    try:
        office.award("later-award")
    except AttributionError as exc:
        rejected = str(exc)
    else:
        raise AssertionError("Expected native join failure after procedural response")
    assert rejected == "ORIGINAL_EXTERNAL_RECEIPT_REQUIRED"
    env.close()
    return dict(before_active=before["active_binding_count"], before_stage=before["credits"][0]["stage"],
                normal_action=sent["submissions"][0]["action"], after_active=after["active_binding_count"],
                after_stage=after["credits"][0]["stage"], issues=after["issues"], subsequent_award_error=rejected,
                controls=["substituted filing receipt rejected", "one-minor-unit overallocation rejected"],
                actual_recovered_cash=after["actual_recovered_cash"], fixture_provenance="GENERATED TEST INPUT ONLY")


def probe_draft_isolation(folder):
    env = App(folder / "draft.sqlite", enabled=False)
    url = "/api/vendors/review-draft"
    state = env.post(url + "/candidates", dict(document=SIMPLE_DOC, overlay=SIMPLE_OVERLAY))
    state = env.post(url + "/tests", dict(revision=state["revision"], tests=SIMPLE_TESTS))
    preview = env.post(url + "/shadow-preview", dict(revision=state["revision"], facts=SIMPLE_TESTS[0]["facts"]))
    denied = env.client.post("/api/auth/challenge", headers=env.reviewer.headers,
        json=dict(subject=env.subject, path=url + "/actions/activate", body_sha256="a" * 64))
    assert not state["actions"] and preview["dispatch_authorized"] is False and denied.status_code == 403
    forged = env.reviewer.prepare(url + "/shadow-preview", dict(revision=state["revision"], facts=SIMPLE_TESTS[0]["facts"]))
    forged["content"] = b"{}"
    altered = env.client.post(url + "/shadow-preview", **forged)
    assert altered.status_code == 403
    env.close()
    return dict(draft=state["state"], preview=preview["classification"], promotion_http=denied.status_code,
                changed_body_http=altered.status_code)


def main():
    probes = (probe_resource_totals, probe_region_intake, probe_compound_denial,
              probe_historical_native_join, probe_draft_isolation)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", choices=[f.__name__ for f in probes])
    parser.add_argument("--regressions", action="store_true", help="Run only the inspected synthetic regression modules")
    args = parser.parse_args()
    if args.regressions:
        import pytest
        with TemporaryDirectory(prefix="uptime-independent-regressions-") as directory:
            result = pytest.main(["-q", "-p", "no:cacheprovider", "--basetemp", str(Path(directory).resolve() / "pytest"),
                "tests/test_vendor_draft_authority.py", "tests/test_correspondence_resource.py",
                "tests/test_correspondence_regional.py", "tests/test_ramp_award_claim_integration.py",
                "tests/test_vendor_resource.py", "tests/test_portfolio_v4.py"])
        raise SystemExit(result)
    results = {}
    with TemporaryDirectory(prefix="uptime-independent-final-") as directory:
        base = Path(directory).resolve()
        for function in probes:
            if args.probe and args.probe != function.__name__:
                continue
            folder = base / function.__name__
            folder.mkdir()
            results[function.__name__] = function(folder)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
