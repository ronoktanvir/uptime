"""Tenant-scoped, assisted-mode workflow for local synthetic Twilio claims.

Public entry points: DisputeDesk(sqlite_path), seed(tenant), cases(principal),
case(principal, case_id), act(principal, case_id, action_id). All amounts USD.
clock=None selects explicit deterministic replay time; clock() may instead return
an aware datetime to enforce real elapsed time in tests or a runner. No transport.
"""
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from calendar import monthrange
from pathlib import Path

from uptime.contracts import EvaluationResult, Outcome, Principal, Source, fingerprint
from uptime import disputes_claimant as claimant
from uptime import disputes_vendor as vendor
from uptime.disputes_wire import FIXTURES, TERMS, VERSION, deadline, instant

START = datetime(2026, 11, 2, 10, tzinfo=UTC)
COOLDOWN = timedelta(hours=24)
ROLE_READ = {"viewer", "reviewer"}
ACTIONS = {
    "DRAFTED": ("approve-claim", "Approve simulated claim"),
    "CLAIM_APPROVED": ("submit-claim", "Submit to vendor simulator"),
    "NEEDS_EVIDENCE": ("prepare-response", "Find supporting evidence"),
    "RESPONSE_DRAFTED": ("approve-response", "Approve evidence supplement"),
    "RESPONSE_APPROVED": ("submit-response", "Send evidence to simulator"),
}
SYNTHETIC = [Source.CUSTOMER, Source.REPLAY]
SIMULATED = [Source.VENDOR, Source.REPLAY]
MIXED = [Source.PUBLIC, Source.CUSTOMER, Source.VENDOR, Source.REPLAY]


class DisputeConflict(ValueError):
    """Invalid workflow action or unavailable retry; map to HTTP 409."""


def event(state, principal, at, detail, sources, **fields):
    state["timeline"].append(dict(at=at.isoformat(), event=detail, actor=principal.subject,
                                  role=principal.role, tenant=principal.tenant, sources=sources, **fields))


def authorized(principal: Principal, write=False):
    if not principal.subject or not principal.tenant or principal.role not in ({"reviewer"} if write else ROLE_READ):
        raise PermissionError("Dispute policy denies this action.")


class DisputeDesk:
    def __init__(self, db_path, *, clock=None):
        self.path = Path(db_path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS dispute_cases (
                tenant TEXT NOT NULL, id TEXT NOT NULL, dossier TEXT NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY(tenant, id))""")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS dispute_obligations (
                    tenant TEXT NOT NULL, obligation TEXT NOT NULL, case_id TEXT NOT NULL,
                    PRIMARY KEY(tenant, obligation));
                CREATE TABLE IF NOT EXISTS dispute_artifacts (
                    tenant TEXT NOT NULL, account TEXT NOT NULL, category TEXT NOT NULL,
                    ref TEXT NOT NULL, digest TEXT NOT NULL,
                    PRIMARY KEY(tenant, account, category, ref));
                CREATE TABLE IF NOT EXISTS dispute_manifests (
                    tenant TEXT NOT NULL, account TEXT NOT NULL, digest TEXT NOT NULL,
                    PRIMARY KEY(tenant, account, digest));
                CREATE TABLE IF NOT EXISTS dispute_receipts (
                    id TEXT PRIMARY KEY, tenant TEXT NOT NULL, case_id TEXT NOT NULL,
                    obligation TEXT NOT NULL, action TEXT NOT NULL, body TEXT NOT NULL,
                    UNIQUE(tenant, obligation, action));
                CREATE TRIGGER IF NOT EXISTS dispute_artifacts_no_update BEFORE UPDATE ON dispute_artifacts
                    BEGIN SELECT RAISE(ABORT, 'immutable dispute artifact'); END;
                CREATE TRIGGER IF NOT EXISTS dispute_artifacts_no_delete BEFORE DELETE ON dispute_artifacts
                    BEGIN SELECT RAISE(ABORT, 'immutable dispute artifact'); END;
                CREATE TRIGGER IF NOT EXISTS dispute_manifests_no_update BEFORE UPDATE ON dispute_manifests
                    BEGIN SELECT RAISE(ABORT, 'immutable source manifest'); END;
                CREATE TRIGGER IF NOT EXISTS dispute_manifests_no_delete BEFORE DELETE ON dispute_manifests
                    BEGIN SELECT RAISE(ABORT, 'immutable source manifest'); END;
                CREATE TRIGGER IF NOT EXISTS dispute_receipts_no_update BEFORE UPDATE ON dispute_receipts
                    BEGIN SELECT RAISE(ABORT, 'immutable dispute receipt'); END;
                CREATE TRIGGER IF NOT EXISTS dispute_receipts_no_delete BEFORE DELETE ON dispute_receipts
                    BEGIN SELECT RAISE(ABORT, 'immutable dispute receipt'); END;
                CREATE TRIGGER IF NOT EXISTS dispute_obligations_no_update BEFORE UPDATE ON dispute_obligations
                    BEGIN SELECT RAISE(ABORT, 'immutable obligation reservation'); END;
                CREATE TRIGGER IF NOT EXISTS dispute_obligations_no_delete BEFORE DELETE ON dispute_obligations
                    BEGIN SELECT RAISE(ABORT, 'immutable obligation reservation'); END;
            """)

    def _connect(self):
        return sqlite3.connect(self.path, isolation_level=None, timeout=10)

    def seed(self, tenant: str):
        """Explicit server provisioning; clients cannot create tenants."""
        if not tenant:
            raise ValueError("tenant required")
        dossiers = json.loads((FIXTURES / "claimant" / "dossiers.json").read_text())
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            for case_id, dossier in dossiers.items():
                # Source pins come from approved local provisioning, never a request body.
                for category in ("artifact_registry", "invoice_registry"):
                    for ref, digest in dossier.get(category, {}).items():
                        db.execute("INSERT OR IGNORE INTO dispute_artifacts VALUES(?,?,?,?,?)",
                                   (tenant, dossier["account"], category, ref, digest))
                manifest = fingerprint({key: dossier.get(key, {}) for key in ("artifact_registry", "invoice_registry")})
                db.execute("INSERT OR IGNORE INTO dispute_manifests VALUES(?,?,?)", (tenant, dossier["account"], manifest))
                state = dict(stage="DRAFTED", cursor=START.isoformat(), supplement=[], approval=None,
                             completed=[], timeline=[], submissions=[], replies=[], next_contact=None,
                             needed_kind=None, failed_sends={},
                             ledger=dict(estimated=claimant.estimate(dossier), claimed="0.00",
                                         awarded="0.00", disputed_remainder="0.00", posted="0.00", applied="0.00"))
                event(state, Principal(tenant, "fixture-loader", "system"), START,
                      "Claim drafted from synthetic October API charges and a replayed status interval.", SYNTHETIC)
                db.execute("INSERT OR IGNORE INTO dispute_cases VALUES(?,?,?,?)",
                           (tenant, case_id, json.dumps(dossier), json.dumps(state)))

    def _get(self, db, principal, case_id):
        row = db.execute("SELECT dossier,state FROM dispute_cases WHERE tenant=? AND id=?",
                         (principal.tenant, case_id)).fetchone()
        if row is None:
            raise KeyError("Dispute case not found.")
        return json.loads(row[0]), json.loads(row[1])

    def _integrity(self, db, tenant, dossier):
        if dossier.get("tenant") != tenant:
            return False
        rows = db.execute("SELECT category,ref,digest FROM dispute_artifacts WHERE tenant=? AND account=?",
                          (tenant, dossier.get("account"))).fetchall()
        pinned = {(category, ref): digest for category, ref, digest in rows}
        declared = {(category, ref): digest for category in ("artifact_registry", "invoice_registry")
                    for ref, digest in dossier.get(category, {}).items()}
        actual = {}
        for group in claimant.GROUPS:
            for doc in dossier.get(group, []):
                key = ("artifact_registry", doc.get("ref"))
                if key in actual:
                    return False
                actual[key] = fingerprint(doc)
        for line in dossier.get("invoice_lines", []):
            key = ("invoice_registry", line.get("id"))
            if key in actual:
                return False
            actual[key] = fingerprint(line)
        manifest = fingerprint({key: dossier.get(key, {}) for key in ("artifact_registry", "invoice_registry")})
        registered = db.execute("SELECT 1 FROM dispute_manifests WHERE tenant=? AND account=? AND digest=?",
                                (tenant, dossier.get("account"), manifest)).fetchone()
        return (bool(declared) and registered is not None and declared == actual
                and all(pinned.get(key) == digest for key, digest in declared.items()))

    def _ticket(self, principal, dossier, state, now):
        try:
            return claimant.ticket_for(principal.tenant, dossier, state["supplement"], at=now)
        except (KeyError, TypeError, ValueError) as error:
            raise DisputeConflict("The approved source artifacts or minimized ticket are invalid.") from error

    def _now(self, state):
        if self.clock is None:
            return datetime.fromisoformat(state["cursor"])
        value = self.clock()
        if value.utcoffset() is None:
            raise ValueError("Clock must be timezone-aware.")
        return value.astimezone(UTC)

    def cases(self, principal):
        authorized(principal)
        with closing(self._connect()) as db:
            rows = db.execute("SELECT id,dossier,state FROM dispute_cases WHERE tenant=? ORDER BY id",
                              (principal.tenant,))
            return [self._view(principal, row[0], json.loads(row[1]), json.loads(row[2])) for row in rows]

    def case(self, principal, case_id):
        authorized(principal)
        with closing(self._connect()) as db:
            return self._view(principal, case_id, *self._get(db, principal, case_id))

    def _actions(self, principal, dossier, state):
        if principal.role != "reviewer" or state["stage"] not in ACTIONS:
            return []
        now = self._now(state)
        with closing(self._connect()) as db:
            if not self._integrity(db, principal.tenant, dossier):
                return []
        try:
            cutoff = deadline(dossier["month"])
        except (KeyError, ValueError, TypeError, OverflowError):
            return []
        if now >= cutoff:
            action = ("close-expired", "Close expired filing window")
        elif state["stage"] in {"DRAFTED", "CLAIM_APPROVED"}:
            evaluation = claimant.preflight(dossier, now)
            if evaluation.outcome != Outcome.ELIGIBLE or not claimant.settlement_expressible(str(evaluation.amount.amount)):
                return []
            with closing(self._connect()) as db:
                if not self._integrity(db, principal.tenant, dossier):
                    return []
            try:
                packet = self._ticket(principal, dossier, state, now)
            except DisputeConflict:
                return []
            action = ACTIONS[state["stage"]]
            if state["stage"] == "CLAIM_APPROVED" and state["approval"] and packet.digest != state["approval"]["digest"]:
                action = ("refresh-claim", "Refresh changed evidence for approval")
        elif state["stage"] == "RESPONSE_APPROVED" and now < datetime.fromisoformat(state["next_contact"]):
            if self.clock is not None:
                return []
            action = ("advance-cooldown", "Advance replay to permitted contact time")
        else:
            action = ACTIONS[state["stage"]]
        return [dict(id=action[0], label=action[1])]

    def act(self, principal, case_id, action):
        authorized(principal, write=True)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            dossier, state = self._get(db, principal, case_id)
            if action in state["completed"]:
                return self._view(principal, case_id, dossier, state)
            now = self._now(state)
            stage = state["stage"]
            if stage not in ACTIONS:
                raise DisputeConflict("Case is terminal. No further contact is permitted.")
            expected = ACTIONS[stage][0]
            if action not in (expected, "close-expired", "advance-cooldown", "refresh-claim"):
                raise DisputeConflict("Action requires the corresponding draft and approval.")
            try:
                cutoff = deadline(dossier["month"])
            except (KeyError, ValueError, TypeError, OverflowError) as error:
                raise DisputeConflict("The governing filing period is invalid.") from error
            if now >= cutoff:
                state["stage"] = "EXPIRED"
                event(state, principal, now, "The filing window closed; no further contact was sent.", [Source.PUBLIC, Source.REPLAY])
                done = True
            elif action == "advance-cooldown":
                if self.clock is not None or stage != "RESPONSE_APPROVED":
                    raise DisputeConflict("Only an explicit replay may advance to the follow-up time.")
                next_contact = datetime.fromisoformat(state["next_contact"])
                if now >= next_contact:
                    raise DisputeConflict("The cooldown has already elapsed.")
                now = next_contact
                event(state, principal, now, "Replay clock advanced to the first permitted follow-up time.", [Source.REPLAY])
                done = True
            elif not self._integrity(db, principal.tenant, dossier):
                raise DisputeConflict("Source artifacts differ from immutable provisioning or tenant binding.")
            elif action in ("approve-claim", "submit-claim", "approve-response", "submit-response") and (
                    claimant.preflight(dossier, now).outcome != Outcome.ELIGIBLE
                    or not claimant.settlement_expressible(str(claimant.preflight(dossier, now).amount.amount))):
                raise DisputeConflict("The current claim package does not pass its cited filing preflight or settlement precision review.")
            elif action == "refresh-claim":
                if stage != "CLAIM_APPROVED":
                    raise DisputeConflict("Only an approved initial claim can be refreshed.")
                state["approval"] = None
                state["completed"] = [value for value in state["completed"] if value != "approve-claim"]
                state["stage"] = "DRAFTED"
                event(state, principal, now, "Newly available evidence requires a fresh exact-payload approval.", SYNTHETIC)
                done = False
            elif action in ("approve-claim", "approve-response"):
                ticket = self._ticket(principal, dossier, state, now)
                if action == "approve-claim":
                    evaluation = claimant.preflight(dossier, now)
                    basis = dict(outcome=evaluation.outcome, trace=list(evaluation.trace),
                                 clauses=[asdict(c) for c in evaluation.clauses], usd=f"{evaluation.amount.amount:.2f}")
                else:
                    basis = dict(needed_kind=state["needed_kind"], new_document=fingerprint(state["supplement"][0]))
                state["approval"] = dict(by=principal.subject, at=now.isoformat(), digest=ticket.digest,
                                         action=action, basis=basis)
                state["stage"] = "CLAIM_APPROVED" if action == "approve-claim" else "RESPONSE_APPROVED"
                event(state, principal, now, "Reviewer approved this exact simulated ticket.", SYNTHETIC,
                      digest=ticket.digest, action=action)
                done = True
            elif action == "prepare-response":
                doc = claimant.find_supplement(dossier, state["needed_kind"], at=now)
                if doc is None:
                    state["stage"] = "HUMAN_REVIEW"
                    event(state, principal, now, "No new scoped attachment exists. Escalate without a follow-up.", SYNTHETIC)
                else:
                    state["supplement"] = [doc]
                    state["stage"] = "RESPONSE_DRAFTED"
                    event(state, principal, now, f"Prepared existing archive record {doc['ref']} for the requested component and interval.",
                          SYNTHETIC, digest=fingerprint(doc))
                done = True
            elif action in ("submit-claim", "submit-response"):
                done = self._send(db, principal, case_id, action, dossier, state, now)
                if state["replies"]:
                    now = max(now, instant(state["replies"][-1]["received_at"]))
            else:
                raise DisputeConflict("The filing window is open.")
            if done:
                state["completed"].append(action)
            if state["stage"] in {"HUMAN_REVIEW", "PARTIAL_AWARD_REVIEW"}:
                ledger = state["ledger"]
                with localcontext() as context:
                    context.prec = 80
                    ledger["disputed_remainder"] = f"{Decimal(ledger['claimed']) - Decimal(ledger['awarded']):.2f}"
            if self.clock is None:
                state["cursor"] = (now + timedelta(minutes=1)).isoformat()
            db.execute("UPDATE dispute_cases SET state=? WHERE tenant=? AND id=?",
                       (json.dumps(state), principal.tenant, case_id))
            return self._view(principal, case_id, dossier, state)

    def _send(self, db, principal, case_id, action, dossier, state, now):
        is_response = action == "submit-response"
        ticket = self._ticket(principal, dossier, state, now)
        if not state["approval"] or ticket.digest != state["approval"]["digest"]:
            raise DisputeConflict("Submitted content differs from the approved ticket.")
        if is_response:
            if len(state["submissions"]) != 1 or not state["supplement"]:
                raise DisputeConflict("Exactly one materially new supplement is permitted.")
            if now < datetime.fromisoformat(state["next_contact"]):
                raise DisputeConflict("The simulated follow-up cooldown has not elapsed.")
            if ticket.digest == state["submissions"][0]["digest"]:
                raise DisputeConflict("No new material evidence.")
        owner = db.execute("SELECT case_id FROM dispute_obligations WHERE tenant=? AND obligation=?",
                           (principal.tenant, ticket.obligation_key)).fetchone()
        if owner is not None and owner[0] != case_id:
            raise DisputeConflict("This monthly obligation is already reserved by another case.")
        db.execute("INSERT OR IGNORE INTO dispute_obligations VALUES(?,?,?)",
                   (principal.tenant, ticket.obligation_key, case_id))
        key = fingerprint([ticket.obligation_key, action])
        try:
            reply = vendor.review(ticket, now)
        except (ConnectionError, TimeoutError):
            # The offline reviewer is pure. Receipt, state and action commit together.
            failures = state["failed_sends"].get(key, 0) + 1
            state["failed_sends"][key] = failures
            if failures >= 2:
                state["stage"] = "HUMAN_REVIEW"
            event(state, principal, now, "Simulator unavailable. No receipt or credit recorded.", SIMULATED,
                  action=action, idempotency_key=key, failed_attempts=failures)
            return failures >= 2

        receipt = dict(id="SIM-" + key[:16], idempotency_key=key, action=action, digest=ticket.digest,
                       document_refs=[doc.fact.ref for doc in ticket.documents], approval=state["approval"],
                       subject=ticket.subject, destination=ticket.channel, at=now.isoformat(), sources=SIMULATED)
        receipt["obligation_key"] = ticket.obligation_key
        receipt["source_artifact_digests"] = {doc.fact.ref: dossier["artifact_registry"][doc.fact.ref]
                                               for doc in ticket.documents}
        receipt["payload"] = json.loads(json.dumps(asdict(ticket)))
        db.execute("INSERT INTO dispute_receipts VALUES(?,?,?,?,?,?)",
                   (receipt["id"], principal.tenant, case_id, ticket.obligation_key, action, json.dumps(receipt)))
        state["submissions"].append(receipt)
        event(state, principal, now, "Evidence supplement sent to simulator." if is_response else "Claim sent to simulator.",
              SIMULATED, receipt=receipt["id"], digest=ticket.digest)
        state["approval"] = None
        try:
            received_at = instant(reply.received_at) if reply.received_at else now
            if received_at < now:
                raise ValueError("Reply predates submission.")
            valid_receipt_time = True
        except (ValueError, TypeError):
            received_at, valid_receipt_time = now, False
        state["replies"].append({**asdict(reply), "received_at": received_at.isoformat(),
                                 "sources": SIMULATED, "receipt": receipt["id"]})
        event(state, Principal(principal.tenant, "vendor-simulator", "simulator"), received_at,
              reply.reason, SIMULATED, code=reply.code, clause=reply.clause)
        state["stage"], explanation = claimant.disposition(reply, dossier, is_response,
            filed_at=instant(state["submissions"][0]["at"]), received_at=received_at)
        state["needed_kind"] = reply.needed_kind
        state["ledger"]["claimed"] = ticket.requested
        recognized = claimant.recognized_award(reply, ticket.requested)
        if recognized is None or not valid_receipt_time:
            state["stage"] = "HUMAN_REVIEW"
            explanation = "Vendor amount conflicts with the claim or reply type. Hold the unverified amount for review."
        else:
            state["ledger"]["awarded"] = recognized
        if state["stage"] == "NEEDS_EVIDENCE":
            state["next_contact"] = (now + COOLDOWN).isoformat()
        event(state, Principal(principal.tenant, "dispute-reviewer", "system"), received_at, explanation, MIXED)
        return True

    def _view(self, principal, case_id, dossier, state):
        with localcontext() as context:
            context.prec = 80
            return self._view_precise(principal, case_id, dossier, state)

    def _view_precise(self, principal, case_id, dossier, state):
        stage = state["stage"]
        now = self._now(state)
        # Preserve the original filing assessment when viewing an exchanged ticket later.
        filed_at = (datetime.fromisoformat(state["submissions"][0]["at"]) if state["submissions"] else now)
        evaluation = claimant.preflight(dossier, filed_at)
        with closing(self._connect()) as db:
            intact = self._integrity(db, principal.tenant, dossier)
        if not intact:
            detail = "Current evidence differs from the immutable source manifest or tenant binding."
            evaluation = EvaluationResult(Outcome.MISSING, evaluation.clauses, (detail,), (detail,))
        if stage in {"AWARDED", "PARTIAL_AWARD_REVIEW"}:
            outcome = Outcome.ELIGIBLE
        elif stage in {"DENIAL_ACCEPTED", "EXPIRED"}:
            outcome = Outcome.INELIGIBLE
        elif stage in {"DRAFTED", "CLAIM_APPROVED"}:
            outcome = evaluation.outcome
        else:
            outcome = Outcome.MISSING
        ledger = dict(state["ledger"])
        if evaluation.outcome == Outcome.ELIGIBLE:
            ledger["estimated"] = str(evaluation.amount.amount)
            if stage in {"DRAFTED", "CLAIM_APPROVED"} and not claimant.settlement_expressible(ledger["estimated"]):
                stage = "HUMAN_REVIEW"
        trace = [f"Twilio Services APIs / {dossier.get('plan')} plan / region {dossier.get('region')}.",
                 *evaluation.trace]
        if evaluation.outcome == Outcome.ELIGIBLE:
            start = datetime.fromisoformat(dossier["start"])
            end = datetime.fromisoformat(dossier["end"])
            minutes = (end - start) // timedelta(minutes=1)
            total = monthrange(start.year, start.month)[1] * 24 * 60
            availability = (Decimal(total - minutes) * 100 / total).quantize(Decimal("0.00001"))
            basis = sum((Decimal(line["usd"]) for line in dossier["invoice_lines"] if line["kind"] == "affected_api"), Decimal(0))
            trace.extend([f"Replayed interval {dossier['start']} through {dossier['end']}. "
                          f"If all {minutes} minutes count, monthly availability is {availability}% over {total:,} minutes "
                          "against the 99.95% standard threshold. Section 4 exclusions apply.",
                          f"USD {basis:.2f} in affected API fees × 10% = USD {evaluation.amount.amount} exact contractual entitlement. "
                          "Carrier and tax lines are excluded. An award is a future service credit."])
        trace.extend(item["event"] for item in state["timeline"] if item["role"] in ("system", "simulator"))
        evidence = [
            dict(label="Customer invoice lines", detail=f"{line.get('id')} · {line.get('kind')} · USD {line.get('usd')}", sources=SYNTHETIC)
            for line in dossier.get("invoice_lines", [])]
        for doc in dossier.get("initial_documents", []) + state["supplement"]:
            evidence.append(dict(label=doc["kind"], detail=f"{doc.get('ref')} · {doc.get('product')} · {doc.get('start')} to {doc.get('end')}",
                                 digest=fingerprint(doc), sources=[Source.REPLAY]))
        if stage == "DENIAL_ACCEPTED":
            for doc in dossier["customer_notice_archive"]:
                evidence.append(dict(label="Customer copy of maintenance notice",
                                     detail=f"{doc['ref']} · issued {doc['issued_at']} · {doc['product']}",
                                     digest=fingerprint(doc), sources=SYNTHETIC))
        amount = None
        if outcome == Outcome.ELIGIBLE:
            amount = ledger["awarded"] if stage in {"AWARDED", "PARTIAL_AWARD_REVIEW"} else str(evaluation.amount.amount)
        dispatchable = False
        try:
            packet = self._ticket(principal, dossier, state, now)
            with closing(self._connect()) as db:
                intact = self._integrity(db, principal.tenant, dossier)
            dispatchable = (stage == "CLAIM_APPROVED" and evaluation.outcome == Outcome.ELIGIBLE and intact
                            and dossier.get("allow_approved_initial_dispatch") is True
                            and state["approval"] is not None
                            and {"status_summary", "component_record"} <= {doc.fact.kind for doc in packet.documents}
                            and claimant.settlement_expressible(packet.requested)
                            and state["approval"]["digest"] == packet.digest)
        except DisputeConflict:
            pass
        try:
            cutoff = deadline(dossier["month"]).isoformat()
        except (KeyError, ValueError, TypeError, OverflowError):
            cutoff = None
        return dict(id=case_id, vendor="Twilio", title=dossier["title"], outcome=outcome, stage=stage,
                    amount=amount, currency="USD", sources=MIXED, trace=trace, policy_dispatchable=dispatchable,
                    preflight=dict(outcome=evaluation.outcome, trace=list(evaluation.trace), missing=list(evaluation.missing),
                                   clauses=[asdict(c) for c in evaluation.clauses]),
                    clauses=[dict(label=f"Twilio APIs SLA {VERSION} {section}", uri=TERMS) for section in ("§1 Fee basis", "§3 Filing and credits", "§4 Exclusions")],
                    evidence=evidence, timeline=state["timeline"], actions=self._actions(principal, dossier, state),
                    financials=[dict(label=name.replace("_", " ").title(), value=f"USD {amount}",
                                     sources=SIMULATED if name in ("awarded", "posted", "applied") else SYNTHETIC)
                                for name, amount in ledger.items()], ledger=ledger,
                    replies=state["replies"], submissions=state["submissions"], next_contact=state["next_contact"],
                    filing_cutoff=cutoff, policy="ASSISTED", mode="LOCAL_SIMULATOR")
