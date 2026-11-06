"""The companion workbench reads verified Ramp observations. Only the operator imports new records."""
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi import Depends

from .contracts import Source, fingerprint
from .storage import case_versions, database, persist_case
from .ramp import ORIGIN, RampError, uuid_text
from .ramp_records import load_snapshot, _validate_snapshot
from .ramp_findings import evaluate_snapshot
from .ramp_credit_sync import RampCreditSync
from .ramp_terms_store import RampTermsStore

ROOT = Path(__file__).resolve().parents[1]
PACKAGED = ROOT / "fixtures/ramp/native-observed.json"
PROOF = ROOT / "docs/v4/evidence/ramp-discovery.json"
COLUMNS = ("id","title","vendor","stage","outcome","amount","currency","sources","provider_object_type",
           "provider_id","provider_uri","native_status","native_approval_status","native_amount",
           "finding_kind","finding_digest","data_provenance","trace","actual_recovery","publishable")


def _raw_money(money):
    if money is None:
        return None
    return {"amount":money["amount_minor"],"currency_code":money["currency"],
            "minor_unit_conversion_rate":money["minor_unit_conversion_rate"]}


def _links(rows, output_key, input_key):
    if rows is None:
        return None
    return [{output_key:r[input_key],"amount":_raw_money(r["amount"])} for r in rows]


def credit_observation(snapshot, provider_business_id=None):
    """Project canonical readbacks into the documented bill/credit pair. Carry nulls across.

    provider_business_id is the caller's already validated business context (not
    OAuth proof). Unknown stays omitted so unscoped observation digests are unchanged.
    """
    resources=snapshot["resources"]
    credits=resources["credits"]
    bills=resources["bills"]
    credit_rows=[{"id":r["id"],"vendor_id":r["vendor_id"],"entity_id":r["entity_id"],
                  "reference_bill_id":r["reference_bill_id"],"accounting_date":r["accounting_date"],
                  "archived_at":r["archived_at"],"total_amount":_raw_money(r["total"]),
                  "remaining_amount":_raw_money(r["remaining"]),"total_applied_amount":_raw_money(r["total_applied"]),
                  "applied_bills":_links(r["applied_bills"],"bill_id","bill_id"),
                  "applied_draft_bills":_links(r["applied_drafts"],"bill_id","bill_id")} for r in credits["records"]]
    bill_rows=[{"id":r["id"],"vendor":{"id":r["vendor_id"]},"entity_id":r["entity_id"],
                "issued_at":r["issued_at"],"archived_at":r["archived_at"],"status":r["status"],
                "amount":_raw_money(r["amount"]),"applied_vendor_credits":_links(r["applied_credits"],"id","credit_id")}
               for r in bills["records"] if r["kind"]=="bill"]
    accepted={"COMPLETE","EMPTY","PARTIAL","TRUNCATED"}
    granted=sorted(set((credits.get("grant") or {}).get("granted",[]))|set((bills.get("grant") or {}).get("granted",[])))
    result=dict(id=snapshot["checksum"],observed_at=snapshot["observed_at"],source=Source.RAMP.value,
                provenance_ref="sha256:"+snapshot["checksum"],scopes=granted,
                available=credits["status"] in accepted,list_complete=credits["complete"],credits=credit_rows,bills=bill_rows)
    if provider_business_id is not None:
        result["provider_business_id"]=provider_business_id
    return result


class RampWorkspace:
    def __init__(self, bench, *, award_office=None):
        self.bench=bench
        self.path=bench.path
        self.tenant=bench.tenant
        self.mode=bench.mode
        with database(self.path) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS native_installation (
                tenant TEXT PRIMARY KEY, business_id TEXT NOT NULL UNIQUE)""")
            db.execute("""CREATE TABLE IF NOT EXISTS native_capture (
                tenant TEXT NOT NULL, digest TEXT NOT NULL, observed_at TEXT NOT NULL, snapshot TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','ready')),
                PRIMARY KEY(tenant,digest))""")
        self.credits=RampCreditSync(self.path)
        self.terms = RampTermsStore(self.path)
        self.native_binding = None
        self.awards = None
        if award_office is not None:
            from .ramp_award_attribution import AwardAttributionStore, load_office_config
            config = load_office_config(award_office)
            _, custody, business = self._observation()
            if (self.mode != "sandbox" or custody != "operator_import" or
                    (config.tenant, config.business_id) != (self.tenant, business)):
                raise ValueError("Award verification office must match the installed sandbox business")
            self.awards = AwardAttributionStore(self.path, config)

    def import_observation(self, snapshot, business_id):
        """Publish an import after the idempotent credit projection succeeds. Retrying resumes an interrupted import."""
        if self.mode != "sandbox":
            raise ValueError("Live observations require a sandbox installation")
        uuid_text(business_id)
        if not UUID(business_id).int:
            raise ValueError("Nonzero Ramp business required")
        _validate_snapshot(snapshot)
        data=json.dumps(snapshot,sort_keys=True,separators=(",",":"),allow_nan=False)
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO native_installation VALUES(?,?)",(self.tenant,business_id))
            row=db.execute("SELECT business_id FROM native_installation WHERE tenant=?",(self.tenant,)).fetchone()
            if row is None or row[0]!=business_id:
                raise ValueError("This workspace already belongs to a different Ramp business")
            existing=db.execute("SELECT status,snapshot FROM native_capture WHERE tenant=? AND digest=?",
                                (self.tenant,snapshot["checksum"])).fetchone()
            if existing and existing["snapshot"] != data:
                raise ValueError("Conflicting observations under one capture digest")
            if existing and existing["status"] == "ready":
                return {"digest":snapshot["checksum"],"status":"ready","observed_at":snapshot["observed_at"],"duplicate":True}
            db.execute("INSERT OR IGNORE INTO native_capture VALUES(?,?,?,?,'pending')",
                       (self.tenant,snapshot["checksum"],snapshot["observed_at"],data))
        self.credits.import_snapshot(self.tenant,credit_observation(snapshot,business_id))
        cases=evaluate_snapshot(snapshot,as_of=datetime.fromisoformat(snapshot["completed_at"]))
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            latest=db.execute("SELECT observed_at FROM native_capture WHERE tenant=? AND status='ready' ORDER BY observed_at DESC LIMIT 1",
                              (self.tenant,)).fetchone()
            if latest is None or datetime.fromisoformat(latest[0]) <= datetime.fromisoformat(snapshot["observed_at"]):
                for case in cases:
                    persist_case(db,self.tenant,case)
            db.execute("UPDATE native_capture SET status='ready' WHERE tenant=? AND digest=?",
                       (self.tenant,snapshot["checksum"]))
        return {"digest":snapshot["checksum"],"status":"ready","observed_at":snapshot["observed_at"],"records":len(cases)}

    def _observation(self):
        with database(self.path) as db:
            row=db.execute("""SELECT c.snapshot,i.business_id FROM native_capture c
                JOIN native_installation i ON i.tenant=c.tenant
                WHERE c.tenant=? AND c.status='ready' ORDER BY c.observed_at DESC,c.rowid DESC LIMIT 1""",(self.tenant,)).fetchone()
        if row:
            data=json.loads(row[0])
            _validate_snapshot(data)
            return data,"operator_import",row[1]
        if self.tenant=="bears" and PACKAGED.is_file():
            data=load_snapshot(PACKAGED)
            if data.get("snapshot_status",{}).get("integrity")=="CHECKSUM_VERIFIED":
                return data,"packaged_receipt",None
        return None,"unavailable",None

    def _view(self):
        snapshot,custody,business=self._observation()
        if snapshot is None:
            return None,[],custody,business
        observed=datetime.fromisoformat(snapshot["observed_at"])
        as_of=datetime.fromisoformat(snapshot["completed_at"]) if self.mode=="replay" else datetime.now(UTC)
        fresh=timedelta(0)<=as_of-observed<=timedelta(hours=24)
        status={"integrity":"CHECKSUM_VERIFIED","freshness":"HISTORICAL_REPLAY" if self.mode=="replay" else "FRESH" if fresh else "STALE",
                "custody":custody,"external_writes":False}
        bindings, omissions = self._bindings(snapshot, custody, business)
        rows=evaluate_snapshot(snapshot,bindings=bindings,as_of=as_of)
        simulated = {b.object_id for b in bindings if b.terms_mode == "SYNTHETIC_NEGOTIATED"}
        if simulated:
            rows.extend(r for r in evaluate_snapshot(snapshot,as_of=as_of)
                        if r["provider_object_type"] == "bills" and r["provider_id"] in simulated)
        status["price_terms"]={"verified_bindings":len(bindings),"omissions":omissions}
        for row in rows:
            row.update(workspace_tenant=self.tenant,business_id=business,capture_mode=custody,mode=self.mode,
                       observed_at=snapshot["observed_at"],actual_recovery=None)
            row["sources"]=list(dict.fromkeys([*row["sources"],Source.REPLAY.value]))
        return dict(snapshot,status=status),rows,custody,business

    def _bindings(self, snapshot, custody, business):
        if self.mode != "sandbox" or custody != "operator_import" or business is None:
            return (), []
        return self.terms.resolve(self.tenant, business, snapshot)

    def record_for_native(self,object_type,object_id):
        snapshot,custody,business = self._observation()
        if (self.mode != "sandbox" or custody != "operator_import" or business is None
                or snapshot is None or object_type != "bills"):
            raise PermissionError("A current installed sandbox bill observation is required")
        now=datetime.now(UTC)
        observed=datetime.fromisoformat(snapshot["observed_at"])
        completed=datetime.fromisoformat(snapshot["completed_at"])
        if not observed <= completed <= now <= observed+timedelta(hours=24):
            raise PermissionError("Capture expired or after the decision clock")
        bindings, _ = self._bindings(snapshot, custody, business)
        actual = tuple(b for b in bindings if b.object_id == object_id and b.terms_mode == "OPERATOR_ATTESTED")
        if actual:
            reviewed = next((r for r in evaluate_snapshot(snapshot, bindings=actual, as_of=now)
                             if r["provider_object_type"] == object_type and r["provider_id"] == object_id), None)
            if (reviewed and reviewed["data_provenance"]["classification"] == "PROVIDER_WITH_OPERATOR_EVIDENCE"
                    and reviewed["native_status"] == "OPEN" and reviewed["outcome"] == "ELIGIBLE"
                    and reviewed["amount"] is not None and Decimal(reviewed["amount"]) > 0):
                return dict(reviewed, workspace_tenant=self.tenant,business_id=business,observed_at=snapshot["observed_at"],
                            capture_mode=custody, native_review_reason="ATTESTED_PRICE_EXCEPTION",
                            price_outcome="PRICE_EXCEPTION", terms_provenance={
                                "mode":"OPERATOR_ATTESTED","integrity":"VERIFIED","operator_context_verified":True,
                                "digest":actual[0].terms_evidence_digest})
        rows=evaluate_snapshot(snapshot, as_of=completed)
        for record in rows:
            if record["provider_object_type"]==object_type and record["provider_id"]==object_id:
                if (record["sources"] != [Source.RAMP.value] or record["amount"] is not None
                        or record["data_provenance"]["classification"] != "PROVIDER_OBSERVATION"):
                    raise PermissionError("Native informational review requires a factual observation")
                return dict(record, workspace_tenant=self.tenant,business_id=business,observed_at=snapshot["observed_at"],
                            finding_kind="NATIVE_OBSERVATION", capture_mode=custody, native_review_reason="EVIDENCE_REQUIRED")
        raise KeyError(object_id)

    def _cap_case(self,snapshot):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        proof_path=ROOT/"fixtures/ramp/native-cap-binding.json"
        if self.tenant!="bears" or not proof_path.is_file() or snapshot is None:
            return None
        from .ramp_cap import InvoiceCapScope, evaluate_invoice_cap
        proof=json.loads(proof_path.read_text())
        if proof["capture_digest"]!=snapshot["checksum"]:
            return None
        bill=next((r for r in snapshot["resources"]["bills"]["records"] if r["id"]==proof["bill_id"] and r["kind"]=="bill"),None)
        if bill is None:
            return None
        public=Ed25519PublicKey.from_public_bytes(bytes.fromhex(proof["scripted_public_verifier"]))
        scope=InvoiceCapScope(tenant_id=self.tenant,binding=proof["binding"],trusted_operator_keys={proof["operator_id"]:public})
        at=datetime.fromisoformat(snapshot["completed_at"]) if self.mode=="replay" else datetime.now(UTC)
        terms=json.loads((ROOT/"fixtures/ramp/native-cap-terms.json").read_text())
        raw={k:v for k,v in snapshot.items() if k not in {"status","snapshot_status"}}
        case=evaluate_invoice_cap(raw,bill,terms,as_of=at,scope=scope)
        if case.get("kind")!="case":
            return None
        case.update(id="rehearsal-cap-"+bill["id"],provider_id=bill["id"],provider_object_type="bills",
                    native_status=bill["status"],native_approval_status=bill["approval_status"],actual_recovery=None,
                    observed_at=snapshot["observed_at"],mode=self.mode)
        return case

    def detail(self,case_id):
        snapshot,rows,_,_=self._view()
        case=next((c for c in rows if c["id"]==case_id),None)
        if case is None and case_id.startswith("rehearsal-cap-"):
            cap=self._cap_case(snapshot)
            if cap and cap["id"]==case_id:
                case=cap
        if case is None:
            raise KeyError(case_id)
        provenance=case.get("data_provenance",{})
        record_digest=provenance.get("record_digest") if isinstance(provenance,dict) else None
        source = next((r for value in snapshot["resources"].values() for r in value["records"]
                       if r["id"] == case["provider_id"] and fingerprint(r) == record_digest),None)
        projection={k:source.get(k) for k in ("id","kind","vendor_id","entity_id","status","approval_status",
                    "amount","issued_at","purchase_order_id","bill_ids","reciprocal_bill_ids","merchant_id") if source and k in source}
        if not projection and case.get("finding_kind")=="SYNTHETIC_INVOICE_CAP":
            projection={"id":case["provider_id"],"kind":"bill","amount":case["native_amount"]}
        case["native_projection"]=projection
        case["native_workflow"]=self._plan(case)
        native_case_id=f"ramp-{case['provider_object_type']}-{case['provider_id']}"
        revisions=(case_versions(self.path,self.tenant,native_case_id)
                   if snapshot["status"]["custody"]=="operator_import" else [])
        case["native_audit"]={
            "capture_digest":snapshot["checksum"],"observed_at":snapshot["observed_at"],
            "custody":snapshot["status"]["custody"],
            "record_digest":record_digest,
            "calculation_digest":case.get("finding_digest"),
            "terms_binding_digest":provenance.get("binding_digest") if isinstance(provenance,dict) else None,
            "import_revisions":[{"revision":r["revision"],"digest":r["digest"]} for r in revisions],
        }
        return case

    def workflow(self,case_id):
        return self._plan(self.detail(case_id))

    @staticmethod
    def _plan(case):
        obj=case["provider_object_type"]
        destination=case["provider_id"]
        supported=obj in {"bills","draft-bills","transactions"}
        simulated=Source.CUSTOMER.value in case.get("sources",[])
        enabled_surface=obj=="bills" and not simulated
        return {"object_type":obj,"object_id":destination,"finding_digest":case.get("finding_digest"),
                "method":"POST" if supported else None,"path":f"/developer/v1/comments/{obj}/{destination}" if supported else None,
                "status":"SIMULATION_ONLY" if simulated else "REVIEW_REQUIRED" if enabled_surface else "SUPPORTED_PROVIDER_ONLY" if supported else "NO_DISCUSSION_ENDPOINT",
                "required_scope":("transactions:write" if obj=="transactions" else "bills:write") if supported else None,
                "delivery":"NOT_SENT","approval_trigger_instance_id":None,"sources":case["sources"],
                "note":"A signed exact-object decision and current provider grant are required to publish. A native comment supplies review evidence.",
                "actual_money_prevented":None,"actual_recovery":None}

    def overview(self):
        snapshot,rows,custody,business=self._view()
        cap=self._cap_case(snapshot)
        if cap:
            rows=[cap,*rows]
        state=self.credits.summary(self.tenant)
        attribution=(self.awards.summary(self.tenant,business) if self.awards else
                     {"status":"NO_VERIFICATION_OFFICE","actual_recovery":None,"external_writes":False})
        receipt=json.loads(PROOF.read_text()) if PROOF.exists() and self.tenant=="bears" else {}
        grants=receipt.get("scope_grants",{})
        return dict(source_mode="UNAVAILABLE" if snapshot is None else "REPLAY_OF_RAMP_SANDBOX" if self.mode=="replay" else "SAVED_RAMP_SANDBOX_READ",
                    as_of=snapshot["observed_at"] if snapshot else None,snapshot_status=snapshot["status"] if snapshot else {"custody":custody},
                    resources=[dict(name=name,status=r["status"],complete=r["complete"],count=len(r["records"]),issues=r["issues"])
                               for name,r in (snapshot or {}).get("resources",{}).items()],
                    records=[{k:c.get(k) for k in COLUMNS} for c in rows],
                    credit_sync={"journal":state,"captured_credits":len(snapshot["resources"]["credits"]["records"])
                                 if snapshot and snapshot["resources"]["credits"]["status"] in {"COMPLETE","EMPTY","PARTIAL","TRUNCATED"} else None,
                                 "verified_award_attribution":attribution,
                                 "attributable_real_recovery":None},
                    writeback={"scope_receipt_at":receipt.get("observed_at"),"comment":grants.get("bills:write","NOT_MEASURED"),
                               "blank_canvas":grants.get("blank_canvas:write","NOT_MEASURED"),"mode":"requires exact reviewed permission",
                               "actual_writes":0 if not getattr(self,"native_binding",None) else "See exact-object delivery receipts","registered_active_trigger":None},
                    portfolio_note="Ramp records own financial status. Separate Uptime evidence and hypothetical findings carry their source labels.")


def register_ramp_workspace(app,bench,auth,*,award_office=None):
    workspace=RampWorkspace(bench,award_office=award_office)
    app.state.ramp_workspace=bench.native_workspace=workspace

    @app.get("/api/ramp/workspace")
    def overview(principal=Depends(auth.actor)):
        bench.require_tenant(principal)
        return workspace.overview()

    @app.get("/api/ramp/records/{case_id}/workflow")
    def workflow(case_id:str,principal=Depends(auth.actor)):
        bench.require_tenant(principal)
        return workspace.workflow(case_id)

    @app.get("/api/ramp/records/{case_id}")
    def detail(case_id:str,principal=Depends(auth.actor)):
        bench.require_tenant(principal)
        return workspace.detail(case_id)
    return workspace
