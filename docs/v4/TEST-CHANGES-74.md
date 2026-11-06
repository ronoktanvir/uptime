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
