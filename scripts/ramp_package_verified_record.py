#!/usr/bin/env python3
"""Package the verified Ramp demo-bill excerpt from a person-run read-only capture.

Inputs are local files only: a records snapshot from scripts/ramp_sync.py and the
association receipt from scripts/ramp_verify_browser.py, taken in the same session. The
output keeps only the records the Ramp page's "Verified Ramp record" panel shows (see
uptime/ramp_context.package_verified_excerpt). No credentials, network or provider write.
The output must be a new file; review it and the repository scan before committing.
"""
import argparse
import json
import os
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from uptime.ramp import RampError  # noqa: E402
from uptime.ramp_context import package_verified_excerpt  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--association", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New file; never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("NEW_OUTPUT_REQUIRED")
        body = package_verified_excerpt(json.loads(args.records.read_text()), json.loads(args.association.read_text()))
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(body, handle, indent=1, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except (RampError, ValueError, KeyError, TypeError, OSError, StopIteration) as exc:
        code = str(exc) if str(exc).replace("_", "").isalpha() and str(exc).isupper() else type(exc).__name__
        print(f"Packaging refused ({code}); nothing was written.", file=sys.stderr)
        return 1
    context = body["records"]["bill"]
    print(json.dumps({"bill_id": context["id"], "vendor_name": context.get("vendor_name"),
                      "invoice_number": context.get("invoice_number"), "observed_at": body["source_capture"]["observed_at"],
                      "excerpt_checksum": body["excerpt_checksum"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
