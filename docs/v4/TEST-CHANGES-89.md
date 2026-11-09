# Test changes — decision 89: identity reproduction and financial coverage

Two increments on branch `work/identity-pricing-89`:

1. **Characterization (`4ad4506`)**: no existing test, fixture, receipt or source file changed.
2. **D03-A implementation (this commit)**: one existing test changed, named in its section below. The decision-89 characterization tests that pinned the identity defect were replaced by invariants, as intended.

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

## D03-A implementation

### Existing test changed

**`tests/test_allocation_ledger.py::test_conflicting_duplicate_and_source_alias_cannot_double_count`**

- Before: the test asserted that whitespace-padded spellings (`" tenant "`, `" case-1 "`, `" award-1 "`, `" allocation-1 "`) replay as the same normalized identity.
- Why it changed: D03-A, confirmed 2026-11-09 and accepted in the decision-94 critique, requires the ledger to refuse such input rather than trim or NFC-normalize it.
- Now: those spellings must raise `ValueError`. Direct checks show padded and non-NFC account IDs are refused while a source-shaped `Cedar Orrery Studio` passes unchanged.
- Unchanged: exact replay is still idempotent, and every no-double-count and monetary assertion is as before, including 8,000 applied cents and the cloned application, credit, bill and award refusals.
- One of my draft values (`"acct-1\u0301"`) was wrong: an accent on a digit has no precomposed form, so that string is already NFC and correctly passes. It was replaced with the genuinely non-NFC `"Cafe\u0301 Nord"`.

### Decision-89 characterization tests replaced by invariants

These tests pinned the defect at `4ad4506` and were expected to fail under D03-A; they did, and were replaced:

| Replaced (at `4ad4506`) | Replacement invariant |
| --- | --- |
| `test_identity_validators_disagree_on_exact_source_values` | `test_every_account_and_agreement_entry_point_applies_the_same_bounded_rule`: 21 values × 12 entry points; all accept exactly `source-identity/1`. Also `test_ramp_terms_agreement_accepts_the_shared_rule_and_keeps_legacy_references`. |
| `test_onboarding_accepts_identities_that_claim_intake_or_claim_key_cannot_represent` | `test_accepted_identities_are_never_rewritten` and the entry-point invariant above. |
| `test_recorded_claim_intake_refusals_reproduce_on_current_source` | `test_recorded_requests_no_longer_refuse_their_exact_source_identities`: the preserved e86 bodies remain immutable; their account and contract refusals no longer occur. Missing component, incident, region and invoice remain until D04. |
| `test_spaced_onboarded_account_is_stranded_before_claim_and_governing_fee` | `test_spaced_source_account_keeps_the_same_northwind_economics` (January stays ELIGIBLE 2400.00 with the same fee and steps) and `test_another_accounts_fee_context_is_still_never_borrowed`. |
| `test_trailing_space_account_passes_onboarding_but_not_economic_identity` | `test_padded_or_irregular_accounts_are_refused_at_onboarding_intake_and_filing`. |

The three D04 characterization tests in that file are unchanged.

### New tests

- `tests/test_source_identity_89.py` (5 functions, 37 cases), covering:
  - the versioned rule;
  - a property test that every legacy restricted identifier is accepted byte-identically;
  - refusal codes;
  - a property test that acceptance equals the documented predicate, and that every accepted value also satisfies the claim-key rule.
- `test_case_or_spacing_variant_cannot_file_the_same_obligation_twice` (4 cases): the guard refuses with `NearDuplicateIdentity`. HTTP routes map `ValueError` to 409. No override path exists.
- `test_distinct_obligations_and_exact_retries_are_not_blocked` (3 cases).

Coverage matrix: `IDS-D03-1` and `IDS-D03-2` are now SUPPORTED, `IDS-D03-3` (REFUSED_AT_FILING) is added, and `STP-BAS-1` now cites the fee-context non-borrowing test.
