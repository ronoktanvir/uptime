"""Private, offline blind acceptance over real signed loopback HTTP.

No fixture values, model output, response bodies or exception text may be logged.
The only export is an allowlisted receipt. Product imports occur after --source.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import importlib.util
import logging
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time


def _load_witness_module(name, filename):
    """Pin witness helpers beside this runner, independent of --source checkout."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)


_load_witness_module("_blind_acceptance_mapping", "blind_mapping.py")
_load_witness_module("_blind_acceptance_expectations", "blind_expectations.py")

FREEZE = "9364cd2bf2023adbc1a6f99bc275ac1ae36476ee"
BOUNDARY_FREEZE = "c33642b"
FROZEN_MANIFEST = "f0c9cb6e904c36b490387eefd45bc1a9141b4e1faa3bda313f13a7cadd4d1359"


class BoundaryError(Exception):
    """A constant failure code, never private exception text."""


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    return sha256(value).hexdigest()


def instant(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise BoundaryError("TIMEZONE_MISSING")
    return result.astimezone(UTC)


def local_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise BoundaryError("FIXTURE_PATH_INVALID")
    return path


def read_json(path):
    return json.loads(path.read_bytes(), parse_float=Decimal)


def money(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise BoundaryError("MONEY_ENCODING_INVALID")
    return Decimal(value)


def money_check(expected, observed, *, available):
    """Unknown is not zero; unavailable is not a wrong numeric result."""
    if not available:
        return "UNAVAILABLE"
    if expected is None or observed is None:
        return "PASS" if expected is observed else "UNKNOWN_MISMATCH"
    return "PASS" if money(expected) == money(observed) else "WRONG_MONEY"


def select_records(records, selectors, as_of):
    index = {row["id"]: row for row in records}
    if len(index) != len(records) or len(set(selectors)) != len(selectors):
        raise BoundaryError("DUPLICATE_INPUT_ID")
    if set(selectors) - index.keys():
        raise BoundaryError("MISSING_INPUT_ID")
    ready, unavailable = [], []
    for identifier in selectors:
        row = index[identifier]
        (ready if instant(row["available_at"]) <= instant(as_of) else unavailable).append(row)
    return ready, unavailable


def write_receipt(path, receipt):
    """Create-only, private permissions; never overwrite previous observations."""
    raw = json.dumps(private_receipt(receipt), sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    with open(path, "xb", opener=lambda name, flags: os.open(name, flags, 0o600)) as handle:
        handle.write(raw)


def private_receipt(value):
    """Financial operands and private clocks stay in memory; export digests only."""
    sensitive = {"amount", "awarded", "expected_money", "observed_money", "filing_cutoff", "measurement_month",
                 "expected_value", "observed_value", "supported_credit", "remaining_credit", "eligible_base", "metrics", "contract_cutoff",
                 "covered_seconds", "excluded_seconds", "unresolved_seconds"}
    if isinstance(value, dict):
        return {key + "_sha256" if key in sensitive else key:
                digest(child) if key in sensitive else private_receipt(child) for key, child in value.items()}
    if isinstance(value, list):
        return [private_receipt(child) for child in value]
    return value


def missing_categories(row):
    text = " ".join(row.get("preflight", {}).get("missing", [])) if row else ""
    patterns = {"provider_status": r"resource_status|status record", "customer_attribution": r"resource_attribution|customer cause",
                "scoped_billing": r"resource_invoice|charges|invoice", "complete_month": r"completed service month|complete month",
                "filing_material": r"filing material|request fields", "resource_mapping": r"resource|scope"}
    return [category for category, pattern in patterns.items() if re.search(pattern, text, re.I)]


INPUT_KEYS = {"id", "account_id", "resource_id", "requested_account_id", "requested_resource_id", "month", "measured_month", "as_of",
              "input_artifact_ids", "input_correspondence_ids"}
OUTCOMES = {"ELIGIBLE", "INELIGIBLE", "INSUFFICIENT_EVIDENCE", "UNSUPPORTED_RULE"}
STAGES = {"EVALUATED", "AWAITING_VENDOR", "HISTORICAL_FILING", "DRAFTED", "NEEDS_EVIDENCE", "RESPONSE_DRAFTED", "RESPONSE_APPROVED", "HUMAN_REVIEW",
          "DENIAL_ACCEPTED", "EXPIRED", "AWARDED", "PARTIAL_AWARD_REVIEW", "AWAITING_RESPONSE",
          "CLAIM_APPROVED", "AWAITING_NOTICE"}


def project_input_selectors(raw):
    """Decode input values only; skip all gold value tokens without decoding them."""
    text = raw.decode("utf-8")

    def space(pos):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        return pos

    def end(pos):
        pos = space(pos)
        if text[pos] == '"':
            pos += 1
            while pos < len(text):
                if text[pos] == "\\":
                    pos += 2
                elif text[pos] == '"':
                    return pos + 1
                else:
                    pos += 1
        elif text[pos] in "[{":
            close = "]" if text[pos] == "[" else "}"
            pos += 1
            while space(pos) < len(text):
                pos = space(pos)
                if text[pos] == close:
                    return pos + 1
                if text[pos] in ",:":
                    pos += 1
                else:
                    pos = end(pos)
        else:
            start = pos
            while pos < len(text) and text[pos] not in ",]} \t\r\n":
                pos += 1
            if pos > start:
                return pos
        raise BoundaryError("CASE_PLAN_JSON_INVALID")

    def members(pos):
        pos = space(pos)
        if text[pos] != "{":
            raise BoundaryError("CASE_PLAN_JSON_INVALID")
        pos += 1
        seen = set()
        while text[space(pos)] != "}":
            pos = space(pos)
            stop = end(pos)
            key = json.loads(text[pos:stop])
            if not isinstance(key, str) or key in seen or text[space(stop)] != ":":
                raise BoundaryError("CASE_PLAN_JSON_INVALID")
            seen.add(key)
            start = space(space(stop) + 1)
            stop = end(start)
            yield key, start, stop
            pos = space(stop)
            if text[pos] == ",":
                pos += 1
            elif text[pos] != "}":
                raise BoundaryError("CASE_PLAN_JSON_INVALID")

    plans, defaults = None, {}
    for key, left, right in members(0):
        if key in {"default_account_id", "default_resource_id"}:
            defaults[key.removeprefix("default_")] = json.loads(text[left:right])
        if key != "cases":
            continue
        if text[left] != "[":
            raise BoundaryError("CASE_PLAN_JSON_INVALID")
        plans, pos = [], space(left + 1)
        while text[pos] != "]":
            plans.append({key: json.loads(text[start:stop]) for key, start, stop in members(pos) if key in INPUT_KEYS})
            pos = space(end(pos))
            if text[pos] == ",":
                pos = space(pos + 1)
            elif text[pos] != "]":
                raise BoundaryError("CASE_PLAN_JSON_INVALID")
    if plans is None:
        raise BoundaryError("CASE_PLAN_INCOMPLETE")
    for plan in plans:
        for key, value in defaults.items():
            plan.setdefault(key, value)
    return plans


def git_bytes(source, *args):
    result = subprocess.run(["git", "-C", str(source), *args], capture_output=True, check=False)
    if result.returncode:
        raise BoundaryError("GIT_PROVENANCE_UNAVAILABLE")
    return result.stdout


class Fixture:
    """All private fixture access is local. Gold decoding has a phase guard."""
    def __init__(self, root, *, pinned_manifest=None, suite="initial"):
        self.root = root.resolve()
        self.schema = read_json(local_path(root, "SCHEMA.json"))
        if self.schema.get("schema_version") != "fresh-blind-1":
            raise BoundaryError("FIXTURE_SCHEMA_UNSUPPORTED")
        self.suite, self.additional_evidence, self.base_expected = suite, None, None
        if suite == "boundaries":
            extension = read_json(local_path(root, "BOUNDARY-SCHEMA.json"))
            if extension.get("schema_version") != "fresh-blind-boundaries-1" or extension.get("initial_freeze_commit") != FREEZE:
                raise BoundaryError("BOUNDARY_SCHEMA_UNSUPPORTED")
            self.base_expected = self.schema["private"]["expected"]["path"]
            self.additional_evidence = extension["additional_evidence"]
            self.schema["private"]["expected"]["path"] = extension["additional_expected"]
            self.schema["hash_manifest"] = extension["manifest"]
        manifest_bytes = local_path(root, self.schema["hash_manifest"]).read_bytes()
        if pinned_manifest is not None and manifest_bytes != pinned_manifest:
            raise BoundaryError("FREEZE_MANIFEST_MISMATCH")
        self.manifest_hash = digest(manifest_bytes)
        manifest = json.loads(manifest_bytes)
        files = manifest.get("files", manifest)
        if isinstance(files, list):
            files = {row["path"]: row["sha256"] for row in files}
        self.hashes = {}
        for name, expected in files.items():
            if isinstance(expected, dict):
                expected = expected["sha256"]
            if not isinstance(expected, str) or not re.fullmatch("[a-f0-9]{64}", expected):
                raise BoundaryError("MANIFEST_SCHEMA_UNSUPPORTED")
            actual = digest(local_path(root, name).read_bytes())
            if actual != expected:
                raise BoundaryError("FIXTURE_HASH_MISMATCH")
            self.hashes[name] = actual
        required = [self.schema["public_contract"]["path"]] + [self.schema["private"][k]["path"]
                    for k in ("overlay", "accounts", "evidence", "correspondence", "expected")]
        if set(required) - self.hashes.keys():
            raise BoundaryError("MANIFEST_INCOMPLETE")
        if self.additional_evidence and self.additional_evidence not in self.hashes:
            raise BoundaryError("MANIFEST_INCOMPLETE")
        self.observed_hash = None

    def path(self, kind):
        relative = (self.schema["public_contract"]["path"] if kind == "public" else
                    self.schema["private"][kind]["path"])
        return local_path(self.root, relative)

    def rows(self, kind):
        paths = [self.path(kind)]
        if kind == "evidence" and self.additional_evidence:
            paths.append(local_path(self.root, self.additional_evidence))
        return [json.loads(line) for path in paths for line in path.read_bytes().splitlines() if line.strip()]

    def plan(self, external=None, *, allow_input_projection=False):
        if external:
            data = read_json(external)
            if data.get("fixture_manifest_sha256") != self.manifest_hash:
                raise BoundaryError("INPUT_PLAN_UNBOUND")
            rows = data["cases"]
            if any(set(row) - INPUT_KEYS for row in rows):
                raise BoundaryError("INPUT_PLAN_CONTAINS_NONINPUT_FIELDS")
        elif allow_input_projection:
            # Explicit operator opt-in: project input fields, discard expected fields.
            rows = project_input_selectors(self.path("expected").read_bytes())
        else:
            raise BoundaryError("INPUT_PLAN_REQUIRED")
        if not rows or len({row["id"] for row in rows}) != len(rows):
            raise BoundaryError("CASE_PLAN_INVALID")
        for row in rows:
            if not {"id", "as_of", "input_artifact_ids", "input_correspondence_ids"} <= row.keys():
                raise BoundaryError("CASE_PLAN_INCOMPLETE")
            instant(row["as_of"])
        return rows

    def seal_observations(self, observations):
        self._sealed = json.dumps(observations, sort_keys=True)
        self.observed_hash = digest(observations)
        return self.observed_hash

    def gold(self):
        if self.observed_hash is None:
            raise BoundaryError("GOLD_BEFORE_OBSERVATIONS")
        result = read_json(self.path("expected"))
        if self.base_expected:
            result["terms"] = read_json(local_path(self.root, self.base_expected))["terms"]
            for case in result["cases"]:
                for key in ("period_seconds", "eligible_base"):
                    if key in result:
                        case.setdefault(key, result[key])
        return result

    def unchanged(self):
        return all(digest(local_path(self.root, name).read_bytes()) == value for name, value in self.hashes.items())


def snapshot_source(source):
    files = {str(path.relative_to(source)): digest(path.read_bytes())
             for path in sorted((source / "uptime").rglob("*.py"))}
    return {"commit": git_bytes(source, "rev-parse", "HEAD").decode().strip(),
            "tree_sha256": digest(files), "files_count": len(files)}


@contextmanager
def quiet_runtime():
    """Drop product output at the OS descriptor layer, including server threads."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = [os.dup(fd) for fd in (1, 2)]
    previous = logging.root.manager.disable
    try:
        with open(os.devnull, "wb") as sink:
            for fd in (1, 2):
                os.dup2(sink.fileno(), fd)
            logging.disable(logging.CRITICAL)
            yield
    finally:
        # Buffered Python writes must be discarded before the descriptors return.
        sys.stdout.flush()
        sys.stderr.flush()
        logging.disable(previous)
        for fd, backup in zip((1, 2), saved):
            os.dup2(backup, fd)
            os.close(backup)


TRANSPORT_MODE = "socket"


@contextmanager
def listener(scope, at):
    """Same app and Ed25519 grants for both transports; only socket proves HTTP."""
    import httpx
    import uvicorn
    from fastapi.testclient import TestClient
    from uptime.auth import SCRIPT
    from uptime.auth_client import ReviewerClient
    from uptime.server import create_app
    from uptime.source_config import SourceConfig, create_source
    from uptime.correspondence_types import Scope
    with TemporaryDirectory(prefix="blind-local-") as work:
        sock = None
        if TRANSPORT_MODE == "socket":
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sock.listen(128)
            origin = "http://127.0.0.1:" + str(sock.getsockname()[1])
        else:
            origin = "http://127.0.0.1:8765"
        subjects = {role: "blind-" + role for role in ("status", "customer", "billing", "vendor")}
        config = SourceConfig(version=1, channel="LOCAL_SYNTHETIC", tenant="bears", mode="replay",
                              origin=origin, services=[])
        pairs = [create_source(config, name, role, Scope(**scope)) for role, name in subjects.items()]
        config = config.model_copy(update={"services": [pair[0] for pair in pairs]})
        senders = {pair[1].subject: pair[1] for pair in pairs}
        secret = secrets.token_urlsafe(48)
        app = create_app(Path(work) / "private.sqlite", mode="replay", rehearsal=True,
                         approvals_enabled=True, rehearsal_secret=secret, origin=origin,
                         service_credentials=config.credentials("replay", origin, "bears"))
        clock = [instant(at)]
        app.state.correspondence.clock = lambda: clock[0]
        config.bind(app.state.correspondence)
        server, thread = None, None
        try:
            if sock:
                server = uvicorn.Server(uvicorn.Config(app, log_config=None, log_level="critical", access_log=False))
                thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
                thread.start()
                deadline = time.monotonic() + 15
                while not server.started:
                    if not thread.is_alive() or time.monotonic() > deadline:
                        raise BoundaryError("LISTENER_UNAVAILABLE")
                    time.sleep(.02)
                client_context = httpx.Client(base_url=origin, trust_env=False, timeout=20)
            else:
                client_context = TestClient(app, base_url=origin, client=("127.0.0.1", 41000))
            with client_context as client:
                reviewer = ReviewerClient(client, origin, SCRIPT, secret)
                yield Transport(client, reviewer, app, origin, subjects, senders, clock)
        finally:
            if server:
                server.should_exit = True
                thread.join(timeout=10)
            if sock:
                sock.close()
            if thread and thread.is_alive():
                raise BoundaryError("LISTENER_SHUTDOWN_FAILED")


class Transport:
    def __init__(self, client, reviewer, app, origin, subjects, senders, clock):
        self.client, self.reviewer, self.app, self.origin = client, reviewer, app, origin
        self.subjects, self.senders, self.clock = subjects, senders, clock
        self.operations = []

    def record(self, operation, response):
        self.operations.append({"operation": operation, "http_status": response.status_code})
        if response.status_code != 200:
            return None
        return response.json()

    def get(self, path, operation):
        return self.record(operation, self.client.get(path, headers=self.reviewer.headers))

    def post(self, path, body, operation):
        return self.record(operation, self.reviewer.post(path, body))

    def deliver(self, path, role, scope, body, identifier, available_at):
        from uptime.auth_client import service_headers
        if instant(available_at) < self.clock[0]:
            raise BoundaryError("ARRIVAL_CLOCK_REVERSED")
        self.clock[0] = instant(available_at)
        raw = json.dumps({"event_id": identifier, "scope": scope, "body": body}, separators=(",", ":")).encode()
        subject = self.subjects[role]
        headers = service_headers(instance=self.app.state.auth.instance, origin=self.origin, subject=subject,
                                  key=self.senders[subject], path=path + "/events", body=raw)
        return self.record("signed_" + role + "_event", self.client.post(path + "/events", content=raw, headers=headers))


def compact_case(row):
    if row is None:
        return {"available": False}
    outcome = row.get("outcome")
    stage = row.get("stage")
    return {"available": True, "outcome": outcome if outcome in OUTCOMES else "UNMAPPED",
            "stage": stage if stage in STAGES else "UNMAPPED", "amount": export_money(row.get("amount")),
            "submissions_count": len(row.get("submissions", [])),
            "evidence_count": len(row.get("evidence", [])),
            "actions_count": len(row.get("actions", [])),
            "awarded": export_money(row.get("ledger", {}).get("awarded")),
            "case_id_sha256": digest(row["id"]) if row.get("id") else None,
            "outcome_id_sha256": digest(row["outcome_id"]) if row.get("outcome_id") else None,
            "outcome_record_sha256": digest([row.get("id"), row.get("version"), row.get("observation_digest"), outcome]),
            "receipt_ids_sha256": [digest(r["id"]) for r in row.get("submissions", [])],
            "historical_receipt_ids_sha256": [digest(e["receipt_id"]) for e in row.get("evidence", []) if e.get("receipt_id")],
            "reply_event_ids_sha256": [digest(r["event_id"]) for r in row.get("replies", [])],
            "preflight_outcome": row.get("preflight", {}).get("outcome"),
            "filing_cutoff": row.get("filing_cutoff", row.get("claim_cutoff")),
            "filing_status": row.get("filing_status"),
            "issuance_status": row.get("issuance_status"),
            "response_sha256": digest(row)}


def promote_and_exercise(transport, prefix, state, intake):
    """Independently authored public controls; normal actions and case readback."""
    from _blind_acceptance_mapping import promotion_scenarios
    if transport.post(prefix + "/evaluate", {"facts": {}}, "shadow_dispatch_refused") is not None:
        raise BoundaryError("INACTIVE_DISPATCH_ACCEPTED")
    scenarios = promotion_scenarios(intake["document"]["text"].encode(), state["manifest"], intake["overlay"])
    state = transport.post(prefix + "/tests", dict(revision=state["revision"], tests=scenarios), "independent_shadow_tests")
    if not state or not all(row["passed"] for row in state.get("checks", [])):
        raise BoundaryError("INDEPENDENT_SHADOW_CONTROL_FAILED")
    for operation in ("interpret", "approve", "activate"):
        actions = [row["id"] for row in state.get("actions", []) if row["operation"] == operation]
        if operation == "interpret" and not state.get("interpretation_required"):
            continue
        if len(actions) != 1:
            raise BoundaryError("INDEPENDENT_PROMOTION_ACTION_UNAVAILABLE")
        state = transport.post(prefix + "/actions/" + actions[0], {}, "scripted_" + operation)
        if not state:
            raise BoundaryError("INDEPENDENT_PROMOTION_REFUSED")
    result = {"authority": "SCRIPTED_LOCAL_SYNTHETIC", "human_authority": False, "controls": []}
    for scenario in scenarios:
        row = transport.post(prefix + "/evaluate", {"facts": scenario["facts"]}, "independent_dispatch")
        if not row:
            raise BoundaryError("INDEPENDENT_DISPATCH_UNAVAILABLE")
        readback = transport.get("/api/cases/" + row["id"], "independent_case_readback")
        passed = (row["outcome"] == scenario["expected"]["outcome"]
                  and row["amount"] == scenario["expected"].get("amount")
                  and readback is not None and all(readback.get(k) == row.get(k) for k in ("id", "outcome", "amount", "version")))
        result["controls"].append(dict(scenario_sha256=digest(scenario), passed=passed,
                                       observed=compact_case(row), readback_sha256=digest(readback)))
        transport.last_independent_case = row
    return state, result


def export_money(value):
    money(value)  # validate before a string can enter an exported receipt
    return value


def bound_account(accounts, overlay, plan):
    account = plan.get("account_id", overlay["authorized_account"])
    resource = plan.get("resource_id", overlay["authorized_resource"])
    rows = [r for r in accounts if r["account_id"] == account and r["resource_id"] == resource]
    if len(rows) != 1:
        raise BoundaryError("SCOPE_NOT_UNIQUE")
    row = rows[0]
    authorized = (row.get("consenting") is True and account == overlay["authorized_account"]
                  and resource == overlay["authorized_resource"]
                  and account not in overlay["excluded_account_ids"]
                  and resource not in overlay["excluded_resource_ids"])
    return row, authorized


def fresh_intake(public, overlay, account, artifacts):
    """Translate explicit identity/billing fields only. No contract rule projection."""
    invoices = [r for r in artifacts if r["kind"] == "invoice" and r["account_id"] == account["account_id"]]
    mappings = [r for r in artifacts if r["kind"] == "billing_resource_attestation"
                and r["account_id"] == account["account_id"] and r["resource_id"] == account["resource_id"]]
    # Missing mapping is deliberately unbound; the product must refuse it.
    fee_ref = mappings[0]["recurring_line_id"] if len(mappings) == 1 else "unasserted-fee-reference"
    def boundary(value):
        return instant(value + "T00:00:00Z" if re.fullmatch(r"\d{4}-\d\d-\d\d", value) else value)
    last = boundary(overlay["valid_until_exclusive"]) - timedelta(microseconds=1)
    from _blind_acceptance_mapping import public_identity
    identity = public_identity(public)
    translated = dict(agreement=overlay["overlay_id"], account=account["account_id"], product=account["service"],
                      plan="Unspecified", resource_id=account["resource_id"], resource_label=account["endpoint"],
                      currency=invoices[0]["currency"] if len(invoices) == 1 else "USD",
                      fee_line_ref=fee_ref, effective_from=boundary(overlay["valid_from"]).date().isoformat(),
                      effective_until=last.date().isoformat())
    if identity.get("agreement"):
        translated["public_agreement"] = identity["agreement"]
    if identity.get("scope"):
        translated["public_product"] = identity["scope"]["product"]
        if identity["scope"].get("plan"):
            translated["public_plan"] = identity["scope"]["plan"]
    document = dict(name="Independent synthetic public terms", classification="synthetic_public",
                    uri="urn:synthetic:sha256:" + digest(public), text=public.decode())
    return {"document": document, "overlay": translated}


def general_control(source):
    """Read preexisting independent-of-holdout test inputs, without executing tests.

    This is an explicitly different supported agreement. Its estimate is never
    compared with holdout money. No extraction proposal is made or staged.
    """
    raw = git_bytes(source, "show", "940cd45:tests/test_v4_routes_integration.py")
    module = ast.parse(raw)
    values = {}
    def literal(node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict" and not node.args:
            return {item.arg: literal(item.value) for item in node.keywords}
        return ast.literal_eval(node)
    for node in module.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"SCOPE", "INTERVAL", "SMALL", "TEXT"}:
                values[name] = literal(node.value)
        if isinstance(node, ast.ClassDef) and node.name == "App":
            activate = next(m for m in node.body if isinstance(m, ast.FunctionDef) and m.name == "activate")
            # The independent expected value was written before this runner existed.
            defaults = dict(zip([a.arg for a in activate.args.args][-len(activate.args.defaults):], activate.args.defaults))
            values["EXPECTED"] = literal(defaults["expected"])
    if set(values) != {"SCOPE", "INTERVAL", "SMALL", "TEXT", "EXPECTED"}:
        raise BoundaryError("GENERAL_CONTROL_SOURCE_INVALID")
    values["source_sha256"] = digest(raw)
    return values


def activate_control(transport, setup, account):
    facts = setup["SMALL"] | {"account": account["account_id"]}
    overlay = {k: facts[k] for k in ("agreement", "account", "product", "plan", "fee_line_ref")}
    # Exact validity from the already supported public control, not frozen terms.
    dates = re.search(r"^Effective: (\d{4}-\d\d-\d\d) through (\d{4}-\d\d-\d\d)$", setup["TEXT"], re.M)
    if not dates:
        raise BoundaryError("GENERAL_CONTROL_DATES_INVALID")
    overlay.update(currency="USD", effective_from=dates[1], effective_until=dates[2])
    prefix = "/api/vendors/general-diagnostic"
    state = transport.post(prefix + "/candidates", dict(document=dict(name="Preexisting general diagnostic control",
                           uri="urn:synthetic:general-diagnostic", classification="synthetic_public", text=setup["TEXT"]),
                           overlay=overlay), "general_intake")
    if not state or state.get("state") != "SHADOW":
        raise BoundaryError("GENERAL_CONTROL_QUARANTINED")
    tests = [dict(name="Preexisting positive", facts=facts, expected=dict(outcome="ELIGIBLE", amount=setup["EXPECTED"])),
             dict(name="Zero outage control", facts=facts | {"eligible_downtime_minutes": 0}, expected=dict(outcome="INELIGIBLE"))]
    state = transport.post(prefix + "/tests", dict(revision=state["revision"], tests=tests), "general_tests")
    for operation in ("approve", "activate"):
        actions = [a["id"] for a in state.get("actions", []) if a.get("operation") == operation] if state else []
        if len(actions) != 1:
            raise BoundaryError("GENERAL_CONTROL_NOT_READY")
        state = transport.post(prefix + "/actions/" + actions[0], {}, "general_" + operation)
    return facts, state


def exercise_general(source, account, messages):
    if not messages:
        return {"required_count": 0, "delivered_count": 0, "checks": []}
    setup = general_control(source)
    results = []
    # Each independently authored message gets its own control; no earlier answer
    # can overwrite another message's observed classification.
    for message in messages:
        observation = {"message_sha256": digest(message), "text_sha256": digest(message["text"].encode()), "fail_codes": []}
        try:
            if message["account_id"] != account["account_id"] or message["resource_id"] != account["resource_id"]:
                raise BoundaryError("GENERAL_MESSAGE_SCOPE_REFUSED")
            scope = setup["SCOPE"] | {"account": account["account_id"], "component": account["resource_id"]}
            with listener(scope, setup["SMALL"]["received_at"]) as transport:
                observation["operations"] = transport.operations
                facts, state = activate_control(transport, setup, account)
                path = "/api/correspondence/claims/inbox-general-control"
                row = transport.post("/api/correspondence/claims", dict(claim_id="inbox-general-control", scope=scope), "general_create")
                from calendar import monthrange
                first = instant(scope["month"] + "-01T00:00:00Z")
                following = first + timedelta(days=monthrange(first.year, first.month)[1])
                records = [
                    ("status", dict(kind="status", **setup["INTERVAL"])),
                    ("customer", dict(kind="impact", affected=True, exclusion="none", **setup["INTERVAL"])),
                    ("billing", dict(kind="invoice", lines=[dict(id=facts["fee_line_ref"], kind="affected_api",
                        amount=format(Decimal(facts["monthly_fee_cents"]) / 100, ".2f"))])),
                    ("status", dict(kind="coverage", start=first.isoformat(), end=following.isoformat(),
                        complete=facts["month_complete"], exclusions_removed=facts["exclusions_removed"],
                        incident_ids=[scope["incident"]], total_eligible_minutes=facts["eligible_downtime_minutes"]))]
                for index, (role, body) in enumerate(records):
                    row = transport.deliver(path, role, scope, body, "general-" + str(index), facts["received_at"])
                    if row is None:
                        raise BoundaryError("GENERAL_CONTROL_EVIDENCE_REFUSED")
                row = transport.get(path, "general_preflight")
                if not row or money_check(setup["EXPECTED"], row.get("amount"), available=True) != "PASS":
                    raise BoundaryError("GENERAL_CONTROL_PREFLIGHT_FAILED")
                for action in ("approve-claim", "submit-claim"):
                    row = transport.post(path + "/actions/" + action, {}, "general_" + action.replace("-", "_"))
                if not row or not row.get("submissions"):
                    raise BoundaryError("GENERAL_CONTROL_NO_SUBMISSION")
                if instant(message["available_at"]) < instant(facts["received_at"]):
                    raise BoundaryError("GENERAL_MESSAGE_PREDATES_CONTROL")
                delivery = transport.deliver(path, "vendor", scope, dict(kind="message", text=message["text"],
                    receipt_id=row["submissions"][-1]["id"]), message["id"], message["available_at"])
                row = transport.get(path, "general_observed")
                observation.update(delivered=delivery is not None, observed=compact_case(row), operations=transport.operations,
                                   control_source_sha256=setup["source_sha256"],
                                   control_terms_sha256=digest(setup["TEXT"].encode()))
                # Never infer successful dispute semantics from a 200 alone.
                if not delivery or not row:
                    observation["fail_codes"].append("GENERAL_MESSAGE_NOT_ACCEPTED")
                elif row.get("stage") == "HUMAN_REVIEW":
                    observation["fail_codes"].append("GENERAL_DENIAL_UNRESOLVED")
        except Exception as exc:
            observation["fail_codes"].append(exc.args[0] if isinstance(exc, BoundaryError) else "GENERAL_RUNTIME_UNAVAILABLE")
        results.append(observation)
    return {"required_count": len(messages), "delivered_count": sum(r.get("delivered", False) for r in results), "checks": results}


def independent_inbox_controls(public):
    """Three expressly scripted worlds, separate from every private heldout case."""
    from _blind_acceptance_mapping import independent_reports, promotion_scenarios, public_identity
    from _blind_acceptance_expectations import term_value
    identity = public_identity(public)
    results = []
    for kind in ("positive_and_cure", "negative", "late_denial"):
        result = dict(control=kind, authority="SCRIPTED_LOCAL_SYNTHETIC", passed=False, fail_codes=[])
        try:
            overlay = dict(agreement="independent-control-agreement", public_agreement=identity["agreement"],
                account="independent-control-account", product=identity["scope"]["product"], plan="Independent",
                resource_id="independent-resource", resource_label="endpoint", currency="USD", fee_line_ref="independent-fee",
                effective_from=identity["effective"][0], effective_until="2099-12-31")
            intake = dict(document=dict(name="Public source independent protocol control", classification="synthetic_public",
                uri="urn:synthetic:sha256:"+digest(public), text=public.decode()), overlay=overlay)
            # Month/identities belong exclusively to the authored control world.
            manifest_stub = identity | {"effective": identity["effective"]}
            scenarios = promotion_scenarios(public, manifest_stub, overlay)
            from copy import deepcopy
            facts = deepcopy(scenarios[0]["facts"])
            if kind == "negative":
                # A one-second covered incident keeps every required filing
                # item meaningful while remaining below the public trigger.
                first = facts["intervals"][0]
                first["end"] = (instant(first["start"]) + timedelta(seconds=1)).isoformat()
            scope = dict(account=overlay["account"], vendor=identity["vendor"], contract=overlay["agreement"],
                service=overlay["product"], component=overlay["resource_id"], invoice="independent-invoice",
                incident="independent-outage", currency="USD", month=facts["month"], region="independent-region")
            with listener(scope, facts["received_at"]) as transport:
                result["operations"] = transport.operations
                prefix = "/api/vendors/independent-inbox-control"
                state = transport.post(prefix+"/candidates", intake, "independent_inbox_intake")
                if not state or state.get("state") != "SHADOW":
                    raise BoundaryError("INDEPENDENT_INBOX_INTAKE_FAILED")
                state, _ = promote_and_exercise(transport, prefix, state, intake)
                path = "/api/correspondence/claims/inbox-independent-control"
                row = transport.post("/api/correspondence/claims", {"claim_id":"inbox-independent-control", "scope":scope}, "independent_inbox_create")
                reports = independent_reports(facts, state["manifest"], scope)
                for i, (role, body) in enumerate(reports):
                    if not transport.deliver(path, role, scope, body, "independent-report-"+str(i), facts["received_at"]):
                        raise BoundaryError("INDEPENDENT_INBOX_REPORT_REFUSED")
                row = transport.get(path, "independent_inbox_preflight")
                if kind == "negative":
                    refused = transport.post(path+"/actions/approve-claim", {}, "independent_negative_approval_refused")
                    result["passed"] = bool(row and row["outcome"] == "INELIGIBLE" and refused is None and not row["submissions"])
                elif kind == "late_denial":
                    cutoff = term_value(("filing_deadline_inclusive",), state["manifest"] | {"_measurement_month": facts["month"]})
                    arrived = cutoff + timedelta(seconds=1)
                    material = reports[-1][1]
                    original = dict(kind="original_filing_receipt", source_ref="independent-vendor-receipt", receipt_id="independent-late-receipt",
                        received_at=arrived.isoformat(), observed_at=arrived.isoformat(), submitted_to=material["channel"], fields=material["fields"])
                    if not transport.deliver(path, "vendor", scope, original, "independent-late", arrived.isoformat()):
                        raise BoundaryError("INDEPENDENT_LATE_RECEIPT_REFUSED")
                    if not transport.deliver(path, "vendor", scope, dict(kind="message", receipt_id=original["receipt_id"],
                        text="The filing window expired."), "independent-late-denial", arrived.isoformat()):
                        raise BoundaryError("INDEPENDENT_LATE_DENIAL_REFUSED")
                    row = transport.get(path, "independent_late_readback")
                    result["passed"] = bool(row and row["stage"] == "DENIAL_ACCEPTED" and not row["actions"] and not row["submissions"])
                else:
                    if not row or row["amount"] != scenarios[0]["expected"]["amount"]:
                        raise BoundaryError("INDEPENDENT_SIGNED_POSITIVE_NOT_READY")
                    result["positive"] = compact_case(row)
                    for action in ("approve-claim", "submit-claim"):
                        row = transport.post(path+"/actions/"+action, {}, "independent_"+action)
                    if not row or len(row["submissions"]) != 1:
                        raise BoundaryError("INDEPENDENT_INITIAL_RECEIPT_MISSING")
                    initial = row["submissions"][0]["id"]
                    arrival = instant(facts["received_at"]) + timedelta(hours=1)
                    transport.deliver(path, "vendor", scope, dict(kind="message", receipt_id=initial,
                        text="Please supply the service log, record CONTROL-7."), "independent-request", arrival.isoformat())
                    waiting = transport.get(path, "independent_request_readback")
                    content = "Independent scripted control log. These are authored test observations."
                    common = dict(artifact_ref="CONTROL-7", artifact_type="resource_log", body_sha256=digest(content.encode()), observed_at=arrival.isoformat())
                    transport.deliver(path, "customer", scope, dict(kind="artifact", source_ref="independent-archive", content=content, **common),
                                      "independent-artifact", arrival.isoformat())
                    transport.deliver(path, "status", scope, dict(kind="status_verification", source_ref="independent-verifier", linked_ref=scope["incident"], **common),
                                      "independent-verification", arrival.isoformat())
                    ready = transport.get(path, "independent_cure_ready")
                    approved = transport.post(path+"/actions/approve-response", {}, "independent_response_approve")
                    transport.clock[0] = arrival + timedelta(days=1)
                    row = transport.post(path+"/actions/submit-response", {}, "independent_response_submit")
                    readback = transport.get(path, "independent_cure_readback")
                    result["passed"] = bool(waiting and waiting["stage"] == "NEEDS_EVIDENCE" and ready and ready["stage"] == "RESPONSE_DRAFTED"
                        and approved and row and readback and len(row["submissions"]) == len(readback["submissions"]) == 2
                        and row["submissions"][-1]["packet"].get("in_reply_to") == initial)
                result["observed"] = compact_case(row)
                if not result["passed"]:
                    result["fail_codes"].append("INDEPENDENT_EXPECTED_STAGE_OR_OUTCOME_MISMATCH")
                rollback = next(a["id"] for a in state["actions"] if a["operation"] == "rollback")
                revoked = transport.post(prefix+"/actions/"+rollback, {}, "independent_inbox_rollback")
                result["rollback_verified"] = bool(revoked and not revoked.get("active_version") and
                    transport.post(prefix+"/evaluate", {"facts":facts}, "independent_inbox_rollback_refusal") is None)
        except Exception as exc:
            result["fail_codes"].append(exc.args[0] if isinstance(exc, BoundaryError) else "INDEPENDENT_INBOX_CONTROL_UNAVAILABLE")
        results.append(result)
    return results


def exercise_case(fixture, source, plan, overlay, accounts, evidence, correspondence, public, term_observations=None):
    observed = {"case_sha256": digest(plan["id"]), "fail_codes": [], "operations": []}
    messages, account, authorized = [], None, False
    try:
        selected, future = select_records(evidence, plan["input_artifact_ids"], plan["as_of"])
        messages, future_messages = select_records(correspondence, plan["input_correspondence_ids"], plan["as_of"])
        observed.update(input_sha256=digest({"plan": plan, "evidence": selected, "messages": messages}),
                        available_evidence_count=len(selected), future_evidence_count=len(future),
                        available_correspondence_count=len(messages), future_correspondence_count=len(future_messages))
        controls = [r for r in selected if r["kind"] == "scope_control"]
        target = dict(plan)
        for key in ("account_id", "resource_id"):
            if plan.get("requested_" + key):
                target[key] = plan["requested_" + key]
        if len(controls) == 1 and "account_id" not in target and "resource_id" not in target:
            target.update({key: controls[0][key] for key in ("account_id", "resource_id")})
        account, authorized = bound_account(accounts, overlay, target)
        observed["scope_authorized"] = authorized
        authorized_account, _ = bound_account(accounts, overlay, {})
        intake = fresh_intake(public, overlay, authorized_account, selected)
        receipts = [r for r in selected if r["kind"] == "historical_customer_filing_receipt"]
        invoices = [r for r in selected if r["kind"] == "invoice"]
        months = {plan[k] for k in ("month", "measured_month") if plan.get(k)}
        months.update(r["measured_month"] for r in receipts)
        months.update(r["period_start"][:7] for r in invoices)
        if not months:
            months.update(r["start"][:7] for r in selected if r.get("start"))
        measured_month = next(iter(months)) if len(months) == 1 else None
        observed["measurement_month"] = measured_month
        if measured_month is None:
            # A diagnostic inbox can still test scope refusal and missing-input
            # behavior. This placeholder is never an asserted measurement month.
            months = {plan["as_of"][:7]}
            observed["diagnostic_month_only"] = True
            if authorized:
                observed["fail_codes"].append("MEASUREMENT_MONTH_UNRESOLVED")
        scope = dict(account=authorized_account["account_id"], component=authorized_account["resource_id"],
                     vendor=overlay["provider"], contract=overlay["overlay_id"], service=authorized_account["service"],
                     invoice=invoices[0]["invoice_id"] if len(invoices) == 1 else "unasserted-invoice",
                     incident=receipts[0]["id"] if len(receipts) == 1 else "unasserted-incident",
                     currency=intake["overlay"]["currency"], month=next(iter(months)), region="unasserted")
        first_arrival = min([plan["as_of"]] + [r["available_at"] for r in selected + messages], key=instant)
        with listener(scope, first_arrival) as transport:
            observed["operations"] = transport.operations
            prefix = "/api/vendors/blind-frozen"
            state = transport.post(prefix + "/candidates", intake, "frozen_intake")
            candidate = state.get("state") if state else "UNAVAILABLE"
            observed["candidate_state"] = candidate if candidate in {
                "DRAFT", "VALIDATED", "SHADOW", "APPROVED", "ACTIVE", "QUARANTINED", "REVOKED", "UNAVAILABLE"} else "UNMAPPED"
            observed["candidate_sha256"] = digest(state) if state else None
            if state and state.get("manifest") and term_observations is not None:
                term_observations.append(state["manifest"] | {"_measurement_month": measured_month})
            if state and state.get("manifest"):
                from _blind_acceptance_expectations import term_value
                observed["contract_channel_sha256"] = digest(state["manifest"].get("submission_channel"))
                cutoff = term_value(("filing_deadline_inclusive",), state["manifest"] | {"_measurement_month": measured_month})
                observed["contract_cutoff"] = cutoff.isoformat() if cutoff else None
            if not state or state.get("state") == "QUARANTINED":
                observed["fail_codes"].append("PUBLIC_EXTRACTION_OR_BINDING_UNSUPPORTED")
            else:
                state, observed["independent_lifecycle"] = promote_and_exercise(transport, prefix, state, intake)
                observed["candidate_state"] = state["state"]
            requested_scope = scope | {"account": account["account_id"], "component": account["resource_id"]}
            path = "/api/correspondence/claims/inbox-blind-case"
            row = transport.post("/api/correspondence/claims", dict(claim_id="inbox-blind-case", scope=requested_scope), "blind_create")
            observed["scope_refused"] = row is None and not authorized and transport.operations[-1]["http_status"] == 403
            if row is not None:
                if not authorized:
                    observed["fail_codes"].append("UNAUTHORIZED_SCOPE_ACCEPTED")
                from _blind_acceptance_mapping import event_plan
                events, gaps = event_plan(selected, scope, state["manifest"]) if state and state.get("manifest") else ([], ["ACTIVE_TERMS_UNAVAILABLE"])
                if state and state.get("manifest"):
                    from _blind_acceptance_mapping import bounded_input_diagnostic
                    observed["input_diagnostic"] = bounded_input_diagnostic(selected, scope, state["manifest"])
                observed["fail_codes"].extend(gaps)
                observed["deliveries"] = []
                chronology = [(r, False) for r in events] + [(r, True) for r in messages]
                for record, is_message in sorted(chronology, key=lambda pair: instant(pair[0]["available_at"])):
                    if is_message:
                        before_message = transport.get(path, "before_vendor_arrival")
                        submissions = before_message.get("submissions", []) if before_message else []
                        historical = [r for r in selected if r["kind"] == "historical_customer_filing_receipt"
                                      and instant(r["available_at"]) <= instant(record["available_at"])]
                        receipt_id = submissions[-1]["id"] if submissions else historical[0]["id"] if len(historical) == 1 else "unfiled"
                        envelope = scope | {"account": record["account_id"], "component": record["resource_id"]}
                        body = dict(kind="message", receipt_id=receipt_id, text=record["text"])
                        delivered = transport.deliver(path, "vendor", envelope, body, record["id"], record["available_at"])
                        observed["deliveries"].append(dict(kind="message", input_sha256=digest(record),
                            text_sha256=digest(record["text"].encode()), receipt_id_sha256=digest(receipt_id),
                            wire_sha256=digest(body), accepted=delivered is not None))
                        if delivered is None:
                            observed["fail_codes"].append("HISTORICAL_REPLY_ROUTE_UNAVAILABLE" if historical else "NO_READY_DENIAL_REFUSED")
                    else:
                        delivered = transport.deliver(path, record["role"], scope, record["body"], record["id"], record["available_at"])
                        observed["deliveries"].append(dict(kind=record["body"]["kind"],
                            source_ids_sha256=[digest(v) for v in record["source_ids"]],
                            source_locators_sha256=[digest(v) for v in record["source_locators"]],
                            wire_sha256=digest(record["body"]), event_id_sha256=digest(record["id"]),
                            accepted=delivered is not None, receipt_sha256=digest(delivered)))
                        if delivered is None:
                            observed["fail_codes"].append("SUPPORTED_EVIDENCE_DELIVERY_REFUSED")
                transport.clock[0] = instant(plan["as_of"])
                row = transport.get(path, "blind_observed")
                observed["observation"] = compact_case(row)
                from _blind_acceptance_expectations import metrics
                observed["metrics"] = metrics(row) if row else {}
                observed["observed_provenance_sha256"] = sorted({digest(str(e[k])) for e in row.get("evidence", [])
                    for k in ("source_ref", "receipt_id", "original_ref", "observed_at", "available_at", "filed_at") if e.get(k)}) if row else []
                observed["missing_categories"] = missing_categories(row)
                observed["preflight_trace_sha256"] = digest(row.get("preflight", {})) if row else None
                observed["calculation_available"] = bool(state and state.get("active_version") and row)
            if state and state.get("active_version"):
                actions = [a["id"] for a in state["actions"] if a["operation"] == "rollback"]
                revoked = transport.post(prefix + "/actions/" + actions[0], {}, "scripted_rollback") if actions else None
                refused = transport.post(prefix + "/evaluate", {"facts": {}}, "rollback_dispatch_refused")
                observed["rollback_verified"] = bool(revoked and not revoked.get("active_version") and refused is None)
                last = getattr(transport, "last_independent_case", None)
                history = transport.get("/api/cases/" + last["id"], "rollback_history_readback") if last else None
                observed["rollback_history_verified"] = bool(history and all(history.get(k) == last.get(k) for k in ("id", "outcome", "amount", "version")))
            observed["operations"] = transport.operations
    except Exception as exc:
        observed["fail_codes"].append(exc.args[0] if isinstance(exc, BoundaryError) else "CASE_RUNTIME_UNAVAILABLE")
        if not isinstance(exc, BoundaryError):
            import traceback
            observed["runtime_error"] = {"type": type(exc).__name__, "frames": [
                {"file": Path(frame.filename).name, "line": frame.lineno} for frame in traceback.extract_tb(exc.__traceback__)]}
        observed.setdefault("calculation_available", False)
    try:
        observed["generality"] = exercise_general(source, account, messages) if authorized else {
            "required_count": len(messages), "delivered_count": 0, "checks": [], "fail_codes": ["GENERAL_SCOPE_REFUSED"]}
    except Exception:
        observed["generality"] = {"required_count": len(messages), "delivered_count": 0, "checks": [],
                                   "fail_codes": ["GENERAL_CONTROL_SOURCE_UNAVAILABLE"]}
    observed["fail_codes"] = sorted(set(observed["fail_codes"]))
    return observed


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, path + (str(index),))
    else:
        yield path, value


MONEY_FIELDS = {"amount", "credit_amount", "expected_amount", "expected_credit_amount", "supported_credit"}
DECISION_FIELDS = {"outcome", "decision", "expected_outcome", "expected_decision"}
STAGE_FIELDS = {"stage", "expected_stage"}
METADATA_FIELDS = {"description", "name", "notes", "rationale", "explanation"}


def compare_case(expected, observed):
    """Every expected leaf is checked or explicitly reported as unmapped.

    New expected field names never become silent passes. No matching is based on
    vendor names, case IDs, text similarity or candidate-generated expectations.
    """
    checks = []
    from _blind_acceptance_expectations import NUMERIC_FIELDS, decision_check, normalized, numeric_check
    target = observed.get("observation", {})
    payload = {k: v for k, v in expected.items() if k not in INPUT_KEYS | METADATA_FIELDS}
    for path, value in leaves(payload):
        name = path[-1]
        check = {"field_sha256": digest(path), "feature": "unmapped_expectation", "status": "EXPECTATION_UNMAPPED"}
        if name in NUMERIC_FIELDS:
            check.update(feature="measurement" if "seconds" in name or "availability" in name else "money",
                         status=numeric_check(name, value, observed), expected_sha256=digest(value))
            if name == "confirmed_covered_seconds" and value is not None and observed.get("input_diagnostic"):
                floor = Decimal(observed["input_diagnostic"]["covered_seconds"])
                check["input_floor_status"] = ("GOLD_BELOW_INPUT_FLOOR" if Decimal(value) < floor else
                    "FLOOR_MATCH_ONLY" if Decimal(value) == floor else "GOLD_ABOVE_OBSERVED_FLOOR")
        elif name in MONEY_FIELDS:
            export_money(value)
            check.update(feature="money", status=money_check(value, target.get("amount"),
                         available=observed.get("calculation_available", False)),
                         expected_money=value, observed_money=target.get("amount"))
        elif name in DECISION_FIELDS:
            aliases = {"UNKNOWN": "INSUFFICIENT_EVIDENCE", "UNSUPPORTED": "UNSUPPORTED_RULE"}
            normalized = value.upper().replace(" ", "_") if isinstance(value, str) else None
            normalized = aliases.get(normalized, normalized)
            check["feature"] = "decision"
            if normalized in OUTCOMES:
                check["status"] = ("UNAVAILABLE" if not target.get("available") else
                                   "PASS" if normalized == target.get("outcome") else "WRONG_DECISION")
            else:
                check["feature"], check["status"] = decision_check(value, observed)
        elif name in STAGE_FIELDS:
            check["feature"] = "dispute_stage"
            if value in STAGES:
                check["status"] = ("UNAVAILABLE" if not target.get("available") else
                                   "PASS" if value == target.get("stage") else "WRONG_STAGE")
        elif name == "scope_refused" and type(value) is bool:
            check.update(feature="scope", status="PASS" if value == observed.get("scope_refused") else "WRONG_SCOPE")
        elif name == "remedy_available" and type(value) is bool:
            check.update(feature="filing_gate", status="UNAVAILABLE" if not observed.get("calculation_available") else
                         "PASS" if value == (target.get("outcome") == "ELIGIBLE") else "WRONG_REMEDY_AVAILABILITY")
        elif name == "remedy_available":
            actual = target.get("amount")
            if target.get("filing_status") in {"OUTSIDE_WINDOW", "LATE_SUPPLEMENT"}:
                actual = "0.00"
            check.update(feature="filing_gate", status=money_check(value, actual, available=target.get("available", False)))
        elif name == "filing_valid":
            actual = target.get("filing_status")
            check.update(feature="filing_gate", status="UNAVAILABLE" if actual in {None, "UNDETERMINED"} else
                         "PASS" if value == (actual == "TIMELY") else "WRONG_FILING_GATE")
        elif name in {"deadline_inclusive", "required_channel"}:
            check.update(feature="filing_gate", status="UNAVAILABLE")
            if name == "deadline_inclusive" and observed.get("contract_cutoff"):
                check["status"] = "PASS" if instant(value) == instant(observed["contract_cutoff"]) else "WRONG_TIMESTAMP"
            if name == "required_channel" and observed.get("contract_channel_sha256"):
                check["status"] = "PASS" if digest(value) == observed["contract_channel_sha256"] else "WRONG_CHANNEL"
        elif "required_provenance" in path:
            available = set(observed.get("observed_provenance_sha256", []))
            for delivery in observed.get("deliveries", []):
                if delivery.get("accepted"):
                    available.update(delivery.get("source_ids_sha256", []))
                    available.update(delivery.get("source_locators_sha256", []))
            check.update(feature="provenance", status="PASS" if digest(value) in available else "PROVENANCE_NOT_OBSERVED")
        elif "required_evidence_requests" in path:
            from _blind_acceptance_expectations import normalized as normalize
            words = normalize(value)
            required = "resource_mapping" if "provider" in words and "mapping" in words else "scoped_billing" if "billing" in words else None
            check.update(feature="evidence_request", status="SEMANTIC_PREDICATE_REVIEW_REQUIRED" if required is None else
                         "PASS" if required in observed.get("missing_categories", []) else "EVIDENCE_REQUEST_NOT_OBSERVED")
        elif "must_not" in path:
            from _blind_acceptance_expectations import normalized as normalize
            words = normalize(value)
            check.update(feature="prohibited_behavior", status="SEMANTIC_PREDICATE_REVIEW_REQUIRED")
            if "cash" in words or "refund" in words or "send" in words or "claim" in words and ("account" in words or "resource" in words):
                check["status"] = "PASS" if target.get("submissions_count", 0) == 0 else "PROHIBITED_ACTION_OBSERVED"
            elif "approve" in words and "credit" in words:
                check["status"] = "PASS" if target.get("awarded") in {None, "0.00"} else "UNSUPPORTED_AWARD"
            elif "zero" in words and "amount" in words:
                check["status"] = "PASS" if target.get("amount") is None else "UNKNOWN_COERCED_TO_MONEY"
            elif "appeal" in words:
                check["status"] = "PASS" if target.get("stage") not in {"RESPONSE_DRAFTED", "RESPONSE_APPROVED"} else "PROHIBITED_APPEAL_OBSERVED"
        elif name == "interpretation":
            check.update(feature="interpretation", status="SEMANTIC_PREDICATE_REVIEW_REQUIRED")
        checks.append(check)
    if not checks:
        checks.append({"feature": "expectation_coverage", "status": "NO_EXPECTATIONS"})
    return checks


def compare_terms(expected, manifests):
    from _blind_acceptance_expectations import term_value, term_equal
    checks = []
    for path, value in leaves(expected):
        check = {"feature": "contract_terms", "field_sha256": digest(path), "status": "UNAVAILABLE"}
        if manifests:
            resolved = []
            try:
                for manifest in manifests:
                    current = term_value(path, manifest)
                    if current is not None:
                        resolved.append(current)
            except (KeyError, IndexError, TypeError, ValueError):
                check["status"] = "TERM_EXPECTATION_UNMAPPED"
            else:
                check["status"] = "UNAVAILABLE" if not resolved else "PASS" if all(term_equal(path, value, item) for item in resolved) else "WRONG_TERM"
        checks.append(check)
    return checks or [{"feature": "contract_terms", "status": "TERMS_EXPECTATIONS_MISSING"}]


def compare_gold(gold, observations, manifests=()):
    index = {row["case_sha256"]: row for row in observations}
    checks = []
    expected_cases = gold.get("cases", [])
    if len({digest(row["id"]) for row in expected_cases}) != len(expected_cases):
        raise BoundaryError("DUPLICATE_GOLD_CASE")
    for expected in expected_cases:
        key = digest(expected["id"])
        if key not in index:
            checks.append({"case_sha256": key, "checks": [{"feature": "execution", "status": "CASE_NOT_EXECUTED"}]})
        else:
            checks.append({"case_sha256": key, "checks": compare_case(expected, index[key])})
    if set(index) - {digest(row["id"]) for row in expected_cases}:
        checks.append({"checks": [{"feature": "execution", "status": "UNEXPECTED_CASE_EXECUTED"}]})
    # Terms are required even when intake is quarantined. Count every expected
    # leaf, preserving extraction unavailability rather than treating it as zero.
    terms = compare_terms(gold.get("terms", {}), manifests)
    global_checks = [{"feature": "global_refusal_control", "field_sha256": digest(["global_refusal_controls", i]),
                      "predicate_sha256": digest(value), "status": "GLOBAL_CONTROL_REQUIRES_INDEPENDENT_EXECUTION"}
                     for i, value in enumerate(gold.get("global_refusal_controls", []))]
    return {"cases": checks, "terms": terms, "global_controls": global_checks}


def extraction_provenance(public):
    folder = os.environ.get("UPTIME_PUBLIC_EXTRACTIONS")
    if not folder:
        return {"accepted_count": 0, "rejection_count": 0, "fail_codes": ["EXTRACTION_DIRECTORY_UNSET"]}
    root = Path(folder)
    sha = digest(public)
    accepted = root / (sha + ".json")
    rejected = sorted((root / "rejections" / sha).glob("*.json"))
    return {"accepted_count": int(accepted.is_file()),
            "accepted_sha256": digest(accepted.read_bytes()) if accepted.is_file() else None,
            "rejection_count": len(rejected), "rejection_sha256": [digest(path.read_bytes()) for path in rejected],
            "propositions_enabled": os.environ.get("UPTIME_MODEL_PROPOSITIONS") == "1"}


def restrict_network():
    """Private execution cannot connect to a model/provider, even by accident."""
    def audit(event, args):
        if event == "socket.connect":
            address = args[1]
            if not isinstance(address, tuple) or address[0] != "127.0.0.1":
                raise BoundaryError("NONLOCAL_TRANSPORT_FORBIDDEN")
        if event == "socket.getaddrinfo" and args[0] not in {"127.0.0.1", None}:
            raise BoundaryError("NONLOCAL_RESOLUTION_FORBIDDEN")
        if event == "subprocess.Popen":
            argv = args[1]
            if not isinstance(argv, (list, tuple)) or argv[0] != "git":
                raise BoundaryError("EXTERNAL_PROCESS_FORBIDDEN")
    sys.addaudithook(audit)


def run(args):
    global TRANSPORT_MODE
    TRANSPORT_MODE = getattr(args, "transport", "socket")
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    result = {"protocol": "blind-acceptance/2", "transport": TRANSPORT_MODE,
              "network_proof": False, "gate_2_pass": False, "gate_3_pass": False,
              "fail_codes": [], "observations": [], "authority": "SCRIPTED_LOCAL_SYNTHETIC",
              "commercial_authority": False, "at": datetime.now(UTC).isoformat(),
              "runner_sha256": digest(Path(__file__).read_bytes())}
    try:
        runner_files = {name: digest(Path(__file__).with_name(name).read_bytes()) for name in
                        ("blind_acceptance.py", "blind_mapping.py", "blind_expectations.py")}
        result["runner_files_sha256"] = runner_files
        before = snapshot_source(source)
        result["product"] = before
        suite = getattr(args, "suite", "initial")
        fixture = Fixture(args.fixture_root, suite=suite)
        pinned = args.manifest_sha256
        if not pinned:
            pinned = FROZEN_MANIFEST if suite == "initial" else digest(git_bytes(source, "show", BOUNDARY_FREEZE + ":fixtures/fresh-blind/BOUNDARY-SHA256SUMS.json"))
        if fixture.manifest_hash != pinned:
            raise BoundaryError("FIXTURE_NOT_EXPLICITLY_PINNED")
        result["fixture_manifest_sha256"] = fixture.manifest_hash
        result["fixture_files_count"] = len(fixture.hashes)
        result["suite"] = suite
        if suite == "boundaries":
            result["fixture_freeze"] = git_bytes(source, "rev-parse", BOUNDARY_FREEZE).decode().strip()
            result["base_fixture_freeze"] = FREEZE
            if digest(local_path(fixture.root, "SHA256SUMS.json").read_bytes()) != FROZEN_MANIFEST:
                raise BoundaryError("INITIAL_FREEZE_CHANGED_IN_EXTENSION")
        elif pinned == FROZEN_MANIFEST:
            frozen = git_bytes(source, "show", FREEZE + ":fixtures/fresh-blind/SHA256SUMS.json")
            if digest(frozen) != fixture.manifest_hash:
                raise BoundaryError("FROZEN_COMMIT_MISMATCH")
            result["fixture_freeze"] = FREEZE
        plan = fixture.plan(args.input_plan, allow_input_projection=args.allow_input_projection)
        result["input_plan_sha256"] = digest(plan)
        result["input_projection_authorized"] = args.allow_input_projection
        public = fixture.path("public").read_bytes()
        result["public_source_sha256"] = digest(public)
        result["extraction"] = extraction_provenance(public)
        overlay = read_json(fixture.path("overlay"))
        accounts = read_json(fixture.path("accounts"))["accounts"]
        evidence = fixture.rows("evidence")
        correspondence = fixture.rows("correspondence")
        result["counts"] = dict(cases=len(plan), evidence=len(evidence), correspondence=len(correspondence), accounts=len(accounts))
        term_observations = []
        for row in plan:
            result["observations"].append(exercise_case(fixture, source, row, overlay, accounts, evidence, correspondence, public, term_observations))
        result["independent_inbox"] = independent_inbox_controls(public)
        result["observations_sha256"] = fixture.seal_observations(dict(cases=result["observations"], manifests=term_observations,
                                                                       independent_inbox=result["independent_inbox"]))
        # This is the only expected-result decoding phase. No observed result can
        # subsequently change, and no gold is sent back to the application.
        sealed = json.loads(fixture._sealed)
        result["comparison"] = compare_gold(fixture.gold(), sealed["cases"], sealed["manifests"])
        if not fixture.unchanged():
            raise BoundaryError("FIXTURE_CHANGED_DURING_RUN")
        if any(digest(Path(__file__).with_name(name).read_bytes()) != sha for name, sha in runner_files.items()):
            raise BoundaryError("WITNESS_CHANGED_DURING_RUN")
        if before != snapshot_source(source):
            raise BoundaryError("PRODUCT_CHANGED_DURING_RUN")
        statuses = Counter(c["status"] for row in result["comparison"]["cases"] for c in row["checks"])
        statuses.update(c["status"] for c in result["comparison"]["terms"])
        statuses.update(c["status"] for c in result["comparison"]["global_controls"])
        result["check_counts"] = dict(sorted(statuses.items()))
        controls = [control for row in result["observations"] for control in row.get("independent_lifecycle", {}).get("controls", [])]
        result["independent_check_counts"] = dict(passed=sum(c["passed"] for c in controls), failed=sum(not c["passed"] for c in controls),
            rollback_passed=sum(row.get("rollback_verified", False) and row.get("rollback_history_verified", False) for row in result["observations"]))
        if controls and any(not c["passed"] for c in controls):
            result["fail_codes"].append("INDEPENDENT_READBACK_OR_OUTCOME_FAILED")
        result["independent_check_counts"]["inbox_passed"] = sum(c["passed"] and c.get("rollback_verified", False) for c in result["independent_inbox"])
        result["independent_check_counts"]["inbox_failed"] = len(result["independent_inbox"]) - result["independent_check_counts"]["inbox_passed"]
        if result["independent_check_counts"]["inbox_failed"]:
            result["fail_codes"].append("INDEPENDENT_SIGNED_INBOX_CONTROL_FAILED")
        result["network_proof"] = TRANSPORT_MODE == "socket" and any(row["operations"] for row in result["observations"])
        result["fail_codes"] = sorted(set(result["fail_codes"]) | {code for row in result["observations"] for code in row["fail_codes"]})
        # Agreement remains blocked until complete terms, financial and dispute
        # observations exist. A safe quarantine is not contract acceptance.
        result["gate_2_pass"] = bool(statuses) and set(statuses) == {"PASS"} and not result["fail_codes"]
        result["gate_3_pass"] = result["gate_2_pass"] and all(
            row.get("generality", {}).get("required_count", 0) == row.get("generality", {}).get("delivered_count", -1)
            and not any(c.get("fail_codes") for c in row.get("generality", {}).get("checks", []))
            for row in result["observations"])
    except Exception as exc:
        result["fail_codes"].append(exc.args[0] if isinstance(exc, BoundaryError) else "RUNNER_UNAVAILABLE")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.cwd())
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--suite", choices=("initial", "boundaries"), default="initial")
    parser.add_argument("--manifest-sha256", default=None,
                        help="Explicit pin required for any different external fixture")
    parser.add_argument("--transport", choices=("socket", "testclient"), default="socket")
    parser.add_argument("--input-plan", type=Path)
    parser.add_argument("--allow-input-projection", action="store_true",
                        help="Operator authorizes input selectors only from the combined fixture file")
    args = parser.parse_args()
    if args.receipt.exists():
        print(json.dumps({"fail_codes": ["RECEIPT_ALREADY_EXISTS"]}))
        return 2
    restrict_network()
    with quiet_runtime():
        receipt = run(args)
    try:
        write_receipt(args.receipt, receipt)
    except Exception:
        print(json.dumps({"fail_codes": ["RECEIPT_WRITE_UNAVAILABLE"]}))
        return 2
    print(json.dumps({"receipt_sha256": digest(args.receipt.read_bytes()), "gate_2_pass": receipt["gate_2_pass"],
                      "gate_3_pass": receipt["gate_3_pass"], "counts": receipt.get("check_counts", {}),
                      "fail_codes": receipt["fail_codes"]}))
    return 0 if receipt["gate_2_pass"] and receipt["gate_3_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
