"""Acceptance harness controls; deliberately contain no holdout records."""
from pathlib import Path
import json
import os
from contextlib import contextmanager
import secrets
import subprocess
import sys

import pytest

from scripts.blind_acceptance import (BoundaryError, Fixture, bound_account, compact_case,
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
    from scripts.blind_mapping import event_plan
    source = dict(id="provider-a", kind="provider_incident", account_id="account-a", resource_id=None,
                  source_locator="source-a", available_at="2028-01-02T00:00:00Z", start="2028-01-01T01:00:00Z",
                  end_exclusive="2028-01-01T01:05:00Z", incident_id="incident-a", all_valid_enqueue_requests_failed=True)
    scope = {"account": "account-a", "component": "resource-a"}
    manifest = {"symptoms": ["requests fail"]}
    events, gaps = event_plan([source], scope, manifest)
    assert not events and "PROVIDER_RESOURCE_MAPPING_MISSING" in gaps
    events, gaps = event_plan([source | {"resource_id": "resource-a"}], scope, manifest)
    assert events[0]["body"]["complete"] is False
    assert "COMPLETE_MONTH_STATUS_MISSING" in gaps


def test_historical_receipt_preserves_original_identifier_and_clock():
    from scripts.blind_mapping import event_plan
    source = dict(id="original-a", kind="historical_customer_filing_receipt", account_id="account-a", resource_id="resource-a",
                  source_locator="source-a", available_at="2028-01-02T00:00:00Z", received_at="2028-01-01T00:00:00Z",
                  channel="claims@example.invalid", attachments=[])
    supplement = source | {"id": "supplement-a", "kind": "historical_customer_supplement_receipt",
                           "received_at": "2028-01-02T00:00:00Z"}
    events, gaps = event_plan([source, supplement], {"account": "account-a", "component": "resource-a"}, {})
    assert events[0]["role"] == "vendor" and events[0]["body"]["kind"] == "original_filing_receipt"
    assert events[0]["body"]["receipt_id"] == "original-a"
    assert events[0]["body"]["received_at"] == source["received_at"]
    assert events[1]["body"]["original_ref"] == "original-a"
    assert not any(e["body"]["kind"] == "filing_material" for e in events)


def test_billing_joins_signed_allocation_and_never_invents_credit_history():
    from scripts.blind_mapping import event_plan, invoice_report
    source = dict(id="invoice-a", invoice_id="invoice-a", kind="invoice", account_id="account-a", source_locator="invoice-a",
                  available_at="2028-02-01T00:00:00Z", currency="USD", previously_granted_credit="2.50",
                  period_start="2028-01-01T00:00:00Z", period_end_exclusive="2028-02-01T00:00:00Z", total="45.75",
                  lines=[dict(line_id="gross-a", resource_id="resource-a", type="monthly_recurring", amount="50.00"),
                         dict(line_id="discount-a", resource_id=None, type="allocated_discount", amount="-4.25")])
    mapping = dict(id="mapping-a", kind="billing_resource_attestation", account_id="account-a", resource_id="resource-a",
                   source_locator="billing-mapping-a", available_at="2028-02-02T00:00:00Z", invoice_id="invoice-a",
                   recurring_line_id="gross-a", discount_line_id="discount-a", net_recurring="45.75", previously_granted_credit="2.50")
    scope = {"account": "account-a", "component": "resource-a", "month": "2028-01"}
    assert invoice_report(source, None, scope) is None
    assert invoice_report(source, mapping | {"resource_id": "unrelated"}, scope) is None
    assert invoice_report(source, mapping | {"net_recurring": "45.74"}, scope) is None
    assert invoice_report(source, mapping, scope)["itemized_complete"] is True
    assert invoice_report(source | {"total": "99.00"}, mapping, scope)["itemized_complete"] is False
    assert invoice_report(source | {"period_end_exclusive": "2028-01-30T00:00:00Z"}, mapping, scope)["itemized_complete"] is False
    events, gaps = event_plan([source, mapping], scope, {"prior_credit": "subtract_issued_same_resource_month"})
    body = next(e["body"] for e in events if e["body"]["kind"] == "resource_invoice")
    assert body["lines"][0]["amount_cents"] == 4575
    assert body["lines"][0]["discount_cents"] == 425
    assert not any(e["body"]["kind"] == "prior_credit_evidence" for e in events)
    assert "PRIOR_ISSUANCE_IDS_AND_COMPLETE_HISTORY_MISSING" in gaps


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
    # D04-C (2026-11-09): with no installed governing terms the claim family is unknown, so intake refuses the
    # claim before any denial path (previously NO_READY_DENIAL_REFUSED after a drafted claim).
    assert "SCOPE_FAMILY_REFUSED" in observed["fail_codes"] and "NO_READY_DENIAL_REFUSED" not in observed["fail_codes"]
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
    # D04-C (2026-11-09): a claim needs a known family; the built-in Twilio profile needs no installed terms
    # (incident and component, no region). This test only exercises the listener's exact signed grants.
    SCOPE = {k: v for k, v in SCOPE.items() if k != "region"} | {"vendor": "Twilio", "service": "Twilio Messaging API"}
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


def test_post_observation_financial_and_fraction_projection_distinguishes_missing_and_wrong():
    observation = {"observation": {"available": True}, "metrics": {
        "total_microseconds": 100_000_000, "downtime_microseconds": 1_000_000,
        "affected_fee_cents": 12500, "rate_units": 12_500_000, "service_estimate": "15.63",
        "remaining_estimate": "13.63", "prior_issued_cents": 200}}
    expected = dict(confirmed_covered_seconds="1", availability_percent_exact_fraction="99/1",
                    availability_percent_decimal_display="99.000", eligible_base="125.00", credit_percent="12.5",
                    unrounded_credit="15.625", supported_credit="15.63", remaining_credit="13.63",
                    previously_granted_credit="2.00")
    assert {row["status"] for row in compare_case(expected, observation)} == {"PASS"}
    assert compare_case({"supported_credit": "15.62"}, observation)[0]["status"] == "WRONG_MONEY"
    assert compare_case({"confirmed_covered_seconds": "2"}, observation)[0]["status"] == "WRONG_MEASUREMENT"
    assert compare_case({"supported_credit": "15.63"}, {"observation": {"available": True}})[0]["status"] == "UNKNOWN_MISMATCH"
    assert compare_case({"supported_credit": "15.63"}, {})[0]["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("decision,observed,status", [
    ("refuse_account_scope_not_consented", {"scope_refused": True}, "PASS"),
    ("draft_5.00_future_invoice_claim", {"observation": {"available": True, "outcome": "ELIGIBLE", "stage": "EVALUATED"}}, "PASS"),
    ("no_credit_at_exact_99_percent", {"observation": {"available": True, "outcome": "INELIGIBLE", "stage": "EVALUATED"}}, "PASS"),
    ("accept_denial_for_this_interval_because_verified_cause_is_excluded", {
        "observation": {"available": True, "outcome": "INSUFFICIENT_EVIDENCE", "stage": "HUMAN_REVIEW"}}, "WRONG_DECISION"),
])
def test_semantic_decision_predicates_require_actual_outputs(decision, observed, status):
    assert compare_case({"decision": decision}, observed)[0]["status"] == status


def test_provenance_requires_accepted_delivery_or_actual_readback():
    expected = {"required_provenance": ["invoice-reference"]}
    rejected = {"deliveries": [{"accepted": False, "source_ids_sha256": [digest("invoice-reference")]}]}
    assert compare_case(expected, rejected)[0]["status"] == "PROVENANCE_NOT_OBSERVED"
    accepted = {"deliveries": [{"accepted": True, "source_ids_sha256": [digest("invoice-reference")]}]}
    assert compare_case(expected, accepted)[0]["status"] == "PASS"


def test_public_terms_projection_is_vendor_independent_and_exact_at_deadline():
    manifest = dict(rounding="nearest_cent_half_up", boundary="strict_below", interval_measurement=["exact_elapsed", "availability_ratio"],
                    effective=["2028-01-01", None], scope={"product": "paid Test endpoint", "plan": None},
                    tiers=[{"below_units": 98_000_000, "credit_units": 25_000_000}], submission_channel="claims@example.invalid",
                    filing={"kind": "calendar_days", "count": 12, "utc_time": "17:30:00", "endpoint": "inclusive"},
                    remedy="future_noncash_credit", _measurement_month="2028-02")
    expected = dict(effective_date="2028-01-01", amount_rounding="nearest_cent_half_up_once", availability_comparison="exact_unrounded",
                    strict_tiers_descending_credit=[{"availability_below": "98", "credit_percent": "25"}],
                    filing_channel="claims@example.invalid", filing_deadline_inclusive="2028-03-12T17:30:00Z",
                    period_seconds="2505600", period_start="2028-02-01T00:00:00Z", period_end_exclusive="2028-03-01T00:00:00Z",
                    remedy="future_invoice_credit_only")
    assert {r["status"] for r in compare_terms(expected, [manifest])} == {"PASS"}
    assert compare_terms({"filing_deadline_inclusive": "2028-03-12T17:30:00.000001Z"}, [manifest])[0]["status"] == "WRONG_TERM"


def test_saved_private_receipt_contains_no_financial_operands_or_private_clocks(tmp_path):
    path = tmp_path / "receipt.json"
    raw = {"observations": [{"amount": "123.47", "filing_cutoff": "2028-05-03T01:02:03Z",
            "metrics": {"affected_fee_cents": 21439}, "input_diagnostic": {"covered_seconds": "12345.67", "exact_month": False}}]}
    write_receipt(path, raw)
    saved = path.read_text()
    for marker in ("123.47", "2028-05-03T01:02:03Z", "21439", "12345.67"):
        assert marker not in saved
    assert json.loads(saved)["observations"][0]["amount_sha256"] == digest("123.47")


def test_opaque_source_locator_is_hashed_for_wire_without_dropping_provenance():
    from scripts.blind_mapping import event_plan, wire_ref
    locator = "private archive # dated receipt ? account=local"
    row = dict(id="original", kind="historical_customer_filing_receipt", account_id="a", resource_id="r", source_locator=locator,
               available_at="2028-03-03T00:00:00Z", received_at="2028-03-02T00:00:00Z", channel="claims@example.invalid", attachments=[])
    events, _ = event_plan([row], {"account": "a", "component": "r"}, {})
    assert events[0]["body"]["source_ref"] == wire_ref(locator)
    assert events[0]["source_locators"] == [locator] and events[0]["body"]["receipt_id"] == "original"


def test_partial_input_floor_does_not_become_monthly_evidence_or_product_equality():
    from scripts.blind_mapping import bounded_input_diagnostic
    row = dict(id="provider", kind="provider_incident", account_id="a", resource_id="r", start="2028-03-01T01:00:00Z",
               end_exclusive="2028-03-01T01:01:00Z", cause="provider dispatch controller failed", planned_maintenance=False,
               all_valid_enqueue_requests_failed=True)
    scope = {"account": "a", "component": "r"}
    manifest = {"provider_causes": ["provider dispatch controller failed"], "exclusions": []}
    result = bounded_input_diagnostic([row, row | {"id": "duplicate"}], scope, manifest)
    assert result["covered_seconds"] == "60" and result["exact_month"] is False and result["product_result"] is False
    checks = compare_case({"confirmed_covered_seconds": "60"}, {"observation": {"available": True}, "input_diagnostic": result})
    assert checks[0]["input_floor_status"] == "FLOOR_MATCH_ONLY" and checks[0]["status"] == "UNKNOWN_MISMATCH"
    assert "month_complete" not in result


def test_global_refusals_are_counted_and_never_silently_discarded():
    result = compare_gold({"cases": [], "terms": {}, "global_refusal_controls": ["separately specified behavior"]}, [])
    assert result["global_controls"][0]["status"] == "GLOBAL_CONTROL_REQUIRES_INDEPENDENT_EXECUTION"


def test_input_defaults_are_projected_without_expected_values(monkeypatch):
    raw = json.dumps({"cases": [{"id": "case", "as_of": "2028-01-01T00:00:00Z", "input_artifact_ids": [],
                                "input_correspondence_ids": [], "supported_credit": "private-marker"}],
                      "default_account_id": "account", "default_resource_id": "resource"}).encode()
    real, seen = json.loads, []
    def decode(value, **kwargs):
        seen.append(value)
        return real(value, **kwargs)
    monkeypatch.setattr(json, "loads", decode)
    plan = project_input_selectors(raw)
    assert plan[0]["account_id"] == "account" and plan[0]["resource_id"] == "resource"
    assert all("private-marker" not in token for token in seen)


def test_actual_public_artifact_signed_positive_negative_cure_and_late_routes(monkeypatch):
    """Use the already published public artifact; no private corpus or model call."""
    from scripts import blind_acceptance as runner
    root = Path(__file__).resolve().parents[1]
    document = json.loads((root / "docs/v4/evidence/public-source/blind-contract.json").read_bytes())
    monkeypatch.setenv("UPTIME_PUBLIC_EXTRACTIONS", str(root / "docs/v4/evidence/public-extractions"))
    monkeypatch.setenv("UPTIME_MODEL_PROPOSITIONS", "1")
    monkeypatch.setattr(runner, "TRANSPORT_MODE", "testclient")
    from test_vendor_semantic_bindings import review_submission
    from uptime.vendor_bindings import definitions
    def public_review(state, intake):
        review = review_submission(state['manifest'], state['overlay'], intake['document']['text'])
        fee_definitions = {d['id'] for d in definitions(state['manifest']) if d['role'] == 'fee_inclusions'}
        # The public control's separately authored invoice uses this recurring
        # category. Review it against the source fee clause, never expected money.
        for binding in review['bindings']:
            if binding['definition_id'] in fee_definitions:
                binding['literals'] = ['monthly_recurring']
        return review
    # This explicitly authored public fixture review does not change private
    # corpus execution or create authority from expected monetary answers.
    results = runner.independent_inbox_controls(document["text"].encode(), semantic_review=public_review)
    assert len(results) == 3
    assert all(r["passed"] and r["rollback_verified"] for r in results), [r["fail_codes"] for r in results]
    positive, negative, late = results
    assert positive["positive"]["outcome"] == "ELIGIBLE"
    assert len(positive["observed"]["receipt_ids_sha256"]) == 2
    assert negative["observed"]["outcome"] == "INELIGIBLE"
    assert late["observed"]["stage"] == "DENIAL_ACCEPTED"
    assert len(late["observed"]["historical_receipt_ids_sha256"]) == 1
    assert all(r["authority"] == "SCRIPTED_LOCAL_SYNTHETIC" for r in results)


def test_additive_suite_is_explicit_and_preserves_original_manifest(tmp_path):
    from scripts.blind_acceptance import FREEZE
    fixture = fixture_tree(tmp_path)
    original = (tmp_path / "manifest.json").read_bytes()
    extension = {"schema_version": "fresh-blind-boundaries-1", "initial_freeze_commit": FREEZE,
                 "additional_evidence": "extra.jsonl", "additional_expected": "extra-expected.json", "manifest": "extra-manifest.json"}
    (tmp_path / "BOUNDARY-SCHEMA.json").write_text(json.dumps(extension))
    (tmp_path / "extra.jsonl").write_text(json.dumps({"id": "extra-input"}) + "\n")
    (tmp_path / "extra-expected.json").write_text(json.dumps({"eligible_base": "100.00", "period_seconds": "86400", "cases": [
        {"id": "extra-case", "as_of": "2028-01-01T00:00:00Z", "input_artifact_ids": ["extra-input"], "input_correspondence_ids": []}]}))
    hashes = {p.name:digest(p.read_bytes()) for p in tmp_path.iterdir() if p.is_file()}
    (tmp_path / "extra-manifest.json").write_text(json.dumps({"files": hashes}))
    added = Fixture(tmp_path, suite="boundaries")
    assert fixture.plan(allow_input_projection=True)[0]["id"] == "case-a"
    assert added.plan(allow_input_projection=True)[0]["id"] == "extra-case"
    assert added.rows("evidence") == [{"id":"extra-input"}]
    with pytest.raises(BoundaryError, match="GOLD_BEFORE_OBSERVATIONS"):
        added.gold()
    added.seal_observations([])
    assert added.gold()["cases"][0]["eligible_base"] == "100.00"
    assert (tmp_path / "manifest.json").read_bytes() == original


def test_interval_probe_never_invents_an_exact_request_timestamp():
    from scripts.blind_mapping import event_plan
    probe = dict(id="probe", kind="customer_probe", account_id="a", resource_id="r", incident_id="incident", source_locator="probe-source",
                 start="2028-03-01T01:00:00Z", end_exclusive="2028-03-01T02:00:00Z", available_at="2028-03-02T00:00:00Z",
                 credentials_valid=True, rate_limit_exhausted=False, all_valid_enqueue_requests_failed=True)
    events, gaps = event_plan([probe], {"account":"a", "component":"r"}, {})
    assert not any(e["body"]["kind"] == "request_evidence" for e in events)
    assert "REQUEST_INTERVAL_CANNOT_ESTABLISH_EXACT_SAMPLE_TIME" in gaps
    exact = probe | {"requested_at":"2028-03-01T01:23:45Z"}
    events, gaps = event_plan([exact], {"account":"a", "component":"r"}, {})
    report = next(e["body"] for e in events if e["body"]["kind"] == "request_evidence")
    assert report["records"][0]["requested_at"] == exact["requested_at"]
    assert report["records"][0]["valid"] and report["records"][0]["failed"]
