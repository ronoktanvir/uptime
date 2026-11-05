"""Operator-enabled bill comments through exact local and native authorization.

No provider is constructed at import or registration. All live traffic uses a
fixed sandbox origin, controlled client credentials, and the workflow outbox.
The HTTP boundary consumes the independent mandate for the bytes it sends.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from threading import RLock
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from . import gates, mandates, ramp_credentials
from .auth import NAME
from .auth_keys import public_bytes
from .contracts import fingerprint
from .ramp import ORIGIN, RampError, uuid_text
from .ramp_records import sanitize_bill
from .ramp_webhooks import digest, strict_json, timestamp, utcnow
from .ramp_workflow import RampWorkflow, ScopedSandboxWorkflowProvider, WorkflowError, WorkflowReviewer, remote_state

PREFIX = "/api/ramp/native"
SCOPES = frozenset({"business:read", "bills:read", "bills:write"})
READ_SCOPES = frozenset({"business:read", "bills:read"})
ROOT = Path(__file__).resolve().parents[1]


def _protected_bytes(path):
    """Read a local operator file without following symlinks or accepting shared custody."""
    path = Path(path)
    if (not path.is_absolute() or path.resolve() != path or path.is_relative_to(ROOT)
            or path.parent.stat().st_uid != os.getuid() or path.parent.stat().st_mode & 0o077):
        raise WorkflowError("Use a protected physical operator directory outside the repository")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077
                or info.st_nlink != 1 or info.st_size > 100_000):
            raise WorkflowError("Protected owner-only operator file required")
        return handle.read(100_001)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NativeConfig(_Strict):
    schema_version: Literal["uptime-native-operator/1"]
    enabled: Literal[True]
    tenant: str
    business_id: str
    reviewers: dict[str, dict[str, str]]


class Prepare(_Strict):
    object_type: Literal["bills"]
    object_id: str


class Review(_Strict):
    expires_at: int
    proof: str


class Execute(_Strict):
    review_digest: str


class Empty(_Strict):
    pass


def _credentials(path=None):
    # No token, scope or credential path can come from an HTTP caller or native config.
    if os.environ.get("RAMP_ENV") != "sandbox" or os.environ.get("RAMP_BASE_URL", ORIGIN) != ORIGIN:
        raise WorkflowError("Exact sandbox operator environment required")
    try:
        return ramp_credentials.load(path).basic
    except ramp_credentials.CredentialError:
        raise WorkflowError("Controlled sandbox credentials unavailable") from None


def _client():
    return httpx.Client(trust_env=False, follow_redirects=False, timeout=4.0,
                        transport=httpx.HTTPTransport(retries=0))


def _response(client, method, path, *, headers, content=None):
    try:
        response = client.request(method, ORIGIN + path, headers=headers, content=content,
                                  follow_redirects=False, timeout=4.0, auth=None)
        if response.status_code != 200 or len(response.content) > 4_000_000:
            raise ValueError
        value = strict_json(response.content)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except Exception:
        raise WorkflowError("Provider preflight unavailable; no native mutation attempted") from None


@dataclass
class _Grant:
    client: object = field(repr=False)
    token: str = field(repr=False)
    scopes: frozenset
    observed_at: str
    expires_at: object
    receipt: dict
    provenance: str


def wire_for(plan):
    """Public review artifact. This exact encoding is reused by the guarded HTTP adapter."""
    body = json.dumps(plan["body"], ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    effect = mandates.native_effect_from_request(plan["business_id"], plan["method"], plan["path"], body)
    if effect.action != "bill.comment.create" or plan["kind"] != "comment" or plan["object_type"] != "bills":
        raise WorkflowError("Only informational bill comments are enabled")
    return {"method": plan["method"], "path": plan["path"], "body": body.decode(),
            "body_sha256": sha256(body).hexdigest(), "effect": effect.model_dump()}


class _AuthorizedHTTP:
    """The workflow cannot send a mutation without a request-local exact reservation."""
    def __init__(self, binding, grant, *, principal=None, plan=None):
        self.binding, self.grant, self.principal, self.plan = binding, grant, principal, plan
        self.reserved = wire_for(plan) if plan is not None else None
        self.used = False
        self.mandate_id = None

    def request(self, method, url, *, headers, json=None, params=None, **kwargs):
        self.binding._guard()
        self.binding._current_grant(self.grant)
        path = url.removeprefix(ORIGIN)
        if url != ORIGIN + path or not re.fullmatch(
                r"/developer/v1/(?:bills|comments/bills)/[0-9a-f-]{36}", path):
            raise WorkflowError("Native transport destination is outside the bill allowlist")
        if headers.get("Authorization") != "Bearer " + self.grant.token:
            raise WorkflowError("Native transport token binding changed")
        if method == "GET":
            if json is not None:
                raise WorkflowError("Native reads cannot carry a body")
            return self.grant.client.request("GET", url, headers=headers, params=params,
                                             follow_redirects=False, timeout=4.0, auth=None)
        if (method != "POST" or self.plan is None or self.principal is None or self.used
                or params is not None or json != self.plan["body"]):
            raise WorkflowError("No exact native dispatch reservation")
        wire = wire_for({**self.plan, "method": method, "path": path, "body": json})
        if wire != self.reserved:
            raise WorkflowError("Native request differs from the reviewed bytes")
        # Read and recompute again after discussion lookup, immediately before authorization.
        self.binding._final_check(self.plan, self.grant)
        effect = mandates.native_effect_from_request(self.binding.config.business_id, method, path,
                                                     wire["body"].encode())
        self.mandate_id = self.binding.auth.authorize_native(self.principal, **effect.model_dump())
        self.used = True  # Consumed before the potentially ambiguous network operation; no retries.
        return self.grant.client.request(method, url,
            headers={**headers, "Content-Type": "application/json"}, content=wire["body"].encode(),
            follow_redirects=False, timeout=4.0, auth=None)


class _BoundProvider(ScopedSandboxWorkflowProvider):
    def __init__(self, binding, grant, *, principal=None, plan=None):
        self.binding = binding
        self._business_receipt = {"method": "GET", "path": "/developer/v1/business",
            "response_sha256": grant.receipt["business_response_sha256"], "observed_at": grant.observed_at,
            "business_id": binding.config.business_id, "transport_provenance": grant.provenance,
            "token_expires_at": grant.expires_at.isoformat()}
        adapter = _AuthorizedHTTP(binding, grant, principal=principal, plan=plan)
        super().__init__(business_id=binding.config.business_id, access_token=grant.token,
                         granted_scopes=grant.scopes, observed_at=grant.observed_at, http=adapter,
                         transport_provenance=grant.provenance, clock=binding.clock)

    def capabilities(self):
        return {**super().capabilities(), "business_verification": dict(self._business_receipt)}

    def read_object(self, object_type, object_id):
        if object_type != "bills":
            raise WorkflowError("Only bills are enabled")
        record = super().read_object(object_type, object_id)
        finding = self.binding._finding(object_type, object_id)
        if fingerprint(sanitize_bill(record)) != finding["data_provenance"]["record_digest"]:
            raise WorkflowError("Captured bill differs from current native facts; import and reevaluate")
        return record


class NativeBinding:
    def __init__(self, *, workspace, auth, config_path, clock=utcnow):
        self.workspace, self.auth, self.clock = workspace, auth, clock
        self.config_path = Path(config_path)
        self._config_bytes = _protected_bytes(self.config_path)
        try:
            self.config = NativeConfig.model_validate(strict_json(self._config_bytes))
        except (ValueError, TypeError, RampError):
            # Pydantic's default exception includes rejected values, possibly accidental secrets.
            raise WorkflowError("Invalid public native operator configuration") from None
        uuid_text(self.config.business_id)
        self.lock, self._grant, self._report = RLock(), None, None
        reviewers = {}
        for name, key in self.config.reviewers.items():
            if not NAME.fullmatch(name) or set(key) != {"kty", "crv", "x", "y"}:
                raise WorkflowError("Native config accepts only named public P-256 verification keys")
            public = public_bytes(key)
            if auth.account(name) != ("reviewer", public):
                raise WorkflowError("Native reviewer key must match offline workspace enrollment")
            reviewers[name] = WorkflowReviewer(public, simulation_only=False)
        if not reviewers:
            raise WorkflowError("At least one locally provisioned reviewer public key is required")
        realm = mandates.describe(auth.path, next(iter(reviewers)))["workspace_id"]
        self.installation = {"workspace_id": realm, "tenant": self.config.tenant, "business_id": self.config.business_id,
                             "config_sha256": sha256(self._config_bytes).hexdigest()}
        self._guard()
        self._credential_path = ramp_credentials.selected_path()
        self.outbox_path = self.config_path.with_suffix(".outbox.sqlite3")
        if self.outbox_path.resolve() == Path(auth.path).resolve():
            raise WorkflowError("Native outbox must be separate from the authority database")
        if self.outbox_path.exists() or self.outbox_path.is_symlink():
            self._check_outbox()
        self.flow = RampWorkflow(self.outbox_path, tenant=auth.tenant, business_id=self.config.business_id,
                                 finding_resolver=self._finding, reviewers=reviewers, clock=clock,
                                 native_review_reasons=True)
        auth.native_gate = self._release_ready

    def _check_outbox(self):
        p = self.outbox_path
        if (p.resolve() != p or not p.is_file() or p.stat().st_mode & 0o077
                or p.stat().st_uid != os.getuid() or p.stat().st_nlink != 1):
            raise WorkflowError("Native outbox custody is not protected")

    def _release_ready(self):
        return gates.native_install_ready(self.installation)

    def _guard(self):
        if (self.auth.mode != "sandbox" or self.auth.rehearsal or not self._release_ready() or self.config.tenant != self.auth.tenant
                or self.workspace.tenant != self.auth.tenant or self.workspace.mode != "sandbox"):
            raise WorkflowError("Explicit sandbox installation and current security release gate required")
        if _protected_bytes(self.config_path) != self._config_bytes:
            raise WorkflowError("Native operator configuration changed; restart and review again")

    def _business(self):
        _, custody, business = self.workspace._observation()
        if custody != "operator_import" or business != self.config.business_id:
            raise WorkflowError("Current operator-imported observation must match the configured business")
        return business

    def _finding(self, object_type, object_id):
        self._guard()
        self._business()
        finding = self.workspace.record_for_native(object_type, object_id)
        provenance = finding.get("data_provenance", {})
        expected_sources = (["LIVE_RAMP_SANDBOX", "OPERATOR_ATTESTED_CUSTOMER"]
                            if finding.get("native_review_reason") == "ATTESTED_PRICE_EXCEPTION"
                            else ["LIVE_RAMP_SANDBOX"])
        if (object_type != "bills" or finding.get("provider_object_type") != object_type
                or finding.get("provider_id") != object_id or finding.get("business_id") != self.config.business_id
                or finding.get("workspace_tenant") != self.auth.tenant
                or finding.get("sources") != expected_sources
                or provenance.get("freshness") != "FRESH"
                or not re.fullmatch(r"[a-f0-9]{64}", provenance.get("record_digest", ""))):
            raise WorkflowError("An exact factual provider observation is required; synthetic and foreign findings are blocked")
        if not timedelta(0) <= self.clock()-timestamp(finding.get("observed_at")) <= timedelta(hours=24):
            raise WorkflowError("Current actual capture timestamp required")
        if "native_review_reason" not in finding:
            if (finding.get("finding_kind") not in {"NATIVE_OBSERVATION", "UNBOUND_RECORD"}
                    or provenance.get("classification") != "PROVIDER_OBSERVATION"):
                raise WorkflowError("An exact factual provider observation is required")
            return finding
        reason = finding["native_review_reason"]
        if reason == "EVIDENCE_REQUIRED":
            if (finding.get("finding_kind") != "NATIVE_OBSERVATION"
                    or provenance.get("classification") != "PROVIDER_OBSERVATION"
                    or finding.get("outcome") not in {None, "INSUFFICIENT_EVIDENCE"}
                    or finding.get("terms_provenance") is not None):
                raise WorkflowError("Evidence-required reason conflicts with current evidence")
        elif reason == "ATTESTED_PRICE_EXCEPTION":
            terms = finding.get("terms_provenance")
            if (finding.get("finding_kind") != "OPERATOR_PRICE_REVIEW"
                    or provenance.get("classification") != "PROVIDER_WITH_OPERATOR_EVIDENCE"
                    or provenance.get("terms_mode") != "OPERATOR_ATTESTED"
                    or finding.get("outcome") != "ELIGIBLE"
                    or finding.get("stage") not in {"PREPAYMENT_REVIEW", "RETROSPECTIVE_REVIEW"}
                    or finding.get("missing") != []
                    or not isinstance(finding.get("line_findings"), list) or not finding["line_findings"]
                    or not isinstance(terms, dict) or terms.get("mode") != "OPERATOR_ATTESTED"
                    or terms.get("integrity") != "VERIFIED" or terms.get("operator_context_verified") is not True
                    or not isinstance(terms.get("digest"), str)
                    or not re.fullmatch(r"[a-f0-9]{64}", terms["digest"])
                    or not isinstance(provenance.get("binding_digest"), str)
                    or not re.fullmatch(r"[a-f0-9]{64}", provenance["binding_digest"])):
                raise WorkflowError("Current verified operator-scoped price exception evidence required")
        else:
            # INELIGIBLE also covers exclusions and unsupported comparisons. It
            # cannot establish affirmative compliance or a safe-to-approve bill.
            raise WorkflowError("Unsupported native review reason")
        # The trusted workspace recomputes signature, scope, custody, validity and
        # deterministic outcome. Bind that proof independently of its finding hash.
        proof = {key: finding.get(key) for key in (
            "native_review_reason", "terms_provenance", "outcome", "stage", "missing", "line_findings")}
        proof["data_provenance"] = {key: provenance.get(key) for key in (
            "classification", "freshness", "record_digest", "binding_digest", "terms_mode")}
        finding = dict(finding, native_review_digest=digest(proof))
        return finding

    def _current_grant(self, grant=None):
        grant = grant or self._grant
        if grant is None or grant is not self._grant or self.clock() >= grant.expires_at:
            raise WorkflowError("Run provider preflight and prepare a current plan")
        return grant

    def preflight(self):
        self._guard()
        self._business()
        self.close()
        client = _client()
        self._report = {"origin": ORIGIN, "environment": "sandbox", "requested_scopes": sorted(SCOPES),
                        "granted_scopes": None, "observed_at": self.clock().isoformat(),
                        "comment_ready": False, "business_verified": False, "scope_receipt": "UNAVAILABLE"}
        try:
            data = _response(client, "POST", "/developer/v1/token", headers={
                "Authorization": "Basic " + _credentials(self._credential_path), "Content-Type": "application/x-www-form-urlencoded"},
                content=urlencode({"grant_type": "client_credentials", "scope": " ".join(sorted(SCOPES))}).encode())
            token, scope, expires = data.get("access_token"), data.get("scope"), data.get("expires_in")
            if (not isinstance(token, str) or not token or any(c.isspace() for c in token)
                    or str(data.get("token_type", "")).lower() != "bearer"
                    or not isinstance(scope, str) or type(expires) is not int or expires <= 0
                    or any(not re.fullmatch(r"[a-z_]+:(read|write)", s) for s in scope.split())):
                raise WorkflowError("Explicit token scope and expiration receipt required")
            granted = frozenset(scope.split())
            observed = self.clock()
            # A protocol harness cannot produce LIVE provenance, including through this real adapter.
            provenance = "MOCK_HTTP" if isinstance(client._transport, httpx.MockTransport) else "LIVE_RAMP_SANDBOX"
            self._report = {"origin": ORIGIN, "environment": "sandbox", "requested_scopes": sorted(SCOPES),
                "granted_scopes": sorted(granted), "missing_scopes": sorted(SCOPES-granted),
                "unexpected_scopes": sorted(granted-SCOPES), "observed_at": observed.isoformat(),
                "transport_provenance": provenance, "comment_ready": False, "business_verified": False,
                "scope_receipt": "TOKEN_RESPONSE"}
            if not READ_SCOPES <= granted or not granted <= SCOPES:
                return self.status()
            business = _response(client, "GET", "/developer/v1/business", headers={
                "Authorization": "Bearer " + token, "Accept": "application/json"})
            if business.get("id") != self._business() or business.get("active") is not True:
                raise WorkflowError("Controlled token business GET does not match the active installation")
            self._report.update(business_id=business["id"], business_verified=True,
                                business_response_sha256=digest(business), comment_ready=granted == SCOPES)
            self._grant = _Grant(client, token, granted, observed.isoformat(),
                observed + timedelta(seconds=min(expires, 900)), dict(self._report), provenance)
            return self.status()
        finally:
            if self._grant is None:
                client.close()

    def status(self):
        self._guard()
        return {"enabled": True, "tenant": self.auth.tenant, "business_id": self.config.business_id,
                "preflight": self._report, "grant_current": self._grant is not None and self.clock() < self._grant.expires_at,
                "allowed_actions": ["bill.comment.create"], "metadata": "DISABLED_NO_VERIFIED_TRIGGER_CHAIN",
                "actual_money_prevented": None, "actual_recovery": None}

    def _provider(self, **kwargs):
        return _BoundProvider(self, self._current_grant(), **kwargs)

    def prepare(self, object_type, object_id):
        self._guard()
        plan = self.flow.prepare_comment(object_type, object_id, provider=self._provider())
        return self.get(plan["id"])

    def get(self, action_id):
        self._guard()
        plan = self.flow.get(action_id)
        return {**plan, "wire": wire_for(plan)}

    def review(self, action_id, *, principal, expires_at, proof):
        self._guard()
        self.flow.review(action_id, reviewer=principal.subject, expires_at=expires_at, proof=proof)
        return self.get(action_id)

    def _final_check(self, plan, grant):
        self._guard()
        self._current_grant(grant)
        business = _response(grant.client, "GET", "/developer/v1/business", headers={
            "Authorization": "Bearer " + grant.token, "Accept": "application/json"})
        if business.get("id") != self._business() or business.get("active") is not True:
            raise WorkflowError("Business changed before publication")
        self.flow._check_finding(plan)
        record = _BoundProvider(self, grant).read_object(plan["object_type"], plan["object_id"])
        if remote_state(record, plan["object_id"]) != plan["expected_remote_state"]:
            raise WorkflowError("Native object changed before publication")
        self.flow._check_finding(plan)

    def execute(self, action_id, *, principal, review_digest):
        self._guard()
        plan = self.flow.get(action_id)
        if principal.tenant != self.auth.tenant or principal.role != "reviewer" or review_digest != plan["review_digest"]:
            raise WorkflowError("Exact current review digest and authorized tenant required")
        provider = self._provider(principal=principal, plan=plan)
        self.flow.execute(action_id, provider=provider)
        return self.get(action_id)

    def reconcile(self, action_id):
        self._guard()
        grant = self._current_grant()
        business = _response(grant.client, "GET", "/developer/v1/business", headers={
            "Authorization": "Bearer " + grant.token, "Accept": "application/json"})
        if business.get("id") != self._business() or business.get("active") is not True:
            raise WorkflowError("Current controlled business binding required for reconciliation")
        self.flow.reconcile(action_id, provider=self._provider())
        return self.get(action_id)

    def close(self):
        if self._grant is not None:
            self._grant.client.close()
        self._grant, self._report = None, None


def register_native_binding(app, *, workspace, auth, config_path=None):
    """Root's sole native action mount. None means no routes or provider construction."""
    if config_path is None:
        return None
    binding = NativeBinding(workspace=workspace, auth=auth, config_path=config_path)
    if any(getattr(route, "path", "").startswith("/api/ramp/workflow") for route in app.routes):
        raise WorkflowError("Do not mount the generic workflow API beside the native authorization binding")

    def invoke(actor, fn, *args, **kwargs):
        if actor.tenant != auth.tenant:
            raise HTTPException(403, "Native workspace tenant mismatch")
        try:
            with binding.lock:
                return fn(*args, **kwargs)
        except PermissionError:
            raise HTTPException(403, "Exact independently authorized native action required") from None
        except (RampError, ValueError, KeyError, TypeError, OSError):
            # Never return provider bodies, credential paths, arbitrary workspace exceptions or raw data.
            raise HTTPException(409, "Native action unavailable; inspect current plan, scope report and operator configuration") from None

    @app.get(PREFIX + "/status")
    def status(principal=Depends(auth.actor)):
        return invoke(principal, binding.status)

    @app.post(PREFIX + "/preflight")
    def preflight(body: Empty, principal=Depends(auth.reviewer)):
        return invoke(principal, binding.preflight)

    @app.post(PREFIX + "/prepare")
    def prepare(body: Prepare, principal=Depends(auth.reviewer)):
        return invoke(principal, binding.prepare, body.object_type, body.object_id)

    @app.get(PREFIX + "/actions/{action_id}")
    def get(action_id: str, principal=Depends(auth.actor)):
        return invoke(principal, binding.get, action_id)

    @app.post(PREFIX + "/actions/{action_id}/review")
    def review(action_id: str, body: Review, principal=Depends(auth.reviewer)):
        return invoke(principal, binding.review, action_id, principal=principal, **body.model_dump())

    @app.post(PREFIX + "/actions/{action_id}/execute")
    def execute(action_id: str, body: Execute, principal=Depends(auth.reviewer)):
        return invoke(principal, binding.execute, action_id, principal=principal, **body.model_dump())

    @app.post(PREFIX + "/actions/{action_id}/reconcile")
    def reconcile(action_id: str, body: Empty, principal=Depends(auth.reviewer)):
        return invoke(principal, binding.reconcile, action_id)

    app.state.native_binding = binding
    return binding
