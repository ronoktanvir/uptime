"""Describe/test release evidence or export bytes for an independently held offline signer."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uptime import gates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("source")
    sub.add_parser("status")
    payload = sub.add_parser("signing-bytes")
    payload.add_argument("--role", choices=sorted(gates.ACTORS), required=True)
    payload.add_argument("--tested-commit", required=True)
    inputs = payload.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--report", type=Path)
    inputs.add_argument("--binding", type=Path)
    payload.add_argument("--issued-at", type=int, required=True)
    payload.add_argument("--expires-at", type=int, required=True)
    payload.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "source":
        print(json.dumps(gates.source_identity(), sort_keys=True))
    elif args.command == "status":
        data = gates.release_status()
        print(json.dumps(data, sort_keys=True))
        return 0 if data["ready"] else 1
    else:
        try:
            policy = gates._policy(Path.home()/".config/uptime/release-trust.json")
            if (args.role in gates.REQUIRED_GATES) != bool(args.report):
                parser.error("QA witnesses sign report digests; human and native witnesses sign a binding object")
            binding = gates.digest(args.report.read_bytes()) if args.report else gates.strict_json(args.binding.read_bytes())
            raw = gates.signing_bytes(args.role, policy["roles"][args.role]["subject"],
                gates.source_identity(ROOT,args.tested_commit), binding, policy["campaign"], 1, args.issued_at, args.expires_at)
            with args.out.open("xb") as handle:
                handle.write(raw)
        except gates.ERRORS:
            parser.exit(1,"Trusted registration, tested build, binding or new output path unavailable.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
