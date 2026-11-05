# Authenticated native bill comments

This binding publishes only a fixed informational comment on an exact sandbox bill. It requires a current factual observation, an unchanged current bill, a named reviewer's two signatures, and an independent mandate for the exact outbound HTTP bytes. It does not approve, reject, prevent payment, assert contractual entitlement, or report recovered money. Blank Canvas metadata is disabled because this installation has no genuine verified trigger chain. The existing workflow/webhook modules remain the implementation boundary for any later separately reviewed metadata integration.

The implementation uses `RampWorkflow` and `ScopedSandboxWorkflowProvider.post_comment()` from `uptime/ramp_workflow.py`, and canonicalization/time utilities from `uptime/ramp_webhooks.py`. It adds authorization inside the provider's injected HTTP adapter. There is no direct provider command in the operator CLI.

## Root registration and configuration

Root owns `uptime/server.py`, `scripts/serve.py`, and `uptime/ramp_workspace.py`; this change does not edit them. Add an explicit optional `native_config: Path | None = None` application argument and launcher `--native-config` option, passing the operator's value through unchanged. After creating the existing `Authority` and registering the Ramp workspace:

```python
from uptime.ramp_native_binding import register_native_binding

register_native_binding(app, workspace=ramp_workspace, auth=auth,
                        config_path=native_config)
```

Use the existing workspace and Authority instances. Do not also mount `register_ramp_workflow()` with a live provider. With `config_path=None`, this function installs no routes, creates no HTTP client and reads no credentials. An explicit config still requires sandbox mode, a named non-rehearsal Authority, approvals enabled, matching tenant, enrolled reviewer public keys, and `gates.local_release_ready()`. The release gate is rechecked before each action and at dispatch; its local release attestation does not grant external commercial authority. Root should call `app.state.native_binding.close()` on shutdown when configured.

The operator provisions an absolute physical JSON path outside the repository, in an owner-only directory (0700) and a regular owner-only file (0600). Symlinks and hard-linked files are rejected. Example shape, with actual locally verified public values substituted:

```json
{
  "schema_version": "uptime-native-operator/1",
  "enabled": true,
  "tenant": "your-tenant",
  "business_id": "<canonical sandbox business UUID>",
  "reviewers": {
    "alice.reviewer": {
      "kty": "EC", "crv": "P-256", "x": "<public coordinate>", "y": "<public coordinate>"
    }
  }
}
```

These are public verification keys already enrolled in the same Authority. No private key, provider token, destination, expected scope, synthetic finding or issuer signing credential is accepted in this config. Changes invalidate the running binding and require restart. The independent Ed25519 issuer's public registration and signed mandates use the existing [offline mandate tooling](REVIEWER-MANDATES.md); this binding never enrolls or issues authority.

The outbox lives beside the config, replacing its suffix with `.outbox.sqlite3`, with mode 0600. Preserve it across restarts. It must differ from the Authority database because the workflow holds its dispatch transaction while the final authorization consumes the mandate. A crash can leave `DISPATCHING` or `UNCERTAIN`; retain that state and reconcile it.

Provider credentials remain in the existing protected `~/.config/uptime/ramp-sandbox.json` with exactly `base_url`, `client_id`, and `client_secret`. The server requires `RAMP_ENV=sandbox` and `RAMP_BASE_URL=https://demo-api.ramp.com` (or the latter unset). It reads the credential file only on an authenticated preflight. HTTP uses a fixed TLS sandbox origin, no environment proxies, no redirects and no automatic retries.

## Exact API and workspace shape

All routes use the existing local Authority. GET requires an authenticated session. Every POST requires an exact caller-signed local request, and named non-default tenants also require an installed independent local mandate. The execute POST additionally requires a native effect mandate, even for the default fixture tenant.

| Route | Exact body / result |
|---|---|
| GET `/api/ramp/native/status` | Configuration, current scope receipt and allowed actions; no provider calls |
| POST `/api/ramp/native/preflight` | `{}`; controlled token exchange and exact business GET, no bill mutation |
| POST `/api/ramp/native/prepare` | `{"object_type":"bills","object_id":"<UUID>"}`; current plan and wire artifact |
| GET `/api/ramp/native/actions/{id}` | Persisted plan, delivery state, exact wire artifact and receipt |
| POST `/api/ramp/native/actions/{id}/review` | `{"expires_at":<epoch>,"proof":"<P-256 proof>"}`; subject comes from Authority |
| POST `/api/ramp/native/actions/{id}/execute` | `{"review_digest":"<64 lowercase hex>"}` |
| POST `/api/ramp/native/actions/{id}/reconcile` | `{}`; discussion GET only, never resends |

Extra fields are rejected. The client cannot select business, finding, resolved destination, comment content, provider token, URL or expected scope. Bill IDs must resolve through the current workspace; there is no fallback to another record.

`workspace._observation()` returns `(snapshot, "operator_import", trusted_business_uuid)`. Packaged receipts do not establish a native installation. The binding compares that business with both config and GET `/developer/v1/business` under the controlled token. Root supplies `record_for_native("bills", id)` freshly on each evaluation:

```python
{
    "provider_object_type": "bills", "provider_id": exact_bill_uuid,
    "workspace_tenant": auth.tenant, "business_id": trusted_business_uuid,
    "finding_digest": stable_sha256_of_current_factual_finding,
    "observed_at": actual_capture_timestamp,
    "sources": ["LIVE_RAMP_SANDBOX"],
    "finding_kind": "NATIVE_OBSERVATION",  # UNBOUND_RECORD also accepted
    "data_provenance": {
        "classification": "PROVIDER_OBSERVATION", "freshness": "FRESH",
        "record_digest": fingerprint(captured_sanitized_bill),
    },
}
```

Root recomputes factual findings without synthetic overlays; it must preserve the actual capture time and a digest stable across identical reevaluations. Freshness is checked against the current clock, not an arbitrary client clock. The binding compares `fingerprint(ramp_records.sanitize_bill(current_provider_GET))` to the captured record digest. Thus a recent capture containing outdated amounts or status still fails. The workflow also binds the entire current native object's hash. Both checks run again at execution, with another business read, bill read and finding recomputation immediately before the mutation. Synthetic caps, replay sources, future/stale captures, other tenants and changed findings fail closed.

## Operator procedure

The administrator must separately grant the app `business:read`, `bills:read`, and `bills:write`. Preflight requests exactly these scopes and reports the actual token response. Missing read or write scope prevents publishing; unexpected extra scopes also fail closed. A missing scope field is unavailable evidence, not a grant. A denied token exchange is reported as unavailable, not proof that a particular provider permission is absent. The plan persists the scope receipt and `capabilities.business_verification`: exact GET path, business-response hash, business UUID, observation time, token expiry and transport provenance, without the profile or token. Reconciliation also rechecks the current business by GET. After the administrator changes app scopes, run preflight again and prepare/review a fresh plan; no code change is needed.

1. Provision the named reviewer and independent issuer offline as described in `REVIEWER-MANDATES.md`, then enable the explicit root config only after the release gate passes. The issuer's `native_actions` must include only `bill.comment.create` for this binding and its `business_id` must match the installation. Import the current provider observation through root's existing trusted import path.
2. Stage a preflight or prepare request without network access:

   ```sh
   uv run --locked python scripts/ramp_native_operator.py preflight --stage-file /private/operator/preflight.json
   uv run --locked python scripts/ramp_native_operator.py prepare --object-id BILL_UUID --stage-file /private/operator/prepare.json
   ```

   Each output identifies the exact local path and body SHA-256. The staged document's `body` is encoded using compact UTF-8 JSON, no ASCII escaping, and no NaN. Have the independent issuer sign and install a current local mandate for that path/body, then send the same staged file:

   ```sh
   uv run --locked python scripts/ramp_native_operator.py send --request-file /private/operator/preflight.json --subject alice.reviewer --credential-file /private/operator/alice.json
   ```

   Follow with the separately mandated prepare request. The CLI authenticates and signs the exact local bytes. It cannot substitute a provider call if the API denies the request.
3. Fetch the returned action using `plan --action-id ACTION_ID`, with the same `--subject` and `--credential-file`. Inspect `expected_remote_state`, `finding_digest`, `review_digest`, `body`, `wire` and provenance. `wire` includes method, absolute API path, exact UTF-8 body, body SHA-256 and the derived native effect. It contains no bearer token.
4. Use `review --action-id ACTION_ID --stage-file /private/operator/review.json`, with the reviewer credential arguments. This creates the separate workflow proof, expiring within five minutes, over canonical `['uptime-ramp-review-v1', tenant, business_id, action_id, review_digest, reviewer, expires_at]`. Have the independent issuer install the local review mandate and send this exact file before expiry.
5. Stage `execute --action-id ACTION_ID --review-digest REVIEW_DIGEST --stage-file /private/operator/execute.json`. The independent issuer reviews the native wire artifact and signs a mandate containing both the staged local body hash and `wire.effect`, with an exact business, bill, action, signer, workspace and validity window. Install through `scripts/provision_mandates.py`; the operator then sends the staged execute request. The server stores only public authority material.
6. After any ambiguous response, fetch the action. For `UNCERTAIN` or `DISPATCHING`, use a separately authorized `reconcile --action-id ACTION_ID` (or stage it). This performs only GETs. If the grant expired or the process restarted, preflight can establish a fresh read grant before reconciliation. A missing comment or failed read leaves the action uncertain; neither is permission to post again.

The workflow persists a dispatch reservation before the network attempt. The adapter re-encodes the validated `post_comment()` payload once, compares it with the reviewed wire artifact, calls `mandates.native_effect_from_request()` on the final method/path/bytes, and calls `auth.authorize_native()` at that boundary. It then sends those exact bytes via `content=`, avoiding a second library JSON serialization. Mandate consumption checks expiry, revocation, reviewer, issuer, business, object, operation and byte digest. Native tickets live for at most 60 seconds; only the current authenticated request can use one.

Delivery means the comment's exact ID, message and unique marker were read back from the same bill's paginated discussion. A POST response alone remains uncertain. Foreign pagination, conflicting IDs, duplicate markers and changed messages cannot establish delivery. Provider-side changes can still race the last read: the documented comment API offers no conditional state/version predicate or documented idempotency key. The record carries null `actual_money_prevented` and `actual_recovery` throughout.

## Local validation and provenance

`uv run --locked python scripts/ramp_native_operator.py --rehearsal` creates a disposable outbox, ephemeral keys and a `SimulatedWorkflowProvider`. It loads no provider credentials, opens no HTTP client and reports `SIMULATED_RAMP`. The flag cannot be combined with live operator arguments. It does not satisfy any native release or mandate gate.

`tests/test_ramp_native_binding.py` uses actual Authority challenges, ephemeral P-256 reviewers, separate Ed25519 issuers, protected config files, the real workflow/provider adapter and `httpx.MockTransport`. Socket connections are forbidden. It checks supported JSON wire serialization, same-object receipt, independent native byte authorization, unknown fields, business/scope drift, synthetic/stale/foreign findings, dispatch-time changes, revocation, local signature tampering, direct workflow denial, and restart reconciliation without resend. Its provenance is `MOCK_HTTP`; this is protocol evidence, not a provider execution receipt. No test loads customer captures or real credentials.

The reviewed local official OpenAPI snapshot is `reference/openapi.json`, SHA-256 `2f7d60ff0a94859bd8ae94ac7a688c1a8df60ea281e3ef8f5d061b04b9ae849a`, API title `Ramp Developer API`, version `v1`. It specifies GET `/developer/v1/business` with `business:read`, POST `/developer/v1/comments/{object_type}/{object_id}` with the resource's write scope, `{message, message_format}` and 201 `ApiCommentResource`, and paginated GET for readback. No internet fetch or provider request was made to implement this binding. The schema is a pinned supplied reference, not evidence of current live endpoint behavior.

The genuine Opus 31–36 and 40 replies in `docs/v4/decisions/reviews/` informed the boundary: preserve snapshot/version provenance, prefer comments, reconcile uncertain delivery, verify business/scopes, separate synthetic overlays, and never equate native annotation with prevention or recovery. Those advisory replies do not grant permission or substitute for the schema, scope receipt, current-object checks, independent mandate or real readback.
