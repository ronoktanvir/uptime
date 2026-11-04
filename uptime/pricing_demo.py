"""Offline fixtures and CP1 presentation; no implicit live-provider fallback."""
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

from uptime.contracts import Citation, Source, fingerprint
from uptime.pricing import (
    Agreement, ContractVersion, Invoice, InvoiceLine, Rate, Tier, evaluate_price,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pricing"


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_agreement() -> Agreement:
    """Load the fictional signed agreement and immutable amendment snapshots."""
    data = json.loads((FIXTURES / "agreement.json").read_text())
    versions = []
    for version in data["versions"]:
        rates = tuple(Rate(rate["product"], rate["unit"], tuple(
            Tier(Decimal(t["upper"]) if t["upper"] else None, Decimal(t["rate"])) for t in rate["tiers"]
        ), rate["mode"], rate["quantity_scope"], rate["boundary"]) for rate in version["rates"])
        versions.append(ContractVersion(
            version["id"], _date(version["effective_at"]), _date(version["signed_at"]),
            tuple(version["signatories"]), version["supersedes"], rates,
            tuple(version["excluded_products"]), Citation(**version["citation"]),
            version["currency"], version["tax_treatment"], version["rounding"],
        ))
    return Agreement(data["id"], data["customer"], data["vendor"], _date(data["expires_at"]), tuple(versions))


def load_demo_inputs() -> list[tuple[dict, Invoice]]:
    """Return fixture metadata and separate synthetic invoices for integration tests."""
    inputs = []
    for case in json.loads((FIXTURES / "cases.json").read_text()):
        lines = (
            InvoiceLine("usage", "compute-job", Decimal(case["quantity"]), "job", _date(case["start"]),
                        _date(case["end"]), Decimal(case["net"]), Decimal("0.00"), case["id"] + ":usage-ledger"),
            InvoiceLine("support", "premium-support", None, None, _date(case["start"]),
                        _date(case["end"]), Decimal(case["support"]), Decimal("0.00"), None),
        )
        invoice = Invoice(case["id"] + "-invoice", "synthetic-bears", "synthetic-cloud",
                          _date("2026-11-02T12:00:00Z"), case["status"], "USD",
                          Decimal(case["net"]) + Decimal(case["support"]), lines)
        inputs.append((case, invoice))
    return inputs


def demo_cases() -> list[dict]:
    agreement = load_agreement()
    agreement_data = json.loads((FIXTURES / "agreement.json").read_text())
    cases = []
    for metadata, invoice in load_demo_inputs():
        result = evaluate_price(agreement, invoice)
        sources = [source.value for source in result.sources]
        amount = str(result.overcharge) if result.overcharge is not None else None
        evidence = [
            {"label": "Synthetic signed agreement and amendment", "detail":
             f"Fictional signatures and parties; no real commercial relationship. Agreement SHA256 {fingerprint(agreement_data)}.",
             "sources": [Source.CUSTOMER.value]},
            {"label": "Synthetic itemized invoice", "detail":
             f"{invoice.id}; gross {invoice.total} USD; status {invoice.payment_status}; fixture SHA256 {fingerprint(metadata)}. No live Ramp binding.",
             "sources": sources},
        ]
        for line in invoice.lines:
            evidence.append({"label": f"Line {line.id}", "detail":
                             f"Product {line.product}; quantity {line.quantity}; unit {line.unit}; "
                             f"performance [{line.start.isoformat()}, {line.end.isoformat()}); net {line.net}; "
                             f"tax {line.tax}; allocation {line.allocation_ref or 'non-covered'}.", "sources": sources})
        cases.append({
            "id": metadata["id"], "vendor": "Synthetic Cloud (fictional)", "title": metadata["title"],
            "outcome": result.evaluation.outcome.value, "stage": result.stage,
            "amount": amount, "currency": "USD", "sources": sources,
            "trace": list(result.evaluation.trace),
            "clauses": [{"label": f"{c.document}: {c.section} ({c.version})", "uri": c.uri} for c in result.evaluation.clauses],
            "evidence": evidence,
            "timeline": [
                *({"at": version.signed_at.isoformat(), "event": f"Synthetic signatures: {version.id}", "sources": [Source.CUSTOMER.value]}
                  for version in agreement.versions),
                {"at": invoice.issued_at.isoformat(), "event": f"Synthetic invoice issued; payment status {invoice.payment_status}", "sources": sources},
                {"at": "2026-11-03T12:00:00+00:00", "event": "Deterministic price review; no provider write or claim", "sources": sources},
            ],
            "actions": [],
            "financials": [
                {"label": "Invoice gross", "value": str(invoice.total), "sources": sources},
                {"label": "Provisional overcharge", "value": amount, "sources": sources},
                {"label": "Undercharge (not netted)", "value": str(result.undercharge) if result.undercharge is not None else None, "sources": sources},
                *({"label": label, "value": "0.00", "sources": sources} for label in ("Prevented", "Claimed", "Awarded", "Credit recorded", "Applied")),
            ],
            "payment_status": invoice.payment_status, "missing": list(result.evaluation.missing),
            "provider_binding": None,
            "line_findings": [{"line_id": f.line_id, "product": f.product, "version": f.version,
                               "billed": str(f.billed), "expected": str(f.expected) if f.expected is not None else None,
                               "delta": str(f.delta) if f.delta is not None else None, "direction": f.direction} for f in result.lines],
        })
    return cases
