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
        len(row.get("evidence_http_statuses", [])) == 6
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
        "signed_evidence_deliveries_expected": 6 * expected["denials"],
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
                    raise ValueError("Offered claim exceeds independently frozen oracle amount")
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


def projection(base, case, overlay):
    """Map evidence without rounding downtime or manufacturing absent records."""
    invoice = read_json(base / case["invoice_path"]) if case["invoice_path"] else None
    status = read_json(base / case["status_path"]) if case["status_path"] else None
    facts = {key: overlay[key] for key in ("agreement", "account", "product", "plan", "fee_line_ref")}
    facts.update(month=case["period"]["start"][:7], received_at=case["filing_at"])
    if invoice:
        fee = sum(Decimal(line["amount_usd"]) for line in invoice["lines"]
                  if line["service"] == overlay["product"])
        facts.update(monthly_fee_cents=int(fee * 100), fee_month=facts["month"],
                     fee_ref=digest((base / case["invoice_path"]).read_bytes()))
    if status:
        down = Decimal(status["unavailable_minutes"])
        # A fractional original value must survive projection even if the API refuses it.
        down_value = int(down) if down == down.to_integral_value() else str(down)
        facts.update(eligible_downtime_minutes=down_value, monitor_source="simulated_vendor",
                     month_complete=True, exclusions_removed=True, monitor_month=facts["month"],
                     monitor_ref=digest((base / case["status_path"]).read_bytes()))
    return facts


def expected(gold):
    outcomes = {"eligible": "ELIGIBLE", "ineligible": "INELIGIBLE", "unknown": "INSUFFICIENT_EVIDENCE"}
    row = {"outcome": outcomes[gold["outcome"]]}
    if gold["outcome"] == "eligible":
        row["amount"] = gold["credit_usd"]
    return row


def onboard(reviewer, journal, prefix, document, overlay, suite):
    response, state = journal.post(reviewer, prefix + "/candidates",
                                   {"document": document, "overlay": overlay}, "candidate")
    result = {"http_status": response.status_code, "candidate_state": state.get("state"),
              "candidate_reason": state.get("reason"), "actions_taken": [], "checks": []}
    if response.status_code == 200 and state.get("state") == "SHADOW":
        response, state = journal.post(reviewer, prefix + "/tests",
                                       {"revision": state["revision"], "tests": suite}, "independent-suite")
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
    result["state"] = state.get("state")
    result["active"] = state.get("state") == "ACTIVE" and bool(state.get("active_version"))
    result["source_sha256"] = state.get("manifest", {}).get("document", {}).get("sha256")
    result["extraction_method"] = state.get("extraction", {}).get("method")
    return result


def send_event(client, origin, instance, sender, claim_id, body, journal, label):
    from uptime.auth_client import service_headers
    path = f"/api/correspondence/claims/{claim_id}/events"
    event = {"event_id": "event-" + secrets.token_hex(10), "scope": sender.scope.model_dump(), "body": body}
    raw = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode()
    headers = service_headers(instance=instance, origin=origin, subject=sender.subject,
                              key=sender, path=path, body=raw)
    response = client.post(path, content=raw, headers=headers)
    return response, journal.record(label, response, event)


def correspondence_probe(client, reviewer, app, config, senders, case, denial, gold,
                         base, overlay, journal, clock):
    """Use only frozen records; do not invent outage timestamps or a filed receipt."""
    claim_id = "inbox-prospective-" + denial["id"]
    prefix = "/api/correspondence/claims/" + claim_id
    clock[0] = datetime.fromisoformat(case["filing_at"].replace("Z", "+00:00"))
    response, state = journal.post(reviewer, "/api/correspondence/claims",
                                   {"claim_id": claim_id, "scope": config.services[0].scope.model_dump()},
                                   "create-independent-correspondence")
    evidence_statuses = []
    instance = client.get("/api/auth/context").json()["instance"]
    for kind, field, role, artifact_type in (
        ("status", "status_path", "status", "resource_log"),
        ("invoice", "invoice_path", "billing", "invoice_detail"),
    ):
        if not case[field]:
            continue
        raw = (base / case[field]).read_bytes()
        original = json.loads(raw)
        ref = original["source_id"]
        descriptor = {"source_ref": ref, "observed_at": original["recorded_at"],
                      "artifact_ref": ref, "artifact_type": artifact_type, "body_sha256": digest(raw)}
        # Raw artifacts originate from the independently controlled customer sender;
        # billing/status use their separate keys to verify the corresponding digest.
        r, _ = send_event(client, reviewer.origin, instance, senders["customer"], claim_id,
                          {**descriptor, "kind": "artifact", "content": raw.decode()}, journal, kind + "-raw-artifact")
        evidence_statuses.append(r.status_code)
        r, _ = send_event(client, reviewer.origin, instance, senders[role], claim_id,
                          {**descriptor, "kind": role + "_verification", "linked_ref": ref},
                          journal, kind + "-independent-verification")
        evidence_statuses.append(r.status_code)
        if kind == "invoice":
            lines = [{"id": overlay["fee_line_ref"] if line["service"] == overlay["product"] else "excluded-coaching",
                      "kind": "affected_api" if line["service"] == overlay["product"] else "third_party",
                      "amount": line["amount_usd"]} for line in original["lines"]]
            r, _ = send_event(client, reviewer.origin, instance, senders[role], claim_id,
                              {"kind": "invoice", "lines": lines}, journal, "mapped-itemized-invoice")
            evidence_statuses.append(r.status_code)
        else:
            minutes = Decimal(original["unavailable_minutes"])
            if minutes == minutes.to_integral_value():
                r, _ = send_event(client, reviewer.origin, instance, senders[role], claim_id,
                                  {"kind": "coverage", "start": case["period"]["start"],
                                   "end": case["period"]["end"], "complete": True, "exclusions_removed": True,
                                   "incident_ids": [config.services[0].scope.incident],
                                   "total_eligible_minutes": int(minutes)}, journal, "mapped-monthly-status-total")
                evidence_statuses.append(r.status_code)
    response = client.get(prefix, headers=reviewer.headers)
    state = journal.record("correspondence-before-filing", response)
    for _ in range(2):
        action = next((a for a in state.get("actions", []) if a["id"] in {"approve-claim", "submit-claim"}), None)
        if not action:
            break
        response, state = journal.post(reviewer, prefix + "/actions/" + action["id"], {}, "SCRIPTED_TEST-" + action["id"])
        if response.status_code != 200:
            break
    submissions = state.get("submissions", [])
    # Deliberate unmatched-correlation probe when filing is blocked. It is never
    # represented as an actual submission, and its rejection cannot pass the oracle.
    receipt = submissions[-1]["id"] if submissions else "UNFILED-" + denial["id"]
    clock[0] = datetime.fromisoformat(denial["received_at"].replace("Z", "+00:00"))
    response, _ = send_event(client, reviewer.origin, instance, senders["vendor"], claim_id,
                             {"kind": "message", "receipt_id": receipt, "text": denial["text"]},
                             journal, "independent-signed-denial")
    detail = client.get(prefix, headers=reviewer.headers)
    state = journal.record("correspondence-after-denial", detail)
    workbench_response = client.get("/api/cases/" + claim_id, headers=reviewer.headers)
    workbench_case = journal.record("new-correspondence-workbench-readback", workbench_response)
    measured = response.status_code == 200 and bool(submissions) and bool(state.get("replies"))
    stages = {"accept_denial": {"DENIAL_ACCEPTED"}, "cure_missing_evidence": {"RESPONSE_DRAFTED", "RESPONSE_APPROVED"},
              "escalate": {"HUMAN_REVIEW"}}
    evidence_complete = len(evidence_statuses) == 6 and all(s == 200 for s in evidence_statuses)
    return {"id": denial["id"], "expected_action": gold["action"], "http_status": response.status_code,
            "measured": measured, "matched": bool(measured and evidence_complete and state.get("stage") in stages[gold["action"]]),
            "actual_stage": state.get("stage"), "reply_count": len(state.get("replies", [])),
            "real_local_submission": bool(submissions), "evidence_http_statuses": evidence_statuses,
            "blocked_reason": None if measured else "No classifiable reply through normal signed HTTP",
            "projection_limit": "Monthly totals do not establish specific outage start/end times; none invented",
            "workbench_http_status": workbench_response.status_code,
            "workbench_readback": workbench_response.status_code == 200 and workbench_case.get("id") == claim_id,
            "new_correspondence_case": detail.status_code == 200}


def run(args, base, output, manifest):
    from uptime.correspondence_types import Scope
    from uptime.server import create_app
    from uptime.source_config import SourceConfig, create_source

    private = read_json(base / "inputs/customer-overlay.json")
    cases = read_json(base / "inputs/cases.json")
    gold = {g["id"]: g for g in read_json(base / "gold/evaluations.json")}
    denials = read_json(base / "inputs/denials.json")
    denial_gold = {g["id"]: g for g in read_json(base / "gold/denials.json")}
    protocol = read_json(base / "gold/protocol.json")
    if len(cases) != manifest["expected_evaluation_count"] or len(denials) != manifest["expected_denial_count"]:
        raise ValueError("Freeze cardinalities disagree")
    if {c["id"] for c in cases} != set(gold) or {d["id"] for d in denials} != set(denial_gold):
        raise ValueError("Inputs and gold identities differ")
    overlay = {"agreement": private["public_sla_version"], "account": private["account_id"],
               "product": private["service"], "plan": private["plan"],
               "effective_from": private["period"]["start"][:10],
               "effective_until": (datetime.fromisoformat(private["period"]["end"].replace("Z", "+00:00"))
                                   - timedelta(days=1)).date().isoformat(),
               "fee_line_ref": "frozen-subscription-line", "currency": "USD"}
    document = {"name": args.document_name, "uri": "urn:synthetic:public:" + manifest["public_sha256"],
                "classification": "synthetic_public", "text": Path(manifest["public_path"]).read_text()}
    suite = [{"name": c["id"], "facts": projection(base, c, overlay), "expected": expected(gold[c["id"]])} for c in cases]
    save(output / "projection.json", {"document_sha256": manifest["public_sha256"], "overlay": overlay, "tests": suite})
    journal = Journal(output)
    evaluations, denial_results, onboarding = [], [], []
    workbench_ids = set()
    active = False
    fatal = None
    try:
        # Each denial receives an isolated database to avoid cross-reply state effects.
        for index, denial in enumerate(denials):
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
                              service=overlay["product"], component="subscription", invoice="frozen-invoice",
                              incident="frozen-monthly-total", currency="USD", month=private["period"]["start"][:7], region="global")
                config = SourceConfig(version=1, channel="LOCAL_SYNTHETIC", tenant=tenant, mode="replay", origin=origin, services=[])
                senders = {}
                for role in ("status", "billing", "customer", "vendor"):
                    grant, sender = create_source(config, "prospective." + role, role, scope)
                    config.services.append(grant)
                    senders[role] = sender
                database = output / ("workspace-" + suffix + ".sqlite")
                app = create_app(database, rehearsal=False,
                                 approvals_enabled=True, tenant=tenant,
                                 service_credentials=config.credentials("replay", origin, tenant), origin=origin)
                config.bind(app.state.correspondence)
                clock = [datetime.fromisoformat(cases[0]["filing_at"].replace("Z", "+00:00"))]
                # Explicit deterministic replay clock; authentication keeps its real clock.
                app.state.correspondence.clock = lambda: clock[0]
                with transport(app, args.transport, origin, listener) as client:
                    reviewer = enrolled_reviewer(client, origin, database, "synthetic.test.reviewer", tenant)
                    prefix = "/api/vendors/prospective-slot"
                    install = onboard(reviewer, journal, prefix, document, overlay, suite)
                    onboarding.append(install)
                    active = active or install["active"]
                    if install["active"] and install["source_sha256"] != manifest["public_sha256"]:
                        raise ValueError("Active source digest differs from frozen public source")
                    if index == 0:
                        for case in cases:
                            response, actual = journal.post(reviewer, prefix + "/evaluate",
                                                           {"facts": projection(base, case, overlay)}, "evaluate-" + case["id"])
                            want = expected(gold[case["id"]])
                            measured = response.status_code == 200 and "outcome" in actual
                            measurement_stage = "active_dispatch" if measured else None
                            observed = actual
                            # A failed shadow suite prevents activation but still contains
                            # real evaluation results from the authenticated tests endpoint.
                            if not measured:
                                check = next((check for check in install["checks"]
                                              if check.get("name") == case["id"] and "actual" in check), None)
                                if check:
                                    observed = check["actual"]
                                    measured = True
                                    measurement_stage = "shadow_suite"
                            matched = measured and observed["outcome"] == want["outcome"] and observed.get("amount") == want.get("amount")
                            evaluations.append({"id": case["id"], "http_status": response.status_code,
                                                "measured": measured, "matched": bool(matched), "expected": want,
                                                "measurement_stage": measurement_stage,
                                                "actual": {k: observed.get(k) for k in ("outcome", "amount", "detail", "id")},
                                                "dispatch_refusal": actual.get("detail")})
                            if measurement_stage == "active_dispatch" and actual.get("id"):
                                receipt = client.get("/api/cases/" + actual["id"], headers=reviewer.headers)
                                found = journal.record("workbench-case-readback", receipt)
                                if receipt.status_code == 200 and found.get("id") == actual["id"]:
                                    workbench_ids.add(actual["id"])
                    case = next(c for c in cases if c["id"] == denial["case_id"])
                    reviewer.maximum_amount_cents = int(Decimal(gold[case["id"]]["credit_usd"] or "0") * 100)
                    denial_results.append(correspondence_probe(client, reviewer, app, config, senders, case, denial,
                                                              denial_gold[denial["id"]], base, overlay, journal, clock))
            finally:
                if listener:
                    listener.close()
    except Exception as exc:
        # Exception text may contain private validation data; keep it only in local artifacts.
        fatal = type(exc).__name__
        save(output / "failure.json", {"type": fatal, "detail": str(exc)})
    finally:
        save(output / "http-journal.json", journal.rows)
    summary = summarize(evaluations, denial_results, protocol, active=active, workbench=len(workbench_ids), fatal=fatal)
    result = {"evaluation_id": manifest["evaluation_id"], "attempt": output.name,
              "label": args.label, "classification": "IN_FAMILY_COMPARATOR_ONLY",
              "transport": args.transport, "real_socket": args.transport == "socket", "human_approval": False,
              "reviewer_kind": "SCRIPTED_TEST", "clock": "Explicit synthetic correspondence replay clock; real authentication clock",
              "source_authority": "Four separate Ed25519 source keys; independent of application and reviewer",
              "public_sha256": manifest["public_sha256"], "frozen_manifest_sha256": args.freeze_sha256,
              "external_calls": 0, "application_edits": False, "onboarding": onboarding,
              "evaluations": evaluations, "denials": denial_results, "summary": summary}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-dir", required=True, type=Path)
    parser.add_argument("--freeze-sha256", required=True)
    parser.add_argument("--vendor", required=True, help="New fictitious vendor from the frozen public agreement")
    parser.add_argument("--document-name", required=True)
    parser.add_argument("--extractions-dir", type=Path, help="Root-approved public-only receipts; never invoke a model")
    parser.add_argument("--transport", choices=("testclient", "socket"), default="testclient")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    base = args.freeze_dir.resolve()
    if base.is_relative_to(ROOT):
        raise ValueError("Private freeze must be outside the repository")
    manifest = verify_freeze(base, args.freeze_sha256)
    attempts = base / "runs"
    for number in range(1, 10000):
        output = attempts / f"attempt-{number:03d}"
        try:
            output.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise ValueError("Attempt directory budget exhausted")
    # Only an explicitly selected operator directory can affect this attempt.
    os.environ.pop("UPTIME_PUBLIC_EXTRACTIONS", None)
    os.environ.pop("UPTIME_MODEL_PROPOSITIONS", None)
    if args.extractions_dir:
        os.environ["UPTIME_PUBLIC_EXTRACTIONS"] = str(args.extractions_dir.resolve())
        os.environ["UPTIME_MODEL_PROPOSITIONS"] = "1"
    save(output / "start.json", {"at": datetime.now(timezone.utc).isoformat(),
                                 "code_sha256": digest(Path(__file__).read_bytes()),
                                 "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                                 "transport": args.transport, "label": args.label,
                                 "extractions_directory": str(args.extractions_dir) if args.extractions_dir else None})
    (output / "driver-snapshot.py").write_bytes(Path(__file__).read_bytes())
    result = run(args, base, output, manifest)
    verify_freeze(base, args.freeze_sha256)
    save(output / "result.json", result)
    # No raw customer data, denials, oracle rows, keys or request bodies on stdout.
    print(json.dumps({"attempt": output.name, "result_path": str(output / "result.json"), **result["summary"]}))
    return 0 if result["summary"]["all_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
