"""Durable local claim inbox. No outgoing transport. Signed-source deliveries are independent of filing."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path

from .contracts import Outcome, Source, fingerprint
from .correspondence_reason import propose
from .correspondence_rules import assess, confirmed_maintenance
from .correspondence_types import Claim, Delivery, SOURCE, Scope, instant
from .storage import database

SOURCES = [Source.CUSTOMER.value, Source.REPLAY.value]
VENDOR = [Source.VENDOR.value, Source.REPLAY.value]
TERMINAL = {"AWARDED", "PARTIAL_AWARD_REVIEW", "DENIAL_ACCEPTED", "HUMAN_REVIEW"}
FOLLOW_UP = timedelta(hours=24)
ACTIONS = {"DRAFTED": "approve-claim", "CLAIM_APPROVED": "submit-claim",
           "RESPONSE_DRAFTED": "approve-response", "RESPONSE_APPROVED": "submit-response"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS inbox_account (
 tenant TEXT NOT NULL, account TEXT NOT NULL, vendor TEXT NOT NULL, contract TEXT NOT NULL,
 service TEXT NOT NULL, component TEXT NOT NULL, region TEXT NOT NULL,
 PRIMARY KEY(tenant, account, vendor, contract, service, component, region));
CREATE TABLE IF NOT EXISTS inbox_sender (
 tenant TEXT NOT NULL, subject TEXT NOT NULL, account TEXT NOT NULL, source TEXT NOT NULL,
 PRIMARY KEY(tenant,subject,account,source), UNIQUE(tenant,subject,account));
CREATE TABLE IF NOT EXISTS inbox_claim (
 tenant TEXT NOT NULL, id TEXT NOT NULL, obligation TEXT NOT NULL, scope TEXT NOT NULL,
 state TEXT NOT NULL, PRIMARY KEY(tenant,id), UNIQUE(tenant,obligation));
CREATE TABLE IF NOT EXISTS inbox_delivery (
 tenant TEXT NOT NULL, account TEXT NOT NULL, source TEXT NOT NULL, event_id TEXT NOT NULL,
 claim TEXT NOT NULL, digest TEXT NOT NULL, received TEXT NOT NULL,
 PRIMARY KEY(tenant,account,source,event_id));
"""


def money(amount):
    raw = format(Decimal(amount), "f")
    whole, _, fraction = raw.partition(".")
    return whole + "." + fraction.rstrip("0").ljust(2, "0")


def authorize(p, write=False):
    roles = {"reviewer"} if write else {"viewer", "reviewer"}
    if not p.subject or not p.tenant or p.role not in roles:
        raise PermissionError("An authorized local workspace session is required.")


def audit(state, at, actor, detail, sources=SOURCES, **extra):
    state["timeline"].append({"at": at.isoformat(), "actor": actor, "event": detail, "sources": sources, **extra})


def observe_only(db, tenant):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='policy_revision'").fetchone():
        return False
    setting = db.execute("SELECT mode FROM policy_revision WHERE tenant=? ORDER BY id DESC LIMIT 1", (tenant,)).fetchone()
    return setting is not None and setting[0] == "OBSERVE"


class CorrespondenceDesk:
    def __init__(self, path, clock=None, active_resolver=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.active_resolver = active_resolver
        with database(path) as db:
            db.executescript(SCHEMA)

    def _now(self):
        value = self.clock()
        if value.utcoffset() is None:
            raise ValueError("Clock must supply aware timestamps.")
        return value.astimezone(UTC)

    @contextmanager
    def _write(self, tenant=None):
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if tenant and observe_only(db, tenant):
                raise PermissionError("The workspace is observe-only.")
            yield db

    def provision(self, tenant, account, vendor, contract, service, component, region):
        """Operator-only. Grant a verified agreement/account/component/subscription binding."""
        binding = Scope(account=account, vendor=vendor, contract=contract, service=service, component=component,
                        region=region, month="2026-10", invoice="validation", incident="validation", currency="USD")
        with self._write() as db:
            db.execute("INSERT OR IGNORE INTO inbox_account VALUES(?,?,?,?,?,?,?)",
                       (tenant, binding.account, binding.vendor, binding.contract, binding.service, binding.component, binding.region))

    def bind_sender(self, tenant, account, source, subject):
        """Operator-only allowlist of named HMAC service identities and source roles."""
        if source not in SOURCE.values() or not subject or not tenant:
            raise ValueError("Unsupported source binding.")
        with self._write() as db:
            if not db.execute("SELECT 1 FROM inbox_account WHERE tenant=? AND account=?", (tenant, account)).fetchone():
                raise PermissionError("No such provisioned account.")
            existing = db.execute("SELECT source FROM inbox_sender WHERE tenant=? AND account=? AND subject=?",
                                  (tenant, account, subject)).fetchone()
            if existing and existing["source"] != source:
                raise ValueError("Source roles require independent signers for this account.")
            db.execute("INSERT OR IGNORE INTO inbox_sender VALUES(?,?,?,?)", (tenant, subject, account, source))

    def create(self, p, claim: Claim):
        authorize(p, True)
        scope = claim.scope
        with self._write(p.tenant) as db:
            if not db.execute("SELECT 1 FROM inbox_account WHERE tenant=? AND account=? AND vendor=? AND contract=? AND service=? AND component=? AND region=?",
                              (p.tenant, scope.account, scope.vendor, scope.contract, scope.service, scope.component, scope.region)).fetchone():
                raise PermissionError("No verified account and agreement binding matches this scope.")
            # The covered API monthly credit is a single economic obligation.
            # Invoice, incident, claim and component aliases cannot create a second filing.
            obligation = fingerprint([p.tenant, scope.vendor, scope.account, scope.contract, scope.service, scope.month, "availability"])
            duplicate = db.execute("SELECT id,scope FROM inbox_claim WHERE tenant=? AND (obligation=? OR id=?)",
                                   (p.tenant, obligation, claim.claim_id)).fetchone()
            if duplicate:
                if duplicate["id"] != claim.claim_id or json.loads(duplicate["scope"]) != scope.model_dump():
                    raise ValueError("Claim ID or monthly business obligation already exists.")
                return self._view(db, p, claim.claim_id)
            state = dict(stage="DRAFTED", evidence=[], replies=[], timeline=[], submissions=[], approval=None,
                         awarded="0.00", reason=None, cooldown=None)
            audit(state, self._now(), p.subject, "Opened an assisted local claim intake.")
            db.execute("INSERT INTO inbox_claim VALUES(?,?,?,?,?)",
                       (p.tenant, claim.claim_id, obligation, scope.model_dump_json(), json.dumps(state)))
            return self._view(db, p, claim.claim_id)

    def _read(self, db, tenant, claim_id):
        row = db.execute("SELECT scope,state FROM inbox_claim WHERE tenant=? AND id=?", (tenant, claim_id)).fetchone()
        if not row:
            raise KeyError("Claim not found.")
        return Scope.model_validate_json(row["scope"]), json.loads(row["state"])

    @staticmethod
    def _save(db, tenant, claim_id, state):
        db.execute("UPDATE inbox_claim SET state=? WHERE tenant=? AND id=?", (json.dumps(state), tenant, claim_id))

    def _assess(self, tenant, scope, state, now):
        filed = instant(state["submissions"][0]["at"]) if state["submissions"] else None
        return assess(tenant, scope, state["evidence"], now, filed, self.active_resolver)

    def receive(self, p, claim_id, event: Delivery):
        """Only a server-authenticated service identity can deliver. Return only its receipt."""
        if p.role != "service" or not p.subject or not p.tenant:
            raise PermissionError("An authenticated source service is required.")
        with self._write(p.tenant) as db:
            sender = db.execute("SELECT source FROM inbox_sender WHERE tenant=? AND subject=? AND account=?",
                                (p.tenant, p.subject, event.scope.account)).fetchone()
            if not sender:
                raise PermissionError("Service has no source grant on this account.")
            return self._receive(db, p.tenant, event.scope.account, sender["source"], claim_id, event, p.subject)

    def _receive(self, db, tenant, account, source, claim_id, event, subject):
        if source != SOURCE[event.body.kind] or account != event.scope.account or observe_only(db, tenant):
            raise PermissionError("Source cannot deliver this evidence.")
        scope, state = self._read(db, tenant, claim_id)
        if scope != event.scope:
            raise ValueError("Delivery does not match the full claim scope.")
        body = event.body.model_dump(exclude_unset=True)
        digest = fingerprint([tenant, claim_id, scope.model_dump(), source, body])
        previous = db.execute("SELECT digest,received FROM inbox_delivery WHERE tenant=? AND account=? AND source=? AND event_id=?",
                              (tenant, account, source, event.event_id)).fetchone()
        if previous:
            if previous["digest"] != digest:
                raise ValueError("Delivery identity was reused with different content.")
            return dict(event_id=event.event_id, digest=digest, received_at=previous["received"])
        now = self._now()
        if any(e["digest"] == digest for e in state["evidence"]):
            audit(state, now, source, "Recorded an identical-content delivery alias.", digest=digest)
        else:
            if len(state["evidence"]) >= 200:
                raise ValueError("Case evidence budget exhausted; manual review required.")
            if "start" in body and (instant(body["end"]) <= instant(body["start"]) or instant(body["end"]) > now):
                raise ValueError("Only completed intervals may be delivered.")
            if body["kind"] == "notice" and instant(body["issued_at"]) > now:
                raise ValueError("Notice has not been issued.")
            if body["kind"] == "message":
                if not state["submissions"] or body["receipt_id"] != state["submissions"][-1]["id"]:
                    raise ValueError("Correspondence does not refer to the current local submission.")
                if state["stage"] != "AWAITING_VENDOR":
                    raise ValueError("A substantive response already exists for this receipt.")
            fact = dict(event_id=event.event_id, source=source, subject=subject, kind=body["kind"], digest=digest,
                        received_at=now.isoformat(), body=body)
            state["evidence"].append(fact)
            audit(state, now, subject, "Received authenticated " + body["kind"] + " record.", VENDOR if source == "vendor" else SOURCES,
                  event_id=event.event_id, digest=digest)
            if body["kind"] == "message":
                self._reply(tenant, scope, state, fact, now)
            else:
                self._evidence_arrival(tenant, scope, state, now)
        self._save(db, tenant, claim_id, state)
        db.execute("INSERT INTO inbox_delivery VALUES(?,?,?,?,?,?,?)",
                   (tenant, account, source, event.event_id, claim_id, digest, now.isoformat()))
        return dict(event_id=event.event_id, digest=digest, received_at=now.isoformat())

    def _evidence_arrival(self, tenant, scope, state, now):
        if state["stage"] in TERMINAL:
            return
        if state["approval"]:
            state["stage"] = "DRAFTED" if not state["submissions"] else "RESPONSE_DRAFTED"
            state["approval"] = None
            audit(state, now, "claimant", "New independent evidence invalidated the prior packet approval.")
        if not state["submissions"]:
            return
        evaluation = self._assess(tenant, scope, state, now).evaluation
        if state["reason"] == "maintenance" and confirmed_maintenance(scope, state["evidence"]) and evaluation.outcome == Outcome.INELIGIBLE:
            state["stage"] = "DENIAL_ACCEPTED"
            audit(state, now, "claimant", "Customer notice independently confirms timely scheduled maintenance. Closed without further contact.")
        elif state["reason"] == "component" and state["stage"] in {"NEEDS_EVIDENCE", "RESPONSE_DRAFTED"}:
            initial = set(state["submissions"][0]["evidence_digests"])
            if evaluation.outcome != Outcome.ELIGIBLE:
                state["stage"] = "HUMAN_REVIEW"
            elif any(e["kind"] == "component" and e["digest"] not in initial for e in state["evidence"]):
                state["stage"] = "RESPONSE_DRAFTED"
                audit(state, now, "claimant", "Drafted one supplemental packet using newly acquired matching component evidence.")

    def _reply(self, tenant, scope, state, fact, now):
        proposal = propose(fact["body"]["text"])
        state["reason"] = proposal.reason
        reply = dict(reason=proposal.reason, span=proposal.span, event_id=fact["event_id"], digest=fact["digest"],
                     receipt=fact["body"]["receipt_id"], received_at=now.isoformat(), sources=VENDOR)
        state["replies"].append(reply)
        state["stage"] = "HUMAN_REVIEW"
        current = self._assess(tenant, scope, state, now)
        requested = Decimal(state["submissions"][0]["requested"])
        filed_at = instant(state["submissions"][0]["at"])
        if proposal.reason == "maintenance":
            if confirmed_maintenance(scope, state["evidence"]) and current.evaluation.outcome == Outcome.INELIGIBLE:
                state["stage"] = "DENIAL_ACCEPTED"
            elif not any(e["kind"] == "notice" for e in state["evidence"]):
                state["stage"] = "AWAITING_NOTICE"
        elif current.evaluation.outcome == Outcome.ELIGIBLE and current.evaluation.amount.amount == requested:
            if proposal.reason == "award":
                awarded = Decimal(proposal.amount)
                if 0 < awarded <= requested:
                    state["awarded"] = money(awarded)
                    state["stage"] = "AWARDED" if awarded == requested else "PARTIAL_AWARD_REVIEW"
            elif len(state["submissions"]) == 1:
                if proposal.reason == "component":
                    state["stage"] = "NEEDS_EVIDENCE"
                    self._evidence_arrival(tenant, scope, state, now)
                elif proposal.reason == "time_bar" and filed_at < current.cutoff:
                    state["stage"] = "RESPONSE_DRAFTED"
                    audit(state, now, "claimant", "The original local receipt predates the filing cutoff; drafted a receipt-backed correction.")
        if state["stage"] in {"NEEDS_EVIDENCE", "RESPONSE_DRAFTED"}:
            state["cooldown"] = (now + FOLLOW_UP).isoformat()
        audit(state, now, "claimant", "Evaluated vendor correspondence: " + state["stage"] + ".", VENDOR,
              proposal=proposal.reason, receipt=fact["body"]["receipt_id"])

    def _packet(self, tenant, claim_id, scope, state, current):
        """Construct local simulator wire data from allowlisted fields only. No incoming body/text is copied."""
        if current.evaluation.outcome != Outcome.ELIGIBLE:
            raise ValueError("Claim does not pass its current cited eligibility evaluation.")
        facts = [e for e in state["evidence"] if e["kind"] != "message"]
        request = money(current.evaluation.amount.amount)
        packet = dict(tenant=tenant, claim=claim_id, scope=scope.model_dump(), destination="isolated-local-simulator",
                      subject="SLA Claim", version=current.version, requested=request, evidence_digest=current.evidence_digest,
                      artifacts=[dict(kind=e["kind"], digest=e["digest"]) for e in facts])
        if state["submissions"]:
            original = state["submissions"][0]
            if current.evaluation.amount.amount != Decimal(original["requested"]):
                raise ValueError("The original fee basis no longer matches. Manual review required.")
            packet["in_reply_to"] = original["id"]
            packet["vendor_event"] = state["replies"][-1]["digest"]
            if state["reason"] == "component" and any(e["kind"] == "component" and e["digest"] not in original["evidence_digests"] for e in facts):
                packet["argument"] = "New authenticated customer component evidence identifies the affected service."
            elif state["reason"] == "time_bar" and instant(original["at"]) < current.cutoff:
                packet["argument"] = "The dated original receipt predates the verified filing cutoff."
            else:
                raise ValueError("One material evidence-backed correction is required.")
        return packet

    def _actions(self, p, scope, state, current, now):
        if (p.role != "reviewer" or not (action := ACTIONS.get(state["stage"]))
                or current.evaluation.outcome != Outcome.ELIGIBLE or current.cutoff is None or now >= current.cutoff):
            return []
        if action == "submit-response" and now < instant(state["cooldown"]):
            return []
        return [dict(id=action, label=action.replace("-", " ").title())]

    def act(self, p, claim_id, action):
        authorize(p, True)
        with self._write(p.tenant) as db:
            scope, state = self._read(db, p.tenant, claim_id)
            now = self._now()
            if any(r["action"] == action for r in state["submissions"]):
                return self._view(db, p, claim_id)
            if state["approval"] and state["approval"]["action"] == action:
                return self._view(db, p, claim_id)
            current = self._assess(p.tenant, scope, state, now)
            if action not in {a["id"] for a in self._actions(p, scope, state, current, now)}:
                raise ValueError("Action unavailable for the current policy, filing window, evidence and stage.")
            packet = self._packet(p.tenant, claim_id, scope, state, current)
            digest = fingerprint(packet)
            if action.startswith("approve-"):
                state["approval"] = dict(action=action, actor=p.subject, at=now.isoformat(), digest=digest)
                state["stage"] = "CLAIM_APPROVED" if action == "approve-claim" else "RESPONSE_APPROVED"
                audit(state, now, p.subject, "Approved exact local packet.", digest=digest)
            else:
                if not state["approval"] or state["approval"]["digest"] != digest:
                    raise ValueError("The current packet differs from the approved content.")
                receipt = dict(id="LOCAL-" + digest[:24], action=action, at=now.isoformat(), digest=digest, packet=packet,
                               requested=packet["requested"], approval=state["approval"],
                               evidence_digests=[a["digest"] for a in packet["artifacts"]], sources=VENDOR)
                state["submissions"].append(receipt)
                state["approval"] = None
                state["stage"] = "AWAITING_VENDOR"
                audit(state, now, p.subject, "Filed approved packet in the isolated local outbox.", VENDOR, receipt=receipt["id"])
            self._save(db, p.tenant, claim_id, state)
            return self._view(db, p, claim_id)

    def case(self, p, claim_id):
        authorize(p)
        with database(self.path) as db:
            return self._view(db, p, claim_id)

    def cases(self, p):
        authorize(p)
        with database(self.path) as db:
            return [self._view(db, p, row["id"]) for row in db.execute(
                "SELECT id FROM inbox_claim WHERE tenant=? ORDER BY id", (p.tenant,))]

    def _view(self, db, p, claim_id):
        scope, state = self._read(db, p.tenant, claim_id)
        now = self._now()
        current = self._assess(p.tenant, scope, state, now)
        evaluation = current.evaluation
        predicted = money(evaluation.amount.amount) if evaluation.amount else "0.00"
        submitted = state["submissions"]
        claimed = submitted[0]["requested"] if submitted else "0.00"
        awarded = state["awarded"]
        stage = state["stage"]
        unresolved = stage in {"HUMAN_REVIEW", "PARTIAL_AWARD_REVIEW", "NEEDS_EVIDENCE", "AWAITING_NOTICE", "RESPONSE_DRAFTED", "RESPONSE_APPROVED"}
        ledger = dict(estimated=predicted, claimed=claimed, awarded=awarded, posted="0.00", applied="0.00",
                      disputed_remainder=money(Decimal(claimed) - Decimal(awarded)) if unresolved else "0.00")
        amount = awarded if stage in {"AWARDED", "PARTIAL_AWARD_REVIEW"} else predicted if not submitted and evaluation.amount else None
        outcome = Outcome.INELIGIBLE if stage == "DENIAL_ACCEPTED" else evaluation.outcome if amount is not None or not submitted else Outcome.MISSING
        evidence = [dict(label=e["kind"], detail=e["event_id"] + " · " + e["source"], digest=e["digest"],
                         received_at=e["received_at"], sources=VENDOR if e["source"] == "vendor" else SOURCES)
                    for e in state["evidence"]]
        replies = [{**r, "text": next(e["body"]["text"] for e in state["evidence"] if e["digest"] == r["digest"])} for r in state["replies"]]
        return dict(id=claim_id, title="Claim correspondence · " + scope.invoice, vendor=scope.vendor,
                    mode="LOCAL_SIMULATOR", policy="ASSISTED", tenant=p.tenant, scope=scope.model_dump(), stage=stage,
                    outcome=outcome, amount=amount, currency=scope.currency, sources=SOURCES + [Source.VENDOR.value],
                    trace=list(evaluation.trace), preflight=dict(outcome=evaluation.outcome, trace=list(evaluation.trace),
                    missing=list(evaluation.missing), clauses=[asdict(c) for c in evaluation.clauses]),
                    clauses=[dict(label=c.document + " " + c.version + " " + c.section, uri=c.uri) for c in evaluation.clauses],
                    evidence=evidence, timeline=state["timeline"], submissions=submitted, replies=replies, approval=state["approval"],
                    actions=[] if observe_only(db, p.tenant) else self._actions(p, scope, state, current, now),
                    filing_cutoff=current.cutoff.isoformat() if current.cutoff else None, next_contact=state["cooldown"],
                    policy_dispatchable=False, ledger=ledger,
                    financials=[dict(label=k.replace("_", " ").title(), value=scope.currency + " " + v, sources=SOURCES) for k,v in ledger.items()])
