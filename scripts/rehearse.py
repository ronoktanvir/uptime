"""Execute the film's business path in an isolated SQLite workspace, without a network."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uptime.contracts import Principal
from uptime.workbench import Workbench

def replay():
    p=Principal("bears","scripted-test-reviewer","reviewer")
    with TemporaryDirectory(prefix="uptime-rehearsal-") as tmp:
        db=Path(tmp)/"replay.sqlite"
        bench=Workbench(db,"replay")
        assert bench.case(p,"price-prepayment")["amount"]=="7500.00"
        assert bench.case(p,"sla-eligible")["outcome"]=="ELIGIBLE"
        assert bench.case(p,"sla-ineligible")["outcome"]=="INELIGIBLE"
        assert bench.case(p,"sla-insufficient")["outcome"]=="INSUFFICIENT_EVIDENCE"
        assert bench.case(p,"sla-unsupported")["outcome"]=="UNSUPPORTED_RULE"
        for i in ("dispute-cure","dispute-denial","dispute-review","dispute-partial"):
            bench.act(p,i,"approve-claim")
            bench.act(p,i,"submit-claim")
        for action in ("prepare-response","approve-response","advance-cooldown","submit-response","record-credit","apply-partial"):
            bench.act(p,"dispute-cure",action)
        restarted=Workbench(db,"replay")
        cured=restarted.case(p,"dispute-cure")
        assert cured["ledger"]["awarded"]=="100.00" and cured["ledger"]["applied"]=="50.00"
        assert restarted.case(p,"dispute-denial")["stage"]=="DENIAL_ACCEPTED"
        assert restarted.case(p,"dispute-review")["stage"]=="HUMAN_REVIEW"
        partial=restarted.case(p,"dispute-partial")
        assert partial["ledger"]["disputed_remainder"]=="20.00" and partial["ledger"]["awarded"]=="80.00"
        lab=restarted.lab(p)
        states=[lab["state"]]
        assert lab["state"]=="SHADOW" and lab["reviewer"] is None
        for step in ("approve","activate","rollback"):
            action=next(a["id"] for a in lab["actions"] if a["id"].split("~")[0]==step)
            lab=restarted.lab(p,action)
            states.append(lab["state"])
        assert states[1:3]==["APPROVED","ACTIVE"] and lab["active_version"] is None
        return dict(mode="DETERMINISTIC_REPLAY",identity=p.subject,price_exposure="7500.00",
                    confirmed_simulated_award=cured["ledger"]["awarded"],recorded=cured["ledger"]["posted"],
                    applied=cured["ledger"]["applied"],disputed=partial["ledger"]["disputed_remainder"],
                    onboarding=states,actual_customer_recovery=None)

if __name__=="__main__":
    print(json.dumps(replay(),indent=2))
