# Test changes: workstream onboarding-89

**Changed existing tests: none.** No existing test, expectation, authority assertion or monetary assertion was modified.

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

## Focused results

Run from the worktree with the integration virtual environment (`UV_PROJECT_ENVIRONMENT`), unique `--basetemp` and `-o tmp_path_retention_policy=failed`, base directory deleted afterward.

- Baseline before changes (7 vendor/onboarding files at `03b372e`): **102 passed, 1 warning in 4.42s**.
- `tests/test_vendor_requirements_89.py`: first run **3 failed, 6 passed**. The card looked up the deadline citation as `filing`; the monthly compiler emits `filing_days`. The damage test had passed vacuously for the same reason. Both were fixed, and the damage test now first asserts that the undamaged card is complete. After the Opus-critique fixes: **16 passed, 1 warning in 2.64s**.
- All `tests/test_vendor_*.py` and `tests/test_onboarding*.py`, plus every test referencing `/api/vendors` or route inventories (local review exception, authority, Opus46 security, routes integration, tenant, portfolio, mandates, governing fees, correspondence route tests): **1451 passed, 1 warning in 253.85s**.

The full `uv run --locked pytest` result is recorded in [the verification receipt](evidence/onboarding-89/verification.json) once it has run.
