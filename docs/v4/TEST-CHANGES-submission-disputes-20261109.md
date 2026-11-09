# Test changes, role 2 (dispute automation), branch `work/submission-disputes-20261109`

Started from `origin/main` at `55ea607`.

## Existing tests

None changed so far. Routine automation is a persisted workspace setting:
- `scripts/setup_northwind.py` creates served workspaces with it **on** by default (`--step-by-step` turns it off).
- The Python `prepare()` default is **off**, so every existing step-by-step test and probe walks the eleven operations exactly as before. That includes `tests/test_northwind_workflow.py`, `tests/test_northwind_local_ledger.py`, gent8's restart and socket probes and gent7's browser tests.
- The setting joins the workspace package digest only when it is on. Existing workspaces keep their digest.

## New tests

`tests/test_workflow_coordinator_r2.py`, 10 tests. First run: **10 passed**.
- Person decisions offered are exactly: approve claim, approve response, post credit, apply credit.
- 7 automatic steps, each with recorded authority: approval actor and digest for dispatches, event id and signed source subject for intake.
- Filing lineage and cooldown are preserved.
- Duplicate posts and reloads add nothing.
- An interrupted automatic step stays `UNCERTAIN_DELIVERY` across a process restart until a person resumes it. Resuming reconciles by read-back with no second filing.
- An unfamiliar vendor reply pauses at `UNEXPECTED_GROUND`.
- Judgment, contradiction, missing-approval and observe-mode pauses.
- The step history is append-only.

## Runs

- Existing workflow, ledger and finance tests on the changed code (step-by-step default): **121 passed**.
- Combined with the new tests and the correspondence model-job tests (job view now carries timestamps and the shared `provider` receipt subset): **160 passed, 1 warning**.

## Later increments (`1646930`, `0225970`, `2742be0`)

No existing test changed.

New tests, added to `tests/test_workflow_coordinator_r2.py` (12 tests now):
- `test_dispatch_happens_on_the_workspace_timeline_at_the_cooldown_and_inside_the_cutoff`
- `test_setup_prints_a_plain_sign_in_block_and_writes_a_visible_protected_copy`

First run of the 12: **1 failed, 11 passed.** The sign-in test expected the test-module origin (`:8765`), but the CLI default is `:8776`. The test now compares against the origin the CLI prints. No application code changed for this fix. Second run, with the workflow, finance and model-job tests: **156 passed, 1 warning**.
