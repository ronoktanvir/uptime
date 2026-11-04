"""Provision named users offline or start the loopback workbench."""
import argparse
from getpass import getpass
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
from uptime.server import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["sandbox", "replay"], default="sandbox")
    parser.add_argument("--db", type=Path, default=Path("runtime/workbench-v4.sqlite"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the local sign-in page")
    parser.add_argument("--enroll", metavar="ACCOUNT", help="Provision a named account offline and exit")
    parser.add_argument("--role", choices=["reviewer", "viewer"], default="reviewer")
    parser.add_argument("--enable-local-approvals", action="store_true",
                        help="Enable local actions only with a verified V4 release receipt")
    args = parser.parse_args()
    os.umask(0o077)
    if args.enroll:
        password = getpass("Local workspace password (14 or more characters): ")
        if password != getpass("Confirm password: "):
            parser.exit(1, "Passwords did not match.\n")
        try:
            enroll(args.db, args.enroll, password, args.role, args.mode)
        except ValueError as exc:
            parser.exit(1, str(exc) + "\n")
        print("Named account enrolled for the selected local workspace.")
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", args.port))
        except OSError:
            parser.exit(1, "Port unavailable. Select a different --port.\n")
        listener.listen()
        base = f"http://127.0.0.1:{listener.getsockname()[1]}"
        if args.enable_local_approvals:
            try:
                from uptime.gates import local_release_ready
            except ImportError:
                parser.exit(1, "Missing V4 release gate. Start in observation mode.\n")
            if not local_release_ready():
                parser.exit(1, "V4 release gate did not verify. Start in observation mode.\n")
        app = create_app(args.db, mode=args.mode, origin=base,
                         approvals_enabled=args.enable_local_approvals)
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
        print("Enroll an account before first use with --enroll ACCOUNT and the same --mode and --db.", flush=True)
        config = uvicorn.Config(app, access_log=False, proxy_headers=False, log_level="warning")
        uvicorn.Server(config).run(sockets=[listener])


if __name__ == "__main__":
    main()
