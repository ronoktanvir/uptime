# Submission-readiness handoff

Written by the coordinator on November 9, 2026, at 16:05 PST, and last updated at 21:23 PST. It says what is true now, what is published, what was measured, and what still needs a person. Every time and decision behind it is in [the coordination record](COORDINATION.md).

## Where it stands

- **`main` holds the whole push**: the accepted build, the redesigned interface and the Chrome side panel. A full run passes on that commit (5,452 passed), and the side panel was checked inside the real extension.
- **Independent acceptance covers the build before the redesign.** That build is `52f1a2f`, kept on the branch `frozen/submission-fallback-20261109`. Its full run passes on this machine (5,390 passed) and in GitHub's check workflow ([run 42720204760](https://github.com/ronoktanvir/uptime/actions/runs/42720204760)), and a separate session accepted it from a fresh clone, with the limits listed below. The redesign changed the interface only, but acceptance has not yet looked at it.
- **How `main` got there.** At 16:31 PST Ronok asked for GitHub to be brought up to date for other people. `main` was fast-forwarded from `b6e93bd` three times, never forced: at 16:42 to the accepted build with its records, at 17:03 with the setup refusals, and at about 17:33 with the redesign and the side panel. The repository is public. After the first two moves an anonymous clone was checked: it showed the rebuilt README and served the walkthrough with the README's own command.
- **Nothing from Uptime has been written to Ramp**, and no real vendor was contacted.

## Decisions that are Ronok's

In the order they block the submission.

| # | Decision | What it turns on | State |
|:--|:---|:---|:---|
| 1 | Move `main` to the verified build | Judges clone the default branch. Independent acceptance ranked this first of its findings ([P1-A](acceptance.md)) | **Done** on his instruction, by fast-forward only: 16:42, 17:03 and about 17:33 PST |
| 2 | Which film is the submission film | Role 6 wrote a measured two-minute storyboard and a filming checklist for a spoken film. Separately, a session started by the judge session produced a silent, captioned 89-second cut in `~/uptime-demo/video-01/`, outside the repository; Ronok chose captions over a voice there | **Partly decided, about 17:50 PST:** the film opens on the real Ramp bill with the side panel beside it, then shows the Northwind case as a separate story. Role 6 is re-cutting the storyboard for it. Still open: a spoken film, the silent captioned cut, or both. Both existing versions were made before the redesign |
| 3 | Film on the redesigned build, or on the accepted one | The [filming checklist](presentation.md#filming-checklist-for-ronok) was written for `52f1a2f` and still works on a checkout of it. On `main` several controls have moved or been renamed, and role 6 has not yet rewritten the checklist | Open |
| 4 | Record the voiceover and the film; choose cut A or B after a timed read | Only a person can | Not done |
| 5 | Ease the load on this Mac, or restart it | Five of the coordinator's full runs have stalled in a browser launch, and one of the redesign session's. Two were captured: a freshly launched Chrome sat with its main thread blocked inside a macOS system service, so it never answered the test. Swap was almost full, and in both captures another session had launched Chrome within seconds. The earlier guess, Chrome's pending update, was never shown. Fewer sessions driving Chrome at once, or a restart, is the likely cure | Not done; his call |
| 6 | Load the side-panel extension into his own browser | `chrome://extensions` → Developer mode → Load unpacked. No script does this for him. A copy set to port 8806 is in `~/uptime-demo/side-panel-extension`, with a workspace serving on that port. The steps are under "Start, resume, reset" | Ready for him. The toolbar button opening Chrome's own side panel is the one step no agent could test |
| 7 | Whether a person approves a model candidate on camera | The walkthrough's reviewer is a scripted test account. A person's approval needs a person | Open; the film does not need it |
| 8 | D02: put an authored Northwind bill into the Ramp sandbox | It would show an authored finding beside a Ramp bill. Role 3 recommends against it | Not done; default keeps Northwind out of Ramp |
| 9 | D05 run 2 (sealed vendor evaluation) | Runs only on his go-ahead, in the evaluation session | Not part of this push |
| 10 | A standing policy for the follow-up approval | Would make "approve response" automatic in one narrow case. It combines an approval gate, so it is [a written proposal only](disputes.md) for team review | Not implemented |
| 11 | Clearing temporary files | Free disk fell to 0.8 GiB during a Chrome update and is now about 13 GiB. Old test folders and caches are his to clear | Open; nothing was deleted |

## What changed in this push

| Area | Before | Now | Owner |
|:---|:---|:---|:---|
| Walkthrough | Eleven clicks | Four reviewer decisions (approve the claim, approve the response, post the credit, apply it) and seven steps that run automatically under an approval already recorded or a signed source event. Each step records what authorised it. No approval gate was removed or combined | Role 2 |
| Model work on screen | Not visible in the product | A contract-reading job shows each proposed term beside its quoted sentence; a reply-reading job shows its cited text. Failed and timed-out jobs keep their receipts. A refusal names the passage that caused it | Roles 1, 2, 4 |
| Ramp | A November 5 worklist | A saved, verified record of the sandbox bill that carries the person-posted note, with read time, completeness and the Ramp link. Read-only | Role 3 |
| Sign-in | A credential file in a hidden folder | Setup ends by printing the credential file, the account and the address | Roles 2, 4 |
| Interface | 13 navigation items, a builder's console | 4 destinations, then a full redesign in one visual system: an Overview that leads with the outcome and the next decision, Agreements as plain cards (7,917 px tall before, 3,242 now), Cases as a list, Ramp records leading with the verified record alone, and forms and raw records closed until asked for | Role 4, then the redesign session |
| Beside Ramp | — | A Chrome side panel that shows Uptime's page for the Ramp bill open in the active tab. It is a browser side panel, not a Ramp integration: it reads only the tab's address, and nothing runs inside Ramp or is written to it. Off unless the server is started with one named extension origin | Coordinator, role 2, the redesign session |
| Documents | — | A rebuilt README, a [judge guide](../../JUDGES.md), a measured storyboard and a filming checklist | Role 6 |
| Acceptance | — | Expectations sealed by digest before the build existed, then checked on a fresh clone | Role 5 |

## Published commits

All on `github.com/ronoktanvir/uptime`. Nothing was force-pushed and no history was removed.

| Branch | Commit | What it is | Verified |
|:---|:---|:---|:---|
| `main` | The integration branch's head | The default branch: the accepted build, the setup refusals, the redesign, the side panel and the records. It was `b6e93bd` before this push | Full run passes on its last merge, `4c93a44` (5,452). Hosted checks passed on `main` at `11a6770`, `21eae2c`, `1fa4ab4` and `9bea5fb`, and on `15034f3` |
| `frozen/submission-fallback-20261109` | `52f1a2f` | The verified build | Full run and hosted checks pass; independently accepted |
| `work/submission-integration-20261109` | this file's branch | The same commit as `main`. Last merge `4c93a44`: the interface set in Inter, after `15034f3`, the film re-cut and the icons | Full run passes on `4c93a44`, `15034f3`, `e3dab64` and `1fa4ab4` (5,452 each) |
| `work/submission-design-20261109` | `f689e5d` | The redesign, then 21 Phosphor icons (MIT), the Inter typeface (SIL Open Font License) and a list of renamed controls; [notices](THIRD-PARTY-NOTICES.md) | Merged. Its owner had merged it onto `main` locally at Ronok's direct request; the coordinator read the change and every removed assertion, and looked at each page at 1440 and 420 pixels wide |
| `work/sidepanel-server-20261109` | `dc4ff65` | Side-panel option, extension, setup option and the real-browser check | Merged. Checked inside the real extension together with the redesign's bill page |
| `work/submission-onboarding-20261109` | `088da4a` | Role 1, contract reading | Merged |
| `work/submission-disputes-20261109` | `8addc5a` | Role 2, disputes, the walkthrough, the setup refusals and its test port change | Merged |
| `work/submission-ramp-20261109` | `a15d987` | Role 3, Ramp | Merged |
| `work/submission-ui-20261109` | `7ca68b2` | Role 4, interface before the redesign | Merged |
| `work/submission-acceptance-20261109` | `e60cd60` | Role 5, acceptance, with its dated correction | Merged |
| `work/submission-presentation-20261109` | `7f6e9ec` | Role 6: README, judge guide, the film re-cut for the Ramp opening, the filming checklist for `main`, three README screenshots | Merged |

## Test results

The required command is `uv run --locked pytest`, run once per merge, one run at a time. Every run is kept with its log, including the failed and aborted ones, in [the receipts folder](../evidence/submission-20261109/). The full table is in [the coordination record](COORDINATION.md#integration-and-suites).

| Commit | Result | Note |
|:---|:---|:---|
| `02d86f7` | 2 failed, 5,308 passed | A restart probe assumed eleven clicks; a browser test lost its browser when Chrome updated |
| `c756853` | 1 failed, 5,366 passed | The same probe, before its owner updated it |
| `6c83947` | 5,378 passed | |
| `96615d8` | Aborted, then 5,379 passed | The first run hung in a browser launch and was stopped with its log kept |
| `ff7977c`, `0fe20b4` | 5,386 and 5,388 passed | |
| `6b93e31` | 5,390 passed | All application changes of roles 1–4 |
| **`52f1a2f`** | **5,390 passed** | **The verified build.** 118 JavaScript checks, progress graph, rehearsal and secret scan also pass |
| `e10067f`, `8aa8df4` | 5,390 passed each | Records only |
| `6848390` | Aborted, then 5,390 passed | Records only. The first run stalled in a browser launch |
| `ea58f22` | Aborted twice | The setup refusals. Both runs stalled in a browser launch, at 90 and 38 percent, with every test before that point passing |
| `783d5ec` | 5,398 passed | The same merge plus the records of its stalled runs: 5,390 and 8 new setup-refusal tests |
| `3bbd47e` | Aborted, then 5,452 passed | The redesign and the side panel. Run on a local combination whose files are the same except two record files. 129 JavaScript checks |
| `1fa4ab4` | 5,452 passed | The same merge with its records, run on the commit itself |
| `e3dab64` | 5,452 passed | Role 2's test port change |
| `15034f3` | 5,452 passed | The film re-cut, its screenshots and the interface icons. The first attempt was cut off by a restart of the Mac before any test ran |
| `4c93a44` | 5,452 passed | The interface set in Inter. **This is what `main` holds** |

GitHub's check workflow runs the same command on a clean machine for every pushed commit. It passes on the accepted build, on every integration commit through `1fa4ab4` (the redesign and side-panel merge), on the redesign's commits through `c280283` and on the side-panel branch through `a162951`.

**Why runs stall.** The stalls are in this Mac, not in the tests. In both captured cases a freshly launched Chrome had no page process and its main thread was blocked inside a macOS system service, while another session had launched Chrome within seconds ([first record](../evidence/submission-20261109/suite-ea58f22-aborted2.json), [second](../evidence/submission-20261109/suite-8561fe3-aborted.json)). No test has failed in a stalled run.

These are regression results. They do not measure model accuracy, and they are not evidence of a person's approval or of any effect in Ramp.

## Evaluation results, kept separate

| What was measured | Result | Who measured it |
|:---|:---|:---|
| Unseen contracts, latest independent pass | 12 genuine Opus calls; all 12 proposals failed validation. 0 of 4 intended positives reached shadow. All 6 contracts were refused. All 8 dispute cases stopped at setup, so dispute accuracy is unmeasured ([results](../evaluation-finish-20261109/RESULTS.md)) | The Codex evaluation lane, on `main` |
| Earlier first attempts | 0 of 4, 3 of 6, 0 of 50, and a refused public SLA (Backblaze). Unchanged | Earlier lanes |
| Authored contracts in this push | 1 of 2 written inside the supported grammar reached shadow, with 11 exact quotations. The other and a control were refused | Role 1; verified from receipts by role 5 |
| The accepted build `52f1a2f`, from a fresh clone, before the redesign | Passed: the published steps work once that build is checked out; the money, 58 of 58 citations and each step's authority match the sealed expectations; no unsafe acceptance, invented evidence or unauthorised money movement ([report](acceptance.md)) | Role 5 |
| The redesigned interface | Not yet assessed independently. The coordinator's own look found the same figures and the same four decisions | — |

This push did not improve the unseen-contract result and must not be presented as if it did. Acceptance also found that a differently worded evidence request is not recognised (it goes safely to a reviewer), and that a correct denial with a genuinely late filing cannot be driven through the product's routes.

## Model work

**In the product, all recorded on November 9, none live:**
- Six `claude-opus-5-5` calls read three authored contracts, one call per rule family and none retried.
- One `claude-opus-5-5` call read an authored unclear vendor reply. It was read as ambiguous, the case went to a reviewer, and nothing was awarded.
- Each call ran with no tools, after an operator recorded permission for that exact request. The operator was the engineering agent, named as such; no approval names Ronok. A model's output is a proposal only.
- Northwind's own contract and its vendor's log request use fixed rules, with no model call.

**In the engineering:**
- The six role sessions report `claude-opus-5-5`. The coordinator, the redesign session and the video session report `claude-fable-5-2`.
- One separate `claude-opus-5-5` session criticised the side-panel decision. Its findings and what was done about each are in that branch's decision record.
- These are the sessions' own model names as the app reports them, not provider receipts.

## What reached Ramp

- **One note**, on sandbox bill `f74ba12c-95d0-582d-9f62-26d8057d1d37`, posted by a person in Ramp on November 8 (UTC). Uptime read it back through the API on November 9 at 22:00 UTC, in a read Ronok started himself.
- **Nothing written by Uptime.** No comment, hold, credit or approval. An agent-run posting action was refused by an automatic approval review of the agent's action; it was not retried or routed around.
- An Uptime-origin comment would need a current signed native release, which does not exist.
- The walkthrough's credit is in a local ledger. It is not money recovered in Ramp, and Northwind's agreement is not attached to the DocuSign bill.

## Start, resume, reset

Create, the refusal of an existing folder and resume were run by hand from an anonymous clone of `main` at `21eae2c`; the other options are exercised by the test suite. Use a checkout of `main`.

```bash
uv run --locked python scripts/setup_northwind.py --directory "$HOME/uptime-demo/northwind-01" --serve
```

It builds a fresh walkthrough workspace, prints the credential file, the account (`scripted-test-reviewer`) and the address, and serves at `http://127.0.0.1:8776`.

| To | Do |
|:---|:---|
| Stop | Ctrl-C |
| Resume the same workspace | The same command with `--resume` added |
| Start over | The same command with a new folder name. A workspace is never overwritten. Running it again on an existing folder without `--resume` is refused with one plain line that says what to do |
| Use another port | Add `--origin http://127.0.0.1:PORT` when creating |
| See all eleven steps one by one | Add `--step-by-step` when creating |
| See the unclear-reply branch | Add `--counterparty-reply unclear` when creating |
| Film | [The filming checklist](presentation.md#filming-checklist-for-ronok) gives three terminals, five tabs and a fresh folder per take. It was written for the build before the redesign |
| Use the side panel beside Ramp | Start with the framing option added: `--side-panel-origin chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl --serve`. In Chrome open `chrome://extensions`, turn on Developer mode, choose Load unpacked and pick `extension/`; its ID should read `kibophanbmnepbmhpampfagpjfhjfcnl`. Open a bill in Ramp's demo, click the Uptime toolbar button and sign in inside the panel. If the workspace is not on port 8776, change `origin` in `extension/config.js`. [More](../../../extension/README.md) |
| Run the checks | `uv run --locked pytest`, then `node --test web/*.test.cjs tests/helpers/*.test.cjs` |

The two recorded model workspaces are preserved outside Git. Serve only a copy of each, never the preserved folder: serving changes the database file. The steps are in [the onboarding runbook](onboarding-runbook.md#preserved-recorded-workspace-for-the-film) and [the disputes handoff](disputes.md).

## Open work and blockers

| Item | Owner | State |
|:---|:---|:---|
| Setup command: its real-process tests took a port from 8821–8829 and skipped if all were taken | Role 2 | **Done** (`8addc5a`): they take a port the system assigns. Requested at 17:50 PST. The plain refusals and the `--serve` rule are done |
| Interface-only acceptance check of the redesign and the side panel's default | Role 5 | Requested at 17:50 PST |
| Retake the README's three screenshots (taken before the icons and the typeface), add a README link to the third-party notices, the video link | Role 6 | Not yet requested: waiting for the look to stop changing. The storyboard re-cut, the filming checklist for `main`, the timing recheck and the README's side-panel paragraph are **done** (`7f6e9ec`). First requested at 17:50 PST. The README's and the judge guide's wording still matches the redesigned interface's labels |
| Say how the requested log arrives | Role 6 | The narration and the README's third step say Uptime "attaches" and "verifies" the log. In the walkthrough the log and its verification record arrive as authored events through the signed intake, and Uptime matches them. The product's step names say attach and verify; its authority line says received. Requested with the item above |
| Evidence requests are recognised only in wording the rules know | Disputes owner | Not changed in this push; the wording that overstated it is corrected |
| A case's own claim record sends "0.00" for posted and applied, which it does not track (`uptime/correspondence.py:822`) | Role 2 | Found by the redesign session. The redesigned case page does not show those two figures; the record should send no value instead of a zero. Role 2 is assessing every consumer before any change |
| Re-shoot the 90-second cut on the redesigned build | The video session | Told at 17:50 PST to wait for role 6's storyboard. Its command is `./remake.sh <commit>` in `~/uptime-demo/video-01/`; its selectors need editing first. The Ramp opening is footage only Ronok can record |
| Unseen contracts: 0 of 4 | The Codex lanes ([queued work](../NEXT-WORKSTREAMS-20261109.md)) | Outside this push |
| Responses that return before the header middleware carry no security headers | Application owners | Existing gap, found in review; not changed |
| Any write to Ramp by Uptime | Ronok and the team | Needs a signed native release |
| Nine other branches on GitHub hold commits that are not on `main` | Their owners | Left as they are; see below |

## Branches left as they are

Ronok asked for whatever needs merging to be merged. These nine branches hold commits that are not on `main`, and the coordinator did not merge them, because none is this push's work to merge.

| Branch | What it holds | Why it stays |
|:---|:---|:---|
| `work/evaluation-finish-20261109`, `work/disputes-finish-20261109` | The Codex lanes' later commits, including changes to contract-term code | Their owners closed their pass at `b6e93bd` and queued this work in [NEXT-WORKSTREAMS](../NEXT-WORKSTREAMS-20261109.md). It changes application behaviour and has not been through acceptance |
| `work/release-evaluation-gent8`, `work/dispute-evaluation-86-run`, `work/independent-corpus-84`, `work/d05-run-gent8`, `work/d05-second-gent8` | Evaluation records, frozen runners and a sealed vendor selection | Kept apart from the build on purpose, so implementers do not work beside the expected outcomes. `d05-second` waits for Ronok's go-ahead |
| `work/ramp-identity-d03a-prep` | An earlier preparation of a change that reached `main` by another route | Superseded |
| `work/finance-guide-90` | A commit and its revert | Nothing to merge |

## If the coordinator's session ends

- **State lives in Git.** This file, the coordination record and the receipts are on `work/submission-integration-20261109`. Each role's handoff is beside this file.
- **Messages between sessions pause** after ten sent without a new message from Ronok in the coordinator's session. A message he sends while a turn is running does not lift the pause; his next one after the turn ends does. Anything waiting to be sent is listed at the end of the coordination record's log.
- **To merge a finished branch:** merge it into the integration branch with `--no-ff`, run `uv run --locked pytest` once on the merge commit, then the JavaScript checks, `node scripts/test_progress_graph.cjs`, `scripts/rehearse.py` and `scripts/check_repo.py`. Write a receipt beside the others with the exact commit, command, result and log. Push only after it passes. If a run stops advancing for five minutes, abort it, keep the log and run it again.
- **Order from here:** role 5's interface check and role 6's screenshots and checklist on the redesigned build; then the small fixes waiting with role 2. After each verified merge, fast-forward `main` to it: `git push origin <verified commit>:refs/heads/main`. Never force.
- **Rules that do not relax:** no force-push; no write to Ramp and no retry of the refused posting action; no real vendor contact; no credential, private evaluation answer or customer capture in Git; every changed existing test recorded by exact name and reason; the scripted reviewer is never described as a person; a local credit is never described as money in Ramp.
