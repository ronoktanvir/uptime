# W9 operations handoff: installation, recovery and local operation

Owner: session `gen6`, branch `work/operations-90`, base `03b372e`. As of November 9, 2026, everything listed is merged into `work/integration-90`. This branch was fast-forwarded onto integration `e10d95d` before this docs-only handoff commit. Scope under D11 (*stay local for now*): a loopback-only deliverable with no hosting and no tunnel.

**Status: complete for the local deliverable. Nothing in W9 is blocked on a decision.** Two follow-ups need Ronok personally, and neither blocks the demo:
1. Approve or decline installing a scheduled alert job on the demo Mac (a persistent change to his machine).
2. Decide what happens to tenant records after an uninstall, which is part of the later hosted milestone.

Related: [runbook and trust boundary](OPERATIONS-RECOVERY-90.md) · [demo-machine guide](DEMO-MACHINE-90.md) · [customer installation design](CUSTOMER-INSTALLATION-DESIGN.md) · [ADR 96](decisions/ADR-0096-operations-recovery.md) · [test ledger](TEST-CHANGES-90-OPERATIONS.md) · evidence in [evidence/operations-90](evidence/operations-90/)

## Commits

| W9 commit | Change | Integrated by |
| --- | --- | --- |
| `f4826b4` | Fenced backup and restore, host installation revocation, read-only health check | `8ed847e` |
| `c52a5a4` | Restored epoch blocks native preparation until reconciliation; the workspace revocation event keeps access closed without the host record; Opus packet and review | `8ed847e` |
| `f95834b` | Opt-in bounded retries (1–3) for the read-only Ramp refresh; `RampNetworkError` | `8ed847e` |
| `e522376`, `c0259f4` | Runbook, installation design, ADR and ledger; shared indexes left to W0 | `8ed847e` |
| `0d97fbe` | Pinned focused-verification receipt | `8ed847e` |
| `4994d36`, `682d071` | Mandate gate split into its own W0-accepted commit, with the byte-identical and acknowledgement tests | `8ed847e` |
| `21f733a`, `27e4926` | ADR renumbered to 96; revocation tenant domain pinned to `Id`; W1 review notes applied | `8ed847e` |
| `4a8a80a` | D11 and D06 recorded in W9 docs | `fb1ae06` |
| `25d0a5e` | D10 references limited to model data; uninstall retention marked undecided | `5cdcf2d` |
| `b48b2aa` | Deadline alerts skip filed and closed claims; list cutoffs passed without filing; skip replay mode; flag clock skew and a capture near its limit | `8912307` |
| `cf4636c` | Read-only demo-machine preflight | `8912307` |
| `9589f6c`, `18144a1` | Demo-machine readiness and recovery guide | `8912307` |
| `aba3307` | Native outbox backup and restore behind the W1-specified fence | `8912307` |
| `b3a3fef` | Receipt: fresh clone, preflight and drills at integration `23805c9` | `8912307` |
| `24a3ce8`, `dd32596` | Live-database reads never create `-wal`/`-shm` sidecars or checkpoint a leftover WAL | `4f9fb82` |

## Files changed

**New W9 files:**
- `uptime/installation_revocation.py`, `uptime/workspace_recovery.py`, `uptime/operations_health.py`, `uptime/operations_preflight.py`
- `scripts/workspace_recovery.py`, `scripts/revoke_installation.py`, `scripts/operations_check.py`, `scripts/operations_preflight.py`
- `tests/test_operations_recovery_90.py`
- `docs/v4/OPERATIONS-RECOVERY-90.md`, `CUSTOMER-INSTALLATION-DESIGN.md`, `DEMO-MACHINE-90.md`, `TEST-CHANGES-90-OPERATIONS.md`, this file
- ADR 96 with its packet and review
- Two evidence receipts

**Edits to files other workstreams own, each approved by that owner:**
- W0 `uptime/mandates.py`: 2 lines in `install()`.
- W1 `uptime/ramp.py`: `RampNetworkError`.
- W1 `uptime/ramp_workspace.py`: revocation and reconciliation checks on import and native preparation.
- W1 `scripts/ramp_refresh_workspace.py`: a revocation check before any token exchange, plus `--attempts`.

No existing test function or assertion was changed.

## Behaviour implemented

- **Backup and verify.** An SQLite online copy goes into a new `0700` folder, with a `0600` manifest recording the binding, integrity, case hash-chain status and the digest of every table.
  - It never contains credentials, keys or sessions.
  - It refuses paths inside repositories, including through symlinks and case variants.
  - The native outbox is included only on request.
  - The manifest is a checksum, not a signature.
- **Fenced restore.** It writes new paths only, all or nothing, and requires the expected tenant and mode.
  - It revokes unused reviewer mandates and can carry later revocations forward from the previous database.
  - It records an immutable restore epoch. Native preparation and new mandates are refused until an operator records reconciliation once.
  - A restored outbox follows the W1 fence: `DISPATCHING`→`UNCERTAIN`; a `REVIEWED` comment→`PREPARED` with its review cleared; `PREPARED`/`BLOCKED` comments unchanged; other unsettled actions→`UNCERTAIN`. Webhook quarantines carry forward.
- **Installation revocation.** This is terminal for a (tenant, Ramp business) pair.
  - It writes an owner-only host record outside the workspace and an immutable event inside it.
  - Refresh refuses before any token exchange; import and native preparation also refuse; history stays readable.
  - Neither a restart nor a restore reopens access, and deleting the host record doesn't either.
  - An unsafe store fails closed.
- **Health check** (`operations_check.py`, read-only). It reports:
  - integrity and the case hash chain;
  - capture staleness, a capture near its limit, and clock skew;
  - interrupted imports, as retryable reads;
  - uncertain outbox deliveries and model jobs, as never retried;
  - quarantined webhooks;
  - unfiled claim cutoffs approaching or recently passed (sandbox only);
  - pending restore reconciliation;
  - credential-file custody, checked without reading contents.

  Exit `0` means OK, `2` means attention, `1` means the database was unreadable.
- **Preflight** (`operations_preflight.py`, read-only). It checks free disk, a sandbox-only Ramp environment, tunnelling clients (by process name, never arguments), loopback-only listeners, workspace health and a recent verified backup per exact workspace binding.
- **Live-database reads** never create SQLite sidecar files and never checkpoint a leftover WAL. An idle WAL database is read as immutable; otherwise reads use plain read-only mode.
- **Bounded read retries:** `--attempts 1..3`, default 1. They apply only to raised network errors and HTTP 429/5xx on the whole read, mainly token and business reads, with 5s and 30s waits. They never follow a refusal, scope or binding error, or revocation, and write paths never retry.

## Tests and actual results

| Run | Commit | Result |
| --- | --- | --- |
| Baseline before changes (14 auth, tenant, webhook and job suites) | `03b372e` | 252 passed, 1 warning |
| Focused runs during development | `f4826b4` … `24a3ce8` | 972; 1,128; 412; 183; 1,097; 1,166 passed (each 1 warning) |
| W1 pending branch merged with W9, in a throwaway worktree | `d3caec2`+`18144a1` | 1,082 passed, 1 warning |
| Fresh clone, operations, Ramp and authority suites | integration `23805c9` | 1,206 passed, 1 warning in 117.43s |
| Integration full suite, fresh clone (agent0) | `1b627ad` | 4,110 passed, 1 warning |
| Integration round 4 (agent0) | `3758164` | **1 failed**, 4,581 passed. The failure is W4's `test_blind_acceptance…late_routes`; no W9 test failed |
| Integration round 6, fresh clone, all checks (agent0) | `3f60647` (includes `dd32596`) | 4,664 passed, 1 warning in 322.63s; node, graph, rehearsal, secret scan and render check passed |

- **New tests:** 36 functions, 40 cases, in `tests/test_operations_recovery_90.py`. Twenty-seven targeted source mutations were each detected.
- **JavaScript checks at `e522376`:** 75/75 passed, the progress graph passed, and the secret scan covered 2,154 objects.
- **W9 never completed a full suite of its own.** One attempt was invalidated by a working-tree change, and one was stopped for the shared-disk queue at the integration owner's request; both logs are kept. Full coverage comes from agent0's integration runs above.
- **First-run failures kept in the ledger:**
  - a whole-view comparison that included the wall-clock `evaluated_at`;
  - an all-digit UUID case test;
  - an outbox fixture without W1's tables;
  - a tamper `UPDATE` that matched no rows;
  - two surviving mutants (the outbox checksum and the read-write revocation read), each closed with a new case.

**Drills and preflights on real data (all read-only, or on copies):**
- **Preflights:** READY at 04:30 and on the integration head. On the presentation listeners at about 05:07 (8776 from `presentation-fde492c`, 8777 and 8780), READY with no findings.
- **Drills on copies:** backup, verify, restore and restart drills on copies of the Northwind and CalyxQuay review workspaces passed. CalyxQuay's 9 events are intact through revision 9.
- **Side effect:** one live read, at about 05:07, created an empty `workspace.db-wal` (0 bytes) and a 32 KB `-shm` beside the review database. No data was written. With agent0's agreement they were left in place, and `24a3ce8` prevents a recurrence.

## Remaining gaps

1. **Hosted customer installation is designed, not built:** OAuth, public HTTPS webhooks, distributed workers and deployment files. It is deferred to a later milestone under D11 and D01.
2. **Alerts reach no person.** The reports only print. Installing a scheduled job needs Ronok's approval (persistent configuration on his Mac). D06 also allows no standing-policy execution until W0's policy record and executor exist.
3. **Ramp-side uninstall is manual.** Disabling the app or rotating its secret is a Ramp-admin action; Uptime never calls Ramp's token-revoke endpoint.
4. **Issuer, source and price-evidence revocations have no host record.** They survive a restore only when `--previous` is supplied. The mandate trust model belongs to W0, with the security owner.
5. **Backups:** no signed manifests, no off-host or encrypted copies, and no retention or scheduled restore drills.
6. **Dispute response (supplement) windows** are enforced by W4 when an action is taken, but are not listed by the health check.
7. **A signed-in Northwind restart on a copy was not run.** It needs its private rehearsal secret, which was deliberately not used; W8's `--resume` receipt covers that path.
8. **Per-resource Ramp 429/5xx results** are recorded as `PARTIAL` or `UNAVAILABLE` and are not retried.
9. **The local machine administrator is a trust root.** Someone who restores an old workspace *and* deletes the host store can reopen access.

## Decision references

| Decision | Source | Effect on W9 |
| --- | --- | --- |
| D11 stay local for now | **Ronok's own** | No hosting or tunnel; hosted items are deferred, not blocked |
| D06 humans gate judgment | **Ronok's own** | Restore, reconciliation acknowledgement and revocation stay human; no standing policy or scheduler configured |
| D10 public-only data to models; no retries on uncertain outcomes | **Ronok's own** | No W9 data goes to models; uncertain jobs and deliveries are never retried |
| D14 Opus critique no longer mandatory | **Ronok's own** | The one critique already run stays as recorded |
| D03, including the name extension | **Ronok's own** | The revocation tenant domain is pinned to `Id` by a test |
| D01 two milestones | **Delegated** (overview session, handoff default) | Hosted installation is the second milestone |
| D02 informational bill discussion on the exact record | **Delegated** | Native posting stays blocked; the outbox fence is tested only against W1's simulated provider |
| D08 claim delivery channel | **With Ronok** (undecided) | Whether an uninstall cancels in-flight claims is left to it |
| W0 rulings (agent0) | Workstream owner, not a team decision | Mandate gate accepted as a separate tested commit; ADR 96 numbering; shared indexes owned by W0; sidecars left in place |
| W1 rulings (agent4) | Workstream owner, not a team decision | Ramp-file edits approved; the outbox fence specified by W1 and adopted over my broader proposal |
| Opus 5.5 critique, session `5278d28a` | Advisory model review | Adopted: enforced reconciliation and a fail-closed workspace revocation. Deferred: issuer host store |

## Rollback

- **Whole workstream:** on `work/integration-90`, revert the W9 merges newest first, then the W0 documentation commits that cite W9 (`71e8bb9`, `1878a69`, `7d01403`):

  ```sh
  git revert -m 1 4f9fb82
  git revert -m 1 8912307
  git revert -m 1 5cdcf2d
  git revert -m 1 fb1ae06
  git revert -m 1 8ed847e
  ```

- **Partial rollbacks:**
  - `682d071` removes only the mandate gate. Native preparation stays gated, so also drop the mandate wording in the docs.
  - `24a3ce8` restores the old read behaviour and with it the sidecar risk.
  - `aba3307` removes outbox backup and restore.
- **Data needs no cleanup.** The `operations_restore` and `native_installation_event` tables are additive and inert for older code. Backup folders are harmless.
- **Leave in place:**
  - Host revocation records under `~/.config/uptime/installation-revocations/`. Deleting one re-enables a provider binding and needs a team decision.
  - The empty sidecar files beside the review database. SQLite manages them.

## External proof still missing

- No real restore has been performed on a live demo workspace, and no human has acknowledged reconciliation after one; only copies were drilled.
- None of these are verified against the Ramp sandbox: Ramp's token lifetimes, its revoke endpoint, disconnect behaviour, and whether refresh tokens rotate. The design cites Ramp's public guide, retrieved November 9.
- No Ramp-side uninstall (app disable or secret rotation) has been exercised.
- The outbox fence has run only against W1's `SimulatedWorkflowProvider`; native posting remains blocked.
- No hosted deployment, public webhook, off-host backup or alert delivery exists.
