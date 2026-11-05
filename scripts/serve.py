"""Provision named users offline or start the loopback workbench."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from urllib.request import urlopen
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from uptime.auth import enroll
from uptime.auth_keys import generate_reviewer_key, write_credential
from uptime.server import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="bears", help="Trusted tenant for this local database")
    parser.add_argument("--mode", choices=["sandbox", "replay"], default="sandbox")
    parser.add_argument("--db", type=Path, default=Path("runtime/workbench-v4.sqlite"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--native-config", type=Path, help="Optional protected installation-specific native workflow config")
    parser.add_argument("--award-office", type=Path, help="Protected verification office for provider-confirmed awards and credit attribution")
    parser.add_argument("--source-config", type=Path, help="Protected offline LOCAL_SYNTHETIC source grants")
    parser.add_argument("--open", action="store_true", help="Open the local sign-in page")
    parser.add_argument("--enroll", metavar="ACCOUNT", help="Provision a named account offline and exit")
    keys = parser.add_mutually_exclusive_group()
    keys.add_argument("--credential-file", type=Path,
                      help="Create a random private reviewer JWK at this new absolute path outside the repository")
    keys.add_argument("--public-key", type=Path, help="Enroll an existing public P-256 JWK")
    parser.add_argument("--role", choices=["reviewer", "viewer"], default="reviewer")
    parser.add_argument("--enable-local-approvals", action="store_true",
                        help="Enable local actions only with a verified V4 release receipt")
    args = parser.parse_args()
    os.umask(0o077)
    if args.enroll:
        if not (args.credential_file or args.public_key):
            parser.exit(1, "Enrollment needs --credential-file or --public-key.\n")
        created = None
        try:
            if args.credential_file:
                credential = generate_reviewer_key()
                created = write_credential(args.credential_file, credential, Path(__file__).resolve().parents[1])
            else:
                if args.public_key.stat().st_size > 16384:
                    raise ValueError("Public key file is too large")
                credential = json.loads(args.public_key.read_text())
                if not isinstance(credential, dict) or "d" in credential:
                    raise ValueError("--public-key requires a public JWK without private key material")
            enroll(args.db, args.enroll, credential, args.role, args.mode, args.tenant)
        except (ValueError, OSError) as exc:
            if created is not None:
                created.unlink(missing_ok=True)
            parser.exit(1, "Offline enrollment failed: " + str(exc) + "\n")
        print("Named public key enrolled. Use the matching private credential file to sign in.")
        return
    if args.credential_file or args.public_key:
        parser.exit(1, "Key enrollment options require --enroll ACCOUNT.\n")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", args.port))
        except OSError:
            parser.exit(1, "Port unavailable. Select a different --port.\n")
        listener.listen()
        base = f"http://127.0.0.1:{listener.getsockname()[1]}"
        if args.enable_local_approvals:
            if args.mode != "replay" or args.native_config is not None:
                parser.exit(1, "Local release approval requires replay mode without a native configuration.\n")
            try:
                from uptime.gates import local_release_ready
            except ImportError:
                parser.exit(1, "Missing V4 release gate. Start in observation mode.\n")
            if not local_release_ready():
                parser.exit(1, "V4 release gate did not verify. Start in observation mode.\n")
        from uptime.source_config import SourceRegistry
        sources = SourceRegistry(args.source_config, args.mode, base, args.tenant) if args.source_config else None
        app = create_app(args.db, mode=args.mode, origin=base, tenant=args.tenant, approvals_enabled=args.enable_local_approvals,
                         service_credentials=sources, native_config=args.native_config, award_office=args.award_office)
        if args.enable_local_approvals:
            app.state.auth.local_gate = local_release_ready
        if sources:
            sources.config.bind(app.state.correspondence)
        if args.open:
            def launch():
                for _ in range(80):
                    try:
                        with urlopen(base+"/health", timeout=.5) as response:
                            if response.status == 200:
                                webbrowser.open(base)
                                return
                    except OSError:
                        time.sleep(.1)
            threading.Thread(target=launch, daemon=True).start()
        print(f"Local workbench: {base}/  Sign in with an offline-enrolled account.", flush=True)
        print("Enroll first with --enroll ACCOUNT --credential-file /private/path/key.json and the same --mode and --db.", flush=True)
        config = uvicorn.Config(app, access_log=False, proxy_headers=False, log_level="warning")
        uvicorn.Server(config).run(sockets=[listener])


if __name__ == "__main__":
    main()
