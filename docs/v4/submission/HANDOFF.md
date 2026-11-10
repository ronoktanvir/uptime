# Submission-readiness handoff

Written by the coordinator on November 9, 2026, at 16:05 PST, and updated as the two open branches land. It says what is true now, what is published, what was measured, and what still needs a person. Every time and decision behind it is in [the coordination record](COORDINATION.md).

## Where it stands

- **A verified build exists and has been independently accepted.** It is `52f1a2f`, on the branch `frozen/submission-fallback-20261109`. Its full run passes on this machine (5,390 passed) and in GitHub's check workflow ([run 42720204760](https://github.com/ronoktanvir/uptime/actions/runs/42720204760)). A separate session then accepted it from a fresh clone, with the limits listed below.
- **The default branch does not have it.** `main` is still `b6e93bd`. The repository is public, so anyone who clones it today and follows the README runs `main`'s older build. Moving `main` is Ronok's decision. It would be a fast-forward, with no rewrite of history.
- **Two things are still being built.** The interface redesign Ronok asked for and the Chrome side panel are each on their own branch. Each merges only after its own full run. If either does not land, the verified build stands.
- **Nothing from Uptime has been written to Ramp**, and no real vendor was contacted.

## Decisions that are Ronok's

In the order they block the submission.

| # | Decision | What it turns on | State |
|:--|:---|:---|:---|
| 1 | Move `main` to the verified build | Judges clone the default branch. Until `main` moves they do not see this work. Independent acceptance ranks this first of its findings ([P1-A](acceptance.md)) | Not done. A fast-forward from `b6e93bd`; the coordinator pushes it only on Ronok's word |
| 2 | Which film is the submission film | Role 6 wrote a measured two-minute storyboard and a filming checklist. Separately, the judge session started a "90-second walkthrough video" session at 15:34 PST, which the coordinator did not start | Open. The two must not contradict each other |
| 3 | Film now on the verified build, or wait for the redesign | The [filming checklist](presentation.md#filming-checklist-for-ronok) works today on `52f1a2f`. The redesign changes every screen | Open |
| 4 | Record the voiceover and the film; choose cut A or B after a timed read | Only a person can | Not done |
| 5 | Relaunch Chrome | Two Chrome versions were installed mid-update. One full run hung in a browser launch and was aborted, and role 4 saw the same hang twice in focused runs. The cause is not proven; a relaunch is the cheap test | Not done |
| 6 | Load the side-panel extension into his own browser | `chrome://extensions` → Developer mode → Load unpacked → `extension/`. No script does this for him | Waits for the side panel to land |
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
| Interface | 13 navigation items, a builder's console | 4 navigation items and a shorter Overview. A full redesign is in progress on its own branch | Role 4, then the redesign session |
| Documents | — | A rebuilt README, a [judge guide](../../JUDGES.md), a measured storyboard and a filming checklist | Role 6 |
| Acceptance | — | Expectations sealed by digest before the build existed, then checked on a fresh clone | Role 5 |

## Published commits

All on `github.com/ronoktanvir/uptime`. Nothing was force-pushed and no history was removed.

| Branch | Commit | What it is | Verified |
|:---|:---|:---|:---|
| `main` | `b6e93bd` | The default branch, unchanged by this push | By its owners |
| `frozen/submission-fallback-20261109` | `52f1a2f` | The verified build | Full run and hosted checks pass; independently accepted |
| `work/submission-integration-20261109` | this file's branch | The verified build plus records. Last merge `6848390` | Full run passes on `6848390` (second run); outside `docs/` only `README.md` differs from `52f1a2f` |
| `work/submission-design-20261109` | `943151f` so far | The redesign: visual system, shell, sign-in and Overview. Other pages still to come | Not merged; no full run yet |
| `work/sidepanel-server-20261109` | `f47c4de` | Side-panel option, extension and setup option | Focused checks only (50 Python, 5 JavaScript); not merged |
| `work/submission-onboarding-20261109` | `088da4a` | Role 1, contract reading | Merged |
| `work/submission-disputes-20261109` | `4b98717` | Role 2, disputes and the walkthrough | Merged |
| `work/submission-ramp-20261109` | `a15d987` | Role 3, Ramp | Merged |
| `work/submission-ui-20261109` | `7ca68b2` | Role 4, interface before the redesign | Merged |
| `work/submission-acceptance-20261109` | `e60cd60` | Role 5, acceptance, with its dated correction | Merged |
| `work/submission-presentation-20261109` | `2bf3754` | Role 6, README, judge guide, film | Merged |

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

These are regression results. They do not measure model accuracy, and they are not evidence of a person's approval or of any effect in Ramp.

## Evaluation results, kept separate

| What was measured | Result | Who measured it |
|:---|:---|:---|
| Unseen contracts, latest independent pass | 12 genuine Opus calls; all 12 proposals failed validation. 0 of 4 intended positives reached shadow. All 6 contracts were refused. All 8 dispute cases stopped at setup, so dispute accuracy is unmeasured ([results](../evaluation-finish-20261109/RESULTS.md)) | The Codex evaluation lane, on `main` |
| Earlier first attempts | 0 of 4, 3 of 6, 0 of 50, and a refused public SLA (Backblaze). Unchanged | Earlier lanes |
| Authored contracts in this push | 1 of 2 written inside the supported grammar reached shadow, with 11 exact quotations. The other and a control were refused | Role 1; verified from receipts by role 5 |
| The verified build, from a fresh clone | Passed: the published steps work; the money, 58 of 58 citations and each step's authority match the sealed expectations; no unsafe acceptance, invented evidence or unauthorised money movement ([report](acceptance.md)) | Role 5 |

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

Create, resume and the refusal of an existing folder were run by hand on the integration branch at `0b19b4d`; the other options are exercised by the test suite. Use a checkout of the verified build or later.

```bash
uv run --locked python scripts/setup_northwind.py --directory "$HOME/uptime-demo/northwind-01" --serve
```

It builds a fresh walkthrough workspace, prints the credential file, the account (`scripted-test-reviewer`) and the address, and serves at `http://127.0.0.1:8776`.

| To | Do |
|:---|:---|
| Stop | Ctrl-C |
| Resume the same workspace | The same command with `--resume` added |
| Start over | The same command with a new folder name. A workspace is never overwritten. Running it again on an existing folder without `--resume` is refused; today that refusal prints a stack trace ending in the reason, and role 2 has been asked for a one-line message |
| Use another port | Add `--origin http://127.0.0.1:PORT` when creating |
| See all eleven steps one by one | Add `--step-by-step` when creating |
| See the unclear-reply branch | Add `--counterparty-reply unclear` when creating |
| Film | Follow [the filming checklist](presentation.md#filming-checklist-for-ronok): three terminals, five tabs, a fresh folder per take |
| Run the checks | `uv run --locked pytest`, then `node --test web/*.test.cjs tests/helpers/*.test.cjs` |

The two recorded model workspaces are preserved outside Git. Serve only a copy of each, never the preserved folder: serving changes the database file. The steps are in [the onboarding runbook](onboarding-runbook.md#preserved-recorded-workspace-for-the-film) and [the disputes handoff](disputes.md).

## Open work and blockers

| Item | Owner | State |
|:---|:---|:---|
| Interface redesign, including the Agreements page, the Ramp bill page for the side panel, and two acceptance findings (the "$40 · Scenario only" row beside the verified bill; February's credit cell) | The redesign session | In progress. First part pushed at `943151f` |
| Side panel: check inside the real extension, full run, merge | Coordinator | Waits for the bill page |
| Setup command: a plain message instead of a stack trace on a rerun; the side-panel option without `--serve`; one untested path | Role 2 | Requested |
| Interface-only acceptance check of the redesign | Role 5 | Waits for the redesign to merge |
| Final README screenshots, timing recheck, video link | Role 6 | Waits for the redesign |
| Evidence requests are recognised only in wording the rules know | Disputes owner | Not changed in this push; the wording that overstated it is corrected |
| Unseen contracts: 0 of 4 | The Codex lanes ([queued work](../NEXT-WORKSTREAMS-20261109.md)) | Outside this push |
| Responses that return before the header middleware carry no security headers | Application owners | Existing gap, found in review; not changed |
| Any write to Ramp by Uptime | Ronok and the team | Needs a signed native release |

## If the coordinator's session ends

- **State lives in Git.** This file, the coordination record and the receipts are on `work/submission-integration-20261109`. Each role's handoff is beside this file.
- **Messages between sessions pause** after ten sent without a message from Ronok in the coordinator's session, and resume when he types there. Anything waiting to be sent is listed at the end of the coordination record's log.
- **To merge a finished branch:** merge it into the integration branch with `--no-ff`, run `uv run --locked pytest` once on the merge commit, then the JavaScript checks, `node scripts/test_progress_graph.cjs`, `scripts/rehearse.py` and `scripts/check_repo.py`. Write a receipt beside the others with the exact commit, command, result and log. Push only after it passes. If a run stops advancing for five minutes, abort it, keep the log and run it again.
- **Order:** the setup fixes, then the redesign (followed by role 5's interface check and role 6's screenshots), then the side panel.
- **Rules that do not relax:** no force-push; no write to Ramp and no retry of the refused posting action; no real vendor contact; no credential, private evaluation answer or customer capture in Git; every changed existing test recorded by exact name and reason; the scripted reviewer is never described as a person; a local credit is never described as money in Ramp.
