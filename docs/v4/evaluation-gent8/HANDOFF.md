# Handoff: unseen evaluation, cross-component verification, security probes and release evidence (gent8)

November 9, 2026. Branches:
- `work/release-evaluation-gent8`: evaluation, probes and assessment.
- `work/d05-run-gent8`: the D05 run driver, on top of integration.

Both are pushed to `github.com/ronoktanvir/uptime`. The current verdict is in the [release assessment](RELEASE-ASSESSMENT.md). In short: not releasable; under D13 the new-vendor and new-dispute gates are not met; four items are blocked on Ronok.

## Commits

### `work/release-evaluation-gent8` (first-parent, oldest first)

| Commit | What |
|---|---|
| `dae8af8` | Merge of the unchanged frozen corpus `042d701` and the paused harness commits `a542a21`/`9e49ac9` |
| `adc1c83` | Paused 85/86 work-in-progress preserved byte for byte, SHA-256 checked against the pause checkpoint |
| `c1fa513` | Onboarding runner fix: provider-bounded polling, the server's own terminal state, and a core-tree freeze. Adds the offline preflight. |
| `52bea97` | Hard-kill restart probe, real-transport dry runs, and audit-gate receipts (118/118) |
| `0262262` | ADR-0092, harness validation, pre-registration addendum, first release assessment |
| `0403ec5` | D03 defect reproduction; later replaced by the invariant in `a6dab8d` |
| `487a32f`, `89fe25c` | D03/D04 status; full suite **4,035 passed** on `487a32f` |
| `1c6ee92` | **corpus84 onboarding first attempts: 0/4 supported accepted** (6 genuine `claude-opus-5-5` calls) |
| `757c3a3`, `a6dab8d` | Merge of agent1's D03-A (`6ebaffe`); the defect probe replaced with the D03-A invariant |
| `de88aea`, `46d20b5` | Coverage gates graded against D05/D06/D07/D11 and the D13 bar |
| `b034b7c` | Claim-basis contracts cannot be activated: a second dispute blocker |
| `95a0fae`, `7c970f9`, `2056856` | Socket probes: signed-request attacks, tenant crossing, stale authority, reply injection, duplicate and replayed deliveries |
| `b0bfd32` | `release_evidence.py status` recorded (read-only) |
| `9cb6c5a`, `e0e90fa`, `4a839f8` | Diagnosis released to W3 with Ronok's approval; 1a/3a recorded; single-runner rule |
| `474440a`, `211e2f6`, `e6c1cda` | **D05 unseen-vendor selection pre-registered, then sealed by commitment** |
| `498e337`, `1fdc2b5`, `ff308b6` | Incident-scope question; accept-denial scoring addendum (rule A); verified evaluation86 freeze |
| `00a7d3a` | Assessment on the round-6 head `3f60647` |

### `work/d05-run-gent8` (from `work/integration-90`)

| Commit | What |
|---|---|
| `9438957` | Pre-call checks for the sealed D05 proof |
| `cbec995` | D05 run driver and dry-run receipts |

## Files

**Mine:**
- `scripts/preflight_evaluation84.py`, `scripts/dryrun_onboarding_85_transport.py`
- `scripts/probe_restart_gent8.py`, `scripts/probe_socket_authority_gent8.py`, `scripts/d05_snapshot_gent8.py`
- `scripts/d05_precall_gent8.py`, `scripts/d05_run_gent8.py` (D05 branch)
- `tests/test_preflight_evaluation84.py`, `tests/test_release_probes_gent8.py`
- appended tests in `tests/test_onboarding_evaluation_85.py`; fixes in `scripts/evaluate_onboarding_85.py`
- `docs/v4/evaluation-gent8/*`, `docs/v4/decisions/ADR-0092-*` with its packet and review
- `docs/v4/TEST-CHANGES-release-evaluation-gent8.md`, `docs/v4/evidence/release-evaluation-gent8/*`, `docs/v4/evidence/d05-run-gent8/*`

**Preserved unchanged from others:** corpus84, the evaluation85/86 paused files, and agent1's D03-A changes (`uptime/*` and their tests), which arrived through the `757c3a3` merge.

No W0-owned file was edited.

## Behavior implemented

- **Onboarding runner fix:**
  - it can no longer lose a job's terminal state when the poll times out;
  - it refuses uncommitted or changed core source between prepare and run.
- **Offline, reproducible corpus84 preflight:**
  - pins, the current input contracts, claim-scope checks and claim-basis activation;
  - sealed gold is only `lstat`ed.
- **Listener-level probes:**
  - hard-kill restart with duplicate replay;
  - seven signed-request attacks;
  - tenant crossing;
  - stale authority after a source change;
  - an injected vendor reply, duplicate redelivery and signed replay.
- **D05 selection:**
  - a pre-registered, hash-ordered mechanical selection with a fixed snapshot extractor;
  - sealed expected terms, synthetic overlay and scenarios, with SHA-256 commitments;
  - pre-call checks, and a draft-mode driver with exact per-family export checks and leak scanning.

## Tests and actual results

| Run | Result |
|---|---|
| Full suite, `work/release-evaluation-gent8` @ `487a32f` | **4,035 passed, 1 warning in 791.25 s** ([receipt](../evidence/release-evaluation-gent8/verification-487a32f.json)) |
| Full suite after the D03-A merge on this branch | **Not yet run.** The slot is queued with agent0. Integration round 6 (`3f60647`, which contains D03-A, D04-C and my 6 probe tests) passed 4,664 with 1 warning (`def33b0`). It does not contain my evaluation-only tests. |
| Focused tests | 184 passed after the D03-A merge; `tests/test_release_probes_gent8.py` 6 passed; preflight 6 passed; onboarding runner 41 passed |
| Audit gate on `c1fa513` | 118/118 PASS against a fresh V3 baseline of 73/45, unsigned |
| corpus84 onboarding first attempts | 6/6 strict JSON; **0/4 supported extractions accepted**; both controls refused before assessment; 0 unsafe; about $0.39 ([receipt](../evidence/release-evaluation-gent8/onboarding84-first-attempts.json)) |
| `independent_final_fix_verifier.py` | **Exit 1.** Its preserved originals were edited in `5463bcb`. Recorded; not re-pinned. |
| evaluation86 runner `e1b6657` (agent3) | Verified independently: 32 passed; frozen scorers unchanged; pins match `ea920e9` |

## Remaining gaps

- **New-vendor gate:** no app-path success. A new independent cohort is needed to measure any improvement; D05 additionally needs the sealed unseen-vendor run.
- **New-dispute gate:** no receipts. All 12 corpus84 replies are setup-blocked: the claim-basis contracts are QUARANTINED, and the monthly family requires an incident.
- **Signed gates:** no independent witness or registered human reviewer; nothing is signed.
- **Allocation conflicts:** tested in-process only; the ledger has no HTTP route.
- **UI observation:** a stale approval record is still displayed after a source change. It is unusable, but a "stale" label may help.

## Decisions referenced

- ADR-0084: pre-registered interpretation.
- **ADR-0092:** this lane. One Opus 5.5 critique, session `6d98fd01-…`.
- D03-A, D04-C, D05, D06, D07, D10, D11, D13 and D14, as recorded or reported on November 9.
- Ronok's go-ahead for onboarding84; "Yes, share it"; 1a/3a.
- [Denial-acceptance addendum](PREREG-ADDENDUM-DENIAL-ACCEPTANCE.md) (rule A).
- [D05 pre-registration](D05-SELECTION-PREREGISTRATION.md) and [record](D05-SELECTION-RECORD.md).

## Rollback

- Revert `c1fa513` to restore the original onboarding runner bytes (preserved in `adc1c83`).
- Probes and documents are additive; drop the branch or revert their commits.
- The D03-A merge `757c3a3` can be reverted on this branch without affecting integration.
- The onboarding first attempts cannot be undone and must not be repeated as a score. Their attempt directories and receipts remain in `~/.local/share/uptime-engineering/review/evaluation84-onboarding/`.
- The sealed D05 material is in `~/.local/share/uptime-engineering/review/d05-unseen-vendor/`.
- Nothing external was changed: no Ramp action, signature, approval in Ronok's name, or gold read.

## External proof still missing

- An Uptime-origin Ramp write. The only Ramp comment was posted by a person.
- Ramp vendor credit or applied credit.
- Real vendor delivery and receipt.
- An actual human promotion of an unseen vendor, which needs the D05 run plus a promotion path.
- Independent witness signatures and a registered `ACTUAL_HUMAN` release reviewer.
