"""Controlled tests for the read-only pre-filming check. No credentials, network or writes.

Ramp responses come from a read-only test double through the real installation, records
and lineage code. Nothing here is a live receipt.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest

from test_ramp_case_lineage import COMMENT, FakeRamp, raw_bill, raw_credit, uid
from uptime.ramp_case_lineage import EVIDENCE_GAP_NOTE

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ramp_prefilm_check", ROOT / "scripts/ramp_prefilm_check.py")
prefilm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prefilm)

BUSINESS, BILL, OTHER = uid(900), uid(10), uid(11)
URL = "https://demo.ramp.com/bill-pay/bills/list/" + BILL
NOTE_AT = "2026-11-08T01:46:45+00:00"


class ReadOnlyRamp(FakeRamp):
    """Adds the installation token and business read; every call is recorded."""
    _basic = "synthetic-test-auth"
    client_fingerprint = "a" * 64

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def _http(self, method, path, headers, body=None):
        self.calls.append((method, path))
        if (method, path) == ("POST", "token"):
            return {"access_token": "synthetic", "token_type": "bearer", "scope": "business:read"}
        assert (method, path) == ("GET", "business")
        return {"id": BUSINESS}

    def request(self, token, method, path, query=None, data=None):
        self.calls.append((method, path))
        return super().request(token, method, path, query, data)


def bills(**changes):
    demo = raw_bill(BILL, total=84000, status="OPEN", issued="2026-10-29T00:00:00+00:00")
    demo.update({"approval_status": "PENDING", **changes})
    return [demo, raw_bill(OTHER, vendor=uid(2), status="OPEN")]


def thread(*extra):
    return {BILL: [{"id": COMMENT, "created_at": NOTE_AT, "message": "PRIVATE", "user_id": uid(77)}, *extra]}


def provider(**kwargs):
    values = dict(bills=bills(), credits=(), comments=thread())
    values.update(kwargs)
    return ReadOnlyRamp(values["bills"], values["credits"], values["comments"])


def receipt():
    return {"schema": "uptime-human-ramp-note-readback/1", "status": "VERIFIED_READBACK", "business_id": BUSINESS,
            "bill_id": BILL, "comment_id": COMMENT, "body": EVIDENCE_GAP_NOTE, "created_at": NOTE_AT,
            "observed_at": "2026-11-08T01:50:35+00:00", "write_attempted": False}


@pytest.fixture(scope="module")
def baseline():
    """Built from one controlled read, in the committed evidence's shape."""
    body = prefilm.check(provider(), bill_url=URL, baseline={
        "association": {"business_id": BUSINESS, "bill_id": BILL}, "capture": {"checksum": "0" * 64},
        "demo_bill": {}, "comments_observed": []}, note_receipt=receipt(), tenant="ramp-demo-native")
    bill = next(r for r in body["records"]["resources"]["bills"]["records"] if r["id"] == BILL)
    return {"association": {"business_id": BUSINESS, "bill_id": BILL},
            "capture": {"checksum": body["capture_checksum"]},
            "demo_bill": {k: bill.get(k) for k in ("vendor_id", "entity_id", "amount", "status",
                                                  "status_summary", "approval_status")},
            "comments_observed": [{"id": COMMENT, "object_type": "bills", "object_id": BILL, "created_at": NOTE_AT}]}


def run(baseline, ramp):
    return prefilm.check(ramp, bill_url=URL, baseline=baseline, note_receipt=receipt(), tenant="ramp-demo-native")


def test_unchanged_bill_and_reobserved_note_pass_with_reads_only(baseline):
    ramp = provider()
    body = run(baseline, ramp)
    assert body["result"] == "PASS" and body["failures"] == [] and body["warnings"] == []
    assert body["comment_ids"] == [COMMENT] and body["writes_attempted"] is False
    assert body["lineage"]["status"] == "FINDING_SURFACED"
    assert all(method == "GET" or (method, path) in {("POST", "token"), ("POST", "vendors/agreements")}
               for method, path in ramp.calls)
    assert "synthetic" not in prefilm.summary(body, "/private/receipt.json")


@pytest.mark.parametrize("ramp,expected", [
    (lambda: provider(comments={}), "NOTE_NOT_REOBSERVED"),
    (lambda: provider(bills=bills(amount={"amount": 90000, "currency_code": "USD", "minor_unit_conversion_rate": 100})),
     "BILL_AMOUNT_CHANGED"),
    (lambda: provider(bills=bills(applied_vendor_credits=[{"id": uid(20), "amount": {
        "amount": 100, "currency_code": "USD", "minor_unit_conversion_rate": 100}}])), "CREDIT_APPLIED_TO_BILL"),
    (lambda: provider(credits=[raw_credit(reference=BILL)]), "CREDIT_LINKED_TO_BILL"),
])
def test_changed_demo_facts_fail(baseline, ramp, expected):
    body = run(baseline, ramp())
    assert body["result"] == "FAIL" and expected in body["failures"]


def test_status_change_and_new_comment_are_warnings_not_failures(baseline):
    extra = {"id": "opaque-comment-2", "created_at": "2026-11-09T09:00:00+00:00", "message": "PRIVATE", "user_id": uid(78)}
    body = run(baseline, provider(bills=bills(approval_status="APPROVED"), comments=thread(extra)))
    assert body["result"] == "PASS"
    assert body["warnings"] == ["BILL_APPROVAL_STATUS_CHANGED", "NEW_COMMENTS_ON_BILL"]


def test_other_business_fails(baseline):
    changed = copy.deepcopy(baseline)
    changed["association"]["business_id"] = uid(901)
    assert "BUSINESS_CHANGED" in run(changed, provider())["failures"]


def private_dir(tmp_path):
    directory = tmp_path / "receipts"
    directory.mkdir(mode=0o700)
    os.chmod(directory, 0o700)
    return directory


def wired(monkeypatch, tmp_path, baseline):
    base, note = tmp_path / "baseline.json", tmp_path / "note.json"
    base.write_text(json.dumps(baseline))
    note.write_text(json.dumps(receipt()))
    monkeypatch.setattr(prefilm, "BASELINE", base)
    monkeypatch.setattr(prefilm, "NOTE_RECEIPT", note)
    monkeypatch.delenv("CI", raising=False)


def test_main_writes_one_owner_only_receipt_and_summary(monkeypatch, tmp_path, capsys, baseline):
    wired(monkeypatch, tmp_path, baseline)
    directory = private_dir(tmp_path)
    assert prefilm.main(["--output-dir", str(directory), "--bill-url", URL], provider_factory=provider) == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith("PREFILM PASS bill=" + BILL[:8]) and "writes=0" in line
    [written] = list(directory.iterdir())
    assert os.stat(written).st_mode & 0o777 == 0o600
    assert json.loads(written.read_text())["result"] == "PASS"


@pytest.mark.parametrize("setup,code", [
    (lambda tmp, mp: (mp.setenv("CI", "true"), private_dir(tmp))[1], "NOT_FOR_CI"),
    (lambda tmp, mp: ROOT / "docs", "OUTPUT_INSIDE_REPOSITORY"),
    (lambda tmp, mp: (os.chmod(private_dir(tmp), 0o750), tmp / "receipts")[1], "OUTPUT_DIRECTORY_NOT_PRIVATE"),
    (lambda tmp, mp: tmp / "missing", "OUTPUT_DIRECTORY_REQUIRED"),
])
def test_main_refuses_before_loading_credentials(monkeypatch, tmp_path, capsys, baseline, setup, code):
    wired(monkeypatch, tmp_path, baseline)
    directory = setup(tmp_path, monkeypatch)
    def forbidden():
        raise AssertionError("credentials loaded")
    assert prefilm.main(["--output-dir", str(directory), "--bill-url", URL], provider_factory=forbidden) == 2
    assert code in capsys.readouterr().err
