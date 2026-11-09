# Evaluation finish test ledger — November 9, 2026

No existing test was changed. No application module was changed.

New `tests/test_evaluation_onboarding_finish.py`:
- `test_source_and_input_freeze_refuses_drift_before_dispatch`: source and implementation drift must stop before invocation.
- `test_no_empty_freeze_or_symlinked_input`: no unpinned or aliased corpus file.
- `test_negative_selection_never_stages_or_fabricates_shadow` (three outcomes): terminal refusal/ambiguity/incomplete selections cannot stage an adapter or gain authority; a consumed attempt directory cannot be reused.

Focused run: `uv run --locked --no-sync pytest -q -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp=<owned evaluation test directory> tests/test_evaluation_onboarding_finish.py`, using the existing locked project environment. **5 passed in 0.45s.** No model, Ramp or vendor call. Root serializes the full suite after integration.

The new driver derives from the existing D05 ordinary signed automatic-selection runner, with distinct cohort identity, committed-code and input hash checks, no shell-interpolated Git command, and no access to gold for a leak scan. Frozen D05 and evaluation86 runners are unchanged. This infrastructure result is not an evaluation result.


## Runner composition and scope preflight

Added `tests/test_preflight_scope_finish.py` (44 checks), authored by the real independent Opus runner-review session. They exercise the application's actual claim-scope discrimination/resolution, including missing incidents, unsupported resources, wrong bindings and exact identity checks. The preflight explicitly assumes a minimal in-memory adapter and does not claim actual activation/evidence readiness.

Added `tests/test_evaluation_disputes_finish.py` (4 checks):
- `test_unconfigured_provider_is_separate_from_successful_signed_setup`: normal signed candidate, tests, local scripted activation, claim, evidence and filing must complete before the missing provider request is reported as a setup refusal; consumed attempt folders cannot be reused.
- `test_tampered_source_reading_never_creates_an_attempt`: changed source-only readings stop before case creation.
- `test_real_queue_records_one_controlled_candidate_without_financial_changes` (projection off/on): real signed application and model queue execute exactly one explicit provider double; raw output cannot create money; separately frozen scripted projection is reported independently from candidate accuracy.

Combined focused result: **53 passed, 1 warning in 1.69s.** Warning: existing Starlette TestClient/httpx deprecation. Command used the locked project environment with `uv run --locked --no-sync pytest -q -p no:cacheprovider`, these three new test files, and an owned temporary directory. No scored inference, Ramp or vendor call occurred. The frozen evaluation86 runner and all previous test files remain unchanged. Root retains the full-suite integration check.
