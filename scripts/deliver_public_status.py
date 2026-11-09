"""Deliver one resolved Twilio public incident as an enrolled status source's signed record.

1. Refresh a minimized public snapshot: python -m uptime.evidence_refresh --live --output SNAPSHOT
2. Enroll a status source whose scope names the incident and one of its published
   components: python scripts/provision_sources.py add --source status ...
3. Run this command. It verifies the snapshot integrity and freshness, maps the incident
   to the grant, signs the exact record and delivers it to the pinned local workbench.

The printed receipt joins the workbench receipt with the public provenance. A public
incident is never this customer's impact, fees or complete month coverage.
"""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.deliver_evidence import deliver  # noqa: E402
from uptime.evidence import load_snapshot  # noqa: E402
from uptime.evidence_status_source import StatusSourceRefusal, status_delivery  # noqa: E402
from uptime.source_config import SenderCredential, load_private  # noqa: E402


def deliver_public_status(client, credential, claim_id, snapshot_path, incident_id, *, now=None):
    if credential.source != "status":
        raise ValueError("Only an enrolled status source can deliver a public status record.")
    snapshot = load_snapshot(snapshot_path)
    delivery, provenance = status_delivery(snapshot, incident_id, credential.scope, now=now or datetime.now(UTC))
    receipt = deliver(client, credential, claim_id, delivery.model_dump_json().encode())
    return {"delivery": receipt, "provenance": provenance, "subject": credential.subject}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", type=Path, required=True, help="Minimized snapshot from uptime.evidence_refresh")
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--incident", required=True)
    args = parser.parse_args()
    try:
        credential = load_private(args.credential_file, SenderCredential)
        with httpx.Client(trust_env=False, timeout=5, follow_redirects=False) as client:
            result = deliver_public_status(client, credential, args.claim, args.snapshot, args.incident)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, TypeError, httpx.HTTPError) as exc:
        # Only this repository's own refusal messages are printed; schema errors can echo input.
        if type(exc) in (StatusSourceRefusal, ValueError):
            parser.exit(1, f"Public status delivery refused: {exc}\n")
        parser.exit(1, "Public status delivery failed. Check the snapshot, credential and pinned local listener.\n")


if __name__ == "__main__":
    main()
