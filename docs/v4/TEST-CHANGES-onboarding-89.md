# Test changes: workstream onboarding-89

**Changed existing tests:** none on `work/onboarding-generalization-89`. On `work/onboarding-d05-phase2-89` (D05 phase 2), exactly one:

- `tests/test_vendor_model_jobs_browser.py::test_signed_job_routes_require_approval_and_cannot_grant_financial_actions`. **Reason:** under D05 an operator-chosen profile (`monthly`) can no longer stage a candidate. The test now asserts that candidate is refused with HTTP 409, then stages the same source through automatic selection: the canonical source is selected offline and staged via `POST /candidates`, and a repeat is idempotent. Approval, financial-action denial, provider-call count and cross-reviewer 404 assertions are unchanged; no authority or monetary assertion was weakened.

## Added: `tests/test_vendor_requirements_89.py` (16 tests)

| Test | What it establishes |
|---|---|
| `test_new_module_is_outside_reviewed_semantics_so_existing_reviews_do_not_churn` | `vendor_requirements.py` and `vendor_api.py` are not part of any evaluator semantics hash. |
| `test_monthly_card_cites_every_required_element` | Card elements map to exact source quotes and offsets. |
| `test_generated_drafts_match_hand_calculation_and_shadow_evaluator` | Hand-computed April 2026 thresholds (108/864 of 43,200 minutes), deadline boundary and out-of-interval month. Every draft equals signed shadow preview. |
| `test_drafts_cannot_be_submitted_unchanged_as_the_independent_suite` | Verbatim drafts → HTTP 422; no state change. |
| `test_requirements_route_is_read_only_and_tenant_scoped` | Audit and revision unchanged; viewer may read; other tenant → 404. |
| `test_quarantined_intake_reports_a_review_requirement_not_a_card` | Generic public reason only. |
| `test_missing_cited_element_becomes_a_concrete_requirement` | A removed deadline citation → REVIEW_REQUIRED (non-vacuous: undamaged card first asserted complete). |
| `test_resource_month_card_grounds_fee_evidence_exclusions_and_deadline_in_cited_blocks` | Resource elements cite the blocks whose propositions establish them. |
| `test_new_vendor_name_reaches_shadow_with_useful_drafts_and_no_vendor_code` | Authored "Halcyon Queueing Ltd" source reaches SHADOW, drafts match the evaluator, no package file names the vendor, draft-fact reuse is reported. Not D05 discovery. |
| `test_independent_facts_raise_no_overlap_warning` | No false overlap warning. |
| `test_requirements_expose_nothing_beyond_the_detail_view_for_the_same_principal` | Overlay values in the card are already visible in the detail view to that principal. |
| `test_propositions_manifest_has_no_false_uncategorized_alarm_and_unknown_content_requires_review` | Model-propositions manifest is complete; injected unknown key → REVIEW_REQUIRED. |
| `test_both_monthly_compilers_refuse_a_standalone_exclusion_sentence` | Pins the compiler behavior that `NONE_STATED` summarizes. |
| `test_resource_element_present_without_a_cited_block_requires_review` | Present-but-uncited → REVIEW_REQUIRED. |
| `test_malformed_artifacts_summarize_as_refusals_not_errors` | No exceptions on malformed overlays/manifests. |
| `test_property_sweep_drafts_equal_the_evaluator_for_random_tiers_months_and_windows` | 60 derandomized cases: 1–3 six-decimal tiers, months 2026–2030, 1–60 day windows, fractional cents. |

## Added: `tests/test_vendor_refusal_diagnostics_89.py` (12 tests)

Each test uses provider doubles; no real inference occurs. A model-text sentinel is placed in model-controlled output and must appear in neither the stored row nor the API view.

| Test | What it establishes |
|---|---|
| `test_validator_rejected_passage_is_cited_exactly_without_model_text` | Strict-profile finding cites the exact rejected passage with its offsets and hash. |
| `test_extraction_flag_is_attributed_to_the_extraction` | Propositions refusal caused by the extraction's own flag uses `EXTRACTION_FLAGGED_UNSUPPORTED`. |
| `test_a_model_label_alone_is_never_cited` | A valid line mislabeled "unsupported" is not cited. |
| `test_missing_terms_are_named_only_when_the_validator_establishes_them` | Propositions validator → "claim filing deadline". |
| `test_strict_profile_reports_incomplete_coverage_without_guessing_terms` | Strict validator → `SOURCE_COVERAGE_INCOMPLETE`, no names. |
| `test_invented_quote_cannot_be_cited` / `test_unstructured_output_has_a_fixed_code` | Ungrounded or unstructured output → fixed code, no location. |
| `test_resource_block_marked_unsupported_cites_that_public_block` | Resource-month block citation. |
| `test_successful_jobs_carry_no_diagnostic` | Succeeded jobs carry none; the shared view never does. |
| `test_only_vendor_refusals_store_a_bounded_diagnostic` | Correspondence kind never stores one; 300 KB bound. |
| `test_existing_job_table_gains_a_nullable_column_and_keeps_rows` | Additive migration keeps existing rows and reasons. |
| `test_forged_or_stale_records_are_not_projected` | A self-consistent forgery with a substituted document, wrong offsets, an invented code, a changed profile, or another context is not shown. |

## Added: `tests/test_vendor_family_selection_89.py` (22 tests, D05 phase 1)

Real job service and deterministic validators; the provider double returns a scripted reading per family profile.

| Test | What it establishes |
|---|---|
| `test_canonical_monthly_source_is_selected_offline_without_inference` | Offline selection; zero provider calls. |
| `test_resource_language_keeps_even_a_canonical_source_off_the_offline_shortcut` | Opus falsification probe: dual-fit source refused offline and by the strict parser. |
| `test_a_resource_symptom_clause_has_no_monthly_reading` | A symptom/cause clause is refused under every monthly field label. |
| `test_no_job_is_queued_until_every_family_request_is_approved` | No partial spend. |
| `test_monthly_family_selected_when_the_resource_reading_is_refused` | Monthly selected via jobs; loser reasons shown; SHADOW only; resubmission idempotent. |
| `test_resource_family_selected_when_the_monthly_reading_meets_a_deterministic_qualifier` | Resource selected; the monthly loser was refused structurally. |
| `test_both_refused_is_no_supported_family_with_concrete_requirements` | Per-family requirements. |
| `test_a_family_with_no_grounded_reading_cannot_be_ruled_out` | `INCOMPLETE`, not `SELECTED`. |
| `test_any_other_validated_family_makes_the_source_ambiguous_and_blocks_its_candidate` | A validated family from another reviewer's attempt gives `AMBIGUOUS`; the candidate is refused; a retry stays ambiguous. |
| `test_offline_selection_is_also_ambiguous_when_another_family_validated` | The offline path checks attempts too. |
| `test_outcome_matrix` (8 cases), `test_unsubmitted_and_unconfigured_outcomes`, `test_refusal_classification` | Pure outcome derivation. |
| `test_signed_app_path_selects_stages_and_explains_the_family`, `test_signed_app_path_offline_selection_and_explanation` | Signed HTTP path on the existing draft routes, with `family_selection` on the requirements view. |

## Focused results

Run from the worktree with the integration virtual environment (`UV_PROJECT_ENVIRONMENT`), unique `--basetemp` and `-o tmp_path_retention_policy=failed`, base directory deleted afterward.

- Baseline before changes (7 vendor/onboarding files at `03b372e`): **102 passed, 1 warning in 4.42s**.
- `tests/test_vendor_requirements_89.py`: first run **3 failed, 6 passed**. The card looked up the deadline citation as `filing`; the monthly compiler emits `filing_days`. The damage test had passed vacuously for the same reason. Both were fixed, and the damage test now first asserts that the undamaged card is complete. After the Opus-critique fixes: **16 passed, 1 warning in 2.64s**.
- All `tests/test_vendor_*.py` and `tests/test_onboarding*.py`, plus every test referencing `/api/vendors` or route inventories (local review exception, authority, Opus46 security, routes integration, tenant, portfolio, mandates, governing fees, correspondence route tests): **1451 passed, 1 warning in 253.85s**.

- Refusal diagnostics: first implementation **9 passed**. It was revised after the Opus critique, and `vendor_model_jobs.py` was reverted to byte-identical. Revised file: **12 passed, 1 warning in 1.96s**. The same focused set plus `test_public_proposal_jobs.py`, all `test_correspondence_model_jobs*.py` and `test_correspondence_public_queue_75.py`: **1527 passed, 1 warning in 374.43s**.

Full `uv run --locked pytest`: not run on this branch, at the integration owner's request (shared nearly full disk). It runs once after merge into `work/integration-90`.

- D05 phase 1: new file **22 passed, 1 warning in 1.78s** (first collection failed on a parametrize name that clashed with an imported module; fixed). Focused set (all `test_vendor_*`, `test_onboarding*`, proposal-job, correspondence model-job, route and authority tests): **1174 passed, 1 warning in 71.27s**.
- D05 phase 2 (`work/onboarding-d05-phase2-89`): `test_vendor_family_selection_89.py` **25 passed**, including three new phase 2 tests (`test_operator_chosen_profile_cannot_stage_a_candidate`, `test_a_job_selection_did_not_choose_cannot_stage_a_candidate`, `test_an_incomplete_selection_cannot_stage_its_validated_job`). With `test_vendor_model_jobs_browser.py`, `test_vendor_auth83.py` and `test_vendor_monthly_profile_79.py`: **3 failed, 38 passed in 110.19s**. All three failures are browser tests that drive the current "Extraction profile" select, and they pass only with the W7 change in [D05-SELECTION-API.md](D05-SELECTION-API.md): `test_browser_checks_permission_generates_and_stages_separate_overlay[manual]`, `[utf8_file]` and `test_vendor_auth83.py::test_expired_browser_session_recovers_same_job_without_resubmitting`. Phase 2 is therefore not mergeable without that change.

## D05 phase 2 browser change (`work/onboarding-d05-ui-89`)

`web/v4_ui.js` no longer offers an "Extraction profile" select; it sends `profile: "auto"` and renders the selection view. This was assigned to W3 under Ronok's delegated authority, with gent7 (W7) reviewing. Changed existing tests, each keeping its original safety assertions:

| Test | Reason for change |
|---|---|
| `tests/test_vendor_model_jobs_browser.py::test_browser_checks_permission_generates_and_stages_separate_overlay[manual]`, `[utf8_file]` | The profile select is gone. The test now uses a prose source and a per-family provider double, so the model path still runs: two family jobs, GET-only polling, an explicit refresh, then staging only the selected job. The exact-text, CRLF/edit invalidation, overlay-separation, no-approval-control and 390 px assertions are unchanged. Model call count is now 2 (one per family). |
| `…[offline]` (new parameter) | Canonical source selected offline; staged via `POST /candidates` with zero model calls. |
| `tests/test_vendor_auth83.py::test_expired_browser_session_recovers_same_job_without_resubmitting` | Same flow change. Every recovery assertion is kept: no candidate POST while expired, the same job recovered, one `proposal-jobs` POST, one candidate POST. Model call count is 2. |
| `tests/helpers/vendor_model_jobs.test.cjs` | Rewritten for the selection view. The original controls are kept (draft access, exact untrimmed body, invalidation, GET-only polling, safe text, overlay review, lost-reservation recovery, superseded responses, separate local form). New controls: no profile control, review requirements verbatim, staging only on `SELECTED`, offline staging route, non-selected jobs unstaged. 10 tests. |
| `tests/helpers/vendor_auth83.test.cjs` | The mock server answers with selection views; each 401 path and the overlapping-read guarantee are kept. |
| `tests/helpers/vendor_monthly_profile79.test.cjs` | The phase 79 contract ("the profile is explicit") is retired by D05. It is replaced by: no profile control exists, `auto` is always sent, and any source edit revokes confirmation. |

Not changed by W3: `tests/helpers/refusal_diagnostic.test.cjs` (gent7's, round 3) still sets the removed profile field. gent7 moves it onto this SHA. No pytest test runs it.

Results: the JS helpers (`vendor_auth83`, `vendor_monthly_profile79`, `vendor_model_jobs`) **24 passed**; `browser-contract`, `v4_ui` and `advanced_companion` **33 passed**. The Python set (`test_vendor_model_jobs_browser`, `test_vendor_auth83`, `test_vendor_monthly_profile_79`, `test_vendor_family_selection_89`, `test_advanced_companion`, `test_vendor_model_jobs_runtime`, `test_vendor_refusal_diagnostics_89`, `test_vendor_requirements_89`) **81 passed, 1 warning in 25.81s**.

After merging integration head `c55f2fd`, the broad focused set reported **1 failed, 1182 passed, 1 warning in 58.84s**. The failure was a race in the new browser tests: with an instant provider double, both family jobs can finish before the submit response is computed, so the page goes straight to `SELECTED` and never shows the "finished" message. Both browser tests now accept either path through `await_selected_proposal`. `test_vendor_model_jobs_browser.py` and `test_vendor_auth83.py` then gave **7 passed** on two consecutive runs.

