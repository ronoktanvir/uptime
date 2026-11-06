# Decision81 test-change ledger

New authored deterministic category/reviewer controls do not establish model extraction accuracy or actual-human review performance. Public76 files remain unchanged.

Existing test changes required by the explicit block request version update:

- `tests/test_correspondence_blocks_71.py::test_request_is_public_scope_only_with_existing_budgets`: expected version changes from source_blocks_v2 to source_blocks_v3. Budget, input-field, tool, privacy and exact-schema assertions remain unchanged.
- `tests/test_correspondence_blocks_71.py::test_enabled_adapter_hydrates_once_with_block_provenance`: expected representation changes from source_blocks_v2 to source_blocks_v3. Single provider call, identity, digest, source grounding and lack of semantic authority assertions remain unchanged.

The first stable worker-output run passed **61 tests**, one existing Starlette warning,5.15s. Parent then strengthened the new tests to require grounded UNKNOWN results, exact source/slot equality, the observed NEEDS_EVIDENCE preparation boundary, frozen historical-request refusal and verified-reference narrowing. Final frozen-source results and exact logs are recorded in `evidence/verification-81.json`.

## tests/test_correspondence_artifact_category_81.py

- `test_block_schema_description_carries_all_three_meanings_and_shape_is_unchanged`
- `test_guidance_labels_match_ui_labels_exactly`
- `test_current_request_names_v3_and_carries_guidance`
- `test_stale_request_bytes_and_old_allowlist_are_refused_before_provider`
- `test_missing_type_stays_null_and_reference_exact_without_autofill`
- `test_supplied_explicit_category_survives_grounding_unchanged`
- `test_negated_mixed_and_ambiguous_annotations_remain_unknown`
- `test_artifact_type_on_non_artifact_family_remains_unknown`
- `test_explicit_category_correction_needs_correct_verdict_and_grants_no_authority`
- `test_reference_only_reviewed_reading_remains_reviewable`
- `test_actual_frozen_v2_request_remains_preserved_but_current_runtime_refuses_it`
- `test_corrected_category_only_narrows_independently_verified_reference_match`

## tests/test_correspondence_artifact_category_ui_81.py

- `test_note_is_absent_before_blind_entry`
- `test_untyped_candidate_note_then_explicit_category_correction_keeps_source_and_ref`

Final source `e05864a121ab365e9d3374159d91c87c8fd0a2eb`: **312 passed**, one existing Starlette warning,13.09s. Browser was required; none skipped. No failed test run occurred in81. All source/tests remained frozen through the final run.
