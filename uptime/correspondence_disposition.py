"""Read-only dispute trace: evidence, interpretation, deterministic checks, next actions, disposition.

This module classifies what the case already holds. It never approves, files,
books an award, closes a claim or changes the claim scope. Categories describe
the relationship between a counterparty assertion, its exact source text and the
governing terms as the deterministic engine currently evaluates them.
"""
from decimal import Decimal, localcontext

from .contracts import fingerprint
from .correspondence_interpretation import text_digest
from .correspondence_types import Digest, Strict


class DenialAcceptance(Strict):
    """The exact basis digest the reviewer saw on the offered accept-denial action."""
    basis_digest: Digest

MISSING = frozenset({"component", "artifact", "filing_fields"})
DENIAL = frozenset({"maintenance", "time_bar", "availability", "downtime"})
ESCALATION = ("AMBIGUOUS_GROUNDS", "CHANGED_SCOPE")
GROUND = dict(maintenance="scheduled maintenance exclusion", time_bar="claim filing window",
              availability="availability commitment", downtime="qualifying downtime measurement",
              component="claim documentation requirement", artifact="claim documentation requirement",
              filing_fields="claim documentation requirement", scope_error="account and resource scope",
              award="service credit remedy")
DISPOSITION = dict(DRAFTED="PREPARE_CLAIM", CLAIM_APPROVED="PREPARE_CLAIM", AWAITING_VENDOR="AWAIT_RESPONSE",
                   HISTORICAL_FILING="AWAIT_RESPONSE", NEEDS_EVIDENCE="AWAIT_CURE_EVIDENCE",
                   AWAITING_NOTICE="AWAIT_EVIDENCE", DENIAL_REVIEW="DENIAL_SUBSTANTIATED",
                   DENIAL_ACCEPTED="ACCEPT_DENIAL", AWARDED="AWARD_RECORDED",
                   PARTIAL_AWARD_REVIEW="PARTIAL_AWARD_RECORDED", HUMAN_REVIEW="ESCALATE")
AUTHORITY = "Read-only projection. It grants no approval, filing, award, closure or change of claim scope."


def _money(raw):
    from .correspondence_interpretation import _amount
    return _amount(raw)


def _month(raw):
    from .correspondence_interpretation import _period
    return _period(raw)


def denial_category(stage, rebutted=False):
    if stage in {"DENIAL_REVIEW", "DENIAL_ACCEPTED"}:
        return "CONTRACTUAL_DENIAL"
    if rebutted or stage in {"RESPONSE_DRAFTED", "RESPONSE_APPROVED"}:
        return "INCORRECT_FACTUAL_ASSERTION"
    return "UNRESOLVED_DENIAL"


def disposition(stage, reason):
    if stage in {"RESPONSE_DRAFTED", "RESPONSE_APPROVED"}:
        return "CURE" if reason in MISSING else "REBUT"
    return DISPOSITION.get(stage, stage)


def _proposition_category(p, context, stage, is_primary):
    slots = {s.name: s.source.quote for s in p.slots}
    if p.referent != "current_claim":
        return "CHANGED_SCOPE"
    if "period" in slots:
        try:
            if _month(slots["period"]) != context["scope"]["month"]:
                return "CHANGED_SCOPE"
        except ValueError:
            return "AMBIGUOUS_GROUNDS"
    if p.family == "unsupported" or p.modality != "asserted" or p.polarity == "uncertain" or p.conditions:
        return "AMBIGUOUS_GROUNDS"
    if p.family == "award":
        if p.polarity == "negative":
            return None  # A bare "no credit" takes the category of its stated ground.
        if context.get("requested") is None or "award" not in slots:
            return "AMBIGUOUS_GROUNDS"
        try:
            award, claimed = _money(slots["award"]), Decimal(context["requested"])
        except ValueError:
            return "AMBIGUOUS_GROUNDS"
        if award == claimed:
            return "AWARD_REPORTED"
        return "PARTIAL_AWARD" if 0 < award < claimed else "AMBIGUOUS_GROUNDS"
    if p.polarity != "positive":
        return "AMBIGUOUS_GROUNDS"
    if p.family in MISSING:
        return "MISSING_EVIDENCE"
    if p.family == "scope_error":
        ref, field = slots.get("scope_ref"), p.scope_field
        if field and ref and context["scope"].get(field) != ref:
            return "INCORRECT_FACTUAL_ASSERTION"
        return "AMBIGUOUS_GROUNDS"
    if p.family in DENIAL:
        return denial_category(stage) if is_primary else "UNRESOLVED_DENIAL"
    return "AMBIGUOUS_GROUNDS"


def case_category(categories, primary):
    """The primary mapped proposition governs; otherwise any escalation category controls."""
    if primary is not None and categories[primary]:
        return categories[primary]
    for name in ESCALATION:
        if name in categories:
            return name
    found = [c for c in categories if c]
    return found[0] if found else "AMBIGUOUS_GROUNDS"


def classify_reading(context, interpretation, proposal, stage, primary=None, clauses=()):
    """Per-proposition categories for a reviewer's preview, linked to source bytes and governing terms."""
    if proposal.reason == "unknown":
        primary = None
    rows, categories = [], []
    for i, p in enumerate(interpretation.propositions):
        category = _proposition_category(p, context, stage, i == primary)
        categories.append(category)
        rows.append(dict(index=i, family=p.family, polarity=p.polarity, modality=p.modality, referent=p.referent,
                         source=dict(p.source.model_dump(), unit="utf8_bytes"),
                         conditions=[c.quote for c in p.conditions], slots={s.name: s.source.quote for s in p.slots},
                         ground=GROUND.get(p.family), governing=list(clauses),
                         contract_version=context.get("contract_version"),
                         contract_source_sha256=context.get("contract_source_sha256"),
                         drives_disposition=i == primary))
    overall = case_category(categories, primary)
    for row, category in zip(rows, categories):
        row["category"] = category or overall
    if proposal.reason == "award" and overall == "PARTIAL_AWARD":
        with localcontext() as ctx:
            ctx.prec = 50
            contested = Decimal(context["requested"]) - Decimal(proposal.amount)
        rows[primary]["contested_remainder"] = format(contested, ".2f")
    return dict(category=overall, propositions=rows)


def _span(reply, text):
    if not reply.get("span"):
        return None
    start, end = reply["span"]
    if reply.get("reviewed_interpretation"):
        quote = text.encode("utf-8")[start:end].decode("utf-8", "replace")
        return dict(start=start, end=end, quote=quote, unit="utf8_bytes")
    return dict(start=start, end=end, quote=text[start:end], unit="characters")


def _reply_category(reply, state, scope, later):
    reason = reply["reason"]
    if reason in MISSING:
        return "MISSING_EVIDENCE"
    if reason in DENIAL:
        return denial_category(state["stage"] if not later else "", rebutted=any(
            s["packet"].get("vendor_event") == reply["digest"] for s in state["submissions"][1:]))
    if reason == "scope_error":
        return "INCORRECT_FACTUAL_ASSERTION" if state.get("scope_correction") else "AMBIGUOUS_GROUNDS"
    if reason == "award":
        claimed = Decimal(state["submissions"][0]["requested"]) if state["submissions"] else None
        awarded = Decimal(state["awarded"])
        if claimed is not None and awarded == claimed:
            return "AWARD_REPORTED"
        return "PARTIAL_AWARD" if claimed is not None and 0 < awarded < claimed else "AMBIGUOUS_GROUNDS"
    return "AMBIGUOUS_GROUNDS"


def _checks(desk, scope, state, current, view):
    evaluation = current.evaluation
    checks = [dict(check="governing_evaluation", result=str(evaluation.outcome), detail=list(evaluation.trace),
                   missing=list(evaluation.missing))]
    submissions = state["submissions"]
    if submissions and current.cutoff is not None:
        from .correspondence_types import instant
        filed = instant(submissions[0]["at"])
        checks.append(dict(check="original_filing_within_window", result=filed < current.cutoff,
                           filed_at=submissions[0]["at"], filing_cutoff=current.cutoff.isoformat()))
        original = submissions[0]
        followups = submissions[1:]
        if followups:
            checks.append(dict(check="follow_ups_preserve_original_filing",
                               result=all(s["packet"].get("in_reply_to") == original["id"]
                                          and s["packet"].get("filing_cutoff") == original["packet"].get("filing_cutoff")
                                          for s in followups),
                               original=original["id"], follow_ups=[s["id"] for s in followups]))
    if scope.vendor.casefold() == "twilio" and scope.service == "Twilio Messaging API":
        explicit = any(e["kind"] == "coverage" for e in state["evidence"])
        # The ordinary profile treats one provisioned single-incident status record as the
        # month's record unless an explicit month report arrives (W5 finding F3, D07 pending).
        checks.append(dict(check="month_coverage_basis",
                           result="EXPLICIT_MONTH_REPORT" if explicit else "PROVISIONED_SINGLE_INCIDENT_RECORD",
                           detail=None if explicit else "No signed complete-month report; the amount is evaluated from a "
                                  "single status record that provisioning treats as the month's only incident."))
    if state.get("reason") == "maintenance":
        checks.append(dict(check="timely_independent_maintenance_notice",
                           result=desk._maintenance_substantiated(scope, state, evaluation)))
    if current.measurement:
        checks.append(dict(check="verified_measurement", result=True, measurement=current.measurement,
                           counterparty_downtime_microseconds=state.get("vendor_downtime_us")))
    basis = desk._denial_basis(scope, state, current)
    if state["stage"] == "DENIAL_REVIEW":
        checks.append(dict(check="denial_ground_substantiated", result=basis is not None, basis=basis,
                           basis_digest=fingerprint(basis) if basis else None,
                           filing_cutoff=current.cutoff.isoformat() if current.cutoff else None))
    if state.get("denial_acceptance"):
        checks.append(dict(check="explicit_denial_acceptance", result=True, **state["denial_acceptance"]))
    ledger = view["ledger"]
    with localcontext() as ctx:
        ctx.prec = 50
        conserved = Decimal(ledger["awarded"]) <= Decimal(ledger["claimed"]) or not submissions
    checks.append(dict(check="award_not_above_claim", result=conserved, claimed=ledger["claimed"], awarded=ledger["awarded"]))
    return checks


def dispute_trace(desk, interpretations, p, claim_id):
    from .correspondence import authorize
    from .storage import database
    authorize(p)
    with database(desk.path) as db:
        view = desk._view(db, p, claim_id)
        scope, state = desk._read(db, p.tenant, claim_id)
    current = desk._assess(p.tenant, scope, state, desk._now())
    stage = view["stage"]
    stale = stage == "DENIAL_REVIEW" and desk._denial_basis(scope, state, current) is None
    effective = dict(state, stage="HUMAN_REVIEW") if stale else state
    texts = {e["digest"]: e["body"]["text"] for e in state["evidence"] if e["kind"] == "message"}
    replies = []
    for i, reply in enumerate(state["replies"]):
        text = texts.get(reply["digest"], "")
        later = i != len(state["replies"]) - 1
        origin = ("reviewed_interpretation" if reply.get("reviewed_interpretation")
                  else "unresolved" if reply["reason"] in {"unknown", "contradictory_correspondence"} else "finite_grammar")
        replies.append(dict(receipt=reply["receipt"], event_id=reply["event_id"], digest=reply["digest"],
                            received_at=reply["received_at"], text=text, text_sha256=text_digest(text),
                            interpretation=dict(origin=origin, review_id=reply.get("reviewed_interpretation"),
                                                family=reply["reason"], source=_span(reply, text)),
                            ground=GROUND.get(reply["reason"]),
                            category=_reply_category(reply, effective, scope, later)))
    reviewed = []
    if (interpretations is not None and p.role == "reviewer" and view["stage"] == "HUMAN_REVIEW"
            and view.get("interpretation_review_url")):
        # Another reviewer's reading is shown only after this actor's own blind entry.
        try:
            bridge = interpretations.view(p, claim_id)
        except (ValueError, KeyError):
            bridge = None
        if bridge and bridge["blind_entry"] is not None:
            with database(desk.path) as db:
                ids = [row["id"] for row in db.execute(
                    "SELECT id FROM inbox_interpretation WHERE tenant=? AND claim_id=? AND kind='review' AND context=? "
                    "ORDER BY created_at", (p.tenant, claim_id, bridge["context"]["digest"]))]
            for review_id in ids:
                try:
                    preview = interpretations.preview(p, claim_id, review_id)
                except ValueError:
                    continue
                reviewed.append(dict(review_id=review_id, reviewer=preview["reviewer"], disposition=preview["disposition"],
                                     prepare_allowed=preview["prepare_allowed"], reported_award=preview["reported_award"],
                                     assertions=preview["assertions"], preview_digest=preview["digest"]))
    category = replies[-1]["category"] if replies else None
    own = [r for r in reviewed if r["reviewer"] == p.subject]
    if own and replies and replies[-1]["interpretation"]["origin"] == "unresolved":
        # Only the requester's own latest reading sets the headline; others are rows.
        category = own[-1]["assertions"]["category"]
    procedure = current.procedure or {}
    trace = dict(
        claim=dict(id=claim_id, tenant=p.tenant, scope=scope.model_dump(), obligation_id=view["obligation_id"],
                   stage=view["stage"], state_sha256=view["state_sha256"]),
        governing=dict(agreement_id=current.agreement_id or None, contract_version=current.version or None,
                       contract_source_sha256=current.contract_source_sha256, clauses=view["preflight"]["clauses"],
                       filing_cutoff=view["filing_cutoff"], response_cutoff=procedure.get("response_cutoff"),
                       original_filed_at=(state["submissions"][0]["at"] if state["submissions"] else procedure.get("filed_at"))),
        evidence=[dict(event_id=e["event_id"], kind=e["kind"], source=e["source"], issuer=e.get("subject"),
                       source_grant_id=e.get("source_grant_id"), digest=e["digest"], received_at=e["received_at"],
                       known_at=e.get("known_at", e["received_at"])) for e in state["evidence"] if e["kind"] != "message"],
        correspondence=replies,
        reviewed_readings=reviewed,
        submissions=[dict(id=s["id"], action=s["action"], at=s["at"], digest=s["digest"], requested=s["requested"],
                          in_reply_to=s["packet"].get("in_reply_to"), filing_cutoff=s["packet"].get("filing_cutoff"),
                          argument=s["packet"].get("argument"), approved_by=s["approval"]["actor"],
                          approved_at=s["approval"]["at"]) for s in state["submissions"]],
        deterministic_checks=_checks(desk, scope, state, current, view),
        permitted_next_actions=[a["id"] for a in view["actions"]]
            + (["interpretation-review"] if view.get("interpretation_review_url") else []),
        category=category,
        disposition="ESCALATE" if stale else disposition(stage, state.get("reason")),
        stale_denial_review=stale,
        final=view["stage"] in {"DENIAL_ACCEPTED", "AWARDED"},
        ledger=view["ledger"],
        authority=AUTHORITY)
    trace["digest"] = fingerprint(trace)
    return trace
