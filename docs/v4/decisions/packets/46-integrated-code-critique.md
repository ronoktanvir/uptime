# Independent implementation critique after integration
Inspect concrete public repository code below. No customer data, provider record, credentials, private evaluation fixture or response is included. You are an independent critic, not the implementer. Prior reviews evaluated architecture, now review actual code. Correctness over favorable certification.

Scope is single-host sandbox. Baseline vs pinned corrected source genuinely measured 73 pass/45 fail to 118 pass. Broader suite awaiting final source-stable run. Model-produced fourth synthetic public SLA is now accepted after generic compiler extensions; its first frozen outcomes failed and independent private witness still tests real bindings. User requires general new vendor and new denial outcomes, actual human promotion, and native financial ownership. Reports acknowledge bounded supported grammar, lack of installed OAuth customer distribution, missing app native write scope, zero provider credits and zero real recovery. Never infer a production-readiness or completed external-effect claim from fixtures.

Find the highest severity reproducible security/financial/source problems, and distinguish them from incomplete capabilities and false-positive critiques. Consider evidence gaps, publication of only neutral vs guarded price exceptions, source revocation during delivery, read-before-write races, native exact request/reply verification, customer overlay equality, registry local draft isolation, monetary caps, arbitrary narrative parsing, and blinded evaluation leakage. Identify focused falsifiers. Interpret a source excerpt as partial and avoid claiming absent guards exist nowhere. Recommend the next correction only when concrete. Do not approve any external effect.


## uptime/auth.py require_gate

    def require_gate(self, path=""):
        if self.draft_path(path):
            return
        if path.startswith("/api/ramp/native/") and self.native_gate is not None:
            if self.native_gate():
                return
            raise HTTPException(403, "Native installation release has expired or changed")
        if not self.approvals_enabled or (self.local_gate is not None and not self.local_gate()):
            raise HTTPException(403, "Consequential actions are disabled in this deployment")


## uptime/auth.py challenge

    def challenge(self, request: Request, body: ChallengeRequest):
        self.require_origin(request)
        login = body.path == "/api/auth/login"
        session = ""
        if not login:
            self.require_gate(body.path)
            p = self.actor(request)
            if p.role != "reviewer" or p.subject != body.subject:
                raise HTTPException(403, "Named reviewer required")
            if (not body.path.startswith("/api/") or body.path.startswith("/api/auth/")
                    or any(c in body.path for c in "?#\\") or not re.fullmatch(r"[a-f0-9]{64}", body.body_sha256)):
                raise HTTPException(400, "A reviewer proof must name one exact API action and body digest")
            session = self.session_id(request)
        elif body.body_sha256:
            raise HTTPException(400, "Invalid login challenge")
        with self.lock:
            self.prune()
            if len(self.challenges) >= 2048:
                raise HTTPException(429, "Too many pending challenges")
            nonce = secrets.token_urlsafe(32)
            expires = int(time()) + TTL
            message = json.dumps(["uptime-v4", self.instance, self.origin, self.tenant, self.mode, self.rehearsal,
                                  body.subject, session, "POST", body.path, body.body_sha256,
                                  self.revision, expires, nonce], separators=(",", ":"))
            self.challenges[nonce] = Challenge(body.subject, body.path, body.body_sha256, session,
                                               self.revision, expires, message)
        return {"challenge": nonce, "message": message, "algorithm": "ES256"}


## uptime/auth.py reviewer

    async def reviewer(self, request: Request):
        self.require_origin(request)
        self.require_gate(request.scope["raw_path"].decode("ascii"))
        principal = self.actor(request)
        if principal.role != "reviewer" or request.method != "POST" or request.url.query:
            raise HTTPException(403, "An exact reviewer POST is required")
        path = request.scope["raw_path"].decode("ascii")
        body_hash = digest(await request.body())
        proved, tag = self.consume(request.headers.get("x-uptime-challenge", ""), request.headers.get("x-uptime-proof", ""),
                                    path, body_hash, self.session_id(request))
        session = self.sessions.get(self.session_id(request))
        if not session or proved != principal or session.key_tag != tag:
            raise HTTPException(403, "Reviewer account changed during authorization")
        if self.draft_path(path) and (not self.approvals_enabled or (self.local_gate is not None and not self.local_gate())):
            return DraftReviewer(principal.tenant, principal.subject, principal.role)
        if self.rehearsal:
            if self.tenant != TENANT:
                raise HTTPException(403, "Scripted actions require the isolated fixture tenant")
            return principal
        try:
            fixture_replay = self.mode == "replay" and self.tenant == TENANT
            claimed = mandates.claim(self.path, principal, path, body_hash, self.instance, required=not fixture_replay)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        if claimed:
            return AuthorizedReviewer(principal.tenant, principal.subject, principal.role, claimed.mandate_id,
                                      claimed.ticket, claimed.claim_decision, claimed.credit_decision)
        return principal


## uptime/vendor_registry.py install

def install(path, p, vendor, body):
    with transaction(path, p, vendor, write=True, draft=True) as db:
        old = _tail(db, p, vendor, required=False)
        state = _fresh(old, vendor)
        try:
            intake = Intake.model_validate(body)
            manifest, extraction = staged_extraction(intake.document)
            overlay = bind_overlay(manifest, intake.overlay)
        except (ValueError, OSError, TypeError, OverflowError) as exc:
            # Retain a safe digest and error category, never echo malformed/private raw inputs.
            state.update(state='QUARANTINED', outcome=Outcome.UNSUPPORTED.value, rejected_digest=sha256(json.dumps(body, sort_keys=True, allow_nan=True).encode()).hexdigest(),
                         reason='Invalid intake schema.' if isinstance(exc, ValidationError) else str(exc)[:240])
            if old and old.get('rejected_digest') == state['rejected_digest'] and old['state'] == 'QUARANTINED':
                return _view(db, p, vendor, old)
            _event(db, p, vendor, state, 'Quarantined intake; dispatch suspended')
            return _view(db, p, vendor, state)
        version = candidate_version(manifest, overlay, extraction)
        if old and old['version'] == version:
            return _view(db, p, vendor, old)
        artifact = {'semantics_revision':semantics_revision(manifest),'manifest': manifest, 'overlay': overlay, 'extraction': extraction, 'source_text': intake.document.text,
                    'generated_tests': generated_checks(manifest), 'source_received_at': now()}
        if not _artifact(db, p, vendor, version):
            db.execute('INSERT INTO v4_vendor_artifact VALUES(?,?,?,?)', (p.tenant, vendor, version, encode(artifact)))
        if old and old['active_version']:
            prior = _artifact(db, p, vendor, old['active_version'])
            if _compatible(prior,old['active_version']) and prior['manifest'] == manifest and prior['overlay'] == overlay:
                state['previous'] = old['active_version']
                state['previous_suite'] = old['suite']
        state.update(version=version, vendor=manifest['vendor'],
                     interpretation_required=extraction.get('method') == 'tool_free_model_propositions',
                     interpretation_reviewer=None)
        _event(db, p, vendor, state, 'Imported public document and separate tenant overlay')
        state.update(state='VALIDATED')
        _event(db, p, vendor, state, 'Validated source coverage, typed thresholds and governing dates')
        state.update(state='SHADOW')
        _event(db, p, vendor, state, 'Shadow only; waiting for independent reviewer cases')
        return _view(db, p, vendor, state)


## uptime/vendor_registry.py shadow_preview

def shadow_preview(path, p, vendor, submission):
    with transaction(path, p, vendor, draft=True) as db:
        state = _tail(db, p, vendor)
        if state["revision"] != submission.revision or state["state"] != "SHADOW":
            raise ValueError("Preview requires the current shadow revision.")
        artifact = _require_current(db, p, vendor, state["version"])
        result = evaluate(artifact["manifest"], artifact["overlay"], submission.facts, p.tenant)
        return {"classification":"LOCAL_DRAFT_PREVIEW", "dispatch_authorized":False,
                "vendor_id":vendor, "revision":state["revision"], "evaluation":result}


## uptime/ramp_workspace.py record_for_native

    def record_for_native(self,object_type,object_id):
        snapshot,custody,business = self._observation()
        if (self.mode != "sandbox" or custody != "operator_import" or business is None
                or snapshot is None or object_type != "bills"):
            raise PermissionError("A current installed sandbox bill observation is required")
        now=datetime.now(UTC)
        observed=datetime.fromisoformat(snapshot["observed_at"])
        completed=datetime.fromisoformat(snapshot["completed_at"])
        if not observed <= completed <= now <= observed+timedelta(hours=24):
            raise PermissionError("Capture expired or after the decision clock")
        bindings, _ = self._bindings(snapshot, custody, business)
        actual = tuple(b for b in bindings if b.object_id == object_id and b.terms_mode == "OPERATOR_ATTESTED")
        if actual:
            reviewed = next((r for r in evaluate_snapshot(snapshot, bindings=actual, as_of=now)
                             if r["provider_object_type"] == object_type and r["provider_id"] == object_id), None)
            if (reviewed and reviewed["data_provenance"]["classification"] == "PROVIDER_WITH_OPERATOR_EVIDENCE"
                    and reviewed["native_status"] == "OPEN" and reviewed["outcome"] == "ELIGIBLE"
                    and reviewed["amount"] is not None and Decimal(reviewed["amount"]) > 0):
                return dict(reviewed, workspace_tenant=self.tenant,business_id=business,observed_at=snapshot["observed_at"],
                            capture_mode=custody, native_review_reason="ATTESTED_PRICE_EXCEPTION",
                            price_outcome="PRICE_EXCEPTION", terms_provenance={
                                "mode":"OPERATOR_ATTESTED","integrity":"VERIFIED","operator_context_verified":True,
                                "digest":actual[0].terms_evidence_digest})
        rows=evaluate_snapshot(snapshot, as_of=completed)
        for record in rows:
            if record["provider_object_type"]==object_type and record["provider_id"]==object_id:
                if (record["sources"] != [Source.RAMP.value] or record["amount"] is not None
                        or record["data_provenance"]["classification"] != "PROVIDER_OBSERVATION"):
                    raise PermissionError("Native informational review requires a factual observation")
                return dict(record, workspace_tenant=self.tenant,business_id=business,observed_at=snapshot["observed_at"],
                            finding_kind="NATIVE_OBSERVATION", capture_mode=custody, native_review_reason="EVIDENCE_REQUIRED")
        raise KeyError(object_id)


## uptime/ramp_native_binding.py _finding

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


## uptime/ramp_native_binding.py _final_check

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


## uptime/ramp_award_attribution.py _dispatch

    def _dispatch(self, db, claim_id):
        """Read both physical schemas; v1 versioned hashes are never v2 keys.

        Normalize proven history in memory only. A migrated copy coalesces with
        its original; different owners of one canonical obligation fail closed.
        No registry tables, receipts, locks, or migrations are written here.
        """
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        filings = {}
        try:
            for table in (claim_identity.TABLE, "claim_dispatch_identity"):
                if table not in tables:
                    continue
                for saved in db.execute(f"SELECT * FROM {table} WHERE step='initial'"):
                    row = dict(saved)
                    economic = json.loads(row["identity"]) if table == claim_identity.TABLE else None
                    if economic is not None:
                        if not isinstance(economic, list) or len(economic) != 7:
                            fail("INVALID_LOCAL_FILING")
                        if economic[0] != self._config.tenant:
                            continue
                    else:
                        # v1 omitted tenant; resolve it from the stored scope/case.
                        local = json.loads(row["scope"])
                        owner = local.get("tenant")
                        if row["route"] == "correspondence" and "inbox_claim" in tables:
                            owners = [r[0] for r in db.execute("SELECT tenant,scope FROM inbox_claim WHERE id=?", (row["case_id"],))
                                      if json.loads(r[1]) == local]
                            if len(owners) != 1:
                                fail("HISTORICAL_FILING_UNRESOLVED")
                            owner = owners[0]
                        if owner is None:
                            fail("HISTORICAL_FILING_UNRESOLVED")
                        if owner != self._config.tenant:
                            continue
                    identity, receipt = self._local_filing(db, row, tables)
                    if identity is not None:
                        proven = claim_identity._economic(**identity)
                        if economic is not None and economic != proven:
                            fail("LOCAL_FILING_SCOPE_CONFLICT")
                        if economic is None and row["obligation"] != claim_identity._v1_key(identity):
                            fail("LOCAL_FILING_SCOPE_CONFLICT")
                        economic = proven
                    if economic is None:
                        fail("HISTORICAL_FILING_UNRESOLVED")
                    identity_check = dict(tenant=economic[0], vendor=economic[1], account=economic[2],
                        agreement_id=economic[3], service=economic[4], month=economic[5], remedy=economic[6],
                        agreement_version="excluded-from-v2-identity")
                    if claim_identity._economic(**identity_check) != economic:
                        fail("INVALID_LOCAL_FILING")
                    key = claim_key(**identity_check)
                    if table == claim_identity.TABLE and row["obligation"] != key:
                        fail("LOCAL_FILING_SCOPE_CONFLICT")
                    normalized = {k: row[k] for k in ("step", "route", "case_id", "packet_digest", "receipt_id")}
                    normalized.update(obligation=key, scope=canonical_json(json.loads(row["scope"])),
                                      at=_time(row["at"]), identity=economic, receipt=receipt,
                                      contract_version=identity["agreement_version"] if identity else None)
                    old = filings.get(key)
                    if old is not None and old != normalized:
                        fail("CANONICAL_FILING_CONFLICT")
                    filings[key] = normalized
            # An older writer may append receipts after the v2 migration. Do
            # not overlook an unindexed second filing just because v2 exists.
            indexed = {(r["route"], r["case_id"], r["receipt_id"]) for r in filings.values()}
            for table, route in (("inbox_claim", "correspondence"), ("dispute_cases", "legacy")):
                if table in tables:
                    for case, raw in db.execute(f"SELECT id,state FROM {table} WHERE tenant=?", (self._config.tenant,)):
                        for receipt in json.loads(raw)["submissions"]:
                            if receipt["action"] == "submit-claim" and (route, case, receipt["id"]) not in indexed:
                                fail("UNINDEXED_HISTORICAL_FILING")
            if "dispute_receipts" in tables:
                for case, rid in db.execute("SELECT case_id,id FROM dispute_receipts WHERE tenant=? AND action='submit-claim'",
                                            (self._config.tenant,)):
                    if ("legacy", case, rid) not in indexed:
                        fail("UNINDEXED_HISTORICAL_FILING")
            rows = [r for r in filings.values() if r["case_id"] == claim_id]
            if len(rows) != 1:
                fail("PREEXISTING_LOCAL_FILING_REQUIRED")
            return rows[0]
        except AttributionError:
            raise
        except (sqlite3.DatabaseError, KeyError, TypeError, ValueError, IndexError):
            fail("INVALID_LOCAL_FILING")


## uptime/ramp_award_attribution.py _filing_scope

    def _filing_scope(self, dispatch, body, issued_at):
        s = body.scope
        try:
            expected = claim_key(tenant=self._config.tenant, vendor=s.vendor_name, account=s.account_id,
                                 agreement_id=s.contract_id, agreement_version=s.contract_version,
                                 service=s.service_name, month=s.month, remedy=s.remedy)
        except ValueError:
            fail("LOCAL_FILING_SCOPE_CONFLICT")
        local = json.loads(dispatch["scope"])
        required = dict(account=s.account_id, vendor=s.vendor_name, contract=body.local_contract_id,
                        service=s.service_name, currency=s.currency, month=s.month)
        if dispatch["route"] == "legacy":
            # This historical wire format has no local contract alias or currency.
            required = dict(account=s.account_id, vendor=s.vendor_name, product=s.service_name, month=s.month)
            if body.local_contract_id != s.contract_id or s.currency != "USD" or s.minor_unit_conversion_rate != 100:
                fail("LOCAL_FILING_SCOPE_CONFLICT")
        # Human-readable labels share the registry's NFC/casefold semantics.
        for k in ("vendor", "service", "product"):
            if k in required and k in local:
                local[k], required[k] = claim_identity._label(local[k]), claim_identity._label(required[k])
        if (dispatch["obligation"] != expected or any(local.get(k) != v for k, v in required.items())
                or dispatch["contract_version"] not in (None, s.contract_version)):
            fail("LOCAL_FILING_SCOPE_CONFLICT")
        if dispatch["at"] > issued_at:
            fail("FILING_MUST_PREEXIST_REGISTRATION")
        if self._config.evidence_mode == "ACTUAL_NATIVE":
            witness = body.external_filing
            if dispatch["route"] != "historical-receipt" or witness is None or witness.evidence_mode != "ACTUAL_EXTERNAL":
                fail("ACTUAL_EXTERNAL_FILING_REQUIRED")
            fact = dispatch["receipt"]
            receipt = fact["body"]
            if (witness.receipt_id != receipt["receipt_id"] or witness.receipt_sha256 != digest(fact)
                    or witness.received_at != _time(receipt["received_at"])
                    or witness.submitted_to != receipt["submitted_to"]):
                fail("EXTERNAL_FILING_WITNESS_CONFLICT")
            if _time(fact["received_at"]) > issued_at:
                fail("FILING_MUST_PREEXIST_REGISTRATION")


## uptime/claim_identity.py _backfill

def _backfill(db, tenant):
    """Use stored submissions only. Incomplete/conflicting history closes dispatch.

    No migration-complete flag: receipts appended by an older writer remain visible
    on the next transaction. Both runtime routes still must reserve before sending.
    """
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    old = {}
    if "claim_dispatch_identity" in tables:
        old = {r[6]: tuple(r) for r in db.execute("SELECT obligation,step,route,case_id,scope,packet_digest,receipt_id,at FROM claim_dispatch_identity")}
    migrated = set()
    try:
        legacy = {}
        if "dispute_receipts" in tables:
            for rid, case_id, action, body in db.execute(
                    "SELECT id,case_id,action,body FROM dispute_receipts WHERE tenant=?", (tenant,)):
                r = json.loads(body)
                if r["id"] != rid or r["action"] != action:
                    raise ValueError("Conflicting historical receipt metadata.")
                legacy[rid] = (case_id, r)
        if "dispute_cases" in tables:
            for case_id, raw in db.execute("SELECT id,state FROM dispute_cases WHERE tenant=?", (tenant,)):
                state = json.loads(raw)
                for r in state["submissions"]:
                    saved = legacy.get(r["id"])
                    if saved is not None and saved != (case_id, r):
                        raise ValueError("Historical state and receipt disagree.")
                    legacy[r["id"]] = (case_id, r)
        initial_by_case = {}
        for case_id, r in sorted(legacy.values(), key=lambda item: item[1]["action"] != "submit-claim"):
            payload = r["payload"]
            identity, scope = _legacy(payload)
            if identity["tenant"] != tenant or r["action"] not in {"submit-claim", "submit-response"}:
                raise ValueError("Historical legacy scope is not established.")
            parent = None
            if r["action"] == "submit-response":
                parent = initial_by_case[case_id]
            _reserve(db, identity=identity, route="legacy", case_id=case_id, scope=scope,
                     initial_receipt_id=parent, historical=True, **_receipt(r, payload))
            if parent is None:
                initial_by_case[case_id] = r["id"]
            migrated.add(r["id"])
        if "inbox_claim" in tables:
            for case_id, raw_scope, raw_state in db.execute(
                    "SELECT id,scope,state FROM inbox_claim WHERE tenant=?", (tenant,)):
                scope, state = json.loads(raw_scope), json.loads(raw_state)
                parent = None
                for r in state["submissions"]:
                    packet = r["packet"]
                    if packet["tenant"] != tenant or packet["claim"] != case_id or packet["scope"] != scope:
                        raise ValueError("Historical inbox scope is not established.")
                    existing = db.execute(f"SELECT obligation,step,route,case_id,scope,packet_digest,receipt_id,at,identity "
                                          f"FROM {TABLE} WHERE receipt_id=?", (r["id"],)).fetchone()
                    route = "correspondence"
                    predecessor = parent
                    if existing and existing[2] == "historical-receipt":
                        route = "historical-receipt"
                        predecessor = _historical_parent(db, tenant, case_id, scope, state, r, existing)
                    else:
                        if r["action"] != ("submit-response" if parent else "submit-claim"):
                            raise ValueError("Historical inbox step is not established.")
                        if parent is not None and packet.get("in_reply_to") != parent:
                            raise ValueError("Historical supplement has no matching original receipt.")
                    identity = dict(tenant=tenant, vendor=scope["vendor"], account=scope["account"],
                                    agreement_id=packet["agreement_id"], agreement_version=packet["version"],
                                    service=scope["service"], month=scope["month"], remedy="availability")
                    if existing:
                        identity["remedy"] = json.loads(existing[8])[-1]
                    elif _label(scope["vendor"]) != "twilio":
                        # Older generic packets omitted remedy. Only the old stored
                        # reservation hash can establish which supported remedy it used.
                        candidates = ["availability", "resource-month/" + scope["component"]]
                        matches = [value for value in candidates if r["id"] in old and
                                   _v1_key(identity | {"remedy": value}) == old[r["id"]][0]]
                        if len(matches) != 1:
                            raise ValueError("Historical remedy is unknown; manual reconciliation required.")
                        identity["remedy"] = matches[0]
                    checked = _receipt(r, packet)
                    if existing:
                        expected = (claim_key(**identity), "supplement" if predecessor else "initial", route,
                                    case_id, _json(scope), checked["packet_digest"], checked["receipt_id"],
                                    _instant(checked["at"]), _json(_economic(**identity)))
                        if tuple(existing[:7]) + (_instant(existing[7]), existing[8]) != expected:
                            raise ValueError("Canonical inbox reservation and approved receipt disagree.")
                    _reserve(db, identity=identity, route=route, case_id=case_id, scope=scope,
                             initial_receipt_id=predecessor, historical=True, **checked)
                    if r["id"] in old:
                        row = old[r["id"]]
                        expected = (_v1_key(identity), "supplement" if parent else "initial", "correspondence",
                                    case_id, _json(scope), r["digest"], r["id"])
                        if row[:7] != expected or _instant(row[7]) != _instant(r["at"]):
                            raise ValueError("Historical reservation and receipt disagree.")
                    parent = parent or r["id"]
                    migrated.add(r["id"])
        for rid, row in old.items():
            if rid not in migrated:
                # v1 has no tenant column. An unattributable row cannot be safely ignored.
                row_scope = json.loads(row[4])
                if row_scope.get("tenant") not in (None, tenant):
                    continue
                if row[2] == "correspondence" and "inbox_claim" in tables:
                    owners = [owner for owner, raw_scope in db.execute(
                        "SELECT tenant,scope FROM inbox_claim WHERE id=?", (row[3],))
                        if json.loads(raw_scope) == row_scope]
                    if owners and all(owner != tenant for owner in owners):
                        continue
                raise ValueError("Unresolved historical reservation requires manual reconciliation.")
    except (KeyError, TypeError, IndexError, json.JSONDecodeError) as error:
        raise ValueError("Incomplete historical claim evidence requires manual reconciliation.") from error
