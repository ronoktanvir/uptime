# Test changes, W4 increment 89h: assignment item 8 through the ordinary intake path

Branch `work/dispute-adversarial-89h`, based on `work/integration-90` at `3758164`. It adds one test file and changes no application code and no existing test.

## Item 8 coverage map

"Ordinary intake path" means HMAC-signed source deliveries on the mounted `POST /api/correspondence/claims/{id}/events` route, and signed reviewer requests on the mounted case, interpretation and `denial-acceptance` routes.

| Category | Already covered | Added here (`tests/test_correspondence_adversarial_http_89h.py`) |
|---|---|---|
| Repeated replies | `test_correspondence.py::test_clone_concurrent_retry_restart_and_source_replay`, `::test_substantive_contradictory_vendor_response_and_exact_alias` (desk); `test_correspondence_resource.py::test_replies_are_bound_to_latest_observed_filing_and_exact_predecessor` (HTTP); `test_release_probes_gent8.py::test_socket_injected_reply_duplicate_delivery_and_replay_create_no_money` (socket) | `test_repeated_and_conflicting_replies_after_an_accepted_denial`: after an explicit acceptance, an identical reply under a new event id adds nothing; a reused event id with new content gets 409; a different reply reopens to `HUMAN_REVIEW` with the acceptance kept as history |
| Contradictory evidence | `test_correspondence.py::test_later_contradictory_evidence_freezes_award_without_erasing_receipt`; 89 desk tests; 89b intake refusals | `test_contradictory_notice_reopens_an_accepted_denial_without_money` |
| Stale authority | `test_release_probes_gent8.py::test_socket_authority_attacks_are_refused_without_state_change` and `::test_socket_source_change_after_approval_blocks_submission`; `test_source_config_v4.py` rotation/revocation; 89/89f desk tests | `test_new_evidence_stales_the_basis_a_reviewer_saw`: a stale basis digest gets 409, an unauthenticated acceptance gets 401/403, and only the current digest closes |
| Injected vendor text | `test_correspondence.py::test_unknown_injection_ambiguous_overaward`, `::test_recognized_cue_cannot_hide_additional_material_language`; gent8 socket probe | `test_injection_behind_a_recognized_request_creates_no_money_scope_or_closure`: a recognized cure request followed by agent-directed instructions changes no money, scope or submissions, escalates, and cannot be closed; the trace keeps the text verbatim |
| Out-of-order messages | `test_correspondence_resource.py` (unknown or superseded receipt gets 409); 89 desk order test (reviewed path) | `test_familiar_maintenance_denial_is_order_independent_and_closes_only_on_acceptance[reply_first, notice_first]` (finite-grammar path under D06); `test_reply_before_filing_and_evidence_for_an_unknown_claim_are_refused_without_effect` |
| Uncertain delivery | `test_disputes.py` retry/transport tests (legacy desk); `test_cross_claims.py` reservation; `test_correspondence_model_jobs_75.py::test_uncertain_after_candidate_commit_is_correlated_and_never_retried`; 89 desk test | `test_uncertain_inbound_and_outbound_delivery_is_idempotent_and_never_resent`: a sender's retry with a fresh signature returns the original receipt and leaves state unchanged; changed content under the same id gets 409; a repeated submit click yields the same single receipt; a vendor's "was it sent?" goes to a person; nothing is resent after the window |
| Model confidence cannot authorize money or scope | `test_correspondence_model_jobs_75.py::test_malformed_wrong_model_truncated_or_ungrounded_results_refuse[extra]`, `::test_award_and_conditional_candidates_stay_human_review_without_money`; 89 desk test (`confidence` on `Interpretation`) | `test_confidence_cannot_enter_a_reviewed_reading_on_the_signed_routes[partial, above-claim]`: `confidence` is refused (422) at the request, interpretation and proposition levels; a partial award is informational only; an award above the claim is not even reported; prepare gets 409 and the ledger is unchanged. `test_a_reviewed_scope_assertion_rebuts_but_never_changes_the_claim_scope`: the claim and supplement packet scope stay byte-identical. `test_model_output_carrying_confidence_is_refused_without_a_candidate[result, block, proposition]`: a provider result with `confidence` at any level is `REFUSED` with no candidate |

## Runs

- **First run: 2 failed, 11 passed.** Both failures were wrong expectations in the new test file, not product defects:
  1. The injection test compared the whole ledger. `disputed_remainder` legitimately moves from 0.00 while awaiting the vendor to the claimed amount once the case is in human review. The test now compares the money fields (estimated, claimed, awarded, posted, applied) and asserts the remainder equals the claim.
  2. The award test used "USD 41.74", which is above the 41.736 claim, so the reading is correctly not reported as an award at all. It is now parametrized: a partial "USD 20.00" is reported as 20.00 and informational, and the above-claim amount is reported as nothing.
- **Second run: 14 passed, 1 warning.**
- **Mutation check:** restoring the pre-D06 rule (only reviewed readings held for acceptance) made 5 of the new tests fail. The source was restored byte for byte.

Principals are scripted (`SCRIPTED_NOT_ACTUAL_HUMAN`), and the vendor texts are authored.

**D04-C note:** the file sets the Twilio scope in one fixture line. When claim-scope/1 drops `region` for the Twilio profile, only that line changes.
