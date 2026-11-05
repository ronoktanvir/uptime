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

- Added `invoice periods and source usage details preserve server observations and null without arithmetic` for optional production-projected invoice dates, source evidence values/references and evaluator trace. Missing coverage remains missing and the monthly credit remains null. No existing test assertion changed.

## Actual initial workflow projection review

Read only the approved service projection `initial-projection.json` from `tasks/northwind-projection-001` (SHA-256 `292a36791690de0af963429314589975486f280598402d253f7c4d541b9e7572`). A behavioral DOM run and a native Chrome run rendered the real returned envelope unchanged: three monthly credits remain null, the application bill balance remains null, recorded financial stages remain zero, and no action button or invented award appears. The actual projection is an intermediate source-bound state, not a completed financial walkthrough. No sibling runtime files were read.

- UI omits only the exact known classification prefix `Synthetic invoice only; no live Ramp bill bound.` from the pricing summary; the substantive unsupported advance-billing diagnostic remains visible.
- Application invoice reference, issue date, service period and amounts come directly from `ledger.bill`. The renderer contains no $9,600 or $8,600 result constant. The new behavioral test `application invoice comes only from current projection and pricing failures remain visible without classification prefix` checks an optional future invoice projection, without claiming that invoice has been issued or applied in the actual workflow.
- Added `stale reviewer authority keeps recorded checks separate from current verification`: current `checks_status=REVIEW_REQUIRED` and empty `checks` display no passing check; `recorded_checks` remain inside a separate closed historical disclosure.
- No existing test assertions changed in this increment. Focused validation: 45 Node checks, both existing native-browser tests, plus the one-off native-browser check against the actual approved initial projection pass. The populated C projection and complete action flow remain pending.

## Actual posted workflow projection review

Read only the approved `tasks/northwind-projection-004/posted-projection.json` (SHA-256 `a982a84f3e656c4c8052fba8a39bc31919a777cdac6140a988437ce48fa4996a`). A native Chrome render verifies the actual envelope without mutation: claimed/awarded/posted each USD 2,400; applied USD 0; January eligible USD 2,400; February ineligible with null amount; March insufficient evidence with null amount. The March bill balance and unsupported pricing finding remain unknown. No USD 9,600/8,600 balance, USD 1,000 exposure or application action is invented.

Expanded details preserve the denial, acquired resource log, independent verification, award and actual `local-ledger:` credit references, scripted principal, and all 14 CalyxQuay lifecycle history entries including rollback. This validates rendering of a service-generated posted projection; it does not establish an interactive socket/browser lifecycle.

The only code correction normalizes the known generated diagnostic prefix `Simulated scoped,` to `Scoped,` in monthly summaries and evaluator trace, preserving the full missing-measurement requirement and raw payload. Added `missing measurement diagnostic stays visible in summary and detail without generated source prefix`. No existing test assertion changed. All 46 Node checks and the actual posted-projection native-browser check pass.

## Joined dashboard regression correction

The first full joined run at `efa4b2a` reported **2 failed, 2,857 passed, 1 warning in 212.45s**. Both failures were stale presentation assertions outside the UI-focused harness; the original output remains in `root-ui-merge-01.log`.

- `tests/test_advanced_companion.py::test_signed_wizard_refresh_routes_and_mobile`: the selector now uses the actual `Document origin` accessible label instead of `Public source classification`. It still submits the exact `synthetic_public` wire value, signs the request, tests review invalidation, and preserves authorization, route and overflow assertions.
- `tests/helpers/advanced_companion.test.cjs`, `receipt actions reload the same correspondence case`: checks the actual `Evidence & receipts` section heading instead of removed disclaimer copy. It still requires a second server read of the same case and the returned `REVIEWED` state; no receipt, source-authority or financial assertion changed.
- `tests/test_advanced_companion.py::test_companion_dom_workflows` failed only because it wraps that Node suite; its assertions and invocation are unchanged.

Focused retest: **4 passed, 1 warning in 5.26s**, including the actual signed browser wizard, read-only controls and wrapped Node checks. The warning is the existing Starlette/httpx deprecation. Final joined financial-workflow regression follows the April integration.

## Real browser action correction

The manual signed browser walkthrough found `controls.children.forEach is not a function`: the Node harness used an array where the real DOM supplies an HTMLCollection. The handler now converts the collection with `Array.from` before disabling controls. Added `tests/test_workspace_ui_v4.py::test_workflow_action_uses_real_dom_collection_and_refreshes_server_state`, which clicks the actual rendered button in Chrome, checks the encoded empty-body transport call and subsequent read, and requires the changed monetary state and no browser exception. No existing assertion changed. This test covers DOM behavior; the signed end-to-end authority and ledger checks remain in the separate workflow/socket tests.

The joined run `root-northwind-final-01` at `5146e17` was interrupted when this browser defect was found; it is not a passing full-suite result. Its original output remains preserved. The corrected source receives a fresh full run.

The browser reload correctly discarded its in-memory signing key, but the workflow displayed a generic uncertain-outcome message on the resulting401. It now invokes the existing account-login screen and invalidates the old control. Added Node test `expired signing authority returns to account login and invalidates stale action controls`; no signing policy or server authorization changed. The new browser test's first assertion was corrected to account for Playwright serializing JavaScript `undefined` as Python `None`; its actual click and state transition already passed. One subsequent command named a nonexistent test file and collected no tests; the corrected focused run and original outputs are retained.
