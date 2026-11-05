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
