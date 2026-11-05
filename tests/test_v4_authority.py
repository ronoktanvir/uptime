"""Authority attacks against actual application routes, plus signed inbound wire tests."""
from dataclasses import replace
import json
import secrets

from fastapi import Depends
from fastapi.testclient import TestClient
import pytest

from uptime.auth import DEFAULT_ORIGIN, SCRIPT, digest, enroll
from uptime.auth_client import ReviewerClient, action_headers, service_headers
from uptime.auth_keys import generate_reviewer_key, reviewer_signature
from uptime.server import create_app

TARGET = "/api/cases/dispute-cure/actions/approve-claim"
HEADERS = action_headers(DEFAULT_ORIGIN)


def client_for(app):
    return TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 55000))


def human_app(path, *, enabled=False):
    credential = generate_reviewer_key()
    enroll(path, "case.reviewer", credential)
    app = create_app(path, approvals_enabled=enabled)
    return app, credential


def test_consequential_routes_fail_closed_for_signed_in_named_reviewer_by_default(tmp_path):
    app, credential = human_app(tmp_path/"closed.db")
    with client_for(app) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "case.reviewer", credential)
        for target, payload in [(TARGET, {}), ("/api/onboarding/actions/approve", {}),
                                ("/api/policy", {"mode":"ASSISTED", "cap":"0.00"})]:
            assert client.post(target, json=payload, headers=reviewer.headers).status_code == 403
            challenge = client.post("/api/auth/challenge", headers=reviewer.headers, json={
                "subject":"case.reviewer", "path":target, "body_sha256":digest(b"{}")})
            assert challenge.status_code == 403
        assert not client.get("/api/onboarding", headers=reviewer.headers).json()["actions"]
        assert not client.get("/api/policy", headers=reviewer.headers).json()["can_configure"]


def test_read_bearer_alone_and_captured_proofs_cannot_authorize_actions(tmp_path):
    app, credential = human_app(tmp_path/"named.db", enabled=True)
    with client_for(app) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "case.reviewer", credential)
        assert client.post(TARGET, json={}, headers=reviewer.headers).status_code == 403
        wrong_body = reviewer.prepare(TARGET, {})
        assert client.post(TARGET, **{**wrong_body, "content":b"{ }"}).status_code == 403
        wrong_path = reviewer.prepare(TARGET, {})
        assert client.post(TARGET.replace("cure","partial"), **wrong_path).status_code == 403
        second = ReviewerClient(client, DEFAULT_ORIGIN, "case.reviewer", credential)
        swapped = reviewer.prepare(TARGET, {})
        swapped["headers"]["Authorization"] = second.headers["Authorization"]
        assert client.post(TARGET, **swapped).status_code == 403
        exp = reviewer.prepare(TARGET, {})
        nonce = exp["headers"]["X-Uptime-Challenge"]
        app.state.auth.challenges[nonce] = replace(app.state.auth.challenges[nonce], expires=0)
        assert client.post(TARGET, **exp).status_code == 403
        assert client.get("/api/cases/dispute-cure", headers=reviewer.headers).json()["stage"] == "DRAFTED"
        stale = reviewer.prepare(TARGET.replace("cure","partial"), {})
        correct = reviewer.prepare(TARGET, {})
        action = client.post(TARGET, **correct)
        assert action.json()["stage"] == "CLAIM_APPROVED"
        assert "case.reviewer" in str(action.json()["timeline"])
        assert client.post(TARGET, **correct).status_code == 403
        assert client.post(TARGET.replace("cure","partial"), **stale).status_code == 403
        assert client.post("/api/auth/logout", json={}, headers=reviewer.headers).status_code == 200
        assert client.get("/api/dashboard", headers=reviewer.headers).status_code == 401


def test_login_challenge_is_single_use_even_after_an_invalid_attempt(tmp_path):
    app, credential = human_app(tmp_path/"named.db")
    with client_for(app) as client:
        signer = ReviewerClient(client, DEFAULT_ORIGIN, "case.reviewer", credential)
        challenge = signer.challenge("/api/auth/login", "")
        replay = {"challenge":challenge["challenge"], "proof":reviewer_signature(signer.key, challenge["message"])}
        assert client.post("/api/auth/login", json={**replay,"proof":"0"*128}, headers=HEADERS).status_code == 403
        assert client.post("/api/auth/login", json=replay, headers=HEADERS).status_code == 403
        assert client.get("/session/old-bootstrap").status_code == 404


def test_script_scope_restart_and_mode_are_separate(tmp_path):
    token, path = secrets.token_urlsafe(32), tmp_path/"script.db"
    options = {"rehearsal":True, "rehearsal_secret":token, "approvals_enabled":True}
    with client_for(create_app(path, **options)) as first:
        script = ReviewerClient(first, DEFAULT_ORIGIN, SCRIPT, token)
        unused = script.prepare(TARGET, {})
    with client_for(create_app(path, **options)) as restarted:
        assert restarted.get("/api/dashboard", headers=script.headers).status_code == 401
        assert restarted.post(TARGET, **unused).status_code == 401
        renewed = ReviewerClient(restarted, DEFAULT_ORIGIN, SCRIPT, token)
        unused["headers"]["Authorization"] = renewed.headers["Authorization"]
        assert restarted.post(TARGET, **unused).status_code == 403
    with pytest.raises(ValueError, match="different authority"):
        create_app(path)
    with pytest.raises(ValueError, match="different authority"):
        create_app(path, mode="sandbox")
    with pytest.raises(ValueError, match="Scripted rehearsal requires"):
        create_app(tmp_path/"other.db", mode="sandbox", **options)
    with pytest.raises(ValueError, match="named local human"):
        enroll(tmp_path/"normal.db", SCRIPT, token)
    app, credential = human_app(tmp_path/"human.db", enabled=True)
    with client_for(app) as normal:
        assert normal.get("/api/dashboard", headers=renewed.headers).status_code == 401
        assert normal.post(TARGET, **unused).status_code == 401


def test_scripted_identity_can_never_sign_in_to_normal_viewer_or_reviewer(tmp_path):
    app, credential = human_app(tmp_path/"named.db")
    with client_for(app) as client:
        from httpx import HTTPStatusError
        with pytest.raises(HTTPStatusError) as invalid:
            ReviewerClient(client, DEFAULT_ORIGIN, SCRIPT, credential)
        assert invalid.value.response.status_code == 403
        with pytest.raises(HTTPStatusError) as invalid:
            ReviewerClient(client, DEFAULT_ORIGIN, "case.reviewer", generate_reviewer_key())
        assert invalid.value.response.status_code == 403
        assert client.post("/api/auth/enroll", json={}, headers=HEADERS).status_code == 404


def test_inbound_service_proofs_bind_subject_exact_bytes_runtime_and_one_delivery(tmp_path):
    db, path = tmp_path/"inbound.db", "/api/v4/test-inbound"
    keys = {"fixture.vendor.one":secrets.token_urlsafe(32), "fixture.vendor.two":secrets.token_urlsafe(32)}
    payload = json.dumps({"sender":"forged", "receipt":"synthetic"}).encode()

    def new():
        app = create_app(db, service_credentials=keys, approvals_enabled=True)
        @app.post(path)
        async def inbound(body: dict, p=Depends(app.state.auth.service)):
            return {"subject":p.subject,"role":p.role}
        return app

    app = new()
    def signed():
        return service_headers(instance=app.state.auth.instance, origin=DEFAULT_ORIGIN,
                               subject="fixture.vendor.one", key=keys["fixture.vendor.one"], path=path, body=payload)
    with client_for(app) as client:
        headers = signed()
        assert client.post(path, content=payload+b" ", headers=headers).status_code == 403
        assert client.post(path, content=payload, headers={**headers,"X-Uptime-Service":"fixture.vendor.two"}).status_code == 403
        assert client.post(path, content=payload, headers=headers).json() == {"subject":"fixture.vendor.one","role":"service"}
        assert client.post(path, content=payload, headers=headers).status_code == 403
        assert client.post(TARGET, content=payload, headers=signed()).status_code in (401,403)
        old = signed()
    with client_for(new()) as restarted:
        assert restarted.post(path, content=payload, headers=old).status_code == 403


def test_exact_listener_and_peer_enforced(tmp_path):
    app = create_app(tmp_path/"host.db")
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=("192.0.2.1", 55000)) as client:
        assert client.get("/health").status_code == 400
    with client_for(app) as client:
        assert client.get("/health", headers={"Host":"127.0.0.1:8888"}).status_code == 400
        assert client.post("/api/auth/challenge", headers={**HEADERS,"Origin":"http://127.0.0.1:8888"},
                           json={"subject":"any.user"}).status_code == 403


@pytest.mark.parametrize("path", ["/api/vendors", "/api/vendors/intake", "/api/correspondence",
                                  "/api/correspondence/inbound", "/api/v4/inbound"])
def test_intake_body_caps_verify_exact_raw_length(tmp_path, path):
    app = create_app(tmp_path/"size.db")
    @app.post(path)
    async def intake(body: dict, p=Depends(app.state.auth.service)):
        raise AssertionError("Unauthenticated intake reached a handler")
    with client_for(app) as client:
        # The large-intake family reaches auth at more than the ordinary 4 KiB cap.
        assert client.post(path, content=b'{"text":"'+b"a"*5000+b'"}', headers=HEADERS).status_code == 403
        assert client.post(path, content=b"a"*262145, headers=HEADERS).status_code == 413
        assert client.post(path, content=b"a"*5000,
                           headers={**HEADERS, "Content-Length":"2"}).status_code == 413
        assert client.post(path, content=b"{}",
                           headers={**HEADERS, "Content-Length":"10"}).status_code == 413
        assert client.post(path, json={}, headers={k:v for k,v in HEADERS.items() if k!="Origin"}).status_code == 403


def test_offline_enrollment_file_is_private(tmp_path):
    path = tmp_path/"human.db"
    enroll(path, "alice.smith", generate_reviewer_key())
    assert path.stat().st_mode & 0o777 == 0o600


def test_human_database_contains_only_public_verifier_and_it_cannot_sign(tmp_path):
    from uptime.auth_keys import public_bytes
    from uptime.storage import database
    credential = generate_reviewer_key()
    db = tmp_path/"public.db"
    enroll(db, "alice.smith", credential)
    with database(db) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(authority_user)")}
        verifier = connection.execute("SELECT public_key FROM authority_user").fetchone()[0]
    assert columns == {"subject", "role", "public_key"}
    assert verifier == public_bytes(credential)
    assert credential["d"] not in verifier.decode()
    with client_for(create_app(db, approvals_enabled=True)) as client:
        with pytest.raises(ValueError, match="private credential"):
            ReviewerClient(client, DEFAULT_ORIGIN, "alice.smith", json.loads(verifier))
        legitimate = ReviewerClient(client, DEFAULT_ORIGIN, "alice.smith", credential)
        assert legitimate.post(TARGET, {}).status_code == 200


def test_humans_cannot_enroll_password_or_rehearsal_secret(tmp_path):
    from uptime.auth_keys import rehearsal_key
    for credential in ["a"*80, rehearsal_key(secrets.token_urlsafe(32))]:
        with pytest.raises(ValueError):
            enroll(tmp_path/"human.db", "alice.smith", credential)
    assert not (tmp_path/"human.db").exists()


def test_offline_key_export_is_exclusive_private_and_outside_repository(tmp_path):
    from uptime.auth_keys import write_credential
    repository = tmp_path/"repo"
    repository.mkdir()
    private = tmp_path/"alice.json"
    key = generate_reviewer_key()
    assert write_credential(private, key, repository) == private
    assert private.stat().st_mode & 0o777 == 0o600
    assert json.loads(private.read_text()) == key
    with pytest.raises(FileExistsError):
        write_credential(private, generate_reviewer_key(), repository)
    with pytest.raises(ValueError, match="outside the repository"):
        write_credential(repository/"private.json", key, repository)
    with pytest.raises(ValueError, match="absolute"):
        write_credential("private.json", key, repository)
    assert json.loads(private.read_text()) == key


def test_changed_or_shared_enrolled_public_key_cannot_retain_identity(tmp_path):
    from uptime.auth_keys import public_bytes
    from uptime.storage import database
    db = tmp_path/"rotation.db"
    key = generate_reviewer_key()
    enroll(db, "alice.smith", key)
    with pytest.raises(ValueError, match="already enrolled"):
        enroll(db, "bob.jones", key)
    app = create_app(db, approvals_enabled=True)
    with client_for(app) as client:
        first = ReviewerClient(client, DEFAULT_ORIGIN, "alice.smith", key)
        prepared = first.prepare(TARGET, {})
        with database(db) as connection, connection:
            connection.execute("UPDATE authority_user SET public_key=? WHERE subject=?",
                               (public_bytes(generate_reviewer_key()),"alice.smith"))
        assert client.get("/api/dashboard", headers=first.headers).status_code == 403
        assert client.post(TARGET, **prepared).status_code == 403


def test_cli_enrollment_creates_private_key_and_authenticates_normal_account(tmp_path):
    from pathlib import Path
    import subprocess
    import sys
    db, key_path = tmp_path/"cli.db", tmp_path/"alice.json"
    script = Path(__file__).resolve().parents[1]/"scripts/serve.py"
    result = subprocess.run([sys.executable, str(script), "--enroll", "alice.smith", "--mode", "replay",
                             "--db", str(db), "--credential-file", str(key_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0
    key = json.loads(key_path.read_text())
    assert key_path.stat().st_mode & 0o777 == 0o600
    assert key["d"] not in result.stdout+result.stderr
    with client_for(create_app(db)) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, "alice.smith", key)
        assert client.get("/api/dashboard", headers=reviewer.headers).status_code == 200
        assert client.post(TARGET, json={}, headers=reviewer.headers).status_code == 403
    unused = tmp_path/"duplicate.json"
    duplicate = subprocess.run([sys.executable, str(script), "--enroll", "alice.smith", "--mode", "replay",
                                "--db", str(db), "--credential-file", str(unused)],
                               capture_output=True, text=True)
    assert duplicate.returncode != 0
    assert not unused.exists()
    assert json.loads(key_path.read_text()) == key


def test_malleable_signatures_share_one_consumed_challenge(tmp_path):
    from uptime.auth_keys import P256_ORDER
    app, credential = human_app(tmp_path/"signed.db", enabled=True)
    with client_for(app) as client:
        signer = ReviewerClient(client, DEFAULT_ORIGIN, "case.reviewer", credential)
        prepared = signer.prepare(TARGET, {})
        signature_hex = prepared["headers"]["X-Uptime-Proof"]
        r, s = signature_hex[:64], int(signature_hex[64:],16)
        high = max(s, P256_ORDER-s)
        prepared["headers"]["X-Uptime-Proof"] = r + f"{high:064x}"
        assert client.post(TARGET, **prepared).status_code == 200
        prepared["headers"]["X-Uptime-Proof"] = r + f"{P256_ORDER-high:064x}"
        assert client.post(TARGET, **prepared).status_code == 403


def test_malformed_es256_components_and_der_are_rejected(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    from uptime.auth_keys import P256_ORDER
    app, credential = human_app(tmp_path/"invalid-encoding.db", enabled=True)
    with client_for(app) as client:
        signer = ReviewerClient(client, DEFAULT_ORIGIN, "case.reviewer", credential)
        for invalid in [b"", b"\0"*63, bytes(64), P256_ORDER.to_bytes(32,"big")+bytes(31)+b"\1",
                        bytes(31)+b"\1"+P256_ORDER.to_bytes(32,"big"), encode_dss_signature(1,1)]:
            prepared = signer.prepare(TARGET, {})
            prepared["headers"]["X-Uptime-Proof"] = invalid.hex()
            assert client.post(TARGET, **prepared).status_code == 403
        assert client.get("/api/cases/dispute-cure", headers=signer.headers).json()["stage"] == "DRAFTED"


def test_fifty_simultaneous_presentations_of_one_review_proof_authorize_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    app, credential = human_app(tmp_path/"concurrent-key.db", enabled=True)
    with client_for(app) as client:
        signer = ReviewerClient(client, DEFAULT_ORIGIN, "case.reviewer", credential)
        prepared = signer.prepare(TARGET, {})
        ready = Barrier(50)
        def submit(_):
            ready.wait(timeout=10)
            return client.post(TARGET, **prepared).status_code
        with ThreadPoolExecutor(max_workers=50) as pool:
            results = list(pool.map(submit, range(50)))
    assert sorted(results) == [200] + [403]*49


def test_private_reviewer_export_refuses_dangling_and_parent_symlinks(tmp_path):
    from uptime.auth_keys import write_credential
    repo = tmp_path/"repository"
    repo.mkdir()
    target = tmp_path/"not-created.json"
    alias = tmp_path/"key-link.json"
    alias.symlink_to(target)
    with pytest.raises(ValueError, match="without symlinks"):
        write_credential(alias, generate_reviewer_key(), repo)
    real_dir = tmp_path/"keys"
    real_dir.mkdir()
    path_alias = tmp_path/"key-dir-link"
    path_alias.symlink_to(real_dir, target_is_directory=True)
    with pytest.raises(ValueError, match="without symlinks"):
        write_credential(path_alias/"not-created.json", generate_reviewer_key(), repo)
    assert not target.exists() and not list(real_dir.iterdir())
