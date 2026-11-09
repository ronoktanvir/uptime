"""Read-only Ramp context: completeness, links, identity bindings and attribution.

Snapshots come from a read-only test double through the real records sanitizer and
validator (tests/test_ramp_case_lineage.py), or from the packaged capture. The only real
artifact read is the committed human-note receipt. No network, credentials or writes.
"""
import copy
import json
from pathlib import Path

import pytest

from test_ramp_case_lineage import (APRIL, BUSINESS, CREDIT, JANUARY, OTHER_BUSINESS, T0, FakeRamp, base_bills,
                                    capture, raw_bill, raw_credit, uid)
from uptime import installation_revocation, ramp_context
from uptime.ramp_context import capture_summary, ramp_link, record_context
from uptime.ramp_records import seal_snapshot, sync_records
from uptime.ramp_workspace import RampWorkspace
from uptime.workbench import Workbench

ROOT = Path(__file__).resolve().parents[1]
NOTE = json.loads((ROOT / "docs/v4/evidence/demo-path-87/human-ramp-note.json").read_text())
DEMO_BUSINESS, DEMO_BILL, DEMO_COMMENT = NOTE["business_id"], NOTE["bill_id"], NOTE["comment_id"]
DEMO_URL = "https://demo.ramp.com/bill-pay/bills/list/" + DEMO_BILL


def case_for(snapshot, object_id, **changes):
    case = {"id": "ramp-bills-" + object_id, "provider_object_type": "bills", "provider_id": object_id,
            "outcome": "INSUFFICIENT_EVIDENCE", "amount": None, "sources": ["LIVE_RAMP_SANDBOX"],
            "data_provenance": {"classification": "PROVIDER_OBSERVATION", "capture_digest": snapshot["checksum"]}}
    case.update(changes)
    return case


def demo_capture(comments=True, **bill):
    """A capture shaped like the real demo business, with the committed note's exact IDs."""
    row = raw_bill(DEMO_BILL, total=84000, status="OPEN", issued="2026-10-29T00:00:00+00:00")
    row.update({"approval_status": "PENDING", "invoice_number": "INV-1001", **bill})
    row["vendor"]["name"] = "DocuSign"
    thread = {DEMO_BILL: [{"id": DEMO_COMMENT, "created_at": NOTE["created_at"], "message": "PRIVATE",
                           "user_id": uid(77)}]} if comments else {}
    return capture(T0, [row], comments=thread)


# --- Capture completeness -----------------------------------------------------------

def test_partial_capture_is_never_a_complete_account():
    summary = capture_summary(capture(T0, base_bills(), statuses={"transactions": "TRUNCATED"}),
                              business_id=BUSINESS, custody="operator_import", freshness="FRESH")
    assert summary["account_complete"] is False and summary["incomplete_lists"] == ["transactions"]
    tx = next(r for r in summary["resources"] if r["name"] == "transactions")
    assert tx["has_next"] is True and tx["list_complete"] is False


def test_complete_capture_and_per_parent_coverage_is_not_counted_as_a_list():
    snapshot = capture(T0, base_bills())
    summary = capture_summary(snapshot, business_id=BUSINESS, custody="operator_import", freshness="FRESH")
    bills = next(r for r in summary["resources"] if r["name"] == "bills")
    assert bills["listed"] == 3 and bills["retained"] == 3 and bills["list_complete"] is True
    comments = next(r for r in summary["resources"] if r["name"] == "comments")
    assert comments["listed"] is not None  # The "parents" entry, never the per-bill threads
    assert summary["capture_checksum"] == snapshot["checksum"]


def test_packaged_capture_reports_its_real_gaps(tmp_path):
    workspace = RampWorkspace(Workbench(tmp_path / "work.sqlite", "replay"))
    overview = workspace.overview()
    captured = overview["capture"]
    assert captured["custody"] == "packaged_receipt" and captured["business_id"] is None
    assert captured["freshness"] == "HISTORICAL_REPLAY" and captured["account_complete"] is False
    assert captured["incomplete_lists"] == ["purchase_orders", "transactions"]
    vendors = next(r for r in captured["resources"] if r["name"] == "vendors")
    assert (vendors["retained"], vendors["listed"], vendors["has_next"]) == (12, 40, True)
    row = next(r for r in overview["records"] if r["provider_object_type"] == "bills"
               and r["ramp_context"]["agreement_binding"]["status"] == "NONE")
    context = row["ramp_context"]
    # The November 5 capture predates name capture: shown as not captured, never inferred.
    assert context["vendor_name"] is None and context["invoice_number"] is None and context["ramp_link"] is None
    assert context["credit_links"]["status"] == "UNKNOWN" and context["credit_links"]["reasons"] == ["BUSINESS_UNVERIFIED"]


# --- Exact links ------------------------------------------------------------------------

def test_link_comes_from_ramp_or_an_observed_url_never_a_pattern():
    snapshot = demo_capture()
    row = next(r for r in snapshot["resources"]["bills"]["records"] if r["id"] == DEMO_BILL)
    assert ramp_link(row, "bills") is None
    verified = {"status": "ONE_BILL_READ_VERIFIED", "bill_id": DEMO_BILL, "browser_url": DEMO_URL}
    assert ramp_link(row, "bills", association=verified) == {"url": DEMO_URL, "basis": "OPERATOR_OBSERVED_URL"}
    for bad in (dict(verified, status="NOT_FOUND"), dict(verified, bill_id=uid(5)),
                dict(verified, browser_url=DEMO_URL + "?x=1"), dict(verified, browser_url="https://app.ramp.com/x")):
        assert ramp_link(row, "bills", association=bad) is None
    provider = dict(row, deep_link_url="https://demo.ramp.com/bill-pay/bills/" + DEMO_BILL)
    assert ramp_link(provider, "bills")["basis"] == "PROVIDER_DEEP_LINK"


# --- Exact bindings before a finding is shown on a Ramp record --------------------------

def test_finding_attaches_only_through_a_reviewed_exact_binding():
    snapshot = demo_capture()
    unbound = record_context(snapshot, case_for(snapshot, DEMO_BILL, amount="40.00"), business_id=DEMO_BUSINESS)
    assert unbound["agreement_binding"]["status"] == "NONE" and unbound["finding_attachable"] is False
    digest = "b" * 64
    bound_case = case_for(snapshot, DEMO_BILL, amount="40.00",
                          data_provenance={"binding_digest": digest, "terms_mode": "OPERATOR_ATTESTED"})
    assert record_context(snapshot, bound_case, business_id=DEMO_BUSINESS)["agreement_binding"]["status"] == "CONFLICT"
    assert record_context(snapshot, bound_case, business_id=None,
                          agreements={digest: "MSA 7"})["finding_attachable"] is False
    exact = record_context(snapshot, bound_case, business_id=DEMO_BUSINESS, agreements={digest: "MSA 7"})
    assert exact["agreement_binding"] == {"status": "BOUND", "contract_id": "MSA 7", "binding_digest": digest}
    assert exact["finding_attachable"] is True


def test_northwind_or_hypothetical_terms_never_attach_to_the_demo_bill():
    snapshot = demo_capture()
    for case in (case_for(snapshot, DEMO_BILL, amount="1000.00", sources=["SYNTHETIC_CUSTOMER"]),
                 case_for(snapshot, DEMO_BILL, amount="40.00", finding_kind="SYNTHETIC_INVOICE_CAP"),
                 case_for(snapshot, DEMO_BILL, amount="40.00",
                          data_provenance={"binding_digest": "c" * 64, "terms_mode": "SYNTHETIC_NEGOTIATED"})):
        context = record_context(snapshot, case, business_id=DEMO_BUSINESS, agreements={"c" * 64: "Northwind MSA"})
        assert context["agreement_binding"]["status"] == "HYPOTHETICAL" and context["finding_attachable"] is False
        assert context["agreement_binding"]["contract_id"] is None


# --- Identity and attribution of the person-posted note ---------------------------------

def test_person_posted_note_stays_attributed_to_the_person_on_the_exact_bill():
    snapshot = demo_capture()
    context = record_context(snapshot, case_for(snapshot, DEMO_BILL), business_id=DEMO_BUSINESS)
    assert context["discussion"] == [{"comment_id": DEMO_COMMENT, "created_at": NOTE["created_at"],
                                      "attribution": "PERSON_POSTED_VERIFIED_READBACK"}]
    assert (context["vendor_name"], context["invoice_number"]) == ("DocuSign", "INV-1001")
    assert context["amount"] == {"currency": "USD", "amount": "840"}
    assert context["native_confirmation"] == "RAMP_READ_ONLY" and context["actual_recovery"] is None


@pytest.mark.parametrize("business", [None, OTHER_BUSINESS])
def test_note_is_unattributed_without_the_verified_business(business):
    snapshot = demo_capture()
    context = record_context(snapshot, case_for(snapshot, DEMO_BILL), business_id=business)
    assert [d["attribution"] for d in context["discussion"]] == ["UNATTRIBUTED"]


def test_a_receipt_alone_never_creates_a_ramp_comment_or_confirmation():
    snapshot = demo_capture(comments=False)
    context = record_context(snapshot, case_for(snapshot, DEMO_BILL), business_id=DEMO_BUSINESS)
    assert context["discussion"] == []
    assert context["credit_links"]["status"] == "NO_APPLIED_CREDITS"
    assert context["credit_links"]["applied_verified_minor"] == 0


def test_changed_comment_time_is_not_the_person_posted_note():
    snapshot = demo_capture()
    snapshot["resources"]["comments"]["records"][0]["created_at"] = "2026-11-08T02:00:00+00:00"
    snapshot = seal_snapshot({k: v for k, v in snapshot.items() if k != "checksum"})
    context = record_context(snapshot, case_for(snapshot, DEMO_BILL), business_id=DEMO_BUSINESS)
    assert context["discussion"][0]["attribution"] == "UNATTRIBUTED"


def test_ramp_credit_status_comes_only_from_both_sided_ramp_reads():
    snapshot = capture(T0, base_bills(applied=[(CREDIT, 1500)]), [raw_credit(bills=[(APRIL, 1500)])])
    context = record_context(snapshot, case_for(snapshot, APRIL), business_id=BUSINESS)
    assert context["credit_links"]["status"] == "VERIFIED_APPLICATIONS"
    assert context["credit_links"]["applied_verified_minor"] == 1500


def test_local_ledger_activity_never_appears_as_ramp_confirmation(tmp_path, monkeypatch):
    from uptime.contracts import Principal
    from uptime.storage import initialize, transition_settlement
    monkeypatch.setattr(installation_revocation, "REVOCATION_ROOT", tmp_path / "no-revocations")
    db = tmp_path / "work.sqlite"
    workspace = RampWorkspace(Workbench(db, "sandbox", tenant="ramp-context"))
    snapshot = demo_capture()
    workspace.import_observation(snapshot, DEMO_BUSINESS)
    before = workspace.detail("ramp-bills-" + DEMO_BILL)["ramp_context"]
    initialize(db)
    actor = Principal("ramp-context", "local.reviewer", "reviewer")
    transition_settlement(db, actor, "case-credit", "record-credit", "125.50")
    transition_settlement(db, actor, "case-credit", "apply-partial", "125.50")
    after = workspace.detail("ramp-bills-" + DEMO_BILL)["ramp_context"]
    assert after == before
    assert after["credit_links"]["status"] == "NO_APPLIED_CREDITS" and after["native_confirmation"] == "RAMP_READ_ONLY"
    assert after["discussion"][0]["attribution"] == "PERSON_POSTED_VERIFIED_READBACK"
    overview = workspace.overview()
    assert overview["capture"]["business_id"] == DEMO_BUSINESS and overview["capture"]["custody"] == "operator_import"
