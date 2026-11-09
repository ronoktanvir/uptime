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


## Terminal readback and local continuation

Root review found that the copied dispatch helper read candidates before draining a late job. The additive runner now preserves the poll-bound snapshot and performs a second terminal job/candidate/state read after drain, without another dispatch. New `test_late_terminal_readback_after_drain_is_recorded_without_redispatch` reproduces a RUNNING-at-deadline job that succeeds during drain and verifies the one-POST terminal receipt.

The queue composition test now separately exercises a grounded time-bar reading, ordinary signed response preparation, local approval and local response receipt on an explicitly authored later business clock. The initial control failed at submit-response because the existing one-day follow-up policy correctly refused a same-day response; no policy was changed. The fixture now states its next-day continuation time. Ambiguous source readings remain review-only with zero awards. Correct-denial acceptance support is present but not yet proven by this harness; it must retain a separate continuation result.

Latest combined focused result: **55 passed, 1 warning in 2.14s.** No existing tests changed; no application changes; only controlled provider doubles in these checks.


## Source freeze and observed receipt setup

The separately authored six-contract/eight-reply corpus and expected outcomes were frozen before any scored attempt; only hashes/counts/provenance are committed in `CORPUS-FREEZE.json`. The sealed expected file has not been opened for scoring. Two separate Opus high sessions now receive sources and public schemas only to prepare reply readings and wire mappings.

Added a control for source-stated historical filing instead of fabricating a local original submission. The initial expectation that this monthly-profile setup would succeed was incorrect: the ordinary route refuses historical receipts unless an active reviewed resource-month agreement governs them. The new test now requires that exact setup refusal before model dispatch, with no local initial claim filing. This corrects the test's unsupported premise; no application or existing test was changed. A later monthly late-denial case will retain the setup limitation rather than pass on a forged chronology.

Latest combined focused result: **56 passed, 1 warning in 2.28s.**


## Fixed cohort execution

Added `tests/test_supplementary_finish_batch.py`:
- `test_mapping_refusals_are_terminal_cases_and_cannot_be_repeated`: all fourteen declared cases remain terminal records even if source setup refuses; the run directory cannot be reused.
- `test_dropping_or_relabeling_a_refused_case_cannot_raise_success_rate`: the executor rejects altered cohort composition before a run begins.
- `test_unpinned_consumed_input_cannot_start_a_provider`: every consumed source/setup/provider configuration must be committed by hash.

The additive batch executor opens no expected answers, checks source pins between cases, and records raw model, scripted projection, continuation and setup separately. It is infrastructure, not a result claim. Latest focused result: **59 passed, 1 warning in 2.50s.**


## Provider stream preservation

Wired the already reviewed spool helper into the actual SafePublicClaude providers used by both additive runners. Exact request exports must be registered before the ordinary queue starts. The wrapper retains the actual profile, 60-second timeout, output cap, provider identity/tool checks and ordinary approval gates. It records partial stdout/stderr from process startup; it adds no retry or fallback.

Added `test_spool_preserves_profile_and_only_registered_exact_request` (reject unregistered bytes, preserve delegated provider properties, and refuse reuse of the same call marker) and `test_spool_timeout_preserves_partial_stream_and_restores_transport` (a controlled subprocess emits partial output then times out; bytes and termination evidence survive and the original transport is restored). The first timeout assertion used an incorrect artifact filename and was corrected to the spool helper's existing `provider.stdout` filename. Latest combined focused result: **61 passed, 1 warning in 3.16s.** No application change and no actual provider call in these checks.


## Sealed scoring gate

The copied guarded gold reader referenced a terminal-check helper located outside the copied part of the historical runner. Added the missing guard for this cohort's actual batch records rather than leaving a dead reference. `test_expected_outcomes_stay_sealed_until_all_cases_and_jobs_are_terminal` verifies no expected content is opened before the complete case set exists or while a job remains pending, then verifies the one logged read after terminal records. Runner errors require explicit terminal-state reconciliation. Latest combined focused result: **62 passed, 1 warning in 2.36s.** This test uses a newly authored tiny expected file; no historical or cohort expected file is read.
