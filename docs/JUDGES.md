# Uptime: a guide for judges

> **November 10 update.** After this guide was written, three things were added: Uptime's notes on matched bills in Ramp's sandbox (posted through Ramp's API and read back), a portfolio page with a second vendor, and a template builder in which Claude agents and the decision model Jev build a reader for a new contract type, behind code checks and a reviewer's approval. Where this guide says Uptime writes nothing to Ramp, read "nothing except those fixed notes". The [README](../README.md#where-ramp-fits) and [the day's notes](../DEMO-NOTES.md) are current.
>
> **Later on November 10**, in answer to a review of that template builder: Jev's decision now routes the run (a contract matching an approved template starts no agent), a term Jev does not support must be acknowledged before approval, every read by a template is guarded, an accepted read produces an agreement in shadow and a credit computed by the existing engine, and a held-out evaluation on six contract forms written blind is [published as it scored](demo/TEMPLATE-BUILDER-HELDOUT.md), including its worst run.
>
> **Evening of November 10**, two further changes, each from its own agent. A credit from a contract the template builder read now goes through the same four reviewer decisions as Northwind's: in the recorded run, USD 2,000.00 for October 2026 is applied to a December invoice of USD 8,000.00 and leaves USD 6,000.00, and the case page says how its contract was read. A template now holds a credit schedule of one to six tiers and keeps each period in the contract's own unit. Real public SLA pages went through the builder for the first time, and [every table is published as it scored](demo/TEMPLATE-BUILDER-PUBLIC-SLAS.md): of 13 pages, 1 was read back; after one fix, of 13 fresh pages from other vendors, 3 were read back, with 18 values returned and none wrong. The rest were refused, mostly because they state what a template cannot hold. A second run of those fresh pages, made as a check after the reader prompt's examples were replaced, read back 7 and returned 38 values that agree with the key and one that does not: a payment term the page words two ways. The vendor that answers the claim is simulated, and its usage, invoices and replies are authored.


[Uptime](../README.md) / Judge guide

Five minutes, no credentials. This page says what to run, what to look at, what is authored, and where the evidence for each claim lives.

## The idea in one paragraph

Vendor contracts promise service credits and fixed prices, but collecting them is manual: read the SLA, total the downtime, file a ticket before a deadline, chase the reply, check the next invoice. Uptime turns the contract into typed rules with citations, computes what is owed with exact arithmetic, runs the routine steps of a claim, and stops for a person at every judgment and financial change. Ramp is the system of record: Uptime reads Ramp's records beside it. It does not yet write back to Ramp.

## Run it

```sh
git clone https://github.com/ronoktanvir/uptime.git && cd uptime
uv run --locked python scripts/setup_northwind.py --directory "$HOME/uptime-demo/northwind-01" --serve
```

Open [127.0.0.1:8776](http://127.0.0.1:8776/) and sign in with the account and credential file the command prints. Details are in [the README](../README.md#run-it).

## What to look at

| Look at | Where | What it shows | Evidence |
|:---|:---|:---|:---|
| The money | **Overview**, before you press anything | January's $2,400.00 credit with its clause and inputs; March's $1,000.00 overcharge, kept separate; March's SLA outcome "not determined" because usage evidence is incomplete | [Contract package](../fixtures/northwind/README.md) |
| What runs by itself | Approve the claim, then watch **Activity** | Filing and the vendor's reply happen without a click. The requested log and its verification arrive through a signed source, from two separate senders, and Uptime matches them. It then stops for the response approval | [Dispute automation notes](v4/submission/disputes.md) |
| The decisions that stay human | The four approvals | Claim, response, posting and application. Each approval is bound to the exact content approved | [Action matrix](v4/integration90/D06-ACTION-MATRIX.md) |
| The settlement | **Overview** after the fourth decision | April's $11,000.00 bill becomes $8,600.00 in a local ledger: one credit, applied once | [Workflow read-back receipt](v4/evidence/demo-path-87/northwind-socket.json) |
| The model | A separate recorded workspace (its own sign-in; see the runbook) | Corvid Ledger: a recorded Claude Opus 5.5 reading, 11 exact quotations, validated and staged in shadow; Halden Relay refused. Northwind itself uses fixed rules | [Runbook](v4/submission/onboarding-runbook.md) · [Call receipts](v4/evidence/submission-onboarding-20261109/genuine-calls-summary.json) |
| An unfamiliar reply | A second Northwind workspace made with `--counterparty-reply unclear` | The model read the reply as unsupported; the case stays with a reviewer and nothing is awarded | [Recorded reply reading](v4/evidence/submission-disputes-20261109/denial-model-job.json) |
| Ramp | More tools → Ramp records (from the Overview's Ramp card, **Open Ramp records**) | The sandbox bill, when it was read, and the note a person posted, read back by API | [Ramp notes](v4/submission/ramp.md) · [Read-back receipt](v4/evidence/demo-path-87/human-ramp-note.json) |

## What is authored, local or recorded

- **Authored:** the Northwind contract, amendment, usage records, invoices and vendor replies. Northwind Cloud and the buyer are fictional.
- **Local:** the vendor's side of the dispute is a counterparty built into Uptime, and credits go to a local ledger. No real vendor is contacted, and no money moves in Ramp. The claim packet and the response are approved by their exact content and filed to a local outbox with a receipt; this build does not display their text on any page.
- **Scripted:** the walkthrough's reviewer account, `scripted-test-reviewer`, is a test account, not a record of a person's approval.
- **Recorded:** the model readings were made on November 9 through the ordinary application routes, on authored contracts and two authored vendor replies: one call per rule family, so two per contract and six for the three contracts, plus one for each reply, none retried. Their provider receipts are kept. Northwind's own contract and its vendor's log request are handled by fixed rules, with no model call. The log request uses wording the rules know; a request worded differently goes to a reviewer.
- **Real:** the Ramp sandbox reads, and the note a person posted on sandbox bill `f74ba12c-95d0-582d-9f62-26d8057d1d37`. Since November 10, also the four notes Uptime posted through Ramp's API on three sandbox bills that were entered for the demo.

## Five questions, answered

**Where is this in Ramp?** Uptime runs beside Ramp as a separate local application. It is integrated with Ramp's developer API, read-only: when a person starts a read, it reads bills, vendors, transactions, purchase orders and approvals from the demo sandbox. The latest read, started by Ronok at 22:00 UTC on November 9, shows the sandbox bill's vendor (DocuSign) and invoice (DD-PREAPPROVAL). One thing has reached a Ramp bill: an evidence-gap note that a person typed and Uptime read back. Uptime itself has written nothing to Ramp. An agent-run posting was refused by an automatic approval review of the agent's action, so only a person may run that route. Vendor credits have no public create or apply operation in Ramp's API, and payment holds are not built. A browser side panel can show Uptime's page for the open Ramp bill beside Ramp. It reads only the tab's address and writes nothing; it is not a Ramp integration ([extension/README.md](../extension/README.md)).

**Where is the AI?** Claude Opus 5.5 proposes contract terms as data for wording the fixed rules do not know, and proposes a reading of a vendor's reply, with the cited text, for a reviewer to check. On November 9, one of two authored contracts written inside the supported grammar reached shadow; the other and a deliberate control were refused. An authored unclear reply was read as unsupported and went to a reviewer. A second authored reply, a request for the January log in other words, was read as a request for the right document; Claude also tagged the month, which the reply gives without a year, so Uptime's checks would not act on the proposal and the claim stayed with a reviewer ([record](v4/evidence/submission-disputes-20261109/reworded-model-job.json)). An operator records permission for each exact model request beforehand; in these runs that was the engineering agent running the demonstration. Code validates every proposal, computes every amount and enforces every deadline. A reviewer approves each candidate and each consequential step. The model cannot approve itself, invent evidence or set an amount.

**What happens on an unfamiliar contract?** Today it usually refuses, and says where. In the latest independent first pass, 12 actual Opus calls returned and all 12 proposals failed validation: 0 of 4 intended positive contracts reached shadow and all 6 were refused. All 8 dispute cases stopped at setup, so held-out dispute accuracy is unmeasured. Earlier first attempts (0 of 4, 3 of 6, 0 of 50) and a refused public SLA (Backblaze) stand. A refusal never produces a number. [Results](v4/evaluation-finish-20261109/RESULTS.md)

**Who authorizes follow-up?** A reviewer: in the product, an enrolled person; in the walkthrough, whoever is driving it, signed in as the scripted test account. The reviewer approves the claim packet and the response, then posts and applies the credit. Uptime runs only intake and the dispatch of steps a reviewer already approved. Correctly accepting a vendor's denial is not shown in any demo workspace. Automated tests cover it through the same signed routes. The independent acceptance run also exercised one such case over real HTTP: an announced maintenance window, corroborated by the customer's own notice, reached denial review with only acceptance offered and closed on a signed acceptance, with nothing awarded. A genuinely late filing could not be used, because the routes refuse to file after the cutoff. [Acceptance report](v4/submission/acceptance.md) No standing policy lets it act alone, and it stops on anything unexpected: a new legal ground, contradictory evidence, or uncertain delivery.

**What remains unimplemented?**
- Any write to Ramp by Uptime other than its fixed notes on matched bills, payment holds, and recording or applying vendor credits in Ramp.
- Real vendor delivery: the claim channel is still undecided.
- Reliable reading of unseen contracts, and measured accuracy on unseen dispute replies.
- A hosted installation with Ramp sign-in.

## Independent acceptance

A separate session checked the earlier frozen build `52f1a2f` (before the interface redesign) from a fresh clone, following only the published instructions, against expectations it sealed by digest before it saw the build.
- **The walkthrough:** sign-in and four reviewer decisions, with seven automatic steps between them.
- **Matched the sealed expectations:** the money, 58 of 58 citations and the authority recorded for each step.
- **Safety:** no unsafe acceptance, invented evidence or unauthorized money movement was observed.
- **The model work** was verified from its receipts. It is recorded, not live.
- **Not shown:** generalization. The independent cohort reached shadow on 0 of 4 contracts.
- **Ramp:** nothing reaches Ramp from Uptime.
- **The redesigned interface:** checked afterwards on `main` from an anonymous default clone with no extra step, at `08852a6` and again at `008c4af`. Every sealed figure, all 58 citations and each step's authority hold on `008c4af`. Of its three findings on the redesign, two are resolved: the routine-steps line now says a reviewer approves, and the Overview names "Dana Reyes · Scripted reviewer" with nothing opened. The third is partly resolved and lowered to P3: the case page's record section now says it does not track posting or application, but a second closed section, "Complete server case record", still prints "Posted USD 0.00" and "Applied USD 0.00" as the server sends them.

The [acceptance report](v4/submission/acceptance.md) has the evidence, the controls and its five ranked findings ("Bugs and risks, ranked by consequence"). It ends with two addenda on the redesigned interface: its three findings, and their recheck on `008c4af`.

## Evidence index

- [Capability matrix](v4/CAPABILITIES.md) · [Independent evaluation results](v4/evaluation-finish-20261109/RESULTS.md) · [Full test receipts](v4/evidence/submission-20261109/) ([listed by commit](v4/submission/COORDINATION.md#integration-and-suites)) · [for the frozen build `52f1a2f`](v4/evidence/submission-20261109/suite-52f1a2f.json)
- [Presentation storyboard and script](v4/submission/presentation.md) · [Engineering map](ENGINEERING-MAP.md) · [Decision records](v4/decisions/INDEX.md)
