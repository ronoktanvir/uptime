"""Back up, verify and restore one local workspace database. No credentials are copied."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.workspace_recovery import RecoveryError, backup, restore, verify


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("backup", help="Write a new owner-only backup directory")
    make.add_argument("--db", type=Path, required=True)
    make.add_argument("--output", type=Path, required=True, help="New directory outside any repository")
    check = sub.add_parser("verify", help="Recheck a backup without changing it")
    check.add_argument("--backup", type=Path, required=True)
    put = sub.add_parser("restore", help="Create a new fenced database from a verified backup")
    put.add_argument("--backup", type=Path, required=True)
    put.add_argument("--target", type=Path, required=True, help="New database path; never overwritten")
    put.add_argument("--tenant", required=True)
    put.add_argument("--mode", choices=("replay", "sandbox"), required=True)
    put.add_argument("--previous", type=Path, help="Readable previous database whose revocations carry forward")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.command == "backup":
            manifest = backup(args.db.absolute(), args.output.absolute())
            result = {k: manifest[k] for k in ("schema", "created_at", "binding", "case_history", "integrity")}
            result.update(database_sha256=manifest["database"]["sha256"], tables=len(manifest["tables"]),
                          not_included=manifest["not_included"])
        elif args.command == "verify":
            manifest = verify(args.backup.absolute())
            result = {"verified": True, "created_at": manifest["created_at"], "binding": manifest["binding"],
                      "database_sha256": manifest["database"]["sha256"]}
        else:
            result = restore(args.backup.absolute(), args.target.absolute(), tenant=args.tenant, mode=args.mode,
                             previous=args.previous.absolute() if args.previous else None)
    except (RecoveryError, OSError) as exc:
        # The message never includes database contents or file data.
        parser.exit(1, f"Workspace recovery stopped: {exc if isinstance(exc, RecoveryError) else type(exc).__name__}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
