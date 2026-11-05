#!/usr/bin/env python3
"""Named local API client. Provider credentials and native HTTP are server-owned."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from time import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from uptime.auth import DEFAULT_ORIGIN, valid_origin
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key, public_bytes, reviewer_signature
from uptime.ramp_native_binding import Empty, Execute, PREFIX, Prepare, Review, _protected_bytes
from uptime.ramp_webhooks import canonical, utcnow


def _bytes(body):
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def _validate_request(request):
    if set(request) != {"schema_version", "path", "body"} or request["schema_version"] != "uptime-native-local-request/1":
        raise ValueError("A staged native request is required")
    path = request["path"]
    if path in {PREFIX + "/preflight", PREFIX + "/prepare"}:
        model = Empty if path.endswith("preflight") else Prepare
    else:
        parts = path.removeprefix(PREFIX + "/actions/").split("/")
        if (not path.startswith(PREFIX + "/actions/") or len(parts) != 2 or len(parts[0]) != 64
                or any(c not in "0123456789abcdef" for c in parts[0])):
            raise ValueError("Only exact native operator routes are permitted")
        model = {"review": Review, "execute": Execute, "reconcile": Empty}.get(parts[1])
        if model is None:
            raise ValueError("Unsupported native operation")
    model.model_validate(request["body"])
    return request


def _stage(path, request):
    path = Path(path)
    if (not path.is_absolute() or path.resolve() != path or path.parent.stat().st_mode & 0o077
            or path.parent.stat().st_uid != os.getuid()):
        raise ValueError("Use a protected physical output directory")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(request, handle, indent=2)
        handle.write("\n")
    return {"staged": str(path), "path": request["path"], "body_sha256": sha256(_bytes(request["body"])).hexdigest(),
            "note": "Independent issuer must install a mandate for this exact local body before send; execute also needs the plan's exact native effect."}


def rehearsal():
    """Disposable simulation, deliberately never constructs NativeBinding or an HTTP client."""
    from uptime.ramp_workflow import RampWorkflow, SimulatedWorkflowProvider, WorkflowReviewer
    with TemporaryDirectory(prefix="uptime-native-rehearsal-") as temp:
        business, bill = str(uuid4()), str(uuid4())
        at = utcnow().isoformat()
        key = generate_reviewer_key()
        finding = {"provider_object_type": "bills", "provider_id": bill, "business_id": business,
                   "workspace_tenant": "rehearsal", "observed_at": at, "finding_digest": sha256(b"isolated rehearsal").hexdigest(),
                   "sources": ["SIMULATED_RAMP"], "finding_kind": "SYNTHETIC_REHEARSAL"}
        provider = SimulatedWorkflowProvider(business_id=business, records={("bills", bill): {"id": bill, "status": "OPEN"}})
        flow = RampWorkflow(Path(temp)/"outbox.db", tenant="rehearsal", business_id=business,
                            finding_resolver=lambda kind, ident: finding,
                            reviewers={"rehearsal": WorkflowReviewer(public_bytes(key))})
        plan = flow.prepare_comment("bills", bill, provider=provider)
        expiry = int(time())+120
        message = flow.review_message(plan["id"], reviewer="rehearsal", expires_at=expiry)
        flow.review(plan["id"], reviewer="rehearsal", expires_at=expiry, proof=reviewer_signature(key, message))
        result = flow.execute(plan["id"], provider=provider)
        return {"provenance": "SIMULATED_RAMP", "disposable": True, "provider_network_calls": 0,
                "object_id": bill, "status": result["status"], "remote_id": result["remote_id"],
                "receipt": result["remote_state"], "actual_money_prevented": None, "actual_recovery": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rehearsal", action="store_true", help="Run disposable simulation without credentials or network")
    parser.add_argument("--origin", default=DEFAULT_ORIGIN)
    parser.add_argument("--subject")
    parser.add_argument("--credential-file", type=Path, help="Named reviewer's protected private JWK; never a provider token")
    parser.add_argument("--stage-file", type=Path, help="Stage exact local payload for independent issuer review instead of sending")
    parser.add_argument("--object-id")
    parser.add_argument("--action-id")
    parser.add_argument("--review-digest")
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("command", nargs="?", choices=["status", "preflight", "prepare", "plan", "review", "execute", "reconcile", "send"])
    args = parser.parse_args(argv)
    if args.rehearsal:
        if any((args.command, args.subject, args.credential_file, args.stage_file, args.object_id,
                args.action_id, args.review_digest, args.request_file)) or args.origin != DEFAULT_ORIGIN:
            parser.error("--rehearsal runs alone in disposable simulation")
        print(json.dumps(rehearsal(), indent=2))
        return 0
    try:
        valid_origin(args.origin)
        if not args.command:
            raise ValueError("Choose a command or --rehearsal")
        command = args.command
        if command in {"plan", "review", "execute", "reconcile"} and not re.fullmatch(r"[a-f0-9]{64}", args.action_id or ""):
            raise ValueError("Exact native action digest required")
        if command == "preflight":
            path, body = PREFIX+"/preflight", {}
        elif command == "prepare":
            path, body = PREFIX+"/prepare", {"object_type": "bills", "object_id": args.object_id}
        elif command in {"execute", "reconcile", "review"}:
            path = f"{PREFIX}/actions/{args.action_id}/{command}"
            body = {"review_digest": args.review_digest} if command == "execute" else {}
        elif command == "send":
            request = _validate_request(json.loads(_protected_bytes(args.request_file)))
            path, body = request["path"], request["body"]
        else:
            path, body = None, None
        if args.stage_file and command in {"preflight", "prepare", "execute", "reconcile"}:
            request = _validate_request({"schema_version": "uptime-native-local-request/1", "path": path, "body": body})
            print(json.dumps(_stage(args.stage_file, request), indent=2))
            return 0
        if not args.subject or not args.credential_file:
            raise ValueError("Named subject and protected reviewer credential file required")
        key = json.loads(_protected_bytes(args.credential_file))
        if key.get("uptime_rehearsal"):
            raise ValueError("Rehearsal credentials cannot operate a named installation")
        with httpx.Client(base_url=args.origin, trust_env=False, follow_redirects=False, timeout=20) as client:
            operator = ReviewerClient(client, args.origin, args.subject, key)
            if command in {"status", "plan", "review"}:
                target = PREFIX+"/status" if command == "status" else f"{PREFIX}/actions/{args.action_id}"
                response = client.get(target, headers=operator.headers)
                response.raise_for_status()
                result = response.json()
                if command != "review":
                    print(json.dumps(result, indent=2))
                    return 0
                expiry = int(time())+300
                message = canonical(["uptime-ramp-review-v1", result["tenant"], result["business_id"], result["id"],
                                     result["review_digest"], args.subject, expiry])
                body = {"expires_at": expiry, "proof": reviewer_signature(key, message)}
            request = _validate_request({"schema_version": "uptime-native-local-request/1", "path": path, "body": body})
            if args.stage_file:
                result = _stage(args.stage_file, request)
            else:
                response = operator.post(path, body)
                response.raise_for_status()
                result = response.json()
            print(json.dumps(result, indent=2))
            return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, httpx.HTTPError):
        print("Native operator request failed. Check enrollment, gate, exact mandate, scope report and staged payload; no direct provider fallback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
