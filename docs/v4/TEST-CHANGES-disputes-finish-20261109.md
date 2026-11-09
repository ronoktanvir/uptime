# Dispute completion work — November 9, 2026

The user resumed onboarding and dispute blockers in parallel followed by independent evaluation. A subsequent explicit choice approved a separate strict complete-month evidence path; legacy incident obligations remain unchanged. New scope is opt-in from a grounded reviewed source clause, never inferred from absent incident identifiers.

## Parent-authored temporal intake controls

New kinds `monthly_coverage` and `monthly_attribution` must describe the exact UTC calendar month and cannot be observed before it ends. These checks run before storage through the existing source scope boundary. Existing civil-offset margins and other evidence kinds are unchanged.

New file `tests/monthly_finish_20261109/test_monthly_temporal_parent.py` tests leap-February bounds, equivalent offset-aware timestamps, partial and foreign months, premature reports including `complete=false`, and preservation of the existing incident margin. No existing tests changed.

Focused verification with the locked environment and unique temporary directory:

`uv run --locked --no-sync pytest -q -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp=<owned>/pytest-temporal tests/monthly_finish_20261109/test_monthly_temporal_parent.py tests/onboarding_finish20261109/test_monthly_basis_helper.py`

Result: **43 passed in 0.21s**. This includes the 24 shared marker-validator controls from onboarding, imported as a dependency. The integration owner runs the full suite serially after merge; this result is not full integration or independent evaluation proof.

## Actual delegated coding

Claude Code 2.1.318 authenticated with the existing OAuth subscription session. Two restricted workers were observed as `claude-opus-5-5`, requested `xhigh`, with only Read/Edit/Write/Glob/Grep and no MCP servers. Sessions: `723292a0-1458-46c5-bd66-5a679025c7ef` (refusal audit/helper) and `983dae98-68d4-479b-8328-755e37b99f57` (strict monthly evidence). At this preparation commit they are running, not completed contributions. A preceding detached process emitted no initialization and did not survive its command lifetime; it is recorded as a failed startup, not a model invocation. Parent controls tests and Git. No credentials, private customer captures, frozen expected answers or native financial actions were delegated.

## Verified signed-source refusal journal

Added `uptime/correspondence_refusals.py`, a metadata-only append-only journal for authenticated out-of-scope service requests. It accepts only bounded tenant/signer/key/grant identifiers, an exact route, body digest and receipt timestamp; it does not accept raw bodies, proofs, nonces or arbitrary reasons. Stable deduplication preserves the first receipt. This helper alone does not alter authentication; the separately reviewed service hook remains a dependent change.

Added `tests/disputes_finish_20261109/test_refusal_journal.py` (53 parametrized cases). Tests cover metadata validation before opening storage, tenant/key/grant isolation, first receipt preservation, restart, concurrent insertion, immutable rows, unrelated-table preservation and propagated persistence failures. No existing tests changed.

Focused locked-environment verification: **53 passed in 0.32s**. Command: `uv run --locked --no-sync pytest -q -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp=<owned>/test-journal-1 tests/disputes_finish_20261109/test_refusal_journal.py`. The integration owner runs the full required suite after merge.

The initial xhigh advisory worker (session `723292a0-1458-46c5-bd66-5a679025c7ef`) was stopped after 754.745 seconds (exit 143) after producing a proposal and an overbroad audit draft. That draft was replaced, not treated as delivered code. A bounded high-effort worker (`0f4e344a-5128-4e7e-baa6-586b89db296e`) completed the small journal and tests in 227.145 seconds (exit 0). The parent inspected the complete patch and ran the focused tests.
