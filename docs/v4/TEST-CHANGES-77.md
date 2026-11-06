# Decision 77 test changes

No existing test file or frozen evaluation76 input, expected outcome, manifest or result changed. New controls are in `tests/test_vendor_resource_period_scope_77.py` and `tests/test_correspondence_scoped_filing_77.py`; sources are authored public controls and reviews are named scripted test fixtures, never actual human review.

## Added checks

The period controls reproduce the original April refusal, keep exact source endpoints and citation text, cover other months/year rollover/leap February, preserve supported inclusive/exclusive forms, and reject reversed, negated, qualified, partial, shifted, multi-month, mismatched-label, cross-sentence and non-UTC/subsecond representations. The aggregate end-to-end control uses independent literal arithmetic: 300 unavailable minutes / 43,200 total gives availability below 99.5%; a 10% credit on 10,000 cents is 1,000 cents ($10.00).

The scoped-filing controls preserve the explicit month, receipt basis, timestamp, endpoint and citation/hash; verify inclusive/exclusive boundaries; keep missing, spanning and other months unknown; refuse duplicate/conflicting/out-of-coverage policies, basis/comparator mismatch, inferred clocks, and unsupported neighboring conditions. The ordinary resource financial control retains the existing rounding requirement: 733 / 43,200 minutes downtime puts availability between 98% and 99%; 12.5% of 10,004 cents is 1,250.5 cents, rounded half-up to 1,251 cents ($12.51). No award, action or review authority changes.

Exact added test function names (parameterized rows remain visible in the source):

- `test_unchanged_april_clause_was_refused_by_keyword_gate_and_now_binds_exact_endpoints`
- `test_other_month_and_year_templates_bind_label_and_both_endpoints`
- `test_old_explicit_start_inclusive_end_exclusive_forms_are_preserved`
- `test_unsupported_or_contradictory_period_assertions_refuse`
- `test_keyword_gate_accepted_cross_clause_and_reversed_forms_that_now_refuse`
- `test_non_utc_subsecond_and_incomplete_bounds_refuse`
- `test_april_aggregate_source_compiles_end_to_end_with_scope_and_original_citation`
- `test_aggregate_profile_refuses_a_scoped_filing_primitive`
- `test_source_bound_november_policy_compiles_with_exact_citation_and_no_relative_count`
- `test_matching_month_inclusive_boundary`
- `test_matching_month_exclusive_boundary`
- `test_otherwise_complete_off_month_claim_stays_unknown_and_never_inherits_november`
- `test_distinct_named_month_policies_coexist_and_each_governs_only_its_month`
- `test_direct_deadline_requires_exact_month_matching_bounds_and_receipt_evidence`
- `test_relative_filing_paths_are_unchanged_by_the_scoped_dispatch`
- `test_private_relative_override_cannot_replace_a_scoped_deadline`
- `test_conflicting_duplicate_or_out_of_coverage_scoped_policies_refuse`
- `test_scoped_month_must_lie_wholly_inside_a_bounded_effective_interval`
- `test_ungrounded_qualified_or_contradictory_scoped_filing_refuses_without_side_effects`
- `test_accepted_scoped_forms_never_write_a_relative_day_count`
- `test_supported_scoped_filing_never_discards_an_unsupported_neighbor`

The lead-authored integration test `test_signed_historical_receipt_uses_its_verified_month_and_original_received_time` has two parameterizations: matching June and off-month July. It sends actual locally signed authored vendor receipts through the listener; wrong-source receipt intake is refused. It asserts the retained original receipt, destination, digest and exclusive representation of the inclusive cutoff for June, and no historical procedure/cutoff for July. Both retain null amount, zero claimed/awarded, and no action/submission. These signatures and scripted reviews confer no actual human or provider authority.

## Preserved verification history

- Before implementation: existing resource, resource-operator and service-month suites: **92 passed**.
- Preliminary production-code regression: the same existing suites: **92 passed in 1.32s**.
- First new-suite run during the coding worker's file-only review: **3 failed, 89 passed in 0.28s**. The three failures were parameterizations of `test_otherwise_complete_off_month_claim_stays_unknown_and_never_inherits_november`: its matching-month unreviewed context expected `Z`, while the existing evaluator emits `+00:00`. All off-month amount-null/no-cutoff assertions passed before that assertion. The coding worker independently corrected its own new assertion before completing. The implementation retains the exact source `Z` literal in the compiled policy and existing evaluator serialization. This correction does not weaken a money or authority assertion.
- First historical integration run: **2 failed in 0.74s**, with one existing Starlette/httpx deprecation warning. One new assertion expected raw `Z` despite receipt ingestion's existing normalized `+00:00`; the other expected a detailed reason in the public trace although the existing route deliberately collapses procedural validation errors to an unavailable procedure. Corrected the new expectations to the identical parsed instant and null public cutoff, respectively; money, sender, action and receipt assertions remain. Raw output is preserved outside Git.
- Final focused checks against source freeze `ee44b3872e7d41847360b1f90e5d9b7ecc97e48f`: **352 passed, 1 warning in 20.78s**. Covered vendor resource/operators/service-month/scoped/semantic bindings; both new77 files; correspondence resource/regional/plan references/service. The warning is the existing Starlette/httpx TestClient deprecation. Source hashes remained unchanged afterward. [Exact command and receipt](decisions/reviews/77-focused-verification.json). Root owns merge/full-suite verification.

Protected startup-spooled model streams and test receipts live under the local `review/decision77` directory outside Git. The public model receipt records actual sessions, tool inventory, status, edits and stream hashes.
