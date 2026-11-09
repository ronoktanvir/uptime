# ADR 96 — fenced local recovery, host installation revocation and the customer-installation boundary

Status: local controls implemented and tested on `work/operations-90`. Drafted as decision 90; renumbered 96 because ADR-0090 belongs to another workstream. The packet and review were renamed without content changes, so the review's `packet_sha256` still matches. The pinned receipt `evidence/operations-90/verification.json` keeps the original review path. Customer OAuth installation is proposed only and blocked on D11/D10. November 9, 2026, America/Los_Angeles.

[Decision packet](packets/96-operations-recovery.md) · [Actual Opus 5.5 critique](reviews/96-operations-recovery.json), session `5278d28a-29f2-4537-a285-d5c6f8e66a6c`, model `claude-opus-5-5`, tool-free · [Runbook](../OPERATIONS-RECOVERY-90.md) · [Design](../CUSTOMER-INSTALLATION-DESIGN.md)

## Choice

1. **Restore is fenced and reduces authority.**
   - Backups are SQLite online copies with an unauthenticated checksum manifest. They hold no credential, key or session material.
   - Restore writes a new path only. It requires the expected tenant and mode, and revokes every unused reviewer mandate.
   - Restore carries later revocations forward from a supplied previous database of the same binding.
   - Restore records an immutable restore epoch. Native preparation and new mandate installation stay refused until an operator records reconciliation once.
2. **Installation revocation is terminal and lives on the host.**
   - An owner-only host record and an immutable workspace event both refuse provider access.
   - Refresh, import and native preparation stop before any network request. An unsafe store fails closed.
   - Reinstallation uses a new workspace. Ramp-side app disabling and secret rotation stay human Ramp-admin actions.
3. **Operations monitoring is read-only.**
   - The health check reports retryable reads separately from uncertain external effects, plus quarantined webhooks, claim cutoffs inside a window, restore epochs awaiting reconciliation and configuration custody.
   - It never retries, sends or writes.
4. **Bounded retries are opt-in and limited to reads.** The refresh accepts `--attempts 1..3` (default 1, unchanged behavior) and reruns only after typed transport failures or HTTP 429/5xx.
5. **Hosted customer OAuth, public callbacks, distributed workers and deployment artifacts are not implemented.** D11 is pending, so this decision prepares the design and leaves the loopback deployment unchanged.

## Opus criticism and disposition

Opus ranked fenced restore first, refuse-without-previous as an optional stricter mode, the in-database flag as disqualifying, and plain copy as unsafe. It called terminal installation revocation the right default.

| Opus point | Disposition |
| --- | --- |
| Reconciliation was named, not enforced | **Accepted.** An immutable restore epoch blocks native preparation (`RampWorkspace.record_for_native`) and new mandates (`mandates.install`) until `acknowledge`. The integration owner accepted the W0 `mandates.install` gate as a separate commit (`682d071`), on the condition that tests prove the acknowledgement clears it and a never-restored workspace installs byte-identically. If that commit is dropped, native preparation stays gated; remove mandate references from the restore messages and runbook. |
| A deleted host store fails open | **Accepted in part.** The workspace's own immutable REVOKED event also refuses, and the health check flags the missing host record. An administrator who restores an old workspace *and* deletes the host store remains a trusted actor. A host "installed" marker was rejected for now: it would refuse every existing installation after upgrade and would make tests write into the real home directory. |
| The outbox is excluded, so post-backup effects could look undelivered | **Accepted in part.** The outbox is a separate file that restore never replaces. The reconciliation gate prevents new native preparation until a person reconciles. Marking unknown outbox rows `UNCERTAIN` after a lost outbox is not implemented: there is no record of which rows to mark. Native posting also remains blocked. |
| Issuer and price-evidence revocations vanish without the previous database | **Deferred, recorded disagreement.** Moving issuer revocation into a host store changes the shared mandate trust model and belongs with the security owner. Until then, `--previous` carries revocations forward, and the runbook requires re-applying them otherwise. |
| Hash-chain fork after restore | **Accepted as a restore epoch.** Each restore has an immutable row. Exports and readers can distinguish a restored lineage. |
| The manifest is a checksum, not authentication | **Accepted.** Stated in code and runbook. Signed manifests are a deployment requirement. |
| Unsupported claims: token lifetimes, test counts, secret exclusion | **Accepted.** Ramp facts are cited with a retrieval date and marked not sandbox-verified. Test results are kept as evidence receipts. A backup scan test checks private-key, session-token and credential markers. |
| Missing falsification tests | **Added:** symlink and case-variant repository paths, backups during concurrent writes, staging collisions, a corrupt database returning a non-zero exit, deleted host store, and post-restore native and mandate attempts. Database-only, manifest-only and permission tampering were already covered. A consistent rewrite of both the database and the manifest is deliberately *not* detectable; that is the stated checksum limit. **Not added:** clock rollback, and two whole-process restores racing. The no-overwrite link and the staging collision check cover the race case. |

## Validation

- The original repairs were reproduced before any change. 14 existing suites passed at `03b372e`: 252 passed, 1 warning.
- 26 new test cases are in `tests/test_operations_recovery_90.py`.
- The W1 owner (agent4) approved the three Ramp-file changes after running 983 Ramp, reconciliation, credit-step and workstream tests on `0d97fbe`. Their notes are applied: a test pins the tenant domain to `Id`, write paths never retry `RampNetworkError`, and the runbook states that per-resource 429/5xx results are not retried.
- Ten source mutations were each detected by their targeted test:
  - fence removed;
  - each of three revocation checks removed;
  - carry-forward faked;
  - reconciliation gate removed from mandates;
  - reconciliation gate removed from native preparation;
  - workspace cross-check removed;
  - mandate gate removed again after the split;
  - a gate that writes to a never-restored database.
- Focused runs of the existing suites plus the new tests passed after each change: 1,128 passed, then 412 passed. Full-suite and repository-scan results are recorded in [evidence](../evidence/operations-90/verification.json). No existing test or assertion was changed.

## Rollback

Revert `682d071` (mandate gate) on its own if needed. Revert the whole workstream with `682d071`, `4994d36`, `f95834b`, `c52a5a4` and `f4826b4`, in that order, along with the documentation commits. The W1 edits to `ramp.py`, `ramp_workspace.py` and `scripts/ramp_refresh_workspace.py` were approved by the W1 owner. The additive `operations_restore` and `native_installation_event` tables are inert for older code. Host revocation records should stay. Deleting one re-enables a provider binding and needs an explicit team decision.
