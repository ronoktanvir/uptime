# Identity and scope: changes that depend on D03 and D04 — decision 89

**Status:** characterization only. **No D03 or D04 option is adopted or recommended here.** Both remain pending team decisions in the [team decision handoff](TEAM-DECISION-HANDOFF.md). The team-facing alternatives and their migration consequences are owned by the integration workstream (`docs/v4/integration90/D03-D04-ALTERNATIVES.md` on `work/integration-90`). This page lists exactly which code, stored records and tests a chosen option must change or deliberately preserve, so the decision can be implemented once without rediscovery.

Audited source: `03b372e`. Executable reproduction: `tests/test_identity_domain_89.py`. Line numbers are as of that commit.

## What is reproduced

| Defect | Reproduction | Observed |
| --- | --- | --- |
| D03: identity domains disagree | `test_identity_validators_disagree_on_exact_source_values` (14 values × 8 validators) | Onboarding accepts `Cedar Orrery Studio`, `Acme, Inc.`, `O'Neil & Sons (US)`, `Plan+Plus`, 97–100 character values **and a trailing space**. Claim intake `Scope` refuses all of them. |
| D03: preserved refusals still occur | `test_recorded_claim_intake_refusals_reproduce_on_current_source` | The exact preserved request bodies in `evidence/pause-20261106/e86-01.json` and `e86-04.json` produce the same 422 error set (types and locations) on current source. |
| D03: a valid adapter cannot reach money | `test_spaced_onboarded_account_is_stranded_before_claim_and_governing_fee` | With only the account changed to `Harborline Analytics`, onboarding and the economic claim key accept it. Claim `Scope` refuses it, so no governing-fee context can be issued. Identical Northwind January economics fall from **ELIGIBLE 2400.00** to **INSUFFICIENT_EVIDENCE** (`governing_fee_context`), which is not an evidence problem. |
| D03: trailing space | `test_trailing_space_account_passes_onboarding_but_not_economic_identity` | `bind_overlay` keeps `harborline-001 ` untrimmed; `claim_identity` refuses to form a key for it. |
| D04: universal scope | `test_claim_scope_requires_every_field_for_every_obligation_family`, `test_recorded_scopes_lack_fields_their_obligation_may_not_need` | All ten `Scope` fields are required for every claim. The recorded whole-service case lacks component, incident and region; the resource case lacks invoice, incident and region. |
| D04: authored placeholders | `test_northwind_whole_service_scope_carries_authored_values_the_evaluator_never_reads` | Northwind's whole-service monthly claim carries authored component, incident and region values that the monthly evaluator never reads. |

## Identity validators in force

| Validator | Location | Accepts spaces | Other notable behaviour |
| --- | --- | --- | --- |
| Onboarding `NAME` | `uptime/vendor_terms.py:20`, used at `:304-306`, `:325` | Yes | Also `& ( ) , ' + .`; allows a trailing space; ≤100 chars; ASCII-only first character. |
| Resource manifest vendor/agreement | `uptime/vendor_resource_terms.py:62-63` (`grounded`), used at `:485` | Yes | Only grounded in source text (token-normalized comparison) and ≤160 chars; no character class. |
| Claim `Scope` `Id` (account, contract, component, invoice, incident, region) | `uptime/correspondence_types.py:7` | No | `[A-Za-z0-9._:/-]`, ≤96. |
| Claim `Scope` `Name` (vendor, service) | `uptime/correspondence_types.py:8` | Internal only | No `& ( ) , ' + :`; must end alphanumeric. |
| Economic claim key | `uptime/claim_identity.py:28-36` | Yes | Refuses surrounding whitespace and control characters; NFC + casefold for vendor and service only. |
| Ramp terms `Ref` | `uptime/ramp_terms_store.py:25`; `uptime/ramp_findings.py:82-84` | No | `[A-Za-z0-9_.:/#-]`. |
| Dispute wire | `uptime/disputes_wire.py:19-21` | Yes | Refuses surrounding whitespace and control characters. |
| Reconciliation record | `uptime/reconciliation.py:19-24` | Yes | Refuses surrounding whitespace; must be printable. |
| Ledger allocation scope | `uptime/allocations.py:53-62` | Yes | **Applies NFC and strips whitespace** before comparison, and canonicalizes UUIDs. This is the only identity path found that trims. |
| Evidence incident and component | `uptime/evidence.py:51-58` | No | `[a-zA-Z0-9_-]+`, ≤100. |

## Sites a D03 implementation must change or explicitly preserve

“Hash” means the value is fingerprinted, signed or stored as a key; changing its representation breaks recomputation against stored rows unless a versioned migration preserves the old bytes.

| Stage | Site | Fields | Nature |
| --- | --- | --- | --- |
| Onboarding | `uptime/vendor_terms.py:304-306` (`bind_overlay`) | overlay agreement, product, plan, account, fee line | validate |
| Onboarding | `uptime/vendor_terms.py:378-380`; `uptime/vendor_registry.py:116`, `:318-324` | whole overlay → `candidate_version` | hash (artifact primary key) |
| Onboarding | `uptime/claim_identity.py:62-79` (`resource_remedy`, called from `bind_overlay`) | resource ID, region | validate; `/` and `aggregate-service` reserved |
| Evidence | `uptime/correspondence_types.py:17-27`, `:86-101`, `:119-171`, `:210`, `:322-332` | scope and signed record identities | validate |
| Evidence | `uptime/source_config.py:44-48`, `:69-84`, `:119-123` | full scope; record account, agreement, product, resource | exact equality with the granted scope |
| Evidence | `uptime/correspondence.py:254-278` | scope inside the delivery digest | hash (idempotency) |
| Filing | `uptime/correspondence.py:50-51`, `:150-154`, `:180-182` | subscription ID and exact-scope grant hash | hash |
| Filing | `uptime/correspondence.py:187-200`, `:228` | raw vendor/account/contract/service/month(+component, region) draft key | hash, `UNIQUE` |
| Filing | `uptime/v4_routes.py:69-78` | scope ↔ stored manifest vendor and overlay account/agreement/product | exact SQL equality |
| Filing | `uptime/governing_fees.py:109`, `:131-136`, `:253-255` | scope key; scope ↔ overlay | hash; exact equality |
| Filing | `uptime/claim_identity.py:50-59`, `:92-140`, `:156-159`, `:196` | economic identity v2, v1 key, `HIST-` IDs | hash (immutable registry rows) |
| Filing | `uptime/mandates.py:91-100`, `:111` | `scope_sha256`, `packet_sha256` | hash inside Ed25519-signed mandates |
| Disputes | `uptime/disputes_wire.py:33`, `:87-95`; `uptime/disputes.py:323`, `:348-356`; `uptime/claim_identity.py:143-153` | ticket digest, obligation key, legacy Twilio mapping | hash |
| Reconciliation | `uptime/reconciliation.py:95-99`; `uptime/allocations.py:285-292`; `uptime/ramp_credit_sync.py:401`, `:469-471` | ledger scope fields | normalize (NFC + strip) then compare |
| Ramp awards | `uptime/ramp_award_attribution.py:740-744`, `:892-894` | claim key; recomputed dispatch hash vs signed `dispatch_sha256` | hash; failure is `LOCAL_FILING_CHANGED` |
| Northwind | `uptime/northwind_workflow.py:175-187`; `scripts/setup_northwind.py:31-33` | scope ↔ overlay and manifest | exact equality; package hash |

Two related name-shaped rules sit on these paths and must be kept or replaced deliberately: `uptime/correspondence.py:193` chooses the draft obligation-key shape with `scope.vendor.casefold() != "twilio"` on the **live** filing path, and `uptime/claim_identity.py:275` assigns the availability remedy to unreserved historical inbox records labelled `twilio`.

## Sites a D04 implementation must change

| Site | Current requirement |
| --- | --- |
| `uptime/correspondence_types.py:17-27` (`Scope`) | All ten fields required for every obligation family. |
| `uptime/correspondence.py:187-200` | Draft key appends component (and region when regional) for every non-Twilio vendor. |
| `uptime/v4_routes.py:69-86` | Adapter resolution compares `scope.component` with the overlay resource ID and `scope.region` with the subscription region. |
| `uptime/governing_fees.py:131-136` | `FeeEntry` requires a complete `Scope`, so a whole-service month needs component, incident and region to receive a fee context. |
| `uptime/correspondence.py:150-154`, `:180-182`; `uptime/mandates.py:99` | Grants and mandates hash the full ten-field scope. |
| `fixtures/northwind` scopes | Authored component, incident and region placeholders; preserved in signed history and must stay verifiable. |

## Stored records that must remain verifiable

Whatever option is chosen, existing bytes must keep verifying: v1 and v2 claim-dispatch rows and `HIST-` receipts (`claim_identity`), correspondence grants and delivery digests, signed mandates, Ramp award statements and their `dispatch_sha256`, onboarded `candidate_version` keys, and the Northwind package and specimen signatures. No identity may be repaired by trimming, slugging or case folding, and the existing `allocations.canonical` strip must be reconciled with that rule rather than extended.

## Reviewed-approval churn

Editing any of `contracts.py`, `vendor_terms.py`, `vendor_eval.py`, `vendor_model.py`, `vendor_registry.py`, `claim_identity.py`, `credit_steps.py`, `pricing.py`, `pricing_terms.py`, `governing_fees.py` (and, for resource adapters, the `vendor_resource_*`, `vendor_bindings.py`, `vendor_service_month.py` and `twilio.py` files) changes `vendor_terms.SEMANTICS_REVISIONS`. Active adapters then require reinstallation and renewed review. Editing `pricing.py`, `pricing_terms.py`, `governing_fees.py`, `credit_steps.py` or `vendor_eval.py` also changes `governing_fees.dependency_digest` and revokes issued fee contexts. `correspondence_types.py` is in neither list. A D03 change that touches `claim_identity.py` or `vendor_terms.py` therefore carries this re-review cost.

## Tests a D03 or D04 change would have to update

Each must be updated deliberately and recorded by exact name in a test-change ledger.

| Test | Coupling |
| --- | --- |
| `tests/test_identity_domain_89.py::test_identity_validators_disagree_on_exact_source_values` | Pins today's acceptance table (D03). |
| `tests/test_identity_domain_89.py::test_onboarding_accepts_identities_that_claim_intake_or_claim_key_cannot_represent` | Pins the stranded set (D03). |
| `tests/test_identity_domain_89.py::test_recorded_claim_intake_refusals_reproduce_on_current_source` | Pins the preserved 422 details. The receipts themselves stay immutable (D03, D04). |
| `tests/test_identity_domain_89.py::test_spaced_onboarded_account_is_stranded_before_claim_and_governing_fee` | Pins the degradation (D03). |
| `tests/test_identity_domain_89.py::test_trailing_space_account_passes_onboarding_but_not_economic_identity` | Pins onboarding/key disagreement (D03). |
| `tests/test_identity_domain_89.py::test_claim_scope_requires_every_field_for_every_obligation_family` | Pins the universal scope (D04). |
| `tests/test_identity_domain_89.py::test_recorded_scopes_lack_fields_their_obligation_may_not_need` | Pins the missing-field sets (D04). |
| `tests/test_identity_domain_89.py::test_northwind_whole_service_scope_carries_authored_values_the_evaluator_never_reads` | Pins the placeholders (D04). |
| `tests/test_financial_coverage_89.py::test_contradicting_account_observation_is_reported_as_missing_scope` | Pins scope-mismatch classification (overlaps D03). |
| `tests/test_correspondence_filing_refs.py::test_display_name_does_not_relax_wire_id_or_signed_source_scope` | Asserts a spaced service reference is refused at the signed source (D03). |
| `tests/test_correspondence_plan_refs.py::test_signed_plan_bytes_are_never_trimmed_casefolded_or_unicode_normalized` | Asserts exact plan bytes, including refusal of surrounding spaces (D03; its no-normalization rule must survive). |
| `tests/test_correspondence_plan_refs.py::test_reviewed_display_plan_uses_existing_source_id_without_widening_wire_type` | Asserts a spaced plan is not a wire ID (D03). |
| `tests/test_claim_identity.py::test_registry_requires_transaction_and_canonical_ids` | Asserts a leading space is refused (D03; should survive under any no-trim option). |
| `tests/test_economic_scope_delimiters.py::test_safe_legacy_keys_and_reservation_bytes_survive_retry` | Pins reservation bytes (D03 migration). |
| `tests/test_economic_scope_delimiters.py::test_identity_source_bytes_change_reviewed_evaluator_hash_in_fresh_process` | Pins the approval-churn coupling (D03). |

The matrix rows `IDS-D03-1`, `IDS-D03-2` and `IDS-D04-1` in the [financial coverage matrix](FINANCIAL-COVERAGE-89.md) change status when the decided repair lands.

## Option-neutral acceptance checks

These come from the assignment and apply to any chosen option:

- The same exact source identity survives onboarding, grants, invoice evidence, filing, interpretation, disputes and reconciliation, with no trimming, slugging or case folding introduced.
- All existing stored hashes, receipts and signatures listed above still verify; alias and duplicate-claim controls still refuse a second filing for one economic obligation.
- With only the account representation changed, the Northwind January case returns the same `ELIGIBLE 2400.00` as the authored identity.
- A whole-service monthly claim and a resource or regional claim both reach their correct workflows; missing *required* scope still refuses, and “not applicable” stays distinct from “unknown”. No incident, region or invoice reference is invented to satisfy a schema.

## Not done here

No source, schema, stored record, fixture, receipt or test outside the two decision-89 test files was changed. No Opus consultation was run for D03/D04: the integration workstream runs the single combined critique. No model, Ramp, vendor or reviewer action occurred.
