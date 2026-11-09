# Test changes — integration 90

No existing test function or assertion changed on `work/integration-90`. Specialist branches merged here keep their own ledgers, linked from [the index](TEST-CHANGES.md).

| File | Change | Reason |
|:---|:---|:---|
| `tests/test_local_review_exception.py` | **Added** `test_browser_sign_in_request_passes_the_review_guard` and the helper `browser_sign_in_request`, plus two imports (`pathlib.Path`, `subprocess`). No existing function or assertion changed. | Runs the real `web/auth.js` sign-in form in Node (`tests/helpers/browser_sign_in_challenge.cjs`) and replays its first request through the guarded fixture app. It fails without the integrated sign-in fix: the guard rejects a challenge that omits `path` and `body_sha256`, and the picker must accept `.jwk`. |
| `tests/test_requirements_traceability.py` | **New file**, 6 tests | Pins the 189 original V3 requirement IDs. Requires a closed-vocabulary disposition, owner and gap class, plus evidence for every completion claim, and checks that every cited file and test function exists. Removing an ID is a visible test change. |
| `tests/test_release_probes_gent8.py` | **New file** (from the verification lane, commit `52bea97`), 1 test | Hard-kills a real server process mid-way through the 11-action Northwind flow and checks state, idempotency and the final Local ledger after restart. |

A "dispositions are correct" test does not exist and should not: the record's integrity is mechanical, while the truth of each disposition is reviewed by people against the cited evidence.

## D03 follow-up in W0 reconciliation

| File | Change | Reason |
|:---|:---|:---|
| `tests/test_reconciliation_identity_d03.py` | **New file**, 16 cases | `reconciliation._required` accepted any printable text, so an em dash, a repeated space, non-NFC text or a 97-character account could reconcile while claim intake and the ledger refused it. `account_id` and `contract_id` now use `source_identity.refusal`, with no rewriting. Accepted values, including spaced names, reconcile unchanged, and comparison stays exact (no case folding). Before the fix, 10 refusal cases failed; after it, all 16 pass. No existing test changed. Focused reconciliation/ledger/portfolio/lineage set: 296 passed, 1 warning. |

## Verification-lane probes (round 3)

| File | Change | Reason |
|:---|:---|:---|
| `tests/test_release_probes_gent8.py` | Taken whole from `work/release-evaluation-gent8` at `1d4a17c` (commits `a6dab8d`, `95a0fae`, `7c970f9`). Adds three tests to the integrated restart probe: the D03-A invariant (a spaced onboarded identity now reaches signed claim intake), 7 socket-level signed-request attacks against a separate server process (each 403 with no state change; one legitimate action 200), and tenant crossing between two installations (each attempt 401/403). The restart test is unchanged. | Independent cross-component checks; no evaluation runner or corpus material is included |
| `scripts/probe_socket_authority_gent8.py` | New | Driver for the socket-authority probe |

Focused: `tests/test_release_probes_gent8.py` 4 passed, 1 warning in 25.65 s.
