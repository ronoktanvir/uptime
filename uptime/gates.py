"""Local release attestation. This is a deployment interlock, not organizational identity."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "docs/v4/evidence/release_attestation.json"
REQUIRED_GATES = {"security_financial", "unseen_vendor", "unanticipated_dispute", "regression"}


def code_manifest(root=ROOT):
    root=Path(root)
    files=[]
    for directory in ("uptime","web","tests","scripts"):
        files.extend(p for p in (root/directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py",".js",".cjs",".css",".html",".sh"})
    files.extend(root/name for name in ("pyproject.toml","uv.lock"))
    return {str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def release_status(root=ROOT, receipt=None):
    root=Path(root).resolve()
    receipt=Path(receipt) if receipt is not None else root/"docs/v4/evidence/release_attestation.json"
    try:
        record=json.loads(receipt.read_text())
        if record.get("schema")!="uptime-v4-release/1" or record.get("scope")!="local-simulation":
            raise ValueError("Unrecognized attestation scope")
        if record.get("code")!=code_manifest(root):
            raise ValueError("Running source differs from the tested source")
        if set(record.get("gates",{}))!=REQUIRED_GATES:
            raise ValueError("A required acceptance gate has no evidence")
        for name, entry in record["gates"].items():
            path=(root/entry["path"]).resolve()
            if not path.is_relative_to(root/"docs/v4/evidence") or entry.get("status")!="PASS":
                raise ValueError("Acceptance evidence is outside its trust boundary")
            if sha256(path.read_bytes()).hexdigest()!=entry["sha256"]:
                raise ValueError("Acceptance evidence digest mismatch")
        return {"ready":True,"scope":"local-simulation","gates":sorted(REQUIRED_GATES),
                "note":"Verified local release evidence. Real provider or vendor actions remain separately authorized."}
    except (OSError,ValueError,KeyError,TypeError):
        return {"ready":False,"scope":"read-only","gates":[],
                "note":"Local approvals remain disabled until matching independent gate evidence is installed."}


def local_release_ready():
    return release_status()["ready"]
