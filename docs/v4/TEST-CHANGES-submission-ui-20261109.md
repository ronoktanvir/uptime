# Test changes — submission UI (role 4), November 9

Branch `work/submission-ui-20261109`. This ledger lists every **existing** test that this branch changed: the exact name, the commit and the reason. Tests that were only added are listed separately at the end.

No change weakens a monetary, authority, idempotency or tenant assertion. Every amount that was asserted before is still asserted, as an exact string, in the same or a narrower place.

## Changed existing tests

| # | Test (exact name) | Commit | Change | Reason |
|---|---|---|---|---|
| 1 | `web/finance_focus.test.cjs`: shared fixture `base` (used by all three tests in the file) | `d3ed656` | `claim` gains `month:'2026-01'` | The recovery heading is now derived from the claim month ("January recovery") instead of a fixed string. The tests still assert the same heading. |
| 2 | `web/finance_view.test.cjs` › `attention items, destination and calculation inputs render from the server summary only` | `d3ed656` | The expected caption changed from "Stages of the same credit" to "One credit, shown at each stage. The amounts are not added together." | Task 5: the four stage tiles became one five-step credit lifecycle. The non-additivity statement is kept and is now explicit. |
| 3 | `web/workspace_ui.test.cjs` › `Northwind renders separate exact stages, uncertainty and cited source records without classification chrome` | `d3ed656`, `bef1b70` | The count of 4 `article` tiles became the five lifecycle step labels plus two outcome cards. The shared `projection` fixture gains `finance.stages` and `finance.bill`, and the expected last label is the server's `Applied to bill`. | Task 3 (outcome headline) and the coordinator's ruling that the lifecycle renders only `workflow.finance.stages[]`, never values assembled in the browser. The amounts asserted (`$2,400.00`, `$0.00`, `$1,000.00`, "Not determined") are unchanged. |
| 4 | `web/finance_focus.test.cjs` › `after a recorded action, focus moves to the next offered step`, renamed `after a recorded action, focus moves to the recovery heading and never onto the next decision` | `cd2cfe4` | Asserts that focus is on the "January recovery" heading, not on the next button, and that the status reads "Recorded: … Next: …". | Judge finding: with focus on the next button, a held or repeated Enter approved every remaining step at about 0.3 s each. A person decision must need a deliberate key press. |
| 5 | `tests/test_finance_keyboard_95.py::test_keyboard_only_demo_path_keeps_focus_on_the_next_step`, renamed `test_keyboard_only_demo_path_needs_a_deliberate_tab_before_each_decision` | `cd2cfe4` | After each Enter it asserts: focus is on the heading; the intent count rose by exactly one; a second Enter records nothing; one Tab reaches the next step. It still runs every step by keyboard only at 390 px and checks the $8,600.00 balance and the guide. | Same as #4. The test is stricter: it now also counts intents after every step. |
| 6 | `tests/test_workspace_ui_v4.py::test_configured_workflow_keeps_evidence_money_and_original_navigation_reachable` | `46ab661` | Nav: asserts the four primary links (Overview, Cases, Agreements, Activity), that Ramp records is hidden until "More tools" opens, and that Ramp records, Case ledger and Integrations are then visible. The clause reference `NW-CSA-2026#4` is asserted hidden, then visible after opening "Cited clauses (1)". | Task 1 (four primary destinations, advanced tools under More) and task 6 (clause lists collapsed into inspectors). The money assertions (`$9,600.00`, `$1,000.00`, `$0.00`) and the Ramp records route check are unchanged. |
| 7 | `tests/test_workspace_ui_v4.py::test_workflow_action_uses_real_dom_collection_and_refreshes_server_state` | `46ab661` | The authored projection gains `finance.stages`. The `$2,400.00` check is scoped to the "Claimed" lifecycle step. | The lifecycle renders only the server's stages (coordinator ruling), and the same amount now also appears in the headline, so an exact page-wide text match is ambiguous. The exact request sequence assertion is unchanged. |
| 8 | `tests/test_workspace_ui_v4.py::test_result_quotes_and_decimal_equations_render_as_server_text_without_html_execution` | `46ab661` | Opens "Cited clauses (1)" before "Read clause". | Task 6: cited clauses are in a collapsed inspector. The quote-as-text, no-HTML-execution and decimal assertions are unchanged. |
| 9 | `tests/test_ramp_ui_v4.py::test_ramp_browser_navigation_and_read_only_plan` | `46ab661` | Opens "More tools" before clicking "Case ledger". | Task 1: Case ledger moved to the secondary group. The route and back-navigation assertions are unchanged. |
| 10 | `tests/test_finance_browser_90.py::test_attention_guide_keyboard_actions_and_expired_session_recovery` | `3f011de` | The expected guide sentence is now "…must be received before Mar 3, 2026, 00:00 UTC. It has not been filed." instead of the raw `2026-03-03T00:00:00+00:00`. | Task 7: instants inside sentences are shown as dates at the rendering boundary. The server answer is unchanged; `tests/test_finance_guide_90.py` still asserts the raw server text. |

The helper `live_workspace` in `tests/test_finance_browser_90.py` gained `**prepare_options` (`0c384f1`), forwarded to `setup.prepare`. Its default behavior and every existing caller are unchanged.

## Added tests (no existing test changed)

- `tests/test_finance_view_90.py`: `test_estimated_stage_stays_the_claim_months_amount_through_the_whole_flow` and `test_estimated_stage_stays_unknown_when_neither_source_has_an_amount` (`bef1b70`)
- `web/workspace_ui.test.cjs`:
  - `credit lifecycle and headline come only from the server finance projection, never from ledger fields` (`bef1b70`)
  - `activity shows the server automation record: state, pause, counts, authority and case-timeline times without durations` (`0c384f1`)
- `web/finance_focus.test.cjs`: `a repeated Enter or Space key event on a decision is suppressed; a fresh press is not` (`cd2cfe4`)
- `tests/test_finance_keyboard_95.py::test_a_held_enter_records_one_decision_only` (`cd2cfe4`)
- `tests/test_submission_ui_browser.py` (`46ab661`, `0c384f1`):
  - `test_workspace_name_is_the_same_whatever_page_opens_first`
  - `test_reload_keeps_reading_but_disables_actions_with_one_way_back`
  - `test_credential_file_can_be_dropped_on_the_sign_in_form_and_errors_name_the_file`
  - `test_four_destinations_fit_a_phone_and_the_overview_leads_with_the_outcome`
  - `test_automation_workspace_needs_four_person_decisions_and_activity_shows_every_step`
- `web/browser-contract.test.cjs`: `server stage labels render as sent; the browser never renames a state to hide its destination` (`d596979`)
- `web/workspace_ui.test.cjs`: `the recovery card labels the claim’s own stage and shows the credit’s latest recorded stage beside it` (`61a6fb0`)
- `tests/test_interpretation_uncertain_candidate_r4.py`: `test_uncertain_request_state_and_reason_sit_beside_its_validated_candidate` and `test_a_cleanly_completed_request_keeps_the_ordinary_candidate_label` (`f58e964`)
- `web/workspace_ui.test.cjs`: `a stop for a person shows the server’s reason and detail, and the recovery panel links to the claim’s case`
- `web/model_job_display.test.cjs`: `the denial job receipt shows only reported fields: return code, tool events, empty inventories, cost and session`
- `web/model_job_display.test.cjs`: `a denial model job shows the model the server reports and its latest time, in UTC, and nothing it does not report` (`6374478`)
