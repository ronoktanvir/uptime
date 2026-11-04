"""Compose independently verified domain views. This layer never evaluates contract terms."""
from decimal import Decimal
from threading import RLock

from . import onboarding, policy
from .contracts import Source
from .disputes import DisputeDesk
from .evidence import evidence_summary
from .intelligence import model_card
from .pricing import demo_cases as price_cases
from .other_obligations import demo_cases as other_cases
from .ramp import FixtureRampProvider, ramp_snapshot
from .reconciliation import demo_reconciliation
from .storage import (database, initialize, save_cases, stored_cases, settlement_events,
                      SETTLEMENT_ACTIONS, transition_settlement)
from .twilio import demo_cases as sla_cases

TENANT="bears"
SIM=[Source.VENDOR.value,Source.REPLAY.value]
CUSTOM=[Source.CUSTOMER.value,Source.REPLAY.value]


def usd(amount):
    return f"${Decimal(amount):,.2f}"


class Workbench:
    def __init__(self, path, mode):
        self.path=path
        self.mode=mode
        if mode not in {"sandbox","replay"}:
            raise ValueError("unknown data mode")
        initialize(path)
        policy.setup(path)
        self.mutex=RLock()  # Serializes mode changes with dispatch in this single-process sandbox.
        self.desk=DisputeDesk(path)
        self.desk.seed(TENANT)
        save_cases(path,TENANT,price_cases()+sla_cases()+other_cases())

    def ramp(self):
        data=FixtureRampProvider().snapshot() if self.mode=="replay" else ramp_snapshot()
        if self.mode=="sandbox" and Source.RAMP in data["sources"]:
            data["sources"]=list(dict.fromkeys([*data["sources"],Source.REPLAY.value]))
            data["note"]="Saved live sandbox read. Refresh from the operator CLI to fetch a newer observation."
        else:
            data["note"]="Offline synthetic provider. No Ramp request is made in replay."
        return data

    def pricing_probe(self, principal):
        if principal.tenant != TENANT:
            raise PermissionError("Workspace mismatch")
        if self.mode!="sandbox":
            return []
        data=self.ramp()
        if Source.RAMP not in data["sources"]:
            return []
        result=[]
        for bill in data["bills"]:
            # Fresh imports never inherit the linked synthetic customer's service allocation.
            missing=["verified governing agreement", "performance date", "service mapping", "units and unit price"]
            def native_amount(value):
                if not value or not value.get("currency") or value.get("amount") is None:
                    return "Amount unavailable"
                return f'{value["currency"]} {value["amount"]}'
            currency=(bill.get("amount") or {}).get("currency")
            facts=[{"label":"Ramp expense line","detail":f'{line["id"]} · observed {native_amount(line.get("amount"))}',
                    "sources":data["sources"]} for line in bill["lines"]] or [dict(label="Bill lines",detail="No verified line items",sources=data["sources"])]
            result.append(dict(id="ramp-"+bill["id"],vendor="Ramp sandbox",title=f'{bill["status"].title()} bill · contract check',
                 outcome="INSUFFICIENT_EVIDENCE",stage="NEEDS_MAPPING",amount=None,currency=currency,sources=data["sources"],
                 trace=["No verified negotiated terms or allocation bind this bill to a customer contract.",
                        "Missing: "+", ".join(missing)+". The bill total cannot establish an overcharge."],
                 clauses=[dict(label="Governing agreement unavailable",uri="urn:uptime:missing:governing-agreement")],
                 evidence=facts,timeline=[dict(at=data["observed_at"],event="Sandbox bill retrieved by provider ID",sources=data["sources"])],
                 financials=[dict(label="Observed bill amount",value=native_amount(bill.get("amount")),sources=data["sources"])],
                 actions=[],provider_id=bill["id"],provider_uri="https://demo.ramp.com"))
        return result

    def lab(self, principal, action=None):
        with self.mutex, database(self.path) as db:
            if action is not None:
                self.check_write(principal)
                result=onboarding.act(db,principal,action)
            else:
                result=onboarding.get_lab(db,principal)
            if self.setting(principal)["mode"]=="OBSERVE":
                result["actions"]=[]
            return result

    def setting(self, principal):
        result=policy.policy(self.path,principal)
        if self.mode!="replay":
            result["available_modes"]=["OBSERVE","ASSISTED"]
        return result

    def change_setting(self, principal, mode, cap):
        with self.mutex:
            if mode=="POLICY_AUTOMATED" and self.mode!="replay":
                raise ValueError("Policy automation requires an isolated replay workspace")
            return policy.configure(self.path,principal,mode,cap)

    def check_write(self, principal):
        if principal.role!="reviewer" or self.setting(principal)["mode"]=="OBSERVE":
            raise PermissionError("This session or workspace policy permits observation only")

    def dispute(self, principal, case_id):
        case=self.desk.case(principal,case_id)
        events=settlement_events(self.path,principal.tenant,case_id)
        awarded=case["ledger"]["awarded"]
        stage=events[-1]["stage"] if events else ("AWARDED" if Decimal(awarded)>0 else "NONE")
        rec=demo_reconciliation(awarded,stage,tenant=principal.tenant,case_id=case_id)
        case["reconciliation"]=rec
        case["ledger"].update(posted=rec["posted"], applied=rec["applied"])
        case["financials"]=[dict(label=k.replace("_"," ").title(),value=usd(v),
                                 sources=rec["stage_sources"].get(k, SIM if k in ("disputed_remainder","claimed") else CUSTOM))
                            for k,v in case["ledger"].items()]
        for e in events:
            case["timeline"].append(dict(at=e["at"],event=f'{e["actor"]}: {SETTLEMENT_ACTIONS[e["action"]][2]}',
                                          sources=SIM,role="reviewer",stage=e["stage"]))
        if events and not Decimal(case["ledger"]["disputed_remainder"]):
            case["stage"]=stage
        if Decimal(awarded)>0 and principal.role=="reviewer":
            previous=events[-1]["stage"] if events else None
            case["actions"] += [dict(id=k,label=v[2]) for k,v in SETTLEMENT_ACTIONS.items() if v[0]==previous]
        if principal.role!="reviewer" or self.setting(principal)["mode"]=="OBSERVE":
            case["actions"]=[]
        if case["outcome"]!="ELIGIBLE":
            case["amount"]=None
        return case

    def case(self, principal, case_id):
        if case_id.startswith("dispute-"):
            return self.dispute(principal,case_id)
        for case in stored_cases(self.path,principal.tenant)+self.pricing_probe(principal):
            if case["id"]==case_id:
                return case
        raise KeyError(case_id)

    def act(self, principal, case_id, action):
        with self.mutex:
            self.check_write(principal)
            if not case_id.startswith("dispute-"):
                self.case(principal,case_id)
                raise KeyError("No such action on an observation")
            if action in SETTLEMENT_ACTIONS:
                case=self.dispute(principal,case_id)
                transition_settlement(self.path,principal,case_id,action,case["ledger"]["awarded"])
            else:
                previous=self.desk.case(principal,case_id)["stage"]
                case=self.desk.act(principal,case_id,action)
                new_approval=previous=="DRAFTED" and case["stage"]=="CLAIM_APPROVED" and action=="approve-claim"
                if self.mode=="replay" and new_approval and policy.dispatch_allowed(case,self.setting(principal)):
                    self.desk.act(principal,case_id,"submit-claim")
            return self.dispute(principal,case_id)

    def dashboard(self, principal):
        stored=stored_cases(self.path,principal.tenant)
        cases=stored+[self.dispute(principal,c["id"]) for c in self.desk.cases(principal)]+self.pricing_probe(principal)
        focus=next(c for c in cases if c["id"]=="dispute-cure")
        # Refusals and alternative simulations are controls, not additional portfolio value.
        ledger=focus["ledger"]
        price=next((c for c in stored if c["id"].startswith("price-") and c["outcome"]=="ELIGIBLE"
                    and "pre" in (c["stage"]+" "+c["title"]).casefold()),None)
        metrics=[dict(label="Invoice exposure",value=usd(price["amount"]) if price else "Not verified",
                      note="One unpaid synthetic invoice; amendment-aware discrepancy before approval.",
                      sources=CUSTOM,case_id=price["id"] if price else None)]
        for key,label,note in [("estimated","Estimated credit","Candidate affected fees."),
                               ("claimed","Claim filed","Submitted to the simulator."),
                               ("awarded","Vendor awarded","Confirmed by the simulator."),
                               ("posted","Credit recorded","Identified simulated credit record."),
                               ("applied","Applied to bills","Matched simulated bill application.")]:
            metrics.append(dict(label=label,value=usd(ledger[key]),note=note+" Recovery case: dispute-cure.",
                                sources=focus["reconciliation"]["stage_sources"].get(key, CUSTOM if key=="estimated" else SIM),case_id=focus["id"]))
        columns=("id","vendor","title","outcome","stage","amount","currency","sources")
        audit=[dict(at=e["at"],event=e["event"],case_id=c["id"],sources=e["sources"])
               for c in cases for e in c.get("timeline",[])]
        ramp=self.ramp()
        return dict(workspace="Bears finance lab",as_of=ramp.get("observed_at") or "Deterministic replay",
                    role=principal.role,mode=self.mode,metrics=metrics,
                    cases=[{k:c[k] for k in columns} for c in cases],
                    audit=sorted(audit,key=lambda e:e["at"],reverse=True)[:24],ramp=ramp,
                    real_recovery="No verified customer recovery",actual_applied=None)

    def integrations(self, principal):
        if principal.tenant != TENANT:
            raise PermissionError("Workspace mismatch")
        return dict(ramp=self.ramp(),public_evidence=evidence_summary(),model=model_card(),
                    vendor_transport="SIMULATED_VENDOR",sources=[Source.REPLAY.value])
