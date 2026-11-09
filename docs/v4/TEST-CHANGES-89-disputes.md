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

## Follow-up 89b: W5 findings F1, F2 and F8 (`work/dispute-intake-scope-89b`, based on `work/integration-90` at `25a18fb`)

Behavior:
- An embedded or HMAC delivery that fails W5's `source_config.event_in_scope` is refused before storage. That covers a measured interval wholly outside the service month (`evidence_applicability.temporal_refusal`) and a nested row or field naming another account, invoice, component, month and so on. The signed channel already refuses these at the grant.
- The refusal is recorded in `contradicting_deliveries` and the case timeline. It clears any packet approval, and it moves a pending cure, rebuttal or denial review to `HUMAN_REVIEW`. That record commits before the sender receives the refusal (`ValueError`, HTTP 409).
- **Misroute versus contradiction.**
  - A record wholly for another service month is a misroute: it voids any approval but does not hold the claim.
  - A record naming another identity (account, resource, region, invoice, component) contradicts the claim's scope. It holds every outbound and closing action until a person resolves it. Retraction is F7, which is blocked on a decision.
  - The first design held nothing. The first broad run exposed the regression (below).
- A retried refused event with the same content returns the same refusal without new effects. Reusing the event id with different content is refused.
- The dispute trace adds `status_origin`: the enrolled status signer, `ENROLLED_SOURCE_NOT_ORIGIN_VERIFIED`, and the profile URL as `profile_assumed_origin` (F8).

### Existing tests changed (exact names and reasons)

| Test | Change | Reason | Safety assertion kept |
|---|---|---|---|
| `tests/test_correspondence.py::test_mismatched_fee_and_component_prevent_further_packet` | The foreign-account invoice delivery is wrapped in `pytest.raises(ValueError, match="outside the granted claim scope")`. The preflight expectation changes from `INSUFFICIENT_EVIDENCE` to `ELIGIBLE`, and the test now also asserts the contradicting delivery is listed. | F2: the foreign row is no longer stored as the claim's single invoice record, so it no longer poisons preflight. | `not row["actions"]`, `approval is None` and the failing `submit-claim` are all unchanged. |
| `tests/test_correspondence.py::test_contradictory_component_stops_rebuttal` | The wrong-component delivery is wrapped in `pytest.raises(ValueError, match="outside the granted claim scope")`. | F2: refused before storage. | Stage is `HUMAN_REVIEW` with no actions (unchanged assertion). |
| `tests/test_correspondence.py::test_invoice_scope_mismatch_without_other_invoice` | The wrong-month invoice delivery is wrapped in `pytest.raises(...)`. The trace expectation changes from containing "contradicts" to "Awaiting an authenticated invoice", and the test asserts the contradicting delivery is listed. | F2: refused before storage; the claim correctly awaits an in-scope invoice instead of holding a contradicted one. | Outcome stays `INSUFFICIENT_EVIDENCE` (unchanged assertion). |
| `tests/test_correspondence_regional.py::test_incomplete_contradictory_or_expired_evidence_cannot_authorize_cure[wrong-region]` | For this parameter only, the foreign-region monitor row is delivered separately and expected to return 409 "outside the granted claim scope". The remaining rows are delivered as before. | F2: refused before storage. | `row["actions"] == []` and the zero claimed and awarded amounts are unchanged. |
| `tests/test_correspondence_resource.py::test_conflicting_raw_source_stops_before_claim[wrong-fee-resource]` | For this parameter only, the foreign-resource fee row is delivered separately and expected to return 409. | F2: refused before storage. | `outcome == INSUFFICIENT_EVIDENCE` and `not actions` are unchanged. |
| `tests/test_correspondence_disposition_89.py::test_n89_cure_inapplicable_escalates` (this workstream's own test) | The wrong-component delivery is wrapped in `pytest.raises(...)`, and the test asserts the trace lists the contradiction. | F2. | The frozen expectation `n89-cure-inapplicable` → `HUMAN_REVIEW` / `ESCALATE` is unchanged. |

New tests: `tests/test_correspondence_intake_scope_89b.py`, 7 tests.

Runs:
1. Touched files (first design): **99 passed**.
2. Broad focused run (first design): the dispute tests plus the 32 other test files that deliver through correspondence intake. **2 failed, 1666 passed, 1 warning, 275.82s.** The two failures were the regional and resource rows above.
   - The regional failure exposed a **safety regression in the first design**. With the foreign-region row refused instead of stored, a later historical cure became authorizable (`approve-response` offered).
   - The design was tightened: identity contradictions hold all actions.
   - That test's original `actions == []` assertion now passes without being weakened.
   - The earlier draft of the `test_mismatched_fee_and_component_prevent_further_packet` change, which expected `approve-claim` to be offered, was withdrawn before commit. That test keeps `not row["actions"]`.
3. After tightening, the touched files gave **148 passed**. The final broad result is recorded in `docs/v4/evidence/dispute-intake-scope-89b/verification.json`.
