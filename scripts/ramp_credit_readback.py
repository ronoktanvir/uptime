#!/usr/bin/env python3
"""Offline D09 read-back: every Ramp vendor credit linked to one verified bill.

Reads local files only: either a pre-filming receipt from scripts/ramp_prefilm_check.py,
or a records snapshot (scripts/ramp_sync.py) plus the installation association receipt
(scripts/ramp_verify_browser.py) taken within the same hour. No credentials, network,
model or provider write.

The report checks each credit/bill link on both sides and never attributes a credit to
an award or claim; that needs a reviewed credit binding under separate authority.
"""
import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from uptime.ramp import RampError  # noqa: E402
from uptime.ramp_association import AssociationError  # noqa: E402
from uptime.ramp_case_lineage import credit_links  # noqa: E402
from uptime.ramp_records import _validate_snapshot  # noqa: E402

MAX_BYTES = 32 * 1024 * 1024


def _load(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("INPUT_TOO_LARGE")
    return json.loads(raw)


def report(records, association):
    _validate_snapshot(records)
    if association.get("status") != "ONE_BILL_READ_VERIFIED" or association.get("write_attempted") is not False:
        raise ValueError("ASSOCIATION_RECEIPT_NOT_VERIFIED")
    if abs(datetime.fromisoformat(association["observed_at"]) - datetime.fromisoformat(records["observed_at"])) > timedelta(hours=1):
        raise ValueError("ASSOCIATION_RECEIPT_NOT_CONTEMPORANEOUS")
    return credit_links(records, provider_business_id=association["business_id"], bill_id=association["bill_id"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prefilm-receipt", type=Path)
    source.add_argument("--records", type=Path)
    parser.add_argument("--association-receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="New absolute owner-only file; never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.records is not None and args.association_receipt is None:
            raise ValueError("ASSOCIATION_RECEIPT_REQUIRED")
        if not args.output.is_absolute() or args.output.exists() or args.output.is_symlink():
            raise ValueError("NEW_ABSOLUTE_OUTPUT_REQUIRED")
        if args.prefilm_receipt is not None:
            receipt = _load(args.prefilm_receipt)
            if receipt.get("schema") != "uptime-ramp-prefilm-check/1":
                raise ValueError("NOT_A_PREFILM_RECEIPT")
            result = report(receipt["records"], receipt["association"])
        else:
            result = report(_load(args.records), _load(args.association_receipt))
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except (RampError, AssociationError, ValueError, KeyError, TypeError, OSError) as exc:
        code = str(exc) if str(exc).replace("_", "").isalpha() and str(exc).isupper() else type(exc).__name__
        print(f"Credit read-back refused ({code}); no provider call or write was made.", file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "bill_id": result["bill_id"], "links": len(result["links"]),
                      "applied_verified_minor": result["applied_verified_minor"],
                      "credits_list": result["credits_list"], "attribution": result["attribution"],
                      "writes_attempted": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
