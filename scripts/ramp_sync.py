"""Operator-only bounded sandbox reads. No provider writes or implicit live reads by the UI."""
import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.ramp import RampError, SandboxRampProvider, _bounds
from uptime.ramp_records import sync_records, scope_probe, _validate_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-only", action="store_true", help="only exchange exact read-scope tokens")
    parser.add_argument("--all-purchase-orders", action="store_true", help="also list bounded independent native POs")
    parser.add_argument("--output", type=Path, help="required for records; scope diagnostics otherwise go to stdout")
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--detail-limit", type=int, default=10)
    args = parser.parse_args(argv)
    if not args.scope_only and args.output is None:
        parser.error("--output is required for a records snapshot")
    if args.scope_only and args.all_purchase_orders:
        parser.error("--all-purchase-orders cannot be combined with --scope-only")
    try:
        _bounds(args.page_size, args.max_pages, args.detail_limit)
        # Credential construction only occurs in the operator command, after argument validation.
        provider = SandboxRampProvider()
        proof = scope_probe(provider) if args.scope_only else sync_records(provider,
            page_size=args.page_size, max_pages=args.max_pages, detail_limit=args.detail_limit,
            include_unlinked_purchase_orders=args.all_purchase_orders)
        if not args.scope_only:
            _validate_snapshot(proof)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.output.with_name(".ramp-records-" + str(uuid4()))
            try:
                with open(temporary, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as handle:
                    json.dump(proof, handle, indent=2, allow_nan=False)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.replace(args.output)
            finally:
                temporary.unlink(missing_ok=True)
        if args.scope_only:
            print(json.dumps(proof, indent=2))
            return int(any(r["state"] != "GRANTED" for r in proof["requests"]))
        print(json.dumps({"checksum": proof["checksum"], "resources": {
            name: {"status": r["status"], "complete": r["complete"], "count": len(r["records"])}
            for name, r in proof["resources"].items()}}, indent=2))
        # A truncated bounded sample is usable as an observation; failures produce a nonzero exit.
        return int(any(r["status"] in {"UNAVAILABLE", "FORBIDDEN", "PARTIAL"} for r in proof["resources"].values()))
    except (RampError, OSError, KeyError, ValueError, TypeError):
        print("Ramp synchronization failed; inspect sandbox configuration, bounds, grants and local output path.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
