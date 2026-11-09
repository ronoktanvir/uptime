"""Harness-hosted rehearsal of the decision-91a public status source over a real loopback socket.

Not a release-gated launch: the workspace is started with the same app factory the test
suite uses, approvals enabled, disposable keys and a scripted claim creator, in a fresh
directory. The release gate stays unsatisfied and is not touched. Evidence intake runs
through the ordinary enrollment tools, the signed delivery CLI and the HTTP intake route.

uv run --locked python scripts/rehearse_public_status.py --directory DIR --snapshot SNAPSHOT [--incident ID]
Without --incident, the most recently resolved incident with a published start and
component is selected. The receipt is written to DIR/receipt.json and printed.
"""
import argparse
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uptime.auth import enroll  # noqa: E402
from uptime.auth_client import ReviewerClient  # noqa: E402
from uptime.auth_keys import generate_reviewer_key  # noqa: E402
from uptime.correspondence_types import Scope, instant  # noqa: E402
from uptime.evidence import load_snapshot  # noqa: E402
from uptime.server import create_app  # noqa: E402
from uptime.source_config import SourceConfig, init_config, load_private, update_source  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def select_incident(snapshot):
    rows = [o for o in snapshot.observations if o.status == "resolved" and o.started_at and o.resolved_at and o.components]
    if not rows:
        raise SystemExit("No resolved public incident with a published start and component in this snapshot.")
    return max(rows, key=lambda o: instant(o.resolved_at))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--directory", type=Path, required=True, help="New empty directory for the rehearsal workspace")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--incident")
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    snapshot = load_snapshot(args.snapshot)
    row = next(o for o in snapshot.observations if o.incident_id == args.incident) if args.incident else select_incident(snapshot)
    start = instant(row.started_at)
    scope = Scope(account="local-status-rehearsal", vendor="Twilio", contract="local-rehearsal-agreement",
                  service="Twilio Messaging API", component=row.components[0], invoice="local-rehearsal-invoice",
                  incident=row.incident_id, currency="USD", month=start.strftime("%Y-%m"), region="global")
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    config, sender_file, db = directory / "grants.json", directory / "status-sender.json", directory / "workspace.sqlite"
    init_config(config, "replay", origin, "bears")
    update_source(config, "add", "status.twilio-public", source="status", scope=scope, sender_path=sender_file)
    operator = generate_reviewer_key()
    enroll(db, "rehearsal.operator", operator, tenant="bears")
    grants = load_private(config, SourceConfig)
    app = create_app(db, origin=origin, approvals_enabled=True, tenant="bears",
                     service_credentials=grants.credentials("replay", origin, "bears"))
    grants.bind(app.state.correspondence)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        claim = "inbox-public-status-rehearsal"
        with httpx.Client(base_url=origin, trust_env=False, timeout=10) as client:
            reviewer = ReviewerClient(client, origin, "rehearsal.operator", operator)
            created = reviewer.post("/api/correspondence/claims", {"claim_id": claim, "scope": scope.model_dump()})
            created.raise_for_status()
            command = [sys.executable, str(ROOT / "scripts/deliver_public_status.py"), "--snapshot", str(args.snapshot),
                       "--credential-file", str(sender_file), "--claim", claim, "--incident", row.incident_id]
            first = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=60)
            retry = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=60)
            case = client.get(f"/api/correspondence/claims/{claim}", headers=reviewer.headers).json()
            gate = client.get("/api/auth/context").json()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    receipt = dict(
        rehearsal="decision 91a public status source; harness-hosted loopback workspace, not a release-gated launch",
        recorded_at=datetime.now(UTC).isoformat(), origin=origin, listener_context=gate,
        snapshot=dict(path_name=args.snapshot.name, sha256=sha256(args.snapshot.read_bytes()).hexdigest(),
                      source_uri=snapshot.source_uri, observed_at=snapshot.observed_at, raw_sha256=snapshot.raw_sha256,
                      incidents=len(snapshot.observations)),
        grant=dict(subject="status.twilio-public", source="status", scope=scope.model_dump()),
        delivery_cli=dict(exit=first.returncode, stdout=json.loads(first.stdout) if first.returncode == 0 else None,
                          stderr=first.stderr.strip()),
        retry_cli=dict(exit=retry.returncode, stdout=json.loads(retry.stdout) if retry.returncode == 0 else None,
                       stderr=retry.stderr.strip()),
        claim=dict(stage=case["stage"], outcome=case["outcome"], amount=case["amount"], evidence=case["evidence"],
                   preflight=case["preflight"]),
        authority="disposable operator key created for this rehearsal; scripted claim creation, no human approval",
        not_established=["customer impact", "eligible fees", "complete month coverage", "that the signing key belongs to Twilio",
                         "release-gated ordinary launch"])
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if first.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
