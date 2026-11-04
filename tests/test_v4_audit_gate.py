"""Verify the gate against real immutable V3 code and hostile evidence omissions.

These are gate tests, not a V4 release certificate. The release CLI must pass
independently; an unavailable browser remains a release blocker.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audit_gate", ROOT / "scripts/v4_audit_gate.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    report_path = tmp_path_factory.mktemp("audit-v3") / "report.json"
    run = subprocess.run([sys.executable, str(ROOT / "scripts/v4_audit_gate.py"),
                          "--phase", "baseline", "--report", str(report_path)],
                         cwd=ROOT, capture_output=True, timeout=100)
    assert run.returncode in (0, 2), "Exact-V3 gate did not produce a valid baseline report"
    report = json.loads(report_path.read_text())
    assert report["source"]["commit"] == "18afaa6433284dc582d38c02b797dc4e688892f1"
    assert report["release_pass"] is False
    return {row["id"]: row for row in report["results"]}


# These values are frozen independent audit counterexamples, not observations
# generated from the candidate implementation during test execution.
BASELINE_COUNTEREXAMPLES = {
    "P-fold-incorrect-version": ["ELIGIBLE", "5.00", ["amendment-v2"]],
    "P-fold-conflicting-provider-date": "accepted",
    "T-distant-out-of-period-unknown": ["INSUFFICIENT_EVIDENCE", None],
    "T-padded-repeat": ["ELIGIBLE", "200.0000"],
    "D-cent-claim-drops-to-zero": ["INELIGIBLE", None],
    "D-predates-governing-SLA": ["ELIGIBLE", "100.00"],
    "D-missing-doc-reference": ["ELIGIBLE", "100.00"],
    "D-missing-ref-at-ticket-construction": "KeyError 'ref'",
    "J-ambient-rounding-alters-tier": ["INELIGIBLE", None],
    "B-padded-repeat-triggers-tier": ["ELIGIBLE", "2000.00"],
    "T-blank-document-provenance": ["ELIGIBLE", "100.0000"],
    "R-multi-award-same-bill-total": "160.00",
    "R-zero-cent-partial-stage": ["PARTIALLY_APPLIED", "0.00", 1],
    "R-different-product-account-before-award": "80.00",
    "D-desk-old-terms-can-approve": "CLAIM_APPROVED",
    "J-issuance-vs-filing": "INELIGIBLE",
    "W-business-claim-idempotency": 2,
    "W-outbound-allowlist": True,
    "W-lifecycle-ABA": [409, 200, 200],
    "W-mode-session-isolation": False,
    "W-mode-policy-isolation": False,
    "W-novel-missing-component": "41.73",
    "W-tenant-account-binding": True,
    "A-prevention-paid-title": ["price-000-audit", "$9,123.45"],
    "A-case-revision-not-silent": False,
    "A-billing-profile-intent": True,
    "A-guide-ui-api-limit": 422,
    "A-provider-line-preserves-known-facts": True,
    "A-null-bill-status-resilience": False,
    "P-unrelated-outside-line": "None",
    "J-zero-fee-not-claimable": True,
    "A-unattested-capture-provenance": False,
}


@pytest.mark.parametrize("ident,observed", BASELINE_COUNTEREXAMPLES.items())
def test_real_exact_v3_reproduces_frozen_audit_counterexample(baseline, ident, observed):
    expected_status = "UNAVAILABLE" if ident in GATE.PENDING_INTERFACE_ASSERTIONS else "FAIL"
    assert baseline[ident]["status"] == expected_status
    assert baseline[ident]["observed"] == observed


def test_real_baseline_retains_positive_and_unsupported_controls(baseline):
    for ident, category in GATE.FINANCIAL_MANIFEST.items():
        if category in ("control", "boundary"):
            assert baseline[ident]["status"] == "PASS", ident
    assert baseline["W-novel-positive"]["observed"] == "41.73"
    assert baseline["W-novel-positive"]["status"] == "PASS"
    assert baseline["W-viewer-boundary"]["status"] == "PASS"
    assert baseline["P-covered-line-positive"]["status"] == "PASS"


def test_real_baseline_has_complete_manifest_and_explicit_browser_state(baseline):
    assert set(baseline) == GATE.required_ids()
    for ident in ("W-browser-sibling-origin", "A-ui-financial-join-ids"):
        assert baseline[ident]["status"] in ("FAIL", "UNAVAILABLE")
    assert not GATE.release_passes(list(baseline.values()))
    assert set(GATE.PRIMARY) == {"B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08"}
    assert all(set(ids) <= set(baseline) for ids in GATE.PRIMARY.values())


@pytest.mark.parametrize("omitted", sorted(GATE.required_ids()))
def test_missing_any_required_assertion_blocks_release(omitted):
    rows = [dict(id=ident, status="PASS") for ident in GATE.required_ids() if ident != omitted]
    assert not GATE.release_passes(rows)


@pytest.mark.parametrize("status", ["FAIL", "UNAVAILABLE", "SKIP", "UNRUN", None])
def test_any_nonpass_or_duplicate_blocks_release(status):
    rows = [dict(id=ident, status="PASS") for ident in sorted(GATE.required_ids())]
    assert GATE.release_passes(rows)
    rows[0]["status"] = status
    assert not GATE.release_passes(rows)
    rows[0]["status"] = "PASS"
    assert not GATE.release_passes(rows + [rows[0]])


def test_reported_pass_count_cannot_override_negative_assertion():
    def forged():
        return [dict(id="negative", observed=2, expected=1, matches=True, category="defect")]
    rows = GATE.execute_group("test", forged, ["negative"])
    assert rows[0]["status"] == "FAIL"
    assert rows[0]["observed"] == 2
    assert rows[0]["expected"] == 1


@pytest.mark.parametrize("rows", [[], [{"id": "unexpected"}], [{"id": "needed"}, {"id": "needed"}]])
def test_malformed_probe_output_does_not_reduce_required_coverage(rows):
    result = GATE.execute_group("test", lambda: rows, ["needed"])
    assert [row["id"] for row in result] == ["needed"]
    assert result[0]["status"] == "UNAVAILABLE"


def test_exception_messages_and_synthetic_tokens_never_reach_report():
    sentinel = "synthetic-sensitive-value-never-log"
    def crashed():
        raise RuntimeError(sentinel)
    result = GATE.execute_group("test", crashed, ["required-a", "required-b"])
    assert all(row["status"] == "UNAVAILABLE" for row in result)
    assert sentinel not in json.dumps(result)
    assert result[0]["error_type"] == "RuntimeError"


def test_comparison_cannot_replace_gold_or_certify_unrun_baseline(baseline):
    before = dict(phase="baseline", source={"commit": GATE.V3}, release_pass=False,
                  results=list(baseline.values()))
    transitions, verified = GATE.compare_before(before, list(baseline.values()))
    assert len(transitions) == len(GATE.required_ids())
    assert verified is (not any(r["status"] == "UNAVAILABLE" for r in baseline.values()))
    changed = [dict(row) for row in baseline.values()]
    changed[0]["expected"] = "gold learned from candidate"
    with pytest.raises(ValueError):
        GATE.compare_before(before, changed)
    before["source"]["commit"] = "not-the-audited-release"
    with pytest.raises(ValueError):
        GATE.compare_before(before, list(baseline.values()))
