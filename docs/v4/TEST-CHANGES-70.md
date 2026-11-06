# Decision70 test-change ledger

No existing test file or assertion was changed. `tests/test_vendor_step_proposals.py` is new and checks exact compiler/proposal equivalence, unchanged source offsets/digests, strict wire mutations, legacy normalized and tier acceptance, exact financial vectors, current governing-fee authority, and the normal shadow/review/activation/dispatch/rollback lifecycle.

Preimplementation control freeze: `b2edd35`, `fixtures/opus70_public/freeze.json`. These are authored public controls, not blind or heldout results. `before.json` retains the original proposal-format rejection. Existing compiler acceptance does not establish that the model flow could represent the rule.

Native validation of the actual worker's initial test file: 127 passed, 7 failed. All failures arose from its new `billing_scope` helper omitting required `Scope.component` and `Scope.incident`. The parent supplied explicit test-authored identifiers in that helper; no frozen data, monetary expectation, authority condition or assertion changed. The affected new tests were `test_frozen_ratio_and_monthly_controls_use_engine_results`, the five variants of `test_wrong_tenant_overlay_source_or_forged_context_never_prices`, and `test_unseen_authored_source_catalog_lifecycle_requires_current_pricing_authority`.

Focused rerun: **238 passed**, one existing Starlette deprecation warning, across the new module, `test_credit_steps.py`, `test_vendor_catalog.py` and `test_governing_fees.py`. Original failure and passing receipts remain in `W/tasks/opus70-public-worker/pytest-first.log` and `pytest-focused.log`, where W is the durable uptime-engineering directory.

After merging root transport commit `3449bbe`, the parent added `test_generator_refuses_ambiguous_json_before_proposal_validation` (12 new variants across envelope/proposal duplicate keys and non-finite numbers), and `test_generator_retains_os_login_identity_without_execution_overrides` (one new test of actual OS USER/LOGNAME, existing HOME/PATH and exclusion of ambient execution/provider overrides). No existing test was altered. Final focused validation across the new module, shared transport and catalog: **230 passed**, one existing warning (`pytest-final-focused.log`).

The first post-merge full suite was deliberately interrupted before the authorized environment repair: **1433 passed**, no failures, one warning, exit 2 after SIGINT. Its `pytest-merged-full.log` is retained and is not a final-source pass. The final-source full suite has a separate basetemp and receipt.

Full run at `c11e0cc`: **3117 passed, 1 failed**, one existing warning, 197.87 seconds (`pytest-final-full.log`). The failure is the unchanged `test_vendor_resource.py::test_cli_block_response_reconstructs_verified_public_artifact`: it requires the legacy launcher's pre-existing explicit `CLAUDE_CODE_OAUTH_TOKEN` input. Reusing the stripped environment dropped that supported input. No assertion was removed or weakened to hide this regression.

Root authorized restoring only the existing explicit token pass-through. The new identity test now has present/absent variants and also checks that the synthetic token never enters the prompt, argv or artifact. The existing resource test is unchanged. Repair validation across `test_vendor_step_proposals.py`, `test_vendor_resource.py` and `test_correspondence_model_transport.py`: **224 passed** in 1.57 seconds (`pytest-auth-compat.log`).

The final integrated full-suite gate is root-owned after merging this repair with workstreams 71/72, per the lead's direction to avoid duplicate concurrent suites. This branch does **not** claim a passing full suite after the repair. Historical failures and both earlier full-run receipts remain retained.
