"""Sign an exact synthetic source event and deliver it to its pinned local workbench."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

import httpx
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.auth_client import service_headers
from uptime.correspondence_types import Delivery
from uptime.evidence_applicability import temporal_refusal
from uptime.source_config import CLAIM, SenderCredential, event_in_scope, load_private


def deliver(client, credential, claim_id, raw):
    if len(raw) > 262144 or not CLAIM.fullmatch(claim_id):
        raise ValueError("Invalid claim identifier or oversized event")
    try:
        event = Delivery.model_validate_json(raw)
    except ValidationError:
        raise ValueError("Invalid synthetic event schema") from None
    if event.scope == credential.scope and (reason := temporal_refusal(event.body, credential.scope.month)):
        # Name the operator's own record before signing; the server returns only HTTP 403.
        raise ValueError(reason)
    if not event_in_scope(event, credential.source, credential.scope):
        raise ValueError("Synthetic event does not match this sender's source and grant")
    context_response = client.get(credential.origin+"/api/auth/context", follow_redirects=False)
    if context_response.status_code != 200:
        raise ValueError("The pinned local listener did not return its authority context")
    context = context_response.json()
    if (not isinstance(context, dict) or context.get("origin") != credential.origin or
            context.get("mode") != credential.mode or context.get("tenant") != credential.tenant or
            not re.fullmatch(r"[0-9a-f]{48}", str(context.get("instance","")))):
        raise ValueError("Listener context differs from this credential's pinned workspace")
    path = f"/api/correspondence/claims/{claim_id}/events"
    headers = service_headers(instance=context["instance"], origin=credential.origin, subject=credential.subject,
                              key=credential, path=path, body=raw)
    response = client.post(credential.origin+path, content=raw, headers=headers, follow_redirects=False)
    if response.status_code != 200:
        raise ValueError(f"Local source delivery rejected (HTTP {response.status_code})")
    receipt = response.json()
    if (not isinstance(receipt, dict) or set(receipt) != {"event_id","digest","received_at"} or
            receipt["event_id"] != event.event_id or not re.fullmatch(r"[0-9a-f]{64}", str(receipt["digest"]))):
        raise ValueError("Unexpected local delivery receipt")
    try:
        at = datetime.fromisoformat(receipt["received_at"])
        if at.utcoffset() is None:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Invalid local receipt clock") from None
    return {"event_id":event.event_id, "digest":receipt["digest"], "received_at":at.isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--event", type=Path, required=True, help="Synthetic correspondence delivery JSON")
    args = parser.parse_args()
    try:
        credential = load_private(args.credential_file, SenderCredential)
        with args.event.open("rb") as handle:
            raw = handle.read(262145)
        with httpx.Client(trust_env=False, timeout=5, follow_redirects=False) as client:
            receipt = deliver(client, credential, args.claim, raw)
        print(json.dumps(receipt))
    except (ValueError, OSError, httpx.HTTPError) as exc:
        # Never dump request/response bodies, headers, private fields or subprocess environments.
        if type(exc) is ValueError:
            parser.exit(1, f"Source delivery failed: {exc}\n")
        parser.exit(1, "Source delivery failed. Check the event file and pinned local listener.\n")


if __name__ == "__main__":
    main()
