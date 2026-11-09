"""Tool-free public/synthetic model proposals. Runtime questions never leave the process."""
from hashlib import sha256
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "fixtures/model/public_inputs.json"
PLAN = ROOT / "fixtures/model/verified_plan.json"
INPUT_DIGEST = "0273f1c93a19fde29aebb0e40f8f2d15f7df22322d37bcf7e5e0bc7078866d15"
EXPECTED = {"default_threshold":"99.95", "edition_threshold":"99.99", "minimum_duration":"5",
            "claim_window":"30", "fee_basis":"affected_fees"}
EVIDENCE_TYPES = {
    "status_interval": "Cited status interval for the affected service",
    "fee_lines": "Itemized affected fees after the contractual exclusions",
    "plan": "Applicable edition and purchase period",
    "exclusion": "Documented cause and exclusion classification",
}
INTENTS = {"basis", "proof", "next"}
# D12 (decided 2026-11-09): unsupported questions abstain. "basis" is the fallback intent, so it answers only
# when the question names something the case explains; the intent label itself is unchanged.
BASIS_TOPICS = re.compile(r"\b(?:fees?|amounts?|credits?|calculat\w*|eligib\w*|why|how|outcome|basis|ledger|value|"
                          r"award\w*|applied|claim\w*|estimat\w*|money|usd|percent\w*|price|cost|invoices?|bills?|"
                          r"decision|classif\w*|explain\w*|summar\w*|status|stage|case)\b|\$|%", re.I)
ABSTAIN = "This case's records don't answer that. Ask about its evidence, calculation or next step."
ALLOWED_ATOMS = {
    "basis": ("fee_lines", "outcome", "ledger"),
    "proof": ("required", "evidence", "citations"),
    "next": ("stage", "permitted", "human"),
}


def public_context(path=INPUT):
    content = Path(path).read_bytes()
    if len(content)>12_000 or sha256(content).hexdigest() != INPUT_DIGEST:
        raise ValueError("unapproved or changed public-model input")
    return json.loads(content)


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {"extraction","investigation","guide"}:
        raise ValueError("unexpected model fields")
    values = plan["extraction"]
    if not isinstance(values,list) or len(values) != len(EXPECTED):
        raise ValueError("missing or duplicate extraction")
    for v in values:
        if not isinstance(v,dict) or set(v)!={"ref","value"} or v["ref"] not in EXPECTED or v["value"] != EXPECTED[v["ref"]]:
            raise ValueError("uncited or unsupported contract value")
    if {v["ref"] for v in values} != set(EXPECTED):
        raise ValueError("missing extraction field")
    investigation = plan["investigation"]
    # Investigation is a read-only checklist. No reference can certify evidence exists.
    if not isinstance(investigation,dict) or set(investigation)!={"unitemized_invoice","public_incident_only"}:
        raise ValueError("unknown investigation scenario")
    for k,refs in investigation.items():
        if not isinstance(refs,list) or not refs or len(set(refs))!=len(refs) or set(refs)-set(EVIDENCE_TYPES):
            raise ValueError("invented evidence reference")
        required = {"fee_lines"} if k=="unitemized_invoice" else {"status_interval","plan","fee_lines","exclusion"}
        if not required.issubset(refs):
            raise ValueError("incomplete evidence investigation")
    guide = plan["guide"]
    if not isinstance(guide,dict) or set(guide)!=INTENTS:
        raise ValueError("unrecognized explanation intents")
    for k,atoms in guide.items():
        if not isinstance(atoms,list) or len(atoms)!=3 or set(atoms)!=set(ALLOWED_ATOMS[k]):
            raise ValueError("guide attempted an unsupported explanation")
    return plan


def verified_plan():
    public_context()
    x = json.loads(PLAN.read_text())
    if x["input_digest"] != INPUT_DIGEST or x["model"] != "claude-opus-5-5":
        raise ValueError("model provenance mismatch")
    return validate_plan(x["plan"])


def model_card():
    plan = verified_plan()
    meta = json.loads(PLAN.read_text())
    doc = public_context()
    return dict(model=meta["model"],run=meta["session"],source_uri=doc["uri"],
                input_digest=INPUT_DIGEST, document_digest=doc["source_sha256"],
                fields=plan["extraction"],sources=["LIVE_VENDOR_PUBLIC","DETERMINISTIC_REPLAY"],
                note="Verified tool-free model extraction. Replaying the pinned public-source result.")


def explain(case, question):
    plan=verified_plan()
    text=question.casefold()
    if re.search(r"\b(?:submit|send|approve|activate|next|appeal|file|pay)\b", text):
        intent="next"
    elif any(s in text for s in ("missing","proof","evidence","source","contract","exclusion")):
        intent="proof"
    else:
        intent="basis"
    sources=list(dict.fromkeys(case["sources"]+["DETERMINISTIC_REPLAY"]))
    if intent=="basis" and not BASIS_TOPICS.search(question):
        return {"answer":ABSTAIN,"intent":intent,"abstained":True,"sources":sources,
                "model":"Verified Claude explanation plan + current deterministic case state","external_transmission":False}
    def strings(values,key):
        return ", ".join(str(v[key]) for v in values if isinstance(v,dict) and v.get(key))
    claims=case.get("financials",[])
    checks = plan["investigation"]["public_incident_only"] if case.get("vendor")=="Twilio" else []
    names=[EVIDENCE_TYPES[k] for k in checks]
    atoms={
        "outcome":f'{case["vendor"]} is classified {case["outcome"]}.',
        "fee_lines":(case.get("trace") or ["No verified calculation is available."])[0],
        "ledger":"; ".join(f'{x["label"]} {x["value"]}' for x in claims[:6]) or "No credit has been reconciled for this case.",
        "required":"Check " + ", ".join(names) + "." if names else "Use the governing terms and the case evidence below.",
        "evidence":strings(case.get("evidence",[]),"label") or "No qualifying evidence record.",
        "citations":strings(case.get("clauses",[]),"label") or "No verified source clause.",
        "stage":f'Current stage: {case["stage"]}.',
        "permitted":("Available in this session: " + strings(case.get("actions",[]),"label") + ".") if case.get("actions") else "There is no enabled action at this stage.",
        "human":"The guide is read-only. A reviewer must use the case controls for an authorized simulated action.",
    }
    return {"answer":" ".join(str(atoms[k]) for k in plan["guide"][intent]),"intent":intent,"abstained":False,
            "sources":sources,"model":"Verified Claude explanation plan + current deterministic case state",
            "external_transmission":False}
