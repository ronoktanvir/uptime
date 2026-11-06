# Decision80 test changes

No preexisting test, public source, staged proposal, frozen evaluation input/gold/result or native qualification file changed. New controls are in `tests/test_vendor_fixed_filing_80.py`; all inputs are authored public text. Scripted meaning reviews and local verified-evidence fixtures are not actual human or provider authority.

## What the controls establish

The tests bind the claim obligation, exact UTC literal, comparator and optional same-sentence relative day count; preserve the three known valid blocks; and distinguish a recipient from an actual comparator. They refuse no-deadline, negation, conditional/exception, contradictory suffix/companion, borrowed relative clocks, multiple timestamps and unconsumed material both directly and through aggregate compilation. Every direct refusal preserves the input manifest. Conflicting stored days/deadlines refuse atomically; repeated identical assertions are idempotent.

Full compile/evaluation controls verify before/equal/after behavior for inclusive and exclusive cutoffs. Their independent financial literal is unchanged: 300 unavailable minutes out of 43,200 puts availability below 99.5%; a 10% rate on 10,000 cents yields 1,000 cents ($10.00). The original contradictory clause must fail compilation before producing any eligibility preview. Four lead-added singular/plural claim controls preserve ordinary wording without weakening qualification checks.

Exact new test functions:

- `test_known_blocks_are_the_authored_compatibility_sources`
- `test_three_known_blocks_bind_cutoff_comparator_and_same_sentence_days`
- `test_explicit_comparator_table_and_finite_companions`
- `test_relative_days_with_exclusive_endpoint_and_calendar_unit_are_same_sentence_only`
- `test_unsupported_or_contradictory_filing_blocks_refuse_without_mutation`
- `test_refused_filing_blocks_never_compile_an_aggregate_source`
- `test_keyword_gate_accepted_bug_negation_and_recipient_forms_that_now_refuse`
- `test_malformed_proposals_and_non_utc_timestamps_refuse_without_mutation`
- `test_repeated_identical_validation_is_idempotent`
- `test_identical_absolute_assertion_without_days_keeps_established_days_in_either_order`
- `test_conflicting_stored_filing_or_days_refuse_atomically`
- `test_conflicting_repeated_relative_count_refuses_atomically`
- `test_documented_bug_block_refuses_compilation_before_any_eligibility_preview`
- `test_known_compass_and_april_sources_compile_with_unchanged_citation_and_clock`
- `test_inclusive_compiled_cutoff_before_at_and_after`
- `test_exclusive_compiled_cutoff_before_at_and_after`
- `test_compiler_relative_days_consistency_is_preserved`
- `test_singular_and_plural_claim_obligations_keep_exact_comparator_binding`

## Verification history

- Unchanged base `c5dd4e4`: aggregate service, Decision77 period/scope and correspondence service checks: **141 passed, 1 existing Starlette/httpx warning in 5.67s**.
- Preliminary new controls: **177 passed in 0.28s**. No failing model or test attempt occurred in the implementation run. Both actual model processes completed exit 0; full startup-spooled streams are protected outside Git.
- Final focused checks at source freeze `b009c3323f41309622ba236fffe579e29c89c003`: **352 passed, 1 existing warning in 76.90s**, including all Northwind workflow tests. Unchanged public intake succeeded. Heliograph, April and CalyxQuay compiled manifests are byte-identical under canonical JSON serialization. The original bad aggregate source now refuses with `Block 8 field fixed_filing: Source does not establish the stated filing cutoff and comparator.` [Exact command, hashes and comparison receipt](decisions/reviews/80-focused-verification.json). Source remained unchanged afterward. Root owns the combined integration suite.

One initial baseline probe used the host Python without pytest and failed before loading the control; it was rerun with the project virtual environment. No source or expected result changed. The first worktree command used the user workspace container directory rather than the repository and was refused; worktree creation succeeded from the existing repository. These setup errors are unrelated to validator behavior.
