# Test changes, role 2 (dispute automation), branch `work/submission-disputes-20261109`

Started from `origin/main` at `55ea607`.

## Existing tests

None changed so far. Routine automation is a persisted workspace setting:
- `scripts/setup_northwind.py` creates served workspaces with it **on** by default (`--step-by-step` turns it off).
- The Python `prepare()` default is **off**, so existing tests that build their workspace with `prepare()` walk the eleven operations exactly as before. That includes `tests/test_northwind_workflow.py` and `tests/test_northwind_local_ledger.py`.
- **Correction (coordinator's full suite on `02d86f7`):** an earlier version of this ledger said gent8's restart and socket probes were unaffected. That was wrong. Both create their workspace through the setup command (`scripts/probe_restart_gent8.py:37,75` and `scripts/probe_socket_authority_gent8.py:37`), where automation is now on by default.
  - The full suite failed `tests/test_release_probes_gent8.py::test_hard_kill_mid_flow_preserves_state_idempotency_and_final_ledger` with `assert (0 + 4) == 11`. The product behaved correctly: the probe's four person actions finish the flow.
  - The coordinator asked gent8, the owner, to keep that probe on the eleven-step path with `--step-by-step` and to add a real-process kill for the automated default. I did not edit gent8's probe or test.
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

## Coordinator review fixes

Bug found by the coordinator on `02d86f7`: `--resume --reviewer-credential <existing file>` ended in a raw `FileExistsError` traceback. It is fixed in `scripts/setup_northwind.py`.

New tests (`tests/test_workflow_coordinator_r2.py`, 17 tests now):
- `test_resume_reuses_an_identical_credential_and_refuses_a_different_one_without_overwriting`
- `test_a_refused_credential_path_leaves_no_half_created_workspace[existing, repository, missing-folder]`
- `test_a_stale_approval_binding_is_never_dispatched`: the coordinator-level pin requested by the coordinator.

First run: **1 failed, 16 passed.** My stale-binding test assumed `_approval_binding` returns a dict; it returns a fingerprint string, so the test now substitutes a different value. No application code changed for that.

Focused set (same command as section 7 of the handoff): **161 passed, 1 warning**. The correct-denial node id cited for the runbook: **2 passed**. No existing test changed.

## Receipt pass-through fix (coordinator review of the merged tree)

`uptime/correspondence_model_jobs.py` filtered the shared job's `provider` block with its own key list (`cost_usd`, `elapsed_seconds`, …). That list did not match the shared service's `PUBLIC_RECEIPT_KEYS` (`client_reported_cost_usd`, `tool_events`, `tool_inventory`, `mcp_inventory`, `output_sha256`, `result_sha256`, plus `transport`), so the dispute view silently dropped the cost and the empty tool and MCP inventories. The block is already the shared service's bounded public subset, so it now passes through unchanged.

New tests, `tests/test_correspondence_model_job_view_r2.py` (2): the view and `get` show `client_reported_cost_usd` and the two empty inventories, and a refused job still shows its receipt. **2 passed.** Mutation check: with the old filter, the first test fails.
