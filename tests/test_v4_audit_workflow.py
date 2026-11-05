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


from test_v4_audit_protocol import bootstrap, is_v4, SignedClient, ORIGIN, SUBJECT, scoped_dossier


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
    with workspace() as (u, _, app, _):
        # The exclusion is known only after its recorded availability. Freeze a
        # later synthetic decision time; do not move or rewrite source evidence.
        app.state.bench.desk.clock = lambda: datetime(2026, 11, 3, 12, tzinfo=UTC)
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


@contextmanager
def provision_dossiers(dossiers):
    from uptime import disputes
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root/'claimant').mkdir()
        (root/'claimant/dossiers.json').write_text(json.dumps(dossiers))
        with patch.object(disputes, 'FIXTURES', root):
            yield


def duplicate_and_privacy():
    from uptime import disputes, disputes_vendor
    original_dossiers = json.loads((Path(disputes.FIXTURES)/'claimant/dossiers.json').read_text())
    rows = []
    duplicate = deepcopy(original_dossiers)
    duplicate['dispute-clone'] = deepcopy(duplicate['dispute-partial'])
    # Both aliases are legitimate initial intake, not post-seed SQL tampering.
    with provision_dossiers(duplicate), workspace() as (u, _, _, _):
        receipts = []
        for key in ('dispute-partial', 'dispute-clone'):
            response = post(u, key, 'approve-claim')
            if response.status_code == 200:
                response = post(u, key, 'submit-claim')
            if response.status_code not in (200, 409):
                raise RuntimeError('UnexpectedDuplicateDispatchResponse')
            state = successful(u.get('/api/cases/' + key))
            if state['id'] != key:
                raise RuntimeError('DuplicateCaseIdentityChanged')
            receipts.extend(state['submissions'])
        rows.append(observation('W-business-claim-idempotency', len(receipts), 1))
    sentinel = 'SYNTHETIC-PRIVATE-AUDIT-NOTE'
    annotated = deepcopy(original_dossiers)
    dossier = annotated['dispute-cure']
    dossier['initial_documents'][0]['private_internal_annotation'] = sentinel
    scoped_dossier(dossier)
    with provision_dossiers(annotated), workspace() as (u, _, _, _):
        seen = []
        original = disputes_vendor.review
        def inspect(ticket, clock):
            seen.append(sentinel in json.dumps([d.body for d in ticket.documents]))
            return original(ticket, clock)
        with patch('uptime.disputes.vendor.review', side_effect=inspect):
            successful(post(u, 'dispute-cure', 'approve-claim'))
            successful(post(u, 'dispute-cure', 'submit-claim'))
        if not seen:
            raise RuntimeError('OutboundPositiveControlNotExecuted')
        rows.append(observation('W-outbound-allowlist', any(seen), False))
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
        if is_v4():
            from uptime.server import create_app
            blocked = False
            try:
                create_app(db, mode="sandbox", approvals_enabled=True, origin=ORIGIN)
            except ValueError:
                blocked = True
            target = db.with_name('other-mode.sqlite')
            fresh, fresh_viewer, new_app = bootstrap(target, "sandbox", False)
            try:
                old_request = u.prepare('/api/cases/dispute-review/actions/approve-claim', {})
                replay = fresh.raw.post('/api/cases/dispute-review/actions/approve-claim', **old_request)
                fresh_policy = successful(fresh.get('/api/policy'))
                return [observation('W-viewer-boundary', viewer_status, 403, 'control'),
                        observation('W-mode-session-isolation', replay.status_code in (401,403), True),
                        observation('W-mode-policy-isolation', blocked and fresh_policy['mode'] in fresh_policy['available_modes'], True)]
            finally:
                fresh.close()
                fresh_viewer.close()
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
                wire_fields = {'ref', 'kind', 'account', 'month', 'product', 'region', 'source',
                               'start', 'end', 'origin', 'classification', 'component_id', 'observed_at'}
                public_body = {k:v for k,v in doc.items() if k in wire_fields} if is_v4() else doc
                provider['document_registry'][doc['ref']] = fingerprint(public_body)
        dossier = scoped_dossier(dossier)
        if is_v4():
            provider.update(account=dossier['account'], invoice_id=dossier['invoice_id'])
            provider['lines'] = [dict(id='invoice-'+kind, kind='affected_api', usd='417.30',
                account=dossier['account'], month='2026-10', product='Twilio Messaging API',
                region='US1', currency='USD', invoice_id=dossier['invoice_id'],
                evidence_ref=dossier['invoice_id']+'/invoice-'+kind)]
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
    try:
        wrong = review(ticket_for("other-tenant", dossier, dossier["supplemental_archive"]), START)
        wrong_award = wrong.code in ("AWARD", "PARTIAL_AWARD")
    except (PermissionError, ValueError):
        wrong_award = False
    return [observation("W-tenant-account-positive", [right.code, right.awarded], ["AWARD", "100.00"], "control"),
            observation("W-tenant-account-binding", wrong_award, False)]


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
    if is_v4():
        from test_v4_audit_vendor import mounted_activation
        return mounted_activation()
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
        }, {"preactivation_refused": True, "active_amount": "120.00", "same_case_in_dashboard": True,
             "rollback_refused": True, "history_preserved": True, "same_reviewer": True}, "defect")]


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


def named_authority():
    positive_expected = dict(named=True, role='reviewer', approvals=True, rehearsal=False,
                             accepted=200, stage='CLAIM_APPROVED', readback_same=True)
    refusal_expected = dict(wrong_signer=403, old_subject=403, disabled_gate=403,
                            all_unchanged=True)
    if not is_v4():
        return [observation('W-named-authority-positive', {'named_protocol_present': False}, positive_expected, 'control'),
                observation('W-named-authority-refusals', {'named_protocol_present': False}, refusal_expected)]
    from test_v4_audit_protocol import generate_key, sign
    from fastapi.testclient import TestClient
    from uptime.server import create_app
    with workspace() as (u, _, app, db):
        case = 'dispute-partial'
        path = '/api/cases/'+case+'/actions/approve-claim'
        before = successful(u.get('/api/cases/'+case))
        request = u.prepare(path, {})
        # Sign the right challenge with a different P-256 key, retaining the valid read identity.
        import hashlib
        challenge = successful(u.raw.post('/api/auth/challenge', headers=u.headers,
            json={'subject': u.subject, 'path': path, 'body_sha256': hashlib.sha256(b'{}').hexdigest()}))
        bad = u.raw.post(path, content=b'{}', headers={**u.headers, 'X-Uptime-Challenge': challenge['challenge'],
                        'X-Uptime-Proof': sign(generate_key(), challenge['message'])})
        bad_state = successful(u.get('/api/cases/'+case))
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE authority_user SET role='viewer' WHERE subject=?", (u.subject,))
        old = u.raw.post(path, **request)
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE authority_user SET role='reviewer' WHERE subject=?", (u.subject,))
        old_state = successful(u.get('/api/cases/'+case))
        disabled_app = create_app(db, approvals_enabled=False, origin=ORIGIN)
        raw = TestClient(disabled_app, base_url=ORIGIN, client=('127.0.0.1', 55124), raise_server_exceptions=False)
        disabled = SignedClient(raw, u.subject, u.key)
        try:
            denied = disabled.post(path, json={})
            gate_state = successful(disabled.get('/api/cases/'+case))
        finally:
            disabled.close()
        response = u.post(path, json={})
        after = successful(u.get('/api/cases/'+case))
        returned = response.json() if response.status_code == 200 else {}
        return [observation('W-named-authority-positive', dict(named=u.identity['subject']==SUBJECT,
                    role=u.identity['role'], approvals=u.identity['approvals_enabled'], rehearsal=u.identity['rehearsal'],
                    accepted=response.status_code, stage=after['stage'],
                    readback_same=returned.get('id')==after['id']==case and returned.get('stage')==after['stage']), positive_expected, 'control'),
                observation('W-named-authority-refusals', dict(wrong_signer=bad.status_code, old_subject=old.status_code,
                    disabled_gate=denied.status_code, all_unchanged=all(x['stage']==before['stage'] and x['submissions']==before['submissions']
                        for x in (bad_state, old_state, gate_state))), refusal_expected)]
