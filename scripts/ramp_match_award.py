"""Offline signed award observations. Does not read provider credentials or send requests."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.ramp_award_attribution import AwardAttributionStore, canonical_json, load_office_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--office-config", required=True, type=Path,
                        help="Reviewed, protected public witness configuration; never an API payload")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("register-claim", "import-award", "observe", "attribute"):
        commands.add_parser(name).add_argument("signed_file", type=Path)
    commands.add_parser("summary")
    commands.add_parser("filing-identity").add_argument("claim_id")
    args = parser.parse_args(argv)
    try:
        config = load_office_config(args.office_config)
        store = AwardAttributionStore(args.db, config)
        if args.command == "summary":
            result = store.summary(config.tenant, config.business_id)
        elif args.command == "filing-identity":
            result = dict(dispatch_sha256=store.filing_identity(args.claim_id))
        else:
            with args.signed_file.open("rb") as handle:
                raw = handle.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError("Oversize local input")
            methods = {"register-claim": store.register_claim, "import-award": store.import_award,
                       "observe": store.observe, "attribute": store.attribute}
            result = methods[args.command](json.loads(raw))
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
        parser.exit(2, "Offline award input rejected. No remote action was performed.\n")
    print(canonical_json(result))
    return 1 if result.get("status") == "QUARANTINED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
