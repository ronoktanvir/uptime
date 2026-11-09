# Decision 93 test changes

**No existing test function, fixture or assertion was changed.**

New file `tests/test_ramp_case_lineage.py`: 58 collected cases. Every Ramp record in it comes from an injected read-only fake provider through the real `ramp_records.sync_records` sanitizer and `_validate_snapshot`. No credentials, network, captures or provider writes are used, and none of these results is a live receipt.

The only real artifacts the file reads are `scripts/verify_ramp_comment.py` (to confirm the approved note text matches) and the committed receipt `docs/v4/evidence/demo-path-87/human-ramp-note.json`. That receipt's SHA-256 is pinned at `c688cfeb…` so any rewrite of it fails.

| Area | New tests |
|---|---|
| Exact identity and association | `test_exact_identity_keeps_spaces_and_refuses_rewrites`, `test_association_uses_native_ids_never_names_or_amounts`, `test_missing_provider_fact_is_unknown_not_ineligible`, `test_period_currency_allowlist_and_conflict_rules`, `test_card_transactions_need_explicit_review_and_agreement_absence_is_reported`, `test_association_refuses_wrong_business_or_contract` |
| Identity and money across stages | `test_one_case_keeps_identity_and_applied_comes_only_from_reciprocal_readback`, `test_recorded_credit_without_application_is_not_applied_value`, `test_draft_reservation_is_separate_from_applied`, `test_one_sided_application_leaves_applied_unknown`, `test_reversal_and_later_absence_require_review_not_silent_values`, `test_duplicate_imports_count_once_and_truncated_latest_read_is_unknown`, `test_unbound_same_vendor_credit_is_never_attributed`, `test_application_outside_contract_scope_or_credit_over_award_needs_review`, `test_identity_breaks_stop_the_chain` (8 parameters), `test_northwind_terms_never_attach_to_an_unrelated_ramp_bill`, `test_tampered_finding_and_monetary_finding_without_terms_are_refused` |
| Surfaces | `test_evidence_gap_note_is_informational_and_never_duplicated`, `test_note_receipt_must_match_the_same_object` (7 parameters), `test_note_cannot_sit_on_a_monetary_finding_or_changed_comment`, `test_payment_hold_counts_only_when_read_back_after_the_request`, `test_uncertain_uptime_delivery_is_read_back_never_resent` |
| Person-operated application | `test_preparation_is_not_execution_and_simulated_awards_cannot_drive_it`, `test_preparation_gates` (4 parameters), `test_preparation_refuses_over_application_of_the_bill`, `test_readback_classifies_uncertain_outcomes_without_retry` (6 parameters), `test_readback_refuses_tampering_wrong_business_and_stale_reads` |
| Preserved evidence and boundaries | `test_approved_note_text_matches_the_readback_verifier_and_the_preserved_receipt`, `test_new_modules_have_no_transport_or_write_path` |
| Opus falsification controls | `test_one_credit_cannot_be_counted_by_two_cases_or_split_silently`, `test_bill_side_only_application_leaves_applied_unknown`, `test_note_missing_from_a_later_complete_thread_needs_review`, `test_released_or_preexisting_hold_is_not_a_current_intervention`, `test_preparation_rechecks_lineage_and_needs_current_association`, `test_row_without_known_kind_is_never_the_case_record`, `test_concurrent_use_elsewhere_is_not_a_wrong_amount_and_executor_is_recorded`, `test_double_binding_needs_review_even_when_credit_is_not_observed` |

## Failed attempts kept on record

These are kept rather than squashed away:

- **First run:** 45 of 48 tests failed. The fake provider lacked the second vendor's detail record.
- **Next run:**
  - The January fixture's service period ended after its issue date. The pricing engine correctly returned `UNSUPPORTED_RULE` for that future performance, so the fixture was corrected rather than the engine.
  - A bill with no vendor is dropped by the sanitizer, so that test now covers a missing issue date instead.
- **After the critique fixes:** 23 tests failed because they had to supply the new binding registry and a current association. One tampering test first "edited" a value to the value it already had; it now changes a real value.
- **Self-review after the first commit:** two gaps found in the module itself. Double-binding review was dropped when the bound credit was never observed, and a note receipt without `observed_at` raised an error instead of being refused. Both are fixed, each with new cases.

- **D03 alignment:** after D03 was decided, this branch's own `test_exact_identity_keeps_spaces_and_refuses_rewrites` stopped expecting decomposed Unicode to be refused. It now asserts the value is kept exactly as given. That test is new in this branch, not an existing integration test.
- **D03-A switch (after integration merge `572d5b5`):** `tests/test_ramp_case_lineage.py::test_exact_identity_keeps_spaces_and_refuses_rewrites` is now an integrated test, and it changed again. It returns to expecting decomposed Unicode (`Cafe\u0301`) to be refused, and checks that the NFC form is accepted unchanged. Reason: agent1's implemented D03-A rule refuses non-NFC values, so the earlier relaxation was based on an incomplete summary. New test: `test_account_and_agreement_follow_the_shared_source_identity_rule` checks 15 values, so account and agreement acceptance can't drift from `uptime.source_identity.refusal`.

Production assertions were not weakened at any step.

## Results

- **Focused (new file only):** 55 passed in 1.49s; 58 passed in 2.35s after the self-review fixes.
- **Focused Ramp, allocation, reconciliation and credit suites:** 1,064 passed, 1 warning in 82.86s. This run used the new file before the critique fixes.
- **Full suite (integration owner, fresh clone):** `work/integration-90` at `1b627ad`, containing this branch at `1c8bc86`: 4,110 passed, 1 warning in 586.65s.
- **D03-A switch:** tested on a local, unpushed merge of `work/integration-90` and `work/identity-pricing-89` (`6ebaffe`). This file plus `tests/test_source_identity_89.py`: 96 passed. Ramp, reconciliation, credit, allocation and identity suites: 1,166 passed, 1 warning in 25.71s. Real demo-bill lineage digest unchanged (`6b000b14…`). The integration suite after D03-A merges is the full run of record.
