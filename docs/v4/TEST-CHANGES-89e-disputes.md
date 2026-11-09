# Test changes, W4 follow-up 89e: explicit closure for every denial (D06 "Humans gate judgment", Q2 option A)

Branch `work/dispute-explicit-closure-89e`, based on `work/dispute-coverage-89d`.

**Decision:** D06 "Humans gate judgment" (Ronok). Q2 option A was chosen on 2026-11-09 at 04:28 PST by the overview session under Ronok's delegated (Recommended) authority, not by Ronok personally. The decision asks for a new oracle version: `fixtures/correspondence/oracle-v2-d06.json` holds the new intermediate `DENIAL_REVIEW` step, and the frozen `oracle.json` is untouched.

## Change

Decision 89 already required an explicit reviewer action to close a claim on a *reviewed* reading. This applies the same rule to replies the finite grammar recognizes.

A denial that the deterministic rules substantiate now reaches `DENIAL_REVIEW`, never `DENIAL_ACCEPTED` directly. This covers the local-path maintenance notice and the historical-receipt late-filing and availability grounds. The case closes only through `accept-denial` with the exact offered basis digest.

The basis records `review_id: null` when the reading came from the grammar. Nothing else changes: money, the award ledger, submissions and the counterparty are untouched.

## Existing tests changed

Each change only inserts one explicit acceptance step, using the offered digest, before the original terminal assertions. Every original assertion is kept unchanged, including the frozen oracle comparison in `fixtures/correspondence/oracle.json`, which still expects the terminal `DENIAL_ACCEPTED`. Neither the oracle file nor any expected value was edited.

| Test | Inserted step | Reason |
|---|---|---|
| `tests/test_correspondence.py::test_known_and_newly_received_maintenance` | Assert the stage and offered actions from `oracle-v2-d06.json` (`DENIAL_REVIEW`, `accept-denial`), then accept with the offered digest. The original `oracle.json` comparison follows unchanged. | D06: closing a claim is a judgment |
| `tests/test_correspondence_filing_refs.py::test_signed_original_retains_exact_fields_and_pins_through_valid_threshold_denial` | `accept_explicitly(filing)` (same check, then `POST /denial-acceptance`) | D06 |
| `tests/test_correspondence_language_56.py::test_claim_bound_lateness_uses_actual_original_receipt[True]` | `accept_explicitly(service)` for the late case only | D06 |
| `tests/test_correspondence_language_56.py::test_correct_availability_denial_comes_from_signed_measurements_not_percent_claim` | `accept_explicitly(service)` | D06 |
| `tests/test_correspondence_service.py::test_correct_denial_of_independently_witnessed_original_requires_actual_signed_ground[False]` and `[True]` | `accept_explicitly(service)` | D06 |

A local `accept_explicitly` helper was appended to the three service-fixture test files.

## Results

- **Prototype before the test edits:** exactly these 6 failed, 1002 passed (253.33s). Every failure was a deliberate automatic-closure assertion.
- **After the edits, touched files:** 262 passed.
- **Broad focused run:** **1024 passed, 1 warning, 217.83s.**
- **Re-run after oracle-v2:** `test_correspondence.py` was then wired to read the intermediate step from `oracle-v2-d06.json`. That file and the disposition tests were re-run on the committed source: **93 passed**.

Receipt: `docs/v4/evidence/dispute-explicit-closure-89e/verification.json`.

## Seventh moved expectation (found by agent0's round-4 full suite)

My focused sets for 89e did not include the scripted blind-acceptance controls. agent0's round-4 full suite on a fresh clone of `3758164` gave **1 failed, 4581 passed**. The log is kept at `docs/v4/evidence/integration-90/full-suite-3758164-FAILED.log`. The bisect points to the 89e/89f merge `4f918a1`.

| Location | Before | After | Reason |
|---|---|---|---|
| `scripts/blind_acceptance.py`, `independent_inbox_controls`, `late_denial` control (formerly line 729) and `tests/test_blind_acceptance.py::test_actual_public_artifact_signed_positive_negative_cure_and_late_routes` | The control expected the late-filing denial to read back as `DENIAL_ACCEPTED` with no actions and no submissions | Read back `DENIAL_REVIEW` with exactly one action, `accept-denial`, and no submissions. Then `POST /denial-acceptance` with the offered `basis_digest`, through the same signed transport. Then read back `DENIAL_ACCEPTED` with no actions and no submissions. `result["before_acceptance"]` records the pending stage, action ids and submission count. | D06 (Q2 option A, delegated): a substantiated denial closes only on explicit acceptance |

`tests/test_blind_acceptance.py` itself is unchanged; its final assertion `late["observed"]["stage"] == "DENIAL_ACCEPTED"` still holds after the explicit step.

The `STAGES` allowlist is deliberately unchanged, because the frozen blind-evaluation scorer also uses it.

Results: the test fails without the change and passes with it. `tests/test_blind_acceptance.py` in full: **37 passed, 1 warning**.
