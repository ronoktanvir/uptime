# Test changes — release-evaluation-gent8

No existing test on `v4/integration` was changed, skipped, weakened or deleted. All authority and monetary assertions remain as they were.

The changes below concern only new tests, or test files that existed on the paused evaluation branches but not on integration.

| File | Origin | Change and reason |
|---|---|---|
| `tests/test_onboarding_evaluation_85.py` | Opus-authored on paused branch `work/onboarding-evaluation-85` (committed `a542a21`; uncommitted revision preserved verbatim in `adc1c83`) | **35 original tests unchanged.** 6 tests appended after harness validation: `test_poll_and_shutdown_bounds_cover_the_installed_provider_bound`, `test_poll_timeout_keeps_the_servers_own_terminal_state_without_retry`, `test_success_records_terminal_queue_state`, `test_prepare_freezes_tracked_core_tree`, `test_tracked_core_drift_after_freeze_prevents_inference`, `test_core_tree_refuses_uncommitted_core_changes`. They cover the terminal-state and core-freeze fix in `c1fa513`. |
| `tests/test_disputes_evaluation_86.py` | Paused branch `work/dispute-evaluation-86`, uncommitted; preserved verbatim in `adc1c83` | Unchanged; 20 pass on current source. |
| `tests/test_preflight_evaluation84.py` | New | 5 tests: no gold opened (audit hook over sentinel gold), pins, onboarding input acceptance, 12/12 dispute `Scope` blockers by D03/D04, literal-only scope derivation. |
| `tests/test_release_probes_gent8.py` | New | 2 tests. `test_hard_kill_mid_flow_preserves_state_idempotency_and_final_ledger`: a real-process SIGKILL restart probe of the authored Northwind flow. `test_d03_defect_reproduction_onboarding_identity_is_refused_by_claim_intake`: pins a **known defect**. The signed vendor route evaluates `Cedar Orrery Studio` / `Talus Signal Availability Agreement` as ELIGIBLE 52.17 in shadow. Signed claim intake then refuses the same identity with 422 on exactly `account` and `contract`, while a provisioned identifier-domain control is accepted. **When D03 is implemented, this test must be replaced by the agreed invariant and the replacement recorded here.** |

## Replacements after D03-A landed (merge of `work/identity-pricing-89` @ `6ebaffe`)

Both replaced tests were new on this branch and never on integration. The replacements keep every monetary and authority assertion.

| Replaced test | Replacement | Reason |
|---|---|---|
| `tests/test_release_probes_gent8.py::test_d03_defect_reproduction_onboarding_identity_is_refused_by_claim_intake` (from `0403ec5`) | `test_d03a_exact_source_identity_flows_from_onboarding_into_claim_intake` | The pinned defect is repaired by decision D03-A. The shadow ELIGIBLE 52.17 assertion is kept unchanged. The spaced exact identity now reaches the provisioning gate (403). Once provisioned it opens the claim (200), an exact retry returns the same claim, and the stored scope keeps the exact bytes. Padded, repeated-space, tab, non-NFC, em-dash and `#` values are still refused with 422 at intake. |
| `tests/test_preflight_evaluation84.py::test_every_dispute_case_is_blocked_at_claim_scope_by_d03_and_d04` | `test_after_d03a_every_dispute_case_is_blocked_at_claim_scope_only_by_d04` | After D03-A, 0/12 replies are blocked on identity. 12/12 are still blocked on the universally required component, incident, invoice and region, because D04-C is decided but not yet implemented. The pre-D03 receipt `preflight-evaluation84.json` is preserved unchanged; the new state is in `preflight-evaluation84-after-d03a.json`. |
