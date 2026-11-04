"""Default: bounded sandbox reads. Token-only grants and draft writes are explicit."""
import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.ramp import (ROOT, FIXTURES, SandboxRampProvider, RampError, capture,
                         scope_probe, _bounds, _write_gate, uuid_text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--scope-only", action="store_true", help="exchange tokens; never read records or mutate")
    actions.add_argument("--verify-draft", action="store_true", help="authorized designated vendor draft only")
    parser.add_argument("--include-write-scope", action="store_true", help="only with --scope-only; no bill writes")
    parser.add_argument("--authorize-draft", action="store_true", help="operator confirms authorization for this draft")
    parser.add_argument("--designated-vendor-id", help="explicit approved sandbox vendor UUID; never auto-selected")
    parser.add_argument("--journal", type=Path, default=ROOT / "runtime/ramp-operations.sqlite")
    parser.add_argument("--output", type=Path, help="capture defaults to fixtures/ramp/verified.json; scope proof defaults to stdout")
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--detail-limit", type=int, default=20)
    options = parser.parse_args(argv)
    if options.include_write_scope and not options.scope_only:
        parser.error("--include-write-scope requires --scope-only")
    if (options.authorize_draft or options.designated_vendor_id) and not options.verify_draft:
        parser.error("draft authorization/vendor flags require --verify-draft")
    try:
        _bounds(options.page_size, options.max_pages, options.detail_limit)
        if options.verify_draft:
            _write_gate(options.authorize_draft)
            uuid_text(options.designated_vendor_id)
        # Validation precedes provider construction and therefore credential loading.
        provider = SandboxRampProvider()
        if options.scope_only:
            proof = scope_probe(provider, include_write=options.include_write_scope)
        else:
            proof = capture(provider, options.verify_draft, options.journal,
                            designated_vendor_id=options.designated_vendor_id,
                            authorize_draft=options.authorize_draft,
                            page_size=options.page_size, max_pages=options.max_pages,
                            detail_limit=options.detail_limit)
        target = options.output or (None if options.scope_only else FIXTURES / "verified.json")
        if options.scope_only and target is not None and target.resolve() == (FIXTURES / "verified.json").resolve():
            raise RampError("Scope metadata cannot replace the record capture")
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(".probe-" + str(uuid4()))
            try:
                with open(tmp, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as handle:
                    json.dump(proof, handle, indent=2, allow_nan=False)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                tmp.replace(target)
            finally:
                tmp.unlink(missing_ok=True)
        if options.scope_only:
            print(json.dumps(proof, indent=2))
            return int(any(r["state"] != "GRANTED" for r in proof["requests"]))
        for name, cap in proof["capabilities"].items():
            print(name, cap["state"], ",".join(cap.get("granted", [])))
        states = [c["state"] for c in proof["capabilities"].values()]
        return int(any(s not in {"READ_VERIFIED", "NOT_REQUESTED", "DRAFT_READBACK_VERIFIED"} for s in states))
    except (RampError, OSError, KeyError, ValueError, TypeError):
        # Never print arbitrary exceptions: transport/provider data may contain secrets.
        print("Sandbox probe failed; check sandbox environment, explicit gates, grants and local paths.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
