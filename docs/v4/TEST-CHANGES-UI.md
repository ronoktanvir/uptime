# UI test changes

- `web/ramp_ui.test.cjs`, `pagination bounds 1000 records while all types are selectable; source and money stay exact`: removed the assertion for a repeated row disclaimer. Native amount, finding amount, exact source, freshness, incomplete coverage, pagination and permission assertions remain.
- `web/ramp_ui.test.cjs`, `detail and plan are encoded GETs, never POST; receipt is scoped and unsafe link stays absent`: checks the user-facing “Price cap review” type and ordinary Contract finding heading instead of the removed repetitive scenario banner; the request fixture retains the exact `SYNTHETIC_INVOICE_CAP` backend classification. GET-only, scoped receipt, secret and unsafe-link protections remain.
- `tests/test_ramp_ui_v4.py`, `test_ramp_browser_navigation_and_read_only_plan`: changed only the provider link’s accessible name from “Open record in Ramp sandbox” to “Open record in Ramp”; its exact sandbox URL and all read-only/navigation assertions remain.

## Configured workspace workflow

- `web/browser-contract.test.cjs`, harness and `default landing is Ramp, deep links encode opaque IDs, explicit rehearsal retains dashboard`: fixture now returns the normal unconfigured workspace response `{workflow:null}`. The first-request assertion checks capability discovery before the unchanged native-worklist request; source text, authorization, encoded routes and financial assertions remain.
- `tests/test_ramp_ui_v4.py`, `test_ramp_browser_navigation_and_read_only_plan`: serves the new workspace UI static module and returns `{workflow:null}` from workspace discovery, preserving the existing native-worklist integration scenario.
- New `web/workspace_ui.test.cjs` verifies separate financial stages, exact decimals and missing amounts, source citations, scripted reviewer authority, absence of classification chrome in the configured product, encoded action IDs, duplicate suppression, refresh after lost responses, and stale-control invalidation.

- `web/browser-contract.test.cjs`, new `configured workspace renders inside the finance shell and keeps native records accessible` and `workflow authorization and server errors never silently fall back to native records`: verify configured composition in the existing shell, direct native-record access, and failure propagation for 403/500. Harness now supports an explicit workflow projection/status and loads the workspace renderer.

## Original views and source records

- No existing test assertions changed in this increment. Added `web/v4_ui.test.cjs`, `source identity stays exact inside ordinary record disclosures and intake origin keeps wire values`, to verify that the source identity remains inspectable in a closed record disclosure and document-origin copy preserves exact backend classifications. Existing financial, source, authorization and missing-provenance assertions all remain.
- Added direct main-navigation links to existing Vendor contracts and Correspondence routes; original case ledger, Ramp records and integration permissions remain reachable. Repeated source tags now live in ordinary Source record disclosures; service values are unchanged.

## Final source presentation correction

The latest product direction excludes environment classifications from expandable UI details as well as the main view. This supersedes the prior Source record disclosure approach; raw API classifications and audit exports remain unchanged. Ordinary document references, exact provider destination, receipt verification and scripted principal detail remain visible.

- `web/browser-contract.test.cjs`, `ledger consumes API data, keeps sources exact and treats markup as text`: replaced the visible `SIMULATED_VENDOR` expectation with an assertion that backend classification labels do not render. The incoming fixture keeps both exact source values; authorization, request path, markup safety and money assertions remain.
- `web/ramp_ui.test.cjs`, `pagination bounds 1000 records while all types are selectable; source and money stay exact`: removed only the visible `LIVE_RAMP_SANDBOX` classification expectation. Exact native amount, freshness, coverage, pagination and permission assertions remain.
- `web/v4_ui.test.cjs`, `case inspector shows receipt timeline, exact source, IDs, unknowns and safe text`: removed only the visible `SIMULATED_VENDOR` classification expectation. The fixture source is unchanged; scoped receipts, IDs, missing values, exact zero, safe text, credential omission and encoded authorized action remain asserted.
- `web/v4_ui.test.cjs`, `portfolio comparison preserves exact decimals, zero, unknown and server cohorts`: removed only visible `FIXTURE` and `LIVE_RAMP_SANDBOX` classifications. Both server cohorts and exact values including zero and null remain asserted.
- `web/v4_ui.test.cjs`, `failed reads expose no writable intake, no error details, and unknown provenance is explicit`: changed the missing-reference copy assertion from `Provenance unknown` to `Source references not provided`. Failed reads still expose no forms or private diagnostics, and absent source references remain explicit.
- The new origin-presentation test is now named `document origin copy preserves exact wire classifications without rendering source labels`; it asserts that display copy preserves the exact submitted origin values. New workflow tests cover agreement amendment dates/references, CalyxQuay shadow/approval/activation/rollback history, the scripted principal detail, unchanged source payload, and separate $1,000 exposure and $9,600 outstanding balance.

Final focused validation: 42 Node behavioral checks pass. Both native-browser checks pass: the existing Ramp worklist navigation/read-only plan check and new `test_configured_workflow_keeps_evidence_money_and_original_navigation_reachable`, covering separate monetary amounts, citations, reviewer detail, navigation and 390px overflow. The first new-browser run failed because its static-route fixture omitted dynamically requested `v4_ui.js`/`v4_style.css`; the route allowlist was corrected and the retest passed. No production assertion was relaxed for that harness failure.

## Legacy presentation headings

Known legacy headings/actions now use ordinary names (`Run shadow checks`, agreement/invoice/evidence headings, estimated future-service credit and invoice cap review). Generated evidence summaries that only describe authoring or environment identity now show their exact returned reference/digest instead. Financial stages and missing-evidence/verification failures remain; linked source quotations are unchanged. No existing test assertions changed in this increment.
