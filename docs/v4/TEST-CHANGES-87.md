# Test changes — person-operated demo path

No existing test function, financial expectation, authorization assertion or provenance assertion was changed or removed. Two existing test files gained new functions:

| New function | Why it was added |
|---|---|
| `tests/test_northwind_workflow.py::test_result_calculations_use_current_evaluator_and_citations_keep_original_bytes` | Verify readable arithmetic comes from the current source-bound evaluation, remains exact under a low ambient decimal precision, preserves clause bytes/hashes/offsets and disappears when authority is revoked. |
| `tests/test_workspace_ui_v4.py::test_result_quotes_and_decimal_equations_render_as_server_text_without_html_execution` | Verify exact server-formatted large amounts, safe literal rendering of source text, expandable clauses and a missing March amount without browser floating-point calculations. |

New `tests/test_live_reviewer_setup.py` adds 15 parametrized cases for SHADOW-only scripted preparation, distinct named enrollment, denied promotion without release, signed lifecycle under a test-only mocked release, revocation without an audit mutation, resume/history/key preservation, changed source/unsafe path refusal, safe CLI metadata and public-key-only enrollment. These tests do not establish actual human review. No production flag substitutes a mocked release.

New `tests/test_ramp_comment_readback.py` adds 104 parametrized cases for exact two-read matching, a match on the final page, empty/ambiguous discussions, an explicitly selected comment ID, business/bill/scope mismatch, unsafe or incomplete pagination, duplicate IDs, malformed records, changed ID/body/author/time, fixed safe errors, protected new receipt files and a resource-GET-only transport spy. OAuth token exchange is expected; no comment or bill mutation is allowed.

The first run of the new read-back tests returned **2 failed, 102 passed in 0.18s**. Both new uppercase-UUID controls used digits-only fixture IDs, so uppercasing changed nothing. Root corrected the new fixture IDs to include hexadecimal letters; the tests then returned **104 passed in 0.13s**. No application check or old assertion was weakened. Root also corrected receipt prose so it does not assert personal authorship from an API read. The original Opus completion response is preserved alongside these corrections.

Focused results before integration: teammate setup15 passed, 1 warning in 1.20s; combined setup/Northwind/release84 passed, 1 warning in 72.63s; financial/presentation109 passed, 1 warning in 65.49s; JavaScript workspace: 9 passed. The integration's required full locked suite and 75 JavaScript checks are recorded in [the verification receipt](evidence/demo-path-87/verification.json). Passing these tests does not complete release authorization or demonstrate unseen-vendor/dispute generalization.
