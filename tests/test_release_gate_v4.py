import json
from hashlib import sha256
from pathlib import Path
from uptime.gates import code_manifest, release_status, REQUIRED_GATES


def make_artifact(tmp):
    for part in ("uptime","tests","web","scripts","docs/v4/evidence"):
        (tmp/part).mkdir(parents=True,exist_ok=True)
    (tmp/"uptime/a.py").write_text("x=1")
    for f in ("pyproject.toml","uv.lock"): (tmp/f).write_text("")
    gates={}
    for name in REQUIRED_GATES:
        p=tmp/"docs/v4/evidence"/(name+".json");p.write_text('{"executed":true}')
        gates[name]={"path":str(p.relative_to(tmp)),"sha256":sha256(p.read_bytes()).hexdigest(),"status":"PASS"}
    receipt=tmp/"docs/v4/evidence/release_attestation.json"
    r={"schema":"uptime-v4-release/1","scope":"local-simulation","code":code_manifest(tmp),"gates":gates}
    receipt.write_text(json.dumps(r))
    return receipt,r


def test_gate_closed_without_verified_receipt(tmp_path):
    assert release_status(tmp_path)["ready"] is False


def test_receipt_binds_code_and_each_required_evidence(tmp_path):
    p,r=make_artifact(tmp_path)
    assert release_status(tmp_path)["ready"]
    (tmp_path/"uptime/a.py").write_text("x=2")
    assert not release_status(tmp_path)["ready"]
    (tmp_path/"uptime/a.py").write_text("x=1")
    (tmp_path/r["gates"]["unseen_vendor"]["path"]).write_text("changed")
    assert not release_status(tmp_path)["ready"]


def test_gate_rejects_missing_failed_or_outside_evidence(tmp_path):
    p,r=make_artifact(tmp_path)
    r["gates"]["unseen_vendor"]["status"]="FAIL";p.write_text(json.dumps(r))
    assert not release_status(tmp_path)["ready"]
    r["gates"]["unseen_vendor"]["status"]="PASS";r["gates"]["unseen_vendor"]["path"]="../../elsewhere"
    p.write_text(json.dumps(r))
    assert not release_status(tmp_path)["ready"]
