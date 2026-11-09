"""Revoke this workspace's Ramp installation, or show its state. Makes no provider request."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.auth import bind_workspace
from uptime.installation_revocation import installed_business, record_workspace_event, revoke, status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "revoke"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--reason", help="Required for revoke; one short line")
    args = parser.parse_args(argv)
    if not args.db.is_file():
        parser.exit(1, "Workspace database unavailable\n")
    try:
        bind_workspace(args.db.absolute(), "sandbox", False, args.tenant)
        business = installed_business(args.db.absolute(), args.tenant)
        if business is None:
            parser.exit(1, "This workspace has no installed Ramp business\n")
        if args.command == "status":
            record = status(args.tenant, business)
            result = {"tenant": args.tenant, "business_id": business, "state": "REVOKED" if record else "ACTIVE",
                      "revoked_at": record["revoked_at"] if record else None}
        else:
            if not args.reason:
                parser.exit(2, "--reason is required to revoke\n")
            record = revoke(args.tenant, business, reason=args.reason)
            record_workspace_event(args.db.absolute(), args.tenant, business, record)
            result = {"tenant": args.tenant, "business_id": business, "state": "REVOKED",
                      "revoked_at": record["revoked_at"], "duplicate": record["duplicate"],
                      "next_step": "Disable the Ramp developer app or rotate its client secret in Ramp."}
    except (ValueError, PermissionError, OSError) as exc:
        parser.exit(1, f"Installation command stopped ({type(exc).__name__}: {exc})\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
