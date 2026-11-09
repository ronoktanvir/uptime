# Uptime: a guide for judges

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
| What runs by itself | Approve the claim, then watch **Activity** | Filing, the vendor's reply, the requested log and its verification happen without a click; Uptime stops for the response approval | [Dispute automation notes](v4/submission/disputes.md) |
| The decisions that stay human | The four approvals | Claim, response, posting and application. Each approval is bound to the exact content approved | [Action matrix](v4/integration90/D06-ACTION-MATRIX.md) |
| The settlement | **Overview** after the fourth decision | April's $11,000.00 bill becomes $8,600.00 in a local ledger: one credit, applied once | [Workflow read-back receipt](v4/evidence/demo-path-87/northwind-socket.json) |
| The model | A separate recorded workspace (its own sign-in; see the runbook) | Corvid Ledger: a recorded Claude Opus 5.5 reading, 11 exact quotations, validated and staged in shadow; Halden Relay refused. Northwind itself uses fixed rules | [Runbook](v4/submission/onboarding-runbook.md) · [Call receipts](v4/evidence/submission-onboarding-20261109/genuine-calls-summary.json) |
| An unfamiliar reply | A second Northwind workspace made with `--counterparty-reply unclear` | The model read the reply as unsupported; the case stays with a reviewer and nothing is awarded | [Recorded reply reading](v4/evidence/submission-disputes-20261109/denial-model-job.json) |
| Ramp | The Ramp record panel | The sandbox bill, when it was read, and the note a person posted, read back by API | [Ramp notes](v4/submission/ramp.md) · [Read-back receipt](v4/evidence/demo-path-87/human-ramp-note.json) |

## What is authored, local or recorded

- **Authored:** the Northwind contract, amendment, usage records, invoices and vendor replies. Northwind Cloud and the buyer are fictional.
- **Local:** the vendor's side of the dispute is a counterparty built into Uptime, and credits go to a local ledger. No real vendor is contacted, and no money moves in Ramp.
- **Scripted:** the walkthrough's reviewer account, `scripted-test-reviewer`, is a test account, not a record of a person's approval.
- **Recorded:** the model readings were made on November 9 through the ordinary application routes, on authored contracts and an authored unclear reply, one call each with no retries. Their provider receipts are kept. Northwind's own contract and its vendor's log request are handled by fixed rules, with no model call.
- **Real:** the Ramp sandbox reads, and the note a person posted on sandbox bill `f74ba12c-95d0-582d-9f62-26d8057d1d37`.

## Five questions, answered

**Where is this in Ramp?** Uptime runs beside Ramp as a separate local application and reads bills, vendors, transactions, purchase orders and approvals through Ramp's developer API, in the demo sandbox. One thing has reached a Ramp bill: an evidence-gap note that a person typed and Uptime read back. Uptime itself has written nothing to Ramp. An agent-run posting was refused by an automatic approval review of the agent's action, so only a person may run that route. Vendor credits have no public create or apply operation in Ramp's API, and payment holds are not built.

**Where is the AI?** Claude Opus 5.5 proposes contract terms as data for wording the fixed rules do not know, and proposes a reading of a vendor's reply, with the cited text, for a reviewer to check. On November 9, one of two authored contracts written inside the supported grammar reached shadow; the other and a deliberate control were refused. An authored unclear reply was read as unsupported and went to a reviewer. An operator records permission for each exact model request beforehand; in these runs that was the engineering agent running the demonstration. Code validates every proposal, computes every amount and enforces every deadline. A reviewer approves each candidate and each consequential step. The model cannot approve itself, invent evidence or set an amount.

**What happens on an unfamiliar contract?** Today it usually refuses, and says where. In the latest independent first pass, 12 actual Opus calls returned and all 12 proposals failed validation: 0 of 4 intended positive contracts reached shadow and all 6 were refused. All 8 dispute cases stopped at setup, so held-out dispute accuracy is unmeasured. Earlier first attempts (0 of 4, 3 of 6, 0 of 50) and a refused public SLA (Backblaze) stand. A refusal never produces a number. [Results](v4/evaluation-finish-20261109/RESULTS.md)

**Who authorizes follow-up?** A reviewer: in the product, an enrolled person; in the walkthrough, whoever is driving it, signed in as the scripted test account. The reviewer approves the claim packet and the response, then posts and applies the credit. Uptime runs only intake and the dispatch of steps a reviewer already approved. Correctly accepting a vendor's denial is demonstrated on other dispute cases through the same signed routes, not in the Northwind walkthrough. No standing policy lets it act alone, and it stops on anything unexpected: a new legal ground, contradictory evidence, or uncertain delivery.

**What remains unimplemented?**
- Any write to Ramp by Uptime, payment holds, and recording vendor credits in Ramp.
- Real vendor delivery: the claim channel is still undecided.
- Reliable reading of unseen contracts, and measured accuracy on unseen dispute replies.
- A hosted installation with Ramp sign-in.

## Evidence index

- [Capability matrix](v4/CAPABILITIES.md) · [Independent evaluation results](v4/evaluation-finish-20261109/RESULTS.md) · [Latest full test receipt](v4/evidence/finish-20261109/final-805dd1c.json)
- [Presentation storyboard and script](v4/submission/presentation.md) · [Engineering map](ENGINEERING-MAP.md) · [Decision records](v4/decisions/INDEX.md)
