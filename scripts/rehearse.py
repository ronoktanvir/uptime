"""Execute the film's business path in an isolated SQLite workspace, without a network."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import secrets
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.server import create_app

def replay():
    with TemporaryDirectory(prefix="uptime-rehearsal-") as tmp:
        db=Path(tmp)/"replay.sqlite"
        password = secrets.token_urlsafe(32)
        options = dict(mode="replay", rehearsal=True, rehearsal_secret=password, approvals_enabled=True)
        with TestClient(create_app(db, **options), base_url=DEFAULT_ORIGIN,
                        client=("127.0.0.1", 55000)) as client:
            actor = ReviewerClient(client, DEFAULT_ORIGIN, SCRIPT, password)
            def get(path):
                response = client.get(path, headers=actor.headers)
                response.raise_for_status()
                return response.json()
            def act(case, action):
                response = actor.post(f"/api/cases/{case}/actions/{action}", {})
                response.raise_for_status()
                return response.json()
            assert get("/api/cases/price-prepayment")["amount"]=="7500.00"
            assert get("/api/cases/sla-eligible")["outcome"]=="ELIGIBLE"
            assert get("/api/cases/sla-ineligible")["outcome"]=="INELIGIBLE"
            assert get("/api/cases/sla-insufficient")["outcome"]=="INSUFFICIENT_EVIDENCE"
            assert get("/api/cases/sla-unsupported")["outcome"]=="UNSUPPORTED_RULE"
            for i in ("dispute-cure","dispute-denial","dispute-review","dispute-partial"):
                act(i,"approve-claim")
                act(i,"submit-claim")
            for action in ("prepare-response","approve-response","advance-cooldown","submit-response","record-credit","apply-partial"):
                act("dispute-cure",action)
            # End this runtime and authenticate again against the persisted isolated workspace.
        with TestClient(create_app(db, **options), base_url=DEFAULT_ORIGIN,
                        client=("127.0.0.1", 55000)) as client:
            actor = ReviewerClient(client, DEFAULT_ORIGIN, SCRIPT, password)
            cured=get("/api/cases/dispute-cure")
            assert cured["ledger"]["awarded"]=="100.00" and cured["ledger"]["applied"]=="50.00"
            assert get("/api/cases/dispute-denial")["stage"]=="DENIAL_ACCEPTED"
            assert get("/api/cases/dispute-review")["stage"]=="HUMAN_REVIEW"
            partial=get("/api/cases/dispute-partial")
            assert partial["ledger"]["disputed_remainder"]=="20.00" and partial["ledger"]["awarded"]=="80.00"
            lab=get("/api/onboarding")
            states=[lab["state"]]
            assert lab["state"]=="SHADOW" and lab["reviewer"] is None
            for step in ("approve","activate","rollback"):
                action=next(a["id"] for a in lab["actions"] if a["id"].split("~")[0]==step)
                response = actor.post("/api/onboarding/actions/"+action, {})
                response.raise_for_status()
                lab = response.json()
                states.append(lab["state"])
            assert states[1:3]==["APPROVED","ACTIVE"] and lab["active_version"] is None
            return dict(mode="DETERMINISTIC_REPLAY",identity=SCRIPT,price_exposure="7500.00",
                        confirmed_simulated_award=cured["ledger"]["awarded"],recorded=cured["ledger"]["posted"],
                        applied=cured["ledger"]["applied"],disputed=partial["ledger"]["disputed_remainder"],
                        onboarding=states,actual_customer_recovery=None)

if __name__=="__main__":
    print(json.dumps(replay(),indent=2))
