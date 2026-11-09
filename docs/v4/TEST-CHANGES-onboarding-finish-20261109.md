# Onboarding strict-template remediation — November 9, 2026

The user resumed onboarding and dispute remediation in parallel, followed by independent evaluation. This lane implements the nine released phrasing classes in the 1a plan without changing eligibility, fee calculations, evidence sufficiency, claim scope or authority. Existing 0/4 first-attempt results and the Backblaze refusal remain unchanged.

## Actual worker

Claude Code subscription authentication was observed as `oauth_token`; the actual worker initialized as `claude-opus-5-5`, session `afe5029a-1c61-44e7-814c-d113a349494c`, with requested effort `xhigh`. It exposes only Read, Edit, Write, Glob and Grep and no MCP servers. Root runs tests and Git; the worker receives public source and authored test inputs only. See [start receipt](evidence/onboarding-finish-20261109/worker-start.json).

## Test changes

Changed existing test: `tests/test_vendor_strict_diagnostics_89.py::test_first_unread_clause_is_the_clause_the_parser_refuses`. A bare title or explicit party statement is now recognized; a second such statement remains a duplicate refusal. The test therefore accepts the exact duplicate-vendor/agreement refusal when no unsupported-clause index exists. No monetary or authority assertion was weakened.

New authored modules: `test_strict_template_remediation_20261109.py` (nine classes, exact spans, duplication, qualifiers, arithmetic), `test_strict_diagnostics_remediation_parity_20261109.py` (classifier/parser parity), `test_parent_financial_controls.py` (hand-calculated tier, fee, cutoff and unknown boundaries), `test_monthly_basis_helper.py` (explicit marker validation) and `test_monthly_basis_compilation.py` (strict/model paths, receipt revalidation, whole-source conflicts, source scope, requirement-card compatibility).

Before committing, the parent changed the newly authored `test_effective_sentences` and `test_unsupported_effective_sentences_refuse_at_their_clause`: bare “until” no longer assumes an inclusive end date. Explicit “until and including” remains supported. New `test_model_cannot_make_ambiguous_until_inclusive` checks the model fallback cannot bypass that refusal.

## Verification

No implementation result is claimed by this preparation commit. Focused results and exact changed-test names will be appended before handoff. Full integration suites are serialized by the integration owner to bound temporary disk usage.

## Explicit monthly evidence marker — first slice

The user approved a separate strict whole-month path during this work. `vendor_monthly_basis.py` validates an optional `complete_service_month/1` manifest marker only with an exact explicit clause, source span, UTC monthly measurement, filing citation, supported remedy and one product/plan. An absent marker returns false; malformed or conflicting opt-in refuses. This pure helper does not activate the path or grant authority. Compiler/model wiring and the source-semantics pin remain integration work.

New tests in `tests/onboarding_finish20261109/test_monthly_basis_helper.py` cover legacy absence, explicit acceptance, partial/rolling/incident/conditional variants, unsupported family/remedy, duplicate or missing citations, invalid spans and ambiguous service scope. **24 passed in 0.24s** using the locked existing environment and a unique temporary directory. No existing tests changed in this slice.

Independent authored development controls in `test_parent_financial_controls.py` recorded the expected red phase before grammar implementation: **4 failed, 18 deselected in 0.56s**, all four at the unsupported source parser, not monetary arithmetic. These controls are not independent evaluation scores.

## Final focused verification and retained failures

Final focused command, using the existing locked environment and `PYTHONPATH` containing this worktree and its test directories:

```sh
uv run --locked --no-sync python -m pytest tests/onboarding_finish20261109 tests/test_vendor_strict_diagnostics_89.py tests/test_vendor_catalog.py tests/test_vendor_family_selection_89.py tests/test_vendor_unlabeled_parties_84r.py tests/test_vendor_filing_override_f4.py tests/test_vendor_model_jobs_runtime.py tests/test_public_proposal_jobs.py tests/test_vendor_resource.py tests/test_vendor_requirements_89.py -q --basetemp=/tmp/uptime-onboarding-final7 -o tmp_path_retention_policy=failed
```

**433 passed, 1 warning in 3.17s.** The warning is the existing Starlette/httpx deprecation. Retained intermediate failures: 1 failed / 258 passed (new model fallback lacked party scope), 1 failed / 387 passed (leading determiner case in new title check), and 1 failed / 431 passed (new requirement-card test omitted its helper argument). Each was corrected before this result. The earlier expected red phase remains recorded. See evidence logs and the completed real-worker receipt.

No unseen evaluation score is claimed. Original 0/4 and Backblaze refusal remain. Full monthly claim core plus all source-semantics dependencies must be integrated atomically and the complete locked suite run before freezing for evaluation. The optional monthly evidence marker is an explicitly approved separate path; legacy absence retains incident requirements.

## Combined collection correction

The first complete locked run on `b1e0680` stopped during collection: **1 warning, 1 error in 1.26s**, with 5,254 items discovered. The new `test_monthly_basis_compilation.py` imported an existing root test fixture through the focused command's extra `PYTHONPATH`; the normal suite did not supply that path. The test now loads the same authored fixture by its exact file path. No application source or expected outcome changed. The failed full log is retained as `merge-b1e0680-pytest.log`; the normal locked suite is rerun after this correction.
