# Decision packet 90 — local recovery, installation revocation and the customer-installation boundary

Sanitized. No credentials, tokens, customer data or private evaluation material.

## Context

Uptime is a single-host, loopback-only FastAPI application with SQLite workspaces. Each workspace database is bound to one tenant and execution mode (`authority_workspace`) and carries a random mandate realm. Reviewer sessions are memory-only (one hour) and die on restart; login and write proofs are single-use, origin-, body- and instance-bound. Signed reviewer mandates (≤24h validity, single use) authorize consequential actions. Native Ramp comment delivery uses a separate outbox database that marks a crash after dispatch as UNCERTAIN and never resends. Model jobs mark RUNNING-at-restart as UNCERTAIN and QUEUED as CANCELLED. Ramp access uses sandbox client-credentials read from an owner-only file; tokens are requested per operation and never persisted. A team decision on hosting and identity (D11) is pending, so no public endpoint, tunnel or hosted deployment is authorized.

Gaps found: no backup/restore; the tenant→Ramp business installation binding is permanent with no revocation; no single operator view of stale captures, interrupted imports, uncertain effects, quarantined webhooks or approaching claim cutoffs.

## Implemented (branch work/operations-90, commit f4826b4)

1. **Backup:** SQLite online backup into a new owner-only directory plus manifest (binding, integrity, case hash-chain status, digest of every table). Credentials, private keys, sessions, host authority stores and the native outbox are excluded and listed.
2. **Fenced restore:** verifies the manifest, writes only a new path (never overwrites, refuses paths inside repositories), requires the expected tenant and mode, then revokes every unused reviewer mandate in the restored copy. If the operator supplies the previous database of the same workspace binding, its issuer, mandate and price-evidence revocations are carried forward. The receipt names the backup time from which external effects must be reconciled against Ramp before new mandates are issued.
3. **Installation revocation:** a terminal owner-only host record keyed by (tenant, business) outside the workspace (same pattern as the accepted local-review authority store). Refresh refuses before any token exchange; import and native preparation refuse; history stays readable. Unsafe store fails closed. Reinstall requires a new workspace. Disabling the Ramp app or rotating its secret remains a human Ramp-admin action.
4. **Health check:** read-only, makes no provider request; reports integrity, case-chain verification, capture staleness and interrupted imports as retryable reads, and UNCERTAIN/DISPATCHING outbox entries and UNCERTAIN model jobs as non-retryable; quarantined webhooks; ELIGIBLE or INSUFFICIENT_EVIDENCE cases whose claim cutoff falls inside a window; config-file custody without reading contents. Exit 2 means operator attention.

Tests: 16 new; five mutations (fence removed, each revocation check removed, carry-forward faked) are each caught. 972 existing Ramp/route/tenant/release tests plus the new ones pass.

## Proposed (not implemented; depends on D11)

Customer OAuth install: authorization code with single-use `state` bound to the operator session, tenant and expected business; exact registered HTTPS redirect; code exchange server-side; access tokens memory-only; refresh token encrypted in a managed secret store keyed by installation; single-flight refresh (Ramp refresh tokens do not rotate per its public guide); uninstall = host revocation first, then provider token revocation, then secret deletion; reinstall creates a new installation record. Optional: revoke each client-credentials token (10-day lifetime per Ramp's guide) at the end of an operator refresh.

## Alternatives considered

- Plain file copy restore: preserves everything, but resurrects consumed single-use authority and later-revoked keys.
- Refuse restore unless the previous database is readable: safest, but useless after real data loss.
- In-database installation flag: simpler, but restoring an older snapshot silently re-enables provider access.
- Automatic bounded read retries in the provider client: convenient, but changes request counts in shared code; current choice keeps reads operator-rerun and idempotent.

## Recommendation and strongest counterargument

Keep the fenced restore, host-level installation revocation and read-only health check; defer OAuth implementation to D11. Strongest objection: the host store and carry-forward do not protect against an administrator who replaces all local state, and revocations other than installations can still be lost when the previous database is unavailable. The local administrator remains a trust root.

## Questions

Rank the alternatives. Is revoking all unused mandates on restore sufficient, excessive or incomplete? Is a terminal installation revocation the right default? What falsification tests are missing? What must stay a human or team decision?
