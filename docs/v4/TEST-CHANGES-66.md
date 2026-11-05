# Test changes for the configured local workflow

Baseline: frozen Decision60/62 source `6fe3245`, with root integration `f83587f` merged before implementation. No pre-existing test was changed or renamed. New assertions do not replace old financial or authority controls.

`tests/test_northwind_local_ledger.py` adds 15 parameterized tests for the optional local-provider boundary. Exact new function names and purposes:

- `test_local_write_readback_and_allocation_are_distinct_durable_records`: posting persists separate provider and financial records; repeated writes and restart preserve one identity.
- `test_provider_crash_before_intake_commit_reuses_exact_record`: both write and readback crash windows leave no committed financial credit, and recovery reuses the surviving provider record.
- `test_wrong_readback_never_commits_posted_money`: incorrect UUID, tenant or hash refuses financial commit.
- `test_financial_validation_precedes_local_provider_write`: currency, scope and amount errors are rejected by existing allocation checks before the confirmation callback writes anything.
- `test_application_preserves_original_bill_and_exact_remaining_capacity`: repeated application leaves the original bill unchanged and uses the ledger's remaining capacity.
- `test_changed_provider_payload_is_refused_during_recovery`: deliberate test-only provider corruption cannot redefine the amount on restart.
- `test_provider_refuses_real_or_other_authority_bindings`: local provider configuration is unavailable to non-rehearsal, sandbox or other-tenant databases.
- `test_provider_rejects_shared_transaction_storage_and_new_instance`: provider persistence must be physically separate and remain bound to one workspace instance.

Initial receipt: `W/receipts/northwind-provider-001.log`, 15 passed. The mandatory postmerge full suite runs separately against `24dbed1`; later workflow tests and results will be appended without rewriting unsuccessful attempts. No test result certifies native Ramp activity or human authorization.

Provider allowlist follow-up adds exact scope and generic signed case-route tests (20 focused tests passed). The configured provider now pins the claim, bill and vendor/account/product/contract/currency at the shared Workbench entrypoints, including refusals through the existing generic action route. No pre-existing test changed.

The source-stable24dbed1 full run first had2698 passes and one environment failure because Node was absent from PATH. The unchanged rerun with explicit PATH passed2699 tests in134.83s. Both logs remain: W/receipts/northwind-24dbed1-full-{001,002}.log. Later projection and scope refinements require their own integrated run.
