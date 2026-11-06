# Decision78 test-change ledger

No existing test is intentionally changed. New authored controls are in `tests/test_correspondence_denial_bundle_78.py` and `tests/test_correspondence_denial_bundle_ui_78.py`; these are implementation checks, not blind evaluations or actual-human review evidence.

The frozen public76 corpus, expected answers, requests, model responses and baseline results remain unchanged. The new offline replay uses the identical saved annotations, makes zero provider calls, and reports a remediation measurement separately from the original baseline.

The first new test run reported **1 failed,54 passed**: the source `Availability met target. 10% applied. No credit is due.` incorrectly mapped availability. No action was executed. The implementation now requires performance context in the percentage's own clause as well as the credit-context veto. The test expectation was retained. The second scoped run passed **130 tests**, including browser behavior, with one existing Starlette warning in12.28s.

Final stable-source verification and exact command/log hashes are in `evidence/verification-78.json`. Root owns the full suite after integration.

## tests/test_correspondence_denial_bundle_78.py

- `test_narrow_bundle_preserves_both_orders_and_no_award`
- `test_availability_measurements_are_not_reported_credit`
- `test_other_bundle_shapes_remain_unknown`
- `test_full_source_loss_checks_do_not_trust_empty_secondary_slots`
- `test_percentage_without_performance_context_is_not_silently_lost`
- `test_date_in_separate_denial_cannot_be_claimed_by_primary`
- `test_assigned_wrong_month_stays_unknown`
- `test_omission_requires_explicit_reject`
- `test_review_preview_preserves_denial_and_only_drafts_with_existing_authority`
- `test_reordered_review_requires_correction_and_keeps_content_alignment`
- `test_candidate_only_secondary_cannot_disappear_as_correction`

## tests/test_correspondence_denial_bundle_ui_78.py

- `test_restored_reversed_bundle_keeps_all_propositions_and_preview`
- `test_explicit_candidate_load_preserves_slots_conditions_and_duplicate_spans`
- `test_add_assertion_clears_decisions_and_renders_separate_editor`
- `test_edit_during_save_does_not_publish_stale_preview`

Final frozen-source run at `f4ec198ad6f9cc8202e8283acc1285b63f242a7f`: **241 passed**, one existing Starlette deprecation warning,13.16s. Browser execution was required and no tests were skipped. Source and test files were unchanged throughout that run.
