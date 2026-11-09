"""Claimant evaluation of scoped, pinned evidence available at each decision."""
from calendar import monthrange
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext

from uptime.contracts import Citation, EvaluationResult, Money, Outcome, fingerprint
from uptime.disputes_wire import CENT, TERMS, VERSION, Document, Reply, Ticket, account_identity, canonical, deadline, instant

GROUPS = ("initial_documents", "supplemental_archive", "customer_notice_archive")


def estimate(dossier: dict) -> str:
    """Exact contractual entitlement; no unsupported settlement rounding."""
    with localcontext() as context:
        context.prec = 80
        fees = sum((Decimal(line["usd"]) for line in dossier["invoice_lines"]
                    if line["kind"] == "affected_api"), Decimal(0))
        value = fees / Decimal(10)
        return format(value, ".2f") if value == value.quantize(CENT) else format(value, "f")


def settlement_expressible(value: str) -> bool:
    try:
        with localcontext() as context:
            context.prec = 80
            amount = Decimal(value)
            return amount.is_finite() and amount > 0 and amount == amount.quantize(CENT)
    except (InvalidOperation, ValueError, TypeError):
        return False


def available(body: dict, at: datetime) -> bool:
    # Missing arrival metadata must never conceal a known maintenance notice.
    observed = instant(body.get("observed_at", body.get("issued_at", body["end"])))
    arrived = instant(body.get("available_at", body.get("observed_at", body.get("issued_at", body["end"]))))
    if arrived < observed:
        raise ValueError("Availability cannot precede observation.")
    return arrived <= at.astimezone(UTC)


def scoped(dossier: dict, body: dict) -> bool:
    try:
        return (all(body.get(key) == dossier.get(key) for key in ("account", "product", "region", "month"))
                and all(instant(body[key]) == instant(dossier[key]) for key in ("start", "end")))
    except (KeyError, ValueError, TypeError):
        return False


def verified(dossier: dict, body: dict) -> bool:
    ref = body.get("ref")
    return (canonical(ref) and dossier.get("artifact_registry", {}).get(ref) == fingerprint(body)
            and body.get("source") == "DETERMINISTIC_REPLAY")


def valid_document(dossier: dict, body: dict) -> bool:
    return (verified(dossier, body) and scoped(dossier, body)
            and body.get("origin") == "synthetic_status_archive"
            and body.get("classification") in {"redacted_replay", "restricted"}
            and body.get("kind") in {"status_summary", "component_record"}
            and (body["kind"] != "component_record" or
                 canonical(body.get("component_id")) and body["component_id"] == dossier.get("component_id")))


def available_documents(dossier: dict, at: datetime) -> list[dict]:
    return [doc for group in GROUPS for doc in dossier.get(group, []) if available(doc, at)]


def maintenance(dossier: dict, at: datetime) -> tuple[str, dict | None]:
    """Consult every available archive; relevant but unverified evidence blocks."""
    for body in available_documents(dossier, at):
        if body.get("kind") != "maintenance_notice":
            continue
        if any(body.get(key) != dossier.get(key) for key in ("account", "product", "region", "month")):
            continue
        start, end = instant(dossier["start"]), instant(dossier["end"])
        left, right = instant(body["start"]), instant(body["end"])
        if right <= start or left >= end:
            continue
        if not verified(dossier, body) or not canonical(body.get("ref")):
            return "unresolved", body
        if instant(body["issued_at"]) <= left - timedelta(hours=24):
            return ("excluded" if left <= start and right >= end else "unresolved"), body
        return "unresolved", body
    return "clear", None


def preflight(dossier: dict, at: datetime) -> EvaluationResult:
    def result(outcome, section, detail, amount=None):
        clauses = (Citation("Twilio APIs SLA", VERSION, section, TERMS),)
        return EvaluationResult(outcome, clauses, (detail,), (detail,) if outcome == Outcome.MISSING else (),
                                Money(amount) if amount is not None else None)

    if (dossier.get("governing_version") != VERSION or dossier.get("plan") != "standard"
            or dossier.get("product") != "Twilio Messaging API" or dossier.get("currency") != "USD"
            or dossier.get("vendor") != "Twilio"):
        return result(Outcome.UNSUPPORTED, "§§1, 3", "No supported agreement, plan, covered API or USD fee mapping.")
    try:
        start, end = (instant(dossier[k]) for k in ("start", "end"))
        month = dossier["month"]
        deadline(month)
        first = datetime.strptime(month, "%Y-%m").replace(tzinfo=UTC)
        next_month = first + timedelta(days=monthrange(first.year, first.month)[1])
        if first < datetime(2026, 4, 9, tzinfo=UTC):
            return result(Outcome.UNSUPPORTED, "Effective date", "The monthly period predates the governing April 9, 2026 agreement.")
        if not first <= start < end <= next_month or (end - start) % timedelta(minutes=1) or at.utcoffset() is None:
            raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return result(Outcome.MISSING, "§§1, 3", "A scoped, supported whole-minute status interval and aware clock are required.")
    if at < next_month or at >= deadline(month):
        return result(Outcome.INELIGIBLE, "§3", "Outside the supported UTC post-month filing period.")
    if (not all(canonical(dossier.get(key)) for key in ("account", "region", "component_id", "invoice_id"))
            or not account_identity(dossier.get("account"))):
        return result(Outcome.MISSING, "§3", "Canonical account, invoice, component and region identifiers are required.")
    try:
        known = available_documents(dossier, at)
        exclusion, _ = maintenance(dossier, at)
        if exclusion == "excluded" or dossier.get("exclusion_screen") == "confirmed_excluded":
            return result(Outcome.INELIGIBLE, "§4(d)", "Available evidence identifies an excluded maintenance interval.")
        initial = dossier.get("initial_documents", [])
        if (not initial or any(doc not in known or not valid_document(dossier, doc) for doc in initial)
                or not any(doc.get("kind") == "status_summary" for doc in initial)
                or any(not valid_document(dossier, doc) for doc in known
                       if doc.get("kind") in {"status_summary", "component_record"} and scoped(dossier, doc))
                or len({doc.get("ref") for doc in known}) != len(known)):
            raise ValueError
        exclusion, _ = maintenance(dossier, at)
    except (KeyError, ValueError, TypeError):
        return result(Outcome.MISSING, "§3", "Pinned, nonblank, scoped document/component references and valid availability times are required.")
    if exclusion == "excluded" or dossier.get("exclusion_screen") == "confirmed_excluded":
        return result(Outcome.INELIGIBLE, "§4(d)", "Available evidence identifies an excluded maintenance interval.")
    if exclusion == "unresolved" or dossier.get("exclusion_screen") != "no_known_exclusion":
        return result(Outcome.MISSING, "§4", "Known exclusion evidence is missing, conflicting or unresolved.")
    if end - start < timedelta(minutes=5) or (end - start) * 2000 <= next_month - first:
        return result(Outcome.INELIGIBLE, "§§1, 3, 4(g)", "The countable interval does not breach the ordinary API threshold.")
    lines = dossier.get("invoice_lines", [])
    kinds = {"affected_api", "carrier", "tax", "third_party", "unaffected_api"}
    if not lines or len({line.get("id") for line in lines}) != len(lines) or any(not canonical(line.get("id")) for line in lines):
        return result(Outcome.MISSING, "§1", "Distinct canonical invoice line identifiers are required.")
    if any(line.get("kind") not in kinds for line in lines):
        return result(Outcome.UNSUPPORTED, "§1", "An unmapped charge prevents a verified affected-fee calculation.")
    try:
        with localcontext() as context:
            context.prec = 80
            for line in lines:
                value = Decimal(line["usd"])
                if (set(line) != {"id", "kind", "usd", "account", "month", "product", "region", "currency", "invoice_id", "evidence_ref"}
                        or not isinstance(line["usd"], str) or len(line["usd"]) > 40 or not value.is_finite()
                        or value < 0 or value != value.quantize(CENT)
                        or any(line.get(key) != dossier.get(key) for key in
                               ("account", "month", "product", "region", "currency", "invoice_id"))
                        or not canonical(line.get("evidence_ref"))
                        or dossier.get("invoice_registry", {}).get(line["id"]) != fingerprint(line)):
                    raise ValueError
            if len({line["evidence_ref"] for line in lines}) != len(lines):
                raise ValueError
            amount = Decimal(estimate(dossier))
    except (InvalidOperation, KeyError, TypeError, ValueError):
        return result(Outcome.MISSING, "§1", "Verified invoice lines must bind finite USD cents to this account, service, region, month and invoice.")
    if amount <= 0:
        return result(Outcome.INELIGIBLE, "§§1, 3", "No positive affected-API fee basis.")
    detail = "Governing dates, available archived evidence, exclusions, filing clock and verified invoice scope support the exact entitlement."
    if not settlement_expressible(str(amount)):
        detail += " Fractional-cent entitlement requires human review; no contractual settlement rounding rule is established."
    return result(Outcome.ELIGIBLE, "§§1, 3, 4", detail, amount)


def ticket_for(tenant: str, dossier: dict, supplement: list[dict], *, at: datetime | None = None) -> Ticket:
    if not canonical(tenant) or tenant != dossier.get("tenant") or dossier.get("vendor") != "Twilio":
        raise ValueError("Tenant and vendor must match the provisioned dossier.")
    if at is None:
        at = datetime.max.replace(tzinfo=UTC)
    # Include all known component proof before filing, even if stored in a supplemental archive.
    candidates = dossier["initial_documents"] + [doc for doc in dossier.get("supplemental_archive", [])
                  if available(doc, at) and valid_document(dossier, doc)] + supplement
    docs = {}
    for item in candidates:
        if not available(item, at) or not valid_document(dossier, item):
            raise ValueError("Unverified or unavailable document cannot enter the ticket.")
        if item.get("classification") != "redacted_replay":
            raise ValueError("Restricted document cannot enter the simulator.")
        document = Document.minimized(tenant, item)
        if document.fact.ref in docs and docs[document.fact.ref] != document:
            raise ValueError("Conflicting document identity.")
        docs[document.fact.ref] = document
    return Ticket(tenant, dossier["account"], dossier["month"], dossier["product"], dossier["region"],
                  "SLA Claim", "Twilio Customer Support (simulation)", dossier["start"], dossier["end"],
                  estimate(dossier), tuple(docs.values()), governing_version=dossier["governing_version"])


def find_supplement(dossier: dict, needed_kind: str, *, at: datetime | None = None) -> dict | None:
    at = at or datetime.max.replace(tzinfo=UTC)
    filed_refs = {doc["ref"] for doc in dossier["initial_documents"]}
    for doc in dossier["supplemental_archive"]:
        if (doc["kind"] == needed_kind and doc.get("ref") not in filed_refs
                and available(doc, at) and valid_document(dossier, doc)):
            return doc
    return None


def disposition(reply: Reply, dossier: dict, is_response: bool, *, filed_at: datetime | None = None,
                received_at: datetime | None = None) -> tuple[str, str]:
    if reply.code == "AWARD":
        return "AWARDED", "Record the simulated future-use credit. Posting and bill application require separate receipts."
    if reply.code == "PARTIAL_AWARD":
        return "PARTIAL_AWARD_REVIEW", "Preserve the confirmed portion. Route the outstanding amount to a human without accepting a settlement."
    if reply.code == "DOCUMENTATION_NEEDED" and not is_response:
        return "NEEDS_EVIDENCE", "A component attachment is missing. Search the scoped archive before requesting follow-up approval."
    if reply.code == "MAINTENANCE_EXCLUDED" and received_at is not None:
        try:
            exclusion, notice = maintenance(dossier, received_at)
            if exclusion == "excluded":
                return "DENIAL_ACCEPTED", f"Customer notice {notice['ref']} available by reply receipt independently confirms the exclusion. Close without a rebuttal."
        except (KeyError, ValueError, TypeError):
            pass
        return "HUMAN_REVIEW", "The available customer archive cannot corroborate the stated exclusion. Refer the disagreement to a reviewer."
    if reply.code == "WINDOW_CLOSED":
        if filed_at is not None and filed_at >= deadline(dossier["month"]):
            return "EXPIRED", "The independently checked initial receipt is outside the local filing window."
        return "HUMAN_REVIEW", "The vendor time-bar conflicts with a timely initial receipt or lacks verified receipt evidence. No waiver or expiry inferred."
    return "HUMAN_REVIEW", "The evidence cannot resolve the vendor's position. Stop automated correspondence and refer the case to a human."


def recognized_award(reply: Reply, requested: str) -> str | None:
    try:
        with localcontext() as context:
            context.prec = 80
            amount, ceiling = Decimal(reply.awarded), Decimal(requested)
            if (not amount.is_finite() or not ceiling.is_finite() or amount < 0
                    or amount > ceiling or amount != amount.quantize(CENT)):
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
