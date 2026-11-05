"""Local protocol proof of the mounted native path. Ephemeral data; no network."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import socket
from time import time
from types import SimpleNamespace
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from uptime import mandates, ramp_native_binding as native
from uptime.auth import Authority, DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key, public_bytes, reviewer_signature
from uptime.contracts import Principal, fingerprint
from uptime.ramp_records import sanitize_bill
from uptime.ramp_webhooks import canonical, utcnow
from uptime.storage import database

BUSINESS = "10000000-0000-4000-8000-000000000001"
BILL = "20000000-0000-4000-8000-000000000001"
OTHER = "30000000-0000-4000-8000-000000000001"
COMMENT = "40000000-0000-4000-8000-000000000001"
USER = "reviewer.fixture"
ISSUER = "independent.fixture"
TENANT = "native-fixture"


def raw(body):
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Native binding tests must never open a network socket")
    monkeypatch.setattr(socket.socket, "connect", forbidden)


class Protocol:
    def __init__(self):
        self.record = {"id": BILL, "status": "OPEN", "approval_status": "PENDING", "vendor": {"id": OTHER},
                       "entity_id": OTHER, "amount": {"amount": 1234, "currency_code": "USD", "minor_unit_conversion_rate": 100}}
        self.calls, self.comments, self.posts = [], [], []
        self.scopes = " ".join(sorted(native.SCOPES))
        self.business = BUSINESS
        self.active, self.scope_reported, self.expires = True, True, 3600
        self.uncertain, self.hide_comments, self.foreign_receipt, self.bad_page = False, False, False, False
        self.after_discussion = None
        self.after_bill = None

    def __call__(self, request):
        assert str(request.url).startswith("https://demo-api.ramp.com/developer/v1/")
        path = request.url.path
        self.calls.append((request.method, path))
        if path == "/developer/v1/token":
            assert request.method == "POST"
            assert request.headers["authorization"].startswith("Basic ")
            assert request.content == b"grant_type=client_credentials&scope=bills%3Aread+bills%3Awrite+business%3Aread"
            data = {"access_token": "ephemeral-protocol-token", "token_type": "Bearer", "expires_in": self.expires}
            if self.scope_reported:
                data["scope"] = self.scopes
            return httpx.Response(200, json=data)
        assert request.headers["authorization"] == "Bearer ephemeral-protocol-token"
        if path == "/developer/v1/business":
            assert request.method == "GET"
            return httpx.Response(200, json={"id": self.business, "active": self.active})
        if path == f"/developer/v1/bills/{BILL}":
            assert request.method == "GET"
            if self.after_bill:
                self.after_bill()
            return httpx.Response(200, json=self.record)
        if path == f"/developer/v1/comments/bills/{BILL}":
            if request.method == "GET":
                if self.after_discussion:
                    self.after_discussion()
                return httpx.Response(200, json={"data": [] if self.hide_comments else self.comments,
                    "page": {"next": f"https://demo-api.ramp.com/developer/v1/comments/bills/{OTHER}?start=next" if self.bad_page else None}})
            assert request.method == "POST"
            assert request.headers["content-type"] == "application/json"
            body = json.loads(request.content)
            assert set(body) == {"message", "message_format"}
            assert body["message_format"] == "PLAIN_TEXT"
            self.posts.append(request.content)
            row = {"id": COMMENT, "message": body["message"], "user_id": OTHER, "created_at": utcnow().isoformat()}
            self.comments.append(deepcopy(row))
            if self.uncertain:
                raise httpx.ReadTimeout("ambiguous transport; secret provider body must not be echoed")
            if self.foreign_receipt:
                row["id"] = OTHER
            return httpx.Response(201, json=row)
        raise AssertionError("Unsupported protocol request")


class Workspace:
    tenant, mode = TENANT, "sandbox"

    def __init__(self, protocol):
        self.business, self.custody, self.resolutions = BUSINESS, "operator_import", 0
        self.finding = {"provider_object_type": "bills", "provider_id": BILL, "workspace_tenant": TENANT,
            "business_id": BUSINESS, "finding_digest": fingerprint(["actual-observation", sanitize_bill(protocol.record)]),
            "observed_at": utcnow().isoformat(), "sources": ["LIVE_RAMP_SANDBOX"], "finding_kind": "NATIVE_OBSERVATION",
            "data_provenance": {"classification": "PROVIDER_OBSERVATION", "freshness": "FRESH",
                                "record_digest": fingerprint(sanitize_bill(protocol.record))}}

    def _observation(self):
        return {}, self.custody, self.business

    def record_for_native(self, object_type, object_id):
        self.resolutions += 1
        if (object_type, object_id) != ("bills", BILL):
            raise KeyError("No fallback")
        return deepcopy(self.finding)


class Installation:
    def __init__(self, tmp_path, monkeypatch):
        self.path = tmp_path
        self.db = tmp_path/"auth.db"
        self.key = generate_reviewer_key()
        enroll(self.db, USER, self.key, tenant=TENANT, mode="sandbox")
        self.auth = Authority(self.db, "sandbox", False, True, None, None, DEFAULT_ORIGIN, TENANT)
        self.signer = Ed25519PrivateKey.generate()
        mandates.register_issuer(self.db, mandates.Issuer(subject=ISSUER,
            public_key=self.signer.public_key().public_bytes_raw().hex(), business_id=BUSINESS,
            native_actions=("bill.comment.create",)))
        self.config_path = tmp_path/"native.json"
        self.config = {"schema_version": "uptime-native-operator/1", "enabled": True, "tenant": TENANT,
                       "business_id": BUSINESS, "reviewers": {USER: json.loads(public_bytes(self.key))}}
        self.write_config()
        home = tmp_path/"home"
        credential_dir = home/".config/uptime"
        credential_dir.mkdir(parents=True, mode=0o700)
        credential = credential_dir/"ramp-sandbox.json"
        credential.write_text(json.dumps({"base_url": native.ORIGIN, "client_id": "protocol-client", "client_secret": "protocol-secret"}))
        credential.chmod(0o600)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.setenv("RAMP_ENV", "sandbox")
        monkeypatch.setenv("RAMP_BASE_URL", native.ORIGIN)
        self.protocol = Protocol()
        self.workspace = Workspace(self.protocol)
        monkeypatch.setattr(native.gates, "native_install_ready", lambda installation: True)
        monkeypatch.setattr(native, "_client", lambda: httpx.Client(transport=httpx.MockTransport(self.protocol), trust_env=False))
        self.app = FastAPI()
        self.auth.register(self.app)
        self.binding = native.register_native_binding(self.app, workspace=self.workspace, auth=self.auth, config_path=self.config_path)
        self.client = TestClient(self.app, base_url=DEFAULT_ORIGIN)
        self.operator = ReviewerClient(self.client, DEFAULT_ORIGIN, USER, self.key)

    def write_config(self):
        self.config_path.write_text(json.dumps(self.config))
        self.config_path.chmod(0o600)

    def mandate(self, path, body, effect=None):
        at = int(time())
        mandate = mandates.Mandate.model_validate({**mandates.describe(self.db, USER),
            "schema_version": "uptime-reviewer-mandate/1", "mandate_id": str(uuid4()), "issuer": ISSUER,
            "valid_from": at-1, "valid_until": at+300, "path": path, "body_sha256": sha256(raw(body)).hexdigest(), "effect": effect})
        mandates.install(self.db, mandates.SignedMandate(mandate=mandate, signature=self.signer.sign(mandate.signing_bytes()).hex()))
        return mandate

    def post(self, path, body, effect=None):
        self.mandate(path, body, effect)
        return self.operator.post(path, body)

    def prepare(self):
        response = self.post(native.PREFIX+"/preflight", {})
        assert response.status_code == 200, response.text
        response = self.post(native.PREFIX+"/prepare", {"object_type": "bills", "object_id": BILL})
        assert response.status_code == 200, response.text
        return response.json()

    def reviewed(self):
        plan = self.prepare()
        expiry = int(time())+240
        message = self.binding.flow.review_message(plan["id"], reviewer=USER, expires_at=expiry)
        response = self.post(f"{native.PREFIX}/actions/{plan['id']}/review", {
            "expires_at": expiry, "proof": reviewer_signature(self.key, message)})
        assert response.status_code == 200, response.text
        return response.json()

    def execute(self, plan, effect=None):
        return self.post(f"{native.PREFIX}/actions/{plan['id']}/execute", {"review_digest": plan["review_digest"]},
                         plan["wire"]["effect"] if effect is None else effect)


@pytest.fixture
def installed(tmp_path, monkeypatch):
    installation = Installation(tmp_path, monkeypatch)
    yield installation
    installation.binding.close()
    installation.client.close()


def test_real_supported_body_and_same_object_receipt_through_named_mounted_authority(installed):
    i = installed
    assert i.protocol.calls == []  # Registration never reads credentials or calls Ramp.
    plan = i.reviewed()
    assert plan["transport_provenance"] == "MOCK_HTTP"
    result = i.execute(plan)
    assert result.status_code == 200, result.text
    result = result.json()
    assert result["status"] == "DELIVERED"
    assert result["remote_id"] == COMMENT
    assert result["remote_state"]["verification"] == "EXACT_DISCUSSION_GET"
    assert result["object_id"] == BILL
    assert result["expected_remote_state"]["record_digest"] == fingerprint(i.protocol.record)
    business_receipt = result["capabilities"]["business_verification"]
    assert business_receipt["method"] == "GET" and business_receipt["path"] == "/developer/v1/business"
    assert business_receipt["response_sha256"] == fingerprint({"id": BUSINESS, "active": True})
    assert i.protocol.posts == [plan["wire"]["body"].encode()]
    body = i.protocol.posts[0]
    assert plan["wire"]["body_sha256"] == sha256(body).hexdigest()
    assert plan["wire"]["effect"] == mandates.native_effect_from_request(
        BUSINESS, "POST", f"/developer/v1/comments/bills/{BILL}", body).model_dump()
    assert i.workspace.resolutions >= 5  # Includes independent final-boundary recomputation.
    assert result["actual_recovery"] is None and result["actual_money_prevented"] is None
    assert i.execute(plan).json()["status"] == "DELIVERED"
    assert len(i.protocol.posts) == 1
    assert "protocol-token" not in json.dumps(result) and "protocol-secret" not in json.dumps(result)


def test_real_workspace_capture_evaluator_to_native_receipt_without_fixture_fallback(installed):
    """Exercise root's actual record_for_native and capture tables, not a supplied finding."""
    from uptime.ramp import Token
    from uptime.ramp_records import sync_records
    from uptime.ramp_workspace import RampWorkspace
    from uptime.storage import initialize
    i = installed

    class Reader:
        def token(self, scopes):
            return Token("local-protocol-only", frozenset(scopes), frozenset(scopes))

        def request(self, token, method, path, query=None, data=None):
            if path == "bills/"+BILL:
                return deepcopy(i.protocol.record)
            return {"data": [deepcopy(i.protocol.record)] if path == "bills" else [], "page": {"next": None}}

    snapshot = sync_records(Reader())
    initialize(i.db)
    workspace = RampWorkspace(SimpleNamespace(path=i.db, tenant=TENANT, mode="sandbox"))
    workspace.import_observation(snapshot, BUSINESS)
    first = workspace.record_for_native("bills", BILL)
    assert first["finding_digest"] == workspace.record_for_native("bills", BILL)["finding_digest"]
    assert first["sources"] == ["LIVE_RAMP_SANDBOX"]
    i.binding.workspace = workspace
    result = i.execute(i.reviewed())
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "DELIVERED"
    assert result.json()["finding_digest"] == first["finding_digest"]
    assert result.json()["remote_id"] == COMMENT
    assert len(i.protocol.posts) == 1


def test_default_registration_disabled_and_gate_blocks_registration(installed, monkeypatch):
    i = installed
    app = FastAPI()
    assert native.register_native_binding(app, workspace=i.workspace, auth=i.auth) is None
    assert not any(r.path.startswith(native.PREFIX) for r in app.routes)
    monkeypatch.setattr(native.gates, "native_install_ready", lambda installation: False)
    with pytest.raises(native.WorkflowError):
        native.register_native_binding(app, workspace=i.workspace, auth=i.auth, config_path=i.config_path)
    assert i.protocol.calls == []


@pytest.mark.parametrize("field,value", [("access_token", "forbidden"), ("expected_scopes", ["bills:write"]),
                                       ("base_url", "https://api.ramp.com"), ("enabled", False)])
def test_config_cannot_install_tokens_scopes_production_or_disabled_routes(installed, field, value):
    i = installed
    i.config[field] = value
    i.write_config()
    with pytest.raises(native.WorkflowError):
        native.NativeBinding(workspace=i.workspace, auth=i.auth, config_path=i.config_path)
    assert not i.protocol.calls


@pytest.mark.parametrize("bad", ["private", "different-key", "shared", "symlink", "foreign-tenant"])
def test_operator_config_public_key_custody_and_tenant(installed, bad):
    i = installed
    if bad == "private":
        i.config["reviewers"][USER] = i.key
    if bad == "different-key":
        i.config["reviewers"][USER] = json.loads(public_bytes(generate_reviewer_key()))
    if bad == "foreign-tenant":
        i.config["tenant"] = "other"
    i.write_config()
    if bad == "shared":
        i.config_path.chmod(0o644)
    if bad == "symlink":
        link = i.path/"link.json"
        link.symlink_to(i.config_path)
        i.config_path = link
    with pytest.raises((native.WorkflowError, ValueError)):
        native.NativeBinding(workspace=i.workspace, auth=i.auth, config_path=i.config_path)
    assert not i.protocol.calls


@pytest.mark.parametrize("change", ["missing-write", "missing-read", "excess", "unreported", "foreign-business", "inactive", "expired"])
def test_preflight_reports_actual_scopes_and_exact_business_without_mutating(installed, change):
    i = installed
    if change == "missing-write": i.protocol.scopes = "business:read bills:read"
    if change == "missing-read": i.protocol.scopes = "business:read bills:write"
    if change == "excess": i.protocol.scopes += " vendors:read"
    if change == "unreported": i.protocol.scope_reported = False
    if change == "foreign-business": i.protocol.business = OTHER
    if change == "inactive": i.protocol.active = False
    if change == "expired": i.protocol.expires = 0
    response = i.post(native.PREFIX+"/preflight", {})
    if change in {"missing-write", "missing-read", "excess"}:
        assert response.status_code == 200
        assert not response.json()["preflight"]["comment_ready"]
    else:
        assert response.status_code == 409
    assert i.post(native.PREFIX+"/prepare", {"object_type": "bills", "object_id": BILL}).status_code == 409
    assert not i.protocol.posts


def test_administrator_scope_change_needs_only_new_preflight(installed):
    i = installed
    i.protocol.scopes = "business:read bills:read"
    assert not i.post(native.PREFIX+"/preflight", {}).json()["preflight"]["comment_ready"]
    i.protocol.scopes = " ".join(sorted(native.SCOPES))
    assert i.execute(i.reviewed()).json()["status"] == "DELIVERED"


@pytest.mark.parametrize("payload", [
    {"finding": {}}, {"business_id": OTHER}, {"comment": "arbitrary"}, {"url": "https://api.ramp.com"},
    {"access_token": "forbidden"}, {"expected_scope": "bills:write"}, {"resolved_id": OTHER},
    {"object_type": "transactions"}, {"object_type": "blank-canvas"}, {"action": "approve"}])
def test_untrusted_fields_and_other_action_types_are_refused(installed, payload):
    i = installed
    response = i.post(native.PREFIX+"/prepare", {"object_type": "bills", "object_id": BILL, **payload})
    assert response.status_code == 422
    assert i.protocol.calls == []


@pytest.mark.parametrize("change", ["synthetic", "replay", "foreign", "future", "stale", "capture-business", "packaged", "native-drift"])
def test_prepare_rejects_synthetic_stale_foreign_and_drifted_capture(installed, change):
    i = installed
    assert i.post(native.PREFIX+"/preflight", {}).status_code == 200
    f = i.workspace.finding
    if change == "synthetic": f["finding_kind"] = "SYNTHETIC_INVOICE_CAP"
    if change == "replay": f["sources"].append("DETERMINISTIC_REPLAY")
    if change == "foreign": f["workspace_tenant"] = "other"
    if change == "future": f["observed_at"] = (utcnow()+timedelta(seconds=10)).isoformat()
    if change == "stale": f["observed_at"] = (utcnow()-timedelta(hours=25)).isoformat()
    if change == "capture-business": i.workspace.business = OTHER
    if change == "packaged": i.workspace.custody = "packaged_receipt"
    if change == "native-drift": i.protocol.record["amount"]["amount"] += 1
    assert i.post(native.PREFIX+"/prepare", {"object_type": "bills", "object_id": BILL}).status_code == 409
    assert not i.protocol.posts


@pytest.mark.parametrize("change", ["finding", "native", "business", "gate", "config", "during-final-bill"])
def test_recomputes_at_final_wire_boundary_after_discussion_read(installed, monkeypatch, change):
    i = installed
    plan = i.reviewed()
    def drift():
        if change == "finding": i.workspace.finding["finding_digest"] = "0"*64
        if change == "native": i.protocol.record["approval_status"] = "APPROVED"
        if change == "business": i.protocol.business = OTHER
        if change == "gate": monkeypatch.setattr(native.gates, "native_install_ready", lambda installation: False)
        if change == "config": i.config["enabled"] = False; i.write_config()
        if change == "during-final-bill":
            i.protocol.after_bill = lambda: i.workspace.finding.update(finding_digest="0"*64)
    i.protocol.after_discussion = drift
    result = i.execute(plan)
    assert result.status_code == 409 or result.json()["status"] == "UNCERTAIN"
    assert not i.protocol.posts


@pytest.mark.parametrize("change", ["body", "object", "business", "no-native", "revoked", "signer"])
def test_exact_independent_native_mandate_required_at_dispatch(installed, change):
    i = installed
    plan = i.reviewed()
    effect = deepcopy(plan["wire"]["effect"])
    if change == "body": effect["payload_sha256"] = "0"*64
    if change == "object": effect["resource_id"] = OTHER
    if change == "business": effect["business_id"] = OTHER
    if change == "no-native": effect = None
    path = f"{native.PREFIX}/actions/{plan['id']}/execute"
    payload = {"review_digest": plan["review_digest"]}
    if change == "business":
        with pytest.raises(PermissionError): i.mandate(path, payload, effect)
        return
    issued = i.mandate(path, payload, effect)
    if change == "revoked":
        i.protocol.after_discussion = lambda: mandates.revoke(i.db, "mandate", issued.mandate_id)
    if change == "signer":
        i.protocol.after_discussion = lambda: mandates.revoke(i.db, "issuer", ISSUER)
    response = i.operator.post(path, payload)
    assert response.status_code == 200 and response.json()["status"] == "UNCERTAIN"
    assert not i.protocol.posts


def test_local_caller_signature_and_exact_body_cannot_be_bypassed(installed):
    i = installed
    plan = i.reviewed()
    path = f"{native.PREFIX}/actions/{plan['id']}/execute"
    body = {"review_digest": plan["review_digest"]}
    i.mandate(path, body, plan["wire"]["effect"])
    assert i.client.post(path, json=body).status_code in {401, 403}
    assert i.client.post(path, headers=i.operator.headers, json=body).status_code == 403
    signed = i.operator.prepare(path, body)
    signed["content"] = raw({"review_digest": "0"*64})
    assert i.client.post(path, **signed).status_code == 403
    assert not i.protocol.posts


def test_direct_workflow_or_provider_has_no_dispatch_ticket(installed):
    i = installed
    plan = i.reviewed()
    assert i.binding.flow.execute(plan["id"], provider=i.binding._provider())["status"] == "UNCERTAIN"
    assert not i.protocol.posts


def test_uncertain_post_reconciles_after_restart_without_resend(installed):
    i = installed
    plan = i.reviewed()
    i.protocol.uncertain = i.protocol.hide_comments = True
    assert i.execute(plan).json()["status"] == "UNCERTAIN"
    assert len(i.protocol.posts) == 1
    assert i.execute(plan).status_code == 409
    i.binding.close()
    restarted = native.NativeBinding(workspace=i.workspace, auth=i.auth, config_path=i.config_path)
    assert restarted.get(plan["id"])["status"] == "UNCERTAIN"
    assert restarted.get(plan["id"])["capabilities"]["business_verification"] == plan["capabilities"]["business_verification"]
    restarted.preflight()
    i.protocol.hide_comments = False
    result = restarted.reconcile(plan["id"])
    assert result["status"] == "DELIVERED" and result["remote_id"] == COMMENT
    assert result["remote_state"]["verification"] == "EXACT_DISCUSSION_GET"
    assert len(i.protocol.posts) == 1
    restarted.close()


def test_wrong_receipt_id_or_cross_object_pagination_never_counts_as_delivered(installed):
    i = installed
    plan = i.reviewed()
    i.protocol.foreign_receipt = True
    response = i.execute(plan)
    assert response.status_code == 409
    assert i.binding.get(plan["id"])["status"] == "UNCERTAIN"
    i.protocol.bad_page = True
    assert i.post(f"{native.PREFIX}/actions/{plan['id']}/reconcile", {}).json()["status"] == "UNCERTAIN"
    assert len(i.protocol.posts) == 1


def test_reconcile_requires_current_same_business_read(installed):
    i = installed
    plan = i.reviewed()
    i.protocol.uncertain = True
    assert i.execute(plan).json()["status"] == "UNCERTAIN"
    i.protocol.business = OTHER
    assert i.post(f"{native.PREFIX}/actions/{plan['id']}/reconcile", {}).status_code == 409
    assert i.binding.get(plan["id"])["status"] == "UNCERTAIN"
    assert len(i.protocol.posts) == 1


def load_cli():
    spec = importlib.util.spec_from_file_location("native_operator_cli", Path(__file__).parents[1]/"scripts/ramp_native_operator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_disposable_cli_rehearsal_never_constructs_live_transport(monkeypatch, capsys):
    cli = load_cli()
    monkeypatch.setattr(native, "_client", lambda: pytest.fail("Rehearsal must not construct real HTTP"))
    monkeypatch.setattr(native, "_credentials", lambda: pytest.fail("Rehearsal must not read credentials"))
    assert cli.main(["--rehearsal"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["provenance"] == "SIMULATED_RAMP" and report["status"] == "DELIVERED"
    assert report["provider_network_calls"] == 0 and report["disposable"]
    with pytest.raises(SystemExit): cli.main(["--rehearsal", "execute"])


def test_cli_stages_exact_payload_without_network_and_rejects_bypass(installed, capsys):
    cli = load_cli()
    stage = installed.path/"staged.json"
    assert cli.main(["--stage-file", str(stage), "--object-id", BILL, "prepare"]) == 0
    report = json.loads(capsys.readouterr().out)
    request = json.loads(stage.read_bytes())
    assert report["body_sha256"] == sha256(raw(request["body"])).hexdigest()
    assert not installed.protocol.calls
    for path in ("https://demo-api.ramp.com/developer/v1/comments/bills/"+BILL,
                 "/api/ramp/workflow/prepare", native.PREFIX+"/actions/"+"a"*64+"/approve"):
        with pytest.raises(ValueError):
            cli._validate_request({**request, "path": path})
    assert cli.main(["--origin", "https://api.ramp.com", "status"]) == 1


def test_cli_sends_staged_exact_payload_through_mounted_authority(installed, monkeypatch, capsys):
    i = installed
    plan = i.reviewed()
    cli = load_cli()
    stage, credential = i.path/"execute.json", i.path/"reviewer.json"
    credential.write_text(json.dumps(i.key))
    credential.chmod(0o600)
    assert cli.main(["execute", "--action-id", plan["id"], "--review-digest", plan["review_digest"],
                     "--stage-file", str(stage)]) == 0
    capsys.readouterr()
    request = json.loads(stage.read_text())
    i.mandate(request["path"], request["body"], plan["wire"]["effect"])
    # Only the local client constructor is replaced; the existing provider MockTransport remains intact.
    monkeypatch.setattr(cli.httpx, "Client", lambda **kwargs: i.client)
    assert cli.main(["send", "--request-file", str(stage), "--subject", USER,
                     "--credential-file", str(credential)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "DELIVERED" and result["remote_id"] == COMMENT
    assert i.protocol.posts == [plan["wire"]["body"].encode()]


@pytest.mark.parametrize("change", ["expiry", "refresh"])
def test_grant_expiry_or_refresh_requires_new_preparation(installed, change):
    i = installed
    plan = i.reviewed()
    if change == "expiry":
        i.binding._grant.expires_at = utcnow()-timedelta(seconds=1)
    else:
        assert i.post(native.PREFIX+"/preflight", {}).status_code == 200
    assert i.execute(plan).status_code == 409
    assert not i.protocol.posts


def test_native_install_enables_only_native_review_when_global_actions_disabled(installed):
    i = installed
    i.auth.approvals_enabled = False
    assert i.post(native.PREFIX+"/preflight", {}).status_code == 200
    assert i.operator.client.post("/api/auth/challenge", json={
        "subject": USER, "path": "/api/policy", "body_sha256": "a"*64}, headers=i.operator.headers).status_code == 403
    assert i.protocol.posts == []
