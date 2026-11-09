# Installation, recovery and operations — workstream 90

**Status, November 9, 2026:** local controls are implemented and tested on branch `work/operations-90`. Hosted customer installation is **designed, not implemented**: D11 was decided as **stay local for now** (Ronok's decision on November 9, 2026, relayed by the progress-review session; the integration owner is recording it), so it is deferred to a later hosted milestone, not blocked. Nothing here publishes, tunnels or hosts the current local app. [Decision 96](decisions/ADR-0096-operations-recovery.md) · [Customer installation design](CUSTOMER-INSTALLATION-DESIGN.md) · [Test ledger](TEST-CHANGES-90-OPERATIONS.md)

## Actual trust boundary

Uptime runs as one loopback-only process per workspace. The middleware refuses any non-loopback client or a `Host` header that differs from the configured origin. Each SQLite workspace is bound to exactly one tenant and execution mode (`authority_workspace`). Opening it with another tenant or mode fails.

**The local machine administrator is trusted.** That account can read and alter every workspace database, enroll keys, edit host stores, read the Ramp credential file and replace application code. Audit triggers, hash-chained case history, backup checksums and host-side revocation records detect accidental or partial change. They also constrain the browser and the application. They do not protect against this administrator. Do not describe the local deployment as adversarial separation between people, or as a customer SaaS deployment.

| Element | Custody in the current deployment | Never present in |
| --- | --- | --- |
| Ramp sandbox client ID/secret | Owner-only `~/.config/uptime/ramp-sandbox.json`; process reads it at startup; `RAMP_ENV=sandbox` and the exact demo API origin are required | Git, SQLite, backups, logs, model prompts |
| Ramp access tokens | Requested per operation with an exact scope set; memory only | Disk, logs, backups |
| Reviewer private keys | Held by each named reviewer; the server stores public keys only | Server, backups |
| Mandate issuer and source signing keys | External custody; the workspace stores public keys and revocation flags | Server, backups |
| Sessions and challenges | Process memory; one-hour sessions; single-use origin-, body- and instance-bound proofs | Disk; every restart invalidates them |
| Installation revocations | Owner-only host store `~/.config/uptime/installation-revocations/` plus an immutable workspace event | — |
| Local review exception authority | Separate host store `~/.config/uptime/local-review-exceptions/` (decision 88) | — |

Untrusted input: browser content, contract and vendor text, model output, and webhook bodies before signature verification. Restored snapshots are also untrusted until they are fenced and the reconciliation is acknowledged.

**Tenant isolation.** Every financial, case, capture and job query carries the workspace tenant. Workbench routes call `require_tenant`, and a Ramp business can be bound to only one tenant per workspace. Backups keep the binding. A restore requires the expected tenant and mode, and refuses a "previous" database from another binding. Existing controls include `test_nondefault_workspace_has_its_own_authority_and_no_demo_financial_records`, the business-scoped credit tests in `test_ramp_credit_scope_v72.py`, and the new restore and revocation cases in `test_operations_recovery_90.py`.

## Install a local workspace (reproducible)

Use the [run guide](OPERATIONS.md) for prerequisites, enrollment and the sandbox credential file. A complete sandbox installation is:

```sh
umask 077
uv sync --locked
mkdir -p "$HOME/.config/uptime" "$HOME/.local/share/uptime" "$HOME/.local/share/uptime-backups"
chmod 700 "$HOME/.config/uptime" "$HOME/.local/share/uptime" "$HOME/.local/share/uptime-backups"
db="$HOME/.local/share/uptime/workbench-sandbox.sqlite"
uv run --locked python scripts/serve.py --mode sandbox --db "$db" \
  --enroll analyst.one --role viewer --credential-file "$HOME/.config/uptime/analyst-one.json"
export RAMP_ENV=sandbox RAMP_BASE_URL=https://demo-api.ramp.com
uv run --locked python scripts/ramp_refresh_workspace.py --db "$db" --attempts 2
uv run --locked python scripts/workspace_recovery.py backup --db "$db" \
  --output "$HOME/.local/share/uptime-backups/$(date -u +%Y%m%dT%H%M%SZ)"
uv run --locked python scripts/operations_check.py --db "$db" --config "$HOME/.config/uptime/ramp-sandbox.json"
uv run --locked python scripts/serve.py --mode sandbox --db "$db" --open
```

The refresh only reads. It requests no scope beyond the already approved grant set, and it never asks an administrator to grant a scope again. Keep the same tenant, mode and database for every launch.

## Daily operation and failure classes

`scripts/operations_check.py` is read-only. It makes no provider request, sends nothing, retries nothing and changes no database. Exit `0` means OK. Exit `2` means at least one `ATTENTION` finding. Exit `1` means the database could not be read; treat that as a failure, never as healthy. Schedule it with the operator's own `launchd` or cron job. This workstream installs no scheduler, and the report only prints. Delivering an alert to a person is a remaining deployment requirement.

| Operation | Class | What happens on failure or restart | Retry policy |
| --- | --- | --- | --- |
| Ramp refresh (token exchange plus reads) | Retryable read | The existing capture stays. An interrupted import stays `pending` and resumes when the same refresh runs again. | `--attempts 1..3`; reruns the whole read only after a *raised* transport failure or HTTP 429/500/502/503/504, waiting 5s then 30s. In practice that means token and business-read failures. A 429/5xx on an individual resource is recorded as `PARTIAL` or `UNAVAILABLE` in the capture and is **not** retried; rerun the refresh later to fill it. Never after a refusal, scope or binding error, or revocation. Each attempt exchanges a new token. `RampNetworkError` is never retried on a write path. |
| Capture freshness | Monitoring | `RAMP_CAPTURE_STALE` after 24h (`--stale-hours`). Native preparation already refuses captures older than 24h. | Rerun the refresh. |
| Model proposal job | Uncertain external effect (cost) | On restart, RUNNING becomes `UNCERTAIN` and QUEUED becomes `CANCELLED`. No provider call is repeated (`test_recovery_distinguishes_reserved_and_dispatched_work_without_running_either`). | Never automatic. A new attempt needs a new exact approval. |
| Native bill comment (outbox) | Uncertain external effect | A crash after dispatch leaves `UNCERTAIN`, and the delivery is never resent. Agent posting remains blocked by the execution-policy rejection. | Reconcile against the same Ramp thread; never resend. |
| Ramp webhook event | Authenticated intake | Signature over raw bytes; the same ID with the same bytes is a no-op; the same ID with different bytes quarantines the subscription; older events are `OUT_OF_ORDER`; events older than 7 days or more than 5 minutes in the future are refused. | No retry; the provider redelivers. The receiver is not publicly served (D11: stay local for this deliverable). |
| Signed inbound source | Authenticated intake | 60s timestamp window, single-use nonce, instance binding; restart invalidates outstanding proofs. | The sender signs a new request. |
| Claim cutoff | Deadline alert | `CLAIM_DEADLINE_APPROACHING` lists `ELIGIBLE` and `INSUFFICIENT_EVIDENCE` cases whose cutoff falls within 7 days (`--deadline-days`). Missing evidence stays distinct from ineligibility. | Not applicable. |

Other findings: `DATABASE_INTEGRITY`, `CASE_HISTORY_INTEGRITY`, `RAMP_IMPORT_INTERRUPTED`, `MODEL_JOB_OUTCOME_UNKNOWN`, `EXTERNAL_EFFECT_UNCERTAIN` and `OUTBOX_MISSING` (use `--outbox`), `WEBHOOK_QUARANTINED`, `REVOCATION_STORE_UNSAFE`, `REVOCATION_HOST_RECORD_MISSING`, `RESTORE_RECONCILIATION_PENDING` and `CONFIGURATION_CUSTODY`. The custody check inspects owner, mode, link count and repository location without reading file contents.

Dispute appeal clocks are enforced by the dispute engine when an action is taken; they are not yet listed by the health check.

## Back up, verify and restore

```sh
uv run --locked python scripts/workspace_recovery.py backup --db "$db" --output "$HOME/.local/share/uptime-backups/<new-name>"
uv run --locked python scripts/workspace_recovery.py verify --backup "$HOME/.local/share/uptime-backups/<name>"
uv run --locked python scripts/workspace_recovery.py restore --backup "$HOME/.local/share/uptime-backups/<name>" \
  --target "$HOME/.local/share/uptime/restored.sqlite" --tenant <tenant> --mode sandbox --previous "$db"
uv run --locked python scripts/workspace_recovery.py acknowledge --db "$HOME/.local/share/uptime/restored.sqlite" \
  --operator <operator-account> --note "<what was reconciled>"
```

- **Backup** uses SQLite's online backup, so it is consistent while the server writes. It creates a new `0700` directory with a `0600` single-file copy and manifest. The manifest records the binding, the integrity result, verification of the case hash chain, and the row count and digest of every table. Paths inside any Git repository are refused.
- **Not included:** credentials, private keys, sessions, host revocation and exception stores, configuration files, and the native outbox. Back those up with their own custodians' procedures.
- **The manifest is a checksum, not a signature.** It detects corruption and partial edits, not an administrator who rewrites both files.
- **Restore** verifies the backup and requires the expected tenant and mode. It writes only a new path, never overwrites, and refuses repository, symlinked and case-variant repository paths. It then fences the copy:
  - every unused reviewer mandate is revoked;
  - with `--previous`, later issuer, mandate and price-evidence revocations are carried forward;
  - an immutable restore epoch is recorded.
- **Until `acknowledge` is recorded,** native preparation and new mandate installation are refused and the health check reports `RESTORE_RECONCILIATION_PENDING`. Reconcile every Ramp comment and vendor submission made after the backup time before acknowledging.
- **Restart** with the same tenant and mode. Enrolled keys sign in again, financial and case history is unchanged, and old sessions are rejected (`test_backup_restore_restart_preserves_authority_and_financial_state`).
- **Without `--previous`,** revocations made after the backup (other than installation revocations) must be re-applied by hand. Moving issuer revocation to a host store is a recorded follow-up.

## Revoke or uninstall a Ramp installation

```sh
uv run --locked python scripts/revoke_installation.py status --db "$db" --tenant <tenant>
uv run --locked python scripts/revoke_installation.py revoke --db "$db" --tenant <tenant> --reason "Customer uninstalled Uptime"
```

Revocation is terminal for that tenant and Ramp business. It writes a `0600` host record and an immutable workspace event. Refresh then refuses before any token exchange, and import and native preparation refuse. Recorded history stays readable. Restarting the server or restoring an older workspace copy does not reopen access. A deleted host store does not reopen a current workspace either, because its own event still refuses. An unsafe or unreadable store fails closed. To reinstall, create a new workspace.

Uptime persists no Ramp token, so there is nothing local to delete. Under Ramp's public guide (retrieved November 9, 2026; not verified in the sandbox), client-credentials tokens live up to 10 days and a revoke endpoint exists. Uptime does not call it today. The Ramp administrator must disable the developer app or rotate its secret in Ramp; that is a human action outside Uptime.

## Remaining deployment requirements

These are not met by the local deployment. D11 keeps this deliverable local, so they are deferred to a later hosted milestone; each still needs the named decision details when that milestone opens:

1. **Hosted trust roots (later D11 milestone):** managed identity for operators and reviewers, ownership and rotation of signing keys, and a threat model for an administrator who is not the customer.
2. **Customer OAuth installation:** authorization-code flow, server-side state, encrypted refresh-token custody, single-flight refresh, and revocation calls on uninstall. [Design](CUSTOMER-INSTALLATION-DESIGN.md). Also D10 for data that leaves the installation.
3. **Public HTTPS webhook receiver:** a per-installation secret in a managed store and a root-operated verification transport. The existing inbox logic is reusable; it is not served today.
4. **Durable distributed workers:** a database-backed queue with leases and fencing tokens, replacing the single-process SQLite locks and in-memory nonce caches.
5. **Off-host backups:** encrypted, with retention, scheduled restore drills, and authenticated (signed) manifests.
6. **Alert delivery:** paging or email from the health check, with an accountable on-call operator.
7. **Host revocation for issuer, source and price-evidence keys,** so they survive restore without `--previous`.
8. **Customer data lifecycle:** retention and deletion on uninstall (D10/D11), and redacted centralized logs.
9. **Native action proof:** still governed by D02 and the separate execution-policy rejection. Nothing here retries or reroutes the blocked native posting.

## Rollback

Revert this workstream's commits in reverse order. The additive tables `operations_restore` and `native_installation_event` can stay in databases; older code ignores them. Leave the host revocation records in place. Removing one is a deliberate re-authorization that needs the team's decision.
