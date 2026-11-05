#!/usr/bin/env python3
"""Local prospective witness; frozen private inputs are never an extraction input.

Only application HTTP endpoints perform candidate, review, evaluation, case and
delivery operations. Offline setup enrolls fresh synthetic source public keys.
The reviewer is SCRIPTED_TEST, not a human. No provider/model is invoked here.
Every response and private projection stays in the operator's runs directory.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.prospective.projection import public_join, overlay_for, project_case, fingerprint, instant


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    raw = json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(raw)
    Path(path).chmod(0o600)


def frozen_path(base, relative):
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("Frozen file escaped its directory")
    return path


def verify_freeze(base, expected_manifest):
    manifest_path = base / "freeze-manifest.json"
    if digest(manifest_path.read_bytes()) != expected_manifest:
        raise ValueError("Freeze manifest changed")
    manifest = read_json(manifest_path)
    for relative, expected in manifest["files"].items():
        if digest(frozen_path(base, relative).read_bytes()) != expected:
            raise ValueError("Frozen private file changed or is missing")
    if digest(Path(manifest["public_path"]).read_bytes()) != manifest["public_sha256"]:
        raise ValueError("Frozen public source changed")
    return manifest


def summarize(evaluations, denials, protocol, *, active, workbench, fatal=None):
    """Empty, missing, blocked or duplicated results can never be all green."""
    expected = protocol["expected_counts"]
    evaluation_ids = [row["id"] for row in evaluations]
    denial_ids = [row["id"] for row in denials]
    complete = (
        len(evaluations) == expected["evaluations"] == len(set(evaluation_ids))
        and len(denials) == expected["denials"] == len(set(denial_ids))
    )
    measured = sum(row.get("measured") is True for row in evaluations)
    classified = sum(row.get("measured") is True for row in denials)
    matched = sum(row.get("matched") is True for row in evaluations)
    denial_matched = sum(row.get("matched") is True for row in denials)
    evidence_complete = len(denials) == expected["denials"] and all(
        len(row.get("evidence_http_statuses", [])) == row.get("evidence_deliveries_expected", 6)
        and row.get("evidence_deliveries_expected", 6) >= 6
        and all(status == 200 for status in row["evidence_http_statuses"]) for row in denials
    )
    return {
        "complete_result_rows": complete,
        "evaluations_expected": expected["evaluations"],
        "evaluations_measured": measured,
        "evaluations_matched": matched,
        "evaluations_blocked": expected["evaluations"] - measured,
        "denials_expected": expected["denials"],
        "denials_measured": classified,
        "denials_matched": denial_matched,
        "denials_blocked": expected["denials"] - classified,
        "signed_evidence_deliveries_expected": sum(row.get("evidence_deliveries_expected", 6) for row in denials)
            + 6 * (expected["denials"] - len(denials)),
        "signed_evidence_deliveries_accepted": sum(status == 200 for row in denials
                                                   for status in row.get("evidence_http_statuses", [])),
        "activation_observed": active,
        "workbench_evaluation_cases": workbench,
        "workbench_correspondence_cases": sum(row.get("workbench_readback") is True for row in denials),
        "fatal": fatal,
        "all_green": bool(complete and evidence_complete and active and not fatal
                          and workbench >= expected["workbench_cases_min"]
                          and measured == matched == expected["evaluations"]
                          and classified == denial_matched == expected["denials"]),
    }


class Journal:
    def __init__(self, output):
        self.output = output
        self.rows = []

    def record(self, label, response, payload=None):
        try:
            body = response.json()
        except ValueError:
            body = {"non_json_response_sha256": digest(response.content)}
        self.rows.append({"label": label, "http_status": response.status_code,
                          "request": payload, "response": body})
        return body

    def post(self, reviewer, path, payload, label):
        response = reviewer.post(path, payload)
        return response, self.record(label, response, payload)


def enrolled_reviewer(client, origin, database, subject, tenant):
    """Exercise the normal issuer/mandate path with explicitly scripted test keys."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from uptime.auth import enroll
    from uptime.auth_client import ReviewerClient
    from uptime.auth_keys import generate_reviewer_key
    from uptime.mandates import Mandate, describe, install, local_purpose, register_issuer

    credential = generate_reviewer_key()
    enroll(database, subject, credential, tenant=tenant)
    issuer = Ed25519PrivateKey.generate()
    issuer_subject = "synthetic-independent-mandate-issuer"
    register_issuer(database, {"subject": issuer_subject,
                              "public_key": issuer.public_key().public_bytes_raw().hex(),
                              "local_purposes": ("workspace", "claim-filing", "vendor-promotion")})
    binding = describe(database, subject)

    class ScriptedReviewer(ReviewerClient):
        maximum_amount_cents = 0

        def post(self, path, payload):
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
            claim = None
            if local_purpose(path) == "claim-filing":
                detail_path, action = path.rsplit("/actions/", 1)
                response = self.client.get(detail_path, headers=self.headers)
                response.raise_for_status()
                offered = next(a for a in response.json()["actions"] if a["id"] == action)
                claim = offered["mandate_claim"]
                if claim["max_amount_cents"] > self.maximum_amount_cents:
                    raise ValueError("Offered claim exceeds the original invoice fee ceiling")
            stamp = int(time.time())
            mandate = Mandate(schema_version="uptime-reviewer-mandate/1", mandate_id=str(uuid.uuid4()),
                              **binding, issuer=issuer_subject, valid_from=stamp - 5, valid_until=stamp + 300,
                              path=path, body_sha256=digest(raw), effect=None, claim=claim)
            install(database, {"mandate": mandate.model_dump(), "signature": issuer.sign(mandate.signing_bytes()).hex()})
            return super().post(path, payload)

    return ScriptedReviewer(client, origin, subject, credential)


@contextmanager
def transport(app, kind, origin, listener):
    if kind == "testclient":
        from fastapi.testclient import TestClient
        with TestClient(app, base_url=origin, client=("127.0.0.1", 45100),
                        raise_server_exceptions=False) as client:
            yield client
        return
    import httpx
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Local socket listener failed to start")
            time.sleep(0.02)
        with httpx.Client(base_url=origin, timeout=20, trust_env=False) as client:
            yield client
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        if thread.is_alive():
            raise RuntimeError("Local listener did not stop")


def expected(gold):
    outcomes = {"eligible": "ELIGIBLE", "ineligible": "INELIGIBLE", "unknown": "INSUFFICIENT_EVIDENCE"}
    row = {"outcome": outcomes[gold["outcome"]]}
    if gold["outcome"] == "eligible":
        row["amount"] = gold["credit_usd"]
    return row


def seal(output, filenames, name="seal.json"):
    save(output / name, {"at": datetime.now(timezone.utc).isoformat(),
                         "files": {n: digest((output / n).read_bytes()) for n in filenames}})


def check_seal(output, name="seal.json"):
    receipt = read_json(output / name)
    if any(digest((output / n).read_bytes()) != value for n, value in receipt["files"].items()):
        raise ValueError("Sealed observation changed")
    return receipt


def public_controls(manifest, overlay):
    """New explicit scenarios. Never derive them from private records or expected rows."""
    period = manifest["fixed_period"]
    minutes = int((instant(period["end"]) - instant(period["start"])).total_seconds() // 60)
    scope = {k: overlay[k] for k in ("agreement", "account", "product", "plan")}
    scope["month"] = period["start"][:7]
    def record(ref, content):
        return dict(scope, verified=True, complete=True, ref="synthetic-control-" + ref,
                    recorded_at=period["end"], content=content, content_sha256=fingerprint(content))
    facts = dict(scope, fee_line_ref=overlay["fee_line_ref"],
                 service_monitor=record("monitor", {"source": "simulated_vendor", "unavailable_minutes": minutes}),
                 service_invoice=record("invoice", {"currency": "USD", "paid": True, "lines": [
                     {"ref": overlay["fee_line_ref"], "kind": "recurring_subscription", "category": "subscription", "amount_cents": 10000}]}),
                 filing_proof=dict(scope, verified=True, ref="synthetic-control-filing", received_at=period["end"],
                                   fields={k: "Explicit synthetic control " + k for k in manifest.get("request_fields", [])}))
    missing = deepcopy(facts)
    missing.pop("service_monitor")
    return [{"name": "SYNTHETIC_CONTROL_entire_month_outage_100_USD", "facts": facts},
            {"name": "SYNTHETIC_CONTROL_missing_monitor", "facts": missing}]


def control_expectations(receipt):
    # Independent Decimal reading of the public propositions. No product arithmetic.
    tiers = [t for row in receipt["proposal"] if isinstance(row.get("value"), dict)
             for t in row["value"].get("tiers", []) if Decimal(t["below"]) > 0
             and (t.get("at_least") is None or Decimal(t["at_least"]) == 0)]
    if not tiers:
        raise ValueError("No public tier covers the explicit zero-availability control")
    tier = min(tiers, key=lambda t: Decimal(t["below"]))
    from decimal import ROUND_HALF_UP
    amount = Decimal(tier["credit"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return [{"outcome": "ELIGIBLE", "amount": str(amount)}, {"outcome": "INSUFFICIENT_EVIDENCE"}]


def onboard(reviewer, journal, prefix, document, overlay, receipt, output, suffix):
    response, state = journal.post(reviewer, prefix + "/candidates",
                                   {"document": document, "overlay": overlay}, "candidate")
    result = {"http_status": response.status_code, "candidate_state": state.get("state"),
              "candidate_reason": state.get("reason"), "actions_taken": [], "checks": []}
    if response.status_code == 200 and state.get("state") == "SHADOW":
        manifest = state["manifest"]
        if manifest.get("source_version") != overlay["agreement"] or manifest.get("agreement") != overlay["public_agreement"]:
            raise ValueError("Compiled public agreement/version differs from the witnessed exact join")
        controls = public_controls(manifest, overlay)
        observations = []
        for control in controls:
            r, observation = journal.post(reviewer, prefix + "/shadow-preview",
                {"revision": state["revision"], "facts": control["facts"]}, control["name"])
            observations.append({"http_status": r.status_code, "observation": observation})
        filename = "public-controls-" + suffix + ".json"
        save(output / filename, {"scenarios": controls, "observations": observations,
                                "original_input_denominator": False, "human_approval": False})
        seal(output, [filename], "public-controls-" + suffix + "-seal.json")
        # The control run is sealed before expected arithmetic is computed.
        check_seal(output, "public-controls-" + suffix + "-seal.json")
        expectations = control_expectations(receipt)
        control_matches = [observed["http_status"] == 200
                           and observed["observation"].get("evaluation", {}).get("outcome") == want["outcome"]
                           and observed["observation"].get("evaluation", {}).get("amount") == want.get("amount")
                           for observed, want in zip(observations, expectations, strict=True)]
        save(output / ("public-controls-" + suffix + "-comparison.json"),
             {"expected": expectations, "matches": control_matches, "original_input_denominator": False})
        if not all(control_matches):
            raise ValueError("Sealed explicit public control disagrees with independent public-source arithmetic")
        suite = [dict(control, expected=want) for control, want in zip(controls, expectations, strict=True)]
        response, state = journal.post(reviewer, prefix + "/tests",
                                       {"revision": state["revision"], "tests": suite}, "explicit-public-control-suite")
        result["checks"] = state.get("checks", [])
        for _ in range(3):
            action = next((a for a in state.get("actions", [])
                           if a.get("operation") in {"interpret", "approve", "activate"}), None)
            if not action:
                break
            response, state = journal.post(reviewer, prefix + "/actions/" + action["id"], {},
                                           "SCRIPTED_TEST-" + action["operation"])
            result["actions_taken"].append({"operation": action["operation"], "http_status": response.status_code,
                                             "human_approval": False})
            if response.status_code != 200:
                break
    result.update(state=state.get("state"), active=state.get("state") == "ACTIVE" and bool(state.get("active_version")),
                  source_sha256=state.get("manifest", {}).get("document", {}).get("sha256"),
                  extraction_method=state.get("extraction", {}).get("method"))
    return result, state


def send_event(client, origin, instance, sender, claim_id, body, journal, label):
    from uptime.auth_client import service_headers
    path = f"/api/correspondence/claims/{claim_id}/events"
    event = {"event_id": "event-" + secrets.token_hex(10), "scope": sender.scope.model_dump(), "body": body}
    raw = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode()
    headers = service_headers(instance=instance, origin=origin, subject=sender.subject,
                              key=sender, path=path, body=raw)
    response = client.post(path, content=raw, headers=headers)
    return response, journal.record(label, response, event)


def correspondence_probe(client, reviewer, config, senders, case, denial, projected,
                         base, journal, clock):
    """Send original aggregate evidence. Unknown completeness stays false."""
    claim_id = "inbox-prospective-" + denial["id"]
    prefix = "/api/correspondence/claims/" + claim_id
    clock[0] = instant(case["filing_at"])
    response, state = journal.post(reviewer, "/api/correspondence/claims",
                                   {"claim_id": claim_id, "scope": config.services[0].scope.model_dump()},
                                   "create-independent-correspondence")
    evidence_statuses, unsupported = [], []
    instance = client.get("/api/auth/context").json()["instance"]
    for name, field, role, artifact_type in (
        ("service_monitor", "status_path", "status", "resource_log"),
        ("service_invoice", "invoice_path", "billing", "invoice_detail"),
    ):
        record = projected["facts"].get(name)
        if record is None:
            continue
        raw = frozen_path(base, case[field]).read_bytes()
        # The projected event's digest and the original artifact's byte hash are
        # different commitments. Preserve both; never call either provider-confirmed.
        body = {"kind": name, "source_ref": record["ref"], "observed_at": record["recorded_at"],
                "recorded_at": record["recorded_at"], "plan": record["plan"], "complete": record["complete"],
                "content": record["content"], "content_sha256": record["content_sha256"]}
        # Scope lives in the signed envelope; never overwrite a conflicting original.
        source_matches = record["verified"] and all(record.get(k) == projected["facts"].get(k)
                             for k in ("account", "agreement", "product", "plan", "month"))
        if source_matches:
            r, _ = send_event(client, reviewer.origin, instance, senders[role], claim_id,
                              body, journal, "original-" + name)
            evidence_statuses.append(r.status_code)
            if r.status_code != 200:
                unsupported.append({"kind": name, "http_status": r.status_code})
        else:
            evidence_statuses.append(None)
            unsupported.append({"kind": name, "reason": "Source scope mismatch; event withheld"})
        descriptor = {"source_ref": record["ref"], "observed_at": record["recorded_at"],
                      "artifact_ref": record["ref"], "artifact_type": artifact_type, "body_sha256": digest(raw)}
        for role_name, event in (
            ("customer", dict(descriptor, kind="artifact", content=raw.decode())),
            (role, dict(descriptor, kind=role + "_verification", linked_ref=record["ref"])),
        ):
            r, _ = send_event(client, reviewer.origin, instance, senders[role_name], claim_id,
                              event, journal, "frozen-local-integrity-" + name + "-" + role_name)
            evidence_statuses.append(r.status_code)
    # Only explicit original filing materials/receipts can be submitted as evidence.
    # A case's proposed filing_at is not a historical provider receipt.
    additional = 0
    original_receipt = None
    for field, role in (("filing_material", "customer"), ("original_filing_receipt", "vendor")):
        if case.get(field):
            additional += 1
            r, _ = send_event(client, reviewer.origin, instance, senders[role], claim_id,
                              case[field], journal, "original-" + field)
            evidence_statuses.append(r.status_code)
            if field == "original_filing_receipt" and r.status_code == 200:
                original_receipt = case[field]["receipt_id"]
    state = journal.record("correspondence-before-filing", client.get(prefix, headers=reviewer.headers))
    invoice = projected["facts"].get("service_invoice", {}).get("content", {})
    reviewer.maximum_amount_cents = sum(line["amount_cents"] for line in invoice.get("lines", [])
                                       if type(line.get("amount_cents")) is int and line["amount_cents"] >= 0)
    for _ in range(2):
        action = next((a for a in state.get("actions", []) if a["id"] in {"approve-claim", "submit-claim"}), None)
        if not action:
            break
        response, state = journal.post(reviewer, prefix + "/actions/" + action["id"], {}, "SCRIPTED_TEST-" + action["id"])
        if response.status_code != 200:
            break
    submissions = state.get("submissions", [])
    filed = bool(submissions) or bool(original_receipt)
    receipt = submissions[-1]["id"] if submissions else original_receipt or "UNFILED-" + denial["id"]
    clock[0] = instant(denial["received_at"])
    response, _ = send_event(client, reviewer.origin, instance, senders["vendor"], claim_id,
                             {"kind": "message", "receipt_id": receipt, "text": denial["text"]},
                             journal, "original-signed-denial" if filed else "EXPLICIT_UNFILED_CORRELATION_CONTROL")
    detail = client.get(prefix, headers=reviewer.headers)
    state = journal.record("correspondence-after-denial", detail)
    workbench_response = client.get("/api/cases/" + claim_id, headers=reviewer.headers)
    found = journal.record("new-correspondence-workbench-readback", workbench_response)
    measured = response.status_code == 200 and filed and bool(state.get("replies"))
    return {"id": denial["id"], "http_status": response.status_code, "measured": measured,
            "actual_stage": state.get("stage"), "reply_count": len(state.get("replies", [])),
            "real_local_submission": bool(submissions), "evidence_http_statuses": evidence_statuses,
            "evidence_deliveries_expected": 6 + additional, "unsupported_events": unsupported,
            "original_synthetic_receipt_accepted": bool(original_receipt), "unfiled_correlation_control": not filed,
            "blocked_reason": None if measured else "No classifiable reply through normal signed HTTP",
            "projection_issues": projected["issues"],
            "workbench_readback": workbench_response.status_code == 200 and found.get("id") == claim_id,
            "new_correspondence_case": detail.status_code == 200}


def application_identity(root):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    files = {str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted((root / "uptime").rglob("*.py"))}
    return {"root": str(root), "git_head": head, "source_files": files, "source_tree_sha256": fingerprint(files)}


def observe(args, base, output, manifest):
    """Observation phase: no semantic read of any gold file is permitted here."""
    from uptime.correspondence_types import Scope
    from uptime.server import create_app
    from uptime.source_config import SourceConfig, create_source

    private = read_json(base / "inputs/customer-overlay.json")
    cases = read_json(base / "inputs/cases.json")
    denials = read_json(base / "inputs/denials.json")
    evaluations = [{"id": c["id"], "measured": False, "blocked_reason": "Setup not completed"} for c in cases]
    denial_results = [{"id": d["id"], "measured": False, "blocked_reason": "Setup not completed"} for d in denials]
    journal = Journal(output)
    result = {"evaluation_id": manifest["evaluation_id"], "attempt": output.name, "label": args.label,
              "classification": "CURRENT_PROTOCOL_FROZEN_ORIGINAL_COMPARATOR",
              "transport": args.transport, "real_socket": args.transport == "socket", "human_approval": False,
              "reviewer_kind": "SCRIPTED_TEST", "external_calls": 0, "application_edits": False,
              "source_authority": "Four isolated synthetic test keys; no provider-confirmed private identities",
              "clock": "Explicit synthetic replay clock; real authentication clock",
              "public_source_path": manifest["public_path"], "public_sha256": manifest["public_sha256"],
              "frozen_manifest_sha256": args.freeze_sha256, "expected_evaluation_count": manifest["expected_evaluation_count"],
              "expected_denial_count": manifest["expected_denial_count"],
              "onboarding": [], "evaluations": evaluations, "denials": denial_results, "fatal": None,
              "active": False, "workbench": 0, "oracle_read_during_observation": False}
    try:
        if len(cases) != manifest["expected_evaluation_count"] or len(denials) != manifest["expected_denial_count"]:
            raise ValueError("Freeze cardinalities disagree")
        if len({c["id"] for c in cases}) != len(cases) or len({d["id"] for d in denials}) != len(denials):
            raise ValueError("Duplicate frozen scenario identity")
        document = {"name": args.document_name, "uri": "urn:synthetic:public:" + manifest["public_sha256"],
                    "classification": "synthetic_public", "text": Path(manifest["public_path"]).read_text()}
        receipt = read_json(args.extractions_dir / (manifest["public_sha256"] + ".json"))
        try:
            join = public_join(private, document["text"], receipt)
        except (KeyError, ValueError, TypeError) as exc:
            result["input_classification"] = "CONTRACT_JOIN_GAP"
            raise ValueError("Exact public agreement/version join refused: " + str(exc)) from exc
        overlay = overlay_for(private, join)
        save(output / "public-join.json", join)
        result["input_classification"] = "PUBLIC_TITLE_VERSION_PROJECTION_CORRECTED"
        projections, workbench_ids = {}, set()
        # Original denials remain separate scenarios, each in a clean local database.
        for index in range(max(1, len(denials))):
            suffix = str(index + 1)
            tenant = private["tenant_id"] + "-" + suffix
            listener = None
            if args.transport == "socket":
                listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                listener.bind(("127.0.0.1", 0))
                origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
            else:
                origin = "http://127.0.0.1:8765"
            try:
                scope = Scope(account=overlay["account"], vendor=args.vendor, contract=overlay["agreement"],
                              service=overlay["product"], component="subscription", invoice="witness-invoice-alias",
                              incident="witness-month-alias", currency="USD", month=private["period"]["start"][:7], region="global")
                config = SourceConfig(version=1, channel="LOCAL_SYNTHETIC", tenant=tenant, mode="replay", origin=origin, services=[])
                senders = {}
                for role in ("status", "billing", "customer", "vendor"):
                    grant, sender = create_source(config, "prospective." + role, role, scope)
                    config.services.append(grant)
                    senders[role] = sender
                database = output / ("workspace-" + suffix + ".sqlite")
                app = create_app(database, rehearsal=False, approvals_enabled=True, tenant=tenant,
                                 service_credentials=config.credentials("replay", origin, tenant), origin=origin)
                config.bind(app.state.correspondence)
                clock = [instant(cases[0]["filing_at"])]
                app.state.correspondence.clock = lambda: clock[0]
                with transport(app, args.transport, origin, listener) as client:
                    reviewer = enrolled_reviewer(client, origin, database, "synthetic.test.reviewer", tenant)
                    prefix = "/api/vendors/prospective-slot"
                    install, state = onboard(reviewer, journal, prefix, document, overlay, receipt, output, suffix)
                    result["onboarding"].append(install)
                    result["active"] = result["active"] or install["active"]
                    if not state.get("manifest"):
                        result["input_classification"] = "PUBLIC_CONTRACT_COMPILATION_REFUSED"
                        continue
                    if install["source_sha256"] != manifest["public_sha256"]:
                        raise ValueError("Candidate source digest differs from frozen public source")
                    if index == 0:
                        for position, case in enumerate(cases):
                            try:
                                projected = project_case(base, case, overlay, state["manifest"], manifest["files"])
                                projections[case["id"]] = projected
                                path, payload = "/evaluate", {"facts": projected["facts"]}
                                stage = "active_dispatch"
                                if not install["active"] and state.get("state") == "SHADOW":
                                    path, payload, stage = "/shadow-preview", dict(payload, revision=state["revision"]), "shadow_preview"
                                response, actual = journal.post(reviewer, prefix + path, payload, "original-" + case["id"])
                                actual = actual.get("evaluation", actual)
                                evaluations[position] = {"id": case["id"], "http_status": response.status_code,
                                    "measured": response.status_code == 200 and "outcome" in actual,
                                    "measurement_stage": stage, "actual": actual, "projection_issues": projected["issues"]}
                                if stage == "active_dispatch" and actual.get("id"):
                                    r = client.get("/api/cases/" + actual["id"], headers=reviewer.headers)
                                    found = journal.record("original-workbench-readback", r)
                                    if r.status_code == 200 and found.get("id") == actual["id"]:
                                        workbench_ids.add(actual["id"])
                            except Exception as exc:
                                evaluations[position]["blocked_reason"] = type(exc).__name__
                                save(output / ("evaluation-failure-" + str(position) + ".json"), {"type": type(exc).__name__, "detail": str(exc)})
                        result["workbench"] = len(workbench_ids)
                        save(output / "projection.json", {"overlay": overlay, "cases": projections,
                                                       "public_sha256": manifest["public_sha256"]})
                    if denials:
                        denial = denials[index]
                        case = next(c for c in cases if c["id"] == denial["case_id"])
                        projected = projections.get(case["id"])
                        if projected:
                            denial_results[index] = correspondence_probe(client, reviewer, config, senders, case, denial,
                                                                         projected, base, journal, clock)
            except Exception as exc:
                # Preserve all earlier observations and continue other isolated scenarios.
                result["fatal"] = type(exc).__name__
                save(output / ("scenario-failure-" + suffix + ".json"), {"type": type(exc).__name__, "detail": str(exc)})
            finally:
                if listener:
                    listener.close()
    except Exception as exc:
        result["fatal"] = type(exc).__name__
        save(output / "failure.json", {"type": type(exc).__name__, "detail": str(exc)})
    finally:
        save(output / "http-journal.json", journal.rows)
    return result


def compare_sealed(base, output):
    """Only this post-seal observer may interpret the frozen original oracle."""
    check_seal(output)
    result = read_json(output / "observations.json")
    gold = {g["id"]: g for g in read_json(base / "gold/evaluations.json")}
    denial_gold = {g["id"]: g for g in read_json(base / "gold/denials.json")}
    protocol = read_json(base / "gold/protocol.json")
    if ({r["id"] for r in result["evaluations"]} != set(gold)
            or {r["id"] for r in result["denials"]} != set(denial_gold)
            or protocol["expected_counts"]["evaluations"] != result["expected_evaluation_count"]
            or protocol["expected_counts"]["denials"] != result["expected_denial_count"]):
        raise ValueError("Frozen oracle and original input denominator disagree")
    for row in result["evaluations"]:
        want = expected(gold[row["id"]])
        actual = row.get("actual", {})
        row.update(expected=want, matched=bool(row["measured"] and actual.get("outcome") == want["outcome"]
                                              and actual.get("amount") == want.get("amount")))
    stages = {"accept_denial": {"DENIAL_ACCEPTED"}, "cure_missing_evidence": {"RESPONSE_DRAFTED", "RESPONSE_APPROVED"},
              "escalate": {"HUMAN_REVIEW"}}
    for row in result["denials"]:
        want = denial_gold[row["id"]]["action"]
        complete = (len(row.get("evidence_http_statuses", [])) == row.get("evidence_deliveries_expected", 6)
                    and all(s == 200 for s in row.get("evidence_http_statuses", [])))
        row.update(expected_action=want, matched=bool(row["measured"] and complete and row.get("actual_stage") in stages[want]))
    result["summary"] = summarize(result["evaluations"], result["denials"], protocol,
                                  active=result["active"], workbench=result["workbench"], fatal=result["fatal"])
    codes = [i["code"] for r in result["evaluations"] for i in r.get("projection_issues", [])]
    result["projection_issue_counts"] = {code: codes.count(code) for code in sorted(set(codes))}
    result["comparison"] = {"kind": "POST_SEAL_ORIGINAL_ORACLE", "seal_sha256": digest((output / "seal.json").read_bytes()),
                            "control_scenarios_in_original_denominator": False}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-dir", required=True, type=Path)
    parser.add_argument("--freeze-sha256", required=True)
    parser.add_argument("--vendor", required=True)
    parser.add_argument("--document-name", required=True)
    parser.add_argument("--extractions-dir", required=True, type=Path, help="Approved public-only receipts; never invokes a model")
    parser.add_argument("--app-root", type=Path, default=ROOT, help="Read-only current application checkout")
    parser.add_argument("--app-sha", help="Refuse a checkout at a different commit")
    parser.add_argument("--transport", choices=("testclient", "socket"), default="testclient")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    base, app_root = args.freeze_dir.resolve(), args.app_root.resolve()
    if base.is_relative_to(ROOT) or base.is_relative_to(app_root):
        raise ValueError("Private freeze must be outside all application repositories")
    args.extractions_dir = args.extractions_dir.resolve()
    manifest = verify_freeze(base, args.freeze_sha256)
    application = application_identity(app_root)
    if args.app_sha and application["git_head"] != args.app_sha:
        raise ValueError("Application commit differs from the requested SHA")
    sys.path.insert(0, str(app_root))
    attempts = base / "runs"
    attempts.mkdir(exist_ok=True)
    for number in range(1, 10000):
        output = attempts / f"attempt-{number:03d}"
        try:
            output.mkdir(mode=0o700)
            break
        except FileExistsError:
            continue
    else:
        raise ValueError("Attempt directory budget exhausted")
    os.environ["UPTIME_PUBLIC_EXTRACTIONS"] = str(args.extractions_dir)
    os.environ["UPTIME_MODEL_PROPOSITIONS"] = "1"
    driver_files = {"driver-snapshot.py": Path(__file__), "projection-snapshot.py": Path(__file__).with_name("projection.py")}
    for name, path in driver_files.items():
        (output / name).write_bytes(path.read_bytes())
    save(output / "start.json", {"at": datetime.now(timezone.utc).isoformat(), "application": application,
                                 "driver_sha256": {name: digest(path.read_bytes()) for name, path in driver_files.items()},
                                 "transport": args.transport, "label": args.label,
                                 "extractions_directory": str(args.extractions_dir),
                                 "public_receipt_sha256": digest((args.extractions_dir / (manifest["public_sha256"] + ".json")).read_bytes())})
    result = observe(args, base, output, manifest)
    verify_freeze(base, args.freeze_sha256)
    result["application"] = application
    result["application_unchanged"] = application == application_identity(app_root)
    if not result["application_unchanged"]:
        result["fatal"] = "ApplicationChangedDuringRun"
    save(output / "observations.json", result)
    filenames = [p.name for p in output.glob("*.json")] + list(driver_files)
    seal(output, sorted(filenames))
    result = compare_sealed(base, output)
    save(output / "result.json", result)
    verify_freeze(base, args.freeze_sha256)
    print(json.dumps({"attempt": output.name, "result_path": str(output / "result.json"), **result["summary"]}))
    return 0 if result["summary"]["all_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
