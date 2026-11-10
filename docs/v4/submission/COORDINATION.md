# Submission readiness: coordination record

Started November 9, 2026, 12:50 PST, at Ronok's request. One coordinator turns the November 9 judge review into a better product and a two-minute presentation. This file is the dependency map: owners, branches, tested commits, blockers and evidence. It is a dated record, updated after meaningful events; it does not show that any agent is still running.

**For the current state in one page, read [the handoff](HANDOFF.md):** what is verified, what is published, what was measured, what reached Ramp, the commands, and the decisions that wait for Ronok.

**Objective.** Show one credible sequence: contract → cited obligation → financial finding → reviewed claim → understood denial → evidence-backed response → credit reconciliation. Ramp stays the financial system of record. The presentation must separate what Uptime computes, what a model proposes, what a person approves and what has actually reached Ramp.

## Starting point (verified 13:00 PST)

| Item | State |
|:---|:---|
| Judged commit | `fcbeede` (fresh clone, walkthrough run end to end by the judge session) |
| Current `origin/main` | `55ea607`; 94 files changed since `fcbeede`, none under `web/` |
| `web/` and `README.md` | **Byte-identical** between `fcbeede` and `55ea607`, so every interface and README criticism still applies |
| Application source | Last changed at `805dd1c`; later commits change records and `progress/data.json` only |
| Regression baseline | `uv run --locked pytest` on `805dd1c`: 5,298 passed, 1 warning in 357.07 s ([receipt](../evidence/finish-20261109/final-805dd1c.json), run by the Codex integration lane) |
| Independent cohort | Six contracts and eight replies, executed once 12:49–12:58 PST by the Codex evaluation lane. **Results not yet published; not opened by the coordinator.** Historical 0/4, 3/6 and 0/50 stay as recorded |
| Free disk | 3.5 GiB. One full suite at a time |

**Other owners active on this machine.** The four Codex-run lanes (`work/{integration,onboarding,disputes,evaluation}-finish-20261109`) own their worktrees and have been fast-forwarding `main`; they cannot be messaged from Claude sessions and are observed through Git only. The overview session audits disk and lanes until 16:23 PST. The judge session is drafting README and screenshot material from `fcbeede`.

**Local services left untouched.** 8776 presentation workspace (`a6e5931`), 8777 Ronok's recorded CalyxQuay review (never restart it on new code), 8780 progress dashboard, 8797 the judge session's scratch run.

## Judge findings against current source

| Finding | Class | Evidence on current source | Owner |
|:---|:---|:---|:---|
| No model runs in the walkthrough; "Generate proposals" is disabled there | Missing functionality in the demo path (both model paths exist) | `web/v4_ui.js` and `scripts/setup_northwind.py` unchanged since `fcbeede` | Onboarding, Disputes |
| Guide answers a renewal-date and notice question with `Clause 1: "Service Level Agreement"` | Bug, to be reproduced with a failing test | Guide modules unchanged since `fcbeede` | Onboarding |
| Published scores 0/4, 3/6, 0/50 and the Backblaze refusal | Historical first attempts, never rescored. Remediation is integrated; the new cohort result is pending | [FINISH-20261109](../FINISH-20261109.md) | Acceptance |
| Eleven manual clicks on one button | Missing functionality. Seven of the eleven operations are intake or dispatch after approval; four are approvals or ledger actions | `uptime/northwind_workflow.py` `_next` | Disputes, Interface |
| Counterparty replies are authored | By design; disclosed in the runbook and narration | `fixtures/northwind/` | Presentation |
| "Ramp bill: Not linked", destination "Local ledger" | Accurate state, not a defect | `connection` and `ledger` in the workflow view | Presentation |
| Northwind cannot run beside a Ramp connection | By design; the isolation check stays | `uptime/server.py:38` | Ramp (context link only) |
| Ramp page lists bills by UUID from a truncated capture | Usability defect and missing pagination disclosure | `web/ramp_ui.js` unchanged | Ramp |
| No Uptime-origin Ramp write | **Blocked by authorization.** The agent posting retest was refused; only a person may run the operator route | [TEAM-DECISION-HANDOFF](../TEAM-DECISION-HANDOFF.md) | Ramp (packet only) |
| Northwind and the real Ramp bill are separate stories | Partly blocked: D02 (a delegated default) keeps Northwind out of Ramp. A person may create a matching authored bill | D02 | Ramp (proposal only), Ronok |
| Navigation sprawl, three workspace names | Usability defect | `web/index.html`, `web/app.js:151,347,357` | Interface |
| Headline is four tiles reading $2,400; the $11,000 → $8,600 and $1,000 results are buried | Usability defect; the values already exist in the `ledger`, `price_finding` and `finance` projections | `northwind_workflow.view` | Interface |
| Raw hashes, ISO timestamps, `20000000/1000000% credit` | Usability defect at the rendering boundary. The fraction is an evaluator message (`uptime/vendor_eval.py:141,145`); pinned evaluator source is not edited for display | `web/` unchanged | Interface, with Onboarding advising |
| `'Simulated award' → 'Awarded credit'` text substitution | Usability and trust defect | `web/app.js:18` | Interface |
| Sign-in needs a `.jwk` from a hidden folder; reload discards the signing key | Usability defect. The in-memory key is deliberate; the hidden path is not | `web/auth.js`, `scripts/setup_northwind.py` | Interface, Disputes |
| README: no screenshot, video, before-and-after or problem size; first command opens the engineering map; test count stale (3,967) | Presentation defect | `README.md` unchanged | Presentation |

## Roles, owners and branches

Every branch starts from `origin/main` at `55ea607` or later. Sessions are existing Claude Code sessions in the "ramp" group, reused because each already owns the matching workstream. Model and effort are read from session metadata, not assumed.

| Role | Session (model, effort) | Branch | Owns |
|:---|:---|:---|:---|
| Coordinator and integration | this session (`claude-fable-5-2`, max) | `work/submission-integration-20261109` | Merges, serialized full suites, this record, shared schemas and central routes listed in [OWNERSHIP](../integration90/OWNERSHIP.md) |
| 1. Contract intelligence | `agent2` (`claude-opus-5-5`, xhigh) | `work/submission-onboarding-20261109` | `uptime/vendor_*.py`, `uptime/onboarding*.py`, `uptime/public_proposal_*.py`, `uptime/vendor_api.py`; guide answer logic for this push |
| 2. Dispute automation | `agent3` (`claude-opus-5-5`, xhigh) | `work/submission-disputes-20261109` | `uptime/correspondence*.py` (except types), `uptime/disputes*.py`, `uptime/northwind_workflow.py`, `scripts/setup_northwind.py`, the workflow coordinator |
| 3. Ramp connection | `agent4` (`claude-opus-5-5`, xhigh) | `work/submission-ramp-20261109` | `uptime/ramp*.py`, `scripts/ramp*`, the capability matrix and operator packet |
| 4. Presentation interface | `gent7` (`claude-opus-5-5`, xhigh) | `work/submission-ui-20261109` | `web/`, `uptime/workbench.py`, browser interaction tests |
| 5. Independent acceptance | `gent8` (`claude-opus-5-5`, xhigh) | `work/submission-acceptance-20261109` | Acceptance report; expected outcomes stay isolated from implementers |
| 6. README, evidence, film | `agent0` (`claude-opus-5-5`, xhigh), starting from the judge session's drafts | `work/submission-presentation-20261109` | `README.md`, the judge-facing guide, screenshots, storyboard |

Each owner keeps one handoff file, `docs/v4/submission/<role>.md`, with its interface notes, evidence and limits, plus its ledger `docs/v4/TEST-CHANGES-submission-<role>-20261109.md` for every changed existing test (exact name and reason).

## Dependency order

1. Refreshed baseline (done above).
2. Model and workflow interfaces (roles 1 and 2) → interface (role 4). Role 4 starts on work that needs no new interface.
3. Ramp capability and identity review (role 3) → connected-context presentation (role 4).
4. Frozen combined application → independent acceptance (role 5).
5. Verified application and acceptance findings → final screenshots, README and film (role 6).

## Shared interfaces

The interface renders persisted backend state. It never computes money, never times its own transitions and never substitutes one state name for another.

- **Financial headline and credit lifecycle** (role 2 provides, role 4 renders): from the existing `ledger`, `price_finding` and `finance` projections of `GET /api/workspace/workflow`. Amounts are decimal strings or null. Estimated → Claimed → Awarded → Posted → Applied are states of one credit with its real destination.
- **Automation state** (role 2 provides): persisted run state per step, giving class (intake, computation, delivery, judgment, approval, financial mutation), actor or policy authorization, state, time, and a typed pause reason (approval required, missing authority, uncertain delivery, contradictory evidence, unexpected legal ground).
- **Model job state** (roles 1 and 2 provide): job identifier, kind, state including failure and timeout, provider and model actually used, provider receipt, source digest, timestamps, exact quotations, proposed terms, validation outcome and lifecycle state.
- **Ramp context** (role 3 provides): exact business, vendor, bill and agreement bindings, observation time, completeness of the capture and the exact Ramp link.

Owners publish the actual field names in their handoff file before the interface consumes them.

## Rules for this push

- Decimal or integer money, citations, deadlines, exclusions, state machines, tenant boundaries and idempotency stay strict. Unknown stays null.
- Models propose. They do not authorize, invent evidence or create financial truth.
- No demo or synthetic badges and no hidden flags in product screens; source identity and authorization records stay intact; destinations and financial states stay accurate.
- Northwind's agreement is never attached to the unrelated DocuSign bill. Local amounts are never described as money recovered in Ramp.
- Nobody repeats the CalyxQuay review, creates another exception, reads Ronok's reviewer key or signs as him.
- The refused agent-run Ramp posting is not retried or routed around by any model, browser, script or credential. No real vendor communication.
- No credentials, private evaluation answers or customer captures in Git or in model context.
- Specialists run focused tests only, with a named `--basetemp` they delete afterwards. The coordinator alone runs `uv run --locked pytest` after each integration merge, one at a time, and keeps failure logs.
- No force-push. Failed and interrupted runs are kept.
- Any proposal to combine or remove an approval gate is written up separately for team review and not implemented.

## Coordinator decisions

Each is reversible and inside Ronok's brief. None changes an approval gate, a financial meaning or what may be sent to Ramp.

| Decision | Choice | Why, and how to undo it |
|:---|:---|:---|
| Getting the real Ramp bill onto the page (role 3, task 5) | Add a second packaged read-only record, `fixtures/ramp/verified-demo-bill.json`, shown as a "Verified Ramp record" panel beside the unchanged November 5 worklist. Replacing the November 5 capture was rejected | The bill id, business id and operator-observed URL are already committed (20, 10 and 2 places), so nothing new is disclosed. The note stays attributed to a person, the agreement binding is NONE and no finding attaches. Undo by deleting the fixture and the panel |
| Sign-in (roles 2 and 4) | Setup gains an explicit `--reviewer-credential PATH` and always ends by printing the credential path, account name and URL. The README's first command uses a visible directory. No automatic copy of key material into the home folder, no login URL, key in browser memory only | Removes the hidden-folder hunt without a second default copy of a private key. Undo by removing the flag and the printed block |
| Genuine model calls for the demonstration | Role owners record the exact-request permission through the existing operator command, for authored or public text only, naming themselves as the engineering operator. Planned: six calls for three authored contracts, up to three for denials, up to three for acceptance; no retry until a pass | Ronok's brief orders the genuine runs. The permission covers model invocation only and is never a human semantic or financial approval |
| Credit lifecycle source | The interface renders the five stages from `workflow.finance.stages[]` only | One server projection, no browser assembly of money |
| Browser tests | Throwaway listeners on ephemeral loopback ports are allowed in automated tests | They cannot collide with the fixed service ports |

## Independent result published during this push

The Codex evaluation lane published its first pass at [RESULTS](../evaluation-finish-20261109/RESULTS.md) (`b6e93bd`): twelve actual Opus calls returned and all twelve proposals failed validation; 0 of 4 intended positive contracts reached SHADOW; all six contracts were refused; all eight dispute cases stopped at setup, so held-out dispute accuracy is unmeasured. A separate public control completed one model reading of a denial and a linked local rebuttal. This push demonstrates the model path on authored contracts written inside the validated grammar. It does not change those scores and must not be presented as if it did.

## Integration and suites

The coordinator merges delivered branches and runs `uv run --locked pytest` once per merge, one run at a time. Branches that are ready together and share no files are merged in a single merge commit, so one run covers that merge. Every run is kept, including the failed ones.

| Commit | Contents | Full suite | Other checks | Receipt |
|:---|:---|:---|:---|:---|
| `02d86f7` | `main` `b6e93bd` plus role 2 at `5e913b2` | **2 failed, 5,308 passed**, 1 warning, 444.98 s | 104 JavaScript checks, graph, rehearsal, secret scan pass | [suite-02d86f7](../evidence/submission-20261109/suite-02d86f7.json) |
| `c756853` | plus role 2 fix `888d64f`, role 1 `43f5b9d`, role 3 `db9b680` | **1 failed, 5,366 passed**, 1 warning, 380.78 s | 109 JavaScript checks, graph, rehearsal, secret scan pass | [suite-c756853](../evidence/submission-20261109/suite-c756853.json) |
| `6c83947` | plus probe update `0be2955`, role 2 job view `8cc4f6f`, role 4 `c3a6dc5` | **5,378 passed**, 1 warning, 378.23 s | 114 JavaScript checks, graph, rehearsal, secret scan pass | [suite-6c83947](../evidence/submission-20261109/suite-6c83947.json) |
| `96615d8` | plus role 2 `c612114` (step-history column for older recorded workspaces) | First run **aborted with no result**: it stopped advancing in a browser launch. Second run **5,379 passed**, 1 warning, 362.85 s | Second run: 114 JavaScript checks, graph, rehearsal, secret scan pass | [aborted](../evidence/submission-20261109/suite-96615d8-aborted.json) · [run 2](../evidence/submission-20261109/suite-96615d8-run2.json) |
| `ff7977c` | plus role 3 `a15d987` (verified Ramp excerpt rebuilt from the 22:00 UTC read; plain-word read states) | **5,386 passed**, 1 warning, 361.23 s | 115 JavaScript checks, graph, rehearsal, secret scan pass | [suite-ff7977c](../evidence/submission-20261109/suite-ff7977c.json) |
| `0fe20b4` | plus role 4 `23df7ac` (claim stage beside credit stage, collapsed case records, link to Ramp records) | **5,388 passed**, 1 warning, 350.37 s | 118 JavaScript checks, graph, rehearsal, secret scan pass | [suite-0fe20b4](../evidence/submission-20261109/suite-0fe20b4.json) |
| `6b93e31` | plus role 4 `7ca68b2` (request details behind a disclosure). **All application changes of roles 1–4.** | **5,390 passed**, 1 warning, 370.01 s | 118 JavaScript checks, graph, rehearsal, secret scan pass | [suite-6b93e31](../evidence/submission-20261109/suite-6b93e31.json) |
| `52f1a2f` | plus role 6 `fad6173` (README, judge guide, storyboard). **Frozen fallback build.** | **5,390 passed**, 1 warning, 374.19 s | 118 JavaScript checks, graph, rehearsal, secret scan pass | [suite-52f1a2f](../evidence/submission-20261109/suite-52f1a2f.json) |
| `e10067f` | plus role 6 `c44c4e5` (measured timing, filming checklist, fallback screenshots) and role 5 `8b8132c` (acceptance report). Records only; no application source, test or script changed. | **5,390 passed**, 1 warning, 374.69 s | 118 JavaScript checks, graph, rehearsal, secret scan pass | [suite-e10067f](../evidence/submission-20261109/suite-e10067f.json) |
| `8aa8df4` | plus the acceptance follow-ups: role 6 `2bf3754`, role 2 `4b98717`, role 1 `088da4a`. Documentation and evidence only. | **5,390 passed**, 1 warning, 372.43 s | 118 JavaScript checks, graph, rehearsal, secret scan pass | [suite-8aa8df4](../evidence/submission-20261109/suite-8aa8df4.json) |

What the failures were:

- **Restart probe (both failed runs).** `tests/test_release_probes_gent8.py::test_hard_kill_mid_flow_preserves_state_idempotency_and_final_ledger` failed with `assert (0 + 4) == 11`. Role 2 made routine automation the default for workspaces created by the setup command, so the probe's four reviewer actions finished the walkthrough. The product state was correct. The probe's owner kept it on the eleven-step path with `--step-by-step`, with every assertion unchanged, and added a real-process kill for the automated default.
- **Browser test (first run only).** A Playwright test failed when Google Chrome auto-updated during the run and closed the launched browser. It passed alone on the same commit and in both later runs.

- **Hung run (`96615d8`, first run).** The log stopped growing nine seconds in, inside a browser launch. The coordinator aborted it after almost seven minutes, kept the log and reran it: 5,379 passed. Two Chrome versions were installed at the time, mid-update; the cause is not proven. The runner now aborts any run whose log stops growing for 300 seconds.

Not merged into this branch: the interface redesign (`work/submission-design-20261109`) and the side panel (`work/sidepanel-server-20261109`). Each merges only after its own full run.

## What this push changed, and its limits

- **Clicks.** The walkthrough's eleven clicks are four reviewer decisions: approve claim, approve response, post to Local ledger, apply credit. Seven steps run on the server under an existing approval or a signed source event, each with its authority recorded. No approval gate was removed or combined. A standing policy for the follow-up approval is a written proposal only.
- **Model on screen.** Six genuine `claude-opus-5-5` calls on three authored contracts, none repeated: one of two intended positives reached SHADOW with eleven exact quotations, the other was refused for vendor naming, and the control was refused. One genuine call read an authored unclear vendor reply and the case went to human review with nothing awarded. Both recorded runs are preserved and shown from copies. Nothing was approved or activated by a model or on a person's behalf.
- **Ramp.** A saved verified record of the sandbox bill that carries the person-posted note is shown beside the earlier worklist, with read time, completeness and the exact Ramp link. The capture sanitizer now keeps vendor names and invoice numbers, as the brief's task asks; other private fields are still stripped. Nothing from Uptime has been written to Ramp.
- **Limits.** Correct denial is covered only by automated tests; no served workspace shows it. Vendor names show as not captured until a person runs a read-only capture. An Uptime-origin Ramp comment needs a current signed native release, which does not exist. Advanced screens under "More tools" show the seeded data's own labels. Independent scores are unchanged: 0 of 4 intended positives in the latest pass.

## Frozen fallback build

`52f1a2f` is the frozen fallback for the submission: application commit `6b93e31` plus the README, judge guide and storyboard. `uv run --locked pytest`: **5,390 passed, 1 warning in 374.19 s**; 118 JavaScript checks; graph, rehearsal and secret scan pass ([receipt](../evidence/submission-20261109/suite-52f1a2f.json)). Independent acceptance runs against this commit. The interface redesign and the side panel are separate branches; each merges only after its own full run, and if either does not land, this build stands.

### Independent acceptance of the frozen build

Role 5 ran its acceptance on a fresh clone of `52f1a2f`, following only the published instructions, against expectations it had sealed by digest before it saw the build ([report](acceptance.md), `8b8132c`).

- **Passed:** the fresh clone reaches sign-in and four reviewer decisions with seven automatic steps between them; the money, 58 of 58 citations and the authority recorded for each step match the sealed expectations; the model receipts and job records are genuine.
- **Safety:** no unsafe acceptance, invented evidence or unauthorized money movement was observed. Duplicate, replay, restart, timeout and foreign-bill controls were met.
- **Limits it requires us to state:** the model work is recorded, not live; generalization is not shown (0 of 4 in the independent cohort); a correct denial with a genuinely late filing cannot be driven through the HTTP routes, so a maintenance-with-notice case over real HTTP stood in for it; missing-evidence recognition is narrow; nothing reaches Ramp from Uptime.
- **Not assessed:** the redesign, the side panel, and the recorded workspaces' interface.

| Finding | Owner | State |
|:---|:---|:---|
| P2. A differently worded evidence request is not recognized; it goes safely to a reviewer | Role 6 for the wording; recognition itself is unchanged in this push | README, judge guide and narration corrected at `2bf3754` |
| P2. A constructed $40 "Scenario only" row sits beside the verified Ramp bill | Interface owner | Open on the redesign branch; kept out of frame in the fallback film |
| P3. February reads "Ineligible" with credit "Not determined" | Interface owner | Open on the redesign branch |
| P3. README said "one call per case"; it was one call per rule family | Role 6 | Corrected at `2bf3754` |
| P3. The denial receipt omits its source commit and transport fields | Role 2 | Addendum at `4b98717`; fields never captured are marked as not captured |

## Status log

- **13:05 PST.** Baseline and classification recorded. Integration worktree created from `55ea607`. Roles 1–4 briefed. Role 5 follows the freeze; role 6 follows the judge session's drafts.
- **13:08 PST.** Role 5 briefed for pre-registration only (phase A); execution waits for the frozen commit. The judge session was asked where its two drafts live.
- **13:10 PST. Disk incident.** Free space fell from 3.4 GiB to about 0.8 GiB in under ten minutes. Cause: a Google Chrome auto-update writing about 1.5 GB of patch files to the user temp directory. The coordinator paused the updater's two processes (`kill -STOP 37425 37494`, resumable with `kill -CONT`); nothing was deleted. Free space then held near 1.0 GiB. Specialists were told to skip tests under 1.5 GiB free and to download or clone nothing. Virtual environments are copy-on-write clones and cost no space. Clearing the updater's temp files, old pytest temp trees or the uv cache is Ronok's decision. No full suite runs until space is back.
- **13:13 PST.** All five first deliverables are pushed: `onboarding.md` (`3bc648a`, plus the guide abstention fix `72b65f6` and job receipts `611efdf`), `disputes.md` (`67fbc44`), `ramp.md` (`e8bd7dc`), `ui.md` (`0fd732c`), `acceptance.md` (`60a7ea6`, sealed expectations committed by digest). Role 2 confirms eleven clicks become four person decisions with no gate removed or combined; a standing policy for the follow-up approval is written up as a proposal only. Interface notes forwarded to role 4.
- **13:19 PST.** `origin/main` moved to `b6e93bd` (records and progress data only). The Codex lanes closed their pass and listed queued generalization work in [NEXT-WORKSTREAMS](../NEXT-WORKSTREAMS-20261109.md); that work is not part of this push. Ronok confirmed that the Codex root did not receive this brief and that this session is the only coordinator. Role 6 assigned to `agent0`; the judge session's drafts were copied out of its scratchpad to private task storage. Free disk back to about 1.9 GiB with the updater still paused.
- **13:21 PST.** Free disk is 17 GiB. The coordinator resumed the paused Chrome updater (`kill -CONT`), so nothing it paused is left stopped and nothing was deleted. The test hold is lifted; the check-before-running rule (skip under 1.5 GiB free) stays.
- **13:55 PST.** Roles 1–4 are integrated and verified. See "Integration and suites" below. Ronok confirmed at about 13:42 PST that the existing sessions keep these roles through the freeze; he had intended the roles for new agents, and the coordinator had assigned them to existing sessions without asking first.
- **15:02 PST.** The last role 4 change is merged and the application commit `6b93e31` passes: 5,390 passed, 118 JavaScript checks ([suite-6b93e31](../evidence/submission-20261109/suite-6b93e31.json)). Earlier runs on `0fe20b4` (5,388), `ff7977c` (5,386) and `96615d8` (5,379 on its second run; the first hung in a browser launch and was aborted) are recorded beside it. A side-panel server option is on `work/sidepanel-server-20261109`, unmerged, as a follow-on Ronok asked for after the freeze.
- **15:14 PST. New interface owner.** Ronok tried the integrated build himself, found the Agreements page unreadable, and asked for a new agent to redesign the interface (a Stripe-inspired look, a clearer layout, checked continuously against rendered pages). That agent is the session "Uptime UI redesign (Stripe-inspired)" (`claude-fable-5-2`, max), on `work/submission-design-20261109` from `968c12b`. It is now the only writer in `web/` and the browser tests; `gent7` was told to stop and hand over notes. The redesign is presentation only and merges after its own full suite. The application commit `6b93e31` (5,390 passed) remains the verified fallback.
- **15:24 PST.** Fallback build frozen at `52f1a2f` (5,390 passed). Role 5 starts its acceptance run on it; role 6 times the script and takes a fallback set of screenshots.
- **15:39 PST. Side-panel extension.** `extension/` is on `work/sidepanel-server-20261109` (`3fe6ccd`): a Chrome side panel that frames the real app and follows the Ramp bill open in the active tab. It was loaded into a throwaway Chrome profile and checked against a served workspace; Ramp's site was not contacted. See [the decision record](../decisions/ADR-20261109-side-panel-framing.md) on that branch. Loading it into his own browser is Ronok's step.
- **15:41 PST.** Role 6's measured timing, filming checklist and fallback screenshots (`c44c4e5`) and role 5's acceptance report (`8b8132c`) merged as `e10067f`, records only. Full run at 15:48 PST: 5,390 passed ([suite-e10067f](../evidence/submission-20261109/suite-e10067f.json)). The frozen fallback is still `52f1a2f`.
- **15:50 PST. Side-panel setup option.** Role 2 added `--side-panel-origin` to the walkthrough setup command (`8728fb9`, output order fixed at `da6a090`). The coordinator read the patch and ran the two side-panel test files on the combined branch: 38 passed, plus 4 JavaScript checks. The option is validated before anything is written and is never stored in the workspace. Still to come before that branch can merge: the bill page in the interface, a check inside the real extension, and its own full run.
- **15:51 PST. Acceptance follow-ups and a custody correction.** Role 6 corrected the wording acceptance found (`2bf3754`); role 2 added the receipt addendum (`4b98717`). Separately, the coordinator had noticed that the preserved contract-reading database no longer matched its recorded hash. Role 1 traced it: the preserved folder was served once at 13:31 PST, which changed two SQLite header bytes and no record. It was restored from the untouched original at 15:42 PST, the runbook now forbids serving the preserved folder, and the record of what happened is kept (`088da4a`). The coordinator verified both preserved databases by hash afterwards (`9043eaaf…` and `1a035ab2…`).
- **15:58 PST.** The three acceptance follow-ups merged as `8aa8df4`; full run: 5,390 passed ([suite-8aa8df4](../evidence/submission-20261109/suite-8aa8df4.json)). The application is still the frozen build's; outside `docs/` only `README.md` differs from `52f1a2f`.
- **15:58 PST. Opus 5.5 criticism of the side panel.** A separate read-only session, which named its model as `claude-opus-5-5`, reviewed the framing option, the extension and the setup option. It found no way for a framing page to act or to read the framed page, and no change for a server started without the option. Its findings were smaller: the extension's JavaScript checks did not run inside pytest, the rollback steps were incomplete, the extension README overstated the bill page, enrollment skipped the option's check, and tab lookups could finish out of order. All five are fixed on `work/sidepanel-server-20261109` at `f47c4de` (50 focused checks and 5 JavaScript checks pass). Two points about the setup command went to role 2. It also noticed an existing gap, unchanged here: responses that return before the header middleware carry no security headers. The decision record on that branch has the full list and dispositions.
- **15:58 PST. The repository is public.** GitHub reports it as public and an anonymous request reads `main` and the frozen branch. Every branch pushed in this work is therefore readable by anyone; the secret scan passes on each run, and the Ramp excerpt holds sandbox identifiers only, with no names or addresses. Two consequences are open: the acceptance report calls the repository private (role 5 is asked to recheck the README's own clone command), and `main` is still `b6e93bd`, so a judge who clones the default branch does not get this work. Moving `main` is Ronok's decision.
- **15:58 PST. A second film effort exists.** The judge session started a session titled "Produce the 90-second Uptime walkthrough video" at 15:34 PST. The coordinator did not start it and does not direct it. It was sent the frozen build, the storyboard's location, the redesign in progress, the port map and the statements any film must keep, and asked what it captures and where its output goes. No answer yet.
- **16:04 PST. Handoff written.** [HANDOFF.md](HANDOFF.md) states the current position against the brief's final list. The create and resume commands were run by hand at `0b19b4d`. Rerunning the README's command on an existing folder is correctly refused but prints a stack trace; role 2 was asked for a one-line message. GitHub's check workflow passes on the verified build `52f1a2f` (run 42720204760) and on `e1db0c7`. The redesign session pushed its first part at `943151f` (visual system, shell, sign-in, Overview); the coordinator looked at rendered pages from its working files at 1440 and 420 pixels wide and saw no defect to raise. The Agreements page is not yet redone.
