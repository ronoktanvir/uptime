# Role 6: README, evidence packaging and the two-minute film

Owner `agent0`. Branch `work/submission-presentation-20261109`, from `origin/main` at `b6e93bd`. November 9, 2026. The task text is Ronok's coordination brief (12:50 PST), relayed by the coordinator. This file is the role's handoff: the storyboard, the script, the dependencies on other roles, the fallback and what only Ronok can do. It is a dated record and does not show that work is still running.

**Status: phase 2, part B done on `main` (`0c30f8f`: the redesigned interface and the browser side panel; full run 5,452 passed at `1fa4ab4`).**
- Storyboard recut for the Ramp-and-side-panel opening; log wording fixed; side-panel line in the README and judge guide (`b5493d7`).
- Timed on `main` with two fresh takes, the recorded contract copy, the panel page and the real-extension check ([timing-0c30f8f.json](../evidence/submission-presentation-20261109/timing-0c30f8f.json)).
- The three README screenshots retaken from `main` and placed in the README.
- The deterministic fallback rehearsed again on `main`.
- [The filming checklist](#filming-checklist-for-ronok-main-0c30f8f) rewritten for `main`, with labels read off the redesigned pages.
- Part A results on `52f1a2f` are kept below for reference.

## What phase 1 changes

| File | Change |
|:---|:---|
| `README.md` | The opening is rebuilt around the old way, what Uptime does, one financial example and the shortest launch. The engineering records move below the launch, under one index. Scattered caveats become one capability table, with qualifications kept beside the claims they qualify. The stale 3,967 test count gives way to the CI badge and a commit-pinned receipt. Three screenshot slots and the video slot are HTML comments, so nothing visible is a placeholder |
| `docs/JUDGES.md` (new) | A compact judge-facing guide: run, what to look at, what is authored, the five answers, an evidence index |
| `docs/ENGINEERING-MAP.md` | Index links to the judge guide and this file. No other change |
| This file | Storyboard, script, dependencies, fallback |

No test, application file or historical document is changed, moved or deleted.

## Inputs used

- The judge session's drafts (`README-TOP.md`, `DEMO-SCRIPT.md`, captured from `fcbeede`), handed over through the coordinator. The task list below applies the coordinator's five differences from Ronok's brief:
  - seven beats recut to six windows;
  - no video link until a video exists;
  - no invented cost figure;
  - the model and recovery beats rewritten for roles 1 and 2;
  - no test count.
- Twilio's API SLA, section 3, checked against the live page on November 9: last updated April 9, 2026. The checked terms:
  - a support request with the subject "SLA Claim", within 30 days of the end of the month, with the dates, times and documentation;
  - a 10% credit, applied to future amounts and not refunded.
- The handoff notes of roles 1–4 on their branches, and the independent results at `docs/v4/evaluation-finish-20261109/RESULTS.md` on `main`.
- A launch check on this branch: from a checkout with no environment, `uv run --locked python scripts/setup_northwind.py --directory <new folder>` created the environment and completed setup in 2.4 s. It printed the account and credential path. The folder was deleted afterwards.

## Storyboard: Ramp opening, then one full case (120 seconds, cut for `main`)

**Ronok's decision (about 17:50 PST, November 9):** the film opens in Ramp, with Uptime's side panel beside the real sandbox bill. The Northwind case follows as a separate story, introduced by one spoken line. Only Ronok records the Ramp window; no agent signs in to Ramp.

**What was cut to make room, and why:**
- **The Twilio page (old 0:00–0:15).** The Ramp bill now carries the manual-workflow sentence: a bill with no contract behind it is where the old way starts. Twilio's claim procedure stays in the README, checked against the live page.
- **The closing Ramp beat (old 1:51–2:00).** The opening now shows the exact Ramp connection and its limit ("Uptime has made no write to Ramp"), so repeating it at the end would spend time on the same fact.
- **Kept:** the recorded model reading, the deterministic finding and approval, the cure and review, and the credit to the balance. These are the task 8 elements. The model beat moves before the bridge line, so it answers "how does Uptime get a contract?" right after a bill without one.

| Window | On screen | Narration | Measured |
|:---|:---|:---|:---|
| **0:00–0:26** Ramp, with the side panel | **Ronok's window.** Sandbox bill `f74ba12c-95d0-582d-9f62-26d8057d1d37` in demo.ramp.com. Click the Uptime toolbar button. The panel reads "This tab · Ramp bill f74ba12c…" and shows DocuSign, invoice DD-PREAPPROVAL, USD 840, "Saved record read from Ramp Nov 9, 2026, 22:00 UTC, started by a person. Not a live read.", "Evidence gap: the governing agreement or usage evidence is missing", "No agreement on file for this bill", the person-posted note, and "Uptime has made no write to Ramp." | "This is a vendor bill in Ramp. Checking it by hand means finding the contract, totalling outages and filing a claim in time. Uptime's side panel shows no agreement on file for this bill: an evidence gap. A person posted that note; Uptime has made no write to Ramp." (49) | On `main`: the panel's `#ramp-bill/f74ba12c…` page renders in 0.07 s at 420 px. The real-extension check (Ramp stubbed locally) follows the tab, keeps the sign-in and shows every line above. The Ramp page itself is not measured: it needs Ronok's sign-in |
| **0:26–0:49** Model-assisted contract reading | Second Uptime tab: the recorded workspace, **Agreements**, the Corvid Ledger card with its model job directly under the facts: job `26ee4e3f…`, SUCCEEDED, claude-opus-5-5, its times, "The proposal is unreviewed and not approved", and each proposed term beside the sentence it cites. Caption: "Recorded run, authored contract". | "Contracts come in two ways. Fixed rules read wording Uptime knows. For new wording, Claude proposes the terms; this recorded run read an authored contract, each term quoted from its text. Code validated it; it waits in shadow for a reviewer. A second contract was refused." (46) | The card renders 0.08 s after opening Agreements; no form is needed on `main`. Pre-loaded before recording |
| **0:49–1:00** The bridge | Switch to the walkthrough tab, **Overview**, untouched | "For a vendor whose contract Uptime holds, here is one full case. Its contract and records are authored for this demo." (21) | Tab switch only |
| **1:00–1:17** Deterministic finding and approval | **Overview**: the January credit with its clause, the March price exception, "Needs attention". Press **Approve January claim**. | "January: 135 minutes down, two steps below target, so twenty percent of twelve thousand: a $2,400 credit, clause attached. March's invoice ignored an amendment: $1,000 over. I approve the claim." (30) | Approve January claim → 1.64 s / 1.50 s (takes 1 and 2), including the four automatic steps |
| **1:17–1:45** Reply, cure and review | **Activity**: "Received automatically: event …" for the vendor reply, the log export and its status verification; the step names say "Attach requested log" and "Verify supplied log", and the authority line says what arrived. Back to **Overview**; press **Approve response**. Activity then shows the dispatch held until the end of the response cooldown. | "The vendor, a local counterparty, not a real vendor, asks for a log in wording the rules know; other wording would go to a reviewer. The log and its verification arrive through a signed source, and Uptime matches them, drafts the response and stops for me. I approve; it's sent after the cooling-off period." (54) | Activity 0.06 / 0.02 s; Approve response → 1.02 / 1.57 s, including the dispatch at the cooldown and the award intake |
| **1:45–2:00** Credit lifecycle and balance | **Overview**: Awarded $2,400.00 → press **Post to Local ledger**, then **Apply credit to eligible invoice**. End on the April invoice: $11,000.00, credit applied $2,400.00, remaining $8,600.00, Local ledger, the lifecycle "not added together", and "4 reviewer decisions and 7 automatic steps recorded". | "The vendor awards $2,400. I post the credit and apply it to April's invoice: $11,000 becomes $8,600. One credit, in a local ledger, not money recovered in Ramp." (28) | Post 0.87 / 1.15 s; Apply 0.82 / 0.73 s; ends "4 reviewer decisions and 7 automatic steps recorded" |

**Fit.** 228 words. The speaking rate is an assumption until Ronok's timed read.

| Window | Seconds | Words | Speech at 125 wpm | Speech at 150 wpm |
|:---|---:|---:|---:|---:|
| 0:00–0:26 | 26 | 49 | 23.5 | 19.6 |
| 0:26–0:49 | 23 | 46 | 22.1 | 18.4 |
| 0:49–1:00 | 11 | 21 | 10.1 | 8.4 |
| 1:00–1:17 | 17 | 30 | 14.4 | 12.0 |
| 1:17–1:45 | 28 | 54 | 25.9 | 21.6 |
| 1:45–2:00 | 15 | 28 | 13.4 | 11.2 |
| **Total** | **120** | **228** | **109.4** | **91.2** |

Every window has its speech at 125 wpm inside it. The slack is for the clicks: 2.5 s at the opening (the toolbar button), 2.6 s at 1:00 (Approve January claim) and 2.1 s at 1:17 (Activity, Overview, Approve response). On `main` a decision takes up to 1.6 s to settle (0.3–0.6 s on `52f1a2f`): finish the sentence, click, and let the result appear before speaking on. Receipt: [timing-0c30f8f.json](../evidence/submission-presentation-20261109/timing-0c30f8f.json).

**Wording rules for this cut:**
- **The log.** It is not fetched or produced by Uptime. The log and its verification arrive as authored events through the signed intake (`fixtures/northwind/supplements.json`): a log export from one sender and a status verification from a second, with the same digest. Uptime matches them. The product's step names say "attach" and "verify", and their authority line says "Received automatically: event …". The narration says "arrive through a signed source … Uptime matches them".
- **The reply.** It is recognized because its wording is one the rules know. A differently worded request goes to a reviewer, as independent acceptance found on `52f1a2f`.
- **The side panel.** It is a browser side panel that reads only the active tab's address. It is never "in Ramp", "a Ramp app" or "Ramp-native", and nothing is written to Ramp.
- **The stories stay separate.** Northwind is never on the Ramp bill, and the Ramp bill has no agreement. The bridge line is the only connection, and it says the contract and records are authored.

**Disclosures that must be spoken:**
- "a person posted that note; Uptime has made no write to Ramp" (0:00);
- "this recorded run read an authored contract" (0:26);
- "authored for this demo" (0:49);
- "a local counterparty, not a real vendor" (1:17);
- "in a local ledger, not money recovered in Ramp" (1:45).

The reviewer account, `scripted-test-reviewer`, shows at the foot of the sidebar; keep it in frame in the walkthrough.

**Not in this cut:** the unclear-reply model reading. It no longer fits in 120 seconds with the Ramp opening. It stays in [the judge guide](../../JUDGES.md) with its receipt.

**Rules for the model beats** (coordinator, November 9): the cut must not imply that the model read the Northwind contract or the cure-branch reply.

## Recorded workspaces for the model beats

Both are preserved by their owners. Phase 2 serves a **copy** of each, never the preserved folder, because signing in writes to the database. Neither can start a new model call: the approvals have expired and the jobs are terminal. Each is labelled on screen and in narration as a recorded run, with its job id and time.

| Beat | Preserved folder | Content | Serve command and labelling |
|:---|:---|:---|:---|
| 0:15–0:40 | `~/.local/share/uptime-engineering/tasks/submission-onboarding-20261109/recorded-workspace/` (tenant `submission-onboarding`, account `role1-operator`) | Corvid Ledger, job `26ee4e3f`, SHADOW `ff76ed67` | [Onboarding runbook](onboarding-runbook.md), "Preserved recorded workspace". On `main` the job shows on the Agreements card under the agreement's facts, so no form entry is needed |
| Not in the current cut (judge guide only) | `~/.local/share/uptime-engineering/tasks/submission-disputes-20261109/recorded-workspace/` (Northwind, unclear reply; recorded origin `http://127.0.0.1:8823`) | Job `29f371d0` SUCCEEDED 21:19:55–21:20:00 UTC: candidate "unsupported" citing the whole reply; trace ESCALATE / AMBIGUOUS_GROUNDS; awarded 0.00; paused at UNEXPECTED_GROUND | [Disputes handoff](disputes.md), "Recorded denial-job workspace" |

**Not filmed: correct denial.** No demo workspace shows a vendor's denial being correctly accepted. Automated tests cover it through the signed routes. The independent acceptance run exercised one such case over real HTTP (announced maintenance corroborated by the customer's notice, closed on a signed acceptance). A genuinely late filing cannot be driven through the routes. The judge guide says so and links [the report](acceptance.md).

**Interface before and after** (gent7's measurements; usable in one spoken line or the judge guide):
- primary navigation: 13 → 4 items;
- workspace names: 3 → 1;
- Overview height at 1440 px after the flow: 8,547 → 3,880 px;
- sign-in to applied credit: 11 clicks → 4 reviewer decisions.

**Suites to cite** (the coordinator's receipts under `docs/v4/evidence/submission-20261109/`), failures included:
- `02d86f7`: 2 failed, 5,308 passed.
- `c756853`: 1 failed, 5,366 passed.
- `6c83947`: 5,378 passed.
- `96615d8`: the first run stopped advancing and was aborted; the second run gave 5,379 passed.
- `ff7977c`: 5,386 passed.
- `0fe20b4`: 5,388 passed.
- `6b93e31` (application): 5,390 passed.
- **`52f1a2f` (frozen fallback): 5,390 passed, 1 warning in 374.19 s**, the README's verification link.

**Discrepancy to note, not to fix here.** The preserved onboarding folder's database hash is `41fecca2…`, not the `9043eaaf…` that role 1's runbook records. It did not change during these runs. The recorded job and SHADOW adapter displayed as described. The folder belongs to `agent2`.

## Fallback (task 8, acceptance), rehearsed on `52f1a2f` and `main`

If a take fails, nothing is faked: use the next fresh workspace. If the served walkthrough itself fails, the deterministic fallback is:

```bash
uv run --locked python scripts/rehearse_northwind.py --directory <the throwaway workspace> --receipt <new receipt.json>
```

It runs against a throwaway workspace that `setup_northwind.py --serve` is serving.

**Rehearsed result:**
- Passed in 2.44 s over real loopback HTTP from the frozen checkout, authority `SCRIPTED_REVIEWER`.
- Four decisions: Approve January claim, Approve response, Post to Local ledger, Apply credit to eligible invoice. Each repeated request left the state unchanged, and each read-back was equal.
- Automation finished with 4 person decisions and 7 automatic steps.
- Local ledger: 2,400.00 claimed, awarded, posted and applied; April NW-2026-04 $11,000.00 → $8,600.00.
- [Receipt](../evidence/submission-presentation-20261109/timing-52f1a2f.json) under "deterministic_fallback".

**Rehearsed again on `main` (`0c30f8f`):** passed in 4.07 s, with the same four decisions, 4 reviewer decisions and 7 automatic steps, and April $11,000.00 → $8,600.00 in the Local ledger. [Receipt](../evidence/submission-presentation-20261109/timing-0c30f8f.json), under "deterministic_fallback".

If shown at all, it is described as what it is: "the same steps, replayed by a script over the same local server." It is never presented as the live take. The [fallback screenshots](#screenshots) are the last resort.

## Do not say

Each would be false.
- "We recovered $3,400." The $2,400 is one credit through stages; the $1,000 is a separate open finding.
- "Posted to Ramp", "a Ramp credit", "applied in Ramp". The credit is in a local ledger.
- "Uptime posted this note." A person typed it; Uptime read it back.
- "We stopped the payment." There is no hold, and a note has no payment effect.
- "Live Ramp data" over a saved capture. Say when it was read.
- "It works on any contract." 0 of 4 intended positives reached shadow in the latest independent pass.
- "AI read Northwind's contract." Northwind goes through the deterministic parser.
- "Uptime recognizes any evidence request." Only wording the rules know is recognized. Acceptance's differently worded request for a log went to a reviewer.
- The $40 "Scenario only" row on the Ramp records page, or February's "Not determined" credit cell, as findings. Keep both out of frame (acceptance findings 2 and 3).
- Any time or dollar saving. None is measured.
- "Uptime runs inside Ramp", "a Ramp app" or "Ramp-native" about the side panel. It is a browser side panel that reads only the active tab's address, and writes nothing to Ramp.
- "Uptime fetched the log" or "Uptime verified the log against a second source". The log and its verification arrive as authored events through a signed source, from two senders, and Uptime matches them.

## Five answers, spoken length

Full answers are in [the judge guide](../../JUDGES.md#five-questions-answered).
- **Where is this in Ramp?** "Beside it. Uptime reads Ramp's bills, vendors and approvals through the API. The one thing on a Ramp bill is a note a person posted and Uptime read back. Uptime hasn't written to Ramp yet."
- **Where is the AI?** "Claude proposes contract terms, and readings of vendor replies, with quotes. Code checks every proposal and computes every number; a reviewer approves."
- **What happens on an unfamiliar contract?** "Today it mostly refuses and names the passage. In our independent test, none of four intended contracts got through. We published that."
- **Who authorizes follow-up?** "A reviewer: claim, response, posting and application. Uptime runs only intake and steps a reviewer already approved. Here I'm using the scripted test reviewer."
- **What remains unimplemented?** "Writing to Ramp, holds and credits in Ramp, real vendor delivery, reliable unseen contracts and hosting."

## README and guide claims, checked on `52f1a2f` and `main`

| Claim | Result on `52f1a2f` |
|:---|:---|
| Routine steps run by themselves; four decisions in all | True: 4 person decisions, 7 automatic steps, both takes |
| **Overview**, **Agreements**, **Activity**, More tools → Ramp records | True: four primary destinations; "Open Ramp records" goes to `#records` |
| The model proposes a reading of a reply, cited, for a reviewer | True on the recorded unclear-reply copy: job `29f371d0`, dispute record "needs a reviewer · ambiguous grounds" |
| Corvid Ledger reached shadow; Halden Relay refused | True: recorded job `26ee4e3f` card and SHADOW revision 3; Halden per role 1's receipts |
| Ramp page shows read time and whether each list is complete | True: "read from Ramp Nov 9, 2026, 22:00 UTC, started by a person"; list statements "complete list" / "partial list" |
| "Sign in with the account name and credential file the command prints" | True: setup ends with the credential path, account and address |
| Verification link | Now [suite-1fa4ab4.json](../evidence/submission-20261109/suite-1fa4ab4.json): 5,452 passed, 1 warning, on `main`'s application code (`1fa4ab4..0c30f8f` is docs only). The frozen build's [suite-52f1a2f.json](../evidence/submission-20261109/suite-52f1a2f.json) stays linked from the judge guide |
| README screenshots | Taken from `main` `0c30f8f`, the build the receipt covers |
| How the log arrives | Matches Activity on `main`: "Received automatically: event northwind-jan-resource-log from northwind-2026-01-customer" and "… northwind-jan-status-verification from northwind-2026-01-status" |
| Side panel: reads only the tab's address, nothing in Ramp, off without the one origin | Real-extension check on `main`: it frames Uptime only with `frame-ancestors chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl`; it follows the Ramp bill tab; another site with the same path reads "No Ramp bill open"; another page cannot frame the app. Ramp was stubbed locally and not contacted |
| Independent acceptance | Assessed `52f1a2f` only; the README and judge guide say it has not yet assessed the redesigned interface |
| Links in README.md, docs/JUDGES.md and this file | Rechecked after the role files merged; all resolve |
| Model call count | Corrected after acceptance: one call per rule family (two per contract, six in all), plus one for the unclear reply |
| Evidence-request recognition | Corrected after acceptance: only wording the rules know; acceptance's differently worded request went to a reviewer |
| Correct denial | Not in any demo workspace; tests, plus one real-HTTP case in the acceptance run |

## Screenshots

**In the README, from `main` (`0c30f8f`):** 2880×1800, a 1440 px viewport at 2x, taken through the ordinary sign-in and offered controls.
- [overview.png](../../assets/submission/overview.png): Overview after the four decisions, take 2. April $11,000.00 → $8,600.00; the March $1,000.00 exception "not included in it"; the lifecycle; "4 reviewer decisions and 7 automatic steps recorded".
- [contract-reading.png](../../assets/submission/contract-reading.png): Agreements, "Model proposal job" `26ee4e3f`, claude-opus-5-5, "unreviewed and not approved", each term beside its exact sentence.
- [ramp-record.png](../../assets/submission/ramp-record.png): More tools → Ramp records, "Verified Ramp record": DocuSign, DD-PREAPPROVAL, USD 840, read time "started by a person", evidence gap, the person's note and "Uptime has made no write to Ramp". The worklist below it has its rows closed.

**Side-panel evidence, not in the README** ([folder](../evidence/submission-presentation-20261109/side-panel-0c30f8f/)): the panel page at 420 px and three frames from the real-extension check, with Ramp stubbed locally.

**Fallback set, from `52f1a2f`:** kept under `docs/assets/submission/fallback-52f1a2f/`, unused.

## Filming checklist for Ronok (`main`, `0c30f8f`)

Everything here runs on this Mac, loopback only. Every label below was read off the redesigned pages on `main` on the evening of November 9, during the timing runs.
- The side panel uses the workspace on **8806** that the coordinator set up for you.
- The walkthrough takes and the recorded contract run from the clean checkout of `main` at `~/.local/share/uptime-engineering/presentation-0c30f8f`, on **8861** and **8862**.
- Ports 8776, 8777, 8780 and 8801 are not used.
- Each take needs a fresh walkthrough folder, because the four decisions can be made once.

### 1. Before the first take

**Side panel** (as the coordinator gave it to you):
- The workspace is served on `http://127.0.0.1:8806` from a checkout of `main` with `--side-panel-origin chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl`. Account `scripted-test-reviewer`; credential `~/uptime-demo/side-panel-01/scripted-reviewer.jwk`. If it is not running at filming time:

  ```bash
  cd ~/.local/share/uptime-engineering/presentation-0c30f8f && uv run --locked python scripts/setup_northwind.py --directory "$HOME/uptime-demo/side-panel-01" --origin http://127.0.0.1:8806 --side-panel-origin chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl --resume --serve
  ```

- In Chrome, at `chrome://extensions`: turn on Developer mode, choose **Load unpacked**, and select `~/uptime-demo/side-panel-extension`. That is a copy of `extension/` whose `config.js` points at 8806; its ID reads `kibophanbmnepbmhpampfagpjfhjfcnl`.
- Make no decisions in the 8806 workspace. The panel shows only its Ramp bill page, and the takes happen on 8861.

**Terminal A, "walkthrough"** (take 1):

```bash
cd ~/.local/share/uptime-engineering/presentation-0c30f8f && uv run --locked python scripts/setup_northwind.py --directory "$HOME/uptime-film/take-01" --origin http://127.0.0.1:8861 --serve
```

It ends with the credential file, the account and `http://127.0.0.1:8861`.

**Terminal B, "recorded contract".** Serve a copy, never the preserved folder:

```bash
mkdir -p ~/uptime-film && cp -Rp ~/.local/share/uptime-engineering/tasks/submission-onboarding-20261109/recorded-workspace ~/uptime-film/recorded-contract && chmod 700 ~/uptime-film/recorded-contract
```

```bash
python3 -c 'import json,os,sys; d=sys.argv[1]; c=json.load(open(d+"/protected/config.json")); c["approvals_path"]=d+"/protected/approvals.json"; f=os.open(d+"/protected/view-config.json",os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.write(f,json.dumps(c).encode()); os.close(f)' "$HOME/uptime-film/recorded-contract"
```

```bash
cd ~/.local/share/uptime-engineering/presentation-0c30f8f && uv run --locked python scripts/serve.py --db "$HOME/uptime-film/recorded-contract/workspace.sqlite" --mode replay --tenant submission-onboarding --port 8862 --public-proposal-config "$HOME/uptime-film/recorded-contract/protected/view-config.json"
```

On `main` the recorded job shows directly on the Agreements card; the earlier source-file step is no longer needed. No new model call can start from this copy.

### 2. Windows (sign in to everything before recording)

**Window 1, Ramp (filmed first, 0:00–0:26)**
- Tab: `https://demo.ramp.com/bill-pay/bills/list/f74ba12c-95d0-582d-9f62-26d8057d1d37`, with your own Ramp sandbox sign-in. Only you sign in to Ramp; no agent does. Read only: do not comment, approve or edit.
- Side panel: click the Uptime toolbar button. In the panel's "Sign in to Uptime" card, enter Account name `scripted-test-reviewer`, choose `~/uptime-demo/side-panel-01/scripted-reviewer.jwk` as the Credential file, and press **Sign in**.
- The panel should read:
  - "This tab · Ramp bill f74ba12c…";
  - "Verified Ramp record", DocuSign, "Invoice DD-PREAPPROVAL", USD 840;
  - "Saved record read from Ramp Nov 9, 2026, 22:00 UTC, started by a person. Not a live read.";
  - "Evidence gap: the governing agreement or usage evidence is missing" and "No agreement on file for this bill.";
  - "Note in Ramp: Posted by a person in Ramp; Uptime read it back on this bill";
  - "Uptime has made no write to Ramp."
- Scroll the panel so the note and the last line are in view by 0:20.
- If you click the toolbar button on camera, rehearse it once first, to see that the panel comes back already signed in.

**Window 2, Uptime (full tabs)**

| Tab | Address | Account and credential file | Leave it showing |
|:---|:---|:---|:---|
| 2 | `http://127.0.0.1:8862/` → sidebar **Agreements** | `role1-operator`, `~/uptime-film/recorded-contract/role1-operator.jwk` | The Corvid Data Cooperative card (SHADOW, "Not in force."), scrolled to **Model proposal job**: job `26ee4e3f…`, SUCCEEDED, claude-opus-5-5, "The proposal is unreviewed and not approved.", the terms beside their exact sentences |
| 3 | `http://127.0.0.1:8861/` | `scripted-test-reviewer`, `~/uptime-film/take-01/scripted-reviewer.jwk` | **Overview**, untouched. Do not reload: the signing key lives only in the page |

The sign-in card on every page has an "Account name" field, a "Credential file" drop area and a **Sign in** button. After sign-in, the sidebar foot shows "Refresh data" and "Sign out · <account>".

### 3. Order while recording

1. **0:00** Window 1: the bill, the toolbar button and the panel.
2. **0:26** Window 2, tab 2: the model proposal job.
3. **0:49** Tab 3, Overview: "Northwind Cloud", the January service credit and the March price exception.
4. **1:00** In "January recovery", press **Approve January claim**. Wait for "1 reviewer decision and 4 automatic steps recorded".
5. **1:17**
   - Press **See every step in Activity →**. Activity shows "Steps in order", "Received event" for "Receive vendor response", "Attach requested log" and "Verify supplied log", each "Received automatically: event …".
   - Sidebar **Overview**, then **Approve response**.
6. **1:45** **Post to Local ledger**, then **Apply credit to eligible invoice**. End at the top of Overview: April invoice NW-2026-04, $11,000.00, $2,400.00, $8,600.00, "Credit recorded in Local ledger", and "4 reviewer decisions and 7 automatic steps recorded".

Keep "Sign out · scripted-test-reviewer" (sidebar foot) in frame during the walkthrough. On `main` a decision takes up to 1.6 s to appear, so click, then let it settle before the next sentence.

### 4. Between takes

1. Ctrl-C in terminal A.
2. Rerun its command with `take-02` (then `take-03` …).
3. In tab 3, open `http://127.0.0.1:8861/` and sign in with that take's credential file.

Window 1 and tab 2 stay as they are.

### 5. Afterwards

- Ctrl-C in terminals A and B.
- `~/uptime-film` holds only copies and your takes; delete it when you like.
- The preserved folders under `~/.local/share/uptime-engineering/tasks/` are never touched by these steps.

## What only Ronok can do

- Record the voiceover and the final film, and decide when.
- Decide whether to film from this checklist (ports 8861–8862) or move his own filming workspace (8776, still `a6e5931`).
- Do the timed read-through, then choose cut A or cut B.
- Any action that would put something new on a Ramp bill (a person's action under his release rules).
- Approve a model candidate as a person, if the film is to show a person's approval rather than the scripted reviewer's.
