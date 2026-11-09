# Test changes, W4 follow-up 89f: closure-bound accept-denial mandate (Ronok's decision 2a)

Branch `work/dispute-closure-mandate-89f`, based on `work/integration-90` at `16c4635`. That tip includes agent0's `b36827f` (`mandates.ClosureDecision`, `closure_preview`, `check_closure_decision`). It merges `work/dispute-explicit-closure-89e` at `53e29ee`.

## Change

- **Mandate check.** The fail-closed `correspondence.closure_permitted` gate is gone. `accept-denial` now calls `mandates.check_closure_decision` with `closure_preview(claim_id, basis_digest, scope, state)` on the pre-change state, inside the write transaction:
  - The legacy unmandated `bears` reviewer exemption is unchanged.
  - A mandated principal needs a `ClosureDecision` that matches the basis and claim state exactly, with `max_amount_cents=0`.
- **Non-`bears` view.** The case view attaches `mandate_closure` (the exact decision to issue) to the `accept-denial` offer, and no longer tries to build an outbound packet for it. Before, a closure offer could vanish from a mandated workspace's view while remaining accepted by the action (Opus finding #2).

## Existing tests changed

Only this workstream's own test changed: `tests/test_correspondence_disposition_89.py::test_mandated_principal_cannot_accept_until_a_closure_decision_type_exists` was replaced by `test_mandated_principal_needs_an_exact_closure_decision`.

- **Reason:** decision 2a created the mandate type that the old test said did not exist. A mandated principal now sees the offer, and is refused unless it carries a matching `ClosureDecision`.
- **Still asserted:** refusal without a decision, refusal with a stale claim state, and refusal with a different basis.
- **Now also asserted:** success with the exact decision, with money unchanged.
- **Isolation:** the installed-mandate signature recheck is monkeypatched in this one test. agent0's `tests/test_mandate_claim_closure_2a.py` covers that signature path, and it passes unchanged here.

## New test

`test_other_tenant_view_offers_closure_preview_without_building_a_packet`:
- A non-`bears` tenant's case view offers `accept-denial` with a `mandate_closure` bound to the offered basis and the view's `state_sha256`.
- Acceptance without a decision is refused.
- Claim filing is isolated with a monkeypatch, because filing in a non-`bears` tenant needs its own mandate.
- **Mutation check:** with the old view behaviour (build a packet for every offer), this test fails.

## Results

- Touched files plus `test_mandate_claim_closure_2a.py` and `test_signed_mandates.py`: **87 passed.**
- Broad focused run, including the mandate and authority tests: **1187 passed, 1 warning, 282.65s.** Receipt: `docs/v4/evidence/dispute-closure-mandate-89f/verification.json`.
