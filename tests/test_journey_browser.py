"""Safety checks runnable before server integration; no browser download needed."""
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "browser_replay", Path(__file__).resolve().parents[1] / "scripts/browser_replay.py")
browser_replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser_replay)


@pytest.mark.parametrize("host", ["demo-api.ramp.com", "api.ramp.com", "attacker.invalid",
                                  "192.0.2.1", "127.0.0.1.attacker.invalid"])
def test_capture_refuses_provider_or_remote_network(host):
    with pytest.raises(browser_replay.CaptureBlocked):
        browser_replay.require_loopback((host, 443))


@pytest.mark.parametrize("target", ["https://127.0.0.1:8000/", "http://127.0.0.1:8001/",
                                    "http://127.0.0.1:8000.attacker.invalid/",
                                    "http://attacker.invalid/", "file:///etc/passwd"])
def test_browser_requests_must_match_owned_server_origin(target):
    assert not browser_replay.allowed_browser_url(target, "http://127.0.0.1:8000")


def test_capture_cannot_write_artifacts_outside_owned_area(tmp_path):
    with pytest.raises(browser_replay.CaptureBlocked):
        browser_replay.new_artifact_directory(tmp_path / "external")
    assert not (tmp_path / "external").exists()


def test_capture_never_overwrites_prior_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(browser_replay, "ROOT", tmp_path)
    path = tmp_path / "fixtures/qa/artifacts/prior"
    path.mkdir(parents=True)
    evidence = path / "desktop.png"
    evidence.write_bytes(b"prior evidence")
    with pytest.raises(FileExistsError):
        browser_replay.new_artifact_directory(path)
    assert evidence.read_bytes() == b"prior evidence"


def test_capture_error_output_does_not_expose_exception_details(monkeypatch, capsys):
    def unsafe_error(args):
        raise RuntimeError("sensitive-bootstrap-value private-person@example.invalid")
    monkeypatch.setattr(browser_replay, "record", unsafe_error)
    assert browser_replay.main([]) == 1
    output = capsys.readouterr()
    assert "CAPTURE_BLOCKED" in output.err
    assert "sensitive-bootstrap-value" not in output.err
    assert "private-person" not in output.err


def test_short_video_cannot_be_presented_as_two_minute_backup():
    with pytest.raises(SystemExit) as error:
        browser_replay.main(["--duration", "10"])
    assert error.value.code == 2
