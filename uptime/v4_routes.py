"""Mount both V4 application paths and resolve published terms against independent inbox evidence."""
from datetime import timedelta
from decimal import Decimal, localcontext
from functools import partial
from hashlib import sha256
import json

from fastapi import Depends

from .contracts import Citation, EvaluationResult, Money, Outcome, Principal, fingerprint
from .correspondence import CorrespondenceDesk
from .correspondence_api import make_correspondence_router
from .correspondence_rules import ActiveRemedy
from .correspondence_types import SOURCE, instant
from .storage import database
from .twilio import calendar_bounds
from .vendor_api import make_router
from .vendor_eval import evaluate
from .vendor_terms import candidate_version


def _active_publication(db, tenant, scope):
    """Read the committed ACTIVE slot without attempting a nested write reservation."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='v4_vendor_event'").fetchone():
        return None
    rows = db.execute("""SELECT e.payload, a.version, a.payload FROM v4_vendor_event e
        JOIN v4_vendor_artifact a ON a.tenant=e.tenant AND a.vendor=e.vendor
          AND a.version=json_extract(e.payload, '$.active_version')
        WHERE e.tenant=? AND e.revision=(SELECT max(v.revision) FROM v4_vendor_event v
          WHERE v.tenant=e.tenant AND v.vendor=e.vendor)
          AND json_extract(a.payload, '$.manifest.vendor')=?
          AND json_extract(a.payload, '$.overlay.account')=?
          AND json_extract(a.payload, '$.overlay.agreement')=?
          AND json_extract(a.payload, '$.overlay.product')=? LIMIT 2""",
        (tenant, scope.vendor, scope.account, scope.contract, scope.service)).fetchall()
    if len(rows) != 1:
        return None
    state_json, version, artifact_json = tuple(rows[0])
    state, artifact = json.loads(state_json), json.loads(artifact_json)
    manifest, overlay = artifact["manifest"], artifact["overlay"]
    if (candidate_version(manifest, overlay, artifact["extraction"]) != version
            or manifest["document"]["sha256"] != sha256(artifact["source_text"].encode()).hexdigest()
            or manifest["family"] != "monthly-availability/1"
            or manifest["period"] != "utc_calendar_month" or manifest["remedy"] != "affected_monthly_fees_future_invoice"
            or state["active_version"] != version or overlay["currency"] != scope.currency):
        return None
    return state, manifest, overlay


def _joined_observation(scope, events, overlay, received_at):
    """Translate the complete scoped source attestations into the published evaluator's facts."""
    by_kind = {}
    for event in events:
        kind = event["kind"]
        if SOURCE.get(kind) != event["source"] or kind in by_kind:
            raise ValueError("Conflicting evidence or an unverified source role requires review.")
        by_kind[kind] = event
    for kind in ("status", "impact", "invoice"):
        if kind not in by_kind:
            raise ValueError(f"Awaiting independent {kind} evidence.")
    if "notice" in by_kind:
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
                month=scope.month, eligible_downtime_minutes=(end-start)//timedelta(minutes=1) if impact["affected"] else 0,
                monitor_source="simulated_vendor", monitor_month=scope.month, monitor_ref=by_kind["status"]["digest"],
                month_complete=True, exclusions_removed=True, monthly_fee_cents=cents, fee_line_ref=basis[0]["id"],
                fee_month=scope.month, fee_ref=by_kind["invoice"]["digest"], received_at=received_at.isoformat())


def _filed_at(db, tenant, scope, at):
    # During an inbound reply the actual historical receipt controls timeliness.
    # A prospective claim uses the current authenticated action time.
    row = db.execute("SELECT state FROM inbox_claim WHERE tenant=? AND scope=?", (tenant, scope.model_dump_json())).fetchone()
    submissions = json.loads(row[0])["submissions"] if row else []
    if not submissions:
        return at
    initial = submissions[0]
    if (initial["packet"]["scope"] != scope.model_dump() or initial["packet"]["tenant"] != tenant or
            fingerprint(initial["packet"]) != initial["approval"]["digest"] or initial["digest"] != initial["approval"]["digest"]):
        raise ValueError("Historical filing receipt no longer matches its approved scope and packet.")
    return instant(initial["at"])


def resolve_active(path, tenant, scope, events, at):
    """Re-evaluate the current published source, with no financial input from the reviewer request."""
    with database(path) as db:
        db.execute("BEGIN")
        binding = _active_publication(db, tenant, scope)
        if binding is None:
            return None
        state, manifest, overlay = binding
        filed = _filed_at(db, tenant, scope, at)
    _, following = calendar_bounds(instant(scope.month + "-01T00:00:00Z").date(), "UTC")
    days = overlay.get("override", {}).get("filing_days", manifest["filing_days"])
    cutoff = following + timedelta(days=days)
    publication = state["active_version"]
    cited = tuple(Citation(manifest["document"]["name"], publication,
                           f"Clause {c['id']} (active revision {state['revision']})", manifest["document"]["uri"])
                  for c in manifest["citations"] if c["field"] != "heading")
    if overlay.get("override"):
        cited += (Citation(overlay["override"]["source_ref"], fingerprint(overlay["override"]),
                           "Signed filing-window override", "urn:uptime:private:filing-amendment"),)
    try:
        obs = _joined_observation(scope, events, overlay, filed)
    except ValueError as error:
        result = EvaluationResult(Outcome.MISSING, cited, (str(error),), (str(error),))
    else:
        raw = evaluate(manifest, overlay, obs, tenant)
        amount = Money(Decimal(raw["amount"])) if raw["amount"] is not None else None
        if amount is not None and amount.amount == 0:
            result = EvaluationResult(Outcome.INELIGIBLE, cited, ("The mapped fee line yields no positive contractual amount.",))
        else:
            result = EvaluationResult(Outcome(raw["outcome"]), cited, tuple(raw["trace"]), tuple(raw["missing"]), amount)
    # The economic key describes governing rules for this month. Reformatting
    # or reissuing the same terms must not mint another monthly obligation.
    tiers = sorted((t["below_units"], t["credit_units"]) for t in manifest["tiers"]
                   if t["product"] == scope.service and t["plan"] == overlay["plan"])
    controlling = fingerprint([manifest["family"], manifest["period"], manifest["remedy"], overlay["plan"], tiers, days])
    return ActiveRemedy(tenant, scope, fingerprint([[e["source"], e["digest"]] for e in events]),
                        controlling, cutoff, result, agreement_id=manifest["agreement"])


def register_v4_routes(app, bench, auth):
    inbox = CorrespondenceDesk(bench.path, active_resolver=partial(resolve_active, bench.path))
    app.state.correspondence = bench.inbox = inbox

    def reader(p=Depends(auth.actor)):
        if not auth.approvals_enabled or bench.setting(p)["mode"] == "OBSERVE":
            return Principal(p.tenant, p.subject, "viewer")
        return p

    app.include_router(make_router(bench.path, reader, auth.reviewer, bench.check_write, bench.mutex))
    app.include_router(make_correspondence_router(inbox, reader, auth.reviewer, bench.check_write, auth.service))
