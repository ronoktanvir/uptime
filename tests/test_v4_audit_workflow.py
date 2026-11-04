"""Independent, synthetic mutations derived from the V3 audit, not the release oracle.

These callables return narrowly selected observations. No arbitrary HTTP body,
credential, cookie, provider record or exception message belongs in a gate report.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
from unittest.mock import patch


HEADERS = {"X-Uptime-Action": "1", "Origin": "http://testserver"}


def observation(ident, observed, expected, category="defect"):
    return dict(id=ident, observed=observed, expected=expected,
                matches=observed == expected, category=category)


def bootstrap(db, mode="replay", rehearsal=True):
    from fastapi.testclient import TestClient
    from uptime.server import create_app, viewer_token
    secret = secrets.token_urlsafe(32)
    app = create_app(db, session_secret=secret, mode=mode, rehearsal=rehearsal)
    user = TestClient(app, raise_server_exceptions=False)
    viewer = TestClient(app, raise_server_exceptions=False)
    user.get("/session/" + secret)
    viewer.get("/session/" + viewer_token(secret))
    if user.get("/api/policy").status_code != 200:
        raise RuntimeError("Auth interface requires reviewed adapter")
    return user, viewer, app


@contextmanager
def workspace(mode="replay", rehearsal=True):
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "audit.sqlite"
        user, viewer, app = bootstrap(db, mode, rehearsal)
        try:
            yield user, viewer, app, db
        finally:
            user.close()
            viewer.close()


def post(client, case, action):
    return client.post(f"/api/cases/{case}/actions/{action}", json={}, headers=HEADERS)


def successful(response):
    if response.status_code != 200:
        raise RuntimeError("Positive workflow setup rejected")
    return response.json()


def lab_action(client, lab, operation):
    # Action values are read-only handles, not outcome oracles.
    action = next(a["id"] for a in lab["actions"] if a["id"].startswith(operation + "~"))
    return action, successful(client.post("/api/onboarding/actions/" + action,
                                        json={}, headers=HEADERS))


def stock_denial():
    with workspace() as (u, _, _, _):
        initial = successful(u.get("/api/cases/dispute-denial"))
        response = post(u, "dispute-denial", "approve-claim")
        after = successful(u.get("/api/cases/dispute-denial"))
        return [observation("W-known-exclusion-before-filing", {
            "outcome": initial["outcome"],
            "approval_offered": any(a["id"] == "approve-claim" for a in initial["actions"]),
            "approval_denied": response.status_code in (403, 409),
            "receipts": len(after["submissions"]),
        }, {"outcome": "INELIGIBLE", "approval_offered": False,
            "approval_denied": True, "receipts": 0})]


def complete_policy():
    with workspace() as (u, _, _, _):
        successful(u.post("/api/policy", json={"mode": "POLICY_AUTOMATED", "cap": "100.00"}, headers=HEADERS))
        after = successful(post(u, "dispute-cure", "approve-claim"))
        return [observation("W-complete-policy-packet", {
            "missing_component_reply": any(r["code"] == "DOCUMENTATION_NEEDED" for r in after["replies"]),
            "policy_claims_complete": "complete" in successful(u.get("/api/policy"))["scope"].lower(),
        }, {"missing_component_reply": False, "policy_claims_complete": True})]


def denial_responses():
    from uptime.disputes_wire import Reply
    rows = []
    for code in ("WINDOW_CLOSED", "FREEFORM_MISSING_DOC"):
        with workspace() as (u, _, _, _):
            successful(post(u, "dispute-review", "approve-claim"))
            with patch("uptime.disputes.vendor.review", return_value=Reply(code, "Independent synthetic reply", "§3")):
                after = successful(post(u, "dispute-review", "submit-claim"))
            rows.append(observation("W-reply-" + code, {
                "stage": after["stage"], "awarded": after["ledger"]["awarded"],
                "has_receipt": bool(after["submissions"]),
            }, {"stage": "HUMAN_REVIEW", "awarded": "0.00", "has_receipt": True},
                "defect" if code == "WINDOW_CLOSED" else "control"))
    return rows


def duplicate_and_privacy():
    from uptime import disputes_vendor
    rows = []
    with workspace() as (u, _, _, db):
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO dispute_cases SELECT tenant,'dispute-clone',dossier,state FROM dispute_cases WHERE id='dispute-partial'")
        receipts = []
        for key in ("dispute-partial", "dispute-clone"):
            response = post(u, key, "approve-claim")
            if response.status_code == 200:
                response = post(u, key, "submit-claim")
            if response.status_code not in (200, 409):
                raise RuntimeError("Unexpected duplicate dispatch response")
            state = successful(u.get("/api/cases/" + key))
            receipts.extend(state["submissions"])
        rows.append(observation("W-business-claim-idempotency", len(receipts), 1))
    with workspace() as (u, _, _, db):
        sentinel = "SYNTHETIC-PRIVATE-AUDIT-NOTE"
        with sqlite3.connect(db) as conn:
            dossier = json.loads(conn.execute("SELECT dossier FROM dispute_cases WHERE id='dispute-cure'").fetchone()[0])
            dossier["initial_documents"][0]["private_internal_annotation"] = sentinel
            conn.execute("UPDATE dispute_cases SET dossier=? WHERE id='dispute-cure'", (json.dumps(dossier),))
        seen = []
        original = disputes_vendor.review
        def inspect(ticket, clock):
            seen.append(sentinel in json.dumps([d.body for d in ticket.documents]))
            return original(ticket, clock)
        with patch("uptime.disputes.vendor.review", side_effect=inspect):
            approval = post(u, "dispute-cure", "approve-claim")
            if approval.status_code == 200:
                submitted = post(u, "dispute-cure", "submit-claim")
                if submitted.status_code not in (200, 409):
                    raise RuntimeError("Unexpected minimized dispatch response")
            elif approval.status_code != 409:
                raise RuntimeError("Unexpected privacy approval response")
        rows.append(observation("W-outbound-allowlist", any(seen), False))
    return rows


def lifecycle():
    from uptime import onboarding
    original = onboarding.fixture
    with workspace() as (u, _, _, _):
        initial = successful(u.get("/api/onboarding"))
        approve, approved = lab_action(u, initial, "approve")
        activate, active = lab_action(u, approved, "activate")
        lab_action(u, active, "rollback")
        changed = deepcopy(original("extraction"))
        changed["sources"]["legal"]["text_sha256"] = "0" * 64
        with patch.object(onboarding, "fixture", lambda n: deepcopy(changed) if n == "extraction" else original(n)):
            successful(u.get("/api/onboarding"))
            b_rejects = u.post("/api/onboarding/actions/" + approve, json={}, headers=HEADERS).status_code
        successful(u.get("/api/onboarding"))
        a_approve = u.post("/api/onboarding/actions/" + approve, json={}, headers=HEADERS).status_code
        a_activate = u.post("/api/onboarding/actions/" + activate, json={}, headers=HEADERS).status_code
        return [observation("W-lifecycle-ABA", [b_rejects, a_approve, a_activate], [409, 409, 409])]


def malformed_source():
    from uptime import onboarding
    original = onboarding.fixture
    with workspace() as (u, _, _, _):
        _, approved = lab_action(u, successful(u.get("/api/onboarding")), "approve")
        _, active = lab_action(u, approved, "activate")
        before = len(active["audit"])
        def malformed(name):
            return json.loads('{"rules":') if name == "extraction" else original(name)
        with patch.object(onboarding, "fixture", malformed):
            response = u.get("/api/onboarding")
        restored = successful(u.get("/api/onboarding"))
        return [observation("W-malformed-source-quarantine", {
            "request_rejected_or_quarantined": response.status_code in (200, 409),
            "silently_active": restored["state"] == "ACTIVE",
            "audit_added": len(restored["audit"]) > before,
        }, {"request_rejected_or_quarantined": True, "silently_active": False, "audit_added": True})]


def session_isolation():
    from fastapi.testclient import TestClient
    with workspace() as (u, viewer, _, db):
        viewer_status = post(viewer, "dispute-cure", "approve-claim").status_code
        old_cookies = dict(u.cookies)
        successful(u.post("/api/policy", json={"mode": "POLICY_AUTOMATED", "cap": "100.00"}, headers=HEADERS))
        fresh, _, app = bootstrap(db, "sandbox", False)
        old = TestClient(app, raise_server_exceptions=False)
        old.cookies.update(old_cookies)
        response = post(old, "dispute-review", "approve-claim")
        fresh_policy = successful(fresh.get("/api/policy"))
        return [observation("W-viewer-boundary", viewer_status, 403, "control"),
                observation("W-mode-session-isolation", response.status_code in (401, 403), True),
                observation("W-mode-policy-isolation", fresh_policy["mode"] in fresh_policy["available_modes"], True)]


def novel_evidence():
    from uptime import disputes, disputes_vendor
    from uptime.contracts import fingerprint
    root = Path(disputes.FIXTURES)
    dossiers = json.loads((root / "claimant/dossiers.json").read_text())
    records = json.loads((root / "simulator/records.json").read_text())
    mutated = {}
    for kind in ("positive", "missing-component", "wrong-line-scope"):
        key = "dispute-audit-" + kind
        dossier = deepcopy(dossiers["dispute-cure"])
        dossier.update(title="Synthetic audit " + kind, account="audit-" + kind,
                       start="2026-10-22T01:21:00+00:00", end="2026-10-22T01:47:00+00:00")
        line = dict(id="invoice-" + kind, kind="affected_api", usd="417.30")
        if kind == "wrong-line-scope":
            line.update(month="2024-08", account="unrelated-customer", region="other", currency="CAD")
        dossier["invoice_lines"] = [line]
        provider = deepcopy(records["sim-acct-101"])
        provider.update(start=dossier["start"], end=dossier["end"],
                        lines=[dict(kind="affected_api", usd="417.30")], document_registry={})
        for group in ("initial_documents", "supplemental_archive"):
            for doc in dossier[group]:
                doc.update(ref=kind + "-" + doc["kind"], account=dossier["account"],
                           start=dossier["start"], end=dossier["end"])
                if kind == "missing-component" and doc["kind"] == "component_record":
                    doc.pop("component_id", None)
                provider["document_registry"][doc["ref"]] = fingerprint(doc)
        dossiers[key] = dossier
        records[dossier["account"]] = provider
        mutated[kind] = key
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for directory, name, data in (("claimant", "dossiers", dossiers), ("simulator", "records", records)):
            (root / directory).mkdir()
            (root / directory / (name + ".json")).write_text(json.dumps(data))
        rows = []
        with patch.object(disputes, "FIXTURES", root), patch.object(disputes_vendor, "FIXTURES", root):
            with workspace() as (u, _, _, _):
                for kind, key in mutated.items():
                    for action in ("approve-claim", "submit-claim", "prepare-response", "approve-response", "advance-cooldown", "submit-response"):
                        current = successful(u.get("/api/cases/" + key))
                        if not any(a["id"] == action for a in current["actions"]):
                            break
                        response = post(u, key, action)
                        if response.status_code != 200:
                            if kind == "positive" or response.status_code != 409:
                                raise RuntimeError("Novel fixture interface rejected")
                            break
                    after = successful(u.get("/api/cases/" + key))
                    if kind == "positive":
                        rows.append(observation("W-novel-positive", after["ledger"]["awarded"], "41.73", "control"))
                    elif kind == "wrong-line-scope":
                        rows.append(observation("W-novel-wrong-line-scope", {
                            "receipts": len(after["submissions"]), "awarded": after["ledger"]["awarded"],
                            "eligible": after["preflight"]["outcome"] == "ELIGIBLE",
                        }, {"receipts": 0, "awarded": "0.00", "eligible": False}))
                    else:
                        rows.append(observation("W-novel-missing-component", after["ledger"]["awarded"], "0.00"))
        return rows


def tenant_account():
    from uptime.disputes import START
    from uptime.disputes_wire import FIXTURES
    from uptime.disputes_claimant import ticket_for
    from uptime.disputes_vendor import review
    dossier = json.loads((FIXTURES / "claimant/dossiers.json").read_text())["dispute-cure"]
    right = review(ticket_for("bears", dossier, dossier["supplemental_archive"]), START)
    wrong = review(ticket_for("other-tenant", dossier, dossier["supplemental_archive"]), START)
    return [observation("W-tenant-account-positive", [right.code, right.awarded], ["AWARD", "100.00"], "control"),
            observation("W-tenant-account-binding", wrong.code in ("AWARD", "PARTIAL_AWARD"), False)]


def comparative_api():
    from uptime.contracts import Principal
    from uptime.storage import save_cases
    from uptime.intelligence import explain
    rows = []
    with workspace() as (u, _, app, db):
        principal = Principal("bears", "synthetic-reviewer", "reviewer")
        before = successful(u.get("/api/dashboard"))["metrics"][0]
        paid = app.state.bench.case(principal, "price-paid-retrospective")
        paid.update(id="price-000-audit", title="Premium support retrospective correction", amount="9123.45")
        save_cases(db, "bears", [paid])
        after = successful(u.get("/api/dashboard"))["metrics"][0]
        rows.append(observation("A-prevention-paid-title", [after["case_id"], after["value"]],
                                [before["case_id"], before["value"]]))
        newer = dict(paid, amount="17.00")
        rejected = False
        try:
            save_cases(db, "bears", [newer])
        except ValueError:
            rejected = True
        stored = app.state.bench.case(principal, paid["id"])
        rows.append(observation("A-case-revision-not-silent", rejected or stored["amount"] == "17.00" or
                                bool(stored.get("superseded_by")), True))
        known = app.state.bench.case(principal, "sla-eligible")
        rows.append(observation("A-billing-profile-intent", explain(known, "Show my billing profile.")["intent"] in ("next", "next_action"), False))
        import uptime
        source = Path(uptime.__file__).resolve().parents[1] / "web/app.js"
        # The configured UI/API limit is compared dynamically, not frozen to 1000/2000.
        import re
        match = re.search(r"maxLength\s*=\s*(\d+)|maxlength=[\"'](\d+)", source.read_text(), re.I)
        if match is None:
            raise RuntimeError("UI guide limit extraction requires adapter")
        limit = int(next(g for g in match.groups() if g is not None))
        response = u.post("/api/guide", json={"case_id": "sla-eligible", "question": "q" * limit}, headers=HEADERS)
        rows.append(observation("A-guide-ui-api-limit", response.status_code, 200))
    return rows


def captured_line_api():
    with workspace("sandbox", False) as (u, _, app, _):
        row = dict(id="synthetic-bill", status="OPEN", approval_status="PENDING",
                   amount={"amount": "37500.00", "currency": "USD"},
                   lines=[dict(id="synthetic-line", amount={"amount": "37500.00", "currency": "USD"},
                               quantity="1000", unit_price={"amount": "37.50", "currency": "USD"},
                               service_date="2026-10-01", sku="synthetic-example")])
        data = dict(sources=["LIVE_RAMP_SANDBOX", "DETERMINISTIC_REPLAY"], bills=[row],
                    observed_at="2026-10-31T12:00:00+00:00")
        with patch.object(app.state.bench, "ramp", return_value=data):
            case = successful(u.get("/api/cases/ramp-synthetic-bill"))
            missing_units = any("missing:" in text.lower() and "units and unit price" in text.lower() for text in case["trace"])
            row["status"] = None
            malformed = u.get("/api/dashboard")
        return [observation("A-provider-line-preserves-known-facts", missing_units, False),
                observation("A-null-bill-status-resilience", malformed.status_code in (200, 409, 422), True)]


def activation_runtime():
    with workspace() as (u, _, _, _):
        before = successful(u.get("/api/dashboard"))["cases"]
        _, approved = lab_action(u, successful(u.get("/api/onboarding")), "approve")
        _, active = lab_action(u, approved, "activate")
        current = successful(u.get("/api/dashboard"))["cases"]
        lab_action(u, active, "rollback")
        after = successful(u.get("/api/dashboard"))["cases"]
        def jira_ids(cases):
            return sorted(c["id"] for c in cases if "atlassian" in c["vendor"].lower() or "jira" in c["id"].lower())
        return [observation("W-activation-runtime", {
            "adds_governed_case": bool(set(jira_ids(current)) - set(jira_ids(before))),
            "rollback_removes_active_case": not (set(jira_ids(current)) - set(jira_ids(after))) == set(),
        }, {"adds_governed_case": True, "rollback_removes_active_case": True}, "v3-known-limit")]


def additional_domain():
    from dataclasses import replace
    from uptime.pricing_demo import load_agreement, load_demo_inputs
    from uptime.pricing import evaluate_price
    from uptime import onboarding_rules as jira
    from uptime.contracts import Principal
    agreement = load_agreement()
    invoice = load_demo_inputs()[0][1]
    covered = invoice.lines[0]
    outside = replace(invoice.lines[1], start=datetime(2025, 1, 1, tzinfo=UTC),
                      end=datetime(2025, 2, 1, tzinfo=UTC))
    positive = evaluate_price(agreement, replace(invoice, lines=(covered,), total=covered.net + covered.tax))
    mixed = evaluate_price(agreement, replace(invoice, lines=(covered, outside)))
    template = jira.compile_template(jira.fixture("extraction"))
    overlay = jira.fixture("overlay")
    zero = jira.evaluate(template, Principal(overlay["tenant"], "synthetic", "viewer"),
                         overlay, dict(jira.fixture("observations"), monthly_fee="0.00"))
    return [observation("P-covered-line-positive", str(positive.overcharge), "7500.00", "control"),
            observation("P-unrelated-outside-line", str(mixed.overcharge), "7500.00"),
            observation("J-zero-fee-not-claimable", zero.outcome.value == "ELIGIBLE", False)]


def capture_integrity():
    from uptime import ramp
    # Construct a synthetic capture; never read the actual saved provider capture.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        record = dict(mode="saved sandbox observation", sources=["LIVE_RAMP_SANDBOX"],
                      origin="https://demo-api.ramp.com", observed_at="2026-10-31T12:00:00+00:00",
                      bills=[dict(id="synthetic-tamper", amount={"amount": "999.00", "currency": "USD"})],
                      credits=[], vendor_ids=[], capabilities={})
        (root / "verified.json").write_text(json.dumps(record))
        rejected = False
        with patch.object(ramp, "FIXTURES", root):
            try:
                result = ramp.ramp_snapshot()
            except ValueError:
                rejected = True
                result = {}
        return [observation("A-unattested-capture-provenance", rejected or
                            "LIVE_RAMP_SANDBOX" not in result.get("sources", []), True)]
