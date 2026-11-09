# Dispute completion work — November 9, 2026

The user resumed onboarding and dispute blockers in parallel followed by independent evaluation. A subsequent explicit choice approved a separate strict complete-month evidence path; legacy incident obligations remain unchanged. New scope is opt-in from a grounded reviewed source clause, never inferred from absent incident identifiers.

## Parent-authored temporal intake controls

New kinds `monthly_coverage` and `monthly_attribution` must describe the exact UTC calendar month and cannot be observed before it ends. These checks run before storage through the existing source scope boundary. Existing civil-offset margins and other evidence kinds are unchanged.

New file `tests/monthly_finish_20261109/test_monthly_temporal_parent.py` tests leap-February bounds, equivalent offset-aware timestamps, partial and foreign months, premature reports including `complete=false`, and preservation of the existing incident margin. No existing tests changed.

Focused verification with the locked environment and unique temporary directory:

`uv run --locked --no-sync pytest -q -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp=<owned>/pytest-temporal tests/monthly_finish_20261109/test_monthly_temporal_parent.py tests/onboarding_finish20261109/test_monthly_basis_helper.py`

Result: **43 passed in 0.21s**. This includes the 24 shared marker-validator controls from onboarding, imported as a dependency. The integration owner runs the full suite serially after merge; this result is not full integration or independent evaluation proof.

## Actual delegated coding

Claude Code 2.1.318 authenticated with the existing OAuth subscription session. Two restricted workers were observed as `claude-opus-5-5`, requested `xhigh`, with only Read/Edit/Write/Glob/Grep and no MCP servers. Sessions: `723292a0-1458-46c5-bd66-5a679025c7ef` (refusal audit/helper) and `983dae98-68d4-479b-8328-755e37b99f57` (strict monthly evidence). At this preparation commit they are running, not completed contributions. A preceding detached process emitted no initialization and did not survive its command lifetime; it is recorded as a failed startup, not a model invocation. Parent controls tests and Git. No credentials, private customer captures, frozen expected answers or native financial actions were delegated.

## Verified signed-source refusal journal

Added `uptime/correspondence_refusals.py`, a metadata-only append-only journal for authenticated out-of-scope service requests. It accepts only bounded tenant/signer/key/grant identifiers, an exact route, body digest and receipt timestamp; it does not accept raw bodies, proofs, nonces or arbitrary reasons. Stable deduplication preserves the first receipt. This helper alone does not alter authentication; the separately reviewed service hook remains a dependent change.

Added `tests/disputes_finish_20261109/test_refusal_journal.py` (53 parametrized cases). Tests cover metadata validation before opening storage, tenant/key/grant isolation, first receipt preservation, restart, concurrent insertion, immutable rows, unrelated-table preservation and propagated persistence failures. No existing tests changed.

Focused locked-environment verification: **53 passed in 0.32s**. Command: `uv run --locked --no-sync pytest -q -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp=<owned>/test-journal-1 tests/disputes_finish_20261109/test_refusal_journal.py`. The integration owner runs the full required suite after merge.

The initial xhigh advisory worker (session `723292a0-1458-46c5-bd66-5a679025c7ef`) was stopped after 754.745 seconds (exit 143) after producing a proposal and an overbroad audit draft. That draft was replaced, not treated as delivered code. A bounded high-effort worker (`0f4e344a-5128-4e7e-baa6-586b89db296e`) completed the small journal and tests in 227.145 seconds (exit 0). The parent inspected the complete patch and ran the focused tests.

## Signed-source authentication refusal hook

`Authority.service()` now separates valid Ed25519 proof from grant scope. A current authenticated, unspent out-of-scope claim-events delivery records the bounded journal metadata and still returns 403. The existing lock protects replay checks and journaling; denial does not spend the nonce. Rotated source keys must pass the existing identity-binding check before attribution, including a refused delivery. Invalid signatures, unknown senders, expired stamps, accepted-nonce replay, wrong origin, closed gate and legacy HMAC do not create authenticated refusal entries. Journal failure returns a generic 503 without accepting the delivery.

Added `tests/auth_refusal_finish_20261109/test_signed_refusal_hook.py` with 13 end-to-end/local-auth controls covering these boundaries, exact source identity, repeated and concurrent delivery, unchanged claim intake, tenant separation, key rotation and no body/proof/nonce persistence. All test keys are ephemeral authored fixture credentials. No existing tests changed.

Final focused verification (new hook/journal tests plus existing source-config and authority regressions): **98 passed, 1 warning in 5.92s**. The warning is the existing Starlette `httpx` TestClient deprecation. Command: `uv run --locked --no-sync pytest -q -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp=<owned>/test-auth-final tests/auth_refusal_finish_20261109/test_signed_refusal_hook.py tests/test_source_config_v4.py tests/test_v4_authority.py tests/disputes_finish_20261109/test_refusal_journal.py`. An earlier draft run passed 45 tests with one warning in 5.24s; final verification includes the journal controls.

Actual bounded Opus high worker `9f7c1709-36dc-417c-b697-5b4cb6d07020` completed in 303.406 seconds, exit 0. It edited the auth hook and its new tests using only Read/Edit/Write/Glob/Grep. The parent inspected the final control flow and tests, ran verification and owns this commit.

## Strict whole-service monthly path

Added typed `monthly_coverage` and optional `monthly_attribution`, a new strict join, and opt-in scope/route integration. The already integrated temporal guard rejects partial, foreign and premature reports before storage. The governing source must explicitly permit a complete service month without incident identifiers, with exact clause citations. The join requires an authoritative complete status report and independently enrolled invoice; an optional customer report must corroborate. Missing facts never default to zero. Existing fee/rate/cutoff engines and economic obligation identity remain authoritative.

New test files:

- `test_mf1109_types.py`: strict report schema, required coverage assertions, no coercion and optional repeated identity.
- `test_mf1109_scope_marker.py`: explicit shared marker validation, source grounding, no narrower invented scope and unchanged legacy/Twilio scope.
- `test_mf1109_observation.py`: report completeness, dynamic calendar bounds, independent authority, exact fees, conflicting kinds and receipt chronology.
- `test_mf1109_evaluator.py`: real existing decimal tier evaluator, cutoffs, zero fees and unchanged stepped-fee authority.
- `test_mf1109_route.py`: normal mounted application installation, source-derived marker, scripted version review, two-source intake, optional corroboration, overlap conflicts and unchanged economic key. These controls require the onboarding compiler dependency and never skip that integration requirement.
- `test_parent_monthly_controls.py`: separate parent falsification checks for two-source sufficiency, zero versus absent minutes, optional contradictory attribution, filing preservation, duplicate sources, narrower invoice fields, malformed marker, receipt chronology and malformed invoice amounts.

No existing tests changed. Before first commit, parent revisions to new worker tests were: `test_each_independent_record_is_required` now requires coverage and invoice under the approved two-source policy; the null-marker parameter moved from the legacy-success test to the refusal test; marker fixture text uses the actual supported source clause; `test_resolve_grounds_installed_artifacts_and_refuses_ambiguity` compares dataclass values rather than Python object identity; the route test's temporary compiler skip was removed and the positive flow uses two required records before optional corroboration. These are implementation controls, not frozen evaluation answers.

Observed intermediate results are retained: parent controls initially **5 failed, 7 passed in 0.63s**; worker controls **1 failed, 190 passed in 0.35s** (the object-identity assertion); after core correction **1 failed, 207 passed in 0.36s** (the new test still demanded the now-optional third record). Corrected targeted scope/core checks: **244 passed in 0.32s**. Final core plus legacy route/scope/dispute regressions: **417 passed, 1 warning in 4.25s**. The warning is the existing Starlette TestClient deprecation. The final command used the locked existing environment, unique `test-monthly-regression` directory and the six non-route new monthly files plus existing claim-scope, v4-route, D04 source, correspondence, dispute, identity and intake controls.

Compiler-dependent route tests and semantic hash pins remain for the coordinated integration. The actual Opus worker and follow-up critique receipts, including parent disagreement, are in `docs/v4/decisions/reviews/disputes-monthly-20261109-opus-worker.json` and its linked critique. No independent unseen success is claimed. Historical filing receipt intake remains limited to supported resource-month profiles; this change preserves ordinary local filing time and does not grant new historical monthly filing authority.

## Compiler dependency integrated for focused route proof

Imported canonical onboarding compiler commit `b9930c5` locally as `71f3e72` for verification. The only cherry-pick conflict was its previously absent progress record; the incoming record was preserved. No onboarding source was edited by this lane.

Mandatory ordinary-route controls: **8 passed, 1 warning in 1.27s**, no skips. They compile the explicit source marker normally, install/review the authored version through the ordinary local lifecycle, create a component/incident-free service-month claim, establish eligibility from status plus billing, corroborate with optional customer attribution, refuse mixed evidence and overlapping evidence-basis revisions, and preserve economic identity.

Final combined focused selection on `71f3e72`: **491 passed, 1 warning in 6.18s**. Exact selection: `uv run --locked --no-sync pytest -q -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp=<owned>/test-monthly-final-integrated tests/monthly_finish_20261109 tests/auth_refusal_finish_20261109 tests/disputes_finish_20261109 tests/test_claim_scope_89.py tests/test_v4_routes_integration.py tests/test_source_config_d04c.py tests/test_correspondence.py tests/test_disputes.py tests/test_correspondence_month_coverage_89d.py tests/test_disputes_identity_89c.py tests/test_correspondence_intake_scope_89b.py`. The warning remains the existing Starlette TestClient deprecation.

This resolves the compiler-dependent focused route check. The integration owner still must apply the complete monthly semantic hash pin, run the serialized required full suite and hand its frozen revision to the independent evaluation owner. No new model calls, real data or human review are implied by these authored local results.
