"""Acceptance harness controls; deliberately contain no holdout records."""
from pathlib import Path
import json
import os
from contextlib import contextmanager
import secrets
import subprocess
import sys

import pytest

from scripts.blind_acceptance import (BoundaryError, Fixture, artifact_transport, bound_account, compact_case,
    compare_case, compare_gold, compare_terms, digest, general_control, local_path, money_check,
    project_input_selectors, select_records, write_receipt)


def test_unknown_unavailable_and_wrong_money_are_distinct():
    assert money_check("0.00", None, available=False) == "UNAVAILABLE"
    assert money_check("0.00", None, available=True) == "UNKNOWN_MISMATCH"
    assert money_check(None, "0.00", available=True) == "UNKNOWN_MISMATCH"
    assert money_check("1.01", "1.00", available=True) == "WRONG_MONEY"
    assert money_check("1.00", "1.000", available=True) == "PASS"


def test_case_selection_never_imports_global_or_future_evidence():
    rows = [dict(id="a", available_at="2028-01-01T00:00:00Z"),
            dict(id="b", available_at="2028-01-02T00:00:00Z"),
            dict(id="c", available_at="2028-01-01T00:00:00Z")]
    ready, future = select_records(rows, ["a", "b"], "2028-01-01T00:00:00Z")
    assert [r["id"] for r in ready] == ["a"]
    assert [r["id"] for r in future] == ["b"]
    with pytest.raises(BoundaryError, match="MISSING_INPUT_ID"):
        select_records(rows, ["absent"], "2028-01-01T00:00:00Z")


def test_fixture_cannot_escape_root(tmp_path):
    with pytest.raises(BoundaryError, match="FIXTURE_PATH_INVALID"):
        local_path(tmp_path, "../outside.json")


def fixture_tree(root):
    """An invented harness fixture, not a copy or derivative of the holdout."""
    private = {key: {"path": key + ".json"} for key in ("overlay", "accounts", "evidence", "correspondence", "expected")}
    schema = {"schema_version": "fresh-blind-1", "hash_manifest": "manifest.json", "private": private,
              "public_contract": {"path": "public.md"}}
    data = {"SCHEMA.json": json.dumps(schema), "public.md": "Synthetic harness-only public source.",
            "overlay.json": "{}", "accounts.json": '{"accounts": []}', "evidence.json": "", "correspondence.json": "",
            "expected.json": json.dumps({"terms": {"boundary": "strict_below"}, "cases": [{"id": "case-a",
                "as_of": "2028-01-01T00:00:00Z", "input_artifact_ids": [], "input_correspondence_ids": [],
                "expected": {"outcome": "ELIGIBLE", "amount": "3.14"}}]})}
    for name, text in data.items():
        (root / name).write_text(text)
    (root / "manifest.json").write_text(json.dumps({"files": {name: digest(text.encode()) for name, text in data.items()}}))
    return Fixture(root)


def test_gold_phase_guard_and_explicit_selector_projection(tmp_path):
    fixture = fixture_tree(tmp_path)
    with pytest.raises(BoundaryError, match="GOLD_BEFORE_OBSERVATIONS"):
        fixture.gold()
    with pytest.raises(BoundaryError, match="INPUT_PLAN_REQUIRED"):
        fixture.plan()
    plan = fixture.plan(allow_input_projection=True)
    assert set(plan[0]) == {"id", "as_of", "input_artifact_ids", "input_correspondence_ids"}
    fixture.seal_observations([{"available": False}])
    assert fixture.gold()["cases"][0]["expected"]["amount"] == "3.14"


def test_input_projection_does_not_decode_expected_values(monkeypatch):
    load = json.loads
    decoded = []
    def spy(raw, **kwargs):
        decoded.append(raw)
        return load(raw, **kwargs)
    raw = json.dumps({"terms": {"secret": "harness-gold-marker"}, "cases": [{"id": "case-a", "as_of": "2028-01-01T00:00:00Z",
        "input_artifact_ids": ["item-a"], "input_correspondence_ids": [],
        "expected": {"amount": "harness-gold-marker", "nested": [1, {"quote": '\\"}'}]}}]}).encode()
    monkeypatch.setattr(json, "loads", spy)
    result = project_input_selectors(raw)
    assert result[0]["input_artifact_ids"] == ["item-a"]
    assert all("harness-gold-marker" not in token for token in decoded)


def test_external_case_plan_is_pinned_and_cannot_contain_expectations(tmp_path):
    fixture = fixture_tree(tmp_path)
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"fixture_manifest_sha256": "0" * 64, "cases": []}))
    with pytest.raises(BoundaryError, match="INPUT_PLAN_UNBOUND"):
        fixture.plan(plan)
    plan.write_text(json.dumps({"fixture_manifest_sha256": fixture.manifest_hash,
                               "cases": [{"id": "a", "expected": "ELIGIBLE"}]}))
    with pytest.raises(BoundaryError, match="NONINPUT"):
        fixture.plan(plan)


def test_changed_fixture_never_becomes_new_authorized_input(tmp_path):
    fixture = fixture_tree(tmp_path)
    (tmp_path / "accounts.json").write_text('{"accounts": ["changed"]}')
    assert not fixture.unchanged()
    with pytest.raises(BoundaryError, match="FIXTURE_HASH_MISMATCH"):
        Fixture(tmp_path)


def test_null_resource_does_not_inherit_claim_scope_or_complete_month():
    source = dict(kind="provider_incident", account_id="account-a", resource_id=None,
                  source_locator="source-a", available_at="2028-01-02T00:00:00Z", start="2028-01-01T01:00:00Z",
                  end_exclusive="2028-01-01T01:05:00Z", incident_id="incident-a", all_valid_enqueue_requests_failed=True)
    role, envelope, body, code = artifact_transport(source, {"account": "account-a", "component": "resource-a"})
    assert role == "status" and envelope["component"] is None
    assert body["complete"] is False and body["intervals"][0]["resource_id"] is None
    assert code == "INCIDENT_IS_NOT_COMPLETE_MONTH"


def test_historical_receipt_is_not_disguised_as_scoped_artifact():
    source = dict(kind="historical_customer_filing_receipt", account_id="account-a", resource_id="resource-a",
                  source_locator="source-a", available_at="2028-01-02T00:00:00Z", received_at="2028-01-01T00:00:00Z")
    role, envelope, body, code = artifact_transport(source, {"account": "account-a", "component": "resource-a"})
    assert body == source and role == "customer" and code == "HISTORICAL_FILING_UNSUPPORTED"


def test_billing_preserves_signed_discount_and_prior_credit():
    source = dict(kind="invoice", account_id="account-a", source_locator="invoice-a",
                  available_at="2028-02-01T00:00:00Z", currency="USD", previously_granted_credit="2.50",
                  lines=[dict(line_id="discount-a", resource_id="resource-a", type="allocated_discount", amount="-4.25")])
    _, _, body, code = artifact_transport(source, {"account": "account-a", "component": "resource-a", "month": "2028-01"})
    assert body["lines"][0]["amount_cents"] == -425
    assert body["previously_granted_credit"] == "2.50" and code == "SIGNED_DISCOUNT_AND_PRIOR_CREDIT_UNSUPPORTED"


def test_scope_controls_do_not_gain_consent():
    accounts = [dict(account_id="account-a", resource_id="resource-a", consenting=True),
                dict(account_id="account-b", resource_id="resource-b", consenting=False)]
    overlay = dict(authorized_account="account-a", authorized_resource="resource-a",
                   excluded_account_ids=["account-b"], excluded_resource_ids=[])
    assert bound_account(accounts, overlay, {})[1]
    assert not bound_account(accounts, overlay, {"account_id": "account-b", "resource_id": "resource-b"})[1]


def test_unrun_case_and_unmapped_expectation_block_coverage():
    gold = {"terms": {"boundary": "strict_below"}, "cases": [{"id": "absent", "expected": {"amount": "1.00"}}]}
    report = compare_gold(gold, [])
    assert report["cases"][0]["checks"][0]["status"] == "CASE_NOT_EXECUTED"
    assert report["terms"][0]["status"] == "UNAVAILABLE"
    report = compare_case({"id": "case", "new_financial_assertion": "1.00"}, {})
    assert report[0]["status"] == "EXPECTATION_UNMAPPED"


def test_quarantine_preserves_missing_money_and_does_not_make_gold_zero():
    report = compare_case({"id": "case", "expected": {"amount": "3.14", "outcome": "ELIGIBLE"}},
                          {"calculation_available": False, "observation": {"available": True, "outcome": "UNSUPPORTED_RULE", "amount": None}})
    assert {r["status"] for r in report} == {"UNAVAILABLE", "WRONG_DECISION"}
    assert report[0]["expected_money"] == "3.14" and report[0]["observed_money"] is None


def test_terms_are_compared_after_observation_without_candidate_expectations():
    assert compare_terms({"boundary": "strict_below"}, [{"boundary": "strict_below"}])[0]["status"] == "PASS"
    assert compare_terms({"boundary": "strict_below"}, [{"boundary": "inclusive"}])[0]["status"] == "WRONG_TERM"
    assert compare_terms({"unrecognized": 1}, [{}])[0]["status"] == "TERM_EXPECTATION_UNMAPPED"


def test_export_never_contains_response_text_or_malformed_money():
    raw = {"outcome": "ELIGIBLE", "stage": "DRAFTED", "amount": "3.14", "text": "private-fixture-marker",
           "scope": {"account": "private-account-marker"}, "ledger": {"awarded": "0.00"}}
    projected = compact_case(raw)
    assert "private" not in json.dumps(projected)
    with pytest.raises(BoundaryError, match="MONEY_ENCODING_INVALID"):
        compact_case(raw | {"amount": "private-fixture-marker"})
    with pytest.raises(BoundaryError, match="MONEY_ENCODING_INVALID"):
        compare_case({"amount": "private-fixture-marker"}, {})


def test_receipt_is_private_create_only(tmp_path):
    path = tmp_path / "receipt.json"
    write_receipt(path, {"fail_codes": ["UNAVAILABLE"]})
    assert os.stat(path).st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_receipt(path, {"fail_codes": []})


def test_general_control_is_read_from_preexisting_source_only():
    setup = general_control(Path(__file__).resolve().parents[1])
    assert len(setup["source_sha256"]) == 64
    assert set(setup) == {"SCOPE", "INTERVAL", "SMALL", "TEXT", "EXPECTED", "source_sha256"}
    assert setup["EXPECTED"] == "52.17"



def test_separate_generality_control_reaches_signed_inbox_without_holdout_gold(monkeypatch):
    from scripts import blind_acceptance as runner
    monkeypatch.setattr(runner, "TRANSPORT_MODE", "testclient")
    # Entirely new harness-only message, never loaded from a private fixture.
    account = {"account_id": "harness-account", "resource_id": "harness-resource"}
    message = {"id": "harness-message", **account, "available_at": "2026-11-04T00:00:00Z",
               "text": "Please provide the affected endpoint."}
    result = runner.exercise_general(Path(__file__).resolve().parents[1], account, [message])
    assert result["delivered_count"] == 1, [row["fail_codes"] for row in result["checks"]]
    row = result["checks"][0]
    assert row["observed"]["stage"] == "NEEDS_EVIDENCE"
    assert row["observed"]["awarded"] == "0.00"
    assert "harness-account" not in json.dumps(result)
    assert message["text"] not in json.dumps(result)


def test_quarantined_case_still_attempts_signed_denial_and_general_control(monkeypatch):
    from scripts import blind_acceptance as runner
    monkeypatch.setattr(runner, "TRANSPORT_MODE", "testclient")
    account = dict(account_id="harness-account", resource_id="harness-resource", service="Harness Service",
                   endpoint="Harness Endpoint", consenting=True)
    overlay = dict(authorized_account=account["account_id"], authorized_resource=account["resource_id"],
                   excluded_account_ids=[], excluded_resource_ids=[], overlay_id="harness-overlay", provider="Harness Provider",
                   valid_from="2026-01-01", valid_until_exclusive="2027-01-01")
    message = {"id": "harness-message", "account_id": account["account_id"], "resource_id": account["resource_id"],
               "available_at": "2026-11-04T00:00:00Z", "text": "Please provide the affected endpoint."}
    plan = dict(id="harness-case", month="2026-10", as_of="2026-11-04T00:00:00Z",
                input_artifact_ids=[], input_correspondence_ids=[message["id"]])
    observed = runner.exercise_case(None, Path(__file__).resolve().parents[1], plan, overlay, [account], [], [message],
                                   b"Unrepresentable synthetic harness-only public contract.")
    assert observed["candidate_state"] == "QUARANTINED", observed["fail_codes"]
    assert "NO_READY_DENIAL_REFUSED" in observed["fail_codes"]
    assert observed["generality"]["delivered_count"] == 1
    assert observed["calculation_available"] is False


def test_private_runtime_drops_buffered_output_before_restoring_descriptors():
    program = """from scripts.blind_acceptance import quiet_runtime
import sys
with quiet_runtime():
    print('harness-private-marker', end='')
    print('harness-error-marker', file=sys.stderr, end='')
print('SAFE')
"""
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True,
                           cwd=Path(__file__).resolve().parents[1])
    assert child.stdout == "SAFE\n" and child.stderr == ""


def test_public_promotion_scenarios_have_independent_math_and_real_cure():
    from scripts.blind_mapping import promotion_scenarios
    from copy import deepcopy
    from test_vendor_resource import compiled, OVERLAY
    manifest = compiled()
    manifest.update(supplement="same_filing_deadline", fee_adjustment="after_discounts")
    public = b"| Below 99.9% | 7% |\n| Below 99% | 18% |"
    scenarios = promotion_scenarios(public, manifest, OVERLAY)
    assert [t["expected"]["outcome"] for t in scenarios] == [
        "ELIGIBLE", "INELIGIBLE", "INSUFFICIENT_EVIDENCE", "ELIGIBLE", "INELIGIBLE"]
    assert scenarios[0]["expected"]["amount"] == "7.00"
    changed = deepcopy(manifest)
    changed["tiers"][0]["credit_units"] = 99_000_000
    assert promotion_scenarios(public, changed, OVERLAY) == scenarios
    missing, cure, late = (s["facts"] for s in scenarios[2:])
    assert len(missing["filing_proof"]["fields"]) + 1 == len(scenarios[0]["facts"]["filing_proof"]["fields"])
    assert cure["filing_proof"]["supplements"][0]["original_ref"] == cure["filing_proof"]["ref"]
    assert late["filing_proof"]["supplements"][0]["received_at"] > cure["filing_proof"]["supplements"][0]["received_at"]


def test_new_listener_uses_exact_ed25519_grants_without_socket_claim(monkeypatch):
    from scripts import blind_acceptance as runner
    from test_v4_routes_integration import SCOPE, INTERVAL
    from uptime.source_config import SenderCredential
    monkeypatch.setattr(runner, "TRANSPORT_MODE", "testclient")
    with runner.listener(SCOPE, "2026-11-03T00:00:00Z") as transport:
        assert all(isinstance(key, SenderCredential) for key in transport.senders.values())
        path = "/api/correspondence/claims/inbox-witness"
        assert transport.post("/api/correspondence/claims", {"claim_id": "inbox-witness", "scope": SCOPE}, "create")
        assert transport.deliver(path, "status", SCOPE, {"kind": "status", **INTERVAL}, "status-a", "2026-11-03T00:00:00Z")
        assert transport.deliver(path, "customer", SCOPE, {"kind": "status", **INTERVAL}, "status-b", "2026-11-03T00:00:00Z") is None
        assert transport.deliver(path, "status", SCOPE | {"component": "ungranted"},
                                 {"kind": "status", **INTERVAL}, "status-c", "2026-11-03T00:00:00Z") is None
        with pytest.raises(BoundaryError, match="ARRIVAL_CLOCK_REVERSED"):
            transport.deliver(path, "status", SCOPE, {"kind": "status", **INTERVAL}, "status-d", "2026-11-02T00:00:00Z")
