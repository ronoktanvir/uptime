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

Updated from `2056856` with two more listener-level probes. A source revised after approval yields UNSUPPORTED_RULE, and submission returns 409 with nothing submitted. An injected vendor reply creates no award, submission or action, an exact signed replay is refused, and a re-signed redelivery is idempotent. File total: 6 passed, 1 warning in 27.54 s.

## Ronok's decision 2a: closure-bound accept-denial mandates (W0)

| File | Change | Reason |
|:---|:---|:---|
| `tests/test_mandate_claim_closure_2a.py` | **New file**, 9 tests (10 cases) | The new `ClosureDecision` mandate action `accept-denial` is bound to `scope_sha256`, the reviewed `basis_sha256` and `claim_state_sha256` (`[scope, state]`), with `max_amount_cents` fixed at 0 and local purpose `claim-closure`. The tests check: exact binding (mismatched basis, scope or state is refused); no money; an issuer without the `claim-closure` purpose cannot close; the closure path requires a closure decision; a closure cannot move paths or combine with claim, credit or native effects; existing mandates keep their signing bytes; the legacy unmandated reviewer exemption is unchanged. 8 of the first 9 failed before the implementation. No existing test changed. Authority-related focused set, including signed mandates, local review exception, correspondence, portfolio, operations and probes: 4,432 passed, 1 warning. |

## W1 interface request: webhook hardening (W0 `ramp_webhooks.py`)

| File | Change | Reason |
|:---|:---|:---|
| `tests/test_ramp_workflow_webhooks.py` | **Added** three new tests at the end of the file: `test_malformed_event_type_is_a_400_not_an_unhandled_exception` (4 cases) and `test_duplicate_webhook_headers_rejected`, both from W1's source commit `c61c384`, plus `test_verification_receipt_must_be_exactly_success_true` (4 cases, new here). No existing test or assertion changed. | A non-string event type such as `[]` or `{}` raised `TypeError` instead of a 400. A verification receipt of `{"success": 1}` activated the deployment because `1 == True`. Before the fix, 6 of the new cases failed: 2 type cases, plus the receipt cases, which also need the new read-only `status()`. After it, the file passed 28, and all `tests/test_ramp*.py` passed 1,007 with 1 warning. |

## W3 interface request: F4 on the signed claim route (W0 `v4_routes.py`)

| File | Change | Reason |
|:---|:---|:---|
| `tests/test_claim_route_filing_override_f4.py` | **New file**, 4 tests | After F4, `vendor_eval` applies a private filing amendment only from its `effective_from` month, but the claim route used the override for every month. The route now computes its monthly cutoff with `vendor_terms.private_filing_days`. An undated stored amendment is `UNSUPPORTED_RULE` (a contract-terms limit, never INSUFFICIENT_EVIDENCE). The economic fingerprint binds `{filing_days, effective_from}` only when an override exists, so adapters without one keep exactly the same fingerprint bytes; that is what the test confirms. 3 of 4 failed before the change; the bytes-unchanged test passed before and after. Route, vendor, Northwind, claim-identity, correspondence, blind-acceptance, portfolio and probe suites: 291 passed, 1 warning. No existing test changed. |
