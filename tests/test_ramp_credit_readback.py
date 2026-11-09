"""Controlled tests for the D09 credit/bill link read-back. No credentials, network or writes.

Snapshots come from a read-only test double through the real records sanitizer and
validator. Nothing here is a live receipt.
"""
from datetime import timedelta
import importlib.util
import json
import os
from pathlib import Path

import pytest

from test_ramp_case_lineage import (APRIL, BUSINESS, CREDIT, JANUARY, OTHER_CREDIT, OTHER_VENDOR, T0, base_bills,
                                    capture, raw_bill, raw_credit, uid)
from uptime.ramp_association import AssociationError
from uptime.ramp_case_lineage import credit_links

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ramp_credit_readback", ROOT / "scripts/ramp_credit_readback.py")
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def links(credits=(), statuses=None, bill_id=APRIL, **april):
    snapshot = capture(T0, base_bills(**april), credits, statuses=statuses)
    return credit_links(snapshot, provider_business_id=BUSINESS, bill_id=bill_id)


def test_no_links_on_a_complete_read_is_an_observed_zero():
    result = links()
    assert result["status"] == "NO_APPLIED_CREDITS" and result["links"] == []
    assert result["applied_verified_minor"] == 0 and result["actual_recovery"] is None
    assert result["attribution"] == "NOT_ATTRIBUTED_REQUIRES_REVIEWED_CREDIT_BINDING"


def test_both_sided_applications_count_and_nothing_is_attributed():
    result = links([raw_credit(bills=[(APRIL, 1500)])], applied=[(CREDIT, 1500)])
    assert result["status"] == "VERIFIED_APPLICATIONS" and result["applied_verified_minor"] == 1500
    [row] = result["links"]
    assert (row["state"], row["bill_side_minor"], row["credit_side_minor"]) == ("VERIFIED_BOTH_SIDES", 1500, 1500)
    assert row["credit_remaining_minor"] == 2500 and row["credit_vendor_matches_bill"] is True


@pytest.mark.parametrize("credits,applied,state", [
    ([raw_credit(bills=[(APRIL, 1500)])], [(CREDIT, 1400)], "AMOUNT_OR_CURRENCY_CONFLICT"),
    ([raw_credit()], [(CREDIT, 1500)], "BILL_SIDE_ONLY"),
    ([raw_credit(bills=[(APRIL, 1500)])], [], "CREDIT_SIDE_ONLY"),
])
def test_one_sided_or_conflicting_links_need_review(credits, applied, state):
    result = links(credits, applied=applied)
    assert result["status"] == "REVIEW_REQUIRED" and result["applied_verified_minor"] is None
    assert result["links"][0]["state"] == state


def test_bill_side_credit_missing_from_active_list_is_unknown_not_absent():
    result = links([], applied=[(CREDIT, 1500)])
    assert result["status"] == "UNKNOWN" and result["links"][0]["state"] == "CREDIT_NOT_IN_ACTIVE_LIST"
    assert result["applied_verified_minor"] is None and result["credits_list"]["archived_requested"] is False


def test_incomplete_credit_list_is_unknown():
    result = links([raw_credit()], statuses={"credits": "TRUNCATED"})
    assert result["status"] == "UNKNOWN" and "CREDIT_LIST_INCOMPLETE" in result["reasons"]


def test_credit_created_from_a_paid_bill_is_recorded_not_applied():
    result = links([raw_credit(reference=JANUARY)], bill_id=JANUARY)
    assert result["status"] == "NO_APPLIED_CREDITS" and result["applied_verified_minor"] == 0
    assert result["links"][0]["state"] == "CREATED_FROM_BILL_NOT_APPLIED"
    assert result["links"][0]["created_from_bill"] is True


def test_other_vendor_credit_on_the_bill_needs_review():
    other = raw_credit(OTHER_CREDIT, vendor=OTHER_VENDOR, bills=[(APRIL, 500)])
    result = links([other], applied=[(OTHER_CREDIT, 500)])
    assert result["status"] == "REVIEW_REQUIRED" and "CREDIT_VENDOR_CONFLICT" in result["reasons"]


def test_unobserved_bill_and_invalid_ids_refuse_or_stay_unknown():
    assert links(bill_id=uid(999))["status"] == "UNKNOWN"
    with pytest.raises(AssociationError):
        links(bill_id="not-a-uuid")


def association(snapshot, bill_id=APRIL, **changes):
    return {"status": "ONE_BILL_READ_VERIFIED", "write_attempted": False, "business_id": BUSINESS,
            "bill_id": bill_id, "observed_at": snapshot["observed_at"], **changes}


def test_cli_reads_a_prefilm_receipt_and_writes_one_owner_only_report(tmp_path, capsys):
    snapshot = capture(T0, base_bills(applied=[(CREDIT, 1500)]), [raw_credit(bills=[(APRIL, 1500)])])
    receipt = tmp_path / "prefilm.json"
    receipt.write_text(json.dumps({"schema": "uptime-ramp-prefilm-check/1", "records": snapshot,
                                   "association": association(snapshot)}))
    out = tmp_path / "links.json"
    assert cli.main(["--prefilm-receipt", str(receipt), "--output", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["applied_verified_minor"] == 1500
    assert os.stat(out).st_mode & 0o777 == 0o600
    assert cli.main(["--prefilm-receipt", str(receipt), "--output", str(out)]) == 1


@pytest.mark.parametrize("change,code", [
    (dict(status="NOT_FOUND"), "ASSOCIATION_RECEIPT_NOT_VERIFIED"),
    (dict(observed_at=(T0 + timedelta(hours=2)).isoformat()), "ASSOCIATION_RECEIPT_NOT_CONTEMPORANEOUS"),
])
def test_cli_refuses_unverified_or_stale_association(tmp_path, capsys, change, code):
    snapshot = capture(T0, base_bills())
    records, assoc = tmp_path / "records.json", tmp_path / "assoc.json"
    records.write_text(json.dumps(snapshot))
    assoc.write_text(json.dumps(association(snapshot, **change)))
    assert cli.main(["--records", str(records), "--association-receipt", str(assoc),
                     "--output", str(tmp_path / "out.json")]) == 1
    assert code in capsys.readouterr().err and not (tmp_path / "out.json").exists()
