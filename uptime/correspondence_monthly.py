"""Join strict whole-service month evidence for the opt-in ``complete_service_month/1`` basis.

Opt-in only (parent relay "USER APPROVED strict monthly-evidence path now", 2026-11-09): this
join runs only when reviewed monthly-availability terms carry the exact, source-grounded marker
(uptime.claim_scope.complete_service_month). Without it the legacy incident join in
uptime.v4_routes and the built-in Twilio profile are unchanged.

Two independent, authenticated records establish one UTC calendar month for one whole service:

* ``monthly_coverage`` from the status source: the complete, exclusion-adjusted measurement;
* ``invoice`` from the billing source: the existing invoice record, so the governing-fee resolver
  (uptime.governing_fees) stays the only stepped-credit fee authority.

Optional ``monthly_attribution`` from an independently enrolled customer source must corroborate the
report if supplied. A third source is not universally required by the reviewed whole-month basis.

The join validates and translates. It never computes a rate, an amount or a filing window. Its only
output is the existing evaluator observation (uptime.vendor_eval.FACT_FIELDS), and the deterministic
evaluator decides the outcome. Every refusal raises ValueError, which the route reports as
INSUFFICIENT_EVIDENCE with the reason. No value is defaulted, and no incident is invented.
"""
from decimal import Decimal, localcontext
import re

from pydantic import ValidationError

from .correspondence_artifacts import SUPPLEMENTS
from .correspondence_types import (MONTHLY_IDENTITY, Invoice, MonthlyAttribution, MonthlyCoverage, SOURCE,
                                   instant)
from .evidence_applicability import month_bounds

REPORTS = {"monthly_coverage": MonthlyCoverage, "monthly_attribution": MonthlyAttribution}
REQUIRED = ("monthly_coverage", "invoice")
ALLOWED = frozenset((*REQUIRED, "monthly_attribution"))
# Legacy monthly incident evidence. Mixing it into strict month evidence is refused, never reconciled.
LEGACY_KINDS = frozenset({"status", "impact", "coverage", "component", "notice"})
# The monetary evaluator and the governing-fee registry are USD-only.
SUPPORTED_CURRENCIES = frozenset({"USD"})
WHOLE_SERVICE_ABSENT = ("component", "incident", "region")
PROVENANCE = ("subject", "source_key_id", "source_grant_id")
DIGEST = re.compile(r"[0-9a-f]{64}")


def _known(event):
    """Server-recorded receipt time of a stored delivery (known_at, else received_at)."""
    try:
        received = instant(event["received_at"])
        known = instant(event.get("known_at", event["received_at"]))
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("Strict month evidence requires a retained server receipt time.") from None
    if known < received:
        raise ValueError("Strict month evidence cannot be known before the server received it.")
    return known


def _group(events):
    groups = {}
    for event in events:
        kind = event["kind"]
        if kind in SUPPLEMENTS:
            continue
        if kind in LEGACY_KINDS:
            raise ValueError("Legacy incident status, impact or coverage records cannot be mixed into "
                             "strict whole-month evidence.")
        if kind not in ALLOWED:
            raise ValueError("The whole-month evidence basis does not establish how to use this " + kind + " record.")
        if SOURCE[kind] != event["source"] or kind in groups:
            raise ValueError("Duplicate or wrong-role whole-month evidence requires review.")
        groups[kind] = event
    for kind in REQUIRED:
        if kind not in groups:
            raise ValueError("Awaiting independent " + kind + " evidence for the whole service month.")
    return groups


def _provenance(groups):
    for event in groups.values():
        if (any(not isinstance(event.get(k), str) or not event[k] for k in PROVENANCE)
                or not isinstance(event.get("digest"), str) or not DIGEST.fullmatch(event["digest"])):
            raise ValueError("Strict month evidence requires retained authenticated source provenance.")
    for key in PROVENANCE:
        if len({event[key] for event in groups.values()}) != len(groups):
            raise ValueError("Included month evidence records require distinct enrolled sources "
                             "(subject, key and grant).")


def _same_identity(scope, record, what):
    for name in MONTHLY_IDENTITY:
        if record.get(name) is not None and record[name] != getattr(scope, name):
            raise ValueError("The " + what + " names " + name + " outside the authenticated claim scope.")


def _report(scope, overlay, event, first, following, month_minutes, at):
    kind = event["kind"]
    try:
        body = REPORTS[kind].model_validate(event["body"]).model_dump()
    except ValidationError:
        raise ValueError("The " + kind + " record is not a valid strict month report.") from None
    _same_identity(scope, body, kind + " report")
    if instant(body["start"]) != first or instant(body["end"]) != following:
        raise ValueError("The " + kind + " report must cover exactly the UTC calendar month " + scope.month + ".")
    if body["complete"] is not True or body["exclusions_removed"] is not True:
        raise ValueError("The " + kind + " report must be complete with exclusions removed.")
    if body["gaps"] or body["unresolved_exclusions"]:
        raise ValueError("The " + kind + " report states measurement gaps or unresolved exclusions.")
    if body["plan"] != overlay["plan"]:
        raise ValueError("The " + kind + " report is for a different plan than the governing overlay.")
    minutes = body["eligible_downtime_minutes"]
    if type(minutes) is not int or not 0 <= minutes <= month_minutes:
        raise ValueError("The " + kind + " report needs whole eligible downtime minutes within the month.")
    observed, known = instant(body["observed_at"]), _known(event)
    received = instant(event["received_at"])
    if not following <= observed <= received <= known <= at:
        raise ValueError("The " + kind + " report must be observed and received after the month ends, "
                         "and not in the future.")
    return minutes


def _covered_fee(scope, overlay, event, at):
    try:
        body = Invoice.model_validate(event["body"]).model_dump()
    except ValidationError:
        raise ValueError("The billing record is not a valid invoice.") from None
    if _known(event) > at:
        raise ValueError("The invoice is not yet known at the evaluation time.")
    lines = body["lines"]
    if len({line["id"] for line in lines}) != len(lines):
        raise ValueError("Duplicate invoice line references cannot establish the affected fee.")
    invoices = {line["invoice"] for line in lines if line["invoice"] is not None}
    if len(invoices) > 1 or (scope.invoice is not None and invoices - {scope.invoice}):
        raise ValueError("Invoice lines name contradictory invoice identities.")
    for line in lines:
        _same_identity(scope, line, "invoice line " + line["id"])
        if any(line[name] is not None for name in WHOLE_SERVICE_ABSENT):
            raise ValueError("A whole-service invoice line cannot name a component, incident or region.")
        if line["kind"] == "tax" and Decimal(line["amount"]) != 0:
            raise ValueError("A nonzero tax line makes the covered fee basis unsupported.")
    basis = [line for line in lines if line["kind"] == "affected_api"]
    if len(basis) != 1 or basis[0]["id"] != overlay["fee_line_ref"]:
        raise ValueError("A single affected invoice line must match the active overlay's fee line reference.")
    with localcontext() as context:
        context.prec = 50
        cents = Decimal(basis[0]["amount"]) * 100
        if cents != cents.to_integral_value():
            raise ValueError("The covered fee line must be exact cents.")
    return int(cents), basis[0]["id"]


def monthly_observation(scope, events, overlay, filed, at):
    """Return the existing evaluator observation for one strict whole-service month, or raise ValueError.

    ``filed`` is the original filing time (or the draft evaluation time), passed unchanged as
    ``received_at`` so month end, filing days and cutoff stay with the evaluator. ``at`` is the
    trusted evaluation time; no report may be observed or known after it.
    """
    if any(getattr(scope, name) is not None for name in WHOLE_SERVICE_ABSENT):
        raise ValueError("Strict whole-month evidence applies only to a whole-service scope without "
                         "component, incident or region.")
    if scope.currency not in SUPPORTED_CURRENCIES or overlay.get("currency") != scope.currency:
        raise ValueError("Unsupported or mismatched currency for strict whole-month evidence.")
    if at.utcoffset() is None or filed.utcoffset() is None:
        raise ValueError("Trusted, offset-aware evaluation and filing times are required.")
    groups = _group(events)
    _provenance(groups)
    first, following = month_bounds(scope.month)
    month_minutes = (following - first).days * 24 * 60
    coverage = _report(scope, overlay, groups["monthly_coverage"], first, following, month_minutes, at)
    if "monthly_attribution" in groups:
        attribution = _report(scope, overlay, groups["monthly_attribution"], first, following, month_minutes, at)
        if coverage != attribution:
            raise ValueError("Status coverage and customer attribution disagree about eligible downtime minutes.")
    cents, fee_line = _covered_fee(scope, overlay, groups["invoice"], at)
    return dict(agreement=scope.contract, account=scope.account, product=scope.service, plan=overlay["plan"],
                month=scope.month, eligible_downtime_minutes=coverage,
                monitor_source="simulated_vendor", monitor_month=scope.month, monitor_ref=groups["monthly_coverage"]["digest"],
                month_complete=True, exclusions_removed=True, monthly_fee_cents=cents, fee_line_ref=fee_line,
                fee_month=scope.month, fee_ref=groups["invoice"]["digest"], received_at=filed.isoformat())
