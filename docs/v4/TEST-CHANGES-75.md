# Test changes for workstream 75

Existing test changed:

- `tests/test_correspondence_interpretation_ui.py::test_blind_entry_precedes_model_display_and_no_effect_is_inferred`: updates only the request button and proposal heading to ordinary product language. The request sequence, independent-reading order, unset review attestations and all financial/authority assertions remain unchanged.

New tests use authored public data and scripted reviewers. They do not establish actual human-review performance.

## test_correspondence_model_jobs_75.py

- `test_missing_service_provider_or_approval_and_absent_blind_never_enqueue_or_call`: missing service provider or approval and absent blind never enqueue or call.
- `test_approval_without_own_independent_reading_cannot_enqueue`: approval without own independent reading cannot enqueue.
- `test_request_hash_binds_source_scope_amount_profile_and_actor_target_context`: request hash binds source scope amount profile and actor target context.
- `test_submit_only_queues_then_separate_run_attaches_one_inert_exact_source_candidate`: submit only queues then separate run attaches one inert exact source candidate.
- `test_approval_export_contains_complete_initial_request_without_grant_authority`: approval export contains complete initial request without grant authority.
- `test_uncertain_after_candidate_commit_is_correlated_and_never_retried`: uncertain after candidate commit is correlated and never retried.
- `test_context_change_or_blind_expiry_while_pending_leaves_no_candidate`: context change or blind expiry while pending leaves no candidate.
- `test_malformed_wrong_model_truncated_or_ungrounded_results_refuse`: malformed wrong model truncated or ungrounded results refuse.
- `test_pure_parser_binds_request_bytes_to_current_context_and_matches_adapter`: pure parser binds request bytes to current context and matches adapter.
- `test_polling_is_scoped_to_owner_tenant_claim_and_kind`: polling is scoped to owner tenant claim and kind.
- `test_supported_candidate_still_needs_review_preview_prepare_and_existing_approval`: supported candidate still needs review preview prepare and existing approval.
- `test_award_and_conditional_candidates_stay_human_review_without_money`: award and conditional candidates stay human review without money.
- `test_model_jobs_api_requires_signed_reviewer_write_and_scopes_status`: model jobs api requires signed reviewer write and scopes status.

## test_correspondence_model_jobs_ui_75.py

- `test_permission_required_keeps_request_disabled_and_shows_exact_reference`: permission required keeps request disabled and shows exact reference.
- `test_complete_operator_request_is_readable_and_permission_refresh_never_submits`: complete operator request is readable and permission refresh never submits.
- `test_queued_running_success_shows_exact_source_and_requires_unprefilled_review`: queued running success shows exact source and requires unprefilled review.
- `test_refused_or_uncertain_job_adds_nothing_and_is_not_retried`: refused or uncertain job adds nothing and is not retried.

The new pure-parser test was corrected before its first commit: it checks context/prompt/schema/canonical-byte integrity, while the configured transport and exact operator-approved request bind the provider profile. The parser does not cryptographically attest provider execution.

Additional real shared-queue control:

- `tests/test_correspondence_public_queue_75.py::test_real_queue_releases_signed_write_lock_and_guards_current_source[False]`: the signed enqueue and another signed write return while inference is pending; completion attaches exactly one inert candidate and duplicate submission does not repeat inference.
- `tests/test_correspondence_public_queue_75.py::test_real_queue_releases_signed_write_lock_and_guards_current_source[True]`: a newer signed response invalidates attachment; the old interpretation context returns 409 and no candidate is stored.

The new source-change test initially assumed its interpretation view would remain readable. Two preserved runs reported one pass and one failure. The new test now requires the observed safe 409 closure and independently verifies zero candidate rows; production code and financial assertions were not relaxed. The two-case shared-queue rerun passed. Final focused stable-source verification is pending.
