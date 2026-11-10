# Test changes: submission steps (November 10, 2026)

Branch `work/submission-steps-20261110`. Browser-only change: the "Steps in order" legend and display-only replay on Activity (`web/workspace_ui.js`), and "What was filed" on the case page (`web/v4_ui.js`).

## Existing tests changed

None. No existing test file was edited, and no assertion about money, authority or what reached Ramp was touched.

One existing fixture now shows an extra sentence, but no assertion changed. In `web/workspace_ui.test.cjs`, the test "activity shows the server automation record: state, pause, counts, authority and case-timeline times without durations" sends server counts of 1 reviewer decision and 2 automatic steps. Its third step is `UNCERTAIN`, and the server counts an automatic step only once it has completed. So the new legend, which counts the steps listed, reports that the server's own counts differ. The test still passes unchanged.

## New tests

`web/steps_replay.test.cjs`:
- "recorded order is the server sequence; the replay group is the latest reviewer decision and the steps after it"
- "the legend counts equal the recorded steps and agree with the server’s own counts"
- "off by default: every step shows at once, nothing is scheduled and no request is added"
- "turned on, the next decision’s steps are shown one at a time in recorded order, then all remain"
- "Replay shows the whole list in recorded order; skipping or turning it off shows every step at once"
- "reduced motion: the replay still goes one step at a time but adds no animation class"
- "browser storage that refuses leaves the setting in memory for this page"

`web/filed_view.test.cjs`:
- "a filed claim prints exactly the packet’s own fields in plain labels"
- "the response adds only what its packet carries; an unmatched evidence digest is shown as its digest"
- "a field the server does not send is printed as not sent, never guessed; amounts stay exact"
- "the case page shows What was filed before the correspondence, from the record it already loaded"
