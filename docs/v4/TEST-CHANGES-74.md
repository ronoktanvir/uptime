# Workstream 74 test-change ledger

Existing tests changed only to reflect the separate real generation and local validation controls:

- `tests/test_advanced_companion.py::test_signed_wizard_refresh_routes_and_mobile` and `::test_viewer_and_disabled_gate_are_read_only`, plus their shared `login` helper: the old local parser button is now `Stage local candidate` / `Confirm stage local candidate`. Signing, exact review, edit invalidation, one POST, SHADOW, navigation, mobile width, role and disabled-state assertions remain unchanged.
- `web/v4_ui.test.cjs`: `vendor intake sends exact separate public document and overlay through injected client`, `invalid JSON never sends a request and leaves form data intact`, and `failed vendor detail keeps that vendor read-only without hiding intake` select the renamed local button. The server destinations, bodies and refusal assertions are unchanged.
- `web/v4_ui.test.cjs::starts read-only even with returned actions; fields contain no sample values`: source/customer fields must still be empty; the new protocol attempt field must equal `initial`. No source, customer mapping or monetary value is defaulted.

New actual-queue tests live in `tests/test_vendor_model_jobs_runtime.py`. The actual Opus worker wrote `tests/helpers/vendor_model_jobs.test.cjs`; those DOM controls explicitly use a fake API and do not claim browser, provider or shared-service proof.

Retained native receipts under `W/tasks`:

- `onboarding74-baseline.log`: 58 passed before implementation.
- `onboarding74-prejoin.log`: four actual-core failures exposed the worker's unsupported service kind, corrected to root's exact `vendor` kind.
- `onboarding74-nativejoin.log`: 205 passed / 1 failed. The new corruption-control fixture had not committed its SQLite update; adding the missing test-only commit made all four actual-core controls pass (`onboarding74-storage-control.log`). No assertion was relaxed.
- `onboarding74-firstfreeze.log`: 209 passed / 1 failed, identifying old DOM caption selectors. Only the caption selectors and explicit nonce-default assertion above changed.
- `onboarding74-ui-caption.log`: 210 passed, one existing Starlette warning, 4.86 seconds.
- `onboarding74-dom-first.log`: 14 DOM tests passed, including the worker's exact-source, permission, edit invalidation, polling, lost-response recovery and inert-result controls.

Final signed HTTP/browser integration and the lead-owned merged full suite are separate gates. No final full-suite or genuine runtime model result is claimed by these focused controls.

Final native controls (new tests, no existing assertion changes):

- `tests/test_vendor_model_jobs_runtime.py::test_fenced_runtime_output_is_retained_and_refused_without_candidate`: the runtime applies strict JSON decoding to the original provider text; fenced output remains in private queue evidence and cannot produce a candidate. Legacy `generate()` fence behavior is unchanged.
- `tests/test_vendor_model_jobs_browser.py::test_signed_job_routes_require_approval_and_cannot_grant_financial_actions`: actual signed routes, exact protected permission, one invocation, idempotent SHADOW installation, foreign-owner refusal and disabled financial actions.
- `::test_provider_work_does_not_hold_the_application_post_lock`: a blocked provider does not block a second signed application POST.
- `::test_browser_checks_permission_generates_and_stages_separate_overlay[manual]` and `[utf8_file]`: real Chrome against a loopback server and the actual durable service with an explicit provider double. UTF-8 file import preserves original CRLF in the approved request despite textarea display normalization. Editing creates a different unapproved source; reimporting the original restores the original request. Both paths reach SHADOW with no review/activation authority, no overlay disclosure, no page errors and no mobile horizontal overflow.

New test-fixture corrections retain their failed receipts: reserved `scripted-` account names were replaced with generated-key draft-test names; workspace binding now precedes service initialization; financial refusal is checked at the authentication challenge; the browser assertion reads the actual structured `input.text` field. No source, output or authority assertions were weakened.

- `onboarding74-http-browser.log`, `onboarding74-http-browser2.log`, `onboarding74-http-browser3.log` and `onboarding74-frozen.log` preserve those failures.
- `onboarding74-ready.log`: 252 passed, one existing warning, 14.07 seconds.
- `onboarding74-file-edit.log`: four signed/browser tests passed, one existing warning, 10.14 seconds, after the explicit edit/reimport control and bounded permission copy.
- `onboarding74-dom-file.log`: eight DOM controls passed with the optional file input.

The final integrated full suite remains lead-owned; these are focused results.

`test_proposal_context_pins_only_consumed_family` (both fixed profiles) verifies that only the consumed evaluator family affects the proposal context. Every selected family's existing common and profile source dependencies remain pinned. Resource-only changes cannot invalidate a strict monthly request through an unused family digest; common-source changes still alter the monthly family digest. Decision77 source was merged before the final request freeze.

`onboarding74-final-pins.log`: 106 passed, one existing warning, 10.44 seconds on the decision77 merge plus the scoped dependency change (runtime, signed/browser, source-period and scoped-filing controls). The lead owns the integrated full-suite gate after the final merge.

The one actual public-provider control ran after production freeze `52ca9c3`: signed HTTP, normal protected operator CLI approval, genuine `claude-opus-5-5`, bare JSON, one durable job, normal SHADOW candidate, no human/financial authority. It succeeded with session `88d16a32-9350-4d79-9897-1c047ad560ab`. See `decisions/reviews/74-actual-public-queue.json`; the source is the unchanged studied authored70 control, not a new blind trial. No retry was made. Subsequent commits add only this evidence/documentation.
