#!/usr/bin/env python3
"""Stage one unsigned review proposal; approval and signing are separate person-run steps."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uptime import local_review_exception as permission


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="Write an UNSIGNED proposal only")
    prepare.add_argument("--directory", type=Path, required=True)
    prepare.add_argument("--evidence", type=Path, required=True, help="Full-suite receipt for the exact tested source")
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--hours", type=int, choices=range(1,49), default=48)
    inspect = sub.add_parser("inspect", help="Print the exact public proposal and review digest")
    inspect.add_argument("--proposal", type=Path, required=True)
    owner = sub.add_parser("owner-approve", help="Person-run explicit filesystem-owner approval; not independent QA")
    reviewer = sub.add_parser("authorize", help="Person-run signature with the enrolled reviewer's private key")
    for command in (owner, reviewer):
        command.add_argument("--directory", type=Path, required=True)
        command.add_argument("--proposal", type=Path, required=True)
        command.add_argument("--reviewed-sha256", required=True)
    reviewer.add_argument("--credential-file", type=Path, required=True)
    reviewer.add_argument("--output", type=Path, required=True)
    revoke = sub.add_parser("revoke", help="Durably stop this permission outside the workspace")
    revoke.add_argument("--grant-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            proposal = permission.build_proposal(args.directory, args.evidence, args.hours * 3600)
            permission.write_json(args.output, proposal)
            result = {"status": "UNSIGNED_REVIEW_REQUIRED", "proposal_file": str(args.output),
                      "proposal_sha256": permission.proposal_digest(proposal), "proposal": proposal,
                      "owner_approval_created": False, "reviewer_signature_created": False,
                      "permission_installed": False, "human_actions_performed": False}
        elif args.command == "inspect":
            proposal, _ = permission._read(args.proposal)
            permission.Proposal.model_validate(proposal)
            result = {"proposal_sha256": permission.proposal_digest(proposal), "proposal": proposal}
        elif args.command == "owner-approve":
            path = permission.owner_approve(args.directory, args.proposal, args.reviewed_sha256)
            result = {"status": "OPERATOR_OWNED_APPROVAL_RECORDED", "approval_file": str(path),
                      "independent_release": False, "permission_installed": False}
        elif args.command == "authorize":
            path = permission.authorize(args.directory, args.proposal, args.credential_file, args.output, args.reviewed_sha256)
            result = {"status": "REVIEWER_SIGNATURE_CREATED", "envelope_file": str(path),
                      "independent_release": False, "permission_installed": False}
        else:
            permission.revoke(args.grant_id)
            result = {"status": "REVOKED", "grant_id": args.grant_id}
    except permission.ERRORS:
        parser.exit(1, permission.DENIED + ". No replacement permission was installed.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
