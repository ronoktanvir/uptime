"""Replay the independent review's mounted native join with a pinned original and a lawful response."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


def exercise(folder, damage):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from scripts.independent_final_review_probes import (
        SandboxApp, Office, scope, install_resource, deliver_resource, timedelta, AttributionError)
    from uptime.claim_identity import TABLE
    from uptime.storage import database
    from test_vendor_semantic_bindings import review_submission

    # D04-C (2026-11-09): incident and region do not apply to this non-regional resource family; the probe helper is unchanged.
    sc, claim = {k: v for k, v in scope().items() if k not in ("incident", "region")}, "inbox-native-history"
    env = SandboxApp(folder/"native.sqlite",sc)
    extension = [("An incomplete claim may supplement its missing fields by the same deadline.",
                  {"supplement":"same_filing_deadline"})]
    # Explicit public fixture review; historical filing and financial assertions
    # below remain unchanged. This never represents an actual human decision.
    install_resource(env,folder,"native-history",extra_terms=extension,
        semantic_review=lambda state, text: review_submission(state['manifest'], state['overlay'], text))
    url = "/api/correspondence/claims/"+claim
    env.post("/api/correspondence/claims",{"claim_id":claim,"scope":sc})
    deliver_resource(env,claim,sc)
    provenance = env.get(url)
    version = provenance["contract_version"]
    original = {"kind":"original_filing_receipt","receipt_id":"independent-original","source_ref":"vendor-custody",
                "contract_version":version, "contract_source_sha256":provenance["contract_source_sha256"],
                "received_at":"2026-07-02T12:30:00Z","observed_at":"2026-07-03T00:00:00Z",
                "submitted_to":"claims@example.invalid","fields":[{"name":"station identifier","refs":[sc["component"]]}]}
    env.source(claim,sc,"vendor",original)
    with database(env.path) as db:
        original_fact = json.loads(db.execute("SELECT state FROM inbox_claim WHERE id=?",(claim,)).fetchone()[0])["evidence"][-1]
    office = Office(env,folder,sc,version)
    office.register(claim,sc)
    office.award("first-award")
    office.attribute("first-award")
    before = env.get("/api/ramp/workspace")["credit_sync"]["verified_award_attribution"]
    assert before["active_binding_count"] == 1
    env.source(claim,sc,"vendor",{"kind":"message","receipt_id":original["receipt_id"],
                                "text":"Please supply the missing log references."})
    assert env.get(url)["stage"] == "RESPONSE_DRAFTED"
    env.post(url+"/actions/approve-response",{})
    env.now += timedelta(days=1)
    sent = env.post(url+"/actions/submit-response",{})
    response = sent["submissions"][0]
    assert response["action"] == "submit-response" and response["requested"] == "0.00"
    assert sent["ledger"]["claimed"] == sent["ledger"]["awarded"] == "0.00"
    with database(env.path) as db:
        canonical = [tuple(r) for r in db.execute(f"SELECT step,route,receipt_id FROM {TABLE} ORDER BY step")]
        retained = json.loads(db.execute("SELECT state FROM inbox_claim WHERE id=?",(claim,)).fetchone()[0])["evidence"]
    assert next(e for e in retained if e["kind"] == "original_filing_receipt") == original_fact
    assert len(canonical) == 2 and canonical[0][0:2] == ("initial","historical-receipt")
    assert canonical[1] == ("supplement","historical-receipt",response["id"])
    if damage != "none":
        with database(env.path) as db, db:
            row = db.execute("SELECT state FROM inbox_claim WHERE tenant=? AND id=?",(env.tenant,claim)).fetchone()
            state = json.loads(row[0])
            if damage == "money":
                state["submissions"][0]["requested"] = "0.01"
                state["submissions"][0]["packet"]["requested"] = "0.01"
            elif damage == "duplicate":
                state["submissions"].append(dict(state["submissions"][0]))
            elif damage == "different-predecessor":
                state["submissions"][0]["packet"]["in_reply_to"] = "another-original"
            elif damage == "missing-reservation":
                db.execute(f"DROP TRIGGER {TABLE}_no_delete")
                db.execute(f"DELETE FROM {TABLE} WHERE step='supplement'")
            elif damage == "before-original":
                state["submissions"][0]["at"] = "2026-07-01T00:00:00+00:00"
                db.execute(f"DROP TRIGGER {TABLE}_no_update")
                db.execute(f"UPDATE {TABLE} SET at=? WHERE step='supplement'",(state["submissions"][0]["at"],))
            db.execute("UPDATE inbox_claim SET state=? WHERE tenant=? AND id=?",(json.dumps(state),env.tenant,claim))
    after = env.get("/api/ramp/workspace")["credit_sync"]["verified_award_attribution"]
    if damage == "none":
        assert after["active_binding_count"] == 1 and after["credits"][0]["stage"] == "RAMP_APPLIED_ATTRIBUTED"
        assert after["issues"] == []
        office.award("later-award")
        later = env.get("/api/ramp/workspace")["credit_sync"]["verified_award_attribution"]
        assert later["verified_award_count"] == 2 and later["active_binding_count"] == 1
        assert later["actual_recovered_cash"] is None
        # The original award's terms are historical facts. Current catalog
        # removal cannot silently replace those facts or invoke a latest resolver.
        vendor = env.get("/api/vendors/native-history")
        assert env.action("native-history",vendor,"revoke")["state"] == "REVOKED"
        assert env.get(url)["contract_version"] is None
        office.award("award-after-catalog-revocation")
        retained_awards = env.get("/api/ramp/workspace")["credit_sync"]["verified_award_attribution"]
        assert retained_awards["verified_award_count"] == 3 and retained_awards["active_binding_count"] == 1
        assert retained_awards["actual_recovered_cash"] is None
    else:
        assert after["active_binding_count"] == 0
        with pytest.raises(AttributionError):
            office.award("later-award")
    env.close()
    return {"before_active":before["active_binding_count"],"after_active":after["active_binding_count"],
            "after_stage":after["credits"][0]["stage"],"issues":after["issues"],"damage":damage,
            "actual_recovered_cash":after["actual_recovered_cash"]}


@pytest.mark.parametrize("damage",["none","money","duplicate","different-predecessor","missing-reservation","before-original"])
def test_pinned_external_filing_retains_only_its_legitimate_procedural_response(tmp_path,damage):
    # The independent helper prohibits network at import. Isolate that constraint from other tests.
    result = subprocess.run([sys.executable,str(Path(__file__).resolve()),str(tmp_path),damage],
                            cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=60)
    assert result.returncode == 0,result.stdout+result.stderr
    row = json.loads(result.stdout)
    assert row["damage"] == damage and row["actual_recovered_cash"] is None


if __name__ == "__main__":
    print(json.dumps(exercise(Path(sys.argv[1]),sys.argv[2]),sort_keys=True))
