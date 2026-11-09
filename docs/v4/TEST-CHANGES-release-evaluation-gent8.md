# Test changes — release-evaluation-gent8

No existing test on `v4/integration` was changed, skipped, weakened or deleted. All authority and monetary assertions remain as they were.

The changes below concern only new tests, or test files that existed on the paused evaluation branches but not on integration.

| File | Origin | Change and reason |
|---|---|---|
| `tests/test_onboarding_evaluation_85.py` | Opus-authored on paused branch `work/onboarding-evaluation-85` (committed `a542a21`; uncommitted revision preserved verbatim in `adc1c83`) | **35 original tests unchanged.** 6 tests appended after harness validation: `test_poll_and_shutdown_bounds_cover_the_installed_provider_bound`, `test_poll_timeout_keeps_the_servers_own_terminal_state_without_retry`, `test_success_records_terminal_queue_state`, `test_prepare_freezes_tracked_core_tree`, `test_tracked_core_drift_after_freeze_prevents_inference`, `test_core_tree_refuses_uncommitted_core_changes`. They cover the terminal-state and core-freeze fix in `c1fa513`. |
| `tests/test_disputes_evaluation_86.py` | Paused branch `work/dispute-evaluation-86`, uncommitted; preserved verbatim in `adc1c83` | Unchanged; 20 pass on current source. |
| `tests/test_preflight_evaluation84.py` | New | 5 tests: no gold opened (audit hook over sentinel gold), pins, onboarding input acceptance, 12/12 dispute `Scope` blockers by D03/D04, literal-only scope derivation. |
| `tests/test_release_probes_gent8.py` | New | 1 real-process SIGKILL restart probe of the authored Northwind flow. |
