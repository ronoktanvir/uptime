# Test changes: role 5 (acceptance), November 9, 2026

Branch `work/submission-acceptance-20261109`. Every changed or added test is listed here with its exact name and reason. No authority or monetary assertion was weakened.

| Test | Change | Reason |
|---|---|---|
| `tests/test_release_probes_gent8.py::test_hard_kill_mid_flow_preserves_state_idempotency_and_final_ledger` | **Changed:** the call now passes `step_by_step=True`. `scripts/probe_restart_gent8.py` `run()` gained a `step_by_step` parameter, default `True`, which passes `--step-by-step` to `scripts/setup_northwind.py` at creation. All assertions are unchanged: 4 actions before the kill, 11 in total, state equal after restart, duplicate replay unchanged, and the exact ledger ($2,400 at every stage, April $11,000 → $8,600). | Role 2 made routine automation the default for workspaces created by `setup_northwind.py`: 4 person decisions plus 7 automatic steps. With the default, 4 actions finish the flow, so the kill no longer lands mid-flow and the 11-action assertion failed (`assert (0 + 4) == 11`, reported by the coordinator on the integration branch at `02d86f7`). Creating the workspace with `--step-by-step` restores one person action per operation, so the probe still tests what it was written to test. |
| `tests/test_release_probes_gent8.py::test_hard_kill_after_first_reviewer_decision_with_routine_automation` | **Added.** New `run_automated()` in `scripts/probe_restart_gent8.py`. | Real-process check of the new default. Two OS server processes over loopback, with a SIGKILL after the first person decision; that decision's routine steps ran on the server, then the flow paused at `APPROVAL_REQUIRED`. It asserts:<ul><li>identical persisted state, including `workflow.automation`, after restart;</li><li>an exact re-post of the decision changes nothing;</li><li>the remaining 3 decisions finish the flow;</li><li>`counts == {person_decisions: 4, automatic_steps: 7}`, 11 steps all `COMPLETED` with unique `(operation, intent_id)`;</li><li>exactly one each of submit-claim, submit-response, record-credit and apply-balance;</li><li>the same exact ledger.</li></ul> |

## Not changed

`test_socket_authority_attacks_are_refused_without_state_change` and the other socket probes need no change. The authority probe acts on whichever person action the workspace offers first, so the automated default does not affect it.

## Not attempted

Landing the SIGKILL *inside* an automatic step, so that it surfaces as `UNCERTAIN_DELIVERY` and is reconciled only when a person resumes it, needs a deterministic interruption point. A real-process probe cannot hit one reliably without changing product code. Role 2's in-process tests (`tests/test_workflow_coordinator_r2.py`) cover it; the acceptance phase will report it separately.

## Verification

Run on the coordinator's integration commit `c756853`, which contains role 2's `02d86f7`, plus this change, in a temporary checkout:

```
uv run --locked pytest -q tests/test_release_probes_gent8.py
```

Result: **7 passed, 1 warning in 18.20 s**. The probes require `setup_northwind.py --step-by-step` and the automation projection from role 2, so they pass on the integration branch, not on `main` alone.
