"""Offline registration of trusted issuer public keys and externally signed reviewer mandates."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime import mandates
from uptime.source_config import load_private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="Existing, offline-provisioned installation database")
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("describe").add_argument("--reviewer", required=True)
    sub.add_parser("register-issuer").add_argument("--registration", required=True, type=Path)
    sub.add_parser("install").add_argument("--signed", required=True, type=Path)
    revocation = sub.add_parser("revoke")
    revocation.add_argument("kind", choices=["issuer","mandate"])
    revocation.add_argument("identity")
    args = parser.parse_args()
    os.umask(0o077)
    if not args.db.is_file():
        parser.exit(1, "Choose an existing installation database.\n")
    try:
        if args.operation == "describe":
            print(json.dumps(mandates.describe(args.db, args.reviewer), sort_keys=True))
        elif args.operation == "register-issuer":
            mandates.register_issuer(args.db, load_private(args.registration, mandates.Issuer))
        elif args.operation == "install":
            mandates.install(args.db, load_private(args.signed, mandates.SignedMandate))
        else:
            mandates.revoke(args.db, args.kind, args.identity)
    except (ValueError, OSError, PermissionError) as exc:
        parser.exit(1, f"Offline authority operation refused: {exc}\n")


if __name__ == "__main__":
    main()
