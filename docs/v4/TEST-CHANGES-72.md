# Decision 72 exact test-change ledger

Only authored offline fixtures are used in the new business-scope tests. No live Ramp query, native write or previously rejected native qualification run is part of this work.

## Existing assertions changed

- `tests/test_ramp_credit_sync_v4.py::test_official_fields_unmatched_and_draft_are_not_attributed`: The no-link ledger amount assertions now require null; the observed native totals remain exact and unchanged.
- `tests/test_ramp_credit_sync_v4.py::test_unavailable_partial_stale_future_no_confirmation`: Each unavailable, partial, stale and future case now requires a null linked amount rather than zero when confirmation has not occurred.
- `tests/test_ramp_credit_sync_v4.py::test_duplicate_ids_conflicting_payload_and_tenant_isolation`: The untouched other tenant must report a null linked amount instead of zero. The conflicting-ID and missing-award checks remain.

- `tests/test_ramp_credit_sync_v4.py::test_conflicts_durably_quarantined_without_ledger_mutation`: the exact receipt now also requires the authored provider business ID. Conflict reason codes and no-ledger-mutation assertions remain unchanged.

## Existing shared fixture changes

The `snapshot()` and `binding()` helpers in `tests/test_ramp_credit_sync_v4.py` now supply one explicit authored Ramp business UUID. This supplies the new required association context to the existing scenarios; it does not weaken their financial, provenance, tenant, scope, quarantine, or idempotency assertions. These exact existing test functions consume those helpers, directly or through `link()`:

- `tests/test_ramp_credit_sync_v4.py::test_official_fields_unmatched_and_draft_are_not_attributed`
- `tests/test_ramp_credit_sync_v4.py::test_explicit_link_records_only_reciprocal_bill_amount_and_preserves_simulation`
- `tests/test_ramp_credit_sync_v4.py::test_cumulative_deltas_repeated_and_parallel_delivery`
- `tests/test_ramp_credit_sync_v4.py::test_parallel_link_is_idempotent`
- `tests/test_ramp_credit_sync_v4.py::test_exact_binding_fields_required`
- `tests/test_ramp_credit_sync_v4.py::test_no_synthetic_award_or_bill_created_from_provider_observation`
- `tests/test_ramp_credit_sync_v4.py::test_conflicts_durably_quarantined_without_ledger_mutation`
- `tests/test_ramp_credit_sync_v4.py::test_decrease_after_link_preserves_previous_history_but_never_current_confirmation`
- `tests/test_ramp_credit_sync_v4.py::test_removed_applied_bill_is_a_decrease_even_if_total_is_unchanged`
- `tests/test_ramp_credit_sync_v4.py::test_archive_and_unknown_bill_state_cannot_link`
- `tests/test_ramp_credit_sync_v4.py::test_archived_after_link_quarantines_new_confirmation`
- `tests/test_ramp_credit_sync_v4.py::test_sparse_inputs_are_unknown_not_zero`
- `tests/test_ramp_credit_sync_v4.py::test_scope_string_and_empty_list_are_genuine_zero_records_not_zero_claims`
- `tests/test_ramp_credit_sync_v4.py::test_unavailable_partial_stale_future_no_confirmation`
- `tests/test_ramp_credit_sync_v4.py::test_late_compatible_readback_does_not_add_again`
- `tests/test_ramp_credit_sync_v4.py::test_duplicate_ids_conflicting_payload_and_tenant_isolation`
- `tests/test_ramp_credit_sync_v4.py::test_capacity_failure_rolls_back_credit_post_and_binding`
- `tests/test_ramp_credit_sync_v4.py::test_unmatched_provider_applications_also_consume_capacity`
- `tests/test_ramp_credit_sync_v4.py::test_replay_cannot_be_relabelled_as_native`
- `tests/test_ramp_credit_sync_v4.py::test_non_usd_observed_without_currency_conversion_or_allocation`
- `tests/test_ramp_credit_sync_v4.py::test_durable_minimized_history_and_offline_cli`
- `tests/test_ramp_credit_sync_v4.py::test_all_bindings_rollback_together_on_later_projection_failure`
- `tests/test_ramp_credit_sync_v4.py::test_sparse_bill_scope_can_be_observed_but_cannot_link`
- `tests/test_ramp_credit_sync_v4.py::test_malformed_application_fails_without_cli_payload_echo`
- `tests/test_ramp_credit_sync_v4.py::test_explicit_foreign_tenant_is_rejected`
- `tests/test_ramp_credit_sync_v4.py::test_draft_migration_to_bill_does_not_double_total`
- `tests/test_ramp_credit_sync_v4.py::test_new_valid_looking_read_cannot_silently_clear_archive_conflict`
- `tests/test_ramp_credit_sync_v4.py::test_late_conflict_cannot_be_hidden_by_newer_observation_time`

The test helper scope is authored evidence, not authentication or real customer identity. The new migration tests deliberately omit that field and retain historical immutable row shapes.

## New tests and executed checks

The new `tests/test_ramp_credit_scope_v72.py` contains 32 parameterized cases across these exact functions:

- `test_cross_business_same_ids_reject_and_leave_prior_application`
- `test_parallel_first_pin_race_admits_exactly_one_business`
- `test_unscoped_advance_after_scoped_link_is_factual_but_never_projects`
- `test_latest_unscoped_observation_blocks_new_link`
- `test_unscoped_only_tenant_cannot_pin_or_link`
- `test_legacy_nonempty_evidence_without_bindings_freezes_scoped_projection`
- `test_legacy_binding_and_ledger_amounts_retained_never_advanced`
- `test_empty_legacy_observations_do_not_block_scoped_link`
- `test_legacy_duplicate_digest_and_unknown_scope_preserved`
- `test_invalid_business_types_and_zero_uuid_rejected_before_storage`
- `test_business_uuid_is_normalized_and_null_is_unknown`
- `test_missing_or_wrong_binding_scope_cannot_link`
- `test_projection_defensively_requires_exact_explicit_business`
- `test_receipt_history_summary_source_custody`
- `test_linked_zero_application_remains_zero`
- `test_workspace_adapter_passes_known_business_and_omits_unknown`
- `test_workspace_import_persists_business_through_credit_projection`
- `test_workspace_zero_business_rejects_before_partial_installation`

The actual Opus delegate authored the initial 30 cases. The lead extended immediate import receipt expectations and added `test_workspace_import_persists_business_through_credit_projection` and `test_workspace_zero_business_rejects_before_partial_installation`. Final focused sync/ledger checks: **134 passed in 3.15 seconds**. Adjacent workspace/award checks: **120 passed, 1 existing deprecation warning in 9.07 seconds**. The delegated patch before those two integration tests also passed 132 checks; no failed test run is omitted. Pre-change baseline: `test_ramp_credit_sync_v4.py` and `test_allocation_ledger.py`, 102 passed in 2.60 seconds. The pre-fix authored reproduction showed foreign-business import advancing 200 applied minor units to 500; that failed behavior is retained outside Git in `review/decision72/baseline-reproduction.json`.

[Decision and limits](decisions/ADR-0072-ramp-credit-business-scope.md)
