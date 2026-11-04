"""Public-term/synthetic-customer fixtures and the CP1 case-detail read model."""
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path

from uptime.contracts import Source, fingerprint
from uptime.twilio import (ClaimBasis, Coverage, Exclusion, FeeKind, FeeLine,
                           Plan, ServiceFamily, ServiceScope, StatusInterval,
                           TwilioInput, evaluate)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "twilio" / "cases.json"
SYNTHETIC_SOURCES = [Source.CUSTOMER.value, Source.REPLAY.value]


def input_from_dict(raw: dict) -> TwilioInput:
    """Decode trusted local fixture JSON; not an HTTP request/authorization API."""
    data = dict(raw)
    data["month"] = date.fromisoformat(data["month"])
    for key in ("as_of", "submitted_at"):
        if data.get(key) is not None:
            data[key] = datetime.fromisoformat(data[key])
    if data.get("administration_purchased_on"):
        data["administration_purchased_on"] = date.fromisoformat(data["administration_purchased_on"])
    scope = data["service"]
    data["service"] = ServiceScope(**{**scope, "family": ServiceFamily(scope["family"])})
    data["plan"] = Plan(data["plan"]) if data.get("plan") else None
    data["basis"] = ClaimBasis(data.get("basis", "availability"))
    for key in ("subscription_coverage", "status_coverage"):
        item = data.get(key)
        data[key] = Coverage(**{**item, "start": datetime.fromisoformat(item["start"]),
                               "end": datetime.fromisoformat(item["end"])}) if item else None
    data["intervals"] = tuple(StatusInterval(**{
        **item, "start": datetime.fromisoformat(item["start"]), "end": datetime.fromisoformat(item["end"]),
        "exclusion": Exclusion(item["exclusion"]), "documentation_refs": tuple(item["documentation_refs"]),
        "scheduled_notice_hours": Decimal(item["scheduled_notice_hours"]) if item.get("scheduled_notice_hours") is not None else None,
    }) for item in data["intervals"])
    data["fees"] = tuple(FeeLine(**{**item, "month": date.fromisoformat(item["month"]),
                                   "kind": FeeKind(item["kind"]), "amount": Decimal(item["amount"])})
                         for item in data["fees"])
    return TwilioInput(**data)


def demo_inputs() -> list[tuple[dict, TwilioInput]]:
    """Golden expectations are stored independently of evaluator output."""
    return [(case, input_from_dict(case["input"])) for case in json.loads(FIXTURE.read_text())["cases"]]


def demo_cases() -> list[dict]:
    fixture = json.loads(FIXTURE.read_text())
    cases = []
    for case, inputs in demo_inputs():
        evaluated = evaluate(inputs)
        amount = str(evaluated.amount.amount) if evaluated.amount else None
        # PUBLIC describes the terms only, never the fictional status/fee facts.
        evidence = [{"label": "Dated public API SLA", "detail": fixture["terms"]["provenance"],
                     "ref": fixture["terms"]["uri"], "digest": fixture["terms"]["input_sha256"],
                     "sources": [Source.PUBLIC.value]},
                    {"label": "Synthetic customer evidence", "detail": fixture["label"],
                     "ref": f"fixtures/twilio/cases.json#{case['id']}",
                     "digest": fingerprint(case["input"]), "sources": list(SYNTHETIC_SOURCES)}]
        for interval in inputs.intervals:
            evidence.append({"label": "Synthetic status documentation and customer mapping",
                             "detail": f"{interval.start.isoformat()} to {interval.end.isoformat()}; refs={','.join(interval.documentation_refs)}; attribution={interval.attribution_ref}; exclusion={interval.exclusion_ref}. The status hostname identifies the required source, not an observed historical incident.",
                             "sources": list(SYNTHETIC_SOURCES)})
        for fee in inputs.fees:
            evidence.append({"label": f"Synthetic fee line: {fee.id}",
                             "detail": f"{fee.amount} {fee.currency}; {fee.kind.value}; API={fee.api_id}; ref={fee.evidence_ref}; mapping={fee.mapping_ref}",
                             "sources": list(SYNTHETIC_SOURCES)})
        cases.append({
            "id": case["id"], "vendor": "Twilio", "title": case["title"],
            "outcome": evaluated.outcome.value, "stage": "EVALUATED", "amount": amount,
            "currency": "USD", "sources": [Source.PUBLIC.value, *SYNTHETIC_SOURCES],
            "trace": list(evaluated.trace), "missing": list(evaluated.missing),
            "clauses": [{"label": f"{c.document} ({c.version}) — {c.section}", "uri": c.uri} for c in evaluated.clauses],
            "evidence": evidence,
            "timeline": [{"at": inputs.as_of.isoformat(), "event": "Deterministic synthetic fixture evaluated; nothing submitted", "sources": list(SYNTHETIC_SOURCES)}],
            "actions": [],
            "financials": [
                {"label": "Candidate future-service credit (synthetic, unsubmitted)", "value": amount if amount is not None else "Not established", "sources": list(SYNTHETIC_SOURCES)},
                {"label": "Awarded", "value": "0.00", "sources": list(SYNTHETIC_SOURCES)},
                {"label": "Posted", "value": "0.00", "sources": list(SYNTHETIC_SOURCES)},
                {"label": "Applied", "value": "0.00", "sources": list(SYNTHETIC_SOURCES)},
            ],
        })
    return cases
