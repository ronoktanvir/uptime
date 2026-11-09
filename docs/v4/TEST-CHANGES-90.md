# Test changes — integration 90

No existing test function or assertion changed on `work/integration-90`. Specialist branches merged here keep their own ledgers, linked from [the index](TEST-CHANGES.md).

| File | Change | Reason |
|:---|:---|:---|
| `tests/test_local_review_exception.py` | **Added** `test_browser_sign_in_request_passes_the_review_guard` and the helper `browser_sign_in_request`, plus two imports (`pathlib.Path`, `subprocess`). No existing function or assertion changed. | Runs the real `web/auth.js` sign-in form in Node (`tests/helpers/browser_sign_in_challenge.cjs`) and replays its first request through the guarded fixture app. It fails without the integrated sign-in fix: the guard rejects a challenge that omits `path` and `body_sha256`, and the picker must accept `.jwk`. |
| `tests/test_requirements_traceability.py` | **New file**, 6 tests | Pins the 189 original V3 requirement IDs. Requires a closed-vocabulary disposition, owner and gap class, plus evidence for every completion claim, and checks that every cited file and test function exists. Removing an ID is a visible test change. |
| `tests/test_release_probes_gent8.py` | **New file** (from the verification lane, commit `52bea97`), 1 test | Hard-kills a real server process mid-way through the 11-action Northwind flow and checks state, idempotency and the final Local ledger after restart. |

A "dispositions are correct" test does not exist and should not: the record's integrity is mechanical, while the truth of each disposition is reviewed by people against the cited evidence.
