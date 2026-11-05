"""Bind the fixed synthetic example to one explicitly designated real sandbox bill. Never authorizes an external action."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uptime.ramp_cap import InvoiceCapScope, evaluate_invoice_cap, make_synthetic_binding, sign_synthetic_binding


def bind(snapshot, bill_id, terms, tenant="bears"):
    actor = "scripted-cap-rehearsal"
    payload = make_synthetic_binding(snapshot, bill_id, tenant_id=tenant, operator_id=actor, terms=terms)
    signer = Ed25519PrivateKey.generate()
    binding = sign_synthetic_binding(payload, signer)
    public = signer.public_key()
    row = next(r for r in snapshot["resources"]["bills"]["records"] if r["kind"] == "bill" and r["id"] == bill_id)
    result = evaluate_invoice_cap(snapshot, row, terms, as_of=datetime.fromisoformat(snapshot["completed_at"]),
                                  scope=InvoiceCapScope(tenant_id=tenant, binding=binding, trusted_operator_keys={actor: public}))
    if result.get("kind") != "case" or result["publishable"] is not False:
        raise ValueError("Cannot bind this constructed rehearsal to this bill")
    proof = {"schema": "uptime-rehearsal-cap/1", "actor_kind": "DISPOSABLE_SCRIPTED_REHEARSAL",
             "capture_digest": snapshot["checksum"], "tenant":tenant, "bill_id": bill_id, "operator_id":actor,
             "scripted_public_verifier":public.public_bytes_raw().hex(), "binding":binding}
    return proof, result


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--bill-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tenant", default="bears")
    args=parser.parse_args()
    terms=json.loads((Path(__file__).resolve().parents[1]/"fixtures/ramp/native-cap-terms.json").read_text())
    proof,result=bind(json.loads(args.capture.read_text()),args.bill_id,terms,args.tenant)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with NamedTemporaryFile("w", dir=args.output.parent,delete=False) as out:
        tmp=Path(out.name)
        json.dump(proof,out,indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    try:
        tmp.replace(args.output)
    finally:
        tmp.unlink(missing_ok=True)
    print(json.dumps({"kind":"CONSTRUCTED_REHEARSAL","amount":result["amount"],"currency":result["currency"],
                      "bill_id":args.bill_id,"publishable":False,"actual_recovery":None}))
