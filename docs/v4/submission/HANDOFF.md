# Submission-readiness handoff

Written by the coordinator on November 9, 2026, at 16:05 PST, and last updated on November 10 at 02:31 PST. It says what is true now, what is published, what was measured, and what still needs a person. Every time and decision behind it is in [the coordination record](COORDINATION.md).

## Where it stands

- **`main` holds the whole push**: the accepted build, the redesigned interface and the Chrome side panel. A full run passes on that commit (5,464 passed, none skipped), and the side panel was checked inside the real extension. The interface is set in three bundled typefaces (Inter, Source Serif 4 for quoted source text, JetBrains Mono for references), each checked against its upstream file.
- **Independent acceptance covers both builds.** It first accepted `52f1a2f`, the build before the redesign, kept on the branch `frozen/submission-fallback-20261109` (5,390 passed here and in GitHub's check workflow, [run 42720204760](https://github.com/ronoktanvir/uptime/actions/runs/42720204760)). It then checked the redesigned interface on `main` at `08852a6`, from an anonymous default clone with no extra step: the same figures, citations and step authorities, with three further findings. It rechecked those on `main` at `008c4af`: two are resolved and the third is partly resolved and now minor (below).
- **How `main` got there.** At 16:31 PST Ronok asked for GitHub to be brought up to date for other people. `main` was fast-forwarded from `b6e93bd` three times, never forced: at 16:42 to the accepted build with its records, at 17:03 with the setup refusals, and at about 17:33 with the redesign and the side panel. The repository is public. After the first two moves an anonymous clone was checked: it showed the rebuilt README and served the walkthrough with the README's own command.
- **One thing is held off `main`.** At Ronok's direct request the redesign session built a demo sign-in by name and password, with any password accepted (`5f6c90c`, then `530362c`, on its own branch). The coordinator and an independent Claude Opus 5.5 reviewer both found it cannot merge as built: a start-up option relabels recorded scripted work as the named presenter's, and the record cannot tell a rehearsal key from a person. [The record](../decisions/ADR-20261110-demo-sign-in-held.md) has the findings and the alternatives. He chose a rework with a real password (decision 14); role 2 is building it, and it is not on `main` yet.
- **Nothing from Uptime has been written to Ramp**, and no real vendor was contacted.

## Decisions that are Ronok's

In the order they block the submission.

| # | Decision | What it turns on | State |
|:--|:---|:---|:---|
| 14 | What replaces the demo sign-in | He wants no credential file on camera and his own name as the reviewer. As built, any password is accepted, the form reads as an ordinary login, and the pages name the presenter for work the scripted account did. Options in [the record](../decisions/ADR-20261110-demo-sign-in-held.md): rework it with a password that is set at start-up and really checked, its own key and a demo mark on every recorded step (the coordinator's recommendation); keep the scripted account and sign in before the film starts; or drop it | **Chosen, about 02:20 PST: rework it.** Role 2 is building the reworked version on `work/submission-demo-reviewer-20261110`; the two original commits stay unmerged. Still his: start the filmed walkthrough himself and type the password at its prompt, since no agent sets or learns it |
| 1 | Move `main` to the verified build | Judges clone the default branch. Independent acceptance ranked this first of its findings ([P1-A](acceptance.md)) | **Done** on his instruction, by fast-forward only: 16:42, 17:03 and about 17:33 PST |
| 2 | Which film is the submission film | Role 6 wrote a measured two-minute storyboard and a filming checklist for a spoken film. Separately, a session started by the judge session produced a silent, captioned 89-second cut in `~/uptime-demo/video-01/`, outside the repository; Ronok chose captions over a voice there | **Partly decided, about 17:50 PST:** the film opens on the real Ramp bill with the side panel beside it, then shows the Northwind case as a separate story. Role 6 re-cut the storyboard for it (`b5493d7`). Still open: a spoken film, the silent captioned cut, or both. The 89-second cut was filmed before the redesign, and no re-shoot starts until Ronok says so ("Not yet", 22:28 PST) |
| 3 | Film on the redesigned build, or on the accepted one | Role 6 rewrote the [filming checklist](presentation.md#filming-checklist-for-ronok-main-0c30f8f) for `main` at `0c30f8f`: the redesign before the icons, the application-style layout and the "reviewer" wording. It has not been checked against the look since, so check it before a hand-filmed take. The accepted build `52f1a2f` is still on the fallback branch | Open |
| 4 | Record the voiceover and the film; choose cut A or B after a timed read | Only a person can | Not done |
| 5 | Ease the load on this Mac | Six of the coordinator's full runs have stalled in a browser launch, and one of the redesign session's. Three were captured: a freshly launched Chrome sat with its main thread waiting on a macOS system service, so it never answered the test. The third capture shows the service answering within a millisecond and the browser never picking the answer up, with no other browser launching at the time; and it came after the 18:35 restart, so a restart does not cure it. Swap was nearly full each time. Each stall costs about thirteen minutes and no test has failed in one. Fewer applications and sessions open while a run is going is the only lever left to try | Not done; his call |
| 6 | Load the side-panel extension into his own browser | `chrome://extensions` → Developer mode → Load unpacked. No script does this for him. A copy set to port 8806 is in `~/uptime-demo/side-panel-extension`, with a workspace serving on that port. The steps are under "Start, resume, reset" | Ready for him. The toolbar button opening Chrome's own side panel is the one step no agent could test |
| 7 | Whether a person approves a model candidate on camera | The walkthrough's reviewer is a scripted test account. A person's approval needs a person | Open; the film does not need it |
| 8 | D02: put an authored Northwind bill into the Ramp sandbox | It would show an authored finding beside a Ramp bill. Role 3 recommends against it | Not done; default keeps Northwind out of Ramp |
| 9 | D05 run 2 (sealed vendor evaluation) | Runs only on his go-ahead, in the evaluation session | Not part of this push |
| 10 | A standing policy for the follow-up approval | Would make "approve response" automatic in one narrow case. It combines an approval gate, so it is [a written proposal only](disputes.md) for team review | Not implemented |
| 12 | What a zero means in a claim's own record | The record sends "0.00" for stages it does not track (posted, applied) and for some amounts it does not know (an estimate with no determined outcome; a claim filed outside Uptime). Sending no value instead changes fourteen existing tests and one frozen expectation set | Open; role 2's written proposal is on its way. Not changed tonight |
| 13 | Say where the two company pictures came from | Ronok supplied a cloud for Northwind Cloud and a lighthouse for Harborline Analytics, and asked for them in the interface. They are on `main`, in a public repository. [The notices](THIRD-PARTY-NOTICES.md) record that he supplied them and nothing about who made them or under what terms | Asked at 22:59 and again at 23:38 PST; open. If either is someone else's work, it comes out |
| 11 | Clearing temporary files | Free disk fell to 0.8 GiB during a Chrome update and is now about 13 GiB. Old test folders and caches are his to clear | Open; nothing was deleted |

## What changed in this push

| Area | Before | Now | Owner |
|:---|:---|:---|:---|
| Walkthrough | Eleven clicks | Four reviewer decisions (approve the claim, approve the response, post the credit, apply it) and seven steps that run automatically under an approval already recorded or a signed source event. Each step records what authorised it. No approval gate was removed or combined | Role 2 |
| Model work on screen | Not visible in the product | A contract-reading job shows each proposed term beside its quoted sentence; a reply-reading job shows its cited text. Failed and timed-out jobs keep their receipts. A refusal names the passage that caused it | Roles 1, 2, 4 |
| Ramp | A November 5 worklist | A saved, verified record of the sandbox bill that carries the person-posted note, with read time, completeness and the Ramp link. Read-only | Role 3 |
| Sign-in | A credential file in a hidden folder | Setup ends by printing the credential file, the account and the address | Roles 2, 4 |
| Interface | 13 navigation items, a builder's console | 4 destinations, then a full redesign in one visual system: an Overview that leads with the outcome and the next decision, Agreements as plain cards (7,917 px tall before, 3,242 now), Cases as a list, Ramp records leading with the verified record alone, and forms and raw records closed until asked for. Then icons, three bundled typefaces, an application-style layout and pictures for the two authored companies, each at Ronok's direct request to the redesign session | Role 4, then the redesign session |
| Beside Ramp | — | A Chrome side panel that shows Uptime's page for the Ramp bill open in the active tab. It is a browser side panel, not a Ramp integration: it reads only the tab's address, and nothing runs inside Ramp or is written to it. Off unless the server is started with one named extension origin | Coordinator, role 2, the redesign session |
| Documents | — | A rebuilt README, a [judge guide](../../JUDGES.md), a measured storyboard and a filming checklist | Role 6 |
| Acceptance | — | Expectations sealed by digest before the build existed, then checked on a fresh clone | Role 5 |

## Published commits

All on `github.com/ronoktanvir/uptime`. Nothing was force-pushed and no history was removed.

| Branch | Commit | What it is | Verified |
|:---|:---|:---|:---|
| `main` | The integration branch's head | The default branch: the accepted build, the setup refusals, the redesign, the side panel and the records. It was `b6e93bd` before this push | Full run passes on its last merge, `f89e204` (5,464, none skipped). GitHub's check passed on every `main` commit it has finished, through `6cf2b31` |
| `frozen/submission-fallback-20261109` | `52f1a2f` | The verified build | Full run and hosted checks pass; independently accepted |
| `work/submission-integration-20261109` | this file's branch | The same commit as `main`. Every merge is made and verified here first | One full run per merge; the table below |
| `work/submission-design-20261109` | `1e6c1f8` merged; head `530362c` | The redesign, then Phosphor icons (MIT), three typefaces (Inter, Source Serif 4, JetBrains Mono; all SIL Open Font License), an application-style layout, two company pictures supplied by Ronok, and a list of renamed controls; [notices](THIRD-PARTY-NOTICES.md) | Merged through `1e6c1f8`. Its two later commits, the demo sign-in, are **held and not merged** ([record](../decisions/ADR-20261110-demo-sign-in-held.md)) |
| `work/sidepanel-server-20261109` | `dc4ff65` | Side-panel option, extension, setup option and the real-browser check | Merged. Checked inside the real extension together with the redesign's bill page |
| `work/submission-onboarding-20261109` | `088da4a` | Role 1, contract reading | Merged |
| `work/submission-disputes-20261109` | `845b411` | Role 2: disputes, the walkthrough, the setup refusals, its test port change, and the authored reply variant with its driver | Merged |
| `work/submission-ramp-20261109` | `a15d987` | Role 3, Ramp | Merged |
| `work/submission-ui-20261109` | `7ca68b2` | Role 4, interface before the redesign | Merged |
| `work/submission-acceptance-20261109` | `7c6661f` | Role 5: acceptance, its dated correction, the interface-only addendum on `main`, and the recheck of its three findings on `008c4af` | Merged |
| `work/submission-presentation-20261109` | `5081008` | Role 6: README, judge guide, the film re-cut for the Ramp opening, the filming checklist for `main`, and the README's three screenshots, retaken on `008c4af` with a one-command capture script | Merged |

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
| `4c93a44` | 5,452 passed | The interface set in Inter |
| `c5629c9` | 5,451 passed, 1 skipped | Role 5's addendum and two sentences; documentation only. One browser failed to launch under load and its test skipped; that test passed alone on the same commit. |
| `eacd182` | 5,464 passed | The authored reply variant with its driver, and the interface's "reviewer" wording. Twelve new tests; none skipped, with a browser required. |
| `03f7d27` | 5,464 passed | The app-style pass, two company pictures and the case page's recorded amounts. 132 JavaScript checks |
| `e0e689c` | Aborted | The header at panel width and a keyboard-only focus ring; styles only. Stalled in a browser launch at 90 percent, after 4,950 tests had passed and none had failed. Covered by the next run |
| `6882fd5` | 5,464 passed | The two further typefaces and the light cloud picture, on top of `e0e689c`. 132 JavaScript checks. **The application code `main` holds** |
| `f89e204` | 5,464 passed | Role 5's recheck and role 6's retaken README screenshots; documentation, evidence and images only. **This is what `main` holds** |

GitHub's check workflow runs the same command on a clean machine for every pushed commit. It passes on the accepted build, on every `main` commit it has finished through `88bd23c` (the app-style pass), on the redesign's commits through `0edac3b` and on the side-panel branch through `a162951`. Role 5's branch failed there by itself (2 failed, 5,297 passed) while it carried a restart probe that used an option the branch did not have; it has passed since it was brought up to `main` (`7c6661f`).

**Why runs stall.** The stalls are in this Mac, not in the tests. In all three captured cases a freshly launched Chrome had no page process and its main thread was waiting on a macOS system service ([first record](../evidence/submission-20261109/suite-ea58f22-aborted2.json), [second](../evidence/submission-20261109/suite-8561fe3-aborted.json), [third](../evidence/submission-20261109/suite-e0e689c-aborted.json)). In the first two another session had launched Chrome within seconds. In the third none had, the system log shows the service answering at once, and the Mac had been restarted five hours earlier; so neither another session's browser nor a long uptime is needed for it. No test has failed in a stalled run.

These are regression results. They do not measure model accuracy, and they are not evidence of a person's approval or of any effect in Ramp.

## Evaluation results, kept separate

| What was measured | Result | Who measured it |
|:---|:---|:---|
| Unseen contracts, latest independent pass | 12 genuine Opus calls; all 12 proposals failed validation. 0 of 4 intended positives reached shadow. All 6 contracts were refused. All 8 dispute cases stopped at setup, so dispute accuracy is unmeasured ([results](../evaluation-finish-20261109/RESULTS.md)) | The Codex evaluation lane, on `main` |
| Earlier first attempts | 0 of 4, 3 of 6, 0 of 50, and a refused public SLA (Backblaze). Unchanged | Earlier lanes |
| Authored contracts in this push | 1 of 2 written inside the supported grammar reached shadow, with 11 exact quotations. The other and a control were refused | Role 1; verified from receipts by role 5 |
| The accepted build `52f1a2f`, from a fresh clone, before the redesign | Passed: the published steps work once that build is checked out; the money, 58 of 58 citations and each step's authority match the sealed expectations; no unsafe acceptance, invented evidence or unauthorised money movement ([report](acceptance.md)) | Role 5 |
| The redesigned interface on `main` at `08852a6`, from an anonymous default clone | Passed: every sealed figure, 58 of 58 citations and each step's authority hold; earlier findings 2 and 3 are resolved; the side panel's default, the one-bill page and the bundled font were checked. Three further findings were listed ([addendum](acceptance.md)) | Role 5 |
| The same three findings, rechecked on `main` at `008c4af` from an anonymous default clone | A1 and A3 resolved. A2 partly resolved and lowered to P3. Every sealed figure, 58 of 58 citations and each step's authority hold after the four decisions; nothing new states a person for the scripted account, a local credit as money in Ramp, or an estimate as an award. Not rechecked: narrow widths and the side panel ([second addendum](acceptance.md)) | Role 5 |

This push did not improve the unseen-contract result and must not be presented as if it did. Acceptance also found that a differently worded evidence request is not recognised (it goes safely to a reviewer), and that a correct denial with a genuinely late filing cannot be driven through the product's routes.

## Model work

**In the product, all recorded on November 9, none live:**
- Six `claude-opus-5-5` calls read three authored contracts, one call per rule family and none retried.
- One `claude-opus-5-5` call read an authored unclear vendor reply. It was read as ambiguous, the case went to a reviewer, and nothing was awarded.
- One `claude-opus-5-5` call read an authored reply asking for the January log in other words. It proposed the right document and type, and tagged the month, which the reply gives without a year. Uptime's checks will not act on a period that is not one exact month, so the case stayed with a reviewer and nothing was awarded.
- Each call ran with no tools, after an operator recorded permission for that exact request. The operator was the engineering agent, named as such; no approval names Ronok. A model's output is a proposal only.
- Northwind's own contract and its vendor's log request use fixed rules, with no model call.

**In the engineering:**
- The six role sessions report `claude-opus-5-5`. The coordinator and the video session report `claude-fable-5-2`. The redesign session reported `claude-fable-5-2` for its commits through `1e6c1f8` and `claude-opus-4-8` for the two demo sign-in commits.
- One separate `claude-opus-5-5` session criticised the side-panel decision, and another the demo sign-in. Each one's findings and what was done about them are in that decision's record.
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
| Film | [The filming checklist](presentation.md#filming-checklist-for-ronok-main-0c30f8f) gives three terminals, five tabs and a fresh folder per take. It was written for `main` at `0c30f8f`; the look has changed since |
| Use the side panel beside Ramp | Start with the framing option added: `--side-panel-origin chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl --serve`. In Chrome open `chrome://extensions`, turn on Developer mode, choose Load unpacked and pick `extension/`; its ID should read `kibophanbmnepbmhpampfagpjfhjfcnl`. Open a bill in Ramp's demo, click the Uptime toolbar button and sign in inside the panel. If the workspace is not on port 8776, change `origin` in `extension/config.js`. [More](../../../extension/README.md) |
| Run the checks | `uv run --locked pytest`, then `node --test web/*.test.cjs tests/helpers/*.test.cjs` |

The two recorded model workspaces are preserved outside Git. Serve only a copy of each, never the preserved folder: serving changes the database file. The steps are in [the onboarding runbook](onboarding-runbook.md#preserved-recorded-workspace-for-the-film) and [the disputes handoff](disputes.md).

## Open work and blockers

| Item | Owner | State |
|:---|:---|:---|
| Setup command: its real-process tests took a port from 8821–8829 and skipped if all were taken | Role 2 | **Done** (`8addc5a`): they take a port the system assigns. Requested at 17:50 PST. The plain refusals and the `--serve` rule are done |
| A model step inside the main case: a third authored reply the fixed rules do not recognise, read by one genuine model call and checked by the reviewer against their own reading | Role 2, then the coordinator | Approved by Ronok at about 21:30 PST, relayed by the judge session, for the variant and the one call only. Both are done. **The call's result:** Claude proposed the right document and type but tagged the month without a year, and Uptime's checks would not act on that proposal; under the rule fixed beforehand it does not count as the log request, the case stayed in review and no money moved ([receipt](../evidence/submission-disputes-20261109/reworded-model-job.json)). The film decision is Ronok's: by the agreed rule the current cut stands |
| The routine-steps line said a person approves where the account is scripted (acceptance A1, P2); the scripted reviewer's display name was only inside closed sections of the Overview (A3, P3) | The redesign session, then role 5 | **Done and rechecked.** Fixed in `91dc42c`; role 5 rechecked both on `main` at `008c4af` from an anonymous clone and found them resolved (`7c6661f`, merged) |
| Interface-only acceptance check of the redesign and the side panel's default | Role 5 | **Done** (`319ca43`). First requested at 17:50 PST |
| Retake the README's three screenshots, add a README link to the third-party notices, the video link | Role 6 | **Done except the video link** (`5081008`, merged): the three screenshots are from `008c4af`, and a later retake is one command, `uv run --locked python docs/v4/submission/tools/capture_readme_screenshots.py`, on this Mac, where the recorded workspace is kept. The README links the notices, links the receipts folder instead of one receipt, and states role 5's recheck. The video link waits for the film. If the look changes again, the screenshots need that command run again |
| Say how the requested log arrives | Role 6 | **Done** (`b5493d7`). The README's third step and the storyboard now say the log and its verification arrive through a signed source, from two senders, and Uptime matches them. The product's step names still say attach and verify; its authority line says received |
| Evidence requests are recognised only in wording the rules know | Disputes owner | Not changed in this push; the wording that overstated it is corrected |
| A case's own claim record sends "0.00" for posted and applied, which it does not track (`uptime/correspondence.py:822`) | Role 2 | Found by the redesign session. Acceptance graded it P2 (A2): the case page's closed record section read "Posted USD 0.00" and "Applied USD 0.00" after the credit was posted and applied; the Overview, the older case view and the guide were correct. **The page is fixed** (`824c213`, merged): that section now says the record does not track those stages. Role 2 assessed it: sending no value changes what a zero means in that record, fourteen existing tests and one frozen expectation set. **A decision for Ronok and the team, not made tonight.** The server still sends the zeros; [the proposal](disputes.md) is written. **Role 5's recheck on `008c4af`: partly resolved, lowered to P3.** A second closed section on the same page, "Complete server case record" (`web/v4_ui.js:461`), still prints the server's whole record, zeros included. Nothing is visible unless opened and the explanation is on the same page. Left for the redesign session when it is next in that file; not sent to it tonight, because it changes nothing a film or a reader sees without opening that section |
| Re-shoot the 90-second cut on the redesigned build | The video session | Told at 17:50 PST to wait for role 6's storyboard. Its command is `./remake.sh <commit>` in `~/uptime-demo/video-01/`; its selectors need editing first. The Ramp opening is footage only Ronok can record |
| The demo sign-in | Role 2, then the coordinator | **Being reworked.** `5f6c90c` and `530362c` stay held on the design branch. Role 2 was briefed at 02:31 PST to build the version Ronok chose on `work/submission-demo-reviewer-20261110`: a password read at a prompt and really checked, a key made in the page, a marker on every record that account writes, and labels read from the records ([design and criticism](../decisions/ADR-20261110-demo-sign-in-held.md)). The coordinator then checks it, runs the full suite and merges. Any workspace in which an agent signed in under his name is to be discarded, not filmed. The redesign session's later work has to start from `main`, not from its branch's held commits |
| Unseen contracts: 0 of 4 | The Codex lanes ([queued work](../NEXT-WORKSTREAMS-20261109.md)) | Outside this push |
| Responses that return before the header middleware carry no security headers | Application owners | Existing gap, found in review; not changed |
| Server messages that say "a person" or "human" where the interface now says "reviewer" | Application owners | Listed in the coordination record. Left as they are: they state what a step requires, not who acted |
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
- **Order from here:** never merge `5f6c90c` or `530362c`; when role 2 delivers the reworked demo sign-in, check it against the record's findings (the two scripts in the integration task folder under `demo-label-check/` reproduce the main one), run the full suite and merge; merge what else the redesign session pushes and rerun the screenshot command if the look changed; the film waits for Ronok's word, and so does the answer on where the two company pictures came from. After each verified merge, fast-forward `main` to it: `git push origin <verified commit>:refs/heads/main`. Never force.
- **Rules that do not relax:** no force-push; no write to Ramp and no retry of the refused posting action; no real vendor contact; no credential, private evaluation answer or customer capture in Git; every changed existing test recorded by exact name and reason; the scripted reviewer is never described as a person; no agent or test signs in under Ronok's name; a local credit is never described as money in Ramp.
