# Role 6: README, evidence packaging and the two-minute film

Owner `agent0`. Branch `work/submission-presentation-20261109`, from `origin/main` at `b6e93bd`. November 9, 2026. The task text is Ronok's coordination brief (12:50 PST), relayed by the coordinator. This file is the role's handoff: the storyboard, the script, the dependencies on other roles, the fallback and what only Ronok can do. It is a dated record and does not show that work is still running.

**Status: phase 1.**
- Done: README text and structure, the [judge guide](../../JUDGES.md), the capability table, the six-window storyboard and the five answers.
- Phase 2 waits on the coordinator naming the frozen commit. It covers the three screenshots, measured latency, the final cut and a rehearsed fallback.
- No screenshot, video link or timing in this file is final yet.

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

## Storyboard: six windows, 120 seconds

Narration is written at about 125 words a minute: 222 words. Phase 2 measures each beat on the frozen build and cuts to fit. "Made true by" names the role file and fields that must exist on the frozen build before the beat can be filmed.

| Window | On screen | Narration | Made true by |
|:---|:---|:---|:---|
| **0:00–0:15** The old way | Twilio's live API SLA page, section 3, scrolled to the claim paragraph. Caption: "Twilio API SLA §3". | "Vendor SLAs promise credits that are rarely collected. Twilio's says: open a ticket titled 'SLA Claim', list every outage, attach proof, within thirty days of month end. Then check the next invoice." (32) | Public page (role 6). Checked November 9 |
| **0:15–0:40** Model-assisted contract reading | **Agreements**: an authored prose contract (role 1's "Halden Relay"). The recorded Claude Opus 5.5 job: model, time taken, each proposed term beside its quoted sentence, "validated", then **Shadow**. | "Uptime starts with the contract. This reading was recorded earlier today: Claude Opus proposed each term with the sentence it came from — target, credit steps, claim window. Code validated it and staged it in shadow. Nothing takes effect until a reviewer approves that exact version." (45) | [Role 1](onboarding.md) §2–3: the genuine calls and receipts, and the job fields `model`, timestamps, quotations, validation and lifecycle state. Role 4 renders them on Agreements |
| **0:40–1:05** Deterministic finding and approval | **Overview** of the Northwind workspace: January's $2,400.00 with its clause and inputs, and March's $1,000.00 overcharge. Press **Approve claim**. | "Here is one full case. Northwind's contract and usage records are authored for this demo. January: 135 minutes down, two steps below target, so twenty percent of twelve thousand — a $2,400 credit, clause attached. March's invoice ignored an amendment: $1,000 over. I approve the claim." (45) | Role 4 overview headline ([ui](ui.md) b); role 2 headline fields ([disputes](disputes.md) §3b); approval `approve-claim` |
| **1:05–1:35** Denial, cure and review | **Activity**: the claim is filed. The local counterparty's reply arrives, and the requested log is attached and verified with no click. The pause reads "approval required". Show the model's reading of the denial, labelled recorded. Then press **Approve response**. | "The vendor — a local counterparty, not a real vendor — asks for a log. A model read that reply and named the missing evidence; it can't approve anything. Uptime attaches the log, verifies it against a second source and drafts the response. It stops for me. I approve; Uptime sends it after the cooling-off period." (54) | Role 2 coordinator and `workflow.automation` (§2–3a), the denial model job (§3c), cooldown `timing.not_before`; role 4 Activity |
| **1:35–1:55** Credit lifecycle and balance | **Overview**: the award arrives. Press **Post credit**, then **Apply credit**. End on April: $11,000.00 → $8,600.00, destination Local ledger. | "The vendor awards $2,400. I post the credit and apply it to April's invoice: $11,000 becomes $8,600. One credit, moving through stages, in a local ledger — not money recovered in Ramp." (31) | Role 2 `finance.stages`, `ledger.bill`; role 4 lifecycle |
| **1:55–2:00** Ramp | Role 3's verified record panel for sandbox bill `f74ba12c-95d0-582d-9f62-26d8057d1d37`: business, read time, the person-posted note, its read-back. | "In Ramp, Uptime reads this bill; a person posted the note. Writing back is next." (15) | [Role 3](ramp.md) (c): capture and record fields; the read-back receipt |

**Disclosures that must be spoken** (task 10): "authored for this demo" (0:40), "a local counterparty, not a real vendor" (1:05), "in a local ledger — not money recovered in Ramp" (1:35) and "a person posted the note" (1:55). The scripted reviewer account stays visible in the top bar throughout.

**Recorded model work** (task 9): both model beats say "recorded" or "read" in the past tense, and the screen shows the job's own timestamps and model name. No beat presents a recorded result as happening live. If phase 2 measures a live call that fits its window, the narration may change to the present tense only for that take.

**Open points for phase 2:**
- Which case carries the filmed denial reading. The Northwind cure reply is recognized deterministically. Role 2 §3c places the model job on the case interpretation route, after the reviewer's own reading, which is an undecided D06 sub-question. Agent3 and the coordinator choose the case; the narration follows.
- Whether role 1's recorded job is reachable in the same presentation workspace or needs a second tab. A second tab needs its own sign-in, which must happen before recording.
- The 1:55 window holds 15 words. If it cannot fit, trim the 0:15 window, not the Ramp limitation.

## Fallback (task 8, acceptance)

If a live model call fails, times out or is slow during a take, the take uses the recorded job instead, and the narration says "recorded". If the served walkthrough fails, three deterministic options remain, all offline, repeatable and free of model or Ramp actions:
1. `scripts/rehearse_northwind.py` against a throwaway workspace. It performs the full action path over loopback HTTP with read-back and duplicate checks.
2. The browser checks in real Chrome.
3. The saved screens from the frozen build.

Phase 2 rehearses one of these and records the result here. The fallback is described as a fallback, never as the live run.

## Do not say

Each would be false.
- "We recovered $3,400." The $2,400 is one credit through stages; the $1,000 is a separate open finding.
- "Posted to Ramp", "a Ramp credit", "applied in Ramp". The credit is in a local ledger.
- "Uptime posted this note." A person typed it; Uptime read it back.
- "We stopped the payment." There is no hold, and a note has no payment effect.
- "Live Ramp data" over a saved capture. Say when it was read.
- "It works on any contract." 0 of 4 intended positives reached shadow in the latest independent pass.
- "AI read Northwind's contract." Northwind goes through the deterministic parser.
- Any time or dollar saving. None is measured.

## Five answers, spoken length

Full answers are in [the judge guide](../../JUDGES.md#five-questions-answered).
- **Where is this in Ramp?** "Beside it. Uptime reads Ramp's bills, vendors and approvals through the API. The one thing on a Ramp bill is a note a person posted and Uptime read back. Uptime hasn't written to Ramp yet."
- **Where is the AI?** "Claude proposes contract terms and reads denials, with quotes. Code checks every proposal and computes every number; a reviewer approves."
- **What happens on an unfamiliar contract?** "Today it mostly refuses and names the passage. In our independent test, none of four intended contracts got through. We published that."
- **Who authorizes follow-up?** "A reviewer: claim, response, posting and application. Uptime runs only intake and steps a reviewer already approved. Here I'm using the scripted test reviewer."
- **What remains unimplemented?** "Writing to Ramp, holds and credits in Ramp, real vendor delivery, reliable unseen contracts and hosting."

## README and guide claims that depend on other roles

These sentences describe the target build. Phase 2 checks each against the frozen commit and rewrites any that are not true there.

| Claim | Depends on |
|:---|:---|
| "Uptime runs routine steps itself… It stops for every judgment and every financial change"; "Four decisions in all" | Role 2 coordinator |
| "On **Overview**, approve the January claim"; **Agreements**, **Activity** | Role 4 navigation |
| "reads a vendor's denial to name what it asks for" | Role 2 denial model job |
| "The readings shown in the demo were recorded, on contracts authored for the demo" | Role 1 calls and receipts |
| "shows when each record was read and whether the list was complete"; the Ramp record panel | Role 3 capture fields and panel |
| "Sign in with the account name and credential file the command prints" | True today. Holds after the role 2 or role 4 sign-in change |
| Judge-guide links to `submission/{onboarding,disputes,ramp}.md` | Those files exist on `main` only after integration |
| Verification receipt `final-805dd1c.json` | Replaced by the coordinator's receipt for the frozen commit |

## Screenshots (phase 2)

Taken from a fresh presentation workspace built from the frozen commit, on a port in 8861–8869, at 1440 px wide:

| Slot | File | Content |
|:---|:---|:---|
| 1 | `docs/assets/submission/overview.png` | Overview after the four decisions: April $11,000.00 → $8,600.00, the open $1,000.00 March finding, the credit lifecycle |
| 2 | `docs/assets/submission/contract-reading.png` | A recorded Claude Opus 5.5 reading: proposed terms beside quoted sentences, validation, shadow |
| 3 | `docs/assets/submission/ramp-record.png` | The verified Ramp record for `f74ba12c`: business, read time, the person-posted note and its read-back |

The judge's three fcbeede captures are placeholders and do not ship. Its capture scripts (`shots.py`, Playwright with installed Chrome) are reused, with selectors updated for the new interface.

## What only Ronok can do

- Record the voiceover and the final film, and decide when.
- Decide whether to move his filming workspace (8776, now `a6e5931`) to the frozen build.
- Any action that would put something new on a Ramp bill (a person's action under his release rules).
- Approve a model candidate as a person, if the film is to show a person's approval rather than the scripted reviewer's.
