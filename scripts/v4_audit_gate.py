#!/usr/bin/env python3
"""Independent before/after gate. Baseline observations never imply release approval.

Run with the test interpreter. --phase baseline materializes the exact immutable
V3 commit in a temporary archive. --phase release runs against --source. Missing,
crashed and unavailable checks are blocking, including real-browser checks.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

V3 = "18afaa6433284dc582d38c02b797dc4e688892f1"
GATE_ROOT = Path(__file__).resolve().parents[1]

# IDs and categories are pinned from the independent audit, not discovered from
# candidate output. A candidate cannot pass by returning fewer observations.
FINANCIAL_MANIFEST = {'P-UTC-control': 'control',
 'P-fold-incorrect-version': 'defect',
 'P-fold-conflicting-provider-date': 'defect',
 'T-proven-month': 'control',
 'T-distant-out-of-period-unknown': 'defect',
 'T-padded-repeat': 'defect',
 'T-exact-repeat': 'control',
 'D-known-ordinary-case': 'control',
 'D-cent-positive-W2': 'control',
 'D-cent-claim-drops-to-zero': 'defect',
 'D-predates-governing-SLA': 'defect',
 'T-historical-version-control': 'control',
 'D-missing-doc-reference': 'defect',
 'D-missing-ref-at-ticket-construction': 'defect',
 'T-last-instant': 'control',
 'T-first-late-instant': 'control',
 'T-prior-receipt': 'control',
 'T-no-attribution': 'control',
 'T-incomplete-status-month': 'control',
 'T-tax-carrier-third-party': 'control',
 'T-partial-coverage': 'control',
 'T-connection-throughput': 'boundary',
 'T-base-boundary-at': 'control',
 'T-base-boundary-above': 'control',
 'T-min-5-exact': 'control',
 'T-min-below-5': 'control',
 'T-admin-before-cutoff': 'control',
 'T-admin-cutoff': 'control',
 'T-exclusion-splits-short-spans': 'control',
 'T-short-notice': 'control',
 'T-across-month-five-before-clipping': 'control',
 'T-across-month-fraction-under-five': 'control',
 'J-positive': 'control',
 'J-explicit-vendor-aggregate': 'control',
 'J-threshold-operator': 'control',
 'J-june-43min-premium': 'control',
 'J-june-44min-premium': 'control',
 'J-june-22min-enterprise': 'control',
 'J-june-21min-enterprise': 'control',
 'J-99-exact': 'control',
 'J-99-below': 'control',
 'J-95-exact': 'control',
 'J-95-below': 'control',
 'J-on-time': 'control',
 'J-late': 'control',
 'J-sandbox': 'control',
 'J-general-surface': 'control',
 'J-other-product': 'boundary',
 'J-reseller': 'boundary',
 'J-technical-ticket': 'control',
 'J-good-standing': 'control',
 'J-challenge-local-holiday': 'control',
 'J-unknown-holiday-list': 'control',
 'J-ambient-rounding-alters-tier': 'defect',
 'B-single-below-threshold': 'control',
 'B-identical-repeat': 'control',
 'B-padded-repeat-triggers-tier': 'defect',
 'B-inclusive-and-earlier-credit': 'control',
 'B-inclusive-minus-one-cent': 'control',
 'B-only-closed-year': 'control',
 'B-cross-currency': 'boundary',
 'T-blank-document-provenance': 'defect',
 'T-no-document-provenance': 'control',
 'R-idempotent-positive': 'control',
 'R-multi-award-same-bill-total': 'design gap',
 'R-single-award-bill-cap': 'control',
 'R-zero-cent-partial-stage': 'defect',
 'R-different-product-account-before-award': 'design gap',
 'P-tier-999': 'control',
 'P-tier-1000': 'control',
 'P-tier-1001': 'control',
 'P-amendment-end': 'control',
 'P-amendment-start': 'control',
 'P-unsplit-amendment': 'boundary',
 'P-unimplemented-mode': 'boundary',
 'P-unimplemented-quantity_scope': 'boundary',
 'P-late-amendment': 'boundary',
 'D-desk-old-terms-can-approve': 'defect',
 'J-issuance-vs-filing': 'design gap',
 'T-enhanced-SendGrid-region-is-not-availability-input': 'control',
 'T-base-SendGrid-at-same-duration': 'control',
 'T-enhanced-SendGrid-independent-remedy': 'boundary',
 'T-foreign-status-host': 'control',
 'T-region-scope-dispute-preflight': 'control',
 'T-500-overlap-gap-cross-boundary-patterns': 'control'}

WORKFLOW_GROUPS = {
    "stock_denial": ["W-known-exclusion-before-filing"],
    "complete_policy": ["W-complete-policy-packet"],
    "denial_responses": ["W-reply-WINDOW_CLOSED", "W-reply-FREEFORM_MISSING_DOC"],
    "duplicate_and_privacy": ["W-business-claim-idempotency", "W-outbound-allowlist"],
    "lifecycle": ["W-lifecycle-ABA"],
    "malformed_source": ["W-malformed-source-quarantine"],
    "session_isolation": ["W-viewer-boundary", "W-mode-session-isolation", "W-mode-policy-isolation"],
    "novel_evidence": ["W-novel-positive", "W-novel-missing-component", "W-novel-wrong-line-scope"],
    "tenant_account": ["W-tenant-account-positive", "W-tenant-account-binding"],
    "comparative_api": ["A-prevention-paid-title", "A-case-revision-not-silent", "A-billing-profile-intent", "A-guide-ui-api-limit"],
    "captured_line_api": ["A-provider-line-preserves-known-facts", "A-null-bill-status-resilience"],
    "activation_runtime": ["W-activation-runtime"],
    "additional_domain": ["P-covered-line-positive", "P-unrelated-outside-line", "J-zero-fee-not-claimable"],
    "capture_integrity": ["A-unattested-capture-provenance"],
}
PRIMARY = {
    "B01": ["W-browser-sibling-origin", "W-mode-session-isolation"],
    "B02": ["W-known-exclusion-before-filing", "W-complete-policy-packet"],
    "B03": ["D-predates-governing-SLA", "D-desk-old-terms-can-approve", "W-novel-missing-component", "W-novel-wrong-line-scope", "W-reply-WINDOW_CLOSED"],
    "B04": ["P-fold-incorrect-version", "P-fold-conflicting-provider-date", "P-unrelated-outside-line"],
    "B05": ["T-padded-repeat", "B-padded-repeat-triggers-tier"],
    "B06": ["W-business-claim-idempotency", "W-outbound-allowlist"],
    "B07": ["W-lifecycle-ABA", "W-malformed-source-quarantine"],
    "B08": ["R-multi-award-same-bill-total", "R-zero-cent-partial-stage", "R-different-product-account-before-award"],
}
AUDIT_PROVENANCE = {
    "audit": {"path": "ENGINEERING-AUDIT.md", "sha256": "edf0d5d2a2a1b446c2532ad163f46d23489e258bcb29c1a32c12bb8f08719060"},
    "financial": {"path": "evidence/financial/probes.py", "sha256": "196539928b62eca8e8e576b21d0b4d495c019bf14e88b92d1c0b61f334c5a289"},
    "workflow": {"path": "evidence/workflow/workflow_probe.py", "sha256": "249bd86fbb14edec56292e6729e9a97442ea3098cdebc8498f0683803f6f82d0"},
    "novel": {"path": "evidence/workflow/novel_probe.py", "sha256": "d62b65e8865cf50db68b7e183a0241576f220e1fefd932ccb0ac9f55eb805e43"},
    "boundary": {"path": "evidence/independent/boundary_probes.py", "sha256": "7889daeb293d4f14bfe391207158917c50ab97774c5cf38f11c23b16eb9deac7"},
    "independent": {"path": "evidence/independent/probes.py", "sha256": "fcc5bb8a540496ee0ad95351ed0221fcab1fde9b266dab7e1348f342addafe13"},
    "lead": {"path": "evidence/lead/lead_probes.py", "sha256": "d154fd0e8414f658e94b0eee07f64d3db9878230c3a0cf4639db4cd9de25a1d9"},
}
GROUP_EVIDENCE = {
    "financial.collect_financial": ["financial"],
    "workflow.stock_denial": ["workflow", "independent"],
    "workflow.complete_policy": ["workflow"],
    "workflow.denial_responses": ["independent"],
    "workflow.duplicate_and_privacy": ["boundary"],
    "workflow.lifecycle": ["workflow"],
    "workflow.malformed_source": ["workflow"],
    "workflow.session_isolation": ["workflow"],
    "workflow.novel_evidence": ["novel"],
    "workflow.tenant_account": ["workflow"],
    "workflow.comparative_api": ["lead"],
    "workflow.captured_line_api": ["lead"],
    "workflow.activation_runtime": ["workflow", "independent"],
    "workflow.additional_domain": ["independent"],
    "workflow.capture_integrity": ["audit"],
    "browser.browser_sibling_origin": ["workflow"],
}
SYNTHETIC_INPUTS = [
    "fixtures/disputes/claimant/dossiers.json", "fixtures/disputes/simulator/records.json",
    "fixtures/onboarding/extraction.json", "fixtures/onboarding/overlay.json",
    "fixtures/onboarding/observations.json", "fixtures/pricing/agreement.json",
    "fixtures/pricing/cases.json", "fixtures/twilio/cases.json",
    "fixtures/other_obligations/agreement.txt", "fixtures/other_obligations/examples.json",
]


def input_identity(source):
    return {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in SYNTHETIC_INPUTS}

# These audit design gaps require staged/transactional interfaces which do not
# exist in V3. Keep their real observations, but never pretend prose expectations
# are executable V4 acceptance predicates. Lead must supply the reviewed binding.
PENDING_INTERFACE_ASSERTIONS = {
    "R-multi-award-same-bill-total": "durable cross-award allocation interface",
    "R-different-product-account-before-award": "award restriction and bill scope interface",
    "J-issuance-vs-filing": "separate filing and issuance result interface",
}


def load_probe(name):
    path = GATE_ROOT / "tests" / ("test_v4_audit_" + name + ".py")
    spec = importlib.util.spec_from_file_location("v4_audit_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value):
    # Audit expected tuples and JSON lists mean the same ordered observation.
    return json.loads(json.dumps(value, allow_nan=False))


def execute_group(group, callable_, required):
    """Never trust a probe's reported matches/pass count; recompute assertions."""
    try:
        observations = callable_()
        identifiers = [row["id"] for row in observations]
        if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(required):
            raise ValueError("Probe coverage differs from fixed manifest")
        results = []
        for row in observations:
            observed, expected = canonical(row["observed"]), canonical(row["expected"])
            category = FINANCIAL_MANIFEST.get(row["id"], row["category"])
            result = dict(id=row["id"], group=group, category="v3-known-limit" if category == "boundary" else category,
                status="PASS" if observed == expected else "FAIL", observed=observed,
                expected=expected, assertion_source="independent-audit-and-known-mutation",
                callable=callable_.__name__, execution="OBSERVED")
            if row["id"] in PENDING_INTERFACE_ASSERTIONS:
                result.update(status="UNAVAILABLE", error_type="RequiredV4InterfaceNotSupplied",
                              pending_interface=PENDING_INTERFACE_ASSERTIONS[row["id"]])
            results.append(result)
        return results
    except Exception as exc:
        # Exception text may include records or capabilities. Only type is safe.
        return [dict(id=ident, group=group, status="UNAVAILABLE",
                     category=FINANCIAL_MANIFEST.get(ident, "required"),
                     error_type=type(exc).__name__, callable=callable_.__name__,
                     assertion_source="independent-audit-and-known-mutation") for ident in required]


def required_ids():
    return set(FINANCIAL_MANIFEST) | {i for ids in WORKFLOW_GROUPS.values() for i in ids} | {"W-browser-sibling-origin", "A-ui-financial-join-ids"}


def release_passes(results):
    ids = [r["id"] for r in results]
    return (len(ids) == len(set(ids)) and set(ids) == required_ids()
            and all(r.get("status") == "PASS" for r in results))


def compare_before(before, results):
    """The prior artifact supplies observations only, never expected outcomes."""
    if (before.get("phase") != "baseline" or before.get("source", {}).get("commit") != V3
            or before.get("release_pass") is not False):
        raise ValueError("Baseline provenance mismatch")
    previous = before["results"]
    identifiers = [row["id"] for row in previous]
    if len(set(identifiers)) != len(identifiers) or set(identifiers) != required_ids():
        raise ValueError("Baseline coverage mismatch")
    by_id = {row["id"]: row for row in previous}
    transitions = []
    for row in results:
        prior = by_id[row["id"]]
        if prior.get("status") != "UNAVAILABLE" and row.get("status") != "UNAVAILABLE":
            if prior["expected"] != row["expected"]:
                raise ValueError("Independent assertion changed between runs")
        transitions.append(dict(id=row["id"], before=prior["status"], after=row["status"],
                                before_observed=prior.get("observed"), after_observed=row.get("observed")))
    return transitions, all(r["status"] in ("PASS", "FAIL") for r in previous)


def source_identity(source):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()
    digest = hashlib.sha256()
    for directory, pattern in (("uptime", "*.py"), ("web", "*.js"), ("web", "*.html")):
        for path in sorted((source / directory).glob(pattern)):
            digest.update(str(path.relative_to(source)).encode() + b"\0" + path.read_bytes())
    return dict(commit=git("rev-parse", "HEAD"), product_source_sha256=digest.hexdigest(),
                changed_tracked_paths=git("diff", "HEAD", "--name-only").splitlines())


def collect(source):
    sys.path.insert(0, str(source))
    # Fail rather than accidentally testing another checkout already in memory.
    if "uptime" in sys.modules:
        raise RuntimeError("Run the gate in a fresh Python process")
    results = []
    for name, function, ids in [("financial", "collect_financial", list(FINANCIAL_MANIFEST)),
                               *[("workflow", f, ids) for f, ids in WORKFLOW_GROUPS.items()],
                               ("browser", "browser_sibling_origin", ["W-browser-sibling-origin", "A-ui-financial-join-ids"])]:
        def run(name=name, function=function):
            return getattr(load_probe(name), function)()
        run.__name__ = "test_v4_audit_" + name + "." + function
        group = name + "." + function
        rows = execute_group(group, run, ids)
        for row in rows:
            row["audit_evidence"] = [AUDIT_PROVENANCE[key] for key in GROUP_EVIDENCE[group]]
        results.extend(rows)
    return results


def archive_v3(source, destination):
    archive = destination / "v3.tar"
    with archive.open("wb") as output:
        subprocess.run(["git", "-C", str(source), "archive", V3], stdout=output, check=True)
    with tarfile.open(archive) as content:
        # Only trusted git content, with traversal rejected independently.
        for member in content.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination.resolve()) or member.issym() or member.islnk():
                raise ValueError("Unsafe archive member")
        content.extractall(destination, filter="data")
    archive.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=GATE_ROOT)
    parser.add_argument("--phase", choices=("baseline", "release"), required=True)
    parser.add_argument("--report", type=Path, help="Write selected synthetic observations as JSON")
    parser.add_argument("--before", type=Path, help="Required for release: exact-V3 baseline report from this gate")
    args = parser.parse_args(argv)
    source = args.source.resolve()
    input_hashes = {}
    try:
        identity = source_identity(source)
        if args.phase == "baseline":
            with tempfile.TemporaryDirectory() as tmp:
                archive_v3(source, Path(tmp))
                input_hashes = input_identity(Path(tmp))
                results = collect(Path(tmp))
            identity = {"commit": V3, "materialization": "git archive of exact immutable V3 commit"}
        else:
            input_hashes = input_identity(source)
            results = collect(source)
    except Exception as exc:
        identity = {"unavailable": True, "error_type": type(exc).__name__}
        results = [dict(id=ident, status="UNAVAILABLE", error_type=type(exc).__name__)
                   for ident in sorted(required_ids())]
    baseline_verified = False
    transitions = []
    baseline_error = None
    if args.phase == "release":
        try:
            if args.before is None:
                raise ValueError("Required baseline report missing")
            transitions, baseline_verified = compare_before(json.loads(args.before.read_text()), results)
        except Exception as exc:
            baseline_error = type(exc).__name__
    report = dict(schema="uptime-v4-independent-audit-gate-v1", phase=args.phase,
        generated_at=datetime.now(UTC).isoformat(), baseline_commit=V3, source=identity,
        interpreter=sys.version.split()[0], audit_provenance=AUDIT_PROVENANCE,
        synthetic_input_sha256=input_hashes,
        gate_code={str(path.relative_to(GATE_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in [Path(__file__), *sorted((GATE_ROOT / "tests").glob("test_v4_audit_*.py"))]},
        required_ids=sorted(required_ids()), primary_coverage=PRIMARY, results=results,
        before_after=transitions, baseline_verified=baseline_verified, baseline_error_type=baseline_error,
        release_pass=args.phase == "release" and baseline_verified and release_passes(results),
        counts=dict(Counter(r["status"] for r in results)))
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.report:
        args.report.write_text(payload)
    else:
        print(payload, end="")
    # Baseline defects are expected evidence. Unavailability remains nonzero,
    # and a baseline report can never authorize release.
    if args.phase == "baseline":
        return 2 if any(r["status"] == "UNAVAILABLE" for r in results) else 0
    return 0 if report["release_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
