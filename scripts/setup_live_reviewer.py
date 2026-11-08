#!/usr/bin/env python3
"""Prepare a separate CalyxQuay shadow candidate for a person's local review.

Preparation is recorded as scripted fixture work. This command never signs in as
the named person or approves, activates, interprets or rolls back the adapter.
The ordinary release gate still controls consequential browser actions.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import sys
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uptime.auth import NAME, SCRIPT, enroll, valid_origin
from uptime.auth_keys import generate_reviewer_key, public_bytes, write_credential
from uptime.contracts import Principal, fingerprint
from uptime.gates import local_release_ready
from uptime.server import create_app
from uptime.source_config import _check_file, _protected_path
from uptime import vendor_registry as registry

SCHEMA = "uptime-live-review-workspace/1"
VENDOR = "calyxquay"
TENANT = "bears"


def inputs():
    """Use the accepted public artifact and separately authored customer overlay."""
    from scripts.film_ramp_v4 import public_intake, demo_controls
    with patch.dict(os.environ, {
        "UPTIME_PUBLIC_EXTRACTIONS": str(ROOT / "docs/v4/evidence/public-extractions"),
        "UPTIME_MODEL_PROPOSITIONS": "1",
    }):
        body, manifest, _ = public_intake()
    body = deepcopy(body)
    body["document"]["name"] = "CalyxQuay Beacon Cache Service Agreement"
    body["overlay"].update(account="harborline-calyx", agreement="CQ-2031-04",
                           fee_line_ref="beacon-cache-monthly")
    _, controls = demo_controls(body["overlay"], manifest)
    for row in controls:
        row["name"] = row["name"].replace("Editor demo: ", "Source control: ")
    return body, controls


def _subject(subject):
    if (not isinstance(subject, str) or not NAME.fullmatch(subject)
            or subject.startswith(("scripted-", "service-", "local-"))):
        raise ValueError("Use the teammate's named local account, such as ronok-tanvir")
    return subject


def _origin(origin):
    valid_origin(origin)
    if origin != f"http://127.0.0.1:{urlsplit(origin).port}":
        raise ValueError("Use the exact numeric IPv4 loopback origin")
    return origin


def _directory(directory):
    path = Path(directory)
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("Use an absolute physical workspace path without symlinks")
    if path.is_relative_to(ROOT) or any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise ValueError("Keep the reviewer workspace and credential outside repositories")
    return path


def _save_metadata(directory, metadata):
    path = _protected_path(directory / "workspace.json")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(metadata, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _public_key(path):
    path = _protected_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError("Use an operator-owned public JWK file that others cannot modify")
        raw = handle.read(16385)
    if len(raw) > 16384:
        raise ValueError("Public JWK file is too large")
    value = json.loads(raw)
    if not isinstance(value, dict) or "d" in value or value.get("uptime_rehearsal"):
        raise ValueError("Supply only the person's public P-256 JWK, without private key material")
    public_bytes(value)
    return value


def _load_metadata(directory):
    path = _protected_path(directory / "workspace.json")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        _check_file(handle.fileno())
        raw = handle.read(8193)
    if len(raw) > 8192:
        raise ValueError("Invalid reviewer workspace metadata")
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {"schema", "subject", "origin", "input_sha256", "credential_file"}
            or value["schema"] != SCHEMA):
        raise ValueError("Invalid reviewer workspace metadata")
    _subject(value["subject"])
    _origin(value["origin"])
    if value["credential_file"] is not None:
        _protected_path(value["credential_file"])
    if value["input_sha256"] != fingerprint(inputs()):
        raise ValueError("Source inputs changed; preserve this workspace and prepare a fresh review")
    return value


def open_workspace(directory):
    directory = _directory(directory)
    metadata = _load_metadata(directory)
    app = create_app(directory / "workspace.db", mode="replay", rehearsal=False,
                     origin=metadata["origin"], tenant=TENANT,
                     approvals_enabled=local_release_ready())
    # Recheck at every consequential request, including expiration after startup.
    app.state.auth.local_gate = local_release_ready
    return app, metadata


def prepare(directory, origin, subject, *, public_key=None, credential_file=None):
    """Offline setup only. No HTTP request or person's signed action is performed."""
    directory, origin, subject = _directory(directory), _origin(origin), _subject(subject)
    if (public_key is None) == (credential_file is None):
        raise ValueError("Select a reviewer-owned public key or an explicit new private credential file")
    if directory.exists():
        raise ValueError("Select a fresh directory; --resume preserves an existing review")
    body, controls = inputs()
    credential = _public_key(public_key) if public_key is not None else generate_reviewer_key()
    directory.mkdir(mode=0o700, parents=True)
    if credential_file is not None:
        write_credential(_protected_path(credential_file), credential, ROOT)
    enroll(directory / "workspace.db", subject, credential, mode="replay", tenant=TENANT)
    principal = Principal(TENANT, SCRIPT, "reviewer")
    with patch.dict(os.environ, {
        "UPTIME_PUBLIC_EXTRACTIONS": str(ROOT / "docs/v4/evidence/public-extractions"),
        "UPTIME_MODEL_PROPOSITIONS": "1",
    }):
        state = registry.install(directory / "workspace.db", principal, VENDOR, body)
    if state.get("semantic_review_requirements"):
        from scripts.setup_northwind import scripted_literal_review
        state = registry.review_semantics(directory / "workspace.db", principal, VENDOR,
            registry.SemanticSubmission(revision=state["revision"],
                review=scripted_literal_review(state["semantic_review_requirements"])))
    state = registry.submit_tests(directory / "workspace.db", principal, VENDOR,
        registry.TestSubmission(revision=state["revision"], tests=controls))
    if (state["state"] != "SHADOW" or state["active_version"] is not None
            or state["reviewer"] is not None or state.get("interpretation_reviewer") is not None
            or not state["checks"] or not all(row["passed"] for row in state["checks"])):
        raise ValueError("Prepared source controls did not produce an unapproved shadow candidate")
    metadata = dict(schema=SCHEMA, subject=subject, origin=origin, input_sha256=fingerprint((body, controls)),
                    credential_file=str(credential_file) if credential_file is not None else None)
    _save_metadata(directory, metadata)
    app, metadata = open_workspace(directory)
    return app, metadata, state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--subject", help="Named teammate account; required only for a fresh workspace")
    parser.add_argument("--origin", help="Exact listener for a fresh workspace; default http://127.0.0.1:8777")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--serve", action="store_true")
    keys = parser.add_mutually_exclusive_group()
    keys.add_argument("--public-key", type=Path, help="Preferred: enroll the teammate's existing public P-256 JWK only")
    keys.add_argument("--credential-file", type=Path, help="Alternatively create a private key at this new protected path")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.resume:
            if args.subject or args.origin or args.public_key or args.credential_file:
                raise ValueError("Resume uses the saved reviewer, origin and enrollment without overrides")
            app, metadata = open_workspace(args.directory)
        else:
            if not args.subject:
                raise ValueError("A named teammate account is required")
            app, metadata, _ = prepare(args.directory, args.origin or "http://127.0.0.1:8777", args.subject,
                                      public_key=args.public_key, credential_file=args.credential_file)
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(1, "Reviewer workspace could not be prepared or verified. Preserve any existing directory.\n")
    print(json.dumps({
        "directory": str(args.directory), "origin": metadata["origin"], "account": metadata["subject"],
        "reviewer_credential_file": metadata["credential_file"],
        "local_approvals": "RELEASE_VERIFIED" if app.state.auth.approvals_enabled else "RELEASE_PENDING",
        "human_actions_performed": False, "provider_actions_performed": False,
    }), flush=True)
    if args.serve:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=urlsplit(metadata["origin"]).port,
                    access_log=False, proxy_headers=False, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
