"""Mount both V4 application paths and resolve published terms against independent inbox evidence."""
from datetime import timedelta
from decimal import Decimal, localcontext
from functools import partial
from hashlib import sha256
import json

from fastapi import Depends

from .contracts import DraftReviewer, Citation, EvaluationResult, Money, Outcome, Principal, fingerprint
from .correspondence import CorrespondenceDesk
from .correspondence_api import make_correspondence_router
from .correspondence_rules import ActiveRemedy
from .correspondence_types import SOURCE, instant
from .storage import database
from .twilio import calendar_bounds
from .vendor_api import make_router
from .vendor_registry import evaluate_active_db
from .correspondence_resource import exclusive_cutoff, join_resource
from .correspondence_service import join_service, service_procedure
from .correspondence_history import procedure
from .correspondence_artifacts import HISTORICAL
from .correspondence_artifacts import SUPPLEMENTS
from .vendor_terms import candidate_version


def _economics(manifest, overlay):
    if manifest["family"] == "resource-month/1":
        fields = ("family","period","scope","symptoms","provider_causes","exclusions","fee_basis","fee_exclusions",
                  "rounding","filing","cycle_calendar_month","submission_channel","request_fields","remedy",
                  "account_conditions","precedence","label_bindings","maintenance","prior_credit",
                  "supplement","interval_measurement","fee_adjustment","subscription","telemetry",
                  "original_receipt","cure_clock","fee_settlement","causal_report",
                  "fixed_period","fixed_filing","aggregate_monitor","service_fee","record_integrity","denial_policy")
        semantics = {k:manifest.get(k) for k in fields}
        semantics["tiers"] = [(t["below_units"],t["credit_units"]) for t in manifest["tiers"]]
        semantics["billing_period"] = overlay.get("billing_period", {}).get("kind") if overlay.get("billing_period") else None
        semantics["override"] = overlay.get("override",{}).get("filing_days")
        semantics["private_plan"] = overlay["plan"]
        semantics["private_mappings"] = [overlay.get(k) for k in ("symptom_aliases","cause_aliases","public_plan","public_product")]
        return fingerprint(semantics)
    tiers = sorted((t["below_units"], t["credit_units"]) for t in manifest["tiers"]
                   if t["product"] == overlay["product"] and t["plan"] == overlay["plan"])
    filing_days = overlay.get("override", {}).get("filing_days", manifest["filing_days"])
    return fingerprint([manifest["family"], manifest["period"], manifest["remedy"], overlay["plan"], tiers, filing_days])


def _period(manifest, overlay):
    return (max(manifest["effective"][0], overlay["effective_from"]),
            min(manifest["effective"][1] or overlay["effective_until"], overlay["effective_until"]))


def _active_publication(db, tenant, scope):
    """Read the committed ACTIVE slot without attempting a nested write reservation."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='v4_vendor_event'").fetchone():
        return None
    first, following = calendar_bounds(instant(scope.month + "-01T00:00:00Z").date(), "UTC")
    month_start = first.date().isoformat()
    month_last = (following - timedelta(days=1)).date().isoformat()
    lookup = (tenant, scope.vendor, scope.account, scope.contract, scope.service)
    rows = db.execute("""SELECT e.vendor, e.payload, a.version, a.payload FROM v4_vendor_event e
        JOIN v4_vendor_artifact a ON a.tenant=e.tenant AND a.vendor=e.vendor
          AND a.version=json_extract(e.payload, '$.active_version')
        WHERE e.tenant=? AND e.revision=(SELECT max(v.revision) FROM v4_vendor_event v
          WHERE v.tenant=e.tenant AND v.vendor=e.vendor)
          AND json_extract(a.payload, '$.manifest.vendor')=?
          AND json_extract(a.payload, '$.overlay.account')=?
          AND json_extract(a.payload, '$.overlay.agreement')=?
          AND json_extract(a.payload, '$.overlay.product')=?""", lookup)
    rows = list(rows)
    whole_service = any(json.loads(row[3])["manifest"].get("aggregate_monitor") for row in rows)
    matches = []
    for installation, state_json, version, artifact_json in rows:
        artifact = json.loads(artifact_json)
        if not whole_service and artifact["overlay"].get("resource_id") and artifact["overlay"]["resource_id"] != scope.component:
            continue
        if artifact["overlay"].get("subscription_record", {}).get("region",scope.region) != scope.region:
            continue
        if artifact["manifest"].get("family") not in {"monthly-availability/1","resource-month/1"}:
            return None
        left, right = _period(artifact["manifest"], artifact["overlay"])
        if left <= month_last and right >= month_start:
            if left > month_start or right < month_last:
                return None
            matches.append((installation, json.loads(state_json), version, artifact))
    if len(matches) != 1:
        return None
    installation, state, version, artifact = matches[0]
    manifest, overlay = artifact["manifest"], artifact["overlay"]
    if (candidate_version(manifest, overlay, artifact["extraction"]) != version
            or manifest["document"]["sha256"] != sha256(artifact["source_text"].encode()).hexdigest()
            or (manifest["family"] == "monthly-availability/1" and
                (manifest["period"] != "utc_calendar_month" or manifest["remedy"] != "affected_monthly_fees_future_invoice"))
            or state["active_version"] != version or overlay["currency"] != scope.currency):
        return None
    # A later publication may assert different terms for a month already
    # covered by an earlier activated agreement. This family has no amendment
    # precedence interpreter, so overlapping material revisions cannot be chosen.
    history = db.execute("""SELECT DISTINCT a.payload FROM v4_vendor_artifact a
        JOIN v4_vendor_event e ON a.tenant=e.tenant AND a.vendor=e.vendor
          AND json_extract(e.payload,'$.active_version')=a.version
        WHERE a.tenant=? AND json_extract(a.payload,'$.manifest.vendor')=?
          AND json_extract(a.payload,'$.overlay.account')=? AND json_extract(a.payload,'$.overlay.agreement')=?
          AND json_extract(a.payload,'$.overlay.product')=? AND a.version!=?""", (*lookup, version))
    for row in history:
        prior = json.loads(row[0])
        old_manifest, old_overlay = prior["manifest"], prior["overlay"]
        if (not manifest.get("aggregate_monitor") and not old_manifest.get("aggregate_monitor")
                and old_overlay.get("resource_id") and old_overlay["resource_id"] != scope.component):
            continue
        if old_overlay.get("subscription_record", {}).get("region",scope.region) != scope.region:
            continue
        if old_manifest.get("family") != manifest["family"]:
            return None
        left, right = _period(old_manifest, old_overlay)
        if left <= month_last and right >= month_start and (
                old_manifest["family"] != manifest["family"] or _economics(old_manifest, old_overlay) != _economics(manifest, overlay)
                or old_overlay["fee_line_ref"] != overlay["fee_line_ref"]):
            return None
    return installation, state, manifest, overlay


def _joined_observation(scope, events, overlay, received_at):
    """Translate the complete scoped source attestations into the published evaluator's facts."""
    by_kind = {}
    for event in events:
        kind = event["kind"]
        if kind in SUPPLEMENTS:
            continue
        if SOURCE.get(kind) != event["source"] or kind in by_kind:
            raise ValueError("Conflicting evidence or an unverified source role requires review.")
        by_kind[kind] = event
    for kind in ("status", "impact", "invoice", "coverage"):
        if kind not in by_kind:
            raise ValueError(f"Awaiting independent {kind} evidence.")
    if by_kind.keys() - {"status","impact","invoice","component","coverage"}:
        raise ValueError("The published rule does not establish how this maintenance notice affects the claim.")
    status, impact, invoice = (by_kind[k]["body"] for k in ("status", "impact", "invoice"))
    start, end = instant(status["start"]), instant(status["end"])
    first, following = calendar_bounds(instant(scope.month + "-01T00:00:00Z").date(), "UTC")
    if not first <= start < end <= following or (end - start) % timedelta(minutes=1):
        raise ValueError("A complete whole-minute status interval within the service month is required.")
    for k in ("impact", "component"):
        if k in by_kind and any(by_kind[k]["body"][endpoint] != status[endpoint] for endpoint in ("start", "end")):
            raise ValueError("Customer and status records disagree about the affected interval.")
    if "component" in by_kind and by_kind["component"]["body"]["component_id"] != scope.component:
        raise ValueError("The component record does not match the account binding.")
    if impact["exclusion"] != "none":
        raise ValueError("Customer attribution does not establish exclusion-adjusted downtime under this contract.")
    eligible_minutes = (end-start)//timedelta(minutes=1) if impact["affected"] else 0
    coverage = by_kind["coverage"]["body"]
    if (instant(coverage["start"]) != first or instant(coverage["end"]) != following or not coverage["complete"]
            or not coverage["exclusions_removed"] or coverage["incident_ids"] != [scope.incident]
            or coverage["total_eligible_minutes"] != eligible_minutes):
        raise ValueError("Signed monthly coverage, exclusions and countable downtime do not reconcile to this incident.")
    lines = invoice["lines"]
    if len({line["id"] for line in lines}) != len(lines):
        raise ValueError("Duplicate invoice line references cannot establish the affected fee.")
    if any(line[k] != getattr(scope, k) for line in lines for k in scope.model_fields_set if k in line):
        raise ValueError("An invoice line contradicts the authenticated claim scope.")
    basis = [line for line in lines if line["kind"] == "affected_api"]
    if len(basis) != 1 or basis[0]["id"] != overlay["fee_line_ref"]:
        raise ValueError("A single affected invoice line must match the active overlay's fee line reference.")
    with localcontext() as context:
        context.prec = 50
        cents = int(Decimal(basis[0]["amount"]) * 100)
    return dict(agreement=scope.contract, account=scope.account, product=scope.service, plan=overlay["plan"],
                month=scope.month, eligible_downtime_minutes=eligible_minutes,
                monitor_source="simulated_vendor", monitor_month=scope.month, monitor_ref=by_kind["status"]["digest"],
                month_complete=coverage["complete"], exclusions_removed=coverage["exclusions_removed"], monthly_fee_cents=cents, fee_line_ref=basis[0]["id"],
                fee_month=scope.month, fee_ref=by_kind["invoice"]["digest"], received_at=received_at.isoformat())


def _filing_receipts(db, tenant, scope):
    """Authenticate immutable local packets before using them as dated filing evidence."""
    row = db.execute("SELECT state FROM inbox_claim WHERE tenant=? AND scope=?", (tenant, scope.model_dump_json())).fetchone()
    receipts = json.loads(row[0])["submissions"] if row else []
    if len(receipts) > 2:
        raise ValueError("Historical filings exceed the one-supplement policy.")
    for receipt in receipts:
        packet = receipt["packet"]
        if (packet["scope"] != scope.model_dump() or packet["tenant"] != tenant
                or fingerprint(packet) != receipt["approval"]["digest"] or receipt["digest"] != receipt["approval"]["digest"]
                or receipt["id"] != "LOCAL-" + receipt["digest"][:24]):
            raise ValueError("Historical filing receipt no longer matches its approved scope and packet.")
    return receipts


def resolve_active(path, tenant, scope, events, at):
    """Re-evaluate the current published source, with no financial input from the reviewer request."""
    with database(path) as db:
        db.execute("BEGIN")
        binding = _active_publication(db, tenant, scope)
        if binding is None:
            return None
        installation, state, manifest, overlay = binding
        receipts = _filing_receipts(db, tenant, scope)
        filed = instant(receipts[0]["at"]) if receipts else at
        resource = manifest["family"] == "resource-month/1"
        aggregate = bool(manifest.get("aggregate_monitor"))
        filing = raw = gap = cutoff = historical = None
        if resource and not aggregate and any(e["kind"] in HISTORICAL for e in events):
            try:
                # This entry point also rejects stale interpreter semantics before
                # using a published clause for a nonfinancial procedural response.
                evaluate_active_db(db, Principal(tenant,"local-active-join","viewer"), installation, {},
                                   expected_version=state["active_version"], expected_revision=state["revision"])
                historical = procedure(scope, events, manifest, overlay)
            except ValueError:
                historical = None
        try:
            if aggregate:
                obs, filing = join_service(scope, events, manifest, overlay, filed, receipts)
            elif resource:
                obs, filing = join_resource(scope, events, manifest, overlay, filed, receipts)
            else:
                _, following = calendar_bounds(instant(scope.month+"-01T00:00:00Z").date(), "UTC")
                cutoff = following + timedelta(days=overlay.get("override",{}).get("filing_days",manifest["filing_days"]))
                obs = _joined_observation(scope, events, overlay, filed)
            raw = evaluate_active_db(db, Principal(tenant,"local-active-join","viewer"), installation, obs,
                                     expected_version=state["active_version"], expected_revision=state["revision"])
            if resource:
                cutoff = exclusive_cutoff(raw)
        except ValueError as error:
            gap = str(error)
        if aggregate:
            historical = service_procedure(events, manifest, raw)
    if not cutoff and historical:
        cutoff = instant(historical["cutoff"])
    publication = state["active_version"]
    cited = tuple(Citation(manifest["document"]["name"], publication,
                           f"Clause {c['id']} (active revision {state['revision']})", manifest["document"]["uri"])
                  for c in manifest["citations"] if c["field"] != "heading")
    dates = _period(manifest, overlay)
    cited += (Citation("Authorized scope", publication, f"Governing period {dates[0]} through {dates[1]}", "urn:uptime:scope"),)
    for e in events:
        issuer = fingerprint([e["subject"], e.get("source_key_id"), e.get("source_grant_id")])
        cited += (Citation("Authenticated " + e["source"] + " · " + e["subject"], e["digest"],
                           e["event_id"] + " known " + e.get("known_at", e["received_at"]) + " · signer " + issuer,
                           "urn:uptime:inbox-evidence"),)
    if overlay.get("override"):
        cited += (Citation(overlay["override"]["source_ref"], fingerprint(overlay["override"]),
                           "Signed filing-window override", "urn:uptime:private:filing-amendment"),)
    if gap:
        result = EvaluationResult(Outcome.MISSING, cited, (gap,), (gap,))
    else:
        amount = Money(Decimal(raw["amount"])) if raw["amount"] is not None else None
        if amount is not None and amount.amount == 0:
            result = EvaluationResult(Outcome.INELIGIBLE, cited, ("The mapped fee line yields no positive contractual amount.",))
        else:
            result = EvaluationResult(Outcome(raw["outcome"]), cited, tuple(raw["trace"]), tuple(raw["missing"]), amount)
    # The economic key describes governing rules for this month. Reformatting
    # or reissuing the same terms must not mint another monthly obligation.
    controlling = _economics(manifest, overlay)
    measurement = None
    if result.outcome == Outcome.ELIGIBLE:
        if resource:
            measurement = {k:raw[k] for k in ("downtime_microseconds","total_microseconds")}
        else:
            first, following = calendar_bounds(instant(scope.month + "-01T00:00:00Z").date(), "UTC")
            measurement = dict(downtime_microseconds=obs["eligible_downtime_minutes"] * 60_000_000,
                               total_microseconds=(following-first)//timedelta(microseconds=1))
    return ActiveRemedy(tenant, scope, fingerprint([[e["source"], e["digest"]] for e in events]),
                        controlling, cutoff, result, agreement_id=manifest.get("agreement") or overlay["agreement"],
                        remedy=("resource-month/aggregate-service" if aggregate else
                                "resource-month/"+scope.component+("/"+scope.region if manifest.get("subscription") else "") if resource else "availability"), filing_material=filing,
                        measurement=measurement, procedure=historical)


def register_v4_routes(app, bench, auth):
    inbox = CorrespondenceDesk(bench.path, active_resolver=partial(resolve_active, bench.path))
    app.state.correspondence = bench.inbox = inbox

    def reader(p=Depends(auth.actor)):
        if not auth.approvals_enabled or bench.setting(p)["mode"] == "OBSERVE":
            return Principal(p.tenant, p.subject, "viewer")
        return p

    def vendor_reader(p=Depends(auth.actor)):
        if p.role == "reviewer" and (not auth.approvals_enabled or bench.setting(p)["mode"] == "OBSERVE"):
            return DraftReviewer(p.tenant, p.subject, p.role)
        return p

    app.include_router(make_router(bench.path, vendor_reader, auth.reviewer, bench.check_write, bench.mutex))
    app.include_router(make_correspondence_router(inbox, reader, auth.reviewer, bench.check_write, auth.service))
