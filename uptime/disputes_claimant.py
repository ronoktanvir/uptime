"""Claimant investigation. Uses the customer's archived artifacts and vendor reply only."""
from calendar import monthrange
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from uptime.contracts import Citation, EvaluationResult, Money, Outcome
from uptime.disputes_wire import CENT, TERMS, VERSION, Document, Reply, Ticket, deadline


def estimate(dossier: dict) -> str:
    fees = sum((Decimal(line["usd"]) for line in dossier["invoice_lines"]
                if line["kind"] == "affected_api"), Decimal(0))
    return format((fees * Decimal("0.10")).quantize(CENT), ".2f")



def preflight(dossier: dict, at: datetime) -> EvaluationResult:
    """Independent claimant evaluation on facts known when the original claim is prepared."""
    def result(outcome, section, detail, amount=None):
        clauses = (Citation("Twilio APIs SLA", VERSION, section, TERMS),)
        return EvaluationResult(outcome, clauses, (detail,), (detail,) if outcome == Outcome.MISSING else (),
                                Money(amount) if amount is not None else None)

    if (dossier.get("governing_version") != VERSION or dossier.get("plan") != "standard"
            or dossier.get("product") != "Twilio Messaging API" or dossier.get("currency") != "USD"):
        return result(Outcome.UNSUPPORTED, "§§1, 3", "No supported agreement, plan, covered API or USD fee mapping.")
    try:
        start, end = (datetime.fromisoformat(dossier[k]) for k in ("start", "end"))
        month = dossier["month"]
        first = datetime.strptime(month, "%Y-%m").replace(tzinfo=UTC)
        next_month = first + timedelta(days=monthrange(first.year, first.month)[1])
        if (not start.utcoffset() == end.utcoffset() == timedelta() or not first <= start < end <= next_month
                or (end - start) % timedelta(minutes=1)):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return result(Outcome.MISSING, "§§1, 3", "A scoped, supported whole-minute status interval is missing.")
    if at < next_month or at >= deadline(month):
        return result(Outcome.INELIGIBLE, "§3", "Outside the supported UTC post-month filing period.")
    docs = dossier.get("initial_documents", [])
    if (not dossier.get("account") or not dossier.get("region") or any(not scoped(dossier, doc) for doc in docs)
            or not any(scoped(dossier, doc) and doc.get("kind") == "status_summary"
                       and doc.get("origin") == "synthetic_status_archive"
                       and doc.get("source") == "DETERMINISTIC_REPLAY" for doc in docs)):
        return result(Outcome.MISSING, "§3", "The scoped status dates, times and supporting documentation are required.")
    screen = dossier.get("exclusion_screen")
    if screen == "confirmed_excluded":
        return result(Outcome.INELIGIBLE, "§4", "Known evidence identifies an excluded incident.")
    if screen != "no_known_exclusion":
        return result(Outcome.MISSING, "§4", "The initial exclusion screen is missing or unresolved.")
    duration = end - start
    total = next_month - first
    if duration < timedelta(minutes=5) or duration * 2000 <= total:
        # Ordinary plan requires availability strictly below 99.95%.
        return result(Outcome.INELIGIBLE, "§§1, 3, 4(g)", "The countable interval does not breach the ordinary API threshold.")
    kinds = {"affected_api", "carrier", "tax", "third_party", "unaffected_api"}
    lines = dossier.get("invoice_lines", [])
    if not lines or len({line.get("id") for line in lines}) != len(lines) or any(not line.get("id") for line in lines):
        return result(Outcome.MISSING, "§1", "Distinct period-matched invoice line identifiers are required.")
    if any(line.get("kind") not in kinds for line in lines):
        return result(Outcome.UNSUPPORTED, "§1", "An unmapped charge prevents a verified affected-fee calculation.")
    try:
        amounts = [Decimal(line["usd"]) for line in lines]
        if any(not isinstance(line["usd"], str) or not value.is_finite() or value < 0 or value != value.quantize(CENT)
               for line, value in zip(lines, amounts)):
            raise ValueError
    except (InvalidOperation, KeyError, TypeError, ValueError):
        return result(Outcome.MISSING, "§1", "The invoice lacks a finite, cent-denominated USD amount.")
    amount = Decimal(estimate(dossier))
    if amount <= 0:
        return result(Outcome.INELIGIBLE, "§§1, 3", "No positive affected-API fee basis.")
    return result(Outcome.ELIGIBLE, "§§1, 3, 4", "Covered API, archived status interval, submitted documentation, "
                  "initial exclusion screen, filing clock and affected fees support a local claim.", amount)

def scoped(dossier: dict, body: dict) -> bool:
    return all(body.get(key) == dossier[key]
               for key in ("account", "product", "region", "start", "end", "month"))


def ticket_for(tenant: str, dossier: dict, supplement: list[dict]) -> Ticket:
    # Tenant is supplied by the authenticated caller via the desk. Documents
    # come only from the tenant's persisted case dossier, never from an HTTP body.
    docs = [Document.from_archive(tenant, item) for item in dossier["initial_documents"] + supplement]
    return Ticket(tenant, dossier["account"], dossier["month"], dossier["product"], dossier["region"],
                  "SLA Claim", "Twilio Customer Support (simulation)", dossier["start"], dossier["end"],
                  estimate(dossier), tuple(docs))


def find_supplement(dossier: dict, needed_kind: str) -> dict | None:
    filed_refs = {doc["ref"] for doc in dossier["initial_documents"]}
    for doc in dossier["supplemental_archive"]:
        if doc["kind"] == needed_kind and doc["ref"] not in filed_refs and scoped(dossier, doc):
            return doc
    return None


def disposition(reply: Reply, dossier: dict, is_response: bool) -> tuple[str, str]:
    if reply.code == "AWARD":
        return "AWARDED", "Record the simulated future-use credit. Posting and bill application require separate receipts."
    if reply.code == "PARTIAL_AWARD":
        return "PARTIAL_AWARD_REVIEW", "Preserve the confirmed portion. Route the outstanding amount to a human without accepting a settlement."
    if reply.code == "DOCUMENTATION_NEEDED" and not is_response:
        return "NEEDS_EVIDENCE", "A component attachment is missing. Search the scoped archive before requesting follow-up approval."
    if reply.code == "MAINTENANCE_EXCLUDED":
        for notice in dossier["customer_notice_archive"]:
            if (notice["kind"] == "maintenance_notice" and scoped(dossier, notice)
                    and datetime.fromisoformat(notice["issued_at"])
                    <= datetime.fromisoformat(dossier["start"]) - timedelta(hours=24)):
                return "DENIAL_ACCEPTED", f"Customer notice {notice['ref']} independently confirms the exclusion. Close without a rebuttal."
        return "HUMAN_REVIEW", "The customer archive cannot corroborate the stated exclusion. Refer the disagreement to a reviewer."
    if reply.code == "WINDOW_CLOSED":
        return "EXPIRED", "The local claim clock has closed. No waiver assumed."
    return "HUMAN_REVIEW", "The evidence cannot resolve the vendor's position. Stop automated correspondence and refer the case to a human."


def recognized_award(reply: Reply, requested: str) -> str | None:
    """Preserve an anomalous incoming reply for review without booking its value."""
    try:
        amount = Decimal(reply.awarded)
        ceiling = Decimal(requested)
        if not amount.is_finite() or amount < 0 or amount > ceiling or amount != amount.quantize(CENT):
            return None
    except (InvalidOperation, TypeError, ValueError):
        return None
    if reply.code == "AWARD":
        valid = amount == ceiling and amount > 0
    elif reply.code == "PARTIAL_AWARD":
        valid = 0 < amount < ceiling
    else:
        valid = amount == 0
    return format(amount, ".2f") if valid else None
