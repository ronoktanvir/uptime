"""Read-only gold examples for one explicitly synthetic agreement, version NB-DEMO-2025-10."""
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo
import json

from uptime.contracts import Citation, EvaluationResult, Money, Outcome, Source

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "other_obligations"
SOURCE_PATH = "/fixtures/other_obligations/agreement.txt"
VERSION = "NB-DEMO-2025-10"
TAGS = [Source.CUSTOMER, Source.REPLAY]
FIRST, LAST = date(2025, 10, 1), date(2026, 9, 30)
RENEWAL = date(2026, 11, 9)
PACIFIC = ZoneInfo("America/Los_Angeles")
CENT = Decimal("0.01")


class MissingFact(ValueError):
    pass


class UnsupportedTerm(ValueError):
    pass


def result(section, outcome, trace, amount=None):
    citation = Citation("Northbank demonstration agreement", VERSION, section, SOURCE_PATH)
    return EvaluationResult(outcome, (citation,), tuple(trace),
                            (trace[-1],) if outcome == Outcome.MISSING else (),
                            Money(amount) if amount is not None else None)


def _canonical(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and value.isprintable()


def unique_records(records):
    if not isinstance(records, list):
        raise MissingFact("Complete identified source records are required.")
    unique = {}
    for record in records:
        if not isinstance(record, dict):
            raise MissingFact("An identified source record is missing.")
        key = record.get("id")
        if not _canonical(key) or (key in unique and record != unique[key]):
            raise MissingFact("An identifier is absent or has conflicting source records.")
        unique[key] = record
    return list(unique.values())


def usd(record):
    if record.get("currency") is None:
        raise MissingFact("An included record lacks its currency.")
    if record["currency"] != "USD":
        raise UnsupportedTerm("R-1 provides no currency-conversion method for an included record.")
    if not isinstance(record.get("amount"), str):
        raise MissingFact("An included record lacks a decimal-string amount.")
    value = Decimal(record["amount"])
    if not value.is_finite() or value < 0 or value != value.quantize(CENT):
        raise MissingFact("A finite nonnegative amount in whole cents is required.")
    return value


def evaluate_rebate(data):
    """Isolate exact ledger sums from ambient Decimal precision and rounding."""
    if not isinstance(data, dict):
        return result("R-1", Outcome.MISSING, ["A scoped ledger is required."])
    with localcontext() as context:
        # Cent-aligned amounts need integer digits plus two fractional digits,
        # carry growth for the sum, and headroom for the percentage product.
        width = 0
        count = 0
        for key in ("charges", "credits"):
            records = data.get(key)
            if not isinstance(records, list):
                continue  # The evaluator reports the missing ledger.
            count += len(records)
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get("amount"), str):
                    continue
                try:
                    value = Decimal(record["amount"])
                except InvalidOperation:
                    continue
                if value.is_finite():
                    width = max(width, value.adjusted() + 3)
        context.prec = max(60, width + len(str(count + 1)) + 5)
        return _evaluate_rebate(data)


def _evaluate_rebate(data):
    """Account-scoped annual ledger, with returns and only this term's already-issued credits."""
    trace = []
    try:
        if data.get("complete") is not True or date.fromisoformat(data["through"]) < LAST:
            raise MissingFact("The closed-year paid-charge, return and credit ledgers must be complete.")
        charges = returns = credited = Decimal(0)
        for record in unique_records(data.get("charges")):
            when = date.fromisoformat(record["date"])
            if not FIRST <= when <= LAST:
                continue
            if not record.get("product"):
                raise MissingFact("A period charge lacks a product mapping.")
            if record["product"] not in ("Core", "Analytics"):
                continue
            if record.get("kind") == "paid":
                charges += usd(record)
            elif record.get("kind") == "return":
                returns += usd(record)
            else:
                raise UnsupportedTerm("An included transaction has an unsupported posting type.")
        for memo in unique_records(data.get("credits")):
            if not memo.get("clause") or not memo.get("year_end"):
                raise MissingFact("A credit memo lacks its obligation or year allocation.")
            credit_year = date.fromisoformat(memo["year_end"])
            if memo["clause"] == "R-1" and credit_year == LAST:
                credited += usd(memo)
    except UnsupportedTerm as exc:
        return result("R-1", Outcome.UNSUPPORTED, [str(exc)])
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        return result("R-1", Outcome.MISSING,
                      [str(exc) if isinstance(exc, MissingFact) else "Invalid or missing scoped ledger value."])

    net = charges - returns
    trace.append(f"USD {charges:.2f} paid less USD {returns:.2f} in eligible returns = USD {net:.2f} net.")
    if net < Decimal("100000"):
        return result("R-1", Outcome.INELIGIBLE, trace + ["Annual net spend is below the inclusive USD 100,000 threshold."])
    accrued = (net * Decimal("0.02")).quantize(CENT, rounding=ROUND_HALF_UP)
    trace.append(f"Threshold met. 2.00% of the full net base yields USD {accrued:.2f}.")
    outstanding = max(Decimal(0), accrued - credited)
    trace.append(f"Less USD {credited:.2f} already credited for R-1 in this year. Outstanding estimate USD {outstanding:.2f}.")
    if outstanding == 0:
        return result("R-1", Outcome.INELIGIBLE, trace + ["The earned amount is already covered by identified credits."])
    return result("R-1", Outcome.ELIGIBLE, trace, outstanding)


def notice_cutoff(calendar):
    """Count three working days strictly before renewal using a bounded, explicit calendar."""
    if not calendar or calendar.get("id") != "NB-OFFICE-2026":
        raise MissingFact("The governing NB-OFFICE-2026 working-day calendar is required.")
    begin, end = date.fromisoformat(calendar["from"]), date.fromisoformat(calendar["through"])
    weekdays = set(calendar["weekdays"])
    closed = {date.fromisoformat(item) for item in calendar["closed"]}
    if not begin <= RENEWAL <= end:
        raise MissingFact("The working-day calendar lacks coverage for the renewal.")
    if weekdays != {0, 1, 2, 3, 4} or date(2026, 11, 6) not in closed:
        raise MissingFact("The supplied calendar conflicts with the stated weekend or office closure.")
    when, remaining = RENEWAL, 3
    while remaining:
        when -= timedelta(days=1)
        if when < begin:
            raise MissingFact("The working-day calendar ends before the cutoff can be established.")
        if when.weekday() in weekdays and when not in closed:
            remaining -= 1
    return datetime.combine(when, time(17), tzinfo=PACIFIC)


def evaluate_notice(data):
    try:
        cutoff = notice_cutoff(data.get("calendar"))
    except (KeyError, TypeError, ValueError) as exc:
        return result("N-2", Outcome.MISSING,
                      [str(exc) if isinstance(exc, MissingFact) else "The governing working-day calendar is incomplete."])
    trace = [f"N-2 receipt cutoff {cutoff.isoformat()} in America/Los_Angeles after counting three working days back."]
    receipt = data.get("receipt") or {}
    if (not _canonical(receipt.get("id")) or receipt.get("obligation") != "N-2" or receipt.get("renewal") != RENEWAL.isoformat()
            or receipt.get("channel") != "designated_customer_portal"):
        return result("N-2", Outcome.MISSING, trace + ["The scoped designated-portal receipt is absent."])
    try:
        received = datetime.fromisoformat(receipt["received_at"])
        if received.utcoffset() is None:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return result("N-2", Outcome.MISSING, trace + ["The receipt needs a timestamp with an explicit offset."])
    trace.append(f"Receipt {receipt['id']} arrived {received.astimezone(PACIFIC).isoformat()}.")
    if received.astimezone(UTC) > cutoff.astimezone(UTC):
        return result("N-2", Outcome.INELIGIBLE, trace + ["Receipt was late. Route notice timing to a human reviewer."])
    return result("N-2", Outcome.ELIGIBLE, trace + ["Receipt met the inclusive cutoff. No monetary remedy is modeled."])


def demo_cases():
    data = json.loads((ROOT / "examples.json").read_text())
    rebate = evaluate_rebate(data["rebate"])
    notice = evaluate_notice(data["notice"])
    parity = result("M-3", Outcome.UNSUPPORTED, [
        "The fixture has no authorized comparable commitment or verified parity pricing method. No entitlement is computed."])
    rebate_evidence = [(r["id"], f"{r['date']} · {r['product']} · {r['kind']} · {r['currency']} {r['amount']}")
                       for r in data["rebate"]["charges"]]
    rebate_evidence.extend((r["id"], f"Credit for {r['clause']}, year ending {r['year_end']} · {r['currency']} {r['amount']}")
                           for r in data["rebate"]["credits"])
    receipt = data["notice"]["receipt"]
    rows = [
        ("rebate-annual", "Annual rebate after returns", rebate,
         "REBATE_ESTIMATE" if rebate.amount else "REBATE_REVIEW", rebate_evidence),
        ("notice-renewal", "Renewal notice receipt", notice,
         {Outcome.ELIGIBLE: "NOTICE_RECEIVED_ON_TIME", Outcome.INELIGIBLE: "NOTICE_LATE_REVIEW"}.get(
             notice.outcome, "NOTICE_EVIDENCE_NEEDED"),
         [("Office calendar NB-OFFICE-2026", "Weekdays open except the November 6 closure."),
          (receipt["id"], f"Designated portal receipt for {receipt['obligation']} · {receipt['received_at']}")]),
        ("mfn-comparator", "Price parity requires a comparator", parity, "METHOD_UNSUPPORTED",
         [("Comparator inventory", "No authorized comparator or verified adjustment method in this fixture.")]),
    ]
    agreement = (ROOT / "agreement.txt").read_text()
    views = []
    for case_id, title, evaluation, stage, evidence in rows:
        cite = evaluation.clauses[0]
        section_text = next(part.strip() for part in agreement.split("\n\n") if f"Section {cite.section}." in part)
        amount = f"{evaluation.amount.amount:.2f}" if evaluation.amount else None
        views.append(dict(id=case_id, vendor="Northbank Analytics (synthetic)", title=title, outcome=evaluation.outcome,
                          stage=stage, amount=amount, currency="USD", sources=TAGS.copy(), trace=list(evaluation.trace),
                          clauses=[dict(label=f"{cite.document}, {VERSION}, §{cite.section}", uri=cite.uri)],
                          evidence=[dict(label=label, detail=detail, sources=TAGS.copy())
                                    for label, detail in [(f"Agreement §{cite.section}", section_text), *evidence]],
                          timeline=[dict(at="2026-11-04T12:00:00+00:00", event="Evaluated synthetic agreement and replay facts.",
                                         sources=TAGS.copy())], actions=[],
                          financials=[dict(label="Unclaimed outstanding rebate estimate", value=f"USD {amount}", sources=TAGS.copy())]
                          if amount is not None else []))
    return views
