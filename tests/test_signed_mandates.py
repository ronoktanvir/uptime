"""Ephemeral independent issuers and reviewer keys exercise the real mounted auth dependency; no provider traffic."""
from hashlib import sha256
from time import time
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

from uptime import mandates
from uptime.auth import Authority, DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key, public_bytes
from uptime.contracts import Principal
from uptime.storage import database

ROUTE = "/api/native/actions/dispatch"
ISSUER = "authority.fixture"
USER = "alice.reviewer"
TENANT = "tenant-a"
BUSINESS = "10000000-0000-4000-8000-000000000001"
BILL = "20000000-0000-4000-8000-000000000001"
TRIGGER = "30000000-0000-4000-8000-000000000001"
COMMENT = {"business_id":BUSINESS, "resource_type":"bill", "resource_id":BILL, "action":"bill.comment.create",
           "payload_sha256":mandates.native_effect_digest("POST", f"/developer/v1/comments/bills/{BILL}", b'{"message":"fixture"}')}
METADATA = {"business_id":BUSINESS, "resource_type":"approval_trigger_instance", "resource_id":TRIGGER,
            "action":"blank_canvas.metadata.update", "payload_sha256":mandates.native_effect_digest(
                "PATCH", f"/developer/v1/blank-canvas-approvals/{TRIGGER}/metadata", b'{"key":"fixture"}')}


def installation(db, *, mode="sandbox", issuer=True, enabled=True):
    human = generate_reviewer_key()
    enroll(db, USER, human, tenant=TENANT, mode=mode)
    authority = Authority(db, mode, False, enabled, None, None, DEFAULT_ORIGIN, TENANT)
    signer = Ed25519PrivateKey.generate()
    if issuer:
        mandates.register_issuer(db, mandates.Issuer(subject=ISSUER, public_key=signer.public_key().public_bytes_raw().hex(),
            business_id=BUSINESS, native_actions=("bill.comment.create","blank_canvas.metadata.update")))
    return authority, human, signer


def signed(db, signer, *, effect=COMMENT, **overrides):
    at = int(time())
    values = {**mandates.describe(db, USER), "schema_version":"uptime-reviewer-mandate/1", "mandate_id":str(uuid4()),
              "valid_from":at-1, "valid_until":at+300, "issuer":ISSUER, "path":ROUTE,
              "body_sha256":sha256(b"{}").hexdigest(), "effect":effect, **overrides}
    m = mandates.Mandate.model_validate(values)
    return mandates.SignedMandate(mandate=m, signature=signer.sign(m.signing_bytes()).hex())


def app_for(authority, effect, *, before_native=None, twice=False):
    app = FastAPI()
    authority.register(app)
    app.state.effects = []
    @app.exception_handler(PermissionError)
    async def denied(request, exc):
        return JSONResponse({"detail":str(exc)}, 403)

    @app.post(ROUTE)
    def act(p=Depends(authority.reviewer)):
        if before_native:
            before_native()
        if effect:
            approved = authority.authorize_native(p, **effect)
            app.state.effects.append(approved)
            if twice:
                authority.authorize_native(p, **effect)
        return {"tenant":p.tenant}

    @app.post(ROUTE+"-other")
    def substitute(p=Depends(authority.reviewer)):
        return {"tenant":p.tenant}

    return app


def local(app):
    return TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 50000))


@pytest.mark.parametrize("effect", [COMMENT, METADATA, None])
def test_separate_issuer_and_reviewer_execute_exact_action_once(tmp_path, effect):
    db = tmp_path/"auth.db"
    auth, human, signer = installation(db)
    grant = signed(db, signer, effect=effect)
    app = app_for(auth, effect)
    with local(app) as client:
        operator = ReviewerClient(client, DEFAULT_ORIGIN, USER, human)
        assert operator.post(ROUTE, {}).status_code == 403
        mandates.install(db, grant)
        assert operator.post(ROUTE+"-other", {}).status_code == 403
        assert operator.post(ROUTE, {"changed":True}).status_code == 403
        assert operator.post(ROUTE, {}).json() == {"tenant":TENANT}
        assert operator.post(ROUTE, {}).status_code == 403
    assert app.state.effects == ([grant.mandate.mandate_id] if effect else [])


@pytest.mark.parametrize("change", [
    {"business_id":"40000000-0000-4000-8000-000000000000"}, {"resource_id":TRIGGER},
    {"resource_type":"approval_trigger_instance"}, {"action":"bill.approve"}, {"payload_sha256":"0"*64},
    METADATA])
def test_wire_effect_substitution_denied_before_any_external_effect(tmp_path, change):
    db = tmp_path/"auth.db"
    auth, human, signer = installation(db)
    mandates.install(db, signed(db, signer))
    app = app_for(auth, {**COMMENT, **change})
    with local(app) as client:
        assert ReviewerClient(client, DEFAULT_ORIGIN, USER, human).post(ROUTE, {}).status_code == 403
    assert app.state.effects == []


@pytest.mark.parametrize("violation", ["unknown-issuer","reviewer-as-issuer","wrong-signature","expired","not-yet-valid",
                                      "wrong-realm","wrong-key","wrong-tenant","wrong-mode","issuer-overreach"])
def test_signed_mandates_verified_before_installation(tmp_path, violation):
    db = tmp_path/"auth.db"
    _, human, signer = installation(db, issuer=violation != "unknown-issuer")
    at = int(time())
    overrides = {"expired":{"valid_from":at-100,"valid_until":at-1}, "not-yet-valid":{"valid_from":at+40,"valid_until":at+60},
                 "wrong-realm":{"workspace_id":"0"*64}, "wrong-key":{"reviewer_key_sha256":"0"*64},
                 "wrong-tenant":{"tenant":"tenant-b"}, "wrong-mode":{"mode":"replay"},
                 "issuer-overreach":{"effect":{**COMMENT,"business_id":TRIGGER}}, "reviewer-as-issuer":{"issuer":USER}}
    if violation == "wrong-signature":
        signer = Ed25519PrivateKey.generate()
    with pytest.raises((PermissionError, ValueError)):
        mandates.install(db, signed(db, signer, **overrides.get(violation,{})))


@pytest.mark.parametrize("change", ["revoked-mandate","revoked-issuer","rotated-reviewer","expired","twice"])
def test_dispatch_revalidates_independent_authority_after_local_authorization(tmp_path, change):
    db = tmp_path/"auth.db"
    auth, human, signer = installation(db)
    grant = signed(db, signer)
    mandates.install(db, grant)
    def between():
        if change == "revoked-mandate":
            mandates.revoke(db, "mandate", grant.mandate.mandate_id)
        if change == "revoked-issuer":
            mandates.revoke(db, "issuer", ISSUER)
        if change == "rotated-reviewer":
            with database(db) as conn, conn:
                conn.execute("UPDATE authority_user SET public_key=? WHERE subject=?", (public_bytes(generate_reviewer_key()),USER))
        if change == "expired":
            with database(db) as conn, conn:
                conn.execute("UPDATE reviewer_mandate SET ticket_until=0")
    app = app_for(auth, COMMENT, before_native=between, twice=change=="twice")
    with local(app) as client:
        assert ReviewerClient(client, DEFAULT_ORIGIN, USER, human).post(ROUTE, {}).status_code == 403
    assert len(app.state.effects) == int(change=="twice")


def test_unissued_identity_and_replay_environment_cannot_authorize_native(tmp_path):
    db = tmp_path/"auth.db"
    auth, human, signer = installation(db, mode="replay")
    mandates.install(db, signed(db, signer))
    with pytest.raises(PermissionError):
        auth.authorize_native(Principal(TENANT, USER, "reviewer"), **COMMENT)
    app = app_for(auth, COMMENT)
    with local(app) as client:
        assert ReviewerClient(client, DEFAULT_ORIGIN, USER, human).post(ROUTE, {}).status_code == 403
    assert not app.state.effects


def test_registration_separates_issuers_and_enrolled_reviewers(tmp_path):
    db = tmp_path/"auth.db"
    _, _, signer = installation(db)
    with pytest.raises(ValueError, match="issuer"):
        enroll(db, ISSUER, generate_reviewer_key(), tenant=TENANT, mode="sandbox")
    with pytest.raises(PermissionError, match="reviewer"):
        mandates.register_issuer(db, mandates.Issuer(subject=USER, public_key=signer.public_key().public_bytes_raw().hex()))


def test_protected_native_urls_contribute_to_effect_digest():
    comment = f"/developer/v1/comments/bills/{BILL}"
    content = b'{"message":"fixture"}'
    digest = mandates.native_effect_digest("POST", comment, content)
    for method, path, body in [("PATCH", comment, content), ("POST", comment[:-1]+"2", content), ("POST", comment, content+b" ")]:
        assert digest != mandates.native_effect_digest(method, path, body)


def test_derive_effect_only_from_identified_wire_target():
    for action, method, path, raw in [(COMMENT,"POST",f"/developer/v1/comments/bills/{BILL}",b'{"message":"fixture"}'),
                                     (METADATA,"PATCH",f"/developer/v1/blank-canvas-approvals/{TRIGGER}/metadata",b'{"key":"fixture"}')]:
        assert mandates.native_effect_from_request(BUSINESS, method, path, raw).model_dump() == action
        for substituted in (path+"/", path+"?object="+TRIGGER, path.replace("/developer/v1/", "/")):
            with pytest.raises(PermissionError):
                mandates.native_effect_from_request(BUSINESS, method, substituted, raw)
    with pytest.raises(PermissionError):
        mandates.native_effect_from_request(BUSINESS, "POST", f"/developer/v1/blank-canvas-approvals/{TRIGGER}", b'{}')


@pytest.mark.parametrize("y", [0,1,2**255-20,2**255-19,2707385501144840649318225287225658788936804267575313519463743609750303402022])
def test_operator_cannot_import_a_small_order_or_noncanonical_ed25519_verifier(y):
    from uptime.source_config import SourceGrant
    from test_source_config_v4 import SCOPE
    for sign in (0, 2**255):
        bad = (y | sign).to_bytes(32, "little").hex()
        with pytest.raises(ValueError, match="verifier"):
            mandates.Issuer(subject=ISSUER, public_key=bad)
        with pytest.raises(ValueError, match="verifier"):
            SourceGrant(subject=ISSUER, source="status", scope=SCOPE, public_key=bad)


def test_issuer_and_machine_intake_keys_cannot_cross_roles_even_after_rotation(tmp_path):
    from uptime.source_config import SourceConfig, init_config, load_private, update_source
    from test_source_config_v4 import SCOPE
    db = tmp_path/"auth.db"
    _, _, signer = installation(db)
    config = tmp_path/"public.json"
    init_config(config, "sandbox", DEFAULT_ORIGIN, TENANT)
    update_source(config,"add","status.source",source="status",scope=SCOPE,sender_path=tmp_path/"source.json")
    grants = load_private(config, SourceConfig).credentials("sandbox",DEFAULT_ORIGIN,TENANT)
    Authority(db,"sandbox",False,True,None,grants,DEFAULT_ORIGIN,TENANT)
    public = grants["status.source"].public_key
    with pytest.raises(PermissionError, match="Source"):
        mandates.register_issuer(db, mandates.Issuer(subject="another.issuer",public_key=public))
    with pytest.raises(PermissionError, match="issuer"):
        mandates.remember_source_keys(db,[("test.source",signer.public_key().public_bytes_raw().hex())])


def test_dynamic_claim_authorization_checks_current_packet_and_amount(tmp_path):
    db = tmp_path/"claim.db"
    authority, human, _ = installation(db,issuer=False)
    signer = Ed25519PrivateKey.generate()
    mandates.register_issuer(db, mandates.Issuer(subject=ISSUER, public_key=signer.public_key().public_bytes_raw().hex(),
                                                 local_purposes=("claim-filing",)))
    scope = {"currency":"USD","account":"A"}
    packet = {"claim":"inbox-auth","tenant":TENANT,"scope":scope,"requested":"10.01","version":"terms-A"}
    route = "/api/correspondence/claims/inbox-auth/actions/approve-claim"
    app = FastAPI()
    authority.register(app)
    @app.exception_handler(PermissionError)
    async def denied(request, exc):
        return JSONResponse({"detail":str(exc)},403)
    @app.post(route)
    def act(p=Depends(authority.reviewer)):
        with database(db) as conn:
            mandates.check_claim_decision(p, "approve-claim", scope, packet, conn)
        return {"amount":packet["requested"]}
    preview = mandates.claim_preview("approve-claim",scope,packet)
    with local(app) as client:
        user = ReviewerClient(client,DEFAULT_ORIGIN,USER,human)
        for changes, version, result in [({"max_amount_cents":1000},"terms-A",403), ({},"terms-B",403), ({},"terms-A",200)]:
            grant = signed(db,signer,path=route,effect=None,claim=preview.model_copy(update=changes))
            mandates.install(db,grant)
            packet["version"] = version
            assert user.post(route,{}).status_code == result


@pytest.mark.parametrize("path", ["/api/vendors/vendor-a/actions/activate~1~abcd","/api/policy"])
def test_routine_issuer_cannot_promote_vendors_or_change_policy(tmp_path,path):
    db = tmp_path/"scope.db"
    _, _, signer = installation(db)
    with pytest.raises(PermissionError):
        mandates.install(db,signed(db,signer,path=path,effect=None))


def test_custom_tenant_signed_source_to_exact_credit_and_bill(tmp_path):
    """Exercise the actual reviewer, inbox, case and allocation routes, including state changes after issuance."""
    from datetime import UTC, datetime
    import json
    from uptime.auth_client import service_headers
    from uptime.server import create_app
    from uptime.source_config import SourceConfig, SenderCredential, init_config, load_private, update_source
    from test_portfolio_v4 import BODIES, SCOPE
    db = tmp_path/"money.db"
    human = generate_reviewer_key()
    enroll(db, USER, human, tenant=TENANT)
    signer = Ed25519PrivateKey.generate()
    mandates.register_issuer(db, mandates.Issuer(subject=ISSUER, public_key=signer.public_key().public_bytes_raw().hex(),
                                                 local_purposes=("workspace","claim-filing","credit-allocation")))
    config_path = tmp_path/"sources.json"
    init_config(config_path,"replay",DEFAULT_ORIGIN,TENANT)
    senders = {}
    for role in ("customer","billing","status","vendor"):
        file = tmp_path/(role+".json")
        update_source(config_path,"add",role+".fixture",source=role,scope=SCOPE,sender_path=file)
        senders[role] = load_private(file,SenderCredential)
    config = load_private(config_path,SourceConfig)
    app = create_app(db,tenant=TENANT,approvals_enabled=True,service_credentials=config.credentials("replay",DEFAULT_ORIGIN,TENANT))
    app.state.correspondence.clock = lambda:datetime(2026,11,2,12,tzinfo=UTC)
    config.bind(app.state.correspondence)
    ident = "inbox-credit-review"
    inbox = "/api/correspondence/claims/"+ident
    case_path = "/api/cases/"+ident

    def permit(path, payload, **decisions):
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        mandates.install(db,signed(db,signer,path=path,body_sha256=sha256(raw).hexdigest(),effect=None,**decisions))

    with local(app) as client:
        user = ReviewerClient(client,DEFAULT_ORIGIN,USER,human)
        def read():
            response = client.get(case_path,headers=user.headers)
            assert response.status_code == 200, response.text
            return response.json()
        def send(role, event_id, body):
            raw = json.dumps({"scope":SCOPE.model_dump(),"event_id":event_id,"body":body}).encode()
            headers = service_headers(instance=app.state.auth.instance, origin=DEFAULT_ORIGIN,subject=senders[role].subject,
                                      key=senders[role],path=inbox+"/events",body=raw)
            result = client.post(inbox+"/events",content=raw,headers=headers)
            assert result.status_code == 200, result.text
        payload = {"claim_id":ident,"scope":SCOPE.model_dump()}
        permit("/api/correspondence/claims",payload)
        assert user.post("/api/correspondence/claims",payload).status_code == 200
        for role, kind in [("status","status"),("customer","impact"),("billing","invoice")]:
            send(role,"fixture-"+kind,BODIES[kind])
        for operation in ("approve-claim","submit-claim"):
            offer = read()["actions"][0]
            assert offer["id"] == operation
            path = case_path+"/actions/"+operation
            permit(path,{},claim=offer["mandate_claim"])
            result = user.post(path,{})
            assert result.status_code == 200, result.text
        case = read()
        send("vendor","fixture-award",dict(kind="message",receipt_id=case["submissions"][0]["id"],
                                           text="We have approved a service credit of USD 6.00."))
        record_path = case_path+"/actions/record-credit"
        offered = read()["actions"][0]["mandate_credit"]
        assert offered["bill_id"] is None and offered["amount_cents"] == 600
        for changes in ({"max_amount_cents":599},{"credit_id":"other-credit"},{"contract_version":"wrong-version"}):
            permit(record_path,{},credit={**offered,**changes})
            assert user.post(record_path,{}).status_code == 403
            assert read()["ledger"]["posted"] == "0.00"
        permit(record_path,{},credit=offered)
        assert user.post(record_path,{}).status_code == 200
        record = read()["reconciliations"][0]
        bill = {**record["scope"], "id":"eligible-bill", "source_ref":"eligible-bill", "source":"SYNTHETIC_CUSTOMER",
                "amount_cents":1000, "eligible_cents":1000, "effective_date":"2026-11-02"}
        app.state.bench.allocations.record_bill(TENANT,bill)
        apply_path = case_path+"/actions/apply-balance"
        offered = read()["actions"][0]["mandate_credit"]
        assert offered["bill_id"] == bill["id"] and offered["credit_id"] == record["credit_ids"][0]
        permit(apply_path,{},credit=offered)
        # Changing the journal after signature invalidates even a previously correct native bill target.
        app.state.bench.allocations.record_bill(TENANT,{**bill,"id":"tax-only","source_ref":"tax-only","eligible_cents":0})
        assert user.post(apply_path,{}).status_code == 403
        offered = read()["actions"][0]["mandate_credit"]
        permit(apply_path,{},credit={**offered,"bill_id":"other-bill"})
        assert user.post(apply_path,{}).status_code == 403
        permit(apply_path,{},credit=offered)
        result = user.post(apply_path,{})
        assert result.status_code == 200, result.text
        assert read()["ledger"]["applied"] == "6.00"
