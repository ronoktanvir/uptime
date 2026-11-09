# Test changes, workstream 89 (W4 disputes)

Branch `work/dispute-disposition-89`, based on `v4/integration` at `03b372e`.

## Existing tests

**No existing test was edited, removed, skipped or re-expected.** The unchanged dispute and correspondence suite passed against the implementation commit `3454b33`:

```sh
uv run --locked --offline pytest -q -p no:cacheprovider --basetemp=<unique> -o tmp_path_retention_policy=failed \
  tests/test_correspondence*.py tests/test_disputes*.py tests/test_local_review_exception_disputes.py tests/test_cross_claims.py
```

Result: **849 passed, 1 warning (existing Starlette/httpx deprecation), 226.95s.** This is a focused run, not the full suite. The integration owner runs `uv run --locked pytest` after merge.

## Existing behavior intentionally changed (no existing test asserted the old behavior)

| Behavior | Before | After | Covering new test |
|---|---|---|---|
| Rebuttal or cure loses its basis | Stage stayed `RESPONSE_DRAFTED` with no action and a full disputed remainder after later evidence made the claim ineligible | Returns to `HUMAN_REVIEW`; approval cleared | `test_contradictory_evidence_withdraws_a_drafted_rebuttal` |
| Reviewed maintenance reading, notice arrives after preparation | Closed automatically as `DENIAL_ACCEPTED` | `DENIAL_REVIEW`; closes only on explicit `accept-denial` | `test_n89_denial_maintenance_is_order_independent_and_explicit[review_then_notice]` |
| Reviewed reading projected to `DENIAL_ACCEPTED` with notice already present | Preview only `closure_suggested`; case stayed `HUMAN_REVIEW` indefinitely | Preview disposition `DENIAL_REVIEW`, `prepare_allowed`; explicit `accept-denial` | `...[notice_then_review]` |
| Case view | — | Adds `denial_acceptance` and `trace_url` keys | — |
| Interpretation preview | — | Adds `assertions` classification key; `closure_suggested` now means `DENIAL_REVIEW` | — |

The finite-grammar path that closes a confirmed maintenance denial on its own (`test_known_and_newly_received_maintenance`, oracle `notice_first_obtained_after_filing`) is unchanged. It is recorded as D06-dependent pre-existing behavior.

## New tests

`tests/test_correspondence_disposition_89.py` has 30 tests. They are driven by the cases frozen in `fixtures/correspondence/novel-89/cases.json` (commit `4e50dbc`, before implementation).

First run: **29 passed, 1 failed.** The failure was in a test helper, `reading()`: it found the offset of the inter-sentence whitespace segment with `text.index(" ")`, which matches the first space in the text, and the strict grounding validator rejected the partition. The helper now computes the gap's byte offsets directly. No frozen expectation or application code changed. Second run: **30 passed, 1 warning, 7.95s.**

## Changes after the Opus critique (`8083ab5`)

These edits are to this workstream's own new tests. No pre-existing test changed.

- **Acceptance API.** `accept-denial` now needs the exact offered `basis_digest`. Successful acceptances in the new tests go through the helper `accept(env)`, which reads the offered digest and calls `CorrespondenceDesk.accept_denial`.
- **Stronger negative tests.** They now assert the specific refusal `ValueError("Action unavailable…")` through the same helper, using a non-matching digest. Before, a bare `act("accept-denial")` could not have distinguished a missing digest from an unavailable action.
- **New falsifiers:**
  - `test_mandated_principal_cannot_accept_until_a_closure_decision_type_exists`
  - `test_acceptance_is_bound_to_the_basis_the_reviewer_saw`
  - `test_explicit_acceptance_reopens_when_its_own_ground_fails`
  - `test_trace_headline_uses_only_the_requesters_own_reading`
  - stale-trace assertions in `test_stale_authority_cannot_accept`
  - the `month_coverage_basis` assertion in `test_trace_is_read_only_and_digest_bound`
- **Historical-receipt path coverage.** `test_historical_original_reviewed_denial_requires_explicit_acceptance[True/False]` and `test_historical_timely_original_rebuts_a_novel_time_bar`.
- **Mutation check.** With the ground re-derivation removed and the digest comparison disabled, `test_acceptance_is_bound_to_the_basis_the_reviewer_saw` and `test_explicit_acceptance_reopens_when_its_own_ground_fails` both failed (2 failed). The source was then restored byte for byte.

Focused results:
- Uncommitted post-critique source, before the `month_coverage_basis` check: **904 passed, 1 warning, 341.70s**. This set added `tests/test_v4_routes_integration.py`.
- New file alone on `8083ab5`: **37 passed**.
- Final committed source `8083ab5`: **904 passed, 1 warning, 206.14s** (second attempt). The first attempt hung at an unchanged Playwright test under machine load and was stopped. Both are recorded in `docs/v4/evidence/dispute-disposition-89/verification.json`.
