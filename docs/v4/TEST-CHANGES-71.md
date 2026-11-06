# Test changes for decision 71

No pre-existing test is changed or removed by this workstream. Shared transport changes inherited from `3449bbe` are recorded separately in `TEST-CHANGES-69.md`. Frozen controls were committed before implementation (`303ebed`), and their expected outcomes are unchanged.

New tests validate a bounded source-block interface and preserve the distinction between structural compatibility, semantic mapping and financial authority. The handcrafted control annotations are not actual model or blind-evaluation results.

## tests/test_correspondence_blocks_71.py

- `test_blocks_split_only_at_lf_and_preserve_unicode_crlf_bytes`: blocks split only at lf and preserve unicode crlf bytes.
- `test_duplicate_text_gets_distinct_deterministic_ids`: duplicate text gets distinct deterministic ids.
- `test_strict_count_and_size_caps`: strict count and size caps.
- `test_proposition_bounds_come_from_existing_types`: proposition bounds come from existing types.
- `test_gaps_duplicates_unknown_and_order_are_rejected`: gaps duplicates unknown and order are rejected.
- `test_courtesy_cannot_hide_substantive_text_and_role_counts_are_strict`: courtesy cannot hide substantive text and role counts are strict.
- `test_selectors_require_exact_quote_occurrence_within_their_block`: selectors require exact quote occurrence within their block.
- `test_slot_token_prefix_attacks_are_rejected`: slot token prefix attacks are rejected.
- `test_whole_slot_tokens_are_accepted`: whole slot tokens are accepted.
- `test_hydration_equals_hand_built_byte_spans`: hydration equals hand built byte spans.
- `test_structural_validity_is_not_semantic_validity`: structural validity is not semantic validity.
- `test_default_disabled_never_invokes_provider`: default disabled never invokes provider.
- `test_exact_allowlist_pins_text_schema_profile_and_domain`: exact allowlist pins text schema profile and domain.
- `test_request_is_public_scope_only_with_existing_budgets`: request is public scope only with existing budgets.
- `test_plain_mode_refuses_output_schema_profiles_without_fallback`: plain mode refuses output schema profiles without fallback.
- `test_enabled_adapter_hydrates_once_with_block_provenance`: enabled adapter hydrates once with block provenance.
- `test_hallucinated_or_extra_fields_reject_after_one_attempt`: hallucinated or extra fields reject after one attempt.
- `test_invalid_provider_results_reject_without_retry`: invalid provider results reject without retry.
- `test_eight_frozen_controls_with_handcrafted_semantics`: eight frozen controls with handcrafted semantics.

## tests/test_correspondence_literal_71.py

- `test_potentially_supported_mapping_refuses_unassigned_money_or_dates`: potentially supported mapping refuses unassigned money or dates.
- `test_literal_conservation_accepts_distinct_award_remainder_and_period`: literal conservation accepts distinct award remainder and period.
- `test_nonactionable_meanings_do_not_require_invented_financial_roles`: nonactionable meanings do not require invented financial roles.

The provisional structured-output test written during the initial uncommitted coding attempt was replaced before commit by `test_plain_mode_refuses_output_schema_profiles_without_fallback`, because the actual CLI probe exposed a tool invocation. This change strengthens refusal and does not alter an existing repository test.

Validation results will be recorded after the final source is frozen.
