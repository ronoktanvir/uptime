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

## Plain refusals for common setup mistakes (coordinator request)

No existing test changed. `prepare()` still raises a `ValueError` subclass (`WorkspaceRefused`) for a non-fresh folder, so callers that expect `ValueError` are unaffected.

New `tests/test_setup_refusals.py`, 8 tests: **8 passed** on the first run. Each refusal is checked for exit 1, the exact single line, no "Traceback", empty stdout, and the folder unchanged (or never created).

| Mistake | Before | After |
|---|---|---|
| Re-run create in the same folder (README command twice) | exit 1, traceback ending `ValueError: Select a fresh directory; use --resume for an existing immutable workspace.` | exit 1: `setup_northwind: That folder already holds a workspace. Add --resume to reopen it, or choose a new folder name for a fresh run.` |
| Create in an existing folder without a workspace | same traceback | exit 1: `setup_northwind: That folder already exists. Choose a new folder name for a fresh run.` |
| `--resume` on a missing folder | exit 1, traceback ending `FileNotFoundError` | exit 1: `setup_northwind: That folder does not exist. Run without --resume to create a workspace there.` |
| `--resume` on a folder without a workspace | exit 1, traceback ending `FileNotFoundError …/workspace.json` | exit 1: `setup_northwind: That folder holds no workspace. Choose a new folder name and run without --resume to create one.` |
| `--serve` on a busy port (create) | exit 3, uvicorn `ERROR: [Errno 48] … address already in use`, **and the workspace was created anyway** | exit 1, nothing created: `setup_northwind: Port N is already in use, so <origin> cannot be served. Stop whatever is using it, or choose another port with --origin.` |
| `--resume --serve` on a busy port | the same uvicorn error | exit 1, workspace unchanged: `…Stop whatever is using it; a resumed workspace keeps the port it was created with.` |
| `--resume` on a workspace from a different package | traceback ending `ValueError: The verified package differs…` | exit 1: `setup_northwind: The verified package differs from this workspace; preserve it and create a new directory.` |

Focused, with `tests/test_workflow_coordinator_r2.py`, `tests/test_northwind_workflow.py` and `tests/test_northwind_local_ledger.py`: **81 passed, 1 warning**. That run was before a wording change ("; or" became ", or"); `tests/test_setup_refusals.py` passed again after it.

## Ports in the real-process setup tests (coordinator follow-up)

These tests are on main, so each change is recorded here. **Reason:** they scanned the fixed range 8821–8829 and called `pytest.skip` when every port was taken. A skip can hide a regression, two runs on this machine could race for one port, and 8823 is in Ronok's filming checklist. They now take ports the operating system assigns (bind `127.0.0.1` port 0). There is no skip path, and no assertion changed.

- `tests/test_setup_refusals.py`
  - **Helpers:** `busy_port()` replaces `hold()` and `occupied_port()`, and `assigned_origin()` is new.
  - The module fixture `workspace` records an assigned origin instead of fixed `:8822`, and returns `(folder, origin)`.
  - `test_serving_on_a_busy_port_is_refused_before_a_workspace_is_created`: holds an assigned port.
  - `test_resuming_on_a_busy_port_is_refused_and_leaves_the_workspace_unchanged`: holds the same assigned socket for the whole test, with no close-and-retake (creating without `--serve` never binds).
  - `test_rerunning_create_in_the_same_folder_is_a_plain_refusal`, `test_a_workspace_from_a_different_package_is_refused_plainly`, `test_a_correct_resume_still_works`: they unpack the fixture's new tuple. The last one compares the final line with the recorded origin instead of the literal `:8822`.
- `tests/test_setup_side_panel.py`
  - `free_port()` returns an OS-assigned free port; used by `test_served_create_and_resume_frame_only_when_given_and_print_the_line_first`.

Result: both files, **19 passed, 1 warning**, no skips.

## Reworded log request variant, Phase A (Ronok's go-ahead, relayed by the coordinator)

**Deliberate change:** `scripts/setup_northwind.py` `VARIANTS_SHA256` moves from `9e0e4750…` to `1250baf3cb0f2f10b3ead8ccafc0d060349081749675e7efd64c60626812ee9f`, and `COUNTERPARTY_REPLIES` gains `reworded-log-request`.
- **Reason:** `fixtures/northwind/counterparty-variants.json` gains the authored `reworded-log-request` entry, and its authorship statement now covers both variants. The `unclear` entry is byte-identical.
- **Still opens:** a copy of the preserved `unclear` workspace opens on `21b0551` and shows job `29f371d0` `SUCCEEDED`. The preserved folder's database hash is unchanged (`1a035ab2…`).

`scripts/run_denial_model_job.py` is restructured around `run()`, with `--variant`. The `unclear` path keeps its earlier shape: semantic review in the same workspace, no continuation.

**No existing test changed.** New tests (no real process is launched, so no ports are used):

- `tests/test_reworded_log_request_r2.py` (5 tests):
  - the variant's text hash, and that the fixed rules read it as `unknown`;
  - the pause at `UNEXPECTED_GROUND` with no offer;
  - the reviewer-only bridge (own reading, review, preview `NEEDS_EVIDENCE`, prepare, then "Continue routine steps" and the remaining person decisions) to the same applied credit: 2400.00 claimed, awarded, posted and applied; bill 11000.00, then 8600.00 outstanding; counts 4 and 7; the same eleven steps and authority kinds as the default;
  - a rejected reading and a reading with an `unsupported` segment: prepare refused (409), case in review, ledger unchanged;
  - the default and `unclear` replies unchanged.
- `tests/test_run_denial_model_job_r2.py` (3 tests, stand-in provider as in `test_public_proposal_config.py`):
  - the reworded run stops after the candidate (no review rows in the preserved database);
  - transport fields come from the job row, with an absent `revision` reported as `NOT_CAPTURED`;
  - the continuation runs on the scratch copy only and completes the walkthrough;
  - a dirty checkout is refused before anything is written;
  - the `unclear` run keeps its earlier shape.

First runs: **5 passed**, **7 passed**. Focused set (new tests, coordinator, setup refusals, side panel, Northwind workflow, model jobs, job view and interpretation tests): **167 passed, 1 warning**.

## Model reading gate in the denial driver (coordinator review of `5d69f9d`)

**Problem:** the continuation's scripted review always submitted the reviewer's own reading and answered any difference with "correct". So a model reading that was not a log request would still have completed the walkthrough.

**Change, fixed in code before any call:**
- `LOG_REQUEST_CRITERION` and `CRITERION_TEXT`: the model's candidate **alone** is mapped with the product's `proposal_for_review` and the server context, with no reviewer input. The model read the reply as the log request **iff** `reason == "artifact"`, `reference == "NW-JAN-LOG-001"`, and `artifact_type` is `resource_log` or absent.
- **If it fails:** no review, preview, preparation or copy. The outcome is `MODEL_DID_NOT_READ_A_LOG_REQUEST`, the case stays in review, and the receipt keeps the full candidate interpretation as stored.
- **If it holds:** the review on the copy records, per proposition, accept or correct with the exact differing fields. The overall `agreement` is `IDENTICAL` or `SAME_REQUEST_DIFFERENT_FIELDS` with the list.

**Tests:** these are this push's own new tests (in `tests/test_run_denial_model_job_r2.py`, not yet on main), so this is not a change to existing tests.
- The earlier `test_reworded_run_stops_after_the_candidate_and_continues_only_on_a_copy` is replaced by:
  - `test_identical_reading_continues_on_the_copy_and_records_identical`
  - `test_the_same_request_with_a_different_field_continues_and_names_the_field`. The reply is a single source block, so any model proposition spans the whole reply. The field that can differ while the mapping holds is `artifact_type` (absent).
  - `test_a_reading_that_is_not_the_log_request_stands_and_nothing_continues[unsupported, two-propositions, different-reference]`. Each asserts no copy, no review rows, the case in review, and no money moved.

Result: **7 passed** on the first run. **Mutation check:** making the criterion always true makes all three "not a log request" cases fail.
