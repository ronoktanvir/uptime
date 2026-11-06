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

## Money-boundary correction before integration

Root review identified inconsistent case handling across the already-listed currency codes. New authored tests `test_all_listed_currency_codes_veto_source_money_regardless_of_case` and `test_unassigned_decimal_issuance_cannot_be_dropped_by_denial_bundle` keep their source and annotation unchanged across correction. Before the fix: **33 failed,43 passed,56 deselected**, one warning,0.48s. The failing cases mapped an availability objection despite a separate monetary clause; no financial/action execution occurred.

All existing currency codes now use the same case-insensitive match. A bare decimal paired with an issuance verb in its own clause also forces UNKNOWN without guessing an amount or currency. The controls for availability measurements and target percentages retain their original expectations. After correction, the focused78/71 and interpretation/browser run passed **253 tests**, one existing warning,6.42s, with browser execution required. No existing test was edited and no expected result was weakened. Exact commands, failed nodes, file hashes and both retained logs are in `evidence/verification-78-money-correction.json`.

The offline unchanged-public76-annotation replay remains6/6 supported-family matches,5/6 full semantics and6/6 UNKNOWN controls. Earlier source-specific results and evaluation76 baseline artifacts remain preserved. These finite lexical checks do not establish complete semantics.

## Integer/grouped-number issuance correction

Root found that the first issuance guard handled decimals but missed `We issued 30.`. New `test_unassigned_integer_or_grouped_issuance_cannot_be_dropped` freezes eight numeric spellings (integer, comma/dot grouping, ordinary/nonbreaking/narrow-nonbreaking spaces, mixed decimal/grouping). Before correction: **4 failed,4 passed,132 deselected**, one warning,0.37s. The original assertion/source/annotation stays unchanged.

The same-clause refusal now detects numeric literals, not only decimals, without parsing a monetary amount or currency. Focused78/71 and interpretation/browser checks: **261 passed**, one existing warning,6.01s; browser required, availability percentage positives unchanged. `evidence/verification-78-numeric-correction.json` retains actual commands, exit codes, failing nodes, log hashes and tested-source hashes. No existing tests were changed, no model was called and no financial/action execution occurred.
