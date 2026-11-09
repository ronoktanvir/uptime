# Test changes — evidence custody, decision 91

**No existing test function or assertion changed.** One new file adds 23 controls; one new read-only probe script records findings outside W5 ownership.

| File | Cases | Purpose |
|:---|---:|:---|
| `tests/test_evidence_applicability_91.py` | 23 | Inside/outside month per measured kind; boundary-spanning incidents; ±14-hour civil-zone margin edges; adjacent-month period reports in UTC, UTC−12 and UTC+14; boundary-crossing partial reports; nested resource, telemetry, exclusion, maintenance and request rows; complete-before-end refusal; timestamp kinds deliberately not checked; signed grant still applying every prior scope check; mounted HTTP delivery refused with no stored row, followed by the correct record without a contradiction; delivery client naming the operator's record before contacting the listener; Opus falsification cases. |

New function names, in file order: `test_measured_interval_inside_the_month_is_admissible_and_entirely_previous_month_is_refused` (4 parameters), `test_month_boundary_overlap_is_left_to_the_evaluator_and_offset_months_keep_a_margin`, `test_coverage_report_for_another_month_is_refused`, `test_nested_resource_rows_must_describe_the_granted_month_and_their_own_report`, `test_monitor_records_outside_the_month_are_refused` (2), `test_customer_exclusion_spans_and_maintenance_windows_must_overlap_the_month`, `test_request_witness_outside_the_month_is_refused`, `test_a_complete_report_cannot_be_observed_before_its_period_ends` (2), `test_records_whose_timestamps_are_not_measured_service_time_are_not_refused_by_this_rule` (4), `test_signed_grant_refuses_wrong_period_but_still_applies_every_existing_scope_check`, `test_boundary_crossing_period_reports_keep_more_than_fourteen_hours_inside_the_month`, `test_decision_91_critique_falsification_cases`, `test_month_must_be_an_exact_granted_month`, `test_delivery_client_names_the_operator_record_before_signing`, `test_wrong_period_signed_delivery_is_refused_before_storage_and_cannot_block_the_correct_record`.

## Failed intermediate runs, preserved

1. First rule (all records against the widened month): `test_coverage_report_for_another_month_is_refused` failed — a whole September report overlapped the 14-hour margin and was admitted. Result: 1 failed, 20 passed. Corrected by checking period reports against the unwidened month.
2. Opus critique: the unwidened-overlap rule still admitted a UTC−12 September report. Corrected by requiring more than 14 hours inside the month.
3. That threshold refused the one-hour mid-month report in the **unchanged existing** `tests/test_source_config_v4.py::test_grant_validates_every_nested_resource_and_invoice_line`. Result: 1 failed, 260 passed, 1 warning in 145.67s. The rule was narrowed to boundary-crossing reports; the existing test was not edited.

## Focused results at `a924aae`

`uv run --locked pytest -q -p no:cacheprovider` over the new file plus `test_source_config_v4`, `test_correspondence_receipt_version`, `test_signed_mandates`, `test_blind_acceptance`, all four Northwind suites, `test_live_reviewer_setup`, `test_evidence`, `test_evidence_refresh`, `test_correspondence`, `test_v4_routes_integration`, `test_cross_claims`, `test_portfolio_v4` and `test_correspondence_resource`: **401 passed, 1 warning in 328.72s**. Northwind January/February/March outcomes and the USD 8,600 April balance are asserted by the unchanged workflow tests in that run. The mandatory full `uv run --locked pytest` runs after W0 integration; it is not claimed here. [Receipt](evidence/evidence-custody-90/verification-91.json)

If W4 applies the same rule at the embedded desk (finding F1/F2), its existing tests that deliver foreign nested rows or wrong-period records directly through the desk, including `tests/test_correspondence.py::test_mismatched_fee_and_component_prevent_further_packet`, would need to be listed in W4's own ledger.

## Decision 91a — real public status source

**No existing test function or assertion changed.** `tests/test_evidence_status_source_91a.py` adds 15 cases using the recorded official Twilio capture (`fixtures/evidence/twilio.json`):

`test_a_resolved_public_incident_becomes_one_exact_status_record_with_provenance`, `test_same_public_record_yields_the_same_event_identity`, `test_two_fetches_with_reordered_serialization_keep_one_event_identity`, `test_stale_or_future_snapshots_are_refused` (2), `test_wrong_vendor_incident_component_or_month_is_refused` (4), `test_unknown_or_unresolved_public_incidents_are_refused`, `test_missing_published_start_is_not_replaced_by_creation_time`, `test_an_incident_resolved_after_its_own_observation_is_refused`, `test_another_status_origin_is_refused`, `test_real_public_record_through_the_ordinary_signed_enrollment_path`, `test_operator_script_checks_role_and_joins_receipt_with_provenance`.

Preserved failure: the first version of the enrollment-path test expected a contradiction after a public edit while impact and billing records were still absent. The evaluator reports missing kinds before duplicates, so it returned "Awaiting an authenticated impact record". The test now adds authored impact and billing records from separately enrolled sources, and asserts the contradiction once all three kinds are present. Result before the correction: 1 failed, 14 passed.

W5 evidence suites (`test_evidence_status_source_91a`, `test_evidence_applicability_91`, `test_evidence`, `test_evidence_refresh`, `test_source_config_v4`): **75 passed, 1 warning in 5.01s** at `6d3536f`. Live rehearsal receipt: [public-status-live-91a.json](evidence/evidence-custody-90/public-status-live-91a.json).

## Document custody audit

**No existing test function or assertion changed.** `tests/test_evidence_custody_91.py` adds 9 cases. It reuses the existing `api` fixture and `install` helper from `tests/test_vendor_catalog.py` without changing them.

`test_installed_adapter_citations_re_slice_from_the_stored_source`, `test_tampered_or_detached_citations_are_reported` (5: changed text, shifted offsets, out-of-bounds offsets, altered quote, missing source text), `test_quote_digest_and_absent_citations_are_reported`, `test_audit_never_writes_and_an_empty_catalog_is_not_traceable`, `test_rows_still_in_the_write_ahead_log_are_disclosed`. Result at `7799f2e`: 9 passed, 1 warning in 2.90s. Read-only audit of the two demo workspaces: 77/77 citations traceable ([receipt](evidence/evidence-custody-90/document-custody-91.json)).

## Signed-path acceptance controls

**No existing test function or assertion changed.** `tests/test_evidence_acceptance_91.py` adds 7 cases through the mounted HTTP intake with real Ed25519 grants: `test_wrong_customer_evidence_is_refused`, `test_wrong_period_evidence_is_refused_and_cannot_block_the_correct_record`, `test_stale_or_premature_evidence_is_refused`, `test_a_complete_report_observed_before_its_period_ended_is_refused`, `test_tampered_evidence_is_refused` (pins the exact digest refusal reasons and admits a positive control), `test_tampered_public_snapshot_is_refused`, `test_reused_event_identity_with_different_content_is_refused`. Branch result at `7373318`: 7 passed, 1 warning. On a detached checkout of the merged head `23805c9`, together with the W5, correspondence, resource and Northwind workflow suites: **219 passed, 1 warning in 183.94s** ([receipt](evidence/evidence-custody-90/acceptance-merged-91.json)).

## D04-C compatibility of the public status source

`tests/test_evidence_status_source_91a.py` gains `test_grant_without_incident_or_component_is_refused` (2 parameters). Under D04-C a claim scope may omit incident and component, but a public incident record cannot, so the source now refuses such a grant by name. The two earlier cases in that file are unchanged; the file now has 17. Result with the acceptance file: 24 passed, 1 warning. agent1's uncommitted D04-C hunk in `source_config.event_in_scope` was read: it matches the agreed conditions, and the draft `Scope` omits absent optional fields from serialization.
