# Test changes — submission design, November 9

Branch `work/submission-design-20261109`. This ledger lists every **existing** test that this branch changed: the exact name and the reason. Tests that were only added are listed separately at the end.

No change weakens a monetary, authority, idempotency or tenant assertion. Every amount that was asserted before is still asserted, as an exact string.

## Changed existing tests

| # | Test (exact name) | Change | Reason |
|---|---|---|---|
| 1 | `web/workspace_ui.test.cjs` › `activity shows the server automation record: state, pause, counts, authority and case-timeline times without durations` | The expected sentence reads "1 reviewer decision and 2 automatic steps recorded." instead of "1 person decision…". | Coordinator's correction: in the walkthrough the reviewer is a scripted test account, so the interface must not assert that a person decided. The count is still the server's `counts.person_decisions`, shown unchanged; only the noun is different, and each step still names its account ("Decided by scripted-test-reviewer"). |
| 2 | `web/workspace_ui.test.cjs` › `a stop for a person shows the server’s reason and detail, and the recovery panel links to the claim’s case` | The same noun in the expected sentence. | Same as #1. The pause reason ("Stopped for a person: …") is unchanged: it says what the next step needs, not who decided. |
| 3 | `tests/test_submission_ui_browser.py::test_automation_workspace_needs_four_person_decisions_and_activity_shows_every_step` | The expected sentence reads "Routine steps: Complete. 4 reviewer decisions and 7 automatic steps recorded." | Same as #1. The four-click count, the eleven steps and the three authority counts are asserted as before. |

## Added tests

None yet.

## Interrupted runs

None yet.
