"""Keys, reports and oracle pins here are disposable verifier test inputs."""
import copy
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import subprocess
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from scripts import v4_audit_gate as audit
from uptime import gates as g


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(g.canonical(obj))
    return g.digest(path.read_bytes())


class Bundle:
    def __init__(self, tmp):
        self.root = tmp/"build"
        self.evidence = self.root/"docs/v4/evidence"
        self.trust = tmp/"authority"/"trust.json"
        self.native = tmp/"authority"/"native.json"
        self.receipt = self.evidence/"release_attestation.json"
        for name in ["scripts/v4_audit_gate.py", "scripts/blind_acceptance.py", "scripts/release_regression.py",
                     *(str(p.relative_to(g.ROOT)) for p in (g.ROOT/"tests").glob("test_v4_audit_*.py"))]:
            dst = self.root/name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(g.ROOT/name,dst)
        for name in (*audit.SYNTHETIC_INPUTS, "uptime/a.py", "web/entry.test.cjs", "web/index.html", "pyproject.toml", "uv.lock"):
            p = self.root/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("fixture")
        self.git("init","-q")
        self.git("add",".")
        self.commit()
        self.source = g.source_identity(self.root)
        self.keys = {r:Ed25519PrivateKey.generate() for r in g.ACTORS}
        self.policy = {"schema":"uptime-release-trust/1", "roles":{r:{
            "subject":"witness-"+r,"actor_type":g.ACTORS[r],"public_key":k.public_key().public_bytes_raw().hex()}
            for r,k in self.keys.items()}, "campaign":"a"*64}
        self.now = int(time.time())-1
        self.record = {"schema":"uptime-v4-release/2","scope":"local-simulation","source":self.source,"gates":{}}
        self.iso = datetime.fromtimestamp(self.now, UTC).isoformat()
        self.reports = {"security_financial":self.audit(), "regression":self.regression(), "unseen_vendor":self.blind()}
        self.reports["unanticipated_dispute"] = copy.deepcopy(self.reports["unseen_vendor"])
        self.policy["blind"]["comparison_sha256"] = g.comparison_coverage(self.reports["unseen_vendor"]["comparison"])
        self.sign()
        self.save_trust()

    def git(self,*args):
        subprocess.run(["git","-C",str(self.root),*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def commit(self):
        self.git("-c","user.name=Verifier control","-c","user.email=control@example.invalid","commit","-qm","control")

    def proof(self, role, binding):
        p = {"issued_at":self.now,"expires_at":self.now+3600,"campaign":self.policy["campaign"],"attempt":1}
        data = g.signing_bytes(role,self.policy["roles"][role]["subject"],self.source,binding,**p)
        return {**p,"signature":self.keys[role].sign(data).hex()}

    def save_trust(self):
        write(self.trust,self.policy)
        self.trust.chmod(0o600)

    def sign(self):
        hashes = {}
        for role, data in self.reports.items():
            path = self.evidence/(role+".json")
            hashes[role] = write(path,data)
            self.record["gates"][role] = {"sha256":hashes[role],"path":str(path.relative_to(self.root)),
                                          "proof":self.proof(role,hashes[role])}
        self.review = {"scope":"local-simulation","gates":hashes}
        self.record[g.REVIEW] = self.proof(g.REVIEW,self.review)
        write(self.receipt,self.record)

    def audit(self):
        rs = [dict(id=ident,status="PASS",execution="OBSERVED",observed="2.70",expected="2.70",
                   assertion_source="independent-audit-and-known-mutation") for ident in sorted(audit.required_ids())]
        before = {"schema":audit.SCHEMA,"phase":"baseline","release_pass":False,"source_stable":True,"driver_stable":True,
                  "audit_provenance":audit.AUDIT_PROVENANCE,"source":{"commit":audit.V3,"materialization":"git archive of exact immutable V3 commit"},
                  "baseline_commit":audit.V3,"gate_code":audit.gate_identity(),"results":copy.deepcopy(rs)}
        before["results"][0].update(status="FAIL",observed="2.69")
        self.policy["baseline_sha256"] = write(self.evidence/"security-baseline.json",before)
        transitions,ok = audit.compare_before(before,rs)
        assert ok
        return {"schema":audit.SCHEMA,"phase":"release","baseline_verified":True,"baseline_error_type":None,
                "release_pass":True,"source_stable":True,"driver_stable":True,"baseline_commit":audit.V3,
                "source":{"commit":self.source["commit"],"changed_tracked_paths":[],"product_source_sha256":audit.product_hash(self.root)},
                "gate_code":audit.gate_identity(),"synthetic_input_sha256":audit.input_identity(self.root),
                "required_ids":sorted(audit.required_ids()),"primary_coverage":audit.PRIMARY,"audit_provenance":audit.AUDIT_PROVENANCE,
                "results":rs,"before_after":transitions,"counts":{"PASS":len(rs)},"generated_at":self.iso}

    def regression(self):
        self.policy["regression"] = {s:{"count":2,"collection_sha256":"b"*64} for s in ("pytest","node")}
        return {"schema":"uptime-full-regression/1","source":self.source,"source_stable":True,"generated_at":self.iso,
                "runner_sha256":g.digest((self.root/"scripts/release_regression.py").read_bytes()),**{
                    s:{"collected":2,"counts":{"passed":2},"collection_sha256":"b"*64,"exit_code":0,
                       **({"files":["web/entry.test.cjs"]} if s=="node" else {})} for s in ("pytest","node")}}

    def blind(self):
        key = "c"*64
        self.policy["blind"] = pin = {"case_count":1,"disputes":{key:{"stage":"RESPONSE_DRAFTED","amount":"7.00"}},
            **{f:"d"*64 for f in ("fixture_manifest_sha256","input_plan_sha256","public_source_sha256")}}
        observation = {"case_sha256":key,"fail_codes":[],"candidate_state":"ACTIVE","independent_lifecycle":{
            "authority":"SCRIPTED_LOCAL_SYNTHETIC","human_authority":False,"controls":[{"passed":True,"readback_sha256":key,
            "scenario_sha256":h*64,"observed":{"available":True,"outcome":o,"amount":a}}
            for h,o,a in [("a","ELIGIBLE","7.00"),("b","INELIGIBLE",None)]]},
            "generality":{"checks":[{"message_sha256":key,"fail_codes":[],"delivered":True,
                                     "observed":{"available":True,"stage":"RESPONSE_DRAFTED","amount":"7.00"}}],
                          "required_count":1,"delivered_count":1}}
        chk = {"status":"PASS","field_sha256":key}
        return {"protocol":"blind-acceptance/2","transport":"socket","network_proof":True,"authority":"SCRIPTED_LOCAL_SYNTHETIC",
                "commercial_authority":False,"gate_2_pass":True,"gate_3_pass":True,"fail_codes":[],"product":{
                    "commit":self.source["commit"],"tree_sha256":g.legacy_digest({"uptime/a.py":g.digest(b"fixture")}),"files_count":1},
                "runner_sha256":g.digest((self.root/"scripts/blind_acceptance.py").read_bytes()),"observations":[observation],
                "observations_sha256":g.legacy_digest([observation]),"counts":{"cases":1},"check_counts":{"PASS":3},
                "comparison":{"terms":[{**chk,"feature":"contract_terms"}],"cases":[{"case_sha256":key,"checks":[
                    {**chk,"feature":"decision"},{**chk,"feature":"money","expected_money":"7.00","observed_money":"7.00"}]}]},
                **{k:v for k,v in pin.items() if k.endswith("sha256")},"at":self.iso}

    def ready(self):
        return g.release_status(self.root,trust_path=self.trust)["ready"]


@pytest.fixture
def bundle(tmp_path):
    return Bundle(tmp_path)


def test_missing_current_trust_and_legacy_blobs_are_closed(tmp_path,bundle):
    assert not g.release_status(tmp_path)["ready"]
    write(bundle.receipt,{"schema":"uptime-v4-release/1","scope":"local-simulation","gates":bundle.record["gates"]})
    assert not bundle.ready()
    bundle.reports["security_financial"] = {"executed":True}
    bundle.sign()
    assert not bundle.ready()


def test_all_evidence_and_separate_roles_are_required_and_evidence_commit_is_non_circular(bundle):
    assert bundle.ready()
    bundle.git("add","docs/v4/evidence")
    bundle.commit()
    assert bundle.ready()
    (bundle.root/"uptime/a.py").write_text("changed")
    assert not bundle.ready()


@pytest.mark.parametrize("tamper", ["expired","stale_report","future_report","attempt","wrong_build","code_added","changed_fixture",
                                    "outside","swap_role","same_key","scripted_human","no_human","revoked","old_campaign","bad_baseline",
                                    "digest","available_count","ambiguous_scope","terms_missing","money","wrong_stage","holdout",
                                    "unseen_refused","no_message","asgi","unknown","pytest_subset","failed_js","empty_tests","hybrid"])
def test_signed_false_positive_controls(bundle,tamper):
    b=bundle
    audit_r=b.reports["security_financial"]
    blind=b.reports["unseen_vendor"]
    dispute=b.reports["unanticipated_dispute"]
    regression=b.reports["regression"]
    if tamper=="expired": b.now -= 86500
    elif tamper=="stale_report": audit_r["generated_at"]="2000-01-01T00:00:00+00:00"
    elif tamper=="future_report": blind["at"]="2099-01-01T00:00:00+00:00"
    elif tamper=="wrong_build": audit_r["source"]["commit"]="a"*40
    elif tamper=="code_added": (b.root/"uptime/injected.py").write_text("...")
    elif tamper=="changed_fixture": (b.root/audit.SYNTHETIC_INPUTS[0]).write_text("different")
    elif tamper=="swap_role": b.keys[g.REVIEW]=b.keys["regression"]
    elif tamper=="same_key": b.policy["roles"][g.REVIEW]["public_key"]=b.policy["roles"]["regression"]["public_key"]
    elif tamper=="scripted_human": b.policy["roles"][g.REVIEW]["actor_type"]="SCRIPTED"
    elif tamper=="bad_baseline": (b.evidence/"security-baseline.json").write_text("{}")
    elif tamper=="available_count": audit_r["results"][0]["status"]="UNAVAILABLE"
    elif tamper=="ambiguous_scope": blind["commercial_authority"]=True
    elif tamper=="terms_missing": blind["comparison"]["terms"]=[]
    elif tamper=="money": blind["comparison"]["cases"][0]["checks"][1]["observed_money"]="7.01"
    elif tamper=="wrong_stage": dispute["observations"][0]["generality"]["checks"][0]["observed"]["stage"]="AWARDED"
    elif tamper=="holdout": blind["fixture_manifest_sha256"]="e"*64
    elif tamper=="unseen_refused": blind["observations"][0]["candidate_state"]="QUARANTINED"
    elif tamper=="no_message": dispute["observations"][0]["generality"]={"checks":[],"required_count":0,"delivered_count":0}
    elif tamper=="asgi": blind["transport"]="asgi"
    elif tamper=="unknown": blind["comparison"]["cases"][0]["checks"][1]["expected_money"]=None
    elif tamper=="pytest_subset": regression["pytest"]["collection_sha256"]="f"*64
    elif tamper=="failed_js": regression["node"]["counts"]={"passed":1,"failed":1}
    elif tamper=="empty_tests": regression["pytest"]["collected"]=0
    elif tamper=="hybrid": audit_r["results"][0]["expected"]="2.71"
    for item in (blind,dispute):
        item["observations_sha256"]=g.legacy_digest(item["observations"])
    b.sign()
    if tamper=="outside": b.record["gates"]["regression"]["path"]="../elsewhere"
    elif tamper=="digest": b.record["gates"]["regression"]["sha256"]="e"*64
    elif tamper=="no_human": del b.record[g.REVIEW]
    elif tamper=="attempt": b.record["gates"]["regression"]["proof"]["attempt"]=2
    elif tamper=="old_campaign": b.policy["campaign"]="c"*64
    elif tamper=="revoked": del b.policy["roles"]["regression"]
    b.save_trust()
    write(b.receipt,b.record)
    assert not b.ready()


def test_native_grant_must_be_separate_and_match_exact_installation(bundle):
    b=bundle
    installation={"workspace_id":"realm","tenant":"tenant","business_id":"business","config_sha256":"c"*64}
    kwargs={"root":b.root,"trust_path":b.trust,"grant_path":b.native}
    assert b.ready() and not g.native_install_ready(installation,**kwargs)
    bind={**installation,"release_sha256":g.digest(g.canonical(b.review)),"environment":"sandbox","action":"bill.comment.create"}
    grant={"schema":"uptime-native-release/1","source":b.source,"binding":bind,"proof":b.proof(g.NATIVE,bind)}
    write(b.native,grant)
    b.native.chmod(0o600)
    assert g.native_install_ready(installation,**kwargs)
    for k in installation:
        assert not g.native_install_ready({**installation,k:"other"},**kwargs)
    grant["proof"]=b.proof(g.REVIEW,bind)
    write(b.native,grant)
    assert not g.native_install_ready(installation,**kwargs)


def test_missing_protected_registration_cannot_authorize_running_checkout(tmp_path):
    assert not g.release_status(trust_path=tmp_path/"absent.json")["ready"]
