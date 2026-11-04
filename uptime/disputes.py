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
from decimal import Decimal
from calendar import monthrange
from pathlib import Path

from uptime.contracts import Outcome, Principal, Source, fingerprint
from uptime import disputes_claimant as claimant
from uptime import disputes_vendor as vendor
from uptime.disputes_wire import FIXTURES, TERMS, VERSION, deadline

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
        if now >= deadline(dossier["month"]):
            action = ("close-expired", "Close expired filing window")
        elif state["stage"] in {"DRAFTED", "CLAIM_APPROVED"} and claimant.preflight(dossier, now).outcome != Outcome.ELIGIBLE:
            return []
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
            if action not in (expected, "close-expired", "advance-cooldown"):
                raise DisputeConflict("Action requires the corresponding draft and approval.")
            if now >= deadline(dossier["month"]):
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
            elif action in ("approve-claim", "submit-claim") and claimant.preflight(dossier, now).outcome != Outcome.ELIGIBLE:
                raise DisputeConflict("The current claim package does not pass its cited filing preflight.")
            elif action in ("approve-claim", "approve-response"):
                ticket = claimant.ticket_for(principal.tenant, dossier, state["supplement"])
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
                doc = claimant.find_supplement(dossier, state["needed_kind"])
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
                done = self._send(principal, case_id, action, dossier, state, now)
            else:
                raise DisputeConflict("The filing window is open.")
            if done:
                state["completed"].append(action)
            if state["stage"] in {"HUMAN_REVIEW", "PARTIAL_AWARD_REVIEW"}:
                ledger = state["ledger"]
                ledger["disputed_remainder"] = f"{Decimal(ledger['claimed']) - Decimal(ledger['awarded']):.2f}"
            if self.clock is None:
                state["cursor"] = (now + timedelta(minutes=1)).isoformat()
            db.execute("UPDATE dispute_cases SET state=? WHERE tenant=? AND id=?",
                       (json.dumps(state), principal.tenant, case_id))
            return self._view(principal, case_id, dossier, state)

    def _send(self, principal, case_id, action, dossier, state, now):
        is_response = action == "submit-response"
        ticket = claimant.ticket_for(principal.tenant, dossier, state["supplement"])
        if not state["approval"] or ticket.digest != state["approval"]["digest"]:
            raise DisputeConflict("Submitted content differs from the approved ticket.")
        if is_response:
            if len(state["submissions"]) != 1 or not state["supplement"]:
                raise DisputeConflict("Exactly one materially new supplement is permitted.")
            if now < datetime.fromisoformat(state["next_contact"]):
                raise DisputeConflict("The simulated follow-up cooldown has not elapsed.")
            if ticket.digest == state["submissions"][0]["digest"]:
                raise DisputeConflict("No new material evidence.")
        key = fingerprint([principal.tenant, case_id, action, ticket.digest])
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
        state["submissions"].append(receipt)
        event(state, principal, now, "Evidence supplement sent to simulator." if is_response else "Claim sent to simulator.",
              SIMULATED, receipt=receipt["id"], digest=ticket.digest)
        state["approval"] = None
        state["replies"].append({**asdict(reply), "sources": SIMULATED, "receipt": receipt["id"]})
        event(state, Principal(principal.tenant, "vendor-simulator", "simulator"), now,
              reply.reason, SIMULATED, code=reply.code, clause=reply.clause)
        state["stage"], explanation = claimant.disposition(reply, dossier, is_response)
        state["needed_kind"] = reply.needed_kind
        state["ledger"]["claimed"] = ticket.requested
        recognized = claimant.recognized_award(reply, ticket.requested)
        if recognized is None:
            state["stage"] = "HUMAN_REVIEW"
            explanation = "Vendor amount conflicts with the claim or reply type. Hold the unverified amount for review."
        else:
            state["ledger"]["awarded"] = recognized
        if state["stage"] == "NEEDS_EVIDENCE":
            state["next_contact"] = (now + COOLDOWN).isoformat()
        event(state, Principal(principal.tenant, "dispute-reviewer", "system"), now, explanation, MIXED)
        return True

    def _view(self, principal, case_id, dossier, state):
        stage = state["stage"]
        now = self._now(state)
        # Preserve the original filing assessment when viewing an exchanged ticket later.
        filed_at = (datetime.fromisoformat(state["submissions"][0]["at"]) if state["submissions"] else now)
        evaluation = claimant.preflight(dossier, filed_at)
        if stage in {"AWARDED", "PARTIAL_AWARD_REVIEW"}:
            outcome = Outcome.ELIGIBLE
        elif stage in {"DENIAL_ACCEPTED", "EXPIRED"}:
            outcome = Outcome.INELIGIBLE
        elif stage in {"DRAFTED", "CLAIM_APPROVED"}:
            outcome = evaluation.outcome
        else:
            outcome = Outcome.MISSING
        ledger = state["ledger"]
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
                          f"USD {basis:.2f} in affected API fees × 10% = USD {evaluation.amount.amount:.2f} in the draft. "
                          "Carrier and tax lines are excluded. An award is a future service credit."])
        trace.extend(item["event"] for item in state["timeline"] if item["role"] in ("system", "simulator"))
        evidence = [
            dict(label="Customer invoice lines", detail=f"{line.get('id')} · {line.get('kind')} · USD {line.get('usd')}", sources=SYNTHETIC)
            for line in dossier.get("invoice_lines", [])]
        for doc in dossier["initial_documents"] + state["supplement"]:
            evidence.append(dict(label=doc["kind"], detail=f"{doc['ref']} · {doc['product']} · {doc['start']} to {doc['end']}",
                                 digest=fingerprint(doc), sources=[Source.REPLAY]))
        if stage == "DENIAL_ACCEPTED":
            for doc in dossier["customer_notice_archive"]:
                evidence.append(dict(label="Customer copy of maintenance notice",
                                     detail=f"{doc['ref']} · issued {doc['issued_at']} · {doc['product']}",
                                     digest=fingerprint(doc), sources=SYNTHETIC))
        amount = None
        if outcome == Outcome.ELIGIBLE:
            amount = ledger["awarded"] if stage in {"AWARDED", "PARTIAL_AWARD_REVIEW"} else f"{evaluation.amount.amount:.2f}"
        dispatchable = (stage == "CLAIM_APPROVED" and evaluation.outcome == Outcome.ELIGIBLE
                        and dossier.get("allow_approved_initial_dispatch") is True
                        and state["approval"] is not None
                        and all(doc.get("classification") == "redacted_replay"
                                for doc in dossier["initial_documents"])
                        and state["approval"]["digest"] == claimant.ticket_for(principal.tenant, dossier, []).digest)
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
                    filing_cutoff=deadline(dossier["month"]).isoformat(), policy="ASSISTED", mode="LOCAL_SIMULATOR")
