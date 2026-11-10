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
| Finish cohort: 6 contracts, 8 replies (14 cases) | **Codex evaluation lane** (`work/evaluation-finish-20261109`) | `805dd1c` | As that lane published in `docs/v4/evaluation-finish-20261109/RESULTS.md` (`origin/main` `b6e93bd`): ordinary onboarding 6/6 refused, 0 SHADOW; 0/4 author-intended positives; 2/2 negative controls refused without establishing their decisive defect; 12 actual Opus 5.5 calls returned (no timeouts or tools), all failing proposal validation; held-out disputes 0 of 8 dispatched (6 setup refusals, 2 source-reading refusals), so dispute model accuracy is unmeasured; 0 of 15 financial scenarios reached; no human or native action. Attributed to that lane, not rescored, and its sealed answers and task directory are not opened. |

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

## Decisions: answers received (coordinator, November 9)

1. **Disk.** The earlier dip was a temporary Chrome update and has cleared. Phase B rule: check `df -k /System/Volumes/Data` first, and do not clone or sync below 1.5 GiB free. Make one fresh clone at a time and delete it afterwards.
2. **C6.** Recorded artifacts only. A fresh read-only Ramp read is Ronok's to start and is not part of this plan. The "Verified Ramp record" panel for bill f74ba12c is checked against the committed November 9 capture and association receipt.
3. **Task 5.** Covered by Ronok's brief, per the coordinator. First, dispatch is established from the implementers' job rows, provider receipts and timestamps. Only where those cannot establish it: one fresh `claude-opus-5-5` call per claimed model path, at most 3 in all, authored or public text only, no retry. Each exact request is approved through the existing operator CLI with `approved_by` naming gent8 as the engineering operator. It never names Ronok and never reads as a human review.
4. **D05 run 2.** Not part of this push. It runs only on Ronok's go-ahead in the evaluation session.

---

# Phase B: acceptance report (frozen commit `52f1a2f`)

**Tested:** `52f1a2f478f414d258dc89e122c243f7f5573e0b` (`origin/frozen/submission-fallback-20261109`). Fresh SSH clone from GitHub, started 2026-11-09 23:25:29Z.
- Tracked-file digest `d519dc1a…` over 342 files.
- Claude CLI 2.1.318, SHA-256 `677a2ea7…`. Node v25.9.0.
- [freeze record](../evidence/submission-acceptance-20261109/freeze-52f1a2f.json)

All results below are terminal. The sealed expectations are revealed in [this file](../evidence/submission-acceptance-20261109/sealed-expectations-revealed.json). Its SHA-256 equals the Phase A commitment `6b1c4057…19481`.

## Headline

The frozen build does what the film plan says for the authored walkthrough:
- From a fresh clone, the published instructions lead to sign-in and four reviewer decisions, with seven automatic steps between them. **[Qualified 2026-11-09 23:59Z: only after `git checkout 52f1a2f`, a step the README does not contain. A default clone gets `main` at `b6e93bd`. See the Task 4 correction and finding P1-A.]**
- The money, citations and authority records match the sealed expectations exactly.
- Every refusal and control behaved safely: **no unsafe acceptance, invented evidence or unauthorized money movement was observed.**

The limits that must be stated:
- **The model work is recorded, not live.** It is genuine and verified, on authored inputs.
- **Generalization is not shown:** the Codex lane's independent cohort is 0/4.
- **Correct denial cannot be exercised through the HTTP routes with a genuinely late filing.**
- **Missing-evidence recognition is narrow.**
- **Nothing reaches Ramp from Uptime.**

## Task 4: fresh clone, published instructions only — PASS, with recorded deviations

| Step | Observed |
|---|---|
| Commands | The README's two commands. The setup command printed the credential path, account `scripted-test-reviewer` and URL, as documented ([output](../evidence/submission-acceptance-20261109/setup-output.json)). |
| Deviations forced by this machine | SSH clone (the repository is private); workspace under scratch instead of `$HOME/uptime-demo`; `--origin http://127.0.0.1:8851`, because 8776 is the occupied presentation port. `--origin` is documented in the linked `NORTHWIND-WORKFLOW.md`. **[Corrected 2026-11-09 23:59Z — see below.]** |
| Person path (`BROWSER`, headless system Chrome) | Type the account, choose the credential file, Sign in, then click four decisions: "Approve January claim", "Approve response", "Post to Local ledger", "Apply credit to eligible invoice". 13.9 s of interaction. No undocumented step. [log](../evidence/submission-acceptance-20261109/person-path-log.json) |
| Setup time | About 1 s, with the uv cache already warm. A judge's first run includes the dependency download, which this machine did not measure. |

**Correction, 2026-11-09 23:59Z** (requested by the coordinator; the original row above is kept as written):

- **What was done at the time (23:25Z).** Phase B cloned `git@github.com:ronoktanvir/uptime.git`, the SSH URL of this machine's existing remote. It then ran `git checkout 52f1a2f` before the README's second command.
- **Two errors in the original row:**
  - The reason "the repository is private" was never checked. It was assumed.
  - The row leaves out the checkout itself. That checkout was a deviation: the README contains no such step.
- **What happens now.** The README's first command, `git clone https://github.com/ronoktanvir/uptime.git`, was run anonymously over HTTPS: no credential helper, no git config, no prompt, no SSH.
  - It exits 0. The repository is public (the unauthenticated API reports `visibility: public`).
  - The clone checks out `main` at `b6e93bd`.
  - `git checkout 52f1a2f` then succeeds; the commit is reachable as `frozen/submission-fallback-20261109`.
  - SSH is therefore not needed. The only deviations a judge's machine needs are the workspace folder and, where 8776 is taken, `--origin`.
- **What this changes in the verdict.** The PASS holds for the frozen build *once it is checked out*. The published instructions alone do not reach that build (finding **P1-A** below). The same qualification applies to:
  - the first headline bullet;
  - the "Setup readiness" row in Task 10.

[Record of the anonymous clone](../evidence/submission-acceptance-20261109/anonymous-clone-20261109.txt). The clone was deleted afterwards.

## Task 5: actual model dispatch — PASS from recorded artifacts. No fresh calls were made.

| Path | Evidence | Result |
|---|---|---|
| Contract interpretation (role 1) | Receipts in `docs/v4/evidence/submission-onboarding-20261109/`, cross-checked against the preserved workspace's own `public_proposal_jobs` rows (read on a copy) | 6 jobs, 6 distinct sessions, `claude-opus-5-5` reported by provider and response, empty tool and MCP inventories, 0 tool events, request and output SHA-256, 11.0–14.3 s each, one job per family, no retry. Approvals name the engineering agent, never Ronok. Corvid Ledger: SHADOW with 11 quotations, all 11 re-sliced from the recorded source. Halden Relay and the control: `NO_SUPPORTED_FAMILY`. |
| Denial reading (role 2) | `denial-model-job.json` plus the preserved workspace row | Session `ce56dc6e…`, `claude-opus-5-5`, empty tool and MCP inventories, request hash matches, 5.4 s. Reading `AMBIGUOUS_GROUNDS` led to `HUMAN_REVIEW`, awarded 0.00, ledger unchanged. Approval names agent3 as engineering operator. |

Qualifications:
- The onboarding calls ran on `611efdf`, plus a later uncommitted refusal-explanation change, not on `52f1a2f`. The extraction, validation, selection, job and transport modules are **byte-identical** between `611efdf` and `52f1a2f`, so the runs represent this build's model path.
- The committed denial evidence omits the transport receipt and the source commit; only the preserved database row carries the transport fields.
- The recorded workspaces' interface was not rendered by acceptance.

## Task 6: money, citations, authority — PASS

| Check | Result |
|---|---|
| Money | Before the decisions: estimated $2,400.00, separate open March exception $1,000.00. After: April invoice $11,000.00, credit applied $2,400.00, remaining $8,600.00. Stages estimated, claimed, awarded, posted and applied are each $2,400.00, shown as one credit and never summed. Price finding `PREPAYMENT_REVIEW` $1,000.00 with $0.00 applied. Destination Local ledger; `finance.ramp.linked_record` null. All match the sealed values. ([before](../evidence/submission-acceptance-20261109/overview-before.txt) · [after](../evidence/submission-acceptance-20261109/overview-after.txt)) |
| Citations | **58/58** citations in the workflow view re-slice exactly, with matching quote hashes, from `order-form.txt`, `amendment-2026-03.txt` and the SLA document |
| Authority per step | 4 approvals or financial changes are `PERSON` (`scripted-test-reviewer`). 2 dispatches are `APPROVED_OPERATION` with an approval digest. 5 intakes are `EVENT_INTAKE` with event IDs. No automatic step makes a judgment or moves money. The reviewer is displayed as "Dana Reyes · Scripted reviewer". |
| Ramp wording | No screen says money was recovered in Ramp. The Ramp card reads "No Ramp bill is linked to this agreement". |

## Task 7: controls

| ID | Transport | Input | Result | Against the sealed expectation |
|---|---|---|---|---|
| T7-CD | — | Sealed late-filing denial with a genuinely late filing | **Not exercisable.** The signed HTTP routes refuse to file after the cutoff; the historical late-original path exists only in service-level tests. | Not run as specified |
| T7-CD substitute | `REAL_HTTP` | The product's recognized correct-denial class: announced maintenance corroborated by the customer's notice | `DENIAL_REVIEW` offering only `accept-denial`; no money. After a signed acceptance: `DENIAL_ACCEPTED`, no actions, awarded 0.00, one submission. | Matches the expected outcome, using a substituted input |
| T7-CD wrong ground | `REAL_HTTP` | Sealed late-filing text against an **on-time** claim | `HUMAN_REVIEW`, no actions, no money. Not accepted as substantiated. | Safe |
| T7-AD | `REAL_HTTP` | Sealed conditional and waiver reply | `HUMAN_REVIEW`, no actions, awarded 0.00; nothing settled or waived | **Met** |
| T7-ME | `REAL_HTTP` | Sealed "please provide the request log…" reply | `HUMAN_REVIEW`, `requested_artifact` null. **Not recognized as an evidence request.** Safe: nothing invented, no money. | **Not met as specified** (expected an evidence wait) |
| T7-DS | `REAL_HTTP` | Duplicate decision, exact signed replay, re-signed redelivery | Single effect; replay refused; redelivery leaves state identical | **Met** |
| T7-RS | `REAL_HTTP`, two OS processes | SIGKILL mid-flow, step-by-step and automated | Identical state; replay unchanged; 11 steps, each once; exact ledger | **Met** |
| T7-TO | `CONTROLLED_PROVIDER` (fake executable hanging 75 s) | Authored harness control through the model-job route | Both family jobs `UNCERTAIN` / `provider_timeout`; outcome `INCOMPLETE`; no candidate; one invocation per family, no retry; review requirement names the inconclusive state. Visibility in the browser not checked. | **Met** at the API level |
| T7-FO | `REAL_HTTP` | DocuSign bill as a Northwind claim invoice; an unknown claim; tenant crossing | 403 "bind an inbound source"; 404; workflow unchanged; no link. Tenant crossing refused (probe). | **Met** |

Probe suite on the fresh clone: `uv run --locked pytest -q tests/test_release_probes_gent8.py` gave **7 passed, 1 warning in 17.76 s** ([log](../evidence/submission-acceptance-20261109/probes-52f1a2f.log)). Control outputs: [CD/AD/ME](../evidence/submission-acceptance-20261109/controls-t7-cd-ad-me.json) · [timeout](../evidence/submission-acceptance-20261109/timeout-control-report.json) · [foreign object](../evidence/submission-acceptance-20261109/foreign-object-control.json)

## Task 8: presentation claims

| Claim | Grade | Basis and required wording |
|---|---|---|
| C1 (0–15 s): manual workflow | **Supported** (narration) | README "The old way" section; no product screen claims automation it lacks |
| C2 (15–40 s): model-assisted contract interpretation | **Supported with stated limits** | Genuine `claude-opus-5-5` on authored contracts. **Recorded on November 9, not live.** 1 of 2 authored positives reached SHADOW. The Northwind contract itself uses fixed rules. Do not imply that unseen contracts work: the Codex lane's independent result is 0/4. |
| C3 (40–65 s): deterministic finding and approval | **Supported** | $2,400.00 from the engine with cited clauses that re-slice; the approval is a signed `PERSON` step by the scripted test account, labelled as scripted on screen |
| C4 (65–95 s): denial, evidence cure, required review | **Supported with stated limits** | In the walkthrough, the request-log denial is read by fixed rules, not a model. The cure arrives as signed authored evidence through intake. The response approval is a person decision. The model's denial reading exists only in the separate recorded unclear-reply workspace. Correct-denial acceptance is shown only through tests and this report. |
| C5 (95–115 s): credit lifecycle and balance | **Supported** | Exact sealed values: $11,000.00, $2,400.00, $8,600.00, the open $1,000.00 March exception, Local ledger |
| C6 (115–120 s): Ramp connection and limitation | **Supported with stated limits** | Panel: business `1569e402…`, DocuSign, bill `f74ba12c…`, DD-PREAPPROVAL, USD 840, comment `376563cf…` "Posted by a person in Ramp; Uptime read it back", read at 22:00 UTC started by a person, "Not a live read". No Uptime-origin write. Northwind not linked. ([panel text](../evidence/submission-acceptance-20261109/ramp-records.txt)) |

## Task 10: separate scores

| Bucket | Result |
|---|---|
| Parser success | Northwind's contract and its request-log reply are parsed deterministically. A differently worded evidence request (T7-ME) is not recognized. |
| Model interpretation | Recorded genuine runs: 1/2 authored positives reached SHADOW; the control was refused; the unclear reply was read as ambiguous. **Independent unseen result, by the Codex evaluation lane on `805dd1c`: 0/4 positives; dispute accuracy unmeasured.** Historical results (0/50, 0/4, 3/6, Backblaze refusal) are unchanged. |
| Setup readiness | Fresh clone to walkthrough with the documented steps only. The held-out dispute cohorts are setup-blocked (see the register). **[Qualified 2026-11-09 23:59Z: the frozen build must be checked out explicitly; see finding P1-A.]** |
| Reviewed outcome | 4 person decisions complete the walkthrough. Correct-denial acceptance works through signed routes. |
| Automatic execution | 7 automatic steps, each under approved-operation or event-intake authority; none makes a judgment or moves money |
| Native effects | **None by Uptime.** One person-posted note, read back. |

## Bugs and risks, ranked by consequence (reproductions in the evidence files; none fixed here)

**Added 2026-11-09 23:59Z, after the report.** It ranks first. The numbering of items 1–6 below is unchanged, so earlier references to them stay valid.

**P1-A: a judge who follows the README runs `main`'s build, not the frozen one.** The default branch is `main` at `b6e93bd`.

*Reproduction:*
- Anonymous `git clone https://github.com/ronoktanvir/uptime.git` checks out `main` at `b6e93bd`.
- The repository page renders `main`'s README: blob `bf3ca57`, not the frozen `4057017`.
- Neither README says to check out `52f1a2f` or `frozen/submission-fallback-20261109`.
- The frozen README's second command (`setup_northwind.py --directory … --serve`) is accepted by `main`'s script without error. A judge gets no signal that the build differs.

*Consequence:*
- `main` is an ancestor of `52f1a2f`, 85 commits and 109 files behind.
- It lacks the merges for role 2's dispute automation (`02d86f7`), role 1's contract intelligence and role 3's Ramp context (`c756853`, `ff7977c`), role 4's screens (`0fe20b4`, `6b93e31`) and role 6's README and judge guide (`52f1a2f`).
- Every acceptance result in this report is for `52f1a2f`. None of it is evidence for what a default clone runs. `main`'s walkthrough was not run here.

*Why P1 and not P0:* no unsafe behaviour or wrong money was observed. The issue is that the judged build is not the accepted one.

*Not fixed by acceptance.* Moving `main` or changing the published instructions is Ronok's decision.

**[Closed 2026-11-10 01:49Z]** `main` was fast-forwarded on Ronok's word. An anonymous default clone checked out `0c30f8f`, a descendant of `52f1a2f`, with no extra step. Rechecked at 05:25Z: the default clone gets `08852a6`, also a descendant. See the addendum at the end.

1. **P2: evidence-request recognition is narrow.** A plain request for a request log, worded differently from the product's own phrasing, goes to human review instead of an evidence wait (T7-ME). It is safe, but the README phrase "A recognised request is answered with verified evidence" must not be presented as general recognition.
2. **P2: a constructed scenario sits beside the real Ramp bill.** The Ramp records page lists bill `ae98c421…` (USD 840, earlier capture) with "Invoice cap review · Contract finding ELIGIBLE · USD 40.00 · Scenario only, not a finding". It is labelled, but it shows a constructed $40 eligibility figure in a findings column next to the verified bill. Earlier demo guidance (DEMO-PATH-87) warned against constructed $40/$800 figures. ([panel text](../evidence/submission-acceptance-20261109/ramp-records.txt))
3. **P3: February's credit shows "Not determined" for an ineligible month.** The service-credit evaluation row reads "Ineligible" with credit "Not determined". The credit is known to be zero, so this blurs the ineligible-versus-unknown distinction the product depends on ([after](../evidence/submission-acceptance-20261109/overview-after.txt)).
4. **P3: a README wording error.** "One call per case" is inaccurate: each authored contract made two calls, one per family (11–14 s each). The denial reading took 5.4 s.
5. **P3: evidence completeness.** `denial-model-job.json` lacks the transport receipt and source commit. The onboarding receipts pin `611efdf` plus an uncommitted change rather than the frozen commit; the code path is byte-identical.
6. **Limitation, not a bug: correct denial with a genuinely late filing** cannot be driven through the HTTP routes, and no demo workspace shows correct-denial acceptance. This is already disclosed in `docs/JUDGES.md`.

**Not assessed:** the interface redesign on `work/submission-design-20261109` and the side-panel option. Browser visibility of a timed-out job. The recorded workspaces' interface.

**Do not claim:** production readiness, unseen-contract reliability, dispute accuracy, any money in Ramp, or a person's approval. The walkthrough reviewer is a scripted account.

---

# Addendum, 2026-11-10: interface-only acceptance of `main` at `08852a6`

Requested by the coordinator. Phase B above is unchanged. **Tested:** `08852a611a1bc6db2714f675e47bd143c60943f9`, anonymous HTTPS clone started 05:25:43Z.

- **What changed since `52f1a2f`:**
  - one setup-script fix (plain one-line refusals);
  - the redesign, Phosphor icons and the Inter font, in `web/`, `tests/` and `docs/` only;
  - the opt-in side-panel framing option. Under `uptime/`, only `server.py` differs.
- **Method:**
  - Browser: headless system Chrome 157 at 1440×900, every launch under a time limit. No launch stalled; each took under 0.6 s.
  - Server values: read through the workspace's own signed scripted-reviewer headers, using GET only.
  - Limits: no model call, no Ramp contact, one clone, deleted afterwards. Ports 8851–8853 and 8859 only.
- **Earlier attempt, kept:** the same checks ran on `0c30f8f` from 01:49Z. The Mac restart at about 18:35 PST cut that run off before the report. All points it reached gave the same results as below. [Its evidence](../evidence/submission-acceptance-20261109/main-0c30f8f/) · [this run's evidence](../evidence/submission-acceptance-20261109/main-08852a6/)

## Results by point

| # | Check | Result |
|---|---|---|
| 1 | Default clone | `git clone` checks out `main` at `08852a6` with no extra step; `52f1a2f` is an ancestor. **P1-A stays closed.**<ul><li>The README's second command plus the documented `--origin` built and served the workspace from a cold uv cache.</li><li>8776 was free on this run, so the verbatim command was not run: it would have bound the presentation port. On `0c30f8f`, with 8776 occupied, it refused in one line (`Port 8776 is already in use … choose another port with --origin`) and wrote nothing.</li></ul> [record](../evidence/submission-acceptance-20261109/main-08852a6/clone-and-setup.txt) |
| 2 | Person path and sealed values | Sign-in, then "Approve January claim", "Approve response", "Post to Local ledger", "Apply credit to eligible invoice": 13.2 s, no undocumented step. All sealed values hold exactly:<ul><li>April $11,000.00 → $2,400.00 applied → $8,600.00;</li><li>the five stages at $2,400.00 each, "not added together";</li><li>the March exception $1,000.00, open, $0.00 applied;</li><li>Local ledger, no Ramp record linked;</li><li>authority: 4 `PERSON` steps by `scripted-test-reviewer`, 2 `APPROVED_OPERATION` with digest, 5 `EVENT_INTAKE` with event ID, no duplicate step;</li><li>**58/58** citations re-slice.</li></ul>Every figure is visible on the Overview without opening anything. Two things moved behind a closed section: the citations (per section, "Cited clauses (9)", "(15)") and the reviewer's scripted label (finding A3). [log](../evidence/submission-acceptance-20261109/main-08852a6/person-path-log.json) · [values](../evidence/submission-acceptance-20261109/main-08852a6/workflow-view-summary.json) |
| 3a | Finding 2 ($40 scenario) | **Resolved for the default view.** Ramp records opens with the verified record alone. The "Invoice cap review · Scenario outcome: Eligible · USD 40.00 · Scenario only, not a finding" row appears only inside the closed "Records in this worklist" section, under the separately labelled earlier partial capture. The one-bill page for that bill lists the scenario as "Scenario only, not a finding" with no amount. A residual P3 applies only if the film opens that section. |
| 3b | Finding 3 (February) | **Resolved, and acceptable.**<ul><li>The row reads "Ineligible · No credit".</li><li>The server keeps February's `amount` null with outcome `INELIGIBLE` (0 completed shortfall increments, 0%).</li><li>The page prints "No credit" only when the amount is null *and* the outcome is `INELIGIBLE` (`web/workspace_ui.js:361`). It never invents "$0.00".</li><li>March, whose credit is genuinely unknown, still reads "Not determined".</li></ul>"Unknown amounts stay null" is honoured: February's credit is not unknown, it is decided as none. |
| 4 | "Reviewer decision" wording | Step tags, tallies and Activity attribute every decision to `scripted-test-reviewer` ("4 reviewer decisions", "Decided by scripted-test-reviewer"). **One exception, on the main screen: finding A1.** The remaining "a person" texts are true or are requirements, not claims:<ul><li>"Posted by a person in Ramp" and "started by a person" (Ronok's own Ramp actions);</li><li>"have a person approve before activation".</li></ul> |
| 5 | Side panel | Verified myself over plain HTTP and in Chrome:<ul><li>**Without the option:** `frame-ancestors 'none'` on every response, including 401, 404 and the font.</li><li>**With `--side-panel-origin chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl`:** exactly that origin, and setup prints that only it may frame the workspace.</li><li>**Resumed without the option:** back to `'none'`. The option is not stored (`workspace.json` has no such field).</li><li>**POSTs:** with the extension's origin, the sign-in challenge and a decision route return 403 "Same-origin authenticated workbench action required", on both workspaces. The control with the app's own origin returns 200. A missing origin, a foreign origin and `Sec-Fetch-Site: cross-site` are refused too.</li><li>**Invalid values:** a web origin, `*`, uppercase, two origins, a trailing slash or a 33-character ID each exit 1 with one line, before any folder or port is used. The option without `--serve` exits 2.</li><li>**Foreign framing:** a page on `127.0.0.1:8859` that frames either workspace gets Chrome's own "Framing … violates … frame-ancestors" block.</li></ul>**Not verified by me:** loading the extension, the browser's side-panel container, real Ramp pages. The coordinator's real-extension record ran on an unpushed local combination (`21eae2c` + `a92f86c` + `ed8042`), not on `main`. [default](../evidence/submission-acceptance-20261109/main-08852a6/sidepanel-default.json) · [option](../evidence/submission-acceptance-20261109/main-08852a6/sidepanel-option.json) · [resumed](../evidence/submission-acceptance-20261109/main-08852a6/sidepanel-resumed.json) · [framing](../evidence/submission-acceptance-20261109/main-08852a6/sidepanel-frame-attempt.json) · [invalid values](../evidence/submission-acceptance-20261109/main-08852a6/sidepanel-invalid.txt) |
| 6 | One-bill page | Ten loads: the saved bill, a well-formed unknown ID, the worklist bill `ae98c421…`, the saved ID in upper case, its 8-character prefix, `not-a-bill`, a broken percent-escape, an HTML-injection ID, an empty ID, and a cold load before sign-in.<ul><li>Only the saved ID (any case) and the cold load show the verified DocuSign record.</li><li>The unknown, prefix, malformed and empty IDs show "No saved record for this bill" with none of its facts.</li><li>The worklist bill shows its own capture only.</li><li>No dialog fired.</li><li>Nothing says "recovered". The only "attach" wording is "No contract finding is attached to this bill".</li></ul> [results](../evidence/submission-acceptance-20261109/main-08852a6/bill-pages.json) |
| 7 | Font | `web/InterVariable.woff2` is git blob `5a8d3e72…`, 352,240 bytes, equal to `rsms/inter` tag `v4.1` (checked through GitHub's contents API, metadata only).<ul><li>It is served as `font/woff2` from `/static/` on the app's own origin, and the served bytes equal the file. Inter is loaded.</li><li>Every request on every page in this run went to `127.0.0.1:8851` only. The `demo.ramp.com` strings in `web/` are link targets, never loaded.</li><li>The served content security policy is byte-identical to `52f1a2f`'s.</li><li>The OFL 1.1 licence is reproduced in `THIRD-PARTY-NOTICES.md`.</li></ul> [record](../evidence/submission-acceptance-20261109/main-08852a6/font-check.txt) |
| 8 | Case page | Estimated, claimed and awarded show $2,400.00 in view and the disputed remainder $0.00; the page says "The amounts are not added together". Posted and applied are left out of the summary. **Graded P2 — finding A2.** |

## Findings, ranked by consequence (reproductions in the evidence; none fixed here)

**A1 (P2): the main screen says the walkthrough waits for "a person" to approve, and the approval then comes from the scripted account.**
- *Where:* the Overview's routine-steps line, with nothing opened. It reads "Paused · Waiting for a person to approve" before decision 1 and after decision 1. After decisions 2 and 3 it reads "…to approve a ledger change". That is 4 of the walkthrough's 5 on-screen states, the ones the film shows.
- *Source:* `PAUSE_REASON` in `web/workspace_ui.js:425–428`, already present in `52f1a2f`. Phase B missed it. The redesign's own rule a few lines further down says a decision is attributed to the reviewer account, "never to 'a person': the account may be a scripted one".
- *Same table, not rendered in this run:* "Waiting for a person's judgment", "Stopped for a person: …", and "must be resumed by a person". Also the step-by-step summary "Each step runs when a person presses it" (line 446).

**A2 (P2): the case page's closed claim record shows "Posted USD 0.00" and "Applied USD 0.00" for a credit that was posted and applied.**
- *The contradiction:* the Overview and the workflow ledger show $2,400.00 at both stages.
- *Where:* "Show dispute record" → "Decision, unknowns and amounts as recorded", and the ledger block further down the same page, once closed sections are opened.
- *Cause:* the correspondence API sends constants for every claim: `posted="0.00", applied="0.00"` (`uptime/correspondence.py:822`, unchanged since `52f1a2f`). The correspondence record does not know whether the credit was posted, so the honest value is null ("unknown amounts stay null"), or the ledger's own value.
- *Not exercised, same function:* line 816 turns a missing estimate into `"0.00"`. That shows an unknown estimate as zero.
- *Why P2 and not P1:* the visible case summary omits these two stages. No money moved wrongly, and the workflow ledger is correct. It is still a false money figure one click from the walkthrough's own case page.

**A3 (P3): the reviewer's "Scripted reviewer" label is now only inside closed sections on the Overview.** Those sections are "CalyxQuay coverage in this workspace" and "Agreement & review record"; Phase B's rendered Overview showed it. The account name stays visible without opening anything: in the header ("Sign out · scripted-test-reviewer"), on every Activity step ("Decided by scripted-test-reviewer") and in Agreements ("scripted-test-reviewer (scripted test)"). The Overview's own visible text says "4 reviewer decisions", without "scripted".

**Finding 2, residual (P3, only if opened):** the $40 scenario row remains inside the closed worklist section, labelled.

**Not findings:**
- "Ask about this case" is deterministic: `uptime/finance_guide.py` says "No model is called", so the README's "no model access needed" holds. It was not clicked.
- "January recovery" and "Contract review & recovery" are unchanged since Phase B and sit beside "Local ledger"; no screen says "recovered in Ramp".

**Not assessed:** the extension itself and the side-panel container; narrow widths; the recorded model workspaces' interface; pause states other than the walkthrough's (read from source only).
