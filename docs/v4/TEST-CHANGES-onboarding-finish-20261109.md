# Onboarding strict-template remediation — November 9, 2026

The user resumed onboarding and dispute remediation in parallel, followed by independent evaluation. This lane implements the nine released phrasing classes in the 1a plan without changing eligibility, fee calculations, evidence sufficiency, claim scope or authority. Existing 0/4 first-attempt results and the Backblaze refusal remain unchanged.

## Actual worker

Claude Code subscription authentication was observed as `oauth_token`; the actual worker initialized as `claude-opus-5-5`, session `afe5029a-1c61-44e7-814c-d113a349494c`, with requested effort `xhigh`. It exposes only Read, Edit, Write, Glob and Grep and no MCP servers. Root runs tests and Git; the worker receives public source and authored test inputs only. See [start receipt](evidence/onboarding-finish-20261109/worker-start.json).

## Test changes

Implementation and tests are in progress. No existing test has changed yet. The classifier parity tests will need named migrations where formerly unrecognized source forms gain explicit support; refusals for contradictory or ambiguous terms must remain.

## Verification

No implementation result is claimed by this preparation commit. Focused results and exact changed-test names will be appended before handoff. Full integration suites are serialized by the integration owner to bound temporary disk usage.

## Explicit monthly evidence marker — first slice

The user approved a separate strict whole-month path during this work. `vendor_monthly_basis.py` validates an optional `complete_service_month/1` manifest marker only with an exact explicit clause, source span, UTC monthly measurement, filing citation, supported remedy and one product/plan. An absent marker returns false; malformed or conflicting opt-in refuses. This pure helper does not activate the path or grant authority. Compiler/model wiring and the source-semantics pin remain integration work.

New tests in `tests/onboarding_finish20261109/test_monthly_basis_helper.py` cover legacy absence, explicit acceptance, partial/rolling/incident/conditional variants, unsupported family/remedy, duplicate or missing citations, invalid spans and ambiguous service scope. **24 passed in 0.24s** using the locked existing environment and a unique temporary directory. No existing tests changed in this slice.

Independent authored development controls in `test_parent_financial_controls.py` recorded the expected red phase before grammar implementation: **4 failed, 18 deselected in 0.56s**, all four at the unsupported source parser, not monetary arithmetic. These controls are not independent evaluation scores.
