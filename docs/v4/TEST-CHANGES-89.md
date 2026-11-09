# Test changes — decision 89: identity reproduction and financial coverage

Two increments on branch `work/identity-pricing-89`:

1. **Characterization (`4ad4506`)**: no existing test, fixture, receipt or source file changed.
2. **D03-A implementation (this commit)**: one existing test changed, named in its section below. The decision-89 characterization tests that pinned the identity defect were replaced by invariants, as intended.

## New tests

| File | Functions / cases | Purpose |
| --- | ---: | --- |
| `tests/test_identity_domain_89.py` | 8 / 23 | Characterizes the confirmed D03 identity-domain mismatch and the D04 universal-scope requirement. Replays the preserved `e86-01` and `e86-04` request bodies against current source. Pins the Northwind January degradation from ELIGIBLE 2400.00 to INSUFFICIENT_EVIDENCE when only the account representation changes. |
| `tests/test_financial_coverage_89.py` | 17 / 24 | Keeps the [coverage matrix](FINANCIAL-COVERAGE-89.md) honest: every row cites existing tests and enforcement symbols, every requested dimension has a refusal row, and the page lists exactly the machine rows. Adds boundary probes the audit found without a direct test, plus fixture-name independence checks for Northwind and every pricing demo case. |

Exact function names are in the files. These are new controls, not changes to accepted expectations.

## Probes that pin a debatable classification

These assert today's behaviour so any change is deliberate. None produces money; each is a review item in the [coverage matrix](FINANCIAL-COVERAGE-89.md#audit-result):

- `test_contradictory_product_scope_never_prices`: contradictory product scope is INSUFFICIENT_EVIDENCE, not UNSUPPORTED_RULE.
- `test_missing_evidence_outranks_an_unsupported_line_and_both_are_traced`: missing evidence outranks an unsupported line.
- `test_contradicting_account_observation_is_reported_as_missing_scope`: a contradiction is reported like an absent fact.
- `test_receipt_before_month_end_is_outside_window_and_at_month_end_is_timely`: a premature receipt is INELIGIBLE / OUTSIDE_WINDOW.

## Tests a D03 or D04 decision would change

All eight functions in `tests/test_identity_domain_89.py`, `test_contradicting_account_observation_is_reported_as_missing_scope`, and six existing tests are coupled to the pending identity and scope decisions. The full list, with the coupling for each, is in [identity and scope dependencies](IDENTITY-SCOPE-CONTRACT-89.md#tests-a-d03-or-d04-change-would-have-to-update). That is the migration cost the team should expect; none is changed here.

## Failed attempts, preserved

1. The first run of `test_negotiated_pricing_results_do_not_depend_on_fixture_names` failed in four of five cases with INSUFFICIENT_EVIDENCE, “Both party signatures required”. The test had renamed the agreement parties but not each version's signatories, so the renamed agreement was genuinely unsigned by its parties. This was a test-authoring error, not an engine name dependency. The fifth case passed only because both sides were already INSUFFICIENT_EVIDENCE. The rename now maps signatories consistently; the engine is unchanged.
2. `test_human_matrix_lists_exactly_the_machine_rows` failed first because the page did not exist yet, then because the review-item table repeated row IDs. The check now reads only the `## Matrix` section.
3. Two enforcement references in the draft matrix named nonexistent symbols (`compile_resource`, `evaluate_service_month`). They were found by inspection before the integrity test ran and corrected to `vendor_service_month.validate` and `vendor_service_month.evaluate`.

## Results

Focused results on this branch, with no source changes:

- `tests/test_identity_domain_89.py`: 23 passed in 4.17s.
- Both new files: 47 passed in 7.85s.
- Every test file cited by the matrix (14 files, including the two new ones): 618 passed, 1 warning in 12.71s. The warning is the existing Starlette `TestClient` import notice.

The full `uv run --locked pytest` result and the exact tested commit are recorded in [the verification receipt](evidence/identity-pricing-89/verification.json).

## D03-A implementation

### Existing test changed

**`tests/test_allocation_ledger.py::test_conflicting_duplicate_and_source_alias_cannot_double_count`**

- Before: the test asserted that whitespace-padded spellings (`" tenant "`, `" case-1 "`, `" award-1 "`, `" allocation-1 "`) replay as the same normalized identity.
- Why it changed: D03-A, confirmed 2026-11-09 and accepted in the decision-94 critique, requires the ledger to refuse such input rather than trim or NFC-normalize it.
- Now: those spellings must raise `ValueError`. Direct checks show padded and non-NFC account IDs are refused while a source-shaped `Cedar Orrery Studio` passes unchanged.
- Unchanged: exact replay is still idempotent, and every no-double-count and monetary assertion is as before, including 8,000 applied cents and the cloned application, credit, bill and award refusals.
- One of my draft values (`"acct-1\u0301"`) was wrong: an accent on a digit has no precomposed form, so that string is already NFC and correctly passes. It was replaced with the genuinely non-NFC `"Cafe\u0301 Nord"`.

### Decision-89 characterization tests replaced by invariants

These tests pinned the defect at `4ad4506` and were expected to fail under D03-A; they did, and were replaced:

| Replaced (at `4ad4506`) | Replacement invariant |
| --- | --- |
| `test_identity_validators_disagree_on_exact_source_values` | `test_every_account_and_agreement_entry_point_applies_the_same_bounded_rule`: 21 values × 12 entry points; all accept exactly `source-identity/1`. Also `test_ramp_terms_agreement_accepts_the_shared_rule_and_keeps_legacy_references`. |
| `test_onboarding_accepts_identities_that_claim_intake_or_claim_key_cannot_represent` | `test_accepted_identities_are_never_rewritten` and the entry-point invariant above. |
| `test_recorded_claim_intake_refusals_reproduce_on_current_source` | `test_recorded_requests_no_longer_refuse_their_exact_source_identities`: the preserved e86 bodies remain immutable; their account and contract refusals no longer occur. Missing component, incident, region and invoice remain until D04. |
| `test_spaced_onboarded_account_is_stranded_before_claim_and_governing_fee` | `test_spaced_source_account_keeps_the_same_northwind_economics` (January stays ELIGIBLE 2400.00 with the same fee and steps) and `test_another_accounts_fee_context_is_still_never_borrowed`. |
| `test_trailing_space_account_passes_onboarding_but_not_economic_identity` | `test_padded_or_irregular_accounts_are_refused_at_onboarding_intake_and_filing`. |

The three D04 characterization tests in that file are unchanged.

### New tests

- `tests/test_source_identity_89.py` (5 functions, 37 cases), covering:
  - the versioned rule;
  - a property test that every legacy restricted identifier is accepted byte-identically;
  - refusal codes;
  - a property test that acceptance equals the documented predicate, and that every accepted value also satisfies the claim-key rule.
- `test_case_or_spacing_variant_cannot_file_the_same_obligation_twice` (4 cases): the guard refuses with `NearDuplicateIdentity`. HTTP routes map `ValueError` to 409. No override path exists.
- `test_distinct_obligations_and_exact_retries_are_not_blocked` (3 cases).

Coverage matrix: `IDS-D03-1` and `IDS-D03-2` are now SUPPORTED, `IDS-D03-3` (REFUSED_AT_FILING) is added, and `STP-BAS-1` now cites the fee-context non-borrowing test.

## D03 extension to vendor and service names

No existing test changed. New: `tests/test_identity_domain_89.py::test_every_vendor_service_and_product_entry_point_applies_the_same_bounded_rule` (24 values × 9 entry points: onboarding product and vendor, claim and signed-line vendor/service, resource-line and monitor product, new-filing vendor and service), including `Cloud Hosting (EU)`. The coverage row `IDS-D03-1` now names vendor and service.

Results: decision-89 files 146 passed in 3.42s; identity-related suites 3529 passed, 1 warning in 387.23s.

## F5: reviewed agreement binding

Ronok decided "require reviewed binding" on 2026-11-09. `bind_overlay` now refuses an overlay for a resource source that names no agreement, unless the overlay carries the reviewed governing-terms attestation binding that exact agreement to the exact document, effective date and unamended economics. Whole-service profiles may carry exactly that attestation and still refuse every other private amendment.

**First run after the change:** 32 failed and 1 errored, as the decision intends. Every failure bound an authored source that names no agreement (the Compass and Oriole whole-service texts) without a binding.

**Existing tests changed (fixtures only; no assertion, amount or authority check changed):**

- `tests/test_vendor_service_month.py`, helper `run()` and `test_service_aggregate_signed_api_produces_case_and_rollback`: the authored Compass overlay is bound through `reviewed_binding(manifest, OVERLAY)`.
- `tests/test_vendor_resource_period_scope_77.py`, helper `reviewed()`: an overlay for an unnamed-agreement source receives the same authored binding. Overlays for sources that name their agreement are unchanged.
- `tests/test_correspondence_service.py`, fixture `service`: the API-installed Compass candidate carries the binding.
- `tests/test_correspondence_filing_refs.py`, fixture `filing`: the API-installed Compass variant carries a binding computed from the same compiled rows. It is shared by every function in `test_correspondence_filing_refs.py` (33) and `test_correspondence_plan_refs.py` (34). Those 67 errored at setup in the wide run (3082 passed, 67 errors) and pass after the fixture change (67 passed), with unchanged assertions.

These fixtures carry the following previously failing functions, which pass unchanged in their assertions (amounts `20.99` and `10.00` included):

- `test_vendor_service_month.py`: every function that binds Compass. That includes `test_attested_aggregate_source_exact_month_basis_threshold_and_fixed_clock`, `test_fractional_minutes_at_strict_threshold_are_exact`, `test_invalid_or_out_of_month_durations_abstain`, `test_missing_or_unbound_evidence_never_becomes_a_zero_observation`, `test_unpaid_or_unclassified_fee_and_unseen_invoiced_categories_abstain` and `test_service_aggregate_signed_api_produces_case_and_rollback`.
- `test_vendor_fixed_filing_80.py`: `test_inclusive_compiled_cutoff_before_at_and_after` and `test_exclusive_compiled_cutoff_before_at_and_after`.
- `test_vendor_resource_period_scope_77.py`: `test_april_aggregate_source_compiles_end_to_end_with_scope_and_original_citation`.
- `test_vendor_semantic_bindings.py`: `test_unknown_fee_category_is_not_included_by_failing_to_match_an_exclusion`.
- `test_economic_scope_delimiters.py`: `test_historical_shadow_also_refuses_new_draft_before_inbox_audit[service-True]` and `test_aggregate_legacy_collision_refuses_local_submission_without_partial_writes`.

**New:**

- `tests/governing_binding_89.py`: an authored fixture helper. It is labelled as fixture data, not a real review.
- `tests/test_agreement_binding_f5.py`: 6 functions, 12 cases. They check that an unbound overlay is refused for any agreement; that the binding admits exactly its own agreement and document; that a mismatched or incomplete binding is refused; that a binding cannot be reused for another agreement; that the fixed profile still refuses other private amendments; and that a source naming its agreement still binds by exact equality.

Stored adapters are unaffected. A read-only count found that every stored manifest names its agreement.

## D04-C: server-side claim scope family table

On 2026-11-09 Ronok chose D04-C and "monthly keeps incident". Claim scope component, incident, region and invoice are optional. `uptime/claim_scope.py` (`claim-scope/1`) resolves the governing family from installed terms; it never trusts the client to name it. Required fields must be present and not-applicable fields absent. An unknown or ambiguous family is refused at intake, after authorization, with a distinct `InvalidClaimScope` (HTTP 409). Stored ten-field claims are grandfathered: their serialization is byte-identical, and an explicit `FeeEntry.legacy_scopes` alias keeps their governing fee.

Two consequences shaped most test edits. First, a claim can no longer be created before any governing terms are installed. Second, a field that does not apply to the family, such as region on a Twilio claim, must be omitted. **No monetary amount, authority check, frozen fixture byte, oracle, expected dispute category, disposition, stage or ledger changed.**

### Replaced decision-89 characterization tests

| Replaced | Replacement invariant |
| --- | --- |
| `test_claim_scope_requires_every_field_for_every_obligation_family` | `test_claim_scope_requires_identity_currency_and_month_only` |
| `test_recorded_scopes_lack_fields_their_obligation_may_not_need` | `test_recorded_requests_parse_and_are_judged_by_their_governing_family`: the e86 bodies parse; the monthly case is refused for "requires incident", the resource case for "requires region" |
| `test_northwind_whole_service_scope_carries_authored_values_the_evaluator_never_reads` | `test_northwind_intake_omits_placeholders_and_keeps_its_authored_scope_as_a_legacy_alias`: the intake scope drops placeholders; the authored scope resolves the same fee; an invented region is refused |

### Existing tests and fixtures changed (file, function: reason)

- `tests/test_v4_routes_integration.py`, `App`. New `applicable_scope()`: the test client sends only the fields the server-resolved family needs and never invents one. `provision()`, `create()` and `source()` use it. New `install()` installs the terms (SHADOW) separately from `activate()`. These functions call `env.install()` before intake because terms must exist first: `test_active_rules_join_independent_evidence_and_historical_receipt`, `test_rollback_invalidates_existing_inbox_approval`, `test_active_overlay_requires_exact_authenticated_fee_line`, `test_monthly_tier_requires_complete_signed_month_reconciled_to_incident`, `test_overlapping_active_history_cannot_reprice_existing_measurement_month`, `test_active_effective_dates_must_cover_entire_measurement_month`, `test_active_installation_with_midmonth_effective_date_abstains` and `test_conflicting_duplicate_month_record_invalidates_approval`. `test_exact_source_binding_prevents_early_registration_of_invented_claim` also derives its invented claim from the applicable scope, so it is still refused by the exact source grant (403).
- `tests/test_correspondence.py`:
  - `SCOPE` drops region, which does not apply to Twilio.
  - New harness helper `counterparty_record()`. It first checks that the counterparty fixture's attachment digests reproduce under its authored ten-field scope, then re-envelopes the same authored documents under the region-less claim scope. The fixture bytes are unchanged.
  - `test_independent_simulator_new_evidence_and_oracle` uses `counterparty_record()`.
  - `test_no_twilio_fallback_for_other_vendor`: **expected behaviour changed by the decision.** A vendor with no installed terms is now refused at intake as an unknown family, and nothing is drafted. It was previously drafted and evaluated as UNSUPPORTED_RULE.
  - `test_authoritative_active_resolver_version_and_scope_binding`: the injected resolver stands in for installed terms, so the test also declares their monthly family; the scope drops component and region.
- `tests/test_correspondence_disposition_89.py`, `record()`: uses `counterparty_record()`. Frozen `novel-89` inputs and every expected category are unchanged.
- `tests/test_correspondence_intake_scope_89b.py`, `test_identity_contradiction_holds_actions_but_a_misroute_does_not`: the contradicting invoice-line identity is the account instead of region, because region no longer applies to a Twilio claim.
- `tests/test_correspondence_service.py`:
  - Fixture `service`: the claim is created after the candidate terms are installed.
  - `test_fixed_cutoff_uses_actual_local_receipt_and_whole_service_obligation`: a whole-service claim has no component, so the "component alias" is the same obligation and is refused earlier (409, "obligation already exists") rather than at reservation lookup.
- `tests/test_correspondence_filing_refs.py`, fixture `filing`: the claim is created after the candidate terms are installed.
- `tests/test_correspondence_plan_refs.py`, `test_valid_source_in_another_claim_is_not_a_plan_reference_for_this_join`: no terms are installed for the second account, so a labelled test double declares the same whole-service family for that one creation.
- `tests/test_correspondence_resource.py`:
  - Fixture `env` opts into `create_after_install`, and `install()` then creates the claim after SHADOW.
  - `test_region_alias_without_separate_contractual_coverage_cannot_create_another_intake` posts the applicable scope.
  - `test_independent_resource_vendor_rechecks_private_records_and_verified_attachment`: the counterparty record mirrors the claim's applicable scope.
- `tests/test_correspondence_regional.py`:
  - Fixture `regional` opts into `create_after_install`.
  - `test_distinct_covered_regions_enter_with_shared_evaluation_identity_and_reject_aliases` posts the applicable scope.
- `tests/test_correspondence_scoped_filing_77.py`, `test_signed_historical_receipt_uses_its_verified_month_and_original_received_time`: the claim is created after installation.
- `tests/test_correspondence_receipt_version.py`, `test_signed_public_source_proof_covers_original_pin_and_new_terms_cannot_repin_it`: the injected resolver also declares its resource family; the scope drops the not-applicable incident.
- `tests/test_economic_scope_delimiters.py`, `test_historical_shadow_also_refuses_new_draft_before_inbox_audit`: posts the applicable scope. The whole-service variant collides earlier as the same obligation; the regional variant still hits the reservation.
- `tests/test_claim_identity_historical.py`, `test_signed_procedural_response_survives_backfill_for_an_independent_reservation`: the expected `HIST-` identifier is computed from the stored (applicable) claim scope.
- `tests/test_cross_claims.py`, `setup`: the inbox Twilio scope drops region. Every cross-claims test and the Ramp award tests that reuse this setup are affected only through this input.
- `tests/test_ramp_award_claim_integration.py`, `historical()`: the injected resolver also declares its resource family; the not-applicable incident is dropped.
- `tests/test_ramp_award_procedural.py`, `exercise`: drops the resource scope's not-applicable incident. The historical probe script is unchanged.
- `tests/test_portfolio_v4.py` and `tests/test_source_config_v4.py`, `SCOPE`: Twilio region dropped.
- W5 inputs, approved by gen5:
  - `tests/test_evidence_applicability_91.py`, `SCOPE`: region dropped, and telemetry rows carry their own literal region.
  - `tests/test_evidence_status_source_91a.py`, `SCOPE`: region dropped.
- `tests/test_release_probes_gent8.py`, `test_d03a_exact_source_identity_flows_from_onboarding_into_claim_intake`: the final create and retry send the applicable scope. The unprovisioned-403 and malformed-422 checks are unchanged.
- `tests/test_northwind_inputs.py`, `test_settlement_cites_unchanged_sla_and_authored_memo_has_one_identity`: the registry still has four fee entries, now reachable by eight lookup keys (four current scopes and four explicit legacy aliases).
- `tests/test_identity_domain_89.py`, helper `_northwind_with_account`: renames the account in `legacy_scope` too.

### New tests

- `tests/test_claim_scope_89.py`: the family table, variant checks, unknown and ambiguous refusal, the Twilio entry, absent-versus-null, and byte-identical ten-field serialization.
- `tests/test_source_config_d04c.py`: W5-labelled, 6 functions and 8 cases, implementing gen5's conditions (a)–(c).

### Region rule refinement

A resource-month claim needs its region only when the terms bind a regional subscription (the condition `claim_identity.resource_remedy` already uses) or when a filing field cites a region. Requiring it always would force callers to invent a region. Accordingly:

- `test_resource_period_requires_resource_and_only_cited_or_subscribed_fields` covers four cases.
- The e86-04 invariant uses a regional resource manifest.
- These tests drop a region that does not apply to their non-regional terms:
  - `tests/test_ramp_award_claim_integration.py`, `historical()`;
  - `tests/test_correspondence_receipt_version.py`, `test_signed_public_source_proof_covers_original_pin_and_new_terms_cannot_repin_it`;
  - `tests/test_ramp_award_procedural.py`, `exercise`.
- `correspondence.create` checks for a regional remedy only when a region is present.

### Blind-acceptance harness (assigned by the integration owner after W4 `f3bb0cc`)

`scripts/blind_acceptance.py` no longer invents scope placeholders. Earlier blind runs used the previous harness, which sent `region="unasserted"`/`"independent-region"`, `incident="unasserted-incident"` and `invoice="unasserted-invoice"`. Their published results and receipts (`BLIND-RESULTS`, earlier evidence) are left exactly as recorded and are not reinterpreted.

- New helper `applicable_scope()` keeps only the obligation fields the governing family needs.
- The general control installs the authored monthly terms and sends only the incident.
- The independent control names its resource and invoice; no incident or region is invented.
- Its status verification links to the authored outage interval's own reference, `facts["intervals"][0]["ref"]`. That is the same value the scope incident used to carry.
- The frozen blind case omits an unknown invoice, incident or region. A 409 at intake is recorded as the new fail code `SCOPE_FAMILY_REFUSED`, and a refused intake records `calculation_available = False`.

`tests/test_blind_acceptance.py` changes, each an expected-behaviour change made by the decision, in harness-behaviour tests rather than sealed gold:

- `test_quarantined_case_still_attempts_signed_denial_and_general_control`: with no installed terms the claim is refused at intake. The expectation changes from `NO_READY_DENIAL_REFUSED` to `SCOPE_FAMILY_REFUSED` (and not `NO_READY_DENIAL_REFUSED`). The quarantine, the generality delivery and the absent calculation are unchanged.
- `test_new_listener_uses_exact_ed25519_grants_without_socket_claim`: uses the built-in Twilio scope (no region), so a claim exists without installed terms. The signed-grant assertions are unchanged.
- `test_separate_generality_control_reaches_signed_inbox_without_holdout_gold` and `test_actual_public_artifact_signed_positive_negative_cure_and_late_routes`: no test edit. They pass through the harness changes above.

Result: `tests/test_blind_acceptance.py` 37 passed, 1 warning.

### Newly merged tests aligned after the integration merge

- `tests/test_evidence_acceptance_91.py`, `telemetry()` (W5 input): the telemetry row carries its own literal region (`"east"`), because the Twilio claim scope no longer has one.
- `tests/test_release_probes_gent8.py`:
  - `SocketApp.signed_event` signs the applicable scope the App provisions and files.
  - `test_socket_source_change_after_approval_blocks_submission` and `test_socket_injected_reply_duplicate_delivery_and_replay_create_no_money` install the governing terms before intake.
  - Their money and authority assertions are unchanged.
