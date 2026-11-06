# Phase83 test ledger

No preexisting test, fixture or assertion changed. New controls cover UI recovery only; no API, authentication lifetime, authority, source compiler or monetary behavior changed.

`tests/helpers/vendor_auth83.test.cjs` adds thirteen authored DOM controls: initial vendor/correspondence/case reads, vendor detail, generic action, generation access, generation submission, status polling and candidate-confirmation401 responses request sign-in. Parallel401 responses redirect once. Detached responses and controls cannot replace the new screen or send another request. A terminal status replaces the queued banner; subsequent identical status reads and older overlapping reads preserve an explicit overlay review. Editing the source revokes a detached candidate control.

`tests/test_vendor_auth83.py::test_v4_auth_recovery_dom_controls` includes those controls in normal pytest collection. `::test_expired_browser_session_recovers_same_job_without_resubmitting` runs real Chrome against the signed loopback application and durable queue with an explicit public provider double. It expires a disposable server session without changing production policy, captures the resulting401 on the auth challenge, checks sign-in recovery and disabled old controls, then signs in and recovers the same succeeded job through an explicit access check. Only a newly confirmed candidate request creates SHADOW. Generation POSTs and provider calls remain exactly one; no reviewer/active version is created. The test records only method/path/status, job ID and safe result fields, never credentials.

Preserved receipts under `W/tasks`:

- `onboarding83-first.log`:31 existing DOM controls passed,2 failed. The first code draft assigned `undefined` to a mock button's disabled property and interrupted an existing recovery phrase with the state name. The code now supplies a boolean and appends the current state to the preserved phrase. Existing assertions are unchanged.
- `onboarding83-existing.log`:33 existing DOM controls passed after those corrections.
- `onboarding83-controls-first.log`:12 new auth/status DOM controls passed before the additional overlapping-read control.
- `onboarding83-browser-first.log`:2 new Python controls passed, one existing warning,6.77 seconds, including the actual expired-session browser path.
- `onboarding83-focused.log`:27 focused tests passed, one existing warning,18.93 seconds. A subsequent small account-view change explicitly clears its busy accessibility state; final frozen-source verification is recorded separately.

The original actual browser incident did not capture an HTTP status. Its generic uncertain/read-unavailable messages remain unchanged evidence; expiration is consistent with elapsed time, not established as that incident's cause. The new deterministic regression establishes the401 handling defect separately. No new genuine model invocation was made for this repair. The lead owns the integrated full-suite gate.

Final frozen production source `5b750db`: `onboarding83-frozen.log` reports **27 passed**, one existing Starlette warning,22.13 seconds. This includes the13 new auth/status DOM controls, existing companion/runtime DOM controls, real expired-session browser recovery, previous signed-browser/runtime/profile checks and advanced companion checks. The sign-in screenshot was visually inspected. Safe method/path/status evidence and source hashes are in `decisions/reviews/83-expired-session-recovery.json`; subsequent changes are documentation only.
