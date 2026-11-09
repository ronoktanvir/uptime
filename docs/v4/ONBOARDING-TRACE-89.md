# Onboarding trace, vendor specialization inventory and decision boundaries (workstream 89)

W3 vendor onboarding, November 9, 2026. Branch `work/onboarding-generalization-89` from `v4/integration` `03b372e`. Line references are to that base.

This document separates four results that must not be merged into one claim: **raw extraction quality**, **validation success**, **useful supported coverage** and **human approval**. A safe refusal is not successful onboarding.

## 1. Preserved unfinished work

`work/onboarding-evaluation-85` (HEAD `a542a21`) was inspected and left untouched. Its four uncommitted files are byte-identical to the pause checkpoint (`evidence/pause-20261106/checkpoint.json`):

| File | SHA-256 |
|---|---|
| `scripts/evaluate_onboarding_85.py` | `ed381d85f0a67e71314deeea4c928d1f3de3db0f8e9d62a8bb2e495e2f991674` |
| `tests/test_onboarding_evaluation_85.py` | `3f739ffbcbb24d8754c65ac537e94762ed5e9364df555272f4c94b81cc81bf64` |
| `docs/v4/evaluation85/HARNESS-INTERFACE.md` | `0f845c7a8fd4f94e1c5dd0c15eedb240c4ff51a77fa5f1fdfaca98824c330a6f` |
| `docs/v4/evaluation85/coding-receipt.json` | `b9dd1c93c89fcec6be8860535bb8bb72534a8a4228cdc19f5f6f8f52abdcd058` |

That harness evaluates the frozen corpus84 with an **evaluator-supplied family label** (`monthly_tier` and others mapped to a profile). It therefore cannot measure family discovery. This workstream adds no competing corpus runner and did not open corpus84 inputs or sealed answers.

## 2. Application path, source to approval eligibility

| Stage | Where | What decides it |
|---|---|---|
| Source submission | `vendor_api.py` `POST /{id}/proposal-access`, `/proposal-jobs`; `vendor_model_jobs.ProposalRequest` (line 58) | A reviewer submits an exact public `Document` **and an explicit `profile`**: `monthly`, `monthly-propositions` or `resource-month`. The browser requires "Choose extraction profile" (`web/v4_ui.js` 250–287). |
| Model proposal | `vendor_model.serialize_proposal_request`, `proposal_input` (186) | Tool-free Opus 5.5 call through the pinned public transport. Only document text and instructions leave the machine; the overlay is not part of the input type. |
| Extraction validation | `vendor_model._validated_result` → `proposal_receipt` → `validate_proposal` (83) | Strict compiler `vendor_terms.compile_terms` (185); propositions compiler `compile_propositions` (383); resource compiler `vendor_resource_terms._compile_resource` (308). Failure → job `REFUSED`, reason `proposal_validation_failed` (`public_proposal_jobs.py` 318). |
| Candidate intake | `vendor_api` `POST /{id}/proposal-jobs/{job}/candidate` → `vendor_registry.install` (278) | Receipt is fully revalidated (`job_extraction`, 250). Private overlay bound by `bind_overlay` (295). Any failure → QUARANTINED with a generic public reason. |
| Version | `vendor_terms.candidate_version` (378) | `fingerprint(manifest incl. source SHA-256, overlay, extraction, semantics_revision)`. |
| VALIDATED → SHADOW | `install` 333–337 | Automatic after a successful compile and overlay bind. |
| Shadow evaluation | `shadow_preview` (443); `submit_tests` (389) | Reviewer-authored independent expectations. Approval needs every row and generated arithmetic check to pass, plus positive and refusal coverage. |
| Interpretation | `act` `interpret` (464) | Required for model-proposition adapters. The approving reviewer must be the interpreting reviewer. |
| Approve / activate | `act` (455–490); action IDs from `_key` (221) | IDs bind tenant, subject, vendor, version, revision and operation. Activation requires the approving principal. |
| Staleness | `_compatible` (113), `_capability` (156) | A changed evaluator file, semantic binding or governing-fee context drops current authority to REVIEW_REQUIRED at read time. |

## 3. Vendor-name branches, family hints and fixture assumptions

**Generic V4 path.** `vendor_*.py`, `public_proposal_*.py` and the registry contain **no branch on a vendor name**. Vendor identity is data: the cited `vendor` clause, the installation slot ID and the overlay.

| Item | Location | Classification |
|---|---|---|
| Atlassian/Jira lab | `onboarding.py`, `onboarding_extract.py`, `onboarding_rules.py` (`SCHEMA = 'atlassian-utc-tiers/1'`, Jira experiences, `simulated_atlassian_logs`) | **Vendor-specific control flow, by design.** Preserved V3 D7 lab. Not evidence of unseen-vendor learning. |
| CalyxQuay exception | `local_review_exception.py` (`PREFIX`, `vendor: Literal["calyxquay"]`) | **Legitimate fixed authority scope** for decision 88 (W0-owned). Not adapter logic. |
| `twilio.py` interval helpers | `vendor_resource_eval.py` 7, `vendor_resource_scopes.py` 4 import `_merge`, `_subtract`; `twilio.py` is in the resource-month semantics file set | **Naming coupling, not vendor control flow.** Moving the helpers would change the semantics hash and require re-review. Not changed. |
| Extraction profile | `ProposalRequest.profile`; UI select; CLI `--profile` / `--allow-propositions`; env `UPTIME_MODEL_PROPOSITIONS` | **Manually supplied rule-family hint.** This is the D05 boundary (§4). |
| Evaluation85 family labels | `scripts/evaluate_onboarding_85.py` (uncommitted) | Evaluator-supplied family hint for a frozen measurement. |
| Monitor source literals | `vendor_eval.py` 109 (`simulated_vendor`); `vendor_resource_eval.py` 207 (`simulated_vendor`, `synthetic_customer`); `vendor_service_month.py` 270 | **Fixture-bound evidence assumption.** A real vendor or customer monitor cannot satisfy these evaluators. They are synthetic-only paths, not real evidence connectors (D07). |
| USD only | `vendor_terms.py` 302; `vendor_eval.py` 75 | Declared support limit. Other currencies refuse. |
| `synthetic_public` classification and heading | `vendor_terms.py` 175–179, 266 | Declarative test-source provenance. Accepted alongside `public`. |
| Model prompts | `vendor_model.PROMPT`; `vendor_resource_terms.PROMPT` | Family-specific extraction instructions, with no vendor names. Generic examples only. |

## 4. Automatic family selection (D05, decided 2026-11-09)

**D05 was decided on 2026-11-09: auto-select plus human approval.** Phase 1 is implemented ([decision 97](decisions/ADR-0097-automatic-family-selection.md)).

`POST /api/vendors/{id}/proposal-access` and `/proposal-jobs` accept `{"document": …, "profile": "auto"}`. Uptime then selects the family itself:
1. An offline deterministic parse, guarded against resource-family language.
2. Otherwise, one exact-approved proposal job per supported family.
3. A selection derived from the deterministic validators: `SELECTED`, `AMBIGUOUS`, `NO_SUPPORTED_FAMILY` or `INCOMPLETE`, each with concrete review requirements.

Ambiguity is monotone across attempts and reviewers. `GET /api/vendors/{id}/requirements` shows the installed artifact's `family_selection`.

**Phase 2 (merged at `9b2097c`):** candidate install accepts only the automatically selected job, and the browser sends `profile: "auto"` with no profile select. The unseen-vendor proof follows [the runbook](D05-UNSEEN-VENDOR-RUNBOOK.md). gent8 selects the source by a sealed pre-registered rule; Ronok performs the promotion and rollback.

## 5. Implemented in this workstream

[Decision 90](decisions/ADR-0090-adapter-requirement-card.md): `uptime/vendor_requirements.py` and read-only `GET /api/vendors/{id}/requirements`.

- **Requirement card.** Five elements: source clauses, eligible-fee definition, evidence requirements, exclusions and deadline. Each is `PRESENT` with citation IDs, `FAMILY_DEFINED`, `NONE_STATED`, or `REVIEW_REQUIRED` with a concrete requirement. Covers both supported families. Unknown families and quarantined intake return review requirements, not a card.
- **Generated drafts (monthly tiered family).** Per tier, the first whole-minute downtime past the exclusive threshold and one minute less. Evidence controls: public status only, incomplete month, exclusions not removed, unknown fee, other account. Deadline boundary at the last timely second versus the exclusive cutoff. A month outside the governed interval. Outcomes are derived with exact fractions from the cited percentages and a labeled placeholder fee. Drafts use `derived`, not `expected`, so they cannot be posted unchanged as the independent suite (HTTP 422). Reviewer tests that reuse draft facts are reported.
- **Not generated:** drafts for completed-step credits (need a trusted governing-fee context) and for resource-month (need customer interval, fee-line and filing records). The response states these reasons.
- The module is outside `vendor_terms._PROFILE_FILES`. Existing reviewed adapters, including Northwind and Aster, keep their state.

### Item 5: adapter content requirements

Already enforced at intake by both compilers (cited vendor, dates, period, fee basis/remedy, filing deadline, tiers; full source coverage; unmapped exclusions refuse). This workstream makes the five elements explicit and testable. It does not add a registry gate (rejected option B in decision 90).

### Item 6: approval bound to exact versions

Already implemented and tested; no code change was needed. Version = `fingerprint(manifest incl. source SHA-256, overlay, extraction, semantics_revision)`. Action IDs bind version and revision. Evidence:

- `test_vendor_catalog.py::test_source_cycle_quarantine_revoke_and_review`: stale approve/activate IDs refuse after reinstall.
- `::test_material_source_revision_requires_new_tests_and_blocks_prior_dispatch`
- `::test_principal_tenant_reviewer_and_subject_bound_actions`
- `::test_private_filing_amendment_changes_only_bound_account_scope`: overlay amendment binding.
- `::test_changed_installed_semantics_requires_new_review_and_preserves_prior_receipt`
- `::test_pre_revision_approval_cannot_activate_on_current_semantics`
- `::test_rollback_restores_compatible_previously_reviewed_version`

### Item 7: unseen vendor

| Result | Status |
|---|---|
| New vendor through the ordinary HTTP path, no vendor-specific code | **Shown for an authored source only:** `test_new_vendor_name_reaches_shadow_with_useful_drafts_and_no_vendor_code` ("Halcyon Queueing Ltd", February 2027, three tiers, 30-day window). It reaches SHADOW, 14 drafts all match the shadow evaluator, and no package file names the vendor. Uses the strict offline parser and an operator-supplied family, so it is **not** D05 discovery and **not** an independently chosen real vendor. |
| Independently chosen real unseen vendor, actual model extraction | **Not run.** No new inference was performed in this workstream. Prior public baseline: 0/4 supported contract extractions (`evaluation76/BASELINE.md`). Running it needs an explicitly chosen public source, a public-inference approval of the exact request, and the frozen-corpus protocol to be respected. Under D05, the team may also need to name the vendor. |
| Human approval | **None by this workstream.** All lifecycle actions in tests use the `scripted-test-reviewer` identity on disposable databases. |

### Unsupported cases and refusal reasons

Intake quarantine reasons stay generic by design, because exception text can quote private overlays or model output.

**Refused proposal jobs now carry a verified public diagnostic** ([decision 90 addendum](decisions/ADR-0090-adapter-requirement-card.md#addendum-public-refusal-diagnostics-for-vendor-proposal-jobs)). `GET /api/vendors/{id}/proposal-jobs/{job}` returns `public_diagnostic` with:

- the validator's own finding as a fixed code and explanation;
- the exact public passage it names, re-sliced from the source after the job's pinned context is re-verified;
- the required terms that the validator established are missing.

Codes:

| Code | Meaning |
|---|---|
| `UNSUPPORTED_SOURCE_MATERIAL` | The validator could not represent this passage. |
| `EXTRACTION_FLAGGED_UNSUPPORTED` | The extraction flagged this passage, and the validator refused on that basis. |
| `UNSUPPORTED_BLOCK_PROPOSITION`, `ISSUER_AUTHORITY_UNESTABLISHED` | Resource-month block findings. |
| `REQUIRED_TERMS_MISSING` | Required terms are absent; for example, "claim filing deadline". |
| `SOURCE_COVERAGE_INCOMPLETE` | The source does not establish every required term. |
| `PROPOSAL_NOT_SOURCE_GROUNDED` | The extraction did not quote the source exactly. |
| `OUTPUT_NOT_STRUCTURED` | The extraction output was not structured. |
| `PUBLIC_PROPOSITION_UNESTABLISHED` | Fallback with no location. |

The browser does not render it yet; `web/` belongs to W7, and a request has gone to the integration owner. A refusal remains a refusal. It is not successful onboarding.

## 6. CalyxQuay recorded review: documentation reconciliation

`LOCAL-REVIEW-EXCEPTION.md` and `DEMO-PATH-87.md` predate the recorded review. The workspace record (read with SQLite `mode=ro&immutable=1`; no key file opened, no action taken) shows:

- Revisions 1–5: scripted preparation by `scripted-test-reviewer`, 2026-11-08 01:50Z.
- Revisions 6–9: actions recorded under account `ronok-tanvir`, 2026-11-09 10:07–10:08Z: interpret, approve, activate, roll back.
- Final state: REVOKED at revision 9, with no active version.

The registry labels these actions `authenticated_reviewer`; the record alone does not establish physical presence. [Receipt](evidence/onboarding-89/calyxquay-recorded-review.json). The historical documents and receipts are left unchanged; updating shared status records is the integration owner's job.

## 7. Accepted findings awaiting a semantics revision

W5 reported these against `vendor_terms.py` at `03b372e`, and the integration owner routed them to W3. Each is accepted as a finding and not yet implemented. `vendor_terms.py` is in the reviewed-semantics hash, so fixes must land together as one semantics revision that the team agrees to re-review. Editing it piecemeal would put every reviewed adapter, including the Northwind walkthrough and Aster SHADOW, into REVIEW_REQUIRED.

| Finding | Status | Detail |
|---|---|---|
| F4: private filing override has no effective date or source hash | Blocked on D07 | Add explicit `effective_from` (and source SHA-256); apply only to months starting on or after it; missing or contradictory dates stay unsupported. Interim, with no code change: install a mid-term addendum as a separate slot whose overlay `effective_from` is the addendum date. |
| F5: resource agreement unbound when the manifest agreement is null | Blocked on agent1's D03 identity interface | Bind the private agreement to the public document explicitly, or record that the public document governs. |
| F6: `GoverningTerms.evidence_sha256` only format-checked | No decision dependency | Verify it against stored signed evidence. Until then the documentation calls it an operator-supplied reference. |
| F9: legacy Atlassian PDF path keeps only hashes | Relevant only if D07 adopts PDF intake | Store originals content-addressed, keep page-mapped derived text, and treat numbers read from derived text as needing review. |

## 8. Requirement status after November 9 (W3)

| Requirement | Status | Detail |
|---|---|---|
| ONB-1, discovery from Ramp records | **Not met; deferred until after the demo** (integration owner) | Stored Ramp vendor records keep IDs only; names are stripped as private text. Discovery must therefore be by exact Ramp vendor ID through a reviewed binding between an adapter slot and a Ramp vendor ID. That binding is an identity and authority record (D03; W1 owns `ramp_records`), and it is not decided. Proposal: (a) a read-only exact-ID discovery list; (b) the binding, owned by W1/W0. |
| ONB-3, submission channels | Visible, not delivered | The requirement card shows a cited submission channel and request fields for resource-month sources. Delivery stays with a configured, authorized channel (D08). |
| ONB-4, generated cases | Extended | Drafts cover tier boundaries, evidence controls, unknown fee, deadline boundary, timezone offsets, private-amendment months and out-of-interval months. Drafts are never the independent suite. |
| O3 and item 7, unseen vendor | Pending run | Automatic selection, phase 2 and the runbook are merged. The proof needs gent8's run and Ronok's own promotion and rollback. |

