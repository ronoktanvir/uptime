# Test changes: `work/ramp-w1-followup-93`

**No existing test function, fixture or assertion was changed.**

## New tests in an existing file: `tests/test_ramp_workflow.py`

Seven functions were appended unchanged from the unmerged branch `remediate/native_workflow` (`c61c384`). Before the fix, on integration `a3bfefc`, three failed:

- `test_uncertain_prior_finding_cannot_be_bypassed_with_new_finding`: `DID NOT RAISE WorkflowError`.
- `test_stored_plan_tampering_detected_before_dispatch`: `DID NOT RAISE WorkflowError`.
- `test_reset_receipt_does_not_rewrite_prior_delivery_history`: `KeyError: 'trigger_current'`.

These four passed before the fix and are kept as regression controls: `test_concurrent_workers_dispatch_at_most_once`, `test_process_crash_after_remote_write_keeps_durable_uncertainty`, `test_existing_exact_dedup_marker_prevents_post` and `test_conflicting_remote_marker_requires_manual_resolution`.

After `16ca1a4`, the file passes: 49 passed.

## New file: `tests/test_ramp_workflow_http.py`

Added unchanged from `c61c384`: 14 functions, 25 cases of mock-HTTP contract tests for the outbox transport. A probe run against current code passed all 25 before they were added. I had first assumed the adapter had been restructured; this run showed it hadn't.

## New file: `tests/test_ramp_prefilm_check.py`

12 cases. Ramp responses come from a read-only test double through the real installation, records and lineage code; no credentials, network or writes are used.

- `test_unchanged_bill_and_reobserved_note_pass_with_reads_only`
- `test_changed_demo_facts_fail`, 4 cases: note missing, amount changed, credit applied, credit created from the bill
- `test_status_change_and_new_comment_are_warnings_not_failures`
- `test_other_business_fails`
- `test_main_writes_one_owner_only_receipt_and_summary`
- `test_main_refuses_before_loading_credentials`, 4 cases: CI set, output inside the repository, group-readable directory, missing directory

Failed first attempt: the status-change test first "changed" the approval status to the value the shared fixture already used. Its next version raised a keyword collision. The fixture now defaults the demo bill to `PENDING`, as on the real bill.

## New file: `tests/test_ramp_credit_readback.py`

13 cases for the D09 read-back (`credit_links` and `scripts/ramp_credit_readback.py`):
- an observed zero on a complete read;
- both-sided applications counted without attribution;
- three one-sided or conflicting states;
- a credit missing from the active list, and an incomplete list (both unknown);
- a credit created from a paid bill;
- another vendor's credit on the bill;
- an unobserved bill and an invalid ID;
- one owner-only report from a pre-filming receipt, with no overwrite;
- refusal of an unverified or stale association.

All passed on the first run.

## Results

- `tests/test_ramp_prefilm_check.py` and `tests/test_ramp_case_lineage.py`: 71 passed.
- `tests/test_ramp_workflow_http.py`: 25 passed.
- Ramp, reconciliation, credit, operations-recovery, Northwind workflow and journey suites at `16ca1a4`: 1,143 passed, 1 warning in 309.37s.
- All `tests/test_ramp*.py` with these additions: 1,002 passed, 1 warning in 32.77s.
- `tests/test_ramp_credit_readback.py`: 13 passed.
- First real pre-filming run against the Ramp demo: `PASS` ([summary](evidence/ramp-lineage-93/prefilm-20261109T123606Z.json)).
- Full suite: to be run by the integration owner after merge.
