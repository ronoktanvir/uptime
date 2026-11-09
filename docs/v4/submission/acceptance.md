# Role 5: independent acceptance and evidence

**Phase A, pre-registered November 9, 2026, before any implementer branch was opened.** The owner is `gent8`, which also custodies evaluations 84 and 86 and the D05 runs. Phase B starts when the coordinator names the frozen commit. This file then receives the acceptance report.

The role checks what the revised product actually shows, separately from what implementers say about it. It does not fix bugs: each finding goes to the coordinator with a reproduction. It does not certify production readiness from regression counts.

## Sealed expectations (commitment)

`~/.local/share/uptime-engineering/review/submission-acceptance/sealed-expectations.json` is owner-only and outside Git, SHA-256 **`6b1c4057466f69edb10aa864930ae47055e65aeb7a543cada43ed56bd2c19481`**. It contains:
- the exact authored control inputs: reply texts and foreign identifiers;
- the expected stage, offered actions and money for each control;
- the expected values for each presentation claim.

Its content is committed after every Phase B result is terminal, and verified against this digest. Implementers do not receive it.

## Task 1: freeze

Recorded before any check runs:
- the frozen commit and its tree;
- SHA-256 of every tracked file under `uptime/`, `web/`, `scripts/` and `fixtures/`, plus `uv.lock` and `README.md`;
- the Claude CLI version and binary SHA-256;
- the Python and Node versions.

Checks run only on that commit. If source changes mid-run, everything restarts on a new freeze and the earlier attempt is kept and named.

## Tasks 2–3: historical and existing evaluations

Nothing is rescored, and no competing run is created. The report lists each evaluation with custodian, source pin and status.

| Evaluation | Custodian | Pin | Status (as published) |
|---|---|---|---|
| Independent replies (historical) | earlier lane | earlier source | 0/50 supported recognized; 50/50 review refused |
| eval76 public baseline | earlier lane | `fd6537c` | 0/4 supported onboarding; 3/6 complete replies; 6/6 review abstained |
| corpus84 onboarding first attempts | gent8 | `89fe25c` | 0/4 supported accepted; 0 unsafe |
| evaluation86 dispute cohort | gent8 (grader), agent3 (executor) | runner frozen `e1b6657` | Not run: setup-blocked. Under Ronok's 3a it waits for setup |
| D05 run 1 (sealed vendor, revealed: Backblaze) | gent8 | `cccb5a0` (= `3f60647` code) | `NO_SUPPORTED_FAMILY`; safe; correctness not established |
| D05 run 2 | gent8 | pre-registered `46feb99`, sealed `51f58ac` | Not run; needs Ronok's go-ahead |
| Finish cohort: 6 contracts, 8 replies | **Codex evaluation lane** (`work/evaluation-finish-20261109`) | `805dd1c` | As published in `docs/v4/FINISH-20261109.md` on main: 0/4 intended positives staged after 12 Opus returns; negatives refused at identifier grounding; 6 dispute setups quarantined, 2 readings failed grounding, no held-out dispute inference. Attributed to that lane; its sealed answers and task directory are not opened. |

Any remediation rerun receives a new name, for example `R1-<date>-<scope>`, and never replaces a first attempt.

## Task 4: fresh clone with published instructions only

A single fresh clone of the frozen commit goes into a scratch directory, deleted afterwards. The test follows `README.md` and the linked setup instructions **verbatim**. Every command, prompt, wait and click is recorded with a timestamp.

- **PASS:** a person reaches the presented walkthrough, signs in and completes it with only the documented steps.
- **FAIL:**
  - any undocumented step, such as a hidden key path, environment variable, manual database edit or an unmentioned port;
  - any documented step that fails;
  - an unreachable screen in the film plan.
- **Reported separately:** setup minutes and number of manual actions.

## Task 5: actual model dispatch

For each path the film claims uses a model — contract interpretation, and denial interpretation if claimed — the evidence must be a job record with:
- a new job ID created after the trigger;
- the provider and the actually reported model (`claude-opus-5-5`) and session ID;
- empty tool and MCP inventories;
- request and response SHA-256;
- start and finish times;
- the provider process receipt, with an executable whose SHA-256 matches the installed CLI.

**FAIL**, recorded and not a run: a spinner, a mocked provider, a cached or pre-staged proposal, a reused job, or a model name with no session.

Where existing receipts cannot establish dispatch, one fresh genuine call per path goes through the application's own route: public or authored material only (D10), recorded, no retry.

## Task 6: money, citations and authority along the whole path

- **Money:** every displayed amount equals the backend decimal value. Stages (estimated, claimed, awarded, posted, applied) are states of one credit and are never summed. Unknown stays unknown. The price exception is separate from the SLA credit.
- **Citations:** each cited clause re-slices from stored source text at its offsets, with matching hashes.
- **Authority:**
  - every state-changing action needs a signed reviewer or a named policy;
  - model output never authorizes itself;
  - a scripted reviewer is never shown as a person;
  - no screen calls a local amount "recovered in Ramp".

**FAIL** on any mismatch, uncited amount, unsigned mutation or misleading destination.

## Task 7: controls

Each control's exact input and expected outcome are sealed. Each is exercised through the product's published routes where possible. A control the product cannot express is reported **"not exercisable"**, never simulated as passed.

| ID | Control | Pass criterion (public summary) |
|---|---|---|
| T7-CD | Correct denial | Stops for explicit review with only the accept-denial action; no contesting action; no money change |
| T7-AD | Ambiguous denial (conditional, waiver language) | No automatic acceptance, rebuttal or settlement; required human review; the waiver is never accepted by the system |
| T7-ME | Missing evidence | Waits for existing signed evidence; nothing invented; deadline from source |
| T7-DS | Duplicate submission or redelivery | Exactly one effect; exact signed replay refused |
| T7-RS | Restart mid-workflow (process kill) | Identical state after restart; no duplicate step, receipt or ledger entry |
| T7-TO | Model timeout (controlled provider, labelled) | Terminal timeout state; no retry; no state or financial advance; visible in the interface |
| T7-FO | Foreign object (unrelated Ramp bill, other tenant) | Refused or not linkable; the Northwind agreement is never attached to the DocuSign bill |

## Task 8: presentation claims, each to be matched to an artifact

| Claim | Film segment | Supported only if |
|---|---|---|
| C1 | 0–15 s: the manual contract, invoice and outage workflow | It is a narrated "before" state. No product screen implies automation the product lacks. |
| C2 | 15–40 s: actual model-assisted contract interpretation | Task 5 passes for this path in the filmed build, and the screen shows a proposal pending validation and review |
| C3 | 40–65 s: deterministic financial finding and approval | The amount comes from the deterministic engine with re-sliceable citations; the approval is a signed reviewer action, disclosed as the presenter's or a scripted account's |
| C4 | 65–95 s: denial interpretation, evidence cure, required review | Parser versus model is labelled; the cure uses existing signed evidence; the review stop is visible and not auto-passed |
| C5 | 95–115 s: credit lifecycle and invoice balance | Sealed values match exactly: the April invoice, applied credit and remainder, and the separate March price exception still open. Destination "Local ledger"; never "recovered in Ramp" |
| C6 | 115–120 s: exact Ramp connection and present limitation | Exact business, bill and amount, and the person-posted comment read back. The limitation is stated: no Uptime-origin Ramp write; Northwind not linked |

Each claim is graded **supported**, **supported with stated limits**, or **not supported**.

## Task 9: transport, per check

Each check records one of:
- `REAL_HTTP` (loopback listener, separate process);
- `TESTCLIENT` (in-process);
- `BROWSER` (real browser against a listener);
- `CONTROLLED_PROVIDER` (fake or recorded executable);
- `GENUINE_PROVIDER` (actual `claude-opus-5-5` with receipt);
- `RECORDED_ARTIFACT` (prior receipt only).

## Task 10: separate scores, never pooled

These six buckets are reported side by side and never combined into one number:
1. parser success
2. model interpretation
3. setup readiness
4. reviewed outcome
5. automatic execution
6. native effects

## Acceptance report (Phase B)

The report covers:
- the tested commit and commands;
- the actual pass/fail output;
- new-vendor and new-response outcomes, with custodians;
- remaining setup and authorization blockers;
- reproduced bugs ranked by consequence;
- the claim-by-claim statement from task 8;
- the reveal of the sealed file with its digest check.

## Decisions needed before or during Phase B

1. **Disk.** Free space is about 1.2 GiB, below the brief's 3.4 GiB. A fresh clone with `uv sync` (about 200 MB) and any browser install needs room first.
2. **C6 live check.** Default: verify only from recorded artifacts. A fresh read-only Ramp API read with the existing `bills:read` installation needs Ronok's explicit OK.
3. **Model calls for task 5.** At most one genuine `claude-opus-5-5` call per claimed path (2–3 in total), public or authored text only, no retry. Ronok confirms.
4. **D05 run 2** (pre-registered and sealed) would supply the new-vendor outcome on the frozen commit. It runs only with Ronok's go-ahead.
