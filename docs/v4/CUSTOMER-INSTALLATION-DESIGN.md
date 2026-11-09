# Customer installation design (proposed; blocked on D11)

**Status: proposal only.** No OAuth authorization-code code, callback route, token store or public listener exists, and none is authorized until the team records D11 (hosting, identity owner, key custody) and D10 (data disclosure). The current product uses operator-held sandbox client credentials on one loopback host. [Local operations and trust boundary](OPERATIONS-RECOVERY-90.md) · [Decision 96](decisions/ADR-0096-operations-recovery.md)

## Provider facts this design relies on

From Ramp's public developer guide ([llms-guides](https://docs.ramp.com/llms-guides.txt), retrieved November 9, 2026). None of these has been exercised against the sandbox; verify each with a read-only sandbox check before implementation.

- Authorize at `https://demo.ramp.com/v1/authorize` (sandbox) with `response_type=code`, `client_id`, `redirect_uri`, `scope` and `state`. `state` is required for apps created after June 15, 2023. PKCE is not documented.
- The redirect URI must exactly match a registered URI and use HTTPS, or plain HTTP only for `localhost`/`127.0.0.1`. Codes expire after 5 minutes.
- The token endpoint is `/developer/v1/token` with HTTP Basic client authentication. Authorization-code access tokens default to 1 hour; use `expires_in`. Client-credentials tokens last 10 days.
- Refresh must be enabled for the app. The refresh response carries a new access token and **the same refresh token** (no rotation). `refresh_token_expires_in` appears only if configured.
- Revoke with `POST /developer/v1/token/revoke` and Basic authentication; it returns HTTP 200.
- No disconnect or uninstall webhook is documented.

## Installation flow

1. **Start.** A signed-in operator with installation authority starts an installation for one tenant. The server creates an installation intent containing:
   - a random 256-bit `state`, stored only as a hash;
   - the operator subject and session binding;
   - the tenant;
   - the exact registered redirect URI;
   - the exact approved scope set;
   - an expiry of 10 minutes or less.

   Only the approved scopes are requested. A grant the team already approved is never re-requested from an administrator as a new decision.
2. **Callback.** The HTTPS route checks the state once, in constant time, against the same operator session, tenant and unexpired intent, then consumes it. Errors and denials render a generic page and never echo provider parameters. Responses are `no-store` and carry no `Referer`.
3. **Exchange.** The server exchanges the code with the client secret read from a managed secret store. It accepts the response only if the token type is `bearer`, the granted scope is a subset of the requested scope, and every required scope is present. Missing required scopes mark the installation `DEGRADED`; there is no automatic re-prompt.
4. **Bind.** With `business:read` only, the server reads the business and binds `(tenant, business)` exactly once. A business already bound to another tenant, or a business that differs from an operator-declared expectation, is refused. The existing `native_installation` uniqueness and the host revocation store are reused. A revoked `(tenant, business)` cannot be reinstalled into the same workspace.
5. **Store.** The refresh token is encrypted under a managed key, keyed by installation ID, and is never readable by the web process's log pipeline. Access tokens live in memory only, with expiry from `expires_in`. Audit events record installation ID, scopes, actor and timestamps, never token material.

## Refresh

- Refresh is single-flight per installation behind a lease in the durable job store, started before expiry.
- Transport failures and HTTP 429/5xx: bounded retry (at most 3, with backoff).
- `invalid_grant` or HTTP 401: the installation becomes `NEEDS_REAUTHORIZATION`, operator-visible, with no retry loop.
- If Ramp ever returns a different refresh token, replace it atomically and log only that a rotation happened.
- Remote disconnects are not announced, so a periodic `business:read` validity check detects them.

## Uninstall and revocation (order matters)

1. Write the host revocation record. Local access stops at once; this is implemented now.
2. Stop and cancel the installation's queued jobs, and leave in-flight external effects as `UNCERTAIN` for reconciliation.
3. Call the token revocation endpoint for the refresh token and any live access tokens. On a timeout, retry the revocation a bounded number of times and report `REVOCATION_UNCONFIRMED`.
4. Delete the encrypted token material.
5. Apply the D10 retention and deletion policy to the tenant's records. Financial audit history is not silently erased.

## Callbacks and webhooks

- Exact registered paths, HTTPS only, no open redirects and request-size limits.
- Webhook secrets are stored per installation in the managed store.
- The existing `RampWebhookInbox` already provides raw-body HMAC verification, ID deduplication, conflict quarantine, out-of-order marking and acceptance windows. Its verification challenge is completed by a root-operated transport.
- A webhook never grants financial or action authority; it only queues a read.

## Acceptance tests required before enabling

- A forged, replayed, expired or cross-session `state` is refused.
- A code replayed after exchange fails.
- Requested scopes equal the approved set exactly.
- A business bound to another tenant is refused.
- Concurrent refreshes produce one provider call.
- `invalid_grant` leads to `NEEDS_REAUTHORIZATION`.
- Uninstall refuses access before any provider call, and revocation is called and audited.
- Restart and restore cannot reopen a revoked installation (already covered locally).
- Token material is absent from logs, the database, backups and Git.
- One tenant cannot read another's installation or records.

## Decisions this depends on

| Item | Needs |
| --- | --- |
| Public callback and webhook hosting, managed identity, secret store | D11 |
| What tenant data may leave the installation, and retention after uninstall | D10 |
| Whether uninstall also cancels in-flight claims or disputes with vendors | D08 |
| Which Ramp records carry native findings | D02 |

A loopback redirect URI is allowed by Ramp for development. It does not make a customer installation: it would run on one person's machine with that machine's administrator as the trust root.
