# Role 2: dispute automation within policy (agent3)

Branch `work/submission-disputes-20261109`, started from `origin/main` at `55ea607` on November 9, 2026. The task text is Ronok's coordination brief (12:50 PST), relayed by the coordinator. This file holds the action inventory, the coordinator design, the interface fields role 4 renders, and the setup-side sign-in proposal. It is updated as implementation lands. **Status: implemented and pushed** (commits in section 7). It is waiting for coordinator integration.

## 1. The eleven walkthrough operations versus D06

Source: `uptime/northwind_workflow.py` `WorkspaceWorkflow._next`. Today every operation, including intake of authored counterparty events, is one click on the single "next action" button: eleven clicks.

| # | Operation | Class | Who authorizes it today | D06 target ([matrix](../integration90/D06-ACTION-MATRIX.md)) | After this change |
|---|---|---|---|---|---|
| 1 | `approve-claim` | Approval | Reviewer click; the approval binds the exact packet digest | **Person** | Person (click) |
| 2 | `submit-claim` | Delivery of an approved operation | Reviewer click | Person approves; "system executes once after approval" | **Automatic**, under step 1's recorded approval (same actor and digest), local outbox only, once per economic key |
| 3 | `receive-denial` | Intake (authored counterparty event) | Reviewer click | Automatic intake (not an action) | **Automatic** intake through the signed source route; interpretation follows the reply rows |
| 4 | `receive-artifact` | Intake (authored customer archive event) | Reviewer click | Automatic intake | **Automatic** |
| 5 | `receive-verification` | Intake (authored status verification) | Reviewer click | Automatic intake | **Automatic** |
| 6 | `approve-response` | Approval of a factual follow-up | Reviewer click | **Person** today. Policy-eligible only for this narrow case once a standing policy exists; **none is configured** | Person (click) |
| 7 | `submit-response` | Delivery of an approved operation, after the 24-hour cooldown | Reviewer click | Executes after approval and cooldown | **Automatic**, under step 6's approval, never before `cooldown` |
| 8 | `receive-award` | Intake (authored counterparty decision) | Reviewer click | Automatic intake | **Automatic** |
| 9 | `record-credit` | Financial mutation (Local ledger) | Reviewer click | **Person** | Person (click) |
| 10 | `receive-invoice` | Intake (authored next invoice) | Reviewer click | Automatic intake | **Automatic** |
| 11 | `apply-balance` | Financial mutation (bill application) | Reviewer click | **Person** | Person (click) |

**Result on the main (cure) branch:** 11 clicks become 4 person decisions: approve claim, approve response, post credit, apply credit.
- Seven operations become automatic. They are four intakes of authored local events, one more intake (the next invoice) and two dispatches of operations a person already approved.
- No approval gate is removed or combined, and no standing policy is created.
- Making `approve-response` automatic would need a standing policy record (D06 gap 1). That is a W0 schema change and a team decision, proposed only in section 6.

**Other branches.** Person decisions there are the reviewer's own pre-reading and the semantic review of a model reading (decision 60/75) on the ambiguous and unfamiliar-wording branches, and `accept-denial` on the correct-denial branch (D06, decision 89e, mandate 2a when mandated). The coordinator never performs either.

**Clicks for routine work.** "Resume interrupted action" remains a person click only after a crash leaves an operation's delivery uncertain (section 2).

## 2. Coordinator design

New module `uptime/workflow_coordinator.py`, used by `WorkspaceWorkflow`. It has no new authority, no scheduler, no timer and no browser involvement.

- **Trigger.** It runs on the server inside the same signed reviewer request that completed a person decision. After that decision commits, it advances routine steps until it reaches a pause. It also runs on `POST /api/workspace/workflow/continue` (signed reviewer request), which is needed only after an interruption or restart. A `GET` never advances anything.
- **Execution.** Each automatic step goes through the existing exact-intent machinery (`workspace_workflow_intent`): domain pin, expected effect, `_done` read-back, `EXECUTING` → `COMPLETED`. This keeps idempotency, restart safety and duplicate prevention exactly as they are.
- **Authority record per automatic step.**
  - Dispatch: `kind=APPROVED_OPERATION`, with the approving actor, approval digest and approval time read from the claim's `approval` record. The coordinator dispatches only if that approval's digest equals the current packet digest.
  - Intake: `kind=EVENT_INTAKE`, with the event id, source subject and the authored-package digest.
  - Nothing runs under model confidence.
- **Persisted state.** A new table `workspace_workflow_step` (append-only) records operation, class, authority, state, timestamps and pause reason. The view projects it (section 3a). Progress is read only from this table and domain state.
- **Pause rules.** The coordinator stops and records a typed pause instead of acting when:

| Reason code | Condition |
|---|---|
| `APPROVAL_REQUIRED` | Next operation is `approve-claim` or `approve-response` |
| `FINANCIAL_APPROVAL_REQUIRED` | Next operation is `record-credit` or `apply-balance` |
| `JUDGMENT_REQUIRED` | Claim stage is `DENIAL_REVIEW` (accept-denial offered), or a vendor reply needs the reviewer's reading and semantic review |
| `UNEXPECTED_GROUND` | Claim stage is `HUMAN_REVIEW` after a reply whose ground the system does not recognize or that is multi-ground, conditional or legal |
| `CONTRADICTORY_EVIDENCE` | Unresolved blocking `contradicting_deliveries`, or later evidence moved the claim to `HUMAN_REVIEW` |
| `MISSING_AUTHORITY` | A dispatch's recorded approval is absent or no longer matches the packet; the workspace is in `OBSERVE` mode; or the principal is not the workspace reviewer |
| `UNCERTAIN_DELIVERY` | An `EXECUTING` intent exists (a crash between effect and confirmation). The coordinator never resumes it by itself; a person presses "Resume interrupted action", which reconciles by exact read-back before anything else runs |
| `WAITING` | The next authored event is not yet available, or nothing remains |

- **Preserved.** Original filing lineage and filing cutoff, the 24-hour response cooldown (dispatch time is never before `cooldown`), one filing per economic key, exact-intent duplicate prevention, the domain-pin staleness check, and tenant and identity checks.
- **Disclosure.** The automatically received counterparty events are authored replies from a local counterparty, delivered through the ordinary signed source route. Receiving them is not evidence of a real vendor integration (D08). The runbook and section 5 say so.

## 3. Interface fields for role 4 (gent7)

All values come from `GET /api/workspace/workflow` (`workflow.*`) or the existing case and interpretation routes. Money values are decimal strings or `null`.

### 3a. Automation state (new; field names fixed now)

`workflow.automation`:
- `state`: one of `RUNNING`, `PAUSED`, `COMPLETE`.
- `pause`: `null` or `{reason, operation, detail, since}`. `reason` is one of the codes in section 2.
- `steps`: list, oldest first, of:
  - `{operation, label, class, authority, state, started_at, finished_at, intent_id, pause_reason}`
  - `class`: `INTAKE`, `COMPUTATION`, `DELIVERY`, `JUDGMENT`, `APPROVAL` or `FINANCIAL_MUTATION`.
  - `authority`: `{kind, actor, approval_digest, approved_at, event_id, source_subject}`. `kind` is `PERSON`, `APPROVED_OPERATION` or `EVENT_INTAKE`.
  - `state`: `COMPLETED`, `PAUSED` or `UNCERTAIN`.
- `counts`: `{person_decisions, automatic_steps}`.

- **Clocks.** Each step has two clocks:
  - `at`: the **workspace's own timeline**, the authored event clock that `workflow.as_of` also shows.
  - `recorded_at`: wall-clock UTC when the server recorded the step.
- **`timing` per step:** `{clock: "WORKSPACE", at, filing_cutoff?, not_before?}`.
  - Dispatches (`submit-claim`, `submit-response`) carry `filing_cutoff`.
  - `submit-response` also carries `not_before`, the end of the 24-hour response cooldown.
- **How workspace time advances.** For each step, the workflow moves the workspace clock forward to that step's effect time, never backwards:
  - an authored event's own `known_at` for intake;
  - the cooldown end for the response dispatch.
  - So the response is sent **at** `not_before` on the workspace timeline, one day after the approval's `timing.at`. It is not sent instantly.
  - The interface can show "Sent after the 24-hour cooldown, <date>" from `timing.not_before` and `timing.at`.
  - The coordinator never shortens or skips the cooldown or the filing cutoff. A test asserts `at == not_before` and `at < filing_cutoff`.

`workflow.next_actions` is unchanged in shape. After this change it offers only person decisions, "Continue routine steps" (only after an interrupted automatic run) or "Resume interrupted action". Additional fields: `automation.enabled` (the persisted workspace setting) and `steps[].detail` (an error class for a `FAILED` automatic step).

### 3b. Headline and the credit lifecycle (existing fields; two additions)

- **April invoice and credit applied:**
  - `workflow.ledger.bill.id`, `.original_amount`, `.outstanding_amount`
  - `workflow.finance.bill.{id, original, applied, outstanding, application_ref}`
  - `workflow.ledger.applied`, `workflow.ledger.unapplied_credit`
- **Separate open March price exception:** `workflow.price_finding.{id, state, amount, currency, invoice_id, reason, citations, lines[], credit_applied}`. It is a finding, not a credit; never sum it with the credit stages.
- **Credit lifecycle:**
  - `workflow.finance.stages[]`: `{stage, label, amount, status}` for `estimated`, `claimed`, `awarded`, `posted`, `applied`
  - `workflow.ledger.destination` (`Local ledger`), `workflow.connection.{destination, receipt_status}`, `workflow.finance.ramp.{destination, linked_record, note}`
  - `linked_record` is null because no Ramp record is linked; do not label any amount as recovered in Ramp.
- **Additions (missing today):** `workflow.ledger.bill.month` (`2026-04`) and `workflow.price_finding.month`. These let the headline name the months without parsing ids.

### 3c. Denial model job

On the case's interpretation route (`GET /api/correspondence/claims/{id}/interpretation`):
- **`model_job`:** `{enabled, can_request, reason, message, request_sha256, request_bytes, profile, job}`.
- **`job`:** `{id, state, terminal, kind, target, context_digest, request_sha256, reason, result, submitted_at, started_at, finished_at, provider}`.
  - `provider` is the shared service's public receipt block, passed through unchanged, for any state including failures. Its keys are `model, session, client_reported_cost_usd, usage, returncode, tool_events, tool_inventory, mcp_inventory, output_sha256, result_sha256` and `transport{name, revision, binary_sha256}`.
  - Show `tool_inventory: []` and `mcp_inventory: []` to make a tool-free call visible.
  - New reason codes from role 1: `provider_failed` ("the model call failed; no proposal was produced; a new attempt needs its own approval") and `provider_identity_unverified`.
  - `state` is one of `QUEUED`, `RUNNING`, `SUCCEEDED`, `REFUSED`, `CANCELLED` or `UNCERTAIN`; a timeout is `UNCERTAIN` or `REFUSED` with `reason`.
  - The three timestamps are now projected (they exist on the shared job row).
- **`candidates[]`**, shown only after the reviewer's own pre-reading (decision 60/75; the pre-reading screen is an undecided D06 sub-question and is unchanged):
  - `{id, interpretation, provenance}`
  - `interpretation.propositions[]` carries the proposed reading, each with its exact `source.quote` and byte span in the vendor reply: the cited evidence.
  - `provenance` is `{model, request_sha256, response_sha256, session, usage, client_reported_cost_usd, transport, elapsed_seconds, output_mode}`. `model` is the model actually used and `transport` is the provider receipt.
- **`context`:** `{digest, text_sha256, …}`, the source digest.
- **Review state:**
  - `blind_entry` (the reviewer's own reading, or `null`)
  - review ids from `POST …/reviews`
  - `GET …/reviews/{id}/preview` → `{disposition, prepare_allowed, closure_suggested, reported_award, assertions{category, propositions[]}, ledger_unchanged}`
  - after preparation, the case `stage` and `actions`
- **Read-only trace:** `GET /api/correspondence/claims/{id}/trace` (`correspondence[].interpretation`, `deterministic_checks`, `permitted_next_actions`, `disposition`).
- **Request to role 1 (agent2, owner of `public_proposal_jobs.py`):** a failed or timed-out job has no candidate, so it shows no model or receipt. Exposing an allowlisted receipt summary (model, session, elapsed, error class) on the shared job view for non-success states is that owner's call. Until then, my run script records the full receipt in my evidence file.

## 4. Sign-in: setup-side proposal

**Today.** `scripts/setup_northwind.py --directory <dir>` writes `scripted-reviewer.jwk` (0600, exclusive create, refused inside the repository) into the workspace directory. The runbook placed that directory under a hidden `~/.local/...` path, which is where the judge had to dig.

**Proposed** (setup side; role 4 owns the browser side):
1. **Visible export.** Add `--reviewer-credential PATH`: an absolute, operator-chosen, visible location outside the repository, for example `~/Desktop/northwind-reviewer.jwk`. It reuses the existing `write_credential` (0600, exclusive create, no symlinks, refused inside the repo). The workspace copy stays as it is.
2. **Plain instructions.** On success, print one plain block naming the file path, its mode and the three sign-in steps ("Open <origin>, choose Sign in with reviewer file, select this file"). Never print, log or put in a URL the key material; only the path.
3. **No new sign-in shortcut.** There is no one-time login URL and no automatic sign-in. The browser keeps the key in memory only (role 4), so reload still asks for the file. That is deliberate and stays.
4. **Runbook.** The README and demo runbook use the visible path in the first command.

This is my setup-side half; the coordinator reconciles it with role 4.

## 5. Disclosures

- The Northwind contract, invoices, logs and counterparty replies are authored. The counterparty is a local simulator reached through the ordinary signed source route.
- The reviewer is a scripted local principal (`SCRIPTED_REVIEWER`), not an actual person's approval.
- Credits are posted to the "Local ledger", never to Ramp.

## 6. Not implemented: approval-gate proposals for team review

- **`approve-response` under a standing policy** (D06 "policy-eligible" row, narrow case: a factual follow-up supplying exactly the verified evidence the vendor requested, amount 0).
  - This would turn the main branch's four person decisions into three.
  - It needs D06 gap 1, a policy record with actor, action class, evidence class, scope, expiry and escalation. That is a W0 schema change and a team decision.
  - **Not implemented**; written here for review only.

## 7. Progress

### Commits on `work/submission-disputes-20261109`

| Commit | What |
|---|---|
| `67fbc44` | This design |
| `da3a909` | Coordinator, persisted step history, automation view, month fields, setup automation default and visible credential, job timestamps and receipt passthrough |
| `1646930` | Authored, hash-pinned "unclear" reply variant (`--counterparty-reply unclear`) and the one-call denial model-job runner |
| `0225970` | Receipt of the genuine model job |
| `2742be0` | Workspace-timeline timing per step; the plain sign-in block (last three lines: path, account, URL); `--reviewer-credential` with `--resume` |
| (next commit) | Credential fix: on resume an identical owner-only file is reused (`reviewer_credential_copy: REUSED`) and a different file is refused with one plain line. On create the path is checked before anything is written, and a refused path leaves no workspace directory. Also a stale approval binding test. |

### Tests

```sh
uv run --locked --offline pytest -q -p no:cacheprovider --basetemp=<own dir> -o tmp_path_retention_policy=failed \
  tests/test_workflow_coordinator_r2.py tests/test_northwind_workflow.py tests/test_northwind_local_ledger.py \
  tests/test_finance_view_90.py tests/test_finance_guide_90.py tests/test_correspondence_model_jobs_75.py \
  tests/test_correspondence_public_queue_75.py
```

Result on `2742be0`: **156 passed, 1 warning**. No existing test changed; see `docs/v4/TEST-CHANGES-submission-disputes-20261109.md`.

### Genuine model call (one; no retry)

| Field | Value |
|---|---|
| Model | `claude-opus-5-5` |
| Job | `29f371d0-0a49-4b3b-9454-64eaf7bb1261`, `SUCCEEDED` on its only attempt |
| Session | `ce56dc6e-7a02-45be-b8c5-e91d8dfdf03e` |
| Tools / MCP | empty / empty |
| Usage, cost | 418 output tokens; 0.045 USD client-reported |
| Request | SHA-256 `1bdc9057…`, approved for one invocation by "agent3 (engineering operator, role 2)" through `scripts/public_proposals.py approve --confirm-authored-public --hours 1` |
| Receipt | [`evidence/submission-disputes-20261109/denial-model-job.json`](../evidence/submission-disputes-20261109/denial-model-job.json) (pinned; unedited). Raw request and response stay outside Git. |

**How it was driven.** `scripts/run_denial_model_job.py` builds a fresh workspace and drives the application's own signed HTTP routes through an **in-process test client** (`fastapi.testclient`):
- the workflow action that approves the claim;
- the interpretation blind entry and `model-jobs` routes;
- the review and preview routes.

The routes run with the ordinary request proofs, and the shared job service invokes the **genuine provider** (the Claude Code CLI, `claude-opus-5-5`, empty tools and MCP). No browser, no listening socket and no served workspace were involved. Roles 5 and 6 should label it "genuine model call through the application's signed routes, driven by a script with an in-process test client".

- **Input:** the authored unclear January reply.
- **Proposed reading:** `unsupported`, citing the whole reply (bytes 0–200), shown before the semantic review. The scripted reviewer had saved its own reading first.
- **Scripted semantic review:** category `AMBIGUOUS_GROUNDS`; preparing a response is refused.
- **Result:** the case stays in `HUMAN_REVIEW` (escalation), awarded 0.00, one filing, scope unchanged.

### The three outcomes

| Outcome | Where it works today | Evidence |
|---|---|---|
| Cure missing evidence | The Northwind walkthrough, coordinated | `test_routine_steps_run_under_existing_authority_and_only_person_decisions_are_offered`: a log request, then automatic artifact and verification intake, approved response sent at the cooldown, award, credit, application |
| Escalate ambiguity | The Northwind walkthrough with `--counterparty-reply unclear` | The genuine model job above; `test_an_unfamiliar_vendor_reply_pauses_for_the_reviewer_instead_of_continuing` |
| Accept a correct denial through its authorized control | **Correspondence cases in tests only, not the Northwind walkthrough** | `test_correspondence_adversarial_http_89h.py::test_familiar_maintenance_denial_is_order_independent_and_closes_only_on_acceptance` (signed routes, explicit `accept-denial`); `test_blind_acceptance.py` late-denial control; the coordinator's `JUDGMENT_REQUIRED` pause test; the role-4 accept-denial control (gent7, `a47fb5a`). The authored Northwind facts make the January claim valid, so a correct denial there would need different authored facts. I did not invent any. |

**Reproducing the correct-denial demonstration** (runbook, gent8's control):

```sh
uv run --locked pytest -q "tests/test_correspondence_adversarial_http_89h.py::test_familiar_maintenance_denial_is_order_independent_and_closes_only_on_acceptance"
```

Result on this branch: **2 passed** (reply-first and notice-first).
- The test drives the mounted signed routes through an in-process test client. A familiar-wording maintenance denial and a timely notice reach `DENIAL_REVIEW`, and only `POST /denial-acceptance` with the offered basis digest closes the claim. Money is unchanged.
- **No served workspace shows a clickable correct-denial case.** The Northwind walkthrough has none, and setup seeds no other correspondence case. The correct denial exists **only in tests**. A served demonstration would need a separately authored case seeded through setup; that is not built.

### Click and approval counts (actual, from the tests)

| Branch | Before | After |
|---|---|---|
| Cure (Northwind) | 11 clicks; 4 of them person decisions | **4 clicks**, all person decisions: approve claim, approve response, post credit, apply credit; 7 automatic steps with recorded authority |
| Escalation (Northwind, unclear reply) | 3 clicks to reach the reply (approve, file, receive); then the reviewer's reading, model request and review | **1 click** (approve claim). Filing and intake are automatic, then a pause at `UNEXPECTED_GROUND`. The reviewer's own reading, the model request and the semantic review remain person actions. |
| Correct denial (correspondence cases) | Approval and filing clicks; closure was automatic for familiar wording before D06 89e | Unchanged here. Closure is the explicit `accept-denial` (person), which the coordinator never performs. |

### Limitations

- Counterparty replies and the reviewer are authored and scripted. Automatic intake is not proof of a real vendor channel (D08).
- The correct-denial branch is not in the Northwind walkthrough (see above).
- With routine automation off (`--step-by-step`, and the Python `prepare()` default), every step is a click, as before.
  - Tests that build workspaces with `prepare()` keep the eleven-step path.
  - gent8's restart and socket probes create workspaces through the setup command, where automation is on by default. The restart probe's eleven-action assertion therefore failed in the full suite on `02d86f7` (correct product behavior). Its owner, gent8, is moving it to `--step-by-step` and adding a real-process kill for the automated default.
- A failed or timed-out model job shows a receipt only once role 1's shared job projection (agent2, `611efdf`) is merged. My job view passes that `provider` block through.
- No full suite run here; the coordinator runs it after integration.
