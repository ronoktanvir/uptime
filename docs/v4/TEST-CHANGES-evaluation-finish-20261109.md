# Evaluation finish test ledger — November 9, 2026

No existing test was changed. No application module was changed.

New `tests/test_evaluation_onboarding_finish.py`:
- `test_source_and_input_freeze_refuses_drift_before_dispatch`: source and implementation drift must stop before invocation.
- `test_no_empty_freeze_or_symlinked_input`: no unpinned or aliased corpus file.
- `test_negative_selection_never_stages_or_fabricates_shadow` (three outcomes): terminal refusal/ambiguity/incomplete selections cannot stage an adapter or gain authority; a consumed attempt directory cannot be reused.

Focused run: `uv run --locked --no-sync pytest -q -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp=<owned evaluation test directory> tests/test_evaluation_onboarding_finish.py`, using the existing locked project environment. **5 passed in 0.45s.** No model, Ramp or vendor call. Root serializes the full suite after integration.

The new driver derives from the existing D05 ordinary signed automatic-selection runner, with distinct cohort identity, committed-code and input hash checks, no shell-interpolated Git command, and no access to gold for a leak scan. Frozen D05 and evaluation86 runners are unchanged. This infrastructure result is not an evaluation result.
