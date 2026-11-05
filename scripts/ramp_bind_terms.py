"""Inspect, provision and revoke private offline pricing bindings for an installed sandbox workspace."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uptime.ramp_terms_store import EvidenceError, FinanceKey, RampTermsStore, TermsPacket, private_bytes
from uptime.source_config import _protected_path, load_private


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",type=Path)
    commands=parser.add_subparsers(dest="command",required=True)
    commands.add_parser("schema").add_argument("kind",choices=["packet","registration"])
    desc=commands.add_parser("describe")
    desc.add_argument("--bill")
    status=commands.add_parser("status")
    register=commands.add_parser("register")
    register.add_argument("--registration",type=Path,required=True)
    signing=commands.add_parser("signing-bytes")
    signing.add_argument("--out",type=Path,required=True)
    install=commands.add_parser("install")
    for cmd in (signing,install):
        cmd.add_argument("--packet",type=Path,required=True)
    install.add_argument("--signature",type=Path,required=True,help="Detached raw 64-byte Ed25519 signature")
    install.add_argument("--evidence-dir",type=Path,required=True)
    revoke=commands.add_parser("revoke")
    revoke.add_argument("kind",choices=["key","package"])
    revoke.add_argument("identity")
    for cmd in (desc,status,revoke):
        cmd.add_argument("--tenant",required=True)
        cmd.add_argument("--business",required=True)
    args=parser.parse_args()
    os.umask(0o077)
    try:
        if args.command=="schema":
            model = TermsPacket if args.kind=="packet" else FinanceKey
            print(json.dumps(model.model_json_schema(), indent=2))
            return
        if args.command=="signing-bytes":
            packet=load_private(args.packet,TermsPacket)
            target=_protected_path(args.out)
            with os.fdopen(os.open(target,os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_WRONLY,0o600),"wb") as handle:
                handle.write(packet.signing_bytes())
            print("Wrote canonical private signing bytes")
            return
        if not args.db or not args.db.is_file():
            raise EvidenceError("Choose an existing installed workspace with --db")
        store=RampTermsStore(args.db)
        if args.command=="describe":
            print(json.dumps(store.describe(args.tenant,args.business,args.bill),sort_keys=True))
        elif args.command=="register":
            store.register(load_private(args.registration,FinanceKey))
            print("Registered scoped finance verifier")
        elif args.command=="install":
            package=store.install(load_private(args.packet,TermsPacket),private_bytes(args.signature,64),args.evidence_dir)
            print(json.dumps({"package_id":package,"status":"installed"}))
        elif args.command=="revoke":
            store.revoke(args.kind,args.identity,args.tenant,args.business)
            print("Revoked scoped price authority")
        else:
            print(json.dumps(store.status(args.tenant,args.business),sort_keys=True))
    except (OSError,ValueError,sqlite3.Error) as exc:
        parser.exit(1,(str(exc) if isinstance(exc,EvidenceError) else "Private input, signature or installation rejected") + "\n")


if __name__=="__main__":
    main()
