"""Offline operator provisioning for the local synthetic source channel."""
import argparse
import os
from pathlib import Path
import sys

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.correspondence_types import Scope
from uptime.source_config import SourceConfig, init_config, load_private, update_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--tenant", default="bears")
    init.add_argument("--mode", choices=["replay","sandbox"], required=True)
    init.add_argument("--origin", required=True, help="Exact local listener, e.g. http://127.0.0.1:8765")
    add = commands.add_parser("add")
    add.add_argument("--scope", type=Path, required=True, help="Public synthetic claim scope JSON")
    add.add_argument("--source", choices=["status","customer","billing","vendor"], required=True)
    rotate = commands.add_parser("rotate")
    revoke = commands.add_parser("revoke")
    listing = commands.add_parser("list")
    for command in (init, add, rotate, revoke, listing):
        command.add_argument("--config", type=Path, required=True)
    for command in (add, rotate, revoke):
        command.add_argument("--subject", required=True)
    for command in (add, rotate):
        command.add_argument("--credential-file", type=Path, required=True, help="New private path outside repositories")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.command == "init":
            init_config(args.config, args.mode, args.origin, args.tenant)
            print("Created local synthetic source configuration.")
        elif args.command == "list":
            config = load_private(args.config, SourceConfig)
            for service in config.services:
                print(f"{service.subject}  {service.source}  {service.scope.account}  {service.scope.contract}  {service.scope.component}")
        else:
            scope = None
            if args.command == "add":
                with args.scope.open("rb") as stream:
                    data = stream.read(16385)
                if len(data) > 16384:
                    raise ValueError("Synthetic scope file exceeds 16 KiB")
                scope = Scope.model_validate_json(data)
            update_source(args.config, args.command, args.subject, source=getattr(args, "source", None),
                          scope=scope, sender_path=getattr(args, "credential_file", None))
            print("Updated local synthetic grant. New source bindings require a relaunch.")
    except ValidationError:
        parser.exit(1, "Invalid source identity, claim scope, or local configuration.\n")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Source provisioning failed: {exc}\n")


if __name__ == "__main__":
    main()
