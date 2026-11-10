"""Exact-object Ramp plans, signed review and a durable, conservative outbox.

Only injected transports exist. No credentials, subscriptions or workflow nodes
are provisioned here. Real financial decisions are deliberately unsupported.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import timedelta
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx

from .auth_keys import verify_reviewer
from .ramp import ORIGIN, RampError, uuid_text
from .ramp_webhooks import canonical, digest, opaque, strict_json, timestamp, utcnow
from .storage import database

PREFIX = "/developer/v1"
OBJECTS = {"bills": ("bills", "bills"), "draft-bills": ("bills/drafts", "bills"),
           "transactions": ("transactions", "transactions"), "unified-requests": ("unified-requests", "unified_requests")}
COMMENT_TYPES = frozenset({"bills", "draft-bills", "transactions"})
METADATA_STATUSES = frozenset({"Review pending", "Evidence available", "Needs evidence", "Human review required"})
PROVENANCE = frozenset({"MOCK_HTTP", "LIVE_RAMP_SANDBOX", "SIMULATED_RAMP"})
CONTEXT_SCOPES = frozenset({"unified_requests:read", "custom_forms:read", "spend_programs:read", "blank_canvas:write"})
SOURCE_LABELS = frozenset({"LIVE_RAMP_SANDBOX", "LIVE_VENDOR_PUBLIC", "OPERATOR_ATTESTED_CUSTOMER", "SYNTHETIC_CUSTOMER", "SIMULATED_VENDOR",
                           "DETERMINISTIC_REPLAY", "UNAVAILABLE", "SIMULATED_RAMP"})
NATIVE_REVIEW_MESSAGES = {
    "EVIDENCE_REQUIRED": (
        "Uptime contract review: price compliance is undetermined. Before approving this bill, "
        "obtain the governing signed terms and amendments, and verify itemized charges, service dates, "
        "quantities and tax treatment against those terms."),
    "ATTESTED_PRICE_EXCEPTION": (
        "Uptime contract review: a deterministic comparison against operator-attested signed terms "
        "identified a potential price exception. Before approving this bill, review the governing "
        "terms and amendments and the mapped service dates, quantities and tax treatment with the contract owner. "
        "This provisional finding depends on operator evidence; it does not establish legal entitlement."),
}


class WorkflowError(RampError):
    pass


class ProviderFailure(WorkflowError):
    """No provider bodies/headers in exceptions, even for ambiguous mutations."""


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise WorkflowError("SHA-256 digest required")
    return value


def inspector_url(value, origins):
    try:
        parts = urlsplit(value)
        origin = f"https://{parts.netloc}"
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password or
                parts.port not in (None, 443) or parts.query or parts.fragment or origin not in origins or
                not re.fullmatch(r"/[A-Za-z0-9/_-]*", parts.path)):
            raise ValueError
    except (ValueError, TypeError):
        raise WorkflowError("Allowlisted HTTPS inspector URL without credentials or query required") from None
    return value


def remote_state(record, object_id):
    if not isinstance(record, dict) or record.get("id") != object_id:
        raise WorkflowError("Exact native object readback required")
    state = {key: record.get(key) for key in ("status", "approval_status", "state", "request_status")}
    if not any(value is not None for value in state.values()):
        raise WorkflowError("Native object state unavailable")
    if any(value is not None and (not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,80}", value))
           for value in state.values()):
        raise WorkflowError("Invalid native object state")
    # Bind all returned fields without storing private native payloads.
    return {"id": object_id, **state, "record_digest": digest(record)}


class ScopedSandboxWorkflowProvider:
    """Fixed sandbox contract adapter; root injects already-scoped auth and HTTP.

    `business_id` is a root-verified installation binding, NOT inferred from a
    token string or an OAuth login. `observed_at` dates the actual grant receipt.
    MOCK_HTTP is the default and must not be presented as a live Ramp result.
    """
    def __init__(self, *, business_id, access_token, granted_scopes, observed_at, http,
                 transport_provenance="MOCK_HTTP", clock=utcnow):
        self.business_id = uuid_text(business_id)
        self._token = access_token
        self._scopes = frozenset(granted_scopes)
        self.observed_at, self.http, self.clock = observed_at, http, clock
        self.transport_provenance = transport_provenance
        if (not isinstance(access_token, str) or not access_token or any(c.isspace() for c in access_token) or
                transport_provenance not in {"MOCK_HTTP", "LIVE_RAMP_SANDBOX"} or
                not all(isinstance(s, str) and re.fullmatch(r"[a-z_]+:(read|write)", s) for s in self._scopes)):
            raise WorkflowError("Invalid scoped sandbox transport")
        timestamp(observed_at)

    def capabilities(self):
        return {"origin": ORIGIN, "environment": "sandbox", "business_id": self.business_id,
                "granted_scopes": sorted(self._scopes), "observed_at": self.observed_at,
                "transport_provenance": self.transport_provenance,
                "financial_decisions": "SIMULATION_ONLY"}

    def require(self, scopes):
        if (not set(scopes) <= self._scopes or not timedelta(0) <= self.clock()-timestamp(self.observed_at) <= timedelta(minutes=15)):
            raise WorkflowError("Current explicitly granted provider scopes required")

    def _call(self, method, path, scopes, *, body=None, query=None, expected=200):
        self.require(scopes)
        if not path.startswith(PREFIX + "/") or any(c in path for c in "?#\\"):
            raise WorkflowError("Invalid provider path")
        try:
            response = self.http.request(method, ORIGIN + path, headers={"Authorization": "Bearer " + self._token,
                                         "Accept": "application/json"}, json=body, params=query,
                                         follow_redirects=False, timeout=4.0, auth=None)
            if response.status_code != expected or len(response.content) > 4_000_000:
                raise ProviderFailure("Provider response unavailable; reconcile any attempted mutation")
            return strict_json(response.content)
        except Exception:
            # Transport errors can contain tokens, URLs and native private bodies.
            raise ProviderFailure("Provider response unavailable; reconcile any attempted mutation") from None

    def read_object(self, object_type, object_id):
        uuid_text(object_id)
        if object_type not in OBJECTS:
            raise WorkflowError("Unsupported native object type")
        path, scope = OBJECTS[object_type]
        result = self._call("GET", f"{PREFIX}/{path}/{object_id}", {scope + ":read"})
        remote_state(result, object_id)
        return result

    def context(self, trigger):
        request = self.read_object("unified-requests", trigger["request_id"])
        if request.get("request_status") != "SUBMITTED" or request.get("deleted_at") is not None:
            raise WorkflowError("Procurement request is not awaiting review")
        form_id = request.get("custom_form_collection_response_uuid")
        form_digest = None
        if form_id is not None:
            form = self._call("GET", f"{PREFIX}/custom-form/collections/responses/{uuid_text(form_id)}", {"custom_forms:read"})
            if not isinstance(form, dict) or form.get("id") != form_id:
                raise WorkflowError("Exact custom form readback required")
            form_digest = digest(form)
        # These are the exact OpenAPI fields; spend_program_id is not on this resource.
        program_ref = request.get("assigned_spend_intent") or request.get("spend_intent")
        if not isinstance(program_ref, dict):
            raise WorkflowError("Request spend program reference unavailable")
        program_id = uuid_text(program_ref.get("uuid"))
        program = self._call("GET", f"{PREFIX}/spend-programs/{program_id}", {"spend_programs:read"})
        if program.get("id") != program_id:
            raise WorkflowError("Exact spend program readback required")
        nodes = self._call("GET", f"{PREFIX}/spend-programs/{program_id}/workflow-nodes", {"spend_programs:read"},
                           query={"service_key": trigger["service_key"]})
        matches = [n for n in nodes.get("workflow_nodes", []) if isinstance(n, dict) and
                   n.get("node_id") == trigger["node_id"] and n.get("service_key") == trigger["service_key"]]
        if len(matches) != 1:
            raise WorkflowError("Exact configured workflow node unavailable")
        return {"request_state": remote_state(request, trigger["request_id"]),
                "spend_program_id": program_id, "program_digest": digest(program),
                "form_id": form_id, "form_digest": form_digest, "node_digest": digest(matches[0])}

    def comments(self, object_type, object_id):
        if object_type not in COMMENT_TYPES:
            raise WorkflowError("Unsupported discussion object")
        uuid_text(object_id)
        scope = OBJECTS[object_type][1] + ":read"
        path = f"{PREFIX}/comments/{object_type}/{object_id}"
        query, rows, seen = {"page_size": 100}, [], set()
        for _ in range(100):
            data = self._call("GET", path, {scope}, query=query)
            if not isinstance(data.get("data"), list) or not isinstance(data.get("page"), dict) or "next" not in data["page"]:
                raise ProviderFailure("Incomplete discussion readback")
            rows.extend(data["data"])
            nxt = data["page"]["next"]
            if nxt is None:
                return rows
            if not isinstance(nxt, str) or nxt in seen:
                raise ProviderFailure("Invalid discussion pagination")
            seen.add(nxt)
            url = urlsplit(nxt)
            args = parse_qs(url.query, keep_blank_values=True)
            if (f"{url.scheme}://{url.netloc}" != ORIGIN or url.path != path or url.fragment or
                    not args or not set(args) <= {"start", "page_size"} or "start" not in args or
                    any(len(v) != 1 or not v[0] for v in args.values())):
                raise ProviderFailure("Discussion pagination left exact object")
            query = {"page_size": 100, "start": opaque(args["start"][0])}
        raise ProviderFailure("Discussion pagination incomplete")

    def post_comment(self, plan):
        obj, ident, body = plan["object_type"], plan["object_id"], plan["body"]
        if obj not in COMMENT_TYPES or body != _comment_body(plan):
            raise WorkflowError("Only fixed informational finding comments permitted")
        return self._call("POST", f"{PREFIX}/comments/{obj}/{uuid_text(ident)}", {OBJECTS[obj][1] + ":write"}, body=body, expected=201)

    def patch_metadata(self, plan):
        body = plan["body"]
        if set(body) != {"status", "url"} or body["status"] not in METADATA_STATUSES:
            raise WorkflowError("Only informational metadata permitted")
        inspector_url(body["url"], plan["inspector_origins"])
        ident = uuid_text(plan["approval_trigger_instance_id"])
        return self._call("PATCH", f"{PREFIX}/blank-canvas-approvals/{ident}/metadata", {"blank_canvas:write"}, body=body)

    def decide(self, plan):
        raise WorkflowError("Real financial approve/reject is disabled; separate authority and gates required")


DEMO_NOTE_SHAPES = {
    # Demo line only: the two fixed note shapes Uptime may leave on a matched sandbox bill.
    "possible_credit": re.compile(
        r"Uptime: this bill may be eligible for a [A-Z]{3} [0-9][0-9,]*\.[0-9]{2} service credit under agreement "
        r"[A-Za-z0-9-]{1,40} \((January|February|March|April|May|June|July|August|September|October|November|December) "
        r"[0-9]{4} availability\)\. A claim is being prepared in Uptime\."),
    "credit_applied": re.compile(
        r"Uptime: the vendor awarded a [A-Z]{3} [0-9][0-9,]*\.[0-9]{2} service credit and it has been applied to this "
        r"invoice in Uptime\. Remaining balance [A-Z]{3} [0-9][0-9,]*\.[0-9]{2}\."),
    "price_exception": re.compile(
        r"Uptime: this bill is [A-Z]{3} [0-9][0-9,]*\.[0-9]{2} above the contracted rate \([^()\n]{1,200}\)\. "
        r"Review it in Uptime before payment\."),
}


def _comment_body(plan):
    if "demo_note_kind" in plan:
        kind, text = plan["demo_note_kind"], plan.get("demo_note_text")
        if (plan["object_type"] != "bills" or kind not in DEMO_NOTE_SHAPES or not isinstance(text, str)
                or not DEMO_NOTE_SHAPES[kind].fullmatch(text)):
            raise WorkflowError("Only the fixed demo note shapes are permitted")
        return {"message": text, "message_format": "PLAIN_TEXT"}
    if "native_review_reason" in plan:
        reason = plan["native_review_reason"]
        if not isinstance(reason, str) or reason not in NATIVE_REVIEW_MESSAGES or plan["object_type"] != "bills":
            raise WorkflowError("Unsupported native review reason")
        _sha(plan.get("native_review_digest"))
        return {"message": (NATIVE_REVIEW_MESSAGES[reason] + " "
                            "No approval, payment instruction, entitlement or realized savings is asserted.\n"
                            + plan["dedup_marker"]), "message_format": "PLAIN_TEXT"}
    return {"message": (f"Uptime informational finding for {plan['object_type']}/{plan['object_id']}. "
                        f"Finding SHA-256: {plan['finding_digest']}. "
                        "Evidence requires human review. No approval, payment instruction, entitlement or realized savings is asserted.\n"
                        + plan["dedup_marker"]), "message_format": "PLAIN_TEXT"}


class SimulatedWorkflowProvider(ScopedSandboxWorkflowProvider):
    """Separate in-memory provider. Native shapes, never proof of Ramp execution."""
    def __init__(self, *, business_id, records, clock=utcnow, contexts=None):
        self.records = deepcopy(records)
        self.contexts = deepcopy(contexts or {})
        self.threads, self.metadata, self.decisions, self.calls = {}, {}, {}, []
        self.business_id, self.clock = uuid_text(business_id), clock
        self.observed_at = clock().isoformat()
        self._scopes = frozenset({"bills:read", "bills:write", "transactions:read", "transactions:write"}) | CONTEXT_SCOPES
        self.transport_provenance = "SIMULATED_RAMP"

    def read_object(self, object_type, object_id):
        self.require({OBJECTS[object_type][1] + ":read"})
        if (object_type, object_id) not in self.records:
            raise WorkflowError("Exact simulated object unavailable")
        result = deepcopy(self.records[object_type, object_id])
        remote_state(result, object_id)
        return result

    def context(self, trigger):
        self.require(CONTEXT_SCOPES)
        key = trigger["id"]
        context = self.contexts.get(key)
        if context is None or context.get("node_id") != trigger["node_id"] or context.get("service_key") != trigger["service_key"]:
            raise WorkflowError("Exact simulated workflow context unavailable")
        return {"request_state": remote_state(self.read_object("unified-requests", trigger["request_id"]), trigger["request_id"]),
                "context_digest": digest(context)}

    def comments(self, object_type, object_id):
        self.require({OBJECTS[object_type][1] + ":read"})
        return deepcopy(self.threads.get((object_type, object_id), []))

    def post_comment(self, plan):
        if plan["body"] != _comment_body(plan):
            raise WorkflowError("Invalid simulation comment")
        self.calls.append(("POST", plan["path"]))
        result = {"id": str(uuid4()), "message": plan["body"]["message"], "created_at": self.clock().isoformat(),
                  "user_id": "00000000-0000-4000-8000-000000000001"}
        self.threads.setdefault((plan["object_type"], plan["object_id"]), []).append(result)
        return deepcopy(result)

    def patch_metadata(self, plan):
        self.calls.append(("PATCH", plan["path"]))
        result = {"approval_trigger_instance_id": plan["approval_trigger_instance_id"], **plan["body"]}
        self.metadata[plan["approval_trigger_instance_id"]] = result
        return deepcopy(result)

    def decide(self, plan):
        if plan["body"] not in ({"action": "approve"}, {"action": "reject"}):
            raise WorkflowError("Invalid simulated native decision")
        trigger = plan["approval_trigger_instance_id"]
        if trigger in self.decisions:
            raise WorkflowError("Simulated trigger was already decided")
        self.calls.append(("POST", plan["path"]))
        self.decisions[trigger] = plan["body"]["action"]
        return {"message": "Blank canvas workflow step " + ("approved" if plan["body"]["action"] == "approve" else "rejected") + " successfully"}


@dataclass(frozen=True)
class WorkflowReviewer:
    public_key: bytes = field(repr=False)
    simulation_only: bool = True


class RampWorkflow:
    def __init__(self, path, *, tenant, business_id, finding_resolver, reviewers=None, inbox=None,
                 inspector_origins=(), clock=utcnow, native_review_reasons=False):
        self.path, self.tenant, self.business_id = Path(path), opaque(tenant), uuid_text(business_id)
        self.finding_resolver, self.reviewers, self.inbox = finding_resolver, dict(reviewers or {}), inbox
        self.inspector_origins, self.clock = tuple(sorted(inspector_origins)), clock
        # Only the native binding opts in, after validating the trusted resolver's
        # proof. Generic callers and existing outbox plans retain their old bytes.
        self.native_review_reasons = native_review_reasons
        if inbox and (Path(inbox.path).resolve() != self.path.resolve() or inbox.deployment.tenant != tenant or
                      inbox.deployment.business_id != business_id):
            raise WorkflowError("Webhook and outbox must share the exact tenant, business and database")
        for origin in self.inspector_origins:
            inspector_url(origin + "/", self.inspector_origins)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with database(self.path) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS rw_installation (tenant TEXT PRIMARY KEY, business_id TEXT NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS rw_outbox (
                    tenant TEXT NOT NULL, id TEXT NOT NULL, plan TEXT NOT NULL, status TEXT NOT NULL,
                    review TEXT, remote_id TEXT, remote_state TEXT, attempted_at TEXT,
                    PRIMARY KEY(tenant,id));
            """)
            db.execute("INSERT OR IGNORE INTO rw_installation VALUES(?,?)", (self.tenant, self.business_id))
            if db.execute("SELECT business_id FROM rw_installation WHERE tenant=?", (self.tenant,)).fetchone()[0] != self.business_id:
                raise WorkflowError("Workflow tenant business binding mismatch")
        self.path.chmod(0o600)

    def _finding(self, object_type, object_id, *, include_native_reason=False):
        try:
            finding = self.finding_resolver(object_type, object_id)
        except (KeyError, LookupError):
            raise WorkflowError("Exact native finding unavailable; no fallback permitted") from None
        if (not isinstance(finding, dict) or finding.get("provider_object_type") != object_type or
                finding.get("provider_id") != object_id or finding.get("business_id") != self.business_id or
                finding.get("workspace_tenant") != self.tenant):
            raise WorkflowError("Finding must match exact workspace, business and object")
        _sha(finding.get("finding_digest"))
        observed = timestamp(finding.get("observed_at"))
        if not timedelta(0) <= self.clock()-observed <= timedelta(hours=24):
            raise WorkflowError("Stale finding requires reevaluation")
        sources = finding.get("sources")
        if not isinstance(sources, list) or not sources or any(not isinstance(s, str) or s not in SOURCE_LABELS for s in sources):
            raise WorkflowError("Explicit finding provenance required")
        result = {"finding_digest": finding["finding_digest"], "sources": sorted(set(sources)),
                "observed_at": finding["observed_at"], "simulation_only":
                bool(set(sources) & {"SYNTHETIC_CUSTOMER", "SIMULATED_RAMP", "SIMULATED_VENDOR"}) or
                str(finding.get("finding_kind", "")).startswith("SYNTHETIC")}
        if include_native_reason and "native_review_reason" in finding:
            reason = finding["native_review_reason"]
            if (not self.native_review_reasons or object_type != "bills" or
                    not isinstance(reason, str) or reason not in NATIVE_REVIEW_MESSAGES):
                raise WorkflowError("Unsupported native review reason")
            result.update(native_review_reason=reason,
                          native_review_digest=_sha(finding.get("native_review_digest")))
        return result

    def _check_finding(self, plan):
        fields = ["finding_digest", "sources", "observed_at", "simulation_only"]
        with_reason = "native_review_reason" in plan
        if with_reason:
            fields += ["native_review_reason", "native_review_digest"]
        if self._finding(plan["object_type"], plan["object_id"], include_native_reason=with_reason) != {
                key: plan[key] for key in fields}:
            raise WorkflowError("Finding changed after review")

    def _provider(self, provider, scopes):
        cap = provider.capabilities()
        if (cap.get("business_id") != self.business_id or cap.get("origin") != ORIGIN or
                cap.get("environment") != "sandbox" or cap.get("transport_provenance") not in PROVENANCE):
            raise WorkflowError("Exact sandbox provider/business binding required")
        provider.require(scopes)
        return cap

    def prepare_comment(self, object_type, object_id, *, provider):
        if object_type not in COMMENT_TYPES:
            raise WorkflowError("No supported native discussion endpoint for this object")
        uuid_text(object_id)
        base = OBJECTS[object_type][1]
        plan = self._base("comment", object_type, object_id, provider, {base+":read", base+":write"})
        plan.update(method="POST", path=f"{PREFIX}/comments/{object_type}/{object_id}", required_scope=base+":write")
        return self._save(plan)

    def _base(self, kind, object_type, object_id, provider, scopes):
        finding = self._finding(object_type, object_id, include_native_reason=self.native_review_reasons)
        cap = self._provider(provider, scopes)
        if cap["transport_provenance"] == "LIVE_RAMP_SANDBOX" and finding["simulation_only"]:
            raise WorkflowError("Synthetic findings are simulation-only")
        state = remote_state(provider.read_object(object_type, object_id), object_id)
        return {"kind": kind, "tenant": self.tenant, "business_id": self.business_id,
                "object_type": object_type, "object_id": object_id, **finding,
                "expected_remote_state": state, "capabilities": cap, "required_scopes": sorted(scopes),
                "transport_provenance": cap["transport_provenance"], "approval_trigger_instance_id": None,
                "actual_money_prevented": None, "actual_recovery": None}

    def _trigger_plan(self, kind, trigger_id, provider):
        if self.inbox is None:
            raise WorkflowError("Verified procurement webhook deployment required")
        trigger = self.inbox.trigger(trigger_id)
        if (provider.transport_provenance == "LIVE_RAMP_SANDBOX" and trigger["source"] != "RAMP_SANDBOX_WEBHOOK"):
            raise WorkflowError("Simulated webhook cannot authorize sandbox transport")
        plan = self._base(kind, "unified-requests", trigger["request_id"], provider, CONTEXT_SCOPES)
        plan.update(approval_trigger_instance_id=trigger_id, trigger=trigger, context=provider.context(trigger),
                    required_scope="blank_canvas:write")
        return plan

    def prepare_metadata(self, trigger_id, *, provider, status="Human review required", url):
        if status not in METADATA_STATUSES:
            raise WorkflowError("Informational metadata status required")
        inspector_url(url, self.inspector_origins)
        plan = self._trigger_plan("metadata", trigger_id, provider)
        plan.update(method="PATCH", path=f"{PREFIX}/blank-canvas-approvals/{trigger_id}/metadata",
                    body={"status": status, "url": url}, inspector_origins=list(self.inspector_origins))
        return self._save(plan)

    def prepare_decision(self, trigger_id, *, provider, action):
        if action not in {"approve", "reject"} or type(provider) is not SimulatedWorkflowProvider:
            raise WorkflowError("Financial decisions are supported only on the isolated simulated transport")
        plan = self._trigger_plan("decision", trigger_id, provider)
        plan.update(method="POST", path=f"{PREFIX}/blank-canvas-approvals/{trigger_id}", body={"action": action})
        return self._save(plan)

    def _save(self, plan):
        # Stable logical key excludes token observation time: changing capabilities
        # cannot make an already attempted action eligible for a second delivery.
        key = {k: plan[k] for k in ("tenant", "business_id", "kind", "object_type", "object_id",
                                  "finding_digest", "approval_trigger_instance_id", "transport_provenance")}
        if plan["kind"] == "metadata":
            key["metadata"] = plan["body"]
        # Approve and reject share one trigger-level unit of work.
        if plan["kind"] == "decision":
            key.pop("finding_digest")
        ident = digest(key)
        plan.update(id=ident, dedup_marker=f"[uptime:{ident}]")
        if plan["kind"] == "comment":
            plan["body"] = _comment_body(plan)
        plan["review_digest"] = digest(plan)
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            # A different logical action on the same object (for example, a newer finding)
            # must not be prepared while an earlier one may already have reached Ramp.
            for pending in db.execute("SELECT id,plan FROM rw_outbox WHERE tenant=? AND status IN ('UNCERTAIN','DISPATCHING')",
                                      (self.tenant,)):
                prior = json.loads(pending["plan"])
                if (pending["id"] != ident and prior.get("kind") == plan["kind"]
                        and prior.get("object_type") == plan["object_type"] and prior.get("object_id") == plan["object_id"]):
                    raise WorkflowError("An uncertain action on this exact object must be reconciled first")
            old = db.execute("SELECT plan,status FROM rw_outbox WHERE tenant=? AND id=?", (self.tenant, ident)).fetchone()
            if old and old[0] != canonical(plan):
                if old[1] not in {"PREPARED", "REVIEWED", "BLOCKED"}:
                    raise WorkflowError("This logical action was already attempted; reconcile its original receipt")
                db.execute("UPDATE rw_outbox SET plan=?,status='PREPARED',review=NULL WHERE tenant=? AND id=?",
                           (canonical(plan), self.tenant, ident))
            else:
                db.execute("INSERT OR IGNORE INTO rw_outbox(tenant,id,plan,status) VALUES(?,?,?,'PREPARED')",
                           (self.tenant, ident, canonical(plan)))
        return self.get(ident)

    def _row(self, db, action_id):
        _sha(action_id)
        row = db.execute("SELECT * FROM rw_outbox WHERE tenant=? AND id=?", (self.tenant, action_id)).fetchone()
        if row is None:
            raise WorkflowError("Exact workflow action unavailable")
        # The signed review covers review_digest; a stored plan edited without it is refused.
        plan = json.loads(row["plan"])
        claimed = plan.pop("review_digest", None)
        if (claimed != digest(plan) or plan.get("id") != action_id or plan.get("tenant") != self.tenant
                or plan.get("business_id") != self.business_id):
            raise WorkflowError("Stored workflow plan integrity mismatch")
        return row

    def get(self, action_id):
        with database(self.path) as db:
            row = self._row(db, action_id)
            plan = json.loads(row["plan"])
            current = None
            if plan.get("approval_trigger_instance_id"):
                # Display only: a later reset never rewrites the recorded delivery.
                try:
                    self._guard_trigger(plan, db)
                    current = True
                except RampError:
                    current = False
            return {**plan, "status": row["status"], "delivery": row["status"], "trigger_current": current,
                    "remote_id": row["remote_id"],
                    "remote_state": json.loads(row["remote_state"]) if row["remote_state"] else None}

    def review_message(self, action_id, *, reviewer, expires_at):
        plan = self.get(action_id)
        if "native_review_reason" in plan:
            self._check_finding(plan)
        opaque(reviewer)
        if type(expires_at) is not int or not int(self.clock().timestamp()) < expires_at <= int(self.clock().timestamp())+300:
            raise WorkflowError("Review expiry must be within five minutes")
        return canonical(["uptime-ramp-review-v1", self.tenant, self.business_id, action_id,
                          plan["review_digest"], reviewer, expires_at])

    def _verify_review(self, plan, review):
        reviewer = self.reviewers.get(review["reviewer"])
        if not reviewer or (reviewer.simulation_only and plan["transport_provenance"] == "LIVE_RAMP_SANDBOX"):
            raise WorkflowError("Named human reviewer authority required for real sandbox writes")
        if review["expires_at"] <= int(self.clock().timestamp()):
            raise WorkflowError("Review expired")
        message = canonical(["uptime-ramp-review-v1", self.tenant, self.business_id, plan["id"],
                             plan["review_digest"], review["reviewer"], review["expires_at"]])
        if not verify_reviewer(reviewer.public_key, message, review["proof"]):
            raise WorkflowError("Invalid exact-action reviewer signature")

    def review(self, action_id, *, reviewer, expires_at, proof):
        self.review_message(action_id, reviewer=reviewer, expires_at=expires_at)
        review = {"reviewer": reviewer, "expires_at": expires_at, "proof": proof}
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, action_id)
            if row["status"] not in {"PREPARED", "REVIEWED"}:
                raise WorkflowError("Only an unattempted plan can be reviewed")
            plan = json.loads(row["plan"])
            self._verify_review(plan, review)
            self._guard_trigger(plan, db)
            db.execute("UPDATE rw_outbox SET review=?,status='REVIEWED' WHERE tenant=? AND id=?", (canonical(review), self.tenant, action_id))
        return self.get(action_id)

    def _guard_trigger(self, plan, db):
        if plan["approval_trigger_instance_id"]:
            if self.inbox is None or self.inbox.trigger(plan["approval_trigger_instance_id"], db=db) != plan["trigger"]:
                raise WorkflowError("Exact active procurement trigger changed")

    def _preflight(self, plan, provider):
        if self._provider(provider, plan["required_scopes"]) != plan["capabilities"]:
            raise WorkflowError("Provider capabilities changed after review")
        self._check_finding(plan)
        if remote_state(provider.read_object(plan["object_type"], plan["object_id"]), plan["object_id"]) != plan["expected_remote_state"]:
            raise WorkflowError("Exact native object changed after review")
        if plan["approval_trigger_instance_id"] and provider.context(plan["trigger"]) != plan["context"]:
            raise WorkflowError("Procurement context changed after review")
        if plan["kind"] == "decision" and type(provider) is not SimulatedWorkflowProvider:
            raise WorkflowError("Real financial decisions are disabled")

    def _match_comments(self, plan, provider, remote_id=None):
        matches = []
        for row in provider.comments(plan["object_type"], plan["object_id"]):
            if not isinstance(row, dict):
                raise ProviderFailure("Invalid native discussion readback")
            message = row.get("message")
            if isinstance(message, str) and plan["dedup_marker"] in message:
                if message != plan["body"]["message"] or (remote_id is not None and row.get("id") != remote_id):
                    raise WorkflowError("Dedup marker conflicts with exact comment content or ID")
                if not isinstance(row.get("id"), str) or not row["id"] or len(row["id"]) > 200:
                    raise WorkflowError("Invalid remote comment ID")
                uuid_text(row.get("user_id"))
                timestamp(row.get("created_at"))
                matches.append(row)
        if len(matches) > 1:
            raise WorkflowError("Multiple native comments share the dedup marker")
        return matches[0] if matches else None

    def execute(self, action_id, *, provider):
        plan = self.get(action_id)
        if plan["status"] == "DELIVERED":
            return plan
        if plan["status"] in {"DISPATCHING", "UNCERTAIN"}:
            raise WorkflowError("Delivery may have occurred; reconcile without resending")
        if plan["status"] != "REVIEWED":
            raise WorkflowError("Exact signed review required")
        # Reads happen outside the mutation lock; recheck trigger and review at the boundary.
        self._preflight(plan, provider)
        with database(self.path) as db:
            row = self._row(db, action_id)
            self._verify_review(plan, json.loads(row["review"]))
            self._guard_trigger(plan, db)
        if plan["kind"] == "comment":
            existing = self._match_comments(plan, provider)
            if existing:
                return self._delivered(action_id, existing["id"], {"verification": "EXACT_DISCUSSION_GET", "message_digest": digest(existing["message"])})
        with database(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, action_id)
            if row["status"] != "REVIEWED" or json.loads(row["plan"])["review_digest"] != plan["review_digest"]:
                raise WorkflowError("Action changed or was concurrently dispatched")
            self._verify_review(plan, json.loads(row["review"]))
            self._guard_trigger(plan, db)
            db.execute("UPDATE rw_outbox SET status='DISPATCHING',attempted_at=? WHERE tenant=? AND id=?",
                       (self.clock().isoformat(), self.tenant, action_id))
        # Crash after this commit is UNCERTAIN, never an automatic retry. Serialize
        # the final local reset check and mutation. Remote resets can still race;
        # only Ramp can enforce remote instance currency atomically.
        try:
            with database(self.path) as db, db:
                db.execute("BEGIN IMMEDIATE")
                self._guard_trigger(plan, db)
                result = {"comment": provider.post_comment, "metadata": provider.patch_metadata, "decision": provider.decide}[plan["kind"]](plan)
                remote_id, state = self._mutation_receipt(plan, result)
                db.execute("UPDATE rw_outbox SET status='UNCERTAIN',remote_id=?,remote_state=? WHERE tenant=? AND id=?",
                           (remote_id, canonical(state), self.tenant, action_id))
        except Exception:
            with database(self.path) as db, db:
                db.execute("UPDATE rw_outbox SET status='UNCERTAIN' WHERE tenant=? AND id=? AND status='DISPATCHING'", (self.tenant, action_id))
            return self.get(action_id)
        if plan["kind"] == "comment":
            return self.reconcile(action_id, provider=provider)
        return self._delivered(action_id, remote_id, state)

    def _mutation_receipt(self, plan, result):
        if not isinstance(result, dict):
            raise WorkflowError("Invalid mutation response")
        if plan["kind"] == "comment":
            if (not isinstance(result.get("id"), str) or not result["id"] or len(result["id"]) > 200 or
                    result.get("message") != plan["body"]["message"]):
                raise WorkflowError("Exact comment mutation receipt mismatch")
            uuid_text(result.get("user_id"))
            timestamp(result.get("created_at"))
            return result["id"], {"verification": "POST_RESPONSE_ONLY", "message_digest": digest(result["message"])}
        if plan["kind"] == "metadata":
            if (result.get("approval_trigger_instance_id") != plan["approval_trigger_instance_id"] or
                    any(result.get(key) != value for key, value in plan["body"].items())):
                raise WorkflowError("Exact metadata response mismatch")
            return plan["approval_trigger_instance_id"], {"verification": "PATCH_RESPONSE_ONLY", **plan["body"]}
        expected = "Blank canvas workflow step " + ("approved" if plan["body"]["action"] == "approve" else "rejected") + " successfully"
        if result.get("message") != expected:
            raise WorkflowError("Unexpected simulated decision response")
        return plan["approval_trigger_instance_id"], {"verification": "SIMULATED_RESPONSE_ONLY", "action": plan["body"]["action"]}

    def _delivered(self, action_id, remote_id, state):
        with database(self.path) as db, db:
            db.execute("UPDATE rw_outbox SET status='DELIVERED',remote_id=?,remote_state=? WHERE tenant=? AND id=?",
                       (remote_id, canonical(state), self.tenant, action_id))
        return self.get(action_id)

    def reconcile(self, action_id, *, provider):
        plan = self.get(action_id)
        self._provider(provider, {OBJECTS[plan["object_type"]][1] + ":read"})
        if provider.transport_provenance != plan["transport_provenance"]:
            raise WorkflowError("Receipt transport provenance mismatch")
        if plan["status"] == "DELIVERED":
            return plan
        if plan["status"] not in {"UNCERTAIN", "DISPATCHING"}:
            raise WorkflowError("No uncertain delivery to reconcile")
        if plan["kind"] != "comment":
            # No invented GET metadata/approval endpoint or blind PATCH/POST retry.
            return plan
        try:
            match = self._match_comments(plan, provider, plan["remote_id"])
        except ProviderFailure:
            return plan
        if match:
            return self._delivered(action_id, match["id"], {"verification": "EXACT_DISCUSSION_GET", "message_digest": digest(match["message"])})
        return plan


def register_ramp_workflow(app, workflow, provider, auth):
    """Optional root mount: authenticated read/prepare/review/execute routes.

    Root injects Authority.actor/reviewer and an exact finding resolver. The
    isolated provider webhook listener is deliberately a different application.
    """
    from fastapi import Depends, HTTPException
    from pydantic import BaseModel, ConfigDict

    class Prepare(BaseModel):
        model_config = ConfigDict(extra="forbid")
        kind: str
        object_type: str | None = None
        object_id: str | None = None
        approval_trigger_instance_id: str | None = None
        status: str = "Human review required"
        url: str | None = None
        action: str | None = None

    class Review(BaseModel):
        model_config = ConfigDict(extra="forbid")
        reviewer: str
        expires_at: int
        proof: str

    def tenant(principal):
        if principal.tenant != workflow.tenant:
            raise HTTPException(403, "Workspace tenant mismatch")

    def call(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except RampError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/api/ramp/workflow/actions/{action_id}")
    def get(action_id: str, principal=Depends(auth.actor)):
        tenant(principal)
        return call(workflow.get, action_id)

    @app.post("/api/ramp/workflow/prepare")
    def prepare(body: Prepare, principal=Depends(auth.reviewer)):
        tenant(principal)
        if body.kind == "comment":
            return call(workflow.prepare_comment, body.object_type, body.object_id, provider=provider)
        if body.kind == "metadata":
            return call(workflow.prepare_metadata, body.approval_trigger_instance_id, provider=provider, status=body.status, url=body.url)
        if body.kind == "decision":
            return call(workflow.prepare_decision, body.approval_trigger_instance_id, provider=provider, action=body.action)
        raise HTTPException(400, "Unsupported workflow kind")

    @app.post("/api/ramp/workflow/actions/{action_id}/review")
    def review(action_id: str, body: Review, principal=Depends(auth.reviewer)):
        tenant(principal)
        if body.reviewer != principal.subject:
            raise HTTPException(403, "Review subject mismatch")
        return call(workflow.review, action_id, **body.model_dump())

    @app.post("/api/ramp/workflow/actions/{action_id}/execute")
    def execute(action_id: str, principal=Depends(auth.reviewer)):
        tenant(principal)
        return call(workflow.execute, action_id, provider=provider)

    @app.post("/api/ramp/workflow/actions/{action_id}/reconcile")
    def reconcile(action_id: str, principal=Depends(auth.reviewer)):
        tenant(principal)
        return call(workflow.reconcile, action_id, provider=provider)
    return workflow
