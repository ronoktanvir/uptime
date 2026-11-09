"""Closure-bound accept-denial mandates (Ronok's decision 2a, 2026-11-09).

A mandated reviewer may accept a reviewed denial only under a mandate bound to the
exact reviewed basis and claim state, with no money (max_amount_cents=0) and the
dedicated local purpose "claim-closure". A person performs it; nothing here sends
anything or changes a ledger. Existing mandates keep their signing bytes.
"""
from hashlib import sha256
from time import time
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
import pytest
from pydantic import ValidationError

from uptime import mandates
from uptime.auth import DEFAULT_ORIGIN
from uptime.auth_client import ReviewerClient
from uptime.contracts import Principal, fingerprint
from uptime.storage import database
from tests.test_signed_mandates import ISSUER, TENANT, USER, installation, local

CLAIM = "inbox-closure"
ROUTE = f"/api/correspondence/claims/{CLAIM}/denial-acceptance"
SCOPE = {"currency": "USD", "account": "Cedar Orrery Studio"}
STATE = {"stage": "DENIAL_REVIEW", "revision": 4}
BASIS = fingerprint({"ground": "scheduled maintenance", "notice_hours": 72})


def mandate(db, signer, **overrides):
    at = int(time())
    values = {**mandates.describe(db, USER), "schema_version": "uptime-reviewer-mandate/1", "mandate_id": str(uuid4()),
              "valid_from": at - 1, "valid_until": at + 300, "issuer": ISSUER, "path": ROUTE,
              "body_sha256": sha256(b"{}").hexdigest(), "effect": None, **overrides}
    m = mandates.Mandate.model_validate(values)
    return mandates.SignedMandate(mandate=m, signature=signer.sign(m.signing_bytes()).hex())


def closure_issuer(db, purposes=("claim-closure",)):
    signer = Ed25519PrivateKey.generate()
    mandates.register_issuer(db, mandates.Issuer(subject=ISSUER, public_key=signer.public_key().public_bytes_raw().hex(),
                                                 local_purposes=purposes))
    return signer


def test_denial_acceptance_path_has_its_own_purpose():
    assert mandates.local_purpose(ROUTE) == "claim-closure"
    assert mandates.local_purpose(f"/api/correspondence/claims/{CLAIM}/actions/approve-claim") == "claim-filing"


def test_closure_decision_carries_no_money_and_only_accept_denial():
    exact = mandates.closure_preview(CLAIM, BASIS, SCOPE, STATE)
    assert exact.max_amount_cents == 0 and exact.action == "accept-denial"
    assert exact.claim_state_sha256 == fingerprint([SCOPE, STATE]) and exact.scope_sha256 == fingerprint(SCOPE)
    with pytest.raises(ValidationError):
        exact.model_validate({**exact.model_dump(), "max_amount_cents": 1})
    with pytest.raises(ValidationError):
        exact.model_validate({**exact.model_dump(), "action": "submit-claim"})


def test_closure_mandate_binds_exact_basis_and_claim_state(tmp_path):
    db = tmp_path / "closure.db"
    authority, human, _ = installation(db, issuer=False)
    signer = closure_issuer(db)
    state = dict(STATE)
    app = FastAPI()
    authority.register(app)

    @app.exception_handler(PermissionError)
    async def denied(request, exc):
        return JSONResponse({"detail": str(exc)}, 403)

    @app.post(ROUTE)
    def accept(p=Depends(authority.reviewer)):
        with database(db) as conn:
            mandates.check_closure_decision(conn, p, mandates.closure_preview(CLAIM, BASIS, SCOPE, state))
        return {"closed": True}

    exact = mandates.closure_preview(CLAIM, BASIS, SCOPE, STATE)
    with local(app) as client:
        user = ReviewerClient(client, DEFAULT_ORIGIN, USER, human)
        cases = [({"basis_sha256": fingerprint({"ground": "different"})}, STATE, 403),
                 ({"scope_sha256": fingerprint({"currency": "USD", "account": "Other"})}, STATE, 403),
                 ({}, {**STATE, "revision": 5}, 403),
                 ({}, STATE, 200)]
        for changes, current, status in cases:
            mandates.install(db, mandate(db, signer, closure=exact.model_copy(update=changes)))
            state.clear(); state.update(current)
            assert user.post(ROUTE, {}).status_code == status


def test_routine_or_filing_issuer_cannot_close_and_path_needs_a_closure(tmp_path):
    for purposes in (("workspace",), ("claim-filing",)):
        db = tmp_path / f"{purposes[0]}.db"
        installation(db, issuer=False)
        signer = closure_issuer(db, purposes)
        with pytest.raises(PermissionError):
            mandates.install(db, mandate(db, signer, closure=mandates.closure_preview(CLAIM, BASIS, SCOPE, STATE)))
    db = tmp_path / "missing.db"
    installation(db, issuer=False)
    signer = closure_issuer(db)
    with pytest.raises(ValidationError):
        mandate(db, signer)  # the closure path without a closure decision


@pytest.mark.parametrize("extra", [
    {"path": f"/api/correspondence/claims/inbox-other/denial-acceptance"},
    {"path": f"/api/correspondence/claims/{CLAIM}/actions/submit-claim"},
    {"claim": mandates.ClaimDecision(claim_id=CLAIM, action="approve-claim", scope_sha256=fingerprint(SCOPE),
                                     packet_sha256=BASIS, currency="USD", max_amount_cents=0)},
])
def test_closure_cannot_move_paths_or_combine_with_other_decisions(tmp_path, extra):
    db = tmp_path / "combine.db"
    installation(db, issuer=False)
    signer = closure_issuer(db)
    with pytest.raises(ValidationError):
        mandate(db, signer, closure=mandates.closure_preview(CLAIM, BASIS, SCOPE, STATE), **extra)


def test_existing_mandates_keep_their_signing_bytes(tmp_path):
    db = tmp_path / "bytes.db"
    installation(db)
    signer = Ed25519PrivateKey.generate()
    m = mandate(db, signer, path="/api/policy").mandate
    assert b'"closure"' not in m.signing_bytes()
    assert b'"claim"' not in m.signing_bytes() and b'"credit"' not in m.signing_bytes()


def test_unmandated_legacy_reviewer_exemption_is_unchanged():
    actual = mandates.closure_preview(CLAIM, BASIS, SCOPE, STATE)
    assert mandates.check_closure_decision(None, Principal("bears", "reviewer", "reviewer"), actual) is None
    with pytest.raises(PermissionError):
        mandates.check_closure_decision(None, Principal(TENANT, "reviewer", "reviewer"), actual)
