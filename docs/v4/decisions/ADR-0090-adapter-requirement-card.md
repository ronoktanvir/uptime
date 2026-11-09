# ADR 90 — read-only adapter requirement card and generated review drafts

Status: implemented on branch `work/onboarding-generalization-89`; not an approval gate. November 9, 2026, America/Los_Angeles. Workstream: W3 vendor onboarding. Impact: P2 (generated-adapter review surface; no money, authority or identity change).

Number 89 was already taken by a concurrent workstream; the integration owner assigned 90.

## Question

The onboarding assignment asks that generated adapters show source-grounded clauses, an explicit eligible-fee definition, evidence requirements, exclusions and deadlines; that onboarding produce useful cases; and that unsupported terms produce a concrete review requirement. How should that be added without disturbing reviewed adapters or deciding D05?

## Evidence

- Both compilers already refuse at intake unless the vendor, effective dates, period, fee basis/remedy, filing deadline and tiers are cited and every source character is accounted for. The monthly compilers refuse any exclusion or qualifier; the resource compiler refuses unmapped exclusions. Pinned by `test_unrepresentable_terms_are_quarantined`, `test_guarded_propositions_reject_source_divergence_and_material_qualifiers`, `test_unmapped_conditions_cannot_hide_behind_a_valid_proposition` and the new `test_both_monthly_compilers_refuse_a_standalone_exclusion_sentence`.
- What was missing was an explicit per-element view and reviewable scenarios. The artifact's existing `generated_tests` are tier-threshold arithmetic rows only.
- `vendor_terms.SEMANTICS_REVISIONS` hashes the bytes of the compiler, evaluator, model, registry and pricing files. Editing any of them puts every existing reviewed adapter into REVIEW_REQUIRED on redeploy, including the authored Northwind walkthrough adapter and the Aster SHADOW candidate.
- D05 (automatic rule-family selection) is pending. The operator continues to choose the extraction profile.

## Options

- **A (chosen).** New module `uptime/vendor_requirements.py`, outside the semantics hash, and read-only `GET /api/vendors/{id}/requirements` on the existing W3 router. It returns a five-element card, generated shadow drafts for the monthly tiered family, and a report of reviewer tests that reuse draft facts. No state change and no approval effect.
- **B.** Make the card an approval gate inside the registry. Rejected: semantics churn invalidates current reviews, and it duplicates refusals the compilers already enforce.
- **C.** Store drafts in the artifact as generated tests. Rejected: churn, and tests generated from the adapter's own reading would count toward approval.
- **D.** Documentation only. Rejected: it supplies neither the explicit view nor useful cases.

## Opus 5.5 critique

One tool-free call: `claude -p --model claude-opus-5-5 --tools '' --strict-mcp-config --setting-sources '' --no-session-persistence --output-format json`, Claude Code 2.1.318. The envelope reports `modelUsage` `claude-opus-5-5`, session `3b18edac-7a5e-47cd-b7db-0e0e8ce3a8f1`. [Packet](../evidence/onboarding-89/opus-packet-90.txt) · [Response](../evidence/onboarding-89/opus-critique-90.json).

Opus ranked A > D > B > C and did not dissent on the choice. Its defects and the resolution:

| Opus point | Resolution |
|---|---|
| Resource elements present but uncited were reported as FAMILY_DEFINED or PRESENT | **Accepted.** Present-but-uncited is now REVIEW_REQUIRED, except the fixed service-month profile's default evidence set. Test: `test_resource_element_present_without_a_cited_block_requires_review`. |
| Card echoes overlay values | **Already equivalent.** The route uses the same principal dependency, tenant scope and artifact as `GET /api/vendors/{id}`, which already returns the overlay. Test: `test_requirements_expose_nothing_beyond_the_detail_view_for_the_same_principal`. |
| NONE_STATED asserted compiler behavior from outside the hash | **Accepted.** The monthly card now inspects the manifest. Any uncategorized citation field or manifest key makes exclusions REVIEW_REQUIRED. The card reports the evaluator revision it read. A new pin test covers both compilers. |
| Malformed artifacts could raise HTTP 500 | **Accepted.** Card and drafts return refusals instead. Test: `test_malformed_artifacts_summarize_as_refusals_not_errors`. |
| `_money` does not round to cents | **Disagreed.** The monthly evaluator deliberately preserves fractional-cent estimates when the source has no settlement rounding rule. The property sweep uses six-decimal percentages, produces fractional cents, and matches the evaluator exactly. |
| `effective_until` may be exclusive | **Checked.** The evaluator treats it as inclusive (`last > effective_until` refuses). The shadow-preview test confirms the generated out-of-interval month is UNSUPPORTED_RULE. |
| Draft laundering: renaming `derived` to `expected` is trivial | **Accepted, mitigated without a gate.** The response lists reviewer tests whose facts equal a draft's facts and warns. It does not block them: reuse of facts with independently calculated expectations is legitimate. |
| `complete: true` reads as ready to approve; placeholder fee reads as real | **Accepted.** Renamed to `no_open_requirements`. Every draft carries `placeholder_fee_cents` and states the placeholder fee. |
| Property sweep | **Accepted.** `test_property_sweep_drafts_equal_the_evaluator_for_random_tiers_months_and_windows`: 60 derandomized examples. |

## Decision

Adopt A. The card is a review aid and never an approval or dispatch authority (`authority.approval_gate: false`). Approval continues to require independent reviewer expectations, interpretation acceptance where required, and the existing version/revision-bound actions.

## Rollback

Revert the commit. Nothing is persisted, no evaluator revision changes, and existing adapters, reviews and cases are unaffected.

## Revisit trigger

- A compiler revision admits exclusions or new fields in the monthly family. Uncategorized content then shows as REVIEW_REQUIRED, and the card should be extended.
- Overlap reports show reviewers routinely approving with draft facts. Then propose a registry-side provenance requirement as a separate, semantics-changing decision.
- D05 approval. Automatic family selection would consume the same card to report which family's requirements a source meets.
