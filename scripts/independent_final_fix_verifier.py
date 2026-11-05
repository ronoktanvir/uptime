"""Post-fix assertions for four independent review findings, on disposable state.

PASS means the correction and its stated controls passed. The original defect
reproducer is imported only for synthetic setup helpers and is never edited.
No provider/model process, network, installed database, or private corpus is used.
"""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PIN = "14c343d4f215388eac88e4c5cc7bc4d16917341e"
ORIGINALS = {
    "scripts/independent_final_review_probes.py": "16f071557f95b9fd93c850a123e51a497d53a4aa1ba772923ad6363aaec3b202",
    "docs/v4/INDEPENDENT-FINAL-REVIEW.md": "9633e9089125d051ad1bfc6a20e9287efe1dab80d76443a4c972b07f6adedf6f",
}

# Obtain source metadata before prohibiting subprocesses (including model CLIs).
SOURCE_HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
SOURCE_TREE = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()


def no_process(*args, **kwargs):
    raise RuntimeError("Independent fix verification prohibits child processes")


subprocess.Popen = no_process

# This module clears inherited UPTIME/RAMP configuration, rejects socket and DNS
# access, disables packaged native captures, and imports only synthetic fixtures.
import independent_final_review_probes as setup
from uptime import claim_identity
from uptime.contracts import fingerprint
from uptime.ramp_award_attribution import AttributionError, canonical_json
from uptime.storage import database


def preserved_originals():
    actual = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in ORIGINALS}
    assert actual == ORIGINALS, ("Original review artifacts changed", actual)
    return actual


def replace(value, substitutions):
    if isinstance(value, dict):
        return {k: replace(v, substitutions) for k, v in value.items()}
    if isinstance(value, list):
        return [replace(v, substitutions) for v in value]
    return substitutions.get(value, value) if isinstance(value, str) else value


def fresh_scope(resource=None, region="west"):
    nonce = uuid4().hex[:12]
    return setup.scope(resource=resource or "station-" + nonce, region=region) | {
        "account": "synthetic-fix-" + nonce,
        "invoice": "synthetic-invoice-" + nonce,
        "incident": "synthetic-incident-" + nonce,
    }


def install(env, folder, slot, sc, *, cents=10004, expected="12.51", extra_terms=()):
    overlay, facts = setup.resource_inputs(sc["component"])
    substitutions = {setup.OVERLAY["account"]: sc["account"]}
    overlay, facts = replace(overlay, substitutions), replace(facts, substitutions)
    for row in facts["fee_lines"]:
        if row["kind"] == "resource_service" and row["resource_id"] == sc["component"]:
            row["amount_cents"] = cents
    return setup.install_resource(env, folder, slot, resource=sc["component"], extra_terms=extra_terms,
        overlay_override=overlay, facts_override=facts, expected=expected)


def metric(env, key="estimated"):
    return next(m for m in env.get("/api/dashboard")["cohorts"]["portfolio"]["metrics"] if m["key"] == key)


def verify_resources(folder):
    observations = []
    for label, second_cents, second_amount, total in (
        ("equal", 10004, "12.51", "25.02"),
        ("unequal", 20008, "25.01", "37.52"),
    ):
        env = setup.App(folder / (label + ".sqlite"))
        try:
            first = fresh_scope()
            scopes = [first, first | {"component": first["component"] + "-second"}]
            estimates = []
            for index, sc in enumerate(scopes):
                _, facts = install(env, folder, label + str(index), sc,
                    cents=10004 if index == 0 else second_cents,
                    expected="12.51" if index == 0 else second_amount)
                estimates.append(env.post(f"/api/vendors/{label}{index}/evaluate", {"facts": facts}))
            result = metric(env)
            assert [r["amount"] for r in estimates] == ["12.51", second_amount]
            assert len({r["id"] for r in estimates}) == len({r["obligation_id"] for r in estimates}) == 2
            assert result["amount"] == total, result
            assert sum(Decimal(c["amount"]) for c in result["contributions"]) == Decimal(total)
            # Evaluation, intake and filed views must identify one entitlement.
            if label == "equal":
                for index, sc in enumerate(scopes):
                    claim = "inbox-" + sc["component"]
                    env.provision(sc)
                    env.post("/api/correspondence/claims", {"claim_id": claim, "scope": sc})
                    setup.deliver_resource(env, claim, sc)
                    url = "/api/correspondence/claims/" + claim
                    assert env.get(url)["obligation_id"] == estimates[index]["obligation_id"]
                    assert metric(env)["amount"] == total
                    env.post(url + "/actions/approve-claim", {})
                    submitted = env.post(url + "/actions/submit-claim", {})
                    assert submitted["obligation_id"] == estimates[index]["obligation_id"]
                assert metric(env)["amount"] == metric(env, "claimed")["amount"] == total
                assert len(metric(env)["contributions"]) == 4
                assert metric(env, "awarded")["amount"] == "0.00"
            observations.append({"case": label, "credits": [r["amount"] for r in estimates],
                "distinct_obligations": 2, "portfolio_estimated": metric(env)["amount"],
                "portfolio_claimed": metric(env, "claimed")["amount"],
                "estimate_contributions": len(metric(env)["contributions"])})
        finally:
            env.close()
    # Independent alias controls catch an overbroad 'just sum every case' repair.
    for label, cents, amount, expected in (("equal_alias", 10004, "12.51", "12.51"),
                                           ("conflicting_alias", 20008, "25.01", None)):
        env = setup.App(folder / (label + ".sqlite"))
        try:
            sc = fresh_scope()
            estimates = []
            for slot, fee, credit in (("original", 10004, "12.51"), ("alias", cents, amount)):
                _, facts = install(env, folder, slot, sc, cents=fee, expected=credit)
                estimates.append(env.post(f"/api/vendors/{slot}/evaluate", {"facts": facts}))
            assert estimates[0]["obligation_id"] == estimates[1]["obligation_id"]
            result = metric(env)
            assert result["amount"] == expected and len(result["contributions"]) == 2, result
            if expected is None:
                assert result["value"] == "Not additive"
            observations.append({"case": label, "distinct_obligations": 1,
                "portfolio_estimated": result["amount"], "display": result["value"]})
        finally:
            env.close()
    return observations


def verify_regions(folder):
    from test_vendor_resource_scoped import ROW, subscription, facts as regional_facts
    env = setup.App(folder / "regions.sqlite")
    observations = []
    try:
        base = fresh_scope()
        for region in ("North", "South"):
            sc = base | {"region": region}
            substitutions = {setup.OVERLAY["account"]: sc["account"],
                setup.OVERLAY["resource_id"]: sc["component"], "North": region}
            overlay = replace(subscription(), substitutions)
            facts = replace(regional_facts(), substitutions)
            slot = "region-" + region.lower()
            setup.install_resource(env, folder, slot, extra_terms=ROW,
                overlay_override=overlay, facts_override=facts, expected="15.03")
            estimate = env.post(f"/api/vendors/{slot}/evaluate", {"facts": facts})
            assert estimate["amount"] == "15.03"
            env.provision(sc)
            claim = "inbox-" + sc["component"] + "-" + region.lower()
            created = env.post("/api/correspondence/claims", {"claim_id": claim, "scope": sc})
            assert created["obligation_id"] == estimate["obligation_id"]
            repeat = env.post("/api/correspondence/claims", {"claim_id": claim, "scope": sc})
            assert repeat["state_sha256"] == created["state_sha256"]
            duplicate = env.reviewer.post("/api/correspondence/claims", {"claim_id": claim + "-alias", "scope": sc})
            assert duplicate.status_code == 409, duplicate.text
            observations.append({"region": region, "estimate": estimate["amount"], "intake_http": 200,
                "same_scope_alias_http": duplicate.status_code, "obligation_id": created["obligation_id"]})
        assert observations[0]["obligation_id"] != observations[1]["obligation_id"]
        assert metric(env)["amount"] == "30.06"
    finally:
        env.close()
    # With nonregional terms a region name cannot manufacture another claim.
    env = setup.App(folder / "nonregional.sqlite")
    try:
        sc = fresh_scope(region="North")
        install(env, folder, "whole-resource", sc)
        for region in ("North", "South"):
            env.provision(sc | {"region": region})
        env.post("/api/correspondence/claims", {"claim_id": "inbox-north", "scope": sc})
        duplicate = env.reviewer.post("/api/correspondence/claims", {
            "claim_id": "inbox-south", "scope": sc | {"region": "South"}})
        assert duplicate.status_code == 409, duplicate.text
    finally:
        env.close()
    return {"independent_regions": observations, "portfolio_estimated": "30.06", "nonregional_alias_http": 409}


def verify_denials(folder):
    factual = "We denied your claim because we measured 5 minutes of downtime."
    cases = [
        ("factual", factual, "RESPONSE_DRAFTED"),
        ("closing", factual + " Thank you for your patience. Best regards.", "RESPONSE_DRAFTED"),
        ("waiver", factual + " You waived all service credit claims in a separate settlement agreement.", "HUMAN_REVIEW"),
        ("unknown_condition", factual + " A separate licensing covenant suspends your entitlement pending arbitration.", "HUMAN_REVIEW"),
    ]
    observations = []
    for label, text, expected in cases:
        sc, claim = fresh_scope(), "inbox-" + uuid4().hex[:12]
        env = setup.SandboxApp(folder / (label + ".sqlite"), sc)
        try:
            install(env, folder, label, sc)
            url = "/api/correspondence/claims/" + claim
            env.post("/api/correspondence/claims", {"claim_id": claim, "scope": sc})
            setup.deliver_resource(env, claim, sc)
            assert env.get(url)["amount"] == "12.51"
            env.post(url + "/actions/approve-claim", {})
            filed = env.post(url + "/actions/submit-claim", {})["submissions"][0]
            env.source(claim, sc, "vendor", {"kind": "message", "receipt_id": filed["id"], "text": text})
            row = env.get(url)
            assert row["stage"] == expected and row["replies"][-1]["text"] == text, row
            action_ids = [a["id"] for a in row["actions"]]
            if expected == "HUMAN_REVIEW":
                assert row["replies"][-1]["reason"] == "unknown"
                assert not {"approve-response", "submit-response"} & set(action_ids)
                assert len(row["submissions"]) == 1 and row["ledger"]["awarded"] == "0.00"
            else:
                assert row["replies"][-1]["reason"] == "downtime"
                env.post(url + "/actions/approve-response", {})
                env.now += timedelta(days=1)
                response = env.post(url + "/actions/submit-response", {})
                assert len(response["submissions"]) == 2
                assert "measurements exceed" in response["submissions"][-1]["packet"]["argument"]
            observations.append({"case": label, "signed_text": text, "stage": row["stage"],
                "reason": row["replies"][-1]["reason"], "offered_actions": action_ids})
        finally:
            env.close()
    return observations


def historical_evidence(env, claim):
    """Read-only proof of retained evidence and immutable custody rows."""
    with database(env.path) as db:
        state = json.loads(db.execute("SELECT state FROM inbox_claim WHERE tenant=? AND id=?", (env.tenant, claim)).fetchone()[0])
        original = next(e for e in state["evidence"] if e["kind"] == "original_filing_receipt")
        initial = [tuple(row) for row in db.execute(f"SELECT * FROM {claim_identity.TABLE} WHERE case_id=? AND step='initial'", (claim,))]
        custody = [tuple(row) for row in db.execute("SELECT * FROM award_observation_event WHERE kind='filed_claim'")]
        registered = [tuple(row) for row in db.execute("SELECT * FROM award_observation_claim WHERE id=?", (claim,))]
    return {"original": canonical_json(original), "initial": initial, "custody": custody, "registered": registered}


def fresh_native_binding(office, award_id):
    """Observe the same generated native facts anew and sign a new allocation.

    No previous binding is replayed. This proves a post-response award can first
    become attributed through the normal observation/authorization entrypoints.
    """
    with database(office.env.path) as db:
        snapshot = json.loads(db.execute("SELECT payload FROM award_observation_snapshot ORDER BY rowid DESC LIMIT 1").fetchone()[0])
        prior = json.loads(db.execute("SELECT signed FROM award_observation_event WHERE kind='attribution'").fetchone()[0])
    snapshot.update(id="post-response-snapshot", observed_at=datetime.now(UTC).isoformat())
    observed = office.store.observe(office.signed("native_snapshot", snapshot["id"], snapshot, ["ramp_observer"]))
    binding = prior["statement"]["body"] | {"award_id": award_id, "snapshot_sha256": observed["snapshot_sha256"]}
    result = office.store.attribute(office.signed("attribution", "post-response-binding", binding, ["finance_approver"]))
    assert result["status"] == "ATTRIBUTED_OBSERVATION"


def verify_native_lifecycle(folder):
    sc, claim = fresh_scope(), "inbox-" + uuid4().hex[:12]
    env = setup.SandboxApp(folder / "native.sqlite", sc)
    try:
        state, _ = install(env, folder, "native", sc, extra_terms=[
            ("An incomplete claim may supplement its missing fields by the same deadline.", {"supplement": "same_filing_deadline"})])
        url = "/api/correspondence/claims/" + claim
        env.post("/api/correspondence/claims", {"claim_id": claim, "scope": sc})
        setup.deliver_resource(env, claim, sc)
        current = env.get(url)
        # Correspondence exposes the resolved agreement version; the promoted
        # adapter version remains a cited input, not necessarily the same hash.
        assert len(current["contract_version"]) == 64 and current["preflight"]["outcome"] == "ELIGIBLE"
        assert any(c["version"] == state["active_version"] for c in current["preflight"]["clauses"])
        assert len(current["contract_source_sha256"]) == 64
        original = dict(kind="original_filing_receipt", receipt_id="external-" + uuid4().hex,
            source_ref="synthetic-vendor-custody", received_at="2026-07-02T12:30:00Z",
            observed_at="2026-07-03T00:00:00Z", submitted_to="claims@example.invalid",
            contract_version=current["contract_version"], contract_source_sha256=current["contract_source_sha256"],
            fields=[dict(name="station identifier", refs=[sc["component"]])])
        env.source(claim, sc, "vendor", original)
        assert env.get(url)["stage"] == "HISTORICAL_FILING"
        office = setup.Office(env, folder, sc, current["contract_version"])
        office.register(claim, sc)  # Includes an exact signed custody-digest negative control.
        assert office.award("before-response")["status"] == "VERIFIED_AWARD"
        office.attribute("before-response")  # Includes a signed +1 minor-unit capacity refusal.

        def summary():
            return env.get("/api/ramp/workspace")["credit_sync"]["verified_award_attribution"]

        def bound(view):
            assert view["active_binding_count"] == 1, view
            assert view["credits"][0]["stage"] == "RAMP_APPLIED_ATTRIBUTED", view
            assert view["actual_recovered_cash"] is None

        before = summary()
        bound(before)
        original_retained = historical_evidence(env, claim)
        filing_digest = office.store.filing_identity(claim)
        env.source(claim, sc, "vendor", {"kind": "message", "receipt_id": original["receipt_id"],
            "text": "Please supply the missing log references."})
        assert env.get(url)["stage"] == "RESPONSE_DRAFTED"
        env.post(url + "/actions/approve-response", {})
        env.now += timedelta(days=1)
        sent = env.post(url + "/actions/submit-response", {})
        receipt = sent["submissions"][0]
        assert len(sent["submissions"]) == 1 and receipt["action"] == "submit-response"
        assert receipt["requested"] == receipt["packet"]["requested"] == "0.00"
        assert receipt["packet"]["purpose"] == "procedural_evidence_only"
        assert receipt["packet"]["in_reply_to"] == original["receipt_id"]
        after = summary()
        bound(after)
        assert office.store.filing_identity(claim) == filing_digest
        assert historical_evidence(env, claim) == original_retained
        assert office.award("after-response")["status"] == "VERIFIED_AWARD"
        fresh_native_binding(office, "after-response")
        bound(summary())
        assert summary()["historical_binding_count"] == 2
        # Restart the actual composition with the same public office, no resolver fixture.
        env.reopen(folder / "office-public.json")
        office.store = env.app.state.ramp_workspace.awards
        bound(summary())
        assert historical_evidence(env, claim) == original_retained

        # Explicit negative controls only: corrupt locally persisted copies after
        # the positive chain succeeded. Each original byte string is restored.
        with database(env.path) as db:
            clean_state = db.execute("SELECT state FROM inbox_claim WHERE tenant=? AND id=?", (env.tenant, claim)).fetchone()[0]
        # Even direct local SQL cannot rewrite a canonical reservation normally.
        try:
            with database(env.path) as db:
                db.execute(f"UPDATE {claim_identity.TABLE} SET packet_digest=? WHERE receipt_id=?", ("0" * 64, receipt["id"]))
        except sqlite3.IntegrityError as exc:
            assert str(exc) == "immutable claim reservation"
        else:
            raise AssertionError("Canonical reservation accepted an in-place rewrite")
        corruptions = []
        for damage in ("nonzero_procedural", "wrong_predecessor", "altered_original", "unreserved_response", "second_local_initial"):
            altered = json.loads(clean_state)
            outgoing = altered["submissions"][0]
            if damage == "nonzero_procedural":
                outgoing["requested"] = outgoing["packet"]["requested"] = "0.01"
                outgoing["digest"] = outgoing["approval"]["digest"] = fingerprint(outgoing["packet"])
            elif damage == "wrong_predecessor":
                outgoing["packet"]["in_reply_to"] = "different-external-filing"
                outgoing["digest"] = outgoing["approval"]["digest"] = fingerprint(outgoing["packet"])
            elif damage == "altered_original":
                fact = next(e for e in altered["evidence"] if e["kind"] == "original_filing_receipt")
                fact["body"]["received_at"] = "2026-07-03T12:30:00Z"
            elif damage == "unreserved_response":
                outgoing["id"] = "unreserved-response"
            elif damage == "second_local_initial":
                altered["submissions"].append(deepcopy(outgoing) | {"id": "forged-initial", "action": "submit-claim"})
            with database(env.path) as db:
                db.execute("UPDATE inbox_claim SET state=? WHERE tenant=? AND id=?", (json.dumps(altered), env.tenant, claim))
                db.commit()
            try:
                invalid = summary()
                assert invalid["active_binding_count"] == 0 and invalid["issues"], (damage, invalid)
                assert invalid["actual_recovered_cash"] is None
                try:
                    office.award("invalid-" + damage)
                except AttributionError as exc:
                    refusal = str(exc)
                else:
                    raise AssertionError("Corrupt history authorized a new award: " + damage)
                corruptions.append({"damage": damage, "active_bindings": 0, "issues": invalid["issues"], "award_refusal": refusal})
            finally:
                with database(env.path) as db:
                    db.execute("UPDATE inbox_claim SET state=? WHERE tenant=? AND id=?", (clean_state, env.tenant, claim))
                    db.commit()
            bound(summary())
            assert historical_evidence(env, claim) == original_retained
        return {"original_intake": "ACCEPTED_CURRENT_VERSION_AND_SOURCE", "contract_version": current["contract_version"],
            "contract_source_sha256": current["contract_source_sha256"], "before_active": before["active_binding_count"],
            "after_active": after["active_binding_count"], "after_stage": after["credits"][0]["stage"],
            "subsequent_award": "VERIFIED_AWARD", "post_response_native_binding": "ATTRIBUTED_OBSERVATION",
            "response_requested": receipt["requested"],
            "retained_original_and_custody": "UNCHANGED", "restart": "BOUND", "actual_recovered_cash": None,
            "corruption_controls": corruptions, "other_controls": ["substituted custody digest rejected", "one-minor-unit overallocation rejected", "canonical reservation SQL rewrite rejected"],
            "fixture_provenance": "GENERATED TEST INPUT ONLY; ACTUAL_NATIVE is the exercised verifier mode, not a real Ramp observation"}
    finally:
        env.close()


def main():
    probes = (verify_resources, verify_regions, verify_denials, verify_native_lifecycle)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", choices=[p.__name__ for p in probes])
    args = parser.parse_args()
    results = {"source_pin": SOURCE_PIN, "executed_head": SOURCE_HEAD, "executed_tree": SOURCE_TREE,
        "original_artifacts": preserved_originals(), "results": {}}
    with TemporaryDirectory(prefix="uptime-independent-fix-verifier-") as temporary:
        for probe in probes:
            if args.probe and args.probe != probe.__name__:
                continue
            folder = Path(temporary).resolve() / probe.__name__
            folder.mkdir()
            results["results"][probe.__name__] = probe(folder)
    preserved_originals()
    results["status"] = "PASS"
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
