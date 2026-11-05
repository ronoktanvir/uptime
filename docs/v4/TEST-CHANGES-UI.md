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
