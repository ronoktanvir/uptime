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

## Generic route and signed setup increment

No existing pre-66 tests changed. Added `tests/test_northwind_workflow.py` controls for unconfigured null projection, exact signed setup, actual scripted identity, CalyxQuay activation/rollback/reactivation history, unknown pricing before the governing-fee join, body-bound request authentication, unsupported payload rejection, native/tenant/mode startup refusal, and stepped economic version pins with byte-identical legacy preimages. The 27 focused workflow/provider controls passed in `northwind-composition-001.log`; the new action/recovery implementation still needs its full lifecycle tests after 65a.

Required post-merge acdadf4 full run: 2,797 passed and 8 failed, 159.64 seconds (`northwind-acdadf4-full-001.log`). The failures were existing public shadow/film semantic-review setup and six historical procedural fixture joins; no assertions were weakened. Root owns their integration corrections. No private corpus was inspected.

The initial populated projection at `northwind-projection-003/initial-projection.json` was obtained through actual signed public API setup. Northwind remains SHADOW and money unknown until the approved fee context lands. The separate CalyxQuay catalog is ACTIVE with immutable rollback/review/reactivation history. This is intermediate composition evidence, not a completed financial walkthrough.

Decision68 supersedes the proposed March application: the existing future-invoice guard remains unchanged. April source intake and final application are pending the separately authored settlement input; March application remains unavailable.

## Signed governing-fee join and local-post lifecycle

Added 12 lifecycle/recovery/source-revocation controls in `tests/test_northwind_workflow.py`: all nine real service operations, duplicate clicks with unchanged effects, restart after each individual domain effect, interruption immediately after event-clock advancement, and live vendor source-grant removal. January reaches 2400 claimed, awarded and locally posted; applied remains zero. The test `test_public_signed_setup_and_scripted_calyx_history_preserve_unknowns` now expects the actual January2400 action after the approved typed fee registry is wired, while February and incomplete March remain null. This is a new 66 test update, not a weakening of any earlier corpus assertion.

The joined 78e7564 full suite passed 2,846 tests (`northwind-67-merge-full-001.log`). After the fee resolver/action join, 82 targeted controls passed in22.62s (`northwind-lifecycle-001.log`). Mounted signed HTTP completed all nine stages with actual immutable source/claim/award/provider records. Socket proof and April settlement remain pending. The current fee-authority revalidation repair is an explicit outstanding dependency; no final freeze is claimed before it lands.

The intermediate merge d90286b full run retained2,828 passes and9 failures. The extra failure exposed setup leaving the proposition opt-in set in process environment; commit0649237 restores the original environment after the bounded already-approved public setup. The unchanged existing opt-in regression passed after that correction. Setup occurs before serving requests. The other eight failures were resolved by integration of root67, not assertion removal here.

## Inspectable clauses and actual socket receipt

The projection retains exact original governing quote text, offsets, quote digest and full source digest under contract documents and price citations. The signed setup test verifies the11000 amendment quote and digest without normalizing source bytes. This targeted control passed.

`scripts/rehearse_northwind.py` sends only empty authenticated action bodies over actual loopback HTTP. It verifies the server's mode/tenant/origin, database instance and package digest, repeats each action with a fresh proof to check idempotency, and separately GETs the resulting state. The first real-socket run completed all9 actions through2400 locally posted; all9 duplicate responses and readbacks matched. Receipt: `W/receipts/northwind-socket-posted-001.json`. Application remains0 and March outstanding capacity remainsunknown. This intermediate receipt predates the final current-fee repair and April settlement input; it is not the final walkthrough or native Ramp proof. The owned server was stopped afterward.

## Final66/68 integration

No pre-66 assertion changed in this final increment. Exact updates to newly added66 tests:

- `test_public_signed_setup_and_scripted_calyx_history_preserve_unknowns`: March price now expects1000.00 after approved advance pricing; March SLA remains unknown/null. January remains2400, February ineligible/null. Added raw quote digest checks.
- `test_real_services_complete_denial_cure_award_and_idempotent_post`: after posting, expects the newly available Receive next invoice operation instead of the earlier temporary end state; asserts no April bill is visible yet.
- `test_restart_after_each_domain_effect_completes_same_intent_without_second_effect`: extends positions0–8 to0–10, adding invoice receipt and application crash recovery.

Added April-only balance/version/non-netting, five interruptions between clock/source/authority/capacity stages, changed scope/currency/reference/date refusal, missing linked verifier refusal, live governing-fee revocation, and owner-only browser JWK identity tests. The repaired registry and trusted clock are explicitly forwarded through catalog/current views, Workbench and correspondence resolution. No global authority cache is used.

Final focused run: **86 passed**, one dependency deprecation warning,69.99s; `W/receipts/northwind-final-focused-001.log`. Final actual socket run completed **11/11 actions**, all duplicate-click responses and independent GET readbacks equal. The retained public [socket receipt](validation/northwind/final-socket.json) shows January2400 claimed/awarded/posted/applied, April11000 original/8600 remaining, unapplied credit0, March1000 exposure still unresolved and March credit allocation0. April's issued date, service start and capacity date are April1; the server exposes no April invoice before the receive action. Each financial stage is separate, not additive.

Both real-socket servers owned by this workstream were stopped after verification. Root owns the final mandatory integration-wide suite and browser click-through. Scripted authority and Local ledger receipts are not real-human or native Ramp proof. The final setup output change prints only account/path/listener metadata before serving; no key bytes or rehearsal secret are printed.
