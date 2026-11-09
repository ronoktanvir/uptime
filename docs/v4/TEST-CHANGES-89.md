# Test changes — decision 89: identity reproduction and financial coverage

**No existing test function, assertion, fixture, receipt or source file changed.** This increment adds two test files, one machine-readable matrix and three documents on branch `work/identity-pricing-89`.

## New tests

| File | Functions / cases | Purpose |
| --- | ---: | --- |
| `tests/test_identity_domain_89.py` | 8 / 23 | Characterizes the confirmed D03 identity-domain mismatch and the D04 universal-scope requirement. Replays the preserved `e86-01` and `e86-04` request bodies against current source. Pins the Northwind January degradation from ELIGIBLE 2400.00 to INSUFFICIENT_EVIDENCE when only the account representation changes. |
| `tests/test_financial_coverage_89.py` | 17 / 24 | Keeps the [coverage matrix](FINANCIAL-COVERAGE-89.md) honest: every row cites existing tests and enforcement symbols, every requested dimension has a refusal row, and the page lists exactly the machine rows. Adds boundary probes the audit found without a direct test, plus fixture-name independence checks for Northwind and every pricing demo case. |

Exact function names are in the files. These are new controls, not changes to accepted expectations.

## Probes that pin a debatable classification

These assert today's behaviour so any change is deliberate. None produces money; each is a review item in the [coverage matrix](FINANCIAL-COVERAGE-89.md#audit-result):

- `test_contradictory_product_scope_never_prices`: contradictory product scope is INSUFFICIENT_EVIDENCE, not UNSUPPORTED_RULE.
- `test_missing_evidence_outranks_an_unsupported_line_and_both_are_traced`: missing evidence outranks an unsupported line.
- `test_contradicting_account_observation_is_reported_as_missing_scope`: a contradiction is reported like an absent fact.
- `test_receipt_before_month_end_is_outside_window_and_at_month_end_is_timely`: a premature receipt is INELIGIBLE / OUTSIDE_WINDOW.

## Tests a D03 or D04 decision would change

All eight functions in `tests/test_identity_domain_89.py`, `test_contradicting_account_observation_is_reported_as_missing_scope`, and six existing tests are coupled to the pending identity and scope decisions. The full list, with the coupling for each, is in [identity and scope dependencies](IDENTITY-SCOPE-CONTRACT-89.md#tests-a-d03-or-d04-change-would-have-to-update). That is the migration cost the team should expect; none is changed here.

## Failed attempts, preserved

1. The first run of `test_negotiated_pricing_results_do_not_depend_on_fixture_names` failed in four of five cases with INSUFFICIENT_EVIDENCE, “Both party signatures required”. The test had renamed the agreement parties but not each version's signatories, so the renamed agreement was genuinely unsigned by its parties. This was a test-authoring error, not an engine name dependency. The fifth case passed only because both sides were already INSUFFICIENT_EVIDENCE. The rename now maps signatories consistently; the engine is unchanged.
2. `test_human_matrix_lists_exactly_the_machine_rows` failed first because the page did not exist yet, then because the review-item table repeated row IDs. The check now reads only the `## Matrix` section.
3. Two enforcement references in the draft matrix named nonexistent symbols (`compile_resource`, `evaluate_service_month`). They were found by inspection before the integrity test ran and corrected to `vendor_service_month.validate` and `vendor_service_month.evaluate`.

## Results

Focused results on this branch, with no source changes:

- `tests/test_identity_domain_89.py`: 23 passed in 4.17s.
- Both new files: 47 passed in 7.85s.
- Every test file cited by the matrix (14 files, including the two new ones): 618 passed, 1 warning in 12.71s. The warning is the existing Starlette `TestClient` import notice.

The full `uv run --locked pytest` result and the exact tested commit are recorded in [the verification receipt](evidence/identity-pricing-89/verification.json).
