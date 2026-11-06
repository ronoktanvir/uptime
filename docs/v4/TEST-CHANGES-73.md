# Test changes: public proposal runtime 73

No existing test was changed or weakened. `tests/test_public_proposal_jobs.py` adds 35 cases covering concurrent duplicate suppression, restart recovery, cross-tenant/subject denial, exact request bindings, no provider calls from polling, safe error projection, invalid result refusal, expiry/revocation, daily reservations, explicit new attempts, protected artifacts and canonical byte handling.

Initial collection failed because a parametrized argument used pytest's reserved name `request`. Renaming that new test argument to `encoded` resolved collection without changing behavior or assertions. The next run reported **35 passed in 0.40s**. This is focused queue validation, not application integration or generalization evidence. Wrapper and signed HTTP tests are owned by workstreams 74 and 75. Required full integration tests remain pending until those merges.

The queue, pinned transport and source-block suites then passed **110 tests in 1.41s**, including private rejection-evidence retention with no public response leakage. No model inference occurred in these unit controls.
