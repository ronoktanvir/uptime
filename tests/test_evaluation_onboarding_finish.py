"""Supplementary runner protections, using no model and no cohort answers."""
from contextlib import contextmanager
from hashlib import sha256
import json

import pytest

from scripts import evaluate_onboarding_finish as runner


def test_source_and_input_freeze_refuses_drift_before_dispatch(tmp_path, monkeypatch):
    source = tmp_path / "document.json"
    source.write_text('{"text":"public source"}')
    pins = {str(source): sha256(source.read_bytes()).hexdigest()}
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *a, **kw: b"")
    assert runner.verify_freeze(source_commit="frozen", pinned_inputs=pins)
    source.write_text('{"text":"changed source"}')
    with pytest.raises(ValueError, match="input hash"):
        runner.verify_freeze(source_commit="frozen", pinned_inputs=pins)
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *a, **kw: b"uptime/vendor_terms.py\n")
    with pytest.raises(ValueError, match="implementation"):
        runner.verify_freeze(source_commit="frozen", pinned_inputs=pins)


def test_no_empty_freeze_or_symlinked_input(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *a, **kw: b"")
    with pytest.raises(ValueError, match="required"):
        runner.verify_freeze(source_commit="frozen", pinned_inputs={})
    source = tmp_path / "source.json"
    source.write_text("{}")
    link = tmp_path / "alias.json"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="non-symlink"):
        runner.verify_freeze(source_commit="frozen", pinned_inputs={str(link): sha256(b"{}").hexdigest()})


class Response:
    status_code = 200
    def __init__(self, body):
        self.body = body
    def json(self):
        return self.body
    def raise_for_status(self):
        pass


@pytest.mark.parametrize("outcome", ["NO_SUPPORTED_FAMILY", "AMBIGUOUS", "INCOMPLETE"])
def test_negative_selection_never_stages_or_fabricates_shadow(tmp_path, monkeypatch, outcome):
    from uptime import source_config
    from types import SimpleNamespace
    document = tmp_path / "document.json"
    document.write_text(json.dumps({"name":"Authored terms", "uri":"https://example.invalid/terms", "classification":"synthetic_public", "text":"Agreement: Authored terms."}))
    overlay = tmp_path / "overlay.json"
    overlay.write_text("{}")
    monkeypatch.setattr(source_config, "load_private", lambda *a: SimpleNamespace(executable="unused", approvals_path=str(tmp_path / "approvals.json")))
    calls = []
    class Signed:
        def post(self, path, body):
            calls.append(path)
            assert path.endswith("/proposal-access")
            return Response({"outcome":outcome})
    @contextmanager
    def served(db, config, lifecycle):
        try:
            yield Signed()
        finally:
            lifecycle["server_stopped"] = True
    monkeypatch.setattr(runner, "_served", served)
    report = runner.run(document_path=document, overlay_path=overlay, run_dir=tmp_path / "attempt", config_path=tmp_path / "config.json", approve=True, approved_by="scripted-evaluation-operator")
    assert len(calls) == 1
    assert report["outcome"] == outcome
    assert report["candidate"] is None and report["previews"] == []
    assert report["started"] is False
    assert report["authority"]["promotion_performed"] is False
    with pytest.raises(FileExistsError):
        runner.run(document_path=document, overlay_path=overlay, run_dir=tmp_path / "attempt", config_path=tmp_path / "config.json", approve=True, approved_by="scripted-evaluation-operator")
    assert len(calls) == 1
