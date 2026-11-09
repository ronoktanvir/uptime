#!/usr/bin/env python3
"""Offline lineage for one Ramp bill without a governing agreement (an evidence-gap case).

Inputs are local files only: a records snapshot from scripts/ramp_sync.py, the
installation association receipt from scripts/ramp_verify_browser.py (the verified
business and bill), and optionally a human-note read-back receipt from
scripts/verify_ramp_comment.py. No credentials, network, model or provider write.

Contract cases need a reviewed association, award and credit binding supplied by
trusted server code; this command deliberately does not accept them from files.
"""
import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import sys

_ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from uptime.ramp import RampError  # noqa: E402
from uptime.ramp_case_lineage import CaseIdentity, build_lineage, surface_plan  # noqa: E402
from uptime.ramp_findings import evaluate_snapshot  # noqa: E402
from uptime.ramp_records import _validate_snapshot  # noqa: E402

MAX_BYTES = 32 * 1024 * 1024


def _load(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError
    return json.loads(raw)


def build(records, association, note=None, *, tenant):
    _validate_snapshot(records)
    if association.get("status") != "ONE_BILL_READ_VERIFIED" or association.get("write_attempted") is not False:
        raise ValueError("ASSOCIATION_RECEIPT_NOT_VERIFIED")
    observed = datetime.fromisoformat(association["observed_at"])
    captured = datetime.fromisoformat(records["observed_at"])
    # The business proof must come from the same operator session as the capture.
    if abs(observed - captured) > timedelta(hours=1):
        raise ValueError("ASSOCIATION_RECEIPT_NOT_CONTEMPORANEOUS")
    bill_id, business_id = association["bill_id"], association["business_id"]
    row = next((r for r in records["resources"]["bills"]["records"] if r["id"] == bill_id and r["kind"] == "bill"), None)
    if row is None or row.get("vendor_id") is None or row.get("entity_id") is None or row.get("amount") is None:
        raise ValueError("BILL_NOT_FULLY_OBSERVED")
    as_of = datetime.fromisoformat(records["completed_at"])
    finding = next(c for c in evaluate_snapshot(records, as_of=as_of)
                   if c["provider_object_type"] == "bills" and c["provider_id"] == bill_id)
    identity = CaseIdentity(tenant=tenant, provider_business_id=business_id, vendor_id=row["vendor_id"],
                            entity_id=row["entity_id"], object_type="bills", object_id=bill_id,
                            currency=row["amount"]["currency"])
    lineage = build_lineage(identity, snapshot=records, provider_business_id=business_id, finding=finding,
                            surface=note)
    return {**lineage, "surface_plan": surface_plan(lineage)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--association-receipt", type=Path, required=True)
    parser.add_argument("--note-receipt", type=Path)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--output", type=Path, required=True, help="New owner-only file; never overwritten")
    args = parser.parse_args(argv)
    try:
        output = args.output
        if not output.is_absolute() or output.exists() or output.is_symlink():
            raise ValueError
        result = build(_load(args.records), _load(args.association_receipt),
                       _load(args.note_receipt) if args.note_receipt else None, tenant=args.tenant)
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        stages = {s["stage"]: s["status"] for s in result["stages"]}
        print(json.dumps({"status": result["status"], "stages": stages, "refusals": result["refusals"],
                          "plan": result["surface_plan"]["action"], "lineage_digest": result["lineage_digest"],
                          "writes_attempted": False}, indent=2))
        return 0
    except (RampError, ValueError, KeyError, TypeError, OSError, StopIteration) as exc:
        code = str(exc) if re.fullmatch(r"[A-Z][A-Z_]{2,80}", str(exc)) else "INVALID_LOCAL_INPUT"
        print(f"Lineage refused local input ({code}); no provider call or write was made.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
