"""Compose independently verified domain views. This layer never evaluates contract terms."""
from decimal import Decimal, InvalidOperation, localcontext
from threading import RLock

from . import onboarding, policy
from .contracts import Principal, Source, fingerprint
from .claim_identity import EconomicScopeReviewRequired, claim_key
from .vendor_registry import historical_economic_identity, require_case_semantics
from .vendor_bindings import SemanticBindingRequired
from .governing_fees import GoverningFeeRequired
from .mandates import CreditDecision, check_credit_decision
from .disputes import DisputeDesk
from .evidence import evidence_summary
from .intelligence import model_card
from .pricing import demo_cases as price_cases
from .other_obligations import demo_cases as other_cases
from .ramp import FixtureRampProvider, ramp_snapshot
from .allocations import AllocationLedger, SCOPE_FIELDS, settlement_reconciliation, settlement_actions, usd_cents
from .storage import (database, initialize, save_cases, stored_cases, settlement_events,
                      SETTLEMENT_ACTIONS, transition_settlement, case_versions)
from .twilio import demo_cases as sla_cases

TENANT="bears"
SIM=[Source.VENDOR.value,Source.REPLAY.value]
CUSTOM=[Source.CUSTOMER.value,Source.REPLAY.value]

# Current observations whose authority is unavailable have a distinct shape.
# New evaluator fields cannot silently survive this allowlist. Evidence and
# clauses are immutable inputs; historical amounts live in recorded_* / versions.
REVIEW_OBSERVATION_FIELDS = frozenset({
    'id','vendor','vendor_id','title','version','semantics_revision','obligation_id','economic_identity',
    'sources','clauses','source_sha256','source_received_at','source_currentness','agreement','account',
    'adapter_revision','evidence','timeline','currency','basis','observation_digest','remedy','citations',
    'claim_cutoff','claim_cutoff_exclusive','cutoff_inclusive','deadline_context','recorded_stage','recorded_outcome','recorded_amount',
    'financial_scope_status','financial_scope_reason','semantic_binding_status','pricing_binding_status',
})


def review_observation(case):
    result = {key:value for key,value in case.items() if key in REVIEW_OBSERVATION_FIELDS}
    reason = case.get('financial_scope_reason', 'Current source meaning requires review.')
    result.update(stage='REVIEW_REQUIRED', outcome='INSUFFICIENT_EVIDENCE', amount=None, actions=[],
        trace=[f"Current evaluation unavailable for version {case.get('version', 'unknown')}: {reason}"],
        missing=['Current reviewed source meaning and financial scope'],
        financials=[dict(label='Current estimate', value='Review required', sources=case.get('sources', []))])
    return result


def usd(amount):
    number = Decimal(amount)
    # Entitlements can be sub-cent; presentation must not invent rounding authority.
    places = max(2, -number.normalize().as_tuple().exponent)
    return f"${number:,.{places}f}"


def _sources(groups):
    return sorted({str(s) for group in groups for s in group})


def _sum(values):
    with localcontext() as context:
        context.prec=80
        return format(sum((Decimal(v) for v in values), Decimal("0.00")), "f")


def _whole_cents(amount):
    try:
        usd_cents(str(amount))
        return True
    except (ValueError, InvalidOperation):
        return False


def _unposted(awarded, note):
    return dict(awarded=awarded, posted="0.00", applied="0.00", outstanding=awarded,
                unposted=awarded, unapplied_posted="0.00", stage="AWARDED" if Decimal(awarded)>0 else "NONE",
                sources=SIM, stage_sources=dict(awarded=SIM, posted=[Source.UNAVAILABLE.value],
                                               applied=[Source.UNAVAILABLE.value]),
                credit_ids=[], application_ids=[], bill_ids=[], actual_recovery=None, note=note)


def _obligation(case):
    if case.get("financial_scope_status") == "REVIEW_REQUIRED":
        return None
    submissions=case.get("submissions", [])
    if submissions and submissions[0].get("obligation_key"):
        return submissions[0]["obligation_key"]
    if case.get("obligation_id"):
        return case["obligation_id"]
    scope=case.get("scope")
    if scope:
        return fingerprint([case["vendor"],scope.get("account"),scope.get("contract"),
                            scope.get("service"),scope.get("month")])
    # B's observation snapshot and C's claim can describe the same obligation.
    for fact in case.get("evidence", []):
        detail=fact.get("detail")
        if isinstance(detail, dict) and all(detail.get(k) for k in ("account", "agreement", "product", "month")):
            return fingerprint([case["vendor"], detail["account"], detail["agreement"], detail["product"],detail["month"]])
    return case.get("obligation_id") or case["id"]


def _metrics(cases):
    """Stage snapshots, never a sum across stages or alternative estimates.

    A submitted supplement does not create another claim. Stored revisions have
    already been resolved to their current head; shared economic keys count once.
    Simulated events remain reportable even in historical/comparison cases.
    """
    definitions=[("exposure", "Invoice exposure"), ("estimated", "Estimated credit"),
                 ("claimed", "Claim filed"), ("awarded", "Vendor awarded"),
                 ("posted", "Credit recorded"), ("applied", "Applied to bills")]
    metrics=[]
    for key,label in definitions:
        contributions=[]
        grouped={}
        ambiguous=False
        unresolved_scope=False
        for case in cases:
            if case.get("currency") != "USD":
                continue
            ledger=case.get("ledger", {})
            if case.get("financial_scope_status") == "REVIEW_REQUIRED":
                raw=(case.get("recorded_amount") if key=="estimated" and case.get("recorded_outcome")=="ELIGIBLE"
                     else ledger.get(key) if key not in {"estimated", "exposure"} else None)
                if raw is not None and Decimal(raw)>0:
                    unresolved_scope=True
                    contributions.append(dict(case_id=case["id"], amount=None, recorded_amount=str(raw),
                        sources=case["sources"], references=case.get("financial_refs", []), obligation_id=None,
                        status="REVIEW_REQUIRED", reason=case["financial_scope_reason"]))
                continue
            if key=="exposure":
                if case.get("stage")!="PREPAYMENT_REVIEW" or case.get("payment_status")!="pending" or case.get("outcome")!="ELIGIBLE":
                    continue
                raw=case.get("amount")
            elif key=="estimated":
                if (case.get("preflight", {}).get("outcome", case.get("outcome"))!="ELIGIBLE"
                        or case.get("stage")=="PREPAYMENT_REVIEW"):
                    continue
                raw=ledger.get(key,case.get("amount"))
            else:
                raw=ledger.get(key)
            if raw is None or Decimal(raw)<=0:
                continue
            sources=case.get("reconciliation", {}).get("stage_sources", {}).get(key,
                        case["sources"] if key in {"exposure", "estimated"} else SIM)
            row=dict(case_id=case["id"], amount=str(raw), sources=sources,
                     references=case.get("financial_refs", []), obligation_id=_obligation(case))
            contributions.append(row)
            old=grouped.get(row["obligation_id"])
            if old is not None and Decimal(old)!=Decimal(raw):
                ambiguous=True
            grouped[row["obligation_id"]]=raw
        # Seeded evaluations vary assumptions and can be mutually exclusive.
        # Historical filed/awarded events are activity totals, not projected ROI.
        alternative=(key in {"estimated", "exposure"} and len(contributions)>1
                     and any(c["cohort"]=="seeded" for c in cases if c["id"] in {r["case_id"] for r in contributions}))
        unknown=key in {"estimated", "exposure"} and not contributions
        amount=None if unresolved_scope or ambiguous or alternative or unknown else _sum(grouped.values())
        note=("Historical financial scope requires manual reconciliation; this stage total is unavailable."
              if unresolved_scope else "No verified eligible estimate is available; absence of evidence does not establish zero exposure."
              if unknown else "Alternative or conflicting estimates are nonadditive; inspect each case."
              if ambiguous or alternative else
              "Provisional USD estimate only; no filing, prevention or recovery established."
              if key in {"estimated", "exposure"} else
              "Total unique recorded simulated activity, including partial awards and comparison cases; not actual customer recovery.")
        ids=sorted({r["case_id"] for r in contributions})
        metrics.append(dict(key=key,label=label,value=usd(amount) if amount is not None else "Review required" if unresolved_scope else "Not verified" if unknown else "Not additive",
                            amount=amount,currency="USD",note=note,case_id=ids[0] if len(ids)==1 else None,
                            case_ids=ids,contributions=contributions,
                            **({"financial_scope_status":"REVIEW_REQUIRED"} if unresolved_scope else {}),
                            sources=_sources(r["sources"] for r in contributions) or [Source.UNAVAILABLE.value],
                            actual_recovery=None))
    return metrics


class Workbench:
    def __init__(self, path, mode, *, tenant=TENANT,governing_fees=(),trusted_now=None):
        self.tenant = tenant
        self.governing_fees=governing_fees
        self.trusted_now=trusted_now
        self.path=path
        self.mode=mode
        if mode not in {"sandbox","replay"}:
            raise ValueError("unknown data mode")
        initialize(path)
        policy.setup(path)
        self.mutex=RLock()  # Serializes mode changes with dispatch in this single-process sandbox.
        self.desk=DisputeDesk(path)
        self.seed_ids = set()
        if tenant == TENANT:
            self.desk.seed(tenant)
            seeds = price_cases()+sla_cases()+other_cases()
            existing = {c["id"] for c in stored_cases(path, tenant)}
            save_cases(path, tenant, [c for c in seeds if c["id"] not in existing])
            self.seed_ids.update(c["id"] for c in seeds)
            self.seed_ids.update(c["id"] for c in self.desk.cases(Principal(tenant, "seed-reader", "viewer")))
        self.allocations = AllocationLedger(path)

    def require_tenant(self, principal):
        if principal.tenant != self.tenant:
            raise PermissionError("Workspace mismatch")

    def ramp(self):
        if self.tenant != TENANT:
            return {"sources": [Source.UNAVAILABLE.value], "observed_at": None,
                    "bills": [], "credits": [], "capabilities": {}, "note": "This installation has its own Ramp worklist."}
        data=FixtureRampProvider().snapshot() if self.mode=="replay" else ramp_snapshot()
        if self.mode=="sandbox" and Source.RAMP in data["sources"]:
            data["sources"]=list(dict.fromkeys([*data["sources"],Source.REPLAY.value]))
            data["note"]="Saved live sandbox read. Refresh from the operator CLI to fetch a newer observation."
        elif self.mode=="sandbox":
            data["note"]="Saved sandbox observation is unavailable or invalid. No provider request was made."
        else:
            data["note"]="Offline synthetic provider. No Ramp request is made in replay."
        return data

    def pricing_probe(self, principal):
        self.require_tenant(principal)
        if self.mode!="sandbox":
            return []
        data=self.ramp()
        if Source.RAMP not in data["sources"]:
            return []
        result=[]
        def native_amount(value):
            if not isinstance(value, dict) or not value.get("currency") or value.get("amount") is None:
                return "Amount unavailable"
            return f'{value["currency"]} {value["amount"]}'
        for bill in data.get("bills", []):
            missing=["verified governing agreement", "contract/service mapping"]
            lines=bill.get("lines") if isinstance(bill.get("lines"), list) else []
            facts=[]
            for line in lines:
                missing_line=[]
                for field, label in (("quantity", "quantity"), ("unit_price", "unit price"),
                                     ("service_date", "performance date"), ("sku", "product identity")):
                    if line.get(field) is None:
                        missing_line.append(label)
                if missing_line:
                    missing.append(f'line {line.get("id", "unknown")}: '+", ".join(missing_line))
                facts.append(dict(label="Ramp expense line", sources=data["sources"],
                    detail=f'{line.get("id", "Unknown line")} · observed {native_amount(line.get("amount"))}; '
                           f'quantity {line.get("quantity")}; unit price {native_amount(line.get("unit_price"))}; '
                           f'product {line.get("sku")}; service date {line.get("service_date")}; '
                           f'quantity/rate check {line.get("quantity_rate_check", "UNAVAILABLE")}',
                    **{k:line.get(k) for k in ("id", "quantity", "unit_price", "sku", "service_date",
                                             "quantity_rate_check", "accounting_field_selections")}))
            if not lines:
                missing.append("itemized lines, quantity, unit price and performance dates")
                facts.append(dict(label="Bill lines", detail="No verified line items", sources=data["sources"]))
            status=bill.get("status")
            status=status if isinstance(status, str) and status in {"OPEN", "PAID", "DRAFT"} else "UNKNOWN"
            if status == "UNKNOWN":
                missing.append("recognized bill payment status")
            capture=data.get("capture_status") or {}
            trace=["No verified negotiated terms or allocation bind this bill to a customer contract.",
                   "Missing: "+", ".join(missing)+". The bill total cannot establish an overcharge."]
            trace.append("Capture freshness: "+str(capture.get("freshness", "UNKNOWN"))+
                         "; integrity: "+str(capture.get("integrity", "UNKNOWN"))+
                         "; usable for evaluation: "+str(capture.get("usable_for_evaluation", False))+".")
            for key in ("age_seconds", "max_age_seconds", "legacy", "reasons", "reason"):
                if key in capture:
                    trace.append(f"Capture {key}: {capture[key]}")
            if any(line.get("quantity_rate_check") == "MISMATCH" for line in lines):
                trace.append("Observed line quantity × unit price conflicts with the line amount; independent review required.")
            currency=(bill.get("amount") or {}).get("currency") if isinstance(bill.get("amount"), dict) else None
            result.append(dict(id="ramp-"+bill["id"],vendor="Ramp sandbox",title=f'{status.title()} bill · contract check',
                 outcome="INSUFFICIENT_EVIDENCE",stage="NEEDS_MAPPING",amount=None,currency=currency,sources=data["sources"],
                 trace=trace, note=data.get("note", "Saved sandbox observation; contract mapping remains unverified."),
                 clauses=[dict(label="Governing agreement unavailable",uri="urn:uptime:missing:governing-agreement")],
                 evidence=facts,timeline=[dict(at=data.get("observed_at"),event="Sandbox bill retrieved by provider ID",sources=data["sources"])],
                 financials=[dict(label="Observed bill amount",value=native_amount(bill.get("amount")),sources=data["sources"])],
                 actions=[],provider_id=bill["id"],provider_uri="https://demo.ramp.com", payment_status=status,
                 provider_identity={k:bill.get(k) for k in ("vendor_id", "entity_id", "account_id", "account_identity")},
                 provider_lines=lines, capture_status=capture))
        return result

    def lab(self, principal, action=None):
        self.require_tenant(principal)
        if self.tenant != TENANT:
            raise KeyError("This installation uses the vendor catalog")
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
        self.require_tenant(principal)
        result=policy.policy(self.path,principal)
        if self.mode!="replay":
            result["available_modes"]=["OBSERVE","ASSISTED"]
        return result

    def change_setting(self, principal, mode, cap):
        self.require_tenant(principal)
        with self.mutex:
            if mode=="POLICY_AUTOMATED" and self.mode!="replay":
                raise ValueError("Policy automation requires an isolated replay workspace")
            return policy.configure(self.path,principal,mode,cap)

    def check_write(self, principal):
        self.require_tenant(principal)
        if principal.role!="reviewer" or self.setting(principal)["mode"]=="OBSERVE":
            raise PermissionError("This session or workspace policy permits observation only")

    def dispute(self, principal, case_id):
        self.require_tenant(principal)
        case=self.desk.case(principal,case_id)
        events=settlement_events(self.path,principal.tenant,case_id)
        awarded=case["ledger"]["awarded"]
        stage=events[-1]["stage"] if events else ("AWARDED" if Decimal(awarded)>0 else "NONE")
        try:
            rec=settlement_reconciliation(self.path,principal.tenant,case_id,awarded)
        except ValueError:
            if _whole_cents(awarded):
                raise
            rec=_unposted(awarded, "Exact sub-cent award requires a verified cent settlement; no posting is permitted.")
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
        if (Decimal(awarded)>0 and principal.role=="reviewer"
                and case["preflight"]["outcome"]=="ELIGIBLE"):
            if _whole_cents(awarded):
                case["actions"] += settlement_actions(rec["stage"], awarded)
        if principal.role!="reviewer" or self.setting(principal)["mode"]=="OBSERVE":
            case["actions"]=[]
        if case["outcome"]!="ELIGIBLE":
            case["amount"]=None
        return case

    def _inbox_case(self, principal, case_id):
        inbox=getattr(self, "inbox", None)
        if inbox is None:
            return None
        try:
            return inbox.case(principal, case_id)
        except KeyError:
            return None

    def _correspondence(self, principal, case):
        # C owns the authoritative status ledger; there is no financial_state field.
        awarded=case["ledger"]["awarded"]
        records=self.allocations.list_awards(principal.tenant, case_id=case["id"])
        case["reconciliations"]=records
        case["ledger"].update({key: _sum(r[key] for r in records) for key in ("posted", "applied")})
        case["reconciliation"]=_unposted(awarded, "No scoped credit recorded.")
        if records:
            case["reconciliation"].update({key: _sum(r[key] for r in records)
                                           for key in ("posted", "applied", "outstanding", "unposted", "unapplied_posted")})
            rec=case["reconciliation"]
            rec["stage_sources"]={key: _sources(r["stage_sources"][key] for r in records)
                                  for key in ("awarded", "posted", "applied")}
            rec["sources"]=_sources(r["sources"] for r in records)
            rec["stage"]=("APPLIED" if Decimal(rec["applied"])==Decimal(awarded)
                          else "PARTIALLY_APPLIED" if Decimal(rec["applied"])>0
                          else "POSTED" if Decimal(rec["posted"])>0 else "AWARDED")
            rec["note"]="Persistent scoped simulation records; actual customer recovery remains unknown."
        if not _whole_cents(awarded):
            case["reconciliation"]["note"]="Exact sub-cent award cannot be posted or applied."
        allowed=(case["stage"] in {"AWARDED", "PARTIAL_AWARD_REVIEW"}
                 and case["preflight"]["outcome"] == "ELIGIBLE" and _whole_cents(awarded)
                 and Decimal(awarded)>0 and principal.role == "reviewer"
                 and self.setting(principal)["mode"] != "OBSERVE")
        if allowed:
            plan = self._settlement_plan(principal, case)
            if plan is not None:
                decision, _ = plan
                label = "Record scoped simulated credit" if decision.action == "record-credit" else "Apply simulated credit to the matched eligible bill"
                offer = dict(id=decision.action, label=label)
                if principal.tenant != TENANT:
                    offer["mandate_credit"] = decision.model_dump()
                case["actions"].append(offer)
        case["financials"]=[dict(label=k.replace("_", " ").title(),value=usd(v),
                                sources=case["reconciliation"]["stage_sources"].get(k, CUSTOM if k=="estimated" else SIM))
                            for k,v in case["ledger"].items()]
        if principal.role != "reviewer" or self.setting(principal)["mode"] == "OBSERVE":
            case["actions"]=[]
        return case

    @staticmethod
    def _award_record(case):
        # Only the filed, approved packet and its authenticated award reply supply identity.
        replies=[r for r in case.get("replies", []) if r.get("reason")=="award"]
        if len(replies)!=1 or not case.get("submissions"):
            return None
        reply=replies[0]
        submission=next((s for s in case["submissions"] if s["id"]==reply["receipt"]), None)
        if submission is None or submission["approval"]["digest"]!=submission["digest"]:
            return None
        packet=submission["packet"]
        scope=packet["scope"]
        if (scope != case["scope"] or packet["tenant"] != case["tenant"]
                or fingerprint(packet) != submission["digest"]):
            return None
        record=dict(vendor_id=scope["vendor"], account_id=scope["account"], product_id=scope["service"],
                    contract_id=scope["contract"], contract_version=packet["version"], currency=scope["currency"],
                    id="inbox-award:"+reply["digest"], source_ref="inbox-reply:"+reply["digest"],
                    memo_ref=reply["event_id"], effective_date=reply["received_at"][:10],
                    amount=case["ledger"]["awarded"], source=Source.VENDOR.value, confirmed=True)
        return record if all(record.get(k) for k in SCOPE_FIELDS) else None

    def _application_bill(self, principal, record):
        if record["unapplied_posted_cents"]<=0 or len(record["credit_ids"])!=1:
            return None
        matches=[b for b in self.allocations.list_bills(principal.tenant)
                 if all(b["scope"][k]==record["scope"][k] for k in SCOPE_FIELDS)
                 and b["source"] in {Source.CUSTOMER.value, Source.REPLAY.value}
                 and b["remaining_eligible_cents"]>=record["unapplied_posted_cents"]]
        # Multiple eligible bills need an explicit selection; the generic action carries no bill ID.
        return matches[0] if len(matches)==1 else None

    def _settlement_plan(self, principal, case):
        """Compute both the reviewer-visible commitment and exact journal input from the same scoped records."""
        configured=getattr(self,'settlement_provider',None)
        if configured is not None and not configured.allows_case(case['id'],case['scope']):
            return None
        records = case["reconciliations"]
        if not records:
            award = self._award_record(case)
            if award is None:
                return None
            credit = {**award, "id":"inbox-credit:"+award["id"], "source_ref":"inbox-credit:"+award["source_ref"],
                      "award_id":award["id"], "source":Source.REPLAY.value}
            provider=getattr(self,'settlement_provider',None)
            if provider is not None:
                credit=provider.credit(principal.tenant,award,case_id=case['id'])
            plan = {"award":award, "credits":[credit]}
            amount = usd_cents(award["amount"])
            target = dict(action="record-credit", contract_version=award["contract_version"], award_id=award["id"],
                          credit_id=credit["id"], bill_id=None, journal_sequence=self.allocations.head())
        elif len(records)==1:
            record = records[0]
            bill = self._application_bill(principal, record)
            if bill is None or bill["as_of_sequence"] != record["as_of_sequence"]:
                return None
            amount = record["unapplied_posted_cents"]
            ident = "inbox-application:"+fingerprint([record["award_id"], bill["id"]])
            plan = dict(id=ident, source_ref=ident, credit_id=record["credit_ids"][0], bill_id=bill["id"],
                        source=Source.REPLAY.value, amount_cents=amount,
                        effective_date=max(record["effective_date"],bill["effective_date"]))
            provider=getattr(self,'settlement_provider',None)
            if provider is not None:
                plan=provider.application(principal.tenant,plan,case_id=case['id'])
            target = dict(action="apply-balance", contract_version=record["scope"]["contract_version"],
                          award_id=record["award_id"], credit_id=plan["credit_id"], bill_id=bill["id"],
                          journal_sequence=record["as_of_sequence"])
        else:
            return None
        decision = CreditDecision(claim_id=case["id"], currency=case["scope"]["currency"],
                                  scope_sha256=fingerprint(case["scope"]), claim_state_sha256=case["state_sha256"],
                                  plan_sha256=fingerprint(plan), amount_cents=amount, max_amount_cents=amount, **target)
        return decision, plan

    def _settle_inbox(self, principal, case, action):
        configured=getattr(self,'settlement_provider',None)
        if configured is not None and not configured.allows_case(case['id'],case['scope']):
            raise PermissionError('The configured settlement destination does not authorize this claim.')
        if action not in {a["id"] for a in case["actions"]}:
            # An exact completed action may be retried, but never create another record.
            if action=="record-credit" and case.get("reconciliations"):
                return
            if action=="apply-balance" and any(r["stage"]=="APPLIED" for r in case.get("reconciliations", [])):
                return
            raise ValueError("No authorized scoped settlement action is available.")
        resolved = self._settlement_plan(principal, case)
        if resolved is None or resolved[0].action != action:
            raise ValueError("Current scoped records cannot justify this allocation")
        decision, plan = resolved
        def verify(db):
            check_credit_decision(db, principal, decision)
        provider=getattr(self,'settlement_provider',None)
        confirm=(lambda:provider.confirm(principal.tenant,action,plan,case_id=case['id'])) if provider is not None else None
        if action == "record-credit":
            self.allocations.ingest(principal.tenant, case["id"], **plan, check_authority=verify,confirm=confirm)
        else:
            self.allocations.apply(principal.tenant, plan, check_authority=verify,confirm=confirm)

    def _present(self, case, *, versions=None):
        case=dict(case)
        if case.get("vendor_id") and case["id"].startswith("availability-"):
            try:
                identity = historical_economic_identity(self.path, self.tenant, case)
            except EconomicScopeReviewRequired as error:
                identity = None
                case.update(financial_scope_status="REVIEW_REQUIRED", financial_scope_reason=str(error),
                            recorded_stage=case.get("stage"), recorded_outcome=case.get("outcome"),
                            recorded_amount=case.get("amount"), stage="REVIEW_REQUIRED", outcome="INSUFFICIENT_EVIDENCE",
                            amount=None, actions=[])
            case["economic_identity"] = identity
            case["obligation_id"] = claim_key(**identity) if identity else None
            try:
                require_case_semantics(self.path, self.tenant, case,governing_fees=self.governing_fees,trusted_now=self.trusted_now)
            except (SemanticBindingRequired,GoverningFeeRequired) as error:
                case.update(financial_scope_status="REVIEW_REQUIRED", financial_scope_reason=str(error),
                            semantic_binding_status="REVIEW_REQUIRED", recorded_stage=case.get("recorded_stage",case.get("stage")),
                            recorded_outcome=case.get("recorded_outcome",case.get("outcome")),
                            recorded_amount=case.get("recorded_amount",case.get("amount")), stage="REVIEW_REQUIRED",
                            outcome="INSUFFICIENT_EVIDENCE", amount=None, actions=[],
                            financials=[dict(label="Current estimate", value="Semantic review required", sources=case.get("sources",[]))])
                if isinstance(error,GoverningFeeRequired):
                    case.pop('semantic_binding_status',None)
                    case['pricing_binding_status']='REVIEW_REQUIRED'
            if case.get('financial_scope_status') == 'REVIEW_REQUIRED':
                case = review_observation(case)
        case["cohort"]="seeded" if case["id"] in self.seed_ids else "portfolio"
        case.setdefault("note", "Seeded historical/comparison simulation; estimates are not additive portfolio value."
                        if case["cohort"]=="seeded" else "Entered workspace record; source labels determine whether facts are simulated or observed.")
        refs=[]
        for submission in case.get("submissions", []):
            refs.append(dict(kind="filing", id=submission["id"], digest=submission.get("digest"),
                             sources=submission.get("sources", SIM)))
        for reply in case.get("replies", []):
            refs.append(dict(kind="vendor_response", id=reply.get("event_id") or reply.get("receipt"),
                             digest=reply.get("digest"), sources=reply.get("sources", SIM)))
        for rec in case.get("reconciliations", [case.get("reconciliation", {})]):
            for field in ("award_id", "memo_ref", "source_ref", "credit_ids", "application_ids", "bill_ids"):
                value=rec.get(field)
                for ident in value if isinstance(value, list) else [value] if value else []:
                    stage={"award_id":"awarded", "memo_ref":"awarded", "source_ref":"awarded",
                           "credit_ids":"posted", "application_ids":"applied", "bill_ids":"applied"}[field]
                    refs.append(dict(kind=field, id=ident,
                                     sources=rec.get("stage_sources", {}).get(stage, rec.get("sources", SIM))))
        if case.get("provider_id"):
            refs.append(dict(kind="provider_bill", id=case["provider_id"], sources=case["sources"]))
        if versions:
            case["versions"]=[{k:r[k] for k in ("revision", "digest", "previous_digest", "observed_at")} for r in versions]
            case["revision"]=versions[-1]["revision"]
            refs.append(dict(kind="evaluation", id=versions[-1]["digest"], sources=case["sources"]))
        case["financial_refs"]=refs
        return case

    def case(self, principal, case_id):
        self.require_tenant(principal)
        workspace=getattr(self,"native_workspace",None)
        if workspace and case_id.startswith(("ramp-","rehearsal-cap-")):
            try:
                return self._present(workspace.detail(case_id))
            except KeyError:
                pass
        inbox=self._inbox_case(principal, case_id)
        if inbox is not None:
            return self._present(self._correspondence(principal, inbox))
        if any(c["id"]==case_id for c in self.desk.cases(principal)):
            return self._present(self.dispute(principal,case_id))
        for case in stored_cases(self.path,principal.tenant):
            if case["id"]==case_id:
                return self._present(case, versions=case_versions(self.path,principal.tenant,case_id))
        for case in self.pricing_probe(principal):
            if case["id"]==case_id:
                return self._present(case)
        raise KeyError(case_id)

    def act(self, principal, case_id, action):
        with self.mutex:
            self.check_write(principal)
            provider=getattr(self,'settlement_provider',None)
            if provider is not None and action in SETTLEMENT_ACTIONS and case_id!=provider.claim_id:
                raise PermissionError('The configured settlement destination does not authorize this case.')
            inbox=self._inbox_case(principal, case_id)
            if inbox is not None:
                if action in SETTLEMENT_ACTIONS:
                    self._settle_inbox(principal,self._correspondence(principal,inbox),action)
                else:
                    self.inbox.act(principal,case_id,action)
                return self.case(principal,case_id)
            if not any(c["id"]==case_id for c in self.desk.cases(principal)):
                self.case(principal,case_id)
                raise KeyError("No such action on an observation")
            if action in SETTLEMENT_ACTIONS:
                case=self.dispute(principal,case_id)
                completed={e["action"] for e in settlement_events(self.path,principal.tenant,case_id)}
                if action not in completed and action not in {a["id"] for a in case["actions"]}:
                    raise ValueError("No authorized settlement action is available.")
                transition_settlement(self.path,principal,case_id,action,case["ledger"]["awarded"])
            else:
                previous=self.desk.case(principal,case_id)["stage"]
                case=self.desk.act(principal,case_id,action)
                new_approval=previous=="DRAFTED" and case["stage"]=="CLAIM_APPROVED" and action=="approve-claim"
                if self.mode=="replay" and new_approval and policy.dispatch_allowed(case,self.setting(principal)):
                    self.desk.act(principal,case_id,"submit-claim")
            return self.case(principal,case_id)

    def dashboard(self, principal):
        self.require_tenant(principal)
        cases={c["id"]:self._present(c, versions=case_versions(self.path,principal.tenant,c["id"]))
               for c in stored_cases(self.path,principal.tenant)}
        cases.update({c["id"]:self._present(self.dispute(principal,c["id"])) for c in self.desk.cases(principal)})
        cases.update({c["id"]:self._present(c) for c in self.pricing_probe(principal)})
        inbox=getattr(self, "inbox", None)
        if inbox is not None:
            cases.update({c["id"]:self._present(self._correspondence(principal,c)) for c in inbox.cases(principal)})
        cases=list(cases.values())
        columns=("id","vendor","title","outcome","stage","amount","currency","sources","note","cohort",
                 "financials","financial_refs","revision","payment_status","obligation_id","source_sha256",
                 "source_received_at","source_currentness")
        summary=lambda c:{k:c[k] for k in columns if k in c}
        cohorts={}
        for key,label in (("portfolio", "Entered portfolio and saved sandbox observations"),
                          ("seeded", "Seeded historical and comparison simulations")):
            members=[c for c in cases if c["cohort"]==key]
            cohorts[key]=dict(label=label, sources=_sources(c["sources"] for c in members) or [Source.UNAVAILABLE.value],
                             metrics=_metrics(members), cases=[summary(c) for c in members])
        audit=[dict(at=e["at"],event=e["event"],case_id=c["id"],sources=e["sources"])
               for c in cases for e in c.get("timeline",[])]
        ramp=self.ramp()
        return dict(workspace="Bears finance lab" if self.tenant == TENANT else self.tenant,as_of=ramp.get("observed_at") or "Deterministic replay",
                    role=principal.role,mode=self.mode,metrics=_metrics(cases), cohorts=cohorts,
                    cases=[summary(c) for c in cases],
                    audit=sorted(audit,key=lambda e:e["at"] or "",reverse=True)[:24],ramp=ramp,
                    real_recovery="No verified customer recovery",actual_applied=None)

    def integrations(self, principal):
        self.require_tenant(principal)
        return dict(ramp=self.ramp(),public_evidence=evidence_summary(),model=model_card(),
                    vendor_transport="SIMULATED_VENDOR",sources=[Source.REPLAY.value])
