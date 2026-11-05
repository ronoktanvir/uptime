"""Offline public explanations enter signed intake without reading rejection archives."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from uptime.contracts import fingerprint
from uptime.vendor_model import MODEL, save_rejection
from uptime.vendor_public_diagnostics import create_attachment, publish_attachment, public_issues
from uptime.vendor_terms import Document
from test_vendor_resource import ROWS, OVERLAY
from test_v4_routes_integration import App


@pytest.fixture
def public_rejection(tmp_path, monkeypatch):
    rows = deepcopy(ROWS) + [
        ("There is no\nminimum incident duration.", {"unsupported":"untrusted-model-rationale-marker"}),
        ("Supply a signed custodian statement verifying the intervals.", {"evidence":["verification"]}),
    ]
    document = Document(name="Synthetic public diagnostic source", uri="urn:synthetic:public-diagnostic",
                        classification="synthetic_public", text="\n".join(quote for quote, _ in rows))
    digest = sha256(document.text.encode()).hexdigest()
    proposal = {"blocks":[{"id":i, "value":value} for i, (_, value) in enumerate(rows, 1)]}
    receipt = dict(status="REJECTED", model=MODEL, session="synthetic-offline-diagnostic", source_sha256=digest,
                   profile="resource-month", protocol="public_block_ids/2", allow_propositions=True,
                   reason="untrusted-exception-marker", raw_proposal=proposal, raw_proposal_sha256=fingerprint(proposal))
    path = save_rejection(receipt, tmp_path)
    monkeypatch.setenv("UPTIME_PUBLIC_EXTRACTIONS", str(tmp_path))
    return document, path, create_attachment(document, path, digest)


def test_offline_attachment_uses_public_slices_and_fixed_codes(public_rejection, tmp_path):
    document, receipt, attachment = public_rejection
    before = receipt.read_bytes()
    path = publish_attachment(document, attachment, tmp_path)
    assert path.name == attachment["sha256"] + ".json"
    issues = public_issues(document.model_dump(), attachment)
    assert {i["code"] for i in issues} == {"UNSUPPORTED_BLOCK_PROPOSITION", "ISSUER_AUTHORITY_UNESTABLISHED"}
    for issue in issues:
        assert document.text[issue["start"]:issue["end"]] == issue["quote"]
        assert sha256(issue["quote"].encode()).hexdigest() == issue["block_sha256"]
        assert issue["historical_status"] == "REJECTED"
    assert "untrusted-model-rationale-marker" not in json.dumps(issues)
    assert "untrusted-exception-marker" not in json.dumps(issues)
    assert public_issues(document.model_dump(), attachment) == issues
    assert publish_attachment(document, attachment, tmp_path) == path
    assert receipt.read_bytes() == before
    assert not (tmp_path / (attachment["report"]["source_sha256"] + ".json")).exists()


def test_signed_intake_requires_explicit_attachment_and_keeps_private_failures_generic(public_rejection, tmp_path, monkeypatch):
    document, receipt, attachment = public_rejection
    app = App(tmp_path / "public-issues.sqlite")
    endpoint = "/api/vendors/public-issues"
    body = dict(document=document.model_dump(), overlay=OVERLAY)
    try:
        original = app.post(endpoint + "/candidates", body)
        assert original["state"] == "QUARANTINED" and "public_source_issues" not in original
        publish_attachment(document, attachment, tmp_path)
        monkeypatch.setattr("uptime.vendor_model.replay_rejection", lambda *a, **k:pytest.fail("intake replayed a rejection"))
        monkeypatch.setattr("uptime.vendor_model.generate", lambda *a, **k:pytest.fail("intake invoked a model"))
        monkeypatch.setattr(type(receipt), "glob", lambda *a, **k:pytest.fail("intake traversed an archive"))
        before = receipt.read_bytes()
        explained = app.post(endpoint + "/candidates", body)
        assert explained["revision"] == original["revision"] + 1
        assert explained["state"] == "QUARANTINED" and explained["active_version"] is None and explained["actions"] == []
        assert explained["reason"] == "Source or overlay validation failed."
        assert len(explained["public_source_issues"]) == 2
        assert "public_source_document" not in explained and "public_source_diagnostic" not in explained
        assert app.post(endpoint + "/candidates", body) == explained
        for _ in range(2):
            response = app.client.get(endpoint, headers=app.human.headers)
            assert response.status_code == 200 and response.json() == explained
        private = deepcopy(body)
        private["overlay"].update(account="private-account-marker", private_note="private-exception-marker")
        refused = app.post(endpoint + "/candidates", private)
        assert refused["reason"] == "Invalid intake schema."
        assert refused["public_source_issues"] == explained["public_source_issues"]
        assert "private-account-marker" not in json.dumps(refused) and "private-exception-marker" not in json.dumps(refused)
        assert receipt.read_bytes() == before
    finally:
        app.client.close()


@pytest.mark.parametrize("fault", ["rationale", "code", "offset", "quote", "quote-hash", "source", "uri", "stale", "oversize", "address"])
def test_untrusted_or_mismatched_attachment_has_generic_fallback(public_rejection, tmp_path, fault):
    document, _, attachment = public_rejection
    bad = deepcopy(attachment)
    report = bad["report"]
    issue = report["issues"][0]
    if fault == "rationale":
        report["rationale"] = "private-model-rationale-marker"
    elif fault == "code":
        issue["code"] = "private-exception-marker"
    elif fault == "offset":
        issue["start"] += 1
    elif fault == "quote":
        issue["quote"] = "private-quote-marker"
    elif fault == "quote-hash":
        issue["block_sha256"] = "0" * 64
    elif fault == "source":
        report["source_sha256"] = "0" * 64
    elif fault == "uri":
        report["source_uri"] = "urn:private:marker"
    elif fault == "stale":
        report["validator_revision"] = "0" * 64
    elif fault == "oversize":
        issue["quote"] = "x" * 5000
    bad["sha256"] = "0" * 64 if fault == "address" else fingerprint(report)
    assert public_issues(document.model_dump(), bad) == []
    with pytest.raises(ValueError):
        publish_attachment(document, bad, tmp_path)
    folder = tmp_path / "public-diagnostics"
    folder.mkdir(exist_ok=True)
    (folder / (bad["sha256"] + ".json")).write_text(json.dumps(report))
    digest = sha256(document.text.encode()).hexdigest()
    (tmp_path / (digest + ".diagnostic.json")).write_text(json.dumps({"sha256":bad["sha256"]}))
    app = App(tmp_path / "invalid-diagnostic.sqlite")
    try:
        response = app.post("/api/vendors/invalid-diagnostic/candidates", dict(document=document.model_dump(), overlay=OVERLAY))
        assert response["state"] == "QUARANTINED" and "public_source_issues" not in response
        assert response["reason"] == "Source or overlay validation failed."
        assert "private-" not in json.dumps(response)
    finally:
        app.client.close()


def test_cli_export_is_explicit_and_offline(public_rejection, tmp_path, monkeypatch, capsys):
    from uptime.vendor_model import main

    document, receipt, attachment = public_rejection
    document_path = tmp_path / "public.json"
    document_path.write_text(document.model_dump_json())
    monkeypatch.setattr("uptime.vendor_model.generate", lambda *a, **k:pytest.fail("offline export invoked a model"))
    monkeypatch.setattr("sys.argv", ["vendor_model", "--document", str(document_path), "--approved-sha256",
        attachment["report"]["source_sha256"], "--replay-rejection", str(receipt), "--diagnostic-output-dir", str(tmp_path)])
    main()
    assert str(tmp_path / "public-diagnostics" / (attachment["sha256"] + ".json")) in capsys.readouterr().out
