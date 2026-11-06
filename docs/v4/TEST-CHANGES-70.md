# Decision70 test-change ledger

No existing test file or assertion was changed. `tests/test_vendor_step_proposals.py` is new and checks exact compiler/proposal equivalence, unchanged source offsets/digests, strict wire mutations, legacy normalized and tier acceptance, exact financial vectors, current governing-fee authority, and the normal shadow/review/activation/dispatch/rollback lifecycle.

Preimplementation control freeze: `b2edd35`, `fixtures/opus70_public/freeze.json`. These are authored public controls, not blind or heldout results. `before.json` retains the original proposal-format rejection. Existing compiler acceptance does not establish that the model flow could represent the rule.

Native validation of the actual worker's initial test file: 127 passed, 7 failed. All failures arose from its new `billing_scope` helper omitting required `Scope.component` and `Scope.incident`. The parent supplied explicit test-authored identifiers in that helper; no frozen data, monetary expectation, authority condition or assertion changed. The affected new tests were `test_frozen_ratio_and_monthly_controls_use_engine_results`, the five variants of `test_wrong_tenant_overlay_source_or_forged_context_never_prices`, and `test_unseen_authored_source_catalog_lifecycle_requires_current_pricing_authority`.

Focused rerun: **238 passed**, one existing Starlette deprecation warning, across the new module, `test_credit_steps.py`, `test_vendor_catalog.py` and `test_governing_fees.py`. Original failure and passing receipts remain in `W/tasks/opus70-public-worker/pytest-first.log` and `pytest-focused.log`, where W is the durable uptime-engineering directory.
