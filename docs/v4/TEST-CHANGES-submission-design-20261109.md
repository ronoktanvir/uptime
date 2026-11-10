# Test changes — submission design, November 9

Branch `work/submission-design-20261109`. This ledger lists every **existing** test that this branch changed: the exact name and the reason. Tests that were only added are listed separately at the end.

No change weakens a monetary, authority, idempotency or tenant assertion. Every amount that was asserted before is still asserted, as an exact string.

## Changed existing tests

| # | Test (exact name) | Change | Reason |
|---|---|---|---|
| 1 | `web/workspace_ui.test.cjs` › `activity shows the server automation record: state, pause, counts, authority and case-timeline times without durations` | The expected sentence reads "1 reviewer decision and 2 automatic steps recorded." instead of "1 person decision…". | Coordinator's correction: in the walkthrough the reviewer is a scripted test account, so the interface must not assert that a person decided. The count is still the server's `counts.person_decisions`, shown unchanged; only the noun is different, and each step still names its account ("Decided by scripted-test-reviewer"). |
| 2 | `web/workspace_ui.test.cjs` › `a stop for a person shows the server’s reason and detail, and the recovery panel links to the claim’s case` | The same noun in the expected sentence. | Same as #1. The pause reason ("Stopped for a person: …") is unchanged: it says what the next step needs, not who decided. |
| 3 | `tests/test_submission_ui_browser.py::test_automation_workspace_needs_four_person_decisions_and_activity_shows_every_step` | The expected sentence reads "Routine steps: Complete. 4 reviewer decisions and 7 automatic steps recorded." | Same as #1. The four-click count, the eleven steps and the three authority counts are asserted as before. |
| 4 | `web/vendor_history.test.cjs` › `a rolled-back adapter says nothing is active and separates scripted preparation from account actions` | The two exact counts (5 scripted, 4 under an account) are now taken inside the review history list. Added: the summary in view names each label exactly once with its number of steps, the whole page therefore holds exactly 6 and 5, and the card says "Not in force." The shared `render` helper returns the root instead of its text. | Agreements now states who performed the review steps in view and keeps the full history one click away. The summary repeats each label once, so a whole-page count of 5 and 4 no longer describes the page. The assertion is stricter: rows and summary are counted separately and both exactly. |
| 5 | `web/vendor_history.test.cjs` › `an active adapter names its version; other states are stated plainly` | Also asserts "In force in this workspace." for the active adapter and "Not in force." for the shadow one. | The card now says in plain words whether the agreement is in force. The three original sentences are asserted unchanged. |
| 6 | `tests/helpers/render_requirements.cjs`, the helper behind `tests/test_requirements_card_ui_95.py::test_real_monthly_requirements_render_every_element_requirement_and_draft_read_only` | The helper presses "Show review requirements" only when the control exists, and fails if no requirements card is shown. | A vendor whose detail carries a source manifest has its requirements read with it and shown on its card. The Python test is unchanged and still asserts exactly three GETs, every element, the cited quotations in order and the read-only sentence. |
| 7 | `tests/test_advanced_companion.py::test_signed_wizard_refresh_routes_and_mobile` | Opens "Add an agreement" before waiting for "Stage local candidate" (three places, through the shared `login` helper and after a reload), opens "Review tools, version actions and the full record" before waiting for "Submit independent tests", and expects the `#disputes` page heading "Cases" instead of "Correspondence & disputes". | Forms and tools now sit in closed sections, one click away, and the Cases page is titled with its navigation name; "Correspondence & disputes" remains on the page as its context line. Every request, write count and route assertion is unchanged. |
| 8 | `tests/test_advanced_companion.py::test_viewer_and_disabled_gate_are_read_only` | Uses the same `login` helper, which now opens "Add an agreement". | Same as #7. The disabled and enabled assertions are unchanged. |
| 9 | `tests/test_contract_job_card_r4.py::test_job_card_keeps_digests_one_click_away_and_clauses_in_view` | Opens "Add an agreement" before using the proposal form, and expects the job card labels "Status" and "Model" instead of "status" and "model". | The proposal form is in a closed section, and the job card now uses the same capitalised labels as the rest of the interface. The closed "Request details", the absence of any 64-character value in view, every quotation and the four digests one click away are asserted as before. |
| 10 | `tests/test_vendor_model_jobs_browser.py::test_browser_checks_permission_generates_and_stages_separate_overlay` (all three parameters) | Opens "Add an agreement" before the form and "Review tools, version actions and the full record" before waiting for "Submit independent tests". | Same as #7. Provider call counts, the staged overlay and the SHADOW state are asserted as before. |
| 11 | `tests/test_vendor_auth83.py::test_expired_browser_session_recovers_same_job_without_resubmitting` | The same two openings, through its `login` helper and before the final wait. | Same as #7. The job identity, the single POST counts and the expired-session assertions are unchanged. |
| 12 | `tests/test_workspace_ui_v4.py::test_configured_workflow_keeps_evidence_money_and_original_navigation_reachable` | The test's stand-in server also serves `/static/InterVariable.woff2`, read from disk as bytes with the type `font/woff2`. | The page now loads its typeface from the app itself. This test serves the page's own files from a fixed list and fails on any other request, so the font joins the list. The list of unexpected requests is still asserted empty, and every evidence, money and navigation assertion is unchanged. |
| 13 | `tests/test_ramp_ui_v4.py::test_ramp_browser_navigation_and_read_only_plan` | The same addition to its stand-in server. | Same as #12. Its content security policy header, the single navigation, the request list and the read-only plan assertions are unchanged; the font loads under that policy. |

The helper `open_section(page, title)` and the two section titles were added to `tests/test_vendor_model_jobs_browser.py` and `tests/test_advanced_companion.py`. It clicks a section's summary only when the section is closed.

## Added tests

- `web/ramp_bill.test.cjs` (the one-bill page for the panel beside Ramp):
  - `the verified bill shows what Ramp holds, what Uptime found and the person-posted note, from one read`
  - `a bill found only in the saved worklist shows that worklist’s own statement and a scenario is never its finding`
  - `an unknown, empty or malformed bill id says so in one sentence and offers Ramp records`
  - `a bound agreement and an attachable finding are stated as such; other bindings are never called bound`
  - `a failed read shows no bill and an expired session propagates to sign-in`
- `web/browser-contract.test.cjs`: `the one-bill route makes one request, the saved Ramp workspace, and never reads the workflow projection`
- `tests/test_ramp_bill_panel.py`:
  - `test_the_verified_bill_card_is_in_the_first_viewport_of_a_420_px_panel`
  - `test_an_unknown_bill_says_so_and_ramp_records_opens_without_filling_the_panel_with_navigation`

The pass over every page on a computer screen (`1dca1cf`, `53f6115`) changed no test. Neither did the icons. The typeface changed two (rows 12 and 13).

## Interrupted runs

None before the first merge: no Chrome run hung and no test run was cut off by its time limit.

After it, one. A full run of this session's own, unpushed merge `618cc8e` printed nothing after 14 percent (`tests/test_contract_job_card_r4.py`, the first browser launch) and was cut off by the 30-minute limit, with no test failed before that point. The rerun finished with 5,400 passed. Details are in [the design record, section 6](submission/design.md).

One run of the per-file loop was invalid and is not counted: its scratch parent folder did not exist, so every test that uses `tmp_path` errored at setup within about a second. It was rerun with the folder in place; that rerun is the table in [the design record, section 6](submission/design.md).
