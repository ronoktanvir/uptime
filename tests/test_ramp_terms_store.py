"""Offline Ed25519 finance attestation on a synthetic capture built by the ordinary Ramp importer."""
from copy import deepcopy
from datetime import UTC,datetime,timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from time import time
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from uptime.auth import bind_workspace
from uptime.ramp_findings import evaluate_snapshot
from uptime.ramp_records import seal_snapshot,sync_records
from uptime.ramp_terms_store import EvidenceError,FinanceKey,RampTermsStore,TermsPacket
from uptime.ramp_workspace import RampWorkspace
from uptime.workbench import Workbench
from test_ramp_records_v4 import Reader,BILL,VENDOR,ENTITY,LINE,money,uid

TENANT="fixture-west"
BIZ=uid(800)
CLI=Path(__file__).resolve().parents[1]/"scripts/ramp_bind_terms.py"


def private(path,data):
    path.write_bytes(data)
    path.chmod(0o600)
    return path


def blob(directory,data):
    digest=sha256(data).hexdigest()
    private(directory/digest,data)
    return digest


@pytest.fixture
def custody(tmp_path):
    db=tmp_path/"installed.sqlite"
    bind_workspace(db,"sandbox",False,TENANT)
    ws=RampWorkspace(Workbench(db,"sandbox",tenant=TENANT))
    reader=Reader()
    raw=reader.rows["bills"][0]
    raw["amount"]=money(12000)
    raw["inventory_line_items"][0].update(quantity=2,unit_price=money(6000),amount=money(12000))
    raw["issued_at"]="2026-11-01T00:00:00Z"
    snap=sync_records(reader)
    ws.import_observation(snap,BIZ)
    return db,ws,snap


def package(tmp_path,custody,mode="SYNTHETIC_NEGOTIATED"):
    db,_,snap=custody
    store=RampTermsStore(db)
    info=store.describe(TENANT,BIZ,BILL)
    signer=Ed25519PrivateKey.generate()
    key=FinanceKey(subject="fixture.finance",public_key=signer.public_key().public_bytes_raw().hex(),tenant=TENANT,
                   workspace_id=info["workspace_id"],business_id=BIZ,vendor_id=VENDOR,entity_id=ENTITY,mode=mode)
    directory=tmp_path/"evidence"
    directory.mkdir(mode=0o700)
    contract=blob(directory,b"Private synthetic control fixture: USD 40 per seat, graduated whole units.")
    mapping=blob(directory,b"Private fixture: complete two-seat October service line, zero tax.")
    at=int(time())
    packet=TermsPacket(schema_version="uptime-ramp-price-evidence/1",package_id=str(uuid4()),tenant=TENANT,
        workspace_id=info["workspace_id"],business_id=BIZ,issuer=key.subject,mode=mode,issued_at=at,expires_at=at+300,
        evaluator_sha256=info["evaluator_sha256"],capture_digest=snap["checksum"],bill_id=BILL,bill_digest=info["bill_digest"],
        vendor_id=VENDOR,entity_id=ENTITY,agreement_id="private-control",agreement_expires="2027-01-01T00:00:00Z",
        versions=[dict(version="version.1",effective_at="2026-01-01T00:00:00Z",signed_at="2025-12-30T00:00:00Z",
                  signatories=[ENTITY,VENDOR],supersedes=None,rates=[dict(product="seat",unit="unit",tiers=[dict(upper=None,rate="40")])],
                  excluded_products=[],contract_sha256=contract,section="section-3")],
        mappings=[dict(line_id=LINE,line_digest=info["lines"][0]["sha256"],product="seat",unit="unit",
                       start="2026-10-01T00:00:00Z",end="2026-11-01T00:00:00Z",evidence_sha256=mapping,quantity_source="BILL_INVENTORY")],
        currency="USD",economic_basis="graduated-whole-units/complete-service-slice/net-of-tax/line-half-up-cent",
        attestation="reviewed-entire-governing-chain-and-line-evidence-for-exact-bill")
    return store,key,signer,packet,directory


@pytest.mark.parametrize("mode,classification",[("SYNTHETIC_NEGOTIATED","MIXED"),("OPERATOR_ATTESTED","PROVIDER_WITH_OPERATOR_EVIDENCE")])
def test_offline_cli_registration_signature_and_installed_bill_pricing(tmp_path,custody,mode,classification):
    db,_,snap=custody
    store,key,signer,packet,directory=package(tmp_path,custody,mode)
    keyfile=private(tmp_path/"public.json",key.model_dump_json().encode())
    manifest=private(tmp_path/"packet.json",packet.model_dump_json(indent=2).encode())
    def cli(*args):
        r=subprocess.run([sys.executable,str(CLI),"--db",str(db),*map(str,args)],capture_output=True,text=True)
        assert r.returncode==0, r.stderr
        assert "Private fixture" not in r.stdout+r.stderr
        return r.stdout
    cli("register","--registration",keyfile)
    to_sign=tmp_path/"canonical.bin"
    cli("signing-bytes","--packet",manifest,"--out",to_sign)
    assert to_sign.read_bytes()==packet.signing_bytes() and to_sign.stat().st_mode & 0o777==0o600
    signature=private(tmp_path/"signature.bin",signer.sign(to_sign.read_bytes()))
    for _ in range(2):
        assert json.loads(cli("install","--packet",manifest,"--signature",signature,"--evidence-dir",directory))["package_id"]==packet.package_id
    bindings,omissions=store.resolve(TENANT,BIZ,snap)
    assert len(bindings)==1 and not omissions
    rows=evaluate_snapshot(snap,bindings=bindings)
    row=next(c for c in rows if c["provider_object_type"]=="bills" and c["provider_id"]==BILL)
    assert (row["amount"],row["outcome"],row["publishable"])==("40.00","ELIGIBLE",False)
    assert row["data_provenance"]["classification"]==classification
    assert row["actual_money_prevented"] is None
    status=json.loads(cli("status","--tenant",TENANT,"--business",BIZ))
    assert status["bindings"][0]["authority_digest"]==sha256(packet.signing_bytes()).hexdigest()
    cli("revoke","key",key.subject,"--tenant",TENANT,"--business",BIZ)
    assert not store.bindings(TENANT,BIZ,snap)


@pytest.mark.parametrize("fault",["absent-key","bad-signature","unsigned-rate","absent-bytes","wrong-bytes","new-capture",
        "wrong-tenant","wrong-business","wrong-vendor","wrong-entity","wrong-key-mode","wrong-bill","changed-line",
        "changed-record","wrong-evaluator","late-signer","wrong-service","expired","unsigned-citation"])
def test_economic_binding_falsification(tmp_path,custody,fault):
    _,ws,snap=custody
    store,key,signer,packet,directory=package(tmp_path,custody)
    if fault!="absent-key":
        store.register(key)
    values=deepcopy(packet.model_dump())
    if fault=="absent-bytes": (directory/values["versions"][0]["contract_sha256"]).unlink()
    if fault=="wrong-bytes": private(directory/values["mappings"][0]["evidence_sha256"],b"other evidence")
    if fault=="new-capture":
        newer=seal_snapshot({**snap,"completed_at":datetime.now(UTC).isoformat()})
        ws.import_observation(newer,BIZ)
    changes={"wrong-tenant":("tenant","elsewhere"),"wrong-business":("business_id",uid(730)),"wrong-vendor":("vendor_id",uid(55)),
             "wrong-entity":("entity_id",uid(56)),"wrong-key-mode":("mode","OPERATOR_ATTESTED"),"wrong-bill":("bill_id",uid(502)),
             "changed-record":("bill_digest","c"*64),"wrong-evaluator":("evaluator_sha256","e"*64)}
    if fault in changes:
        k,v=changes[fault];values[k]=v
    if fault=="changed-line": values["mappings"][0]["line_digest"]="a"*64
    if fault=="wrong-service": values["mappings"][0]["product"]="no-such-rate"
    if fault=="late-signer": values["versions"][0]["signed_at"]="2029-01-01T00:00:00Z"
    if fault=="expired": values.update(issued_at=int(time())-60,expires_at=int(time())-1)
    if fault=="unsigned-rate": values["versions"][0]["rates"][0]["tiers"][0]["rate"]="20"
    if fault=="unsigned-citation": values["versions"][0]["section"]="changed"
    modified=TermsPacket.model_validate(values)
    proof=signer.sign(packet.signing_bytes() if fault in {"unsigned-rate","unsigned-citation"} else modified.signing_bytes())
    if fault=="bad-signature": proof=Ed25519PrivateKey.generate().sign(modified.signing_bytes())
    with pytest.raises(EvidenceError):
        store.install(modified,proof,directory)
    assert store.bindings(TENANT,BIZ,snap)==()


def test_resolution_rechecks_custody_and_exact_capture(tmp_path,custody):
    _,ws,snap=custody
    store,key,signer,packet,directory=package(tmp_path,custody)
    store.register(key)
    store.install(packet,signer.sign(packet.signing_bytes()),directory)
    duplicate=packet.model_copy(update={"package_id":str(uuid4())})
    with pytest.raises(EvidenceError):
        store.install(duplicate,signer.sign(duplicate.signing_bytes()),directory)
    assert not store.bindings("foreign",BIZ,snap)
    assert not store.bindings(TENANT,uid(300),snap)
    forged=deepcopy(snap)
    forged["resources"]["bills"]["records"][0]["id"]=uid(358)
    assert not store.bindings(TENANT,BIZ,forged)
    path=directory/packet.versions[0].contract_sha256
    path.chmod(0o644)
    out,missing=store.resolve(TENANT,BIZ,snap)
    assert out==() and missing[0]["package_id"]==packet.package_id
    assert str(directory) not in str(missing)
    path.chmod(0o600)
    assert len(store.bindings(TENANT,BIZ,snap))==1
    new=seal_snapshot({**snap,"completed_at":datetime.now(UTC).isoformat()})
    ws.import_observation(new,BIZ)
    assert not store.bindings(TENANT,BIZ,snap) and not store.bindings(TENANT,BIZ,new)


def test_wrong_workspace_and_finance_reviewer_key_overlap(tmp_path,custody):
    db,_,snap=custody
    store,key,signer,packet,directory=package(tmp_path,custody)
    from uptime.auth import enroll
    from uptime.auth_keys import generate_reviewer_key
    enroll(db,key.subject,generate_reviewer_key(),mode="sandbox",tenant=TENANT)
    with pytest.raises(EvidenceError,match="independent"):
        store.register(key)
    with pytest.raises(EvidenceError,match="installation"):
        store.register(key.model_copy(update={"workspace_id":"d"*64}))


def test_revoked_package_requires_fresh_identity(tmp_path,custody):
    _,_,snap=custody
    store,key,signer,packet,directory=package(tmp_path,custody)
    store.register(key)
    sig=signer.sign(packet.signing_bytes())
    store.install(packet,sig,directory)
    store.revoke("package",packet.package_id,TENANT,BIZ)
    assert store.bindings(TENANT,BIZ,snap)==()
    with pytest.raises(EvidenceError):
        store.install(packet,sig,directory)
    fresh=packet.model_copy(update={"package_id":str(uuid4())})
    assert store.install(fresh,signer.sign(fresh.signing_bytes()),directory)==fresh.package_id


def test_private_source_mutation_or_future_capture_omits_only_financial_binding(tmp_path,custody):
    db,ws,snap=custody
    store,key,signer,packet,directory=package(tmp_path,custody)
    store.register(key)
    store.install(packet,signer.sign(packet.signing_bytes()),directory)
    path=directory/packet.mappings[0].evidence_sha256
    private(path,b"Private fixture service correction")
    valid, reasons=store.resolve(TENANT,BIZ,snap)
    assert not valid and reasons and b"Private fixture" not in json.dumps(reasons).encode()
    stamp=(datetime.now(UTC)+timedelta(hours=1)).isoformat()
    new=seal_snapshot({**snap,"observed_at":stamp,"completed_at":stamp})
    ws.import_observation(new,BIZ)
    _,reasons=store.resolve(TENANT,BIZ,new)
    assert reasons and "future" in reasons[0]["reason"]


def test_missing_itemization_cannot_be_replaced_by_asserted_terms(tmp_path,custody):
    _,ws,snap=custody
    store,key,signer,packet,directory=package(tmp_path,custody)
    store.register(key)
    newer=deepcopy(snap)
    bill=next(r for r in newer["resources"]["bills"]["records"] if r["kind"]=="bill")
    bill["lines"]=[]
    newer["completed_at"]=datetime.now(UTC).isoformat()
    newer=seal_snapshot(newer)
    ws.import_observation(newer,BIZ)
    from uptime.contracts import fingerprint
    at=int(time())
    packet=packet.model_copy(update={"capture_digest":newer["checksum"],"bill_digest":fingerprint(bill),"issued_at":at})
    with pytest.raises(EvidenceError):
        store.install(packet,signer.sign(packet.signing_bytes()),directory)
    rows=evaluate_snapshot(newer,bindings=store.bindings(TENANT,BIZ,newer))
    assert next(c for c in rows if c["provider_id"]==BILL)["amount"] is None


def test_signed_amendment_and_exact_native_purchase_order_line(tmp_path,custody):
    from test_ramp_findings_v4 import SyntheticReader, BILL as LINKED_BILL, PO as LINKED_PO
    db, ws, _=custody
    store,_,signer,base,directory=package(tmp_path,custody)
    observation=sync_records(SyntheticReader(),include_unlinked_purchase_orders=True)
    ws.import_observation(observation,BIZ)
    info=store.describe(TENANT,BIZ,LINKED_BILL)
    # This DTO uses a different synthetic provider business fixture: derive *its* party and line IDs.
    key=FinanceKey(subject=base.issuer,public_key=signer.public_key().public_bytes_raw().hex(),tenant=TENANT,
                   workspace_id=info["workspace_id"],business_id=BIZ,vendor_id=info["vendor_id"],entity_id=info["entity_id"],mode=base.mode)
    store.register(key)
    values=base.model_dump()
    values.update(bill_id=LINKED_BILL,capture_digest=observation["checksum"],bill_digest=info["bill_digest"],
                  issued_at=int(time()),vendor_id=info["vendor_id"],entity_id=info["entity_id"])
    values["versions"][0]["signatories"]=[info["vendor_id"],info["entity_id"]]
    new=deepcopy(values["versions"][0])
    new.update(version="amended",supersedes=values["versions"][0]["version"],effective_at="2026-10-01T00:00:00Z",
               signed_at="2026-09-24T00:00:00Z",contract_sha256=blob(directory,b"Private synthetic signed amendment."))
    new["rates"][0]["tiers"]=[{"upper":"5","rate":"10"},{"upper":None,"rate":"6"}]
    values["versions"].append(new)
    po=info["purchase_orders"][0]
    values["mappings"][0].update(line_id=info["lines"][0]["id"],line_digest=info["lines"][0]["sha256"],
                                 purchase_order_id=LINKED_PO,purchase_order_line_id=po["lines"][0]["id"],
                                 purchase_order_line_digest=po["lines"][0]["sha256"],quantity_source="ATTESTED_FULL_PO_LINE")
    good=TermsPacket.model_validate(values)
    values["mappings"][0]["purchase_order_line_digest"]="a"*64
    bad=TermsPacket.model_validate(values)
    with pytest.raises(EvidenceError):
        store.install(bad,signer.sign(bad.signing_bytes()),directory)
    store.install(good,signer.sign(good.signing_bytes()),directory)
    rows=evaluate_snapshot(observation,bindings=store.bindings(TENANT,BIZ,observation))
    row=next(c for c in rows if c["provider_id"]==LINKED_BILL and c["provider_object_type"]=="bills")
    assert row["amount"]=="40.00" and row["line_findings"][0]["version"]=="amended"


def test_read_missing_installation_leaves_no_database(tmp_path):
    path=tmp_path/"absent.sqlite"
    bindings,omissions=RampTermsStore(path).resolve(TENANT,BIZ,{})
    assert not bindings and omissions and not path.exists()
