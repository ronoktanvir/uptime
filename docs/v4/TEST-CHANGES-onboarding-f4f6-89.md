# Test changes: W3 reviewed-semantics batch (F4, F6)

Branch `work/onboarding-f4f6-89`, based on `origin/work/integration-90` at `36aa17e`. It lands with agent1's batched `vendor_terms.py` re-review (D03 name extension, F5, D04-C), so reviewed adapters are re-reviewed once.

## What changed

- **F4: a private filing amendment governs only from the calendar month it states.** D07 calendar-month matrix.
  - `FilingOverride.effective_from` is required. It must be the first day of a calendar month inside the overlay interval; otherwise binding refuses.
  - `vendor_terms.private_filing_days(overlay, month, default)` returns the amendment's window for months starting on or after that date. Earlier months keep the source rule. A missing or malformed date is unsupported, never defaulted.
  - Used by `vendor_eval.evaluate`, `vendor_resource_eval.deadline` and `vendor_requirements` drafts.
- **F6: the governing-terms evidence digest is labeled honestly.** The dispatched governing citation carries `evidence_verification: OPERATOR_SUPPLIED_UNVERIFIED`. Nothing verifies the digest against stored signed evidence, and no fixture changes.
- **Interface request to W0** (not changed here): `v4_routes.py` reads the override at lines 40, 48, 53 and 244. Its claim cutoff (line 244) must use `private_filing_days(overlay, scope.month, manifest["filing_days"])`. Its semantic fingerprints (40, 48, 53) should include `effective_from`. Until then, claim deadlines on that route ignore the amendment date.

## Changed existing tests

| Test | Reason |
|---|---|
| `tests/test_vendor_catalog.py::test_private_filing_amendment_changes_only_bound_account_scope` | The amendment fixture gains `effective_from = OVERLAY['effective_from']` (the whole interval, as before). All assertions are unchanged. |
| `tests/test_vendor_resource_period_scope_77.py::test_private_relative_override_cannot_replace_a_scoped_deadline` | The fixture gains `effective_from='2026-03-01'`, so the test still reaches its intended refusal ("calendar-day override") rather than a missing-field error. |

## Added: `tests/test_vendor_filing_override_f4.py` (9 tests)

Hand-computed windows: June 2026 keeps the 12-day source window (closes `2026-07-13T00:00Z`), and July uses the 19-day amendment (closes `2026-08-20T00:00Z`). Resource-month gives June `2026-07-10 18:00`, July `2026-08-19 18:00`. Also covered: mid-month, out-of-interval and malformed dates refuse; an undated legacy override is `UNSUPPORTED_RULE` at evaluation; the F6 label appears on a dispatched governing citation.

## Results

- New file: **9 passed**.
- The first broad run hung at 0% CPU in a browser test while another worktree's browser tests ran at the same time. It was stopped and its temp data deleted; the browser tests then passed alone (**15 passed**).
- Broad focused set run alone (all `test_correspondence*`, `test_vendor_*`, `test_onboarding*`, proposal-job, route, authority, semantic-projection, governing-fee and portfolio tests): **1912 passed, 1 warning in 121.37s**.
