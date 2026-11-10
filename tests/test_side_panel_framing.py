"""Framing stays refused unless an operator names exactly one browser-extension origin.

The option changes only who may display the page. It never lets that origin act: sign-in and
every action still require this app's own origin.
"""
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from uptime.auth import DEFAULT_ORIGIN
from uptime.server import create_app, panel_origin

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = "chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl"
DEFAULT_POLICY = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                  "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


def policy(app):
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 12345)) as client:
        return client.get("/health").headers["content-security-policy"]


def test_framing_is_refused_by_default(tmp_path):
    assert policy(create_app(tmp_path / "default.sqlite", mode="replay")) == DEFAULT_POLICY
    assert policy(create_app(tmp_path / "none.sqlite", mode="replay", side_panel_origin=None)) == DEFAULT_POLICY


def test_one_named_extension_may_frame_and_nothing_else_in_the_policy_changes(tmp_path):
    value = policy(create_app(tmp_path / "panel.sqlite", mode="replay", side_panel_origin=EXTENSION))
    assert value == DEFAULT_POLICY.replace("frame-ancestors 'none'", "frame-ancestors " + EXTENSION)
    directives = [part.strip() for part in value.split(";")]
    assert [part for part in directives if part.startswith("frame-ancestors")] == ["frame-ancestors " + EXTENSION]
    assert "*" not in value and "http" not in value


@pytest.mark.parametrize("value", [
    "*", "'self'", "'none'", "", " ", "https://app.ramp.com", "https://demo.ramp.com", "http://localhost:3000",
    "http://127.0.0.1:8776", "chrome-extension://abc", "chrome-extension://" + "q" * 32,
    "chrome-extension://" + "a" * 31, "chrome-extension://" + "a" * 33, "chrome-extension://" + "a" * 32 + "/",
    "chrome-extension://" + "a" * 32 + " chrome-extension://" + "b" * 32,
    "chrome-extension://" + "a" * 32 + "; script-src *", "CHROME-EXTENSION://" + "a" * 32,
    "chrome-extension://" + "A" * 32, "moz-extension://" + "a" * 32, " " + EXTENSION, EXTENSION + "\n",
    123, ["chrome-extension://" + "a" * 32], True,
])
def test_anything_but_one_exact_extension_origin_is_refused(tmp_path, value):
    with pytest.raises(ValueError, match="exactly one chrome-extension origin"):
        panel_origin(value)
    with pytest.raises(ValueError, match="exactly one chrome-extension origin"):
        create_app(tmp_path / "refused.sqlite", mode="replay", side_panel_origin=value)


@pytest.mark.parametrize("path", ["/", "/health", "/static/style.css", "/static/app.js", "/static/favicon.svg",
                                  "/no-such-page", "/api/policy", "/api/workspace/workflow"])
def test_pages_assets_and_ordinary_refusals_all_carry_the_policy(tmp_path, path):
    """Pages, static files, a missing page and an unauthenticated read: each names who may frame it."""
    for option, expected in ((None, "'none'"), (EXTENSION, EXTENSION)):
        app = create_app(tmp_path / (("panel" if option else "default") + ".sqlite"), mode="replay", side_panel_origin=option)
        with TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 12345)) as client:
            response = client.get(path)
        assert response.status_code in (200, 401, 404)
        directives = [part.strip() for part in response.headers["content-security-policy"].split(";")]
        assert [part for part in directives if part.startswith("frame-ancestors")] == ["frame-ancestors " + expected]


@pytest.mark.parametrize("option", [EXTENSION, None])
def test_the_framing_extension_cannot_act(tmp_path, option):
    app = create_app(tmp_path / "act.sqlite", mode="replay", side_panel_origin=option)
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=("127.0.0.1", 12345)) as client:
        action = {"X-Uptime-Action": "1", "Sec-Fetch-Site": "cross-site"}
        refused = client.post("/api/policy", json={"mode": "OBSERVE", "cap": "0.00"},
                              headers={**action, "Origin": EXTENSION})
        assert refused.status_code == 403
        assert refused.json() == {"detail": "Same-origin authenticated workbench action required"}
        forged = client.post("/api/policy", json={"mode": "OBSERVE", "cap": "0.00"},
                             headers={"X-Uptime-Action": "1", "Origin": EXTENSION})
        assert forged.status_code == 403
        login = client.post("/api/auth/challenge", json={"subject": "nobody", "path": "/api/auth/login", "body_sha256": ""},
                            headers={"X-Uptime-Action": "1", "Origin": EXTENSION})
        assert login.status_code == 403


def test_the_packaged_extension_is_the_one_origin_the_option_is_documented_with():
    manifest = json.loads((ROOT / "extension/manifest.json").read_text())
    digest = hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()[:32]
    identifier = "".join(chr(ord("a") + int(character, 16)) for character in digest)
    assert panel_origin("chrome-extension://" + identifier) == EXTENSION
    assert manifest["permissions"] == ["sidePanel"]
    # Demo line: the Uptime app's own origin, so the panel can recognise a tab on Uptime itself.
    assert manifest["host_permissions"] == ["https://demo.ramp.com/*", "http://127.0.0.1:8776/*"]
    assert EXTENSION in (ROOT / "extension/README.md").read_text()


def test_the_extension_javascript_checks_pass():
    """CI runs these through node directly; this keeps them inside the project's required pytest command too."""
    result = subprocess.run(["node", "--test", "tests/helpers/side_panel_extension.test.cjs"], cwd=ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("value, message", [
    ("https://app.ramp.com", "exactly one chrome-extension origin"),
    (EXTENSION, "applies only to a served app"),
])
def test_enrollment_does_not_silently_accept_the_serving_option(tmp_path, value, message):
    """The option is never stored, so an enrollment that carries it is refused before anything is written."""
    credential = tmp_path / "keys" / "reviewer.jwk"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/serve.py"), "--mode", "replay",
                             "--db", str(tmp_path / "enroll.sqlite"), "--enroll", "someone",
                             "--credential-file", str(credential), "--side-panel-origin", value],
                            cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
    assert message in result.stderr and "Traceback" not in result.stderr
    assert not (tmp_path / "enroll.sqlite").exists() and not credential.exists()


def test_serve_command_refuses_a_bad_origin_before_it_listens(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/serve.py"), "--mode", "replay",
                             "--db", str(tmp_path / "serve.sqlite"), "--port", "0",
                             "--side-panel-origin", "https://app.ramp.com"],
                            cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
    assert "exactly one chrome-extension origin" in result.stderr
    assert not (tmp_path / "serve.sqlite").exists()
