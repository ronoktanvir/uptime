"""Capture only sanitized sandbox evidence, explicitly opt in to a tagged draft write."""
import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.ramp import ROOT, FIXTURES, SandboxRampProvider, RampError, capture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-draft", action="store_true", help="requires exact read + write grant")
    options = parser.parse_args()
    try:
        proof = capture(SandboxRampProvider(), options.verify_draft, ROOT / "runtime/ramp-operations.sqlite")
    except (RampError, OSError, KeyError, ValueError) as exc:
        print(str(exc) if isinstance(exc, RampError) else "Sandbox probe failed", file=sys.stderr)
        return 1
    tmp = FIXTURES / (".probe-" + str(uuid4()))
    tmp.write_text(json.dumps(proof, indent=2) + "\n")
    tmp.replace(FIXTURES / "verified.json")
    for name, cap in proof["capabilities"].items():
        print(name, cap["state"], ",".join(cap["granted"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
