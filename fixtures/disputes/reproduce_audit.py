"""Run the same local audit counterexamples against a selected repository root.

Usage: python fixtures/disputes/reproduce_audit.py /path/to/repository
No network, credentials, or external requests. Output contains synthetic facts only.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from uptime import disputes_claimant as claimant, disputes_vendor as vendor
from uptime.contracts import Principal, fingerprint
from uptime.disputes import DisputeDesk, DisputeConflict, START
from uptime.disputes_wire import FIXTURES, Document, Reply

raw = json.loads((FIXTURES / "claimant/dossiers.json").read_text())
principal = Principal("bears", "audit-reproducer", "reviewer")


def repin(d):
    if "artifact_registry" in d:
        d["artifact_registry"] = {doc["ref"]:fingerprint(doc) for group in
                                 ("initial_documents", "supplemental_archive", "customer_notice_archive")
                                 for doc in d[group] if doc.get("ref")}
    if "invoice_registry" in d:
        d["invoice_registry"] = {line["id"]:fingerprint(line) for line in d["invoice_lines"]}


def evaluate(d, at=START):
    result = claimant.preflight(d, at)
    return {"outcome": result.outcome, "amount": str(result.amount.amount) if result.amount else None}


report = {}
d = deepcopy(raw["dispute-cure"])
for key in ("month", "start", "end"):
    d[key] = d[key].replace("2026", "2025")
for group in ("initial_documents", "supplemental_archive"):
    for doc in d[group]:
        for key in ("month", "start", "end", "available_at", "observed_at"):
            if key in doc:
                doc[key] = doc[key].replace("2026", "2025")
for line in d["invoice_lines"]:
    if "month" in line:
        line["month"] = "2025-10"
repin(d)
report["pre_effective_agreement"] = evaluate(d, datetime(2025, 11, 2, tzinfo=UTC))

d = deepcopy(raw["dispute-denial"])
for doc in d["customer_notice_archive"]:
    doc.pop("observed_at", None); doc.pop("available_at", None)
repin(d)
report["already_available_maintenance"] = evaluate(d)

d = deepcopy(raw["dispute-cure"])
for line in d["invoice_lines"]:
    line.update(account="other-account", month="2024-08", currency="CAD", region="other")
repin(d)
report["contradictory_invoice_scope"] = evaluate(d)

d = deepcopy(raw["dispute-cure"])
d["initial_documents"][0].pop("ref")
repin(d)
report["missing_document_reference"] = evaluate(d)

d = deepcopy(raw["dispute-cure"])
d["invoice_lines"] = [dict(d["invoice_lines"][0], usd="0.01")]
repin(d)
report["fractional_cent"] = evaluate(d)

d = deepcopy(raw["dispute-partial"])
packet = claimant.ticket_for("bears", d, [])
record = json.loads((FIXTURES / "simulator/records.json").read_text())[packet.account]
doc = dict(packet.documents[-1].body); doc.pop("component_id", None)
bad = Document.from_archive("bears", doc)
packet = replace(packet, documents=packet.documents[:-1] + (bad,))
record["document_registry"][bad.fact.ref] = bad.fact.digest
report["authentic_missing_component"] = vendor.decide(packet, record, START).code

d = deepcopy(raw["dispute-partial"])
d["initial_documents"][0]["private_notes"] = "SYNTHETIC_SENSITIVE_SENTINEL"
repin(d)
packet = claimant.ticket_for("bears", d, [])
report["sentinel_in_outbound_packet"] = "SYNTHETIC_SENSITIVE_SENTINEL" in json.dumps(asdict(packet))
packet = claimant.ticket_for("bears", deepcopy(raw["dispute-partial"]), [])
packet = replace(packet, tenant="other", documents=tuple(Document.from_archive("other", doc.body) for doc in packet.documents))
report["foreign_tenant_vendor_reply"] = vendor.review(packet, START).code

with TemporaryDirectory() as temp:
    desk = DisputeDesk(Path(temp) / "duplicates.db"); desk.seed("bears")
    with sqlite3.connect(desk.path) as db:
        db.execute("INSERT INTO dispute_cases SELECT tenant,'duplicate',dossier,state FROM dispute_cases WHERE id='dispute-partial'")
    sent = 0
    for name in ("dispute-partial", "duplicate"):
        desk.act(principal, name, "approve-claim")
        try:
            sent += len(desk.act(principal, name, "submit-claim")["submissions"])
        except DisputeConflict:
            pass
    report["duplicate_obligation_receipts"] = sent
    desk = DisputeDesk(Path(temp) / "clock.db"); desk.seed("bears")
    vendor.review = lambda packet, at: Reply("WINDOW_CLOSED", "Synthetic mistaken deadline", "§3")
    desk.act(principal, "dispute-partial", "approve-claim")
    report["timely_time_bar_stage"] = desk.act(principal, "dispute-partial", "submit-claim")["stage"]
    desk = DisputeDesk(Path(temp) / "policy.db"); desk.seed("bears")
    report["incomplete_cure_auto_dispatchable"] = desk.act(principal, "dispute-cure", "approve-claim")["policy_dispatchable"]
print(json.dumps(report, indent=2))
