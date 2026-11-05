# Test changes for Decisions 60 and 62

Comparison baseline: `797c3d0`, before the interpretation bridge. **No pre-existing test function, assertion, expected result, or fixture was changed.** There are no renamed or weakened existing tests to enumerate. The original 32-case public fixture remains SHA256 `2c6823200964cf69a5802c6244d83af59fb0507f4817f133c8010369524ae8c8`; the original bare-mode request manifest remains unchanged. Private evaluator inputs were not inspected or used.

New test files:

- `tests/test_correspondence_interpretation.py`: source-locked manual review, authenticated HTTP integration, blind-entry visibility, complete byte spans, ambiguity, exact state/scope/terms/source/amount pins, stale/expired/tenant rejection, historical absent amount, inert awards, evidence-backed draft preparation, existing approval/submission, and model request allowlisting. Added packet assertions bind the accepted interpretation into the existing exact approval digest. The 26 preregistered varied amount/month controls test reviewed values, not natural-language prediction accuracy.
- `tests/test_correspondence_interpretation_ui.py`: actual Chromium rendering with a public mock API, no prechecked attestations, blind entry before suggestion display, and no award effect button. This is software behavior, not a human accuracy study. The test fixture received an explicit UTF-8 HTML charset after a first browser attempt exposed fixture decoding; expected application behavior was preserved. Input aria labels were corrected in production UI rather than weakening selectors.
- `tests/test_correspondence_model_transport.py`: environment allowlisting, bounded stdout/stderr, exact input delivery, process-group timeout/child cleanup, binary/profile mutation, unexpected tool/MCP activity, and owned-project persistence refusal. These local tests do not use provider credentials.

The public mutation runner `scripts/mutate_correspondence_interpretation.py` copies the candidate into isolated directories. Nine mutations remove context equality, complete-text coverage, full proposition coverage, exact quote checks, request allowlisting, preparation permission, compound refusal, replay binding, or blind-before-preview. All nine were detected; the original source hashes matched before and after. Receipt: `W/tasks/dispute60-mutations-002/receipt.json`.

Preserved unsuccessful attempts: `dispute60-frozen-scope-001.log` selected a nonexistent source-config test filename and ran no tests; the corrected selection is separately recorded in `dispute60-frozen-scope-002.log`. Earlier public bare authentication refusals and safe control attempt001 are retained. No failed model output was repaired or retried under the same measurement.

Full integration verification belongs to the root after merging the independently changed onboarding/native sources. This branch's targeted results cannot be presented as a test of those later sources.
