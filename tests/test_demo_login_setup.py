"""Demo-only name + password sign-in for the scripted walkthrough (added at the owner's request for the recording).

The real signing path is untouched: a demo workspace simply hands the browser the same rehearsal key the credential
file holds, after any password, and the server still verifies a fresh signed proof on sign-in and on every action.
"""
import secrets

from fastapi.testclient import TestClient

from uptime.auth import DEFAULT_ORIGIN, SCRIPT, enroll
from uptime.auth_client import ReviewerClient, action_headers
from uptime.auth_keys import generate_reviewer_key
from uptime.server import create_app

ORIGIN = DEFAULT_ORIGIN
POST = action_headers(ORIGIN)


def client_for(app):
    return TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 55010))


def test_a_demo_workspace_takes_any_password_and_signs_in_the_named_reviewer(tmp_path):
    secret = secrets.token_urlsafe(48)
    app = create_app(tmp_path / "demo.db", rehearsal=True, approvals_enabled=True, rehearsal_secret=secret,
                     rehearsal_subject="ronok-tanvir", demo_login=True)
    with client_for(app) as client:
        context = client.get("/api/auth/context").json()
        assert context["demo_login"] is True
        assert context["subject"] == "ronok-tanvir"
        # Any password is accepted; the response is the signing key the credential file would have held.
        got = client.post("/api/auth/demo-credential",
                          json={"subject": "ronok-tanvir", "password": "literally anything at all"}, headers=POST)
        assert got.status_code == 200
        credential = got.json()["credential"]
        assert credential.get("kty") == "EC" and "d" in credential
        # The same key proves a fresh challenge and reaches an authorized read, as the named reviewer.
        reviewer = ReviewerClient(client, ORIGIN, "ronok-tanvir", credential)
        assert client.get("/api/dashboard", headers=reviewer.headers).status_code == 200
        # The scripted account is still recognised, so scripted setup stays recorded as itself.
        scripted = ReviewerClient(client, ORIGIN, SCRIPT, secret)
        assert client.get("/api/dashboard", headers=scripted.headers).status_code == 200
        # A different name is not a known reviewer.
        assert client.post("/api/auth/demo-credential",
                           json={"subject": "someone-else", "password": "x"}, headers=POST).status_code == 403


def test_without_the_demo_flag_there_is_no_demo_login(tmp_path):
    app = create_app(tmp_path / "plain.db", rehearsal=True, approvals_enabled=True,
                     rehearsal_secret=secrets.token_urlsafe(48))
    with client_for(app) as client:
        context = client.get("/api/auth/context").json()
        assert context["demo_login"] is False
        assert context["subject"] == ""
        assert client.post("/api/auth/demo-credential",
                           json={"subject": SCRIPT, "password": "x"}, headers=POST).status_code == 404


def test_a_real_deployment_never_exposes_a_credential(tmp_path):
    enroll(tmp_path / "real.db", "case.reviewer", generate_reviewer_key())
    app = create_app(tmp_path / "real.db", approvals_enabled=True)  # not a rehearsal workspace
    with client_for(app) as client:
        assert client.get("/api/auth/context").json()["demo_login"] is False
        assert client.post("/api/auth/demo-credential",
                           json={"subject": "case.reviewer", "password": "x"}, headers=POST).status_code == 404
