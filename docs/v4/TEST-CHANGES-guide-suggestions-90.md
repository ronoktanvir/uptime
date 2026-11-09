# Test changes — suggested guide questions (W7, `work/guide-suggestions-90`)

The finance view's read-only guide now offers four one-click questions above the question box:

- What needs my attention?
- How was the January credit calculated?
- Why is March undetermined?
- Did the credit reach Ramp?

They form a labelled group ("Suggested questions"). A click fills the question box and asks through the same `POST /api/workspace/guide` route as a typed question. The buttons are disabled while an answer is loading, so a second click sends nothing. They appear only when the server supplies the finance summary. The guide's answers and its read-only behaviour are unchanged.

**No existing test changed.** The first layout put the suggestions between the question box and its answer. That changed the Tab order, and the merged `tests/test_finance_browser_90.py::test_attention_guide_keyboard_actions_and_expired_session_recovery` failed (1 failed, 50 passed). The suggestions were moved above the question box instead of editing that test.

New tests:

| File | Count | Purpose |
| --- | ---: | --- |
| `web/guide_suggestions.test.cjs` | 3 | Shows the labelled group of ordinary buttons. A click fills the question, asks once and renders the cited answer. A second click while loading sends nothing. No suggestions appear without the summary. |
| `tests/test_guide_suggestions_browser_95.py` | 1 | Live Chrome at 390 px: click and keyboard (Shift+Tab, Enter) answers, only guide POSTs, no workflow intent, no sideways scroll and no page errors. |

Results:

- JavaScript: **101/101**
- New browser test, existing finance browser, workspace UI, guide and view tests: **72 passed, 1 warning in 31.45s**

The prepared presentation listener runs the frozen demo build `fde492c`, which has no suggested questions, so the walkthrough says to type both questions there. Only a listener rebuilt from `9b9092f` or later offers the one-click suggestion.

Full suite: integration round 5 on a fresh clone of `6f43a91`, which contains `9b9092f` and `d580292`: **4663 passed, 1 warning in 322.05s (0:05:22)**, JS 101/101. Receipt: `docs/v4/evidence/integration-90/verification-6f43a91.json`.
