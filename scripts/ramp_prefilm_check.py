#!/usr/bin/env python3
"""Read-only pre-filming check for the Ramp segment of the demo.

Run by Ronok or the operator just before recording, never by rehearse.py or CI. It
uses the same protected sandbox profile as scripts/ramp_sync.py (RAMP_ENV=sandbox and
UPTIME_RAMP_CREDENTIAL_FILE). It makes only GET reads plus Ramp's read-only agreement
list query:

1. the business and the observed demo bill (scripts/ramp_verify_browser.py logic);
2. one bounded records sync (bills, vendors, transactions, agreements, credits,
   approvals, comments);
3. the offline case lineage for that bill with the committed human-note receipt.

PASS requires the same business and bill as the committed November 9 evidence, the
same vendor, entity and amount, no vendor credit applied to or created from the bill,
the person-posted note re-observed in this capture, and a clean evidence-gap lineage.
A changed payment or approval status, or extra comments, are warnings to look at.

The result is one owner-only JSON receipt in an existing private directory outside
the repository, plus one summary line without credentials. No write is attempted.
"""
import argparse
from datetime import UTC, datetime
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uptime.ramp import RampError, SandboxRampProvider  # noqa: E402
from uptime.ramp_installation import verify_browser_bill  # noqa: E402
from uptime.ramp_records import _validate_snapshot, sync_records  # noqa: E402

SCHEMA = "uptime-ramp-prefilm-check/1"
BASELINE = ROOT / "docs/v4/evidence/ramp-lineage-93/live-read-20261109.json"
NOTE_RECEIPT = ROOT / "docs/v4/evidence/demo-path-87/human-ramp-note.json"
DEMO_BILL_URL = "https://demo.ramp.com/bill-pay/bills/list/f74ba12c-95d0-582d-9f62-26d8057d1d37"
FIXED = ("vendor_id", "entity_id", "amount")
WATCHED = ("status", "status_summary", "approval_status")


def _lineage_builder():
    spec = importlib.util.spec_from_file_location("uptime_script_ramp_case_lineage", ROOT / "scripts/ramp_case_lineage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build


def check(provider, *, bill_url, baseline, note_receipt, tenant):
    """Return the receipt body. Failures and warnings are fixed codes only."""
    failures, warnings = [], []
    association = verify_browser_bill(provider, bill_url)
    expected = baseline["association"]
    if association["business_id"] != expected["business_id"]:
        failures.append("BUSINESS_CHANGED")
    if association["bill_id"] != expected["bill_id"]:
        failures.append("BILL_CHANGED")
    records = sync_records(provider, page_size=10, max_pages=1, detail_limit=10)
    _validate_snapshot(records)
    resources = records["resources"]
    for name in ("bills", "comments", "credits"):
        if not resources[name]["complete"]:
            failures.append(f"{name.upper()}_READ_INCOMPLETE")
    bill = next((r for r in resources["bills"]["records"]
                 if r.get("kind") == "bill" and r["id"] == association["bill_id"]), None)
    base_bill = baseline["demo_bill"]
    if bill is None:
        failures.append("BILL_NOT_IN_CAPTURE")
    else:
        for field in FIXED:
            if bill.get(field) != base_bill.get(field):
                failures.append(f"BILL_{field.upper()}_CHANGED")
        if bill.get("applied_credits") != []:
            failures.append("CREDIT_APPLIED_TO_BILL")
        for field in WATCHED:
            if field in base_bill and bill.get(field) != base_bill[field]:
                warnings.append(f"BILL_{field.upper()}_CHANGED")
    for credit in resources["credits"]["records"]:
        linked = {link["bill_id"] for link in credit.get("applied_bills") or []}
        if association["bill_id"] in linked or credit.get("reference_bill_id") == association["bill_id"]:
            failures.append("CREDIT_LINKED_TO_BILL")
            break
    thread = [c for c in resources["comments"]["records"]
              if c["object_type"] == "bills" and c["object_id"] == association["bill_id"]]
    expected_ids = {c["id"] for c in baseline["comments_observed"] if c["object_id"] == association["bill_id"]}
    if {c["id"] for c in thread} - expected_ids:
        warnings.append("NEW_COMMENTS_ON_BILL")
    lineage = None
    try:
        lineage = _lineage_builder()(records, association, note_receipt, tenant=tenant)
    except (RampError, ValueError, KeyError, TypeError, StopIteration) as exc:
        code = str(exc) if str(exc).isupper() else "LINEAGE_REFUSED"
        failures.append(code)
    if lineage is not None:
        surface = next(s for s in lineage["stages"] if s["stage"] == "SURFACE")
        if lineage["status"] != "FINDING_SURFACED":
            failures.append("LINEAGE_" + lineage["status"])
        failures.extend("LINEAGE_" + code for code in lineage["refusals"] + lineage["review_required"])
        if surface.get("status") != "VERIFIED_READBACK" or records["observed_at"] not in surface.get("reobserved_at", []):
            failures.append("NOTE_NOT_REOBSERVED")
        if any(value is not None for key, value in lineage["money"].items() if key.endswith("_minor")):
            failures.append("CASE_MONEY_NOT_NULL")
    failures = sorted(set(failures))
    return {"schema": SCHEMA, "result": "FAIL" if failures else "PASS", "failures": failures,
            "warnings": sorted(set(warnings)), "checked_at": datetime.now(UTC).isoformat(),
            "baseline_capture_checksum": baseline["capture"]["checksum"],
            "capture_checksum": records["checksum"], "capture_observed_at": records["observed_at"],
            "bill_id": association["bill_id"], "comment_ids": sorted(c["id"] for c in thread),
            "association": association, "lineage": lineage, "records": records,
            "writes_attempted": False, "actual_money_recovered": None}


def _private_directory(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ValueError("OUTPUT_DIRECTORY_REQUIRED")
    resolved = path.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise ValueError("OUTPUT_INSIDE_REPOSITORY")
    info = os.lstat(resolved)
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("OUTPUT_DIRECTORY_NOT_PRIVATE")
    return resolved


def _write(directory, body):
    name = "prefilm-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".json"
    target = directory / name
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(body, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return target


def summary(body, receipt):
    comments = ",".join(c[:8] for c in body["comment_ids"]) or "none"
    return (f"PREFILM {body['result']} bill={body['bill_id'][:8]} comments={comments} "
            f"capture={body['capture_checksum'][:12]} failures={','.join(body['failures']) or 'none'} "
            f"warnings={','.join(body['warnings']) or 'none'} writes=0 receipt={receipt}")


def main(argv=None, *, provider_factory=SandboxRampProvider):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Existing private (0700) directory outside the repository")
    parser.add_argument("--bill-url", default=DEMO_BILL_URL)
    parser.add_argument("--tenant", default="ramp-demo-native")
    args = parser.parse_args(argv)
    try:
        if os.environ.get("CI"):
            raise ValueError("NOT_FOR_CI")
        directory = _private_directory(args.output_dir)
        baseline = json.loads(BASELINE.read_text())
        note = json.loads(NOTE_RECEIPT.read_text())
        # Credentials are loaded only after every local check has passed.
        body = check(provider_factory(), bill_url=args.bill_url, baseline=baseline, note_receipt=note, tenant=args.tenant)
        receipt = _write(directory, body)
    except (RampError, OSError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if str(exc).isupper() else type(exc).__name__
        print(f"PREFILM ERROR {code}; no receipt written and no write attempted.", file=sys.stderr)
        return 2
    print(summary(body, receipt))
    return 0 if body["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
