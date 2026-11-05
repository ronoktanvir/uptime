"""Evidence joins for one independently attested monthly API incident and invoice."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Callable

from . import twilio
from .contracts import Citation, EvaluationResult, Outcome, fingerprint
from .correspondence_types import Scope, instant
from .correspondence_artifacts import SUPPLEMENTS
from .disputes_wire import TERMS, VERSION, deadline

@dataclass(frozen=True)
class ActiveRemedy:
    """Optional trusted resolver result from a promoted, server-persisted evaluation.

    A resolver must re-read the ACTIVE publication and scoped evidence on each
    approval/send. A version change therefore invalidates an existing approval.
    """
    tenant: str
    scope: Scope
    evidence_digest: str
    version: str
    cutoff: datetime | None
    evaluation: EvaluationResult
    agreement_id: str = ""
    remedy: str = "availability"
    filing_material: dict | None = None
    measurement: dict | None = None
    procedure: dict | None = None


Resolver = Callable[[str, Scope, tuple[dict, ...], datetime], ActiveRemedy | None]


@dataclass(frozen=True)
class Assessment:
    evaluation: EvaluationResult
    cutoff: datetime | None
    version: str
    evidence_digest: str
    agreement_id: str = "twilio-apis"
    remedy: str = "availability"
    filing_material: dict | None = None
    measurement: dict | None = None
    procedure: dict | None = None


def assess(tenant, scope, events, at, filed=None, resolver: Resolver | None = None):
    facts = tuple(e for e in events if e["kind"] != "message")
    digest = fingerprint([[e["source"], e["digest"]] for e in facts])
    cited = (Citation("Twilio APIs SLA", VERSION, "§§1, 3, 4", TERMS),)
    supported = scope.vendor.casefold() == "twilio" and scope.service == "Twilio Messaging API"
    version = VERSION if supported else ""
    cutoff = deadline(scope.month) if supported else None

    def stop(outcome, why):
        clauses = cited if supported else (Citation("Unresolved agreement", "unverified", "Scope", "urn:uptime:missing:terms"),)
        result = EvaluationResult(outcome, clauses, (why,), (why,) if outcome == Outcome.MISSING else ())
        return Assessment(result, cutoff, version, digest)

    if not supported:
        active = resolver(tenant, scope, facts, at) if resolver else None
        if (active is None or active.tenant != tenant or active.scope != scope or active.evidence_digest != digest
                or not active.version or not active.agreement_id or (active.cutoff is None and active.evaluation.outcome == Outcome.ELIGIBLE)
                or (active.cutoff is not None and active.cutoff.utcoffset() is None)):
            return stop(Outcome.UNSUPPORTED, "No ACTIVE evaluation and remedy terms match this tenant, scope and evidence.")
        if active.evaluation.outcome == Outcome.ELIGIBLE and active.cutoff is not None and (filed or at) >= active.cutoff:
            return Assessment(EvaluationResult(Outcome.INELIGIBLE, active.evaluation.clauses, ("Verified filing window closed.",)),
                              active.cutoff, active.version, digest, active.agreement_id, active.remedy, active.filing_material, active.measurement, active.procedure)
        return Assessment(active.evaluation, active.cutoff, active.version, digest, active.agreement_id, active.remedy, active.filing_material, active.measurement, active.procedure)

    month = datetime.strptime(scope.month, "%Y-%m").date()
    first, following = twilio.calendar_bounds(month, "UTC")
    if first.date().isoformat() < VERSION:
        return stop(Outcome.UNSUPPORTED, "This dated agreement cannot establish the entire service month's applicability.")
    if scope.currency != "USD":
        return stop(Outcome.UNSUPPORTED, "USD mapping required.")
    grouped = {}
    for e in facts:
        if e["kind"] in SUPPLEMENTS:
            continue
        grouped.setdefault(e["kind"], []).append(e)
    if grouped.keys() - {"status","impact","invoice","component","notice","coverage"}:
        return stop(Outcome.MISSING, "Unsupported evidence conflicts with the ordinary API profile.")
    for kind in ("status", "impact", "invoice"):
        if not grouped.get(kind):
            return stop(Outcome.MISSING, f"Awaiting an authenticated {kind} record for this exact claim.")
    if any(len(group) > 1 for group in grouped.values()):
        return stop(Outcome.MISSING, "Contradictory independent records require review. No version is selected silently.")
    status, impact, invoice = (grouped[k][0] for k in ("status", "impact", "invoice"))
    start, end = (instant(status["body"][k]) for k in ("start", "end"))
    if not first <= start < end <= following:
        return stop(Outcome.MISSING, "Status interval does not match the supported service month.")
    for kind in ("impact", "notice", "component"):
        if kind in grouped and any(grouped[kind][0]["body"][k] != status["body"][k] for k in ("start", "end")):
            return stop(Outcome.MISSING, "Evidence disagrees about the affected interval.")
    if "coverage" in grouped:
        report = grouped["coverage"][0]["body"]
        if (instant(report["start"]) != first or instant(report["end"]) != following
                or not report["complete"] or not report["exclusions_removed"] or report["incident_ids"] != [scope.incident]):
            return stop(Outcome.MISSING, "The independent month report contradicts the supported incident scope.")
        if ("notice" not in grouped and impact["body"]["exclusion"] == "none" and
                timedelta(minutes=report["total_eligible_minutes"]) != (end-start if impact["body"]["affected"] else timedelta())):
            return stop(Outcome.MISSING, "The month report contradicts customer-attributed downtime.")
    if "component" in grouped and grouped["component"][0]["body"]["component_id"] != scope.component:
        return stop(Outcome.MISSING, "The customer attachment identifies a different component.")
    I = impact["body"]
    exclusion = {"none": twilio.Exclusion.NONE, "unknown": twilio.Exclusion.UNKNOWN,
                 "customer": twilio.Exclusion.CUSTOMER_TECHNOLOGY}[I["exclusion"]]
    notice_hours = None
    if "notice" in grouped:
        issued = instant(grouped["notice"][0]["body"]["issued_at"])
        if issued > at:
            return stop(Outcome.MISSING, "A future notice cannot corroborate maintenance.")
        if issued <= start and exclusion != twilio.Exclusion.CUSTOMER_TECHNOLOGY:
            exclusion = twilio.Exclusion.SCHEDULED_MAINTENANCE
            # SLA test is inclusive and needs only whole hours for the 24-hour comparison.
            notice_hours = Decimal((start - issued) // timedelta(hours=1))
    kinds = dict(affected_api=twilio.FeeKind.API, unaffected_api=twilio.FeeKind.API,
                 carrier=twilio.FeeKind.CARRIER, tax=twilio.FeeKind.TAX, third_party=twilio.FeeKind.THIRD_PARTY)
    fees = []
    for line in invoice["body"]["lines"]:
        if any(line[k] != getattr(scope, k) for k in scope.model_fields_set if k in line):
            return stop(Outcome.MISSING, "Invoice line contradicts its authenticated envelope.")
        kind = line["kind"]
        fees.append(twilio.FeeLine(line["id"], "unaffected-other" if kind == "unaffected_api" else scope.service,
                                   month, kinds[kind], Decimal(line["amount"]), scope.currency, True,
                                   invoice["digest"], invoice["digest"]))
    # Provisioning attests the ordinary subscription and calendar. A signed
    # status event is the connector's complete monthly single-incident record.
    coverage = twilio.Coverage(first, following, True, scope.contract)
    status_coverage = twilio.Coverage(first, following, True, status["digest"])
    interval = twilio.StatusInterval(start, end, scope.service, "https://status.twilio.com", (status["digest"],),
                                     I["affected"], impact["digest"], exclusion, impact["digest"], notice_hours)
    data = twilio.TwilioInput(month, "UTC", scope.contract, twilio.ServiceScope(
        scope.service, twilio.ServiceFamily.TWILIO, True, True, scope.contract),
        twilio.Plan.BASE, scope.contract, coverage, status_coverage, (interval,), tuple(fees), True,
        invoice["digest"], at, scope.contract, currency=scope.currency, submitted_at=filed,
        submission_ref="local-receipt" if filed else "")
    result = twilio.evaluate(data)
    measurement = None
    if result.outcome == Outcome.ELIGIBLE:
        # This tight profile admits one verified, fully in-month qualifying incident.
        measurement = dict(downtime_microseconds=(end-start)//timedelta(microseconds=1),
                           total_microseconds=(following-first)//timedelta(microseconds=1))
    return Assessment(result, cutoff, version, digest, measurement=measurement)


def confirmed_maintenance(scope, events):
    if scope.vendor.casefold() != "twilio" or scope.service != "Twilio Messaging API":
        return False
    status = [e["body"] for e in events if e["kind"] == "status"]
    notices = [e["body"] for e in events if e["kind"] == "notice"]
    return (len(status) == len(notices) == 1 and
            all(status[0][k] == notices[0][k] for k in ("start", "end")) and
            instant(notices[0]["issued_at"]) <= instant(status[0]["start"]) - timedelta(hours=24))
