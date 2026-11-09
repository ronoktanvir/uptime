# D06 action matrix

**Decision:** D06 "humans gate judgment", decided 2026-11-09 by Ronok. People approve sources and adapters, plus anything that rests on an ambiguous legal ground. Evidence retrieval and clearly bounded factual follow-ups may run under explicit, scoped standing policies that name the actor, evidence, amount/scope limits, expiry, retry and escalation. Model confidence never grants authority, and the existing semantic-review gates stay.

**Status:** this matrix is the D06 deliverable (owner W0). It records today's behavior and the D06 target for each action. **No standing policy is configured or implemented.** The [gaps](#gaps-to-reach-the-d06-target) at the end are what would have to be built before any action below runs under policy. Two D06 sub-questions are still undecided: the pre-reading screen, and whether one person may both prepare and execute an operator credit application.

Legend for "D06 target": **Person** (an authenticated human reviewer acts each time), **Policy-eligible** (may run under a standing policy that meets the limits in the row, once that policy exists), **Never** (no agent or policy, whatever the configuration).

## Sources, adapters and decisions

| Action | Today (code) | D06 target | Evidence and limits |
|:---|:---|:---|:---|
| Import a vendor source; generate a candidate | Operator request; public-only model job (`public_proposal_jobs.py`, `vendor_model_jobs.py`) | Person starts it | D10: public material only; one run, no retry on uncertain outcome |
| Interpret source, approve, activate, roll back, revoke an adapter (`onboarding.py` `ACTIONS`, `vendor_api.py`) | Reviewer with a signed request; activation behind the release gate or a bounded local exception | **Person** | Exact candidate version and digest; shadow checks pass. The local exception is spent (CalyxQuay REVOKED at revision 9) |
| Accept a reviewed vendor-reply interpretation (`correspondence_review.py`) | Reviewer | **Person** | Source-locked interpretation; multi-ground or conditional readings stay UNKNOWN |
| Accept a denial (`accept-denial`, decision 89) | Reviewer, after a deterministic match moves the case to `DENIAL_REVIEW` | **Person** (legal ground) | Re-runs the denial check; award, ledger and submissions unchanged |
| Close a familiar-wording maintenance denial | Previously closed automatically by the finite grammar | **Person**: through `DENIAL_REVIEW` plus explicit `accept-denial` (chosen 2026-11-09 under Ronok's delegation; new oracle version, frozen file untouched; W4 implements) | Same as above |
| Mandated accept-denial (`ClaimDecision` action) | Being added by W0 per Ronok's 2a (2026-11-09) | **Person** | Bound to the reviewed `basis_sha256` and `claim_state_sha256`; `max_amount_cents=0`; local purpose `claim-closure`; no money or outbound effect |
| Change workspace policy mode or cap (`policy.configure`) | Reviewer; `ASSISTED` is the default with cap USD 0.00 | **Person** | Cap 0–10,000 USD at cent precision; history is append-only |
| Enroll a source grant, issue a mandate, approve or sign a local exception | Host operator commands | **Never** by an agent | Nobody signs as Ronok or reads a reviewer key |

## Claims and disputes

| Action | Today (code) | D06 target | Evidence and limits |
|:---|:---|:---|:---|
| Approve a claim packet (`approve-claim`) | Reviewer; approval binds the packet digest | **Person** | Cited eligible evaluation; scope per D03/D04 |
| File an approved claim (`submit-claim`) | System executes once after approval (idempotent reservation). `POLICY_AUTOMATED` may also dispatch to the **simulated** counterparty within a positive cap (`policy.dispatch_allowed`) | **Person** approves. The simulator-only automation predates D06 and must not reach a real channel (D08 pending) | One filing per economic key; near-duplicate guard (D03) |
| Find supporting evidence (`prepare-response`, evidence refresh) | Operator or reviewer action; `evidence_refresh.py` is an explicit opt-in public fetch | **Policy-eligible** | Enrolled source grants only, for the exact artifact the vendor requested. In-period evidence only (decision 91). No customer data to models (D10) |
| Approve and send a factual follow-up that only supplies verified evidence the vendor requested (`approve-response`, `submit-response`) | Reviewer approves; 24-hour cooldown (`FOLLOW_UP`, `COOLDOWN`); a second request for the same proof stops; two failed sends move to `HUMAN_REVIEW` | **Policy-eligible**, only for this narrow case | Amount 0 (no new money claim); one claim; one requested proof; cooldown kept; expiry = the claim's filing cutoff; no retry on uncertain delivery; any non-matching or new ground escalates to a person |
| Any follow-up that argues a legal ground, rebuts an exclusion, appeals or proposes a settlement | Reviewer | **Person** | Never under policy |
| Receive a vendor reply or award | Service-signed delivery from the simulated counterparty | Automatic intake (not an action) | Interpretation of the reply follows the rows above |

## Money stages

| Action | Today (code) | D06 target | Evidence and limits |
|:---|:---|:---|:---|
| Post an award as a credit (`record-credit`, Local ledger) | Reviewer; amount ≤ award; idempotent | **Person** | Destination named "Local ledger"; never called a Ramp credit |
| Apply credit to a bill (`apply-partial`, `apply-balance`) | Reviewer; capacity triggers stop over-application | **Person** | Exact bill; remaining balance shown; stages never summed |
| Prepare an operator credit application in Ramp (W1 lineage) | Prepared and confirmed by read-back; never executed by Uptime | **Person** in Ramp | One-person versus two-person separation is undecided (D06 sub-question); recorded, not enforced |
| Post a Ramp comment, hold a bill, create or apply a Ramp credit | Not performed by Uptime; the agent posting retest is blocked | **Never** by an agent | Person-operated in Ramp only |

## Operations

| Action | Today (code) | D06 target | Evidence and limits |
|:---|:---|:---|:---|
| Restore a workspace; acknowledge reconciliation; revoke an installation (decision 96) | Operator commands; new mandates and native preparation stay blocked until acknowledged | **Person** | No scheduler and no standing policy configured |
| Read-only Ramp refresh with opt-in bounded retries | Operator command; retries only reads on network errors and 429/5xx | Person starts it | No write is ever retried |
| Read-only guide answers | Deterministic, cited; abstains when unsupported (D12) | Not an action | Cannot prepare or execute anything |

## Gaps to reach the D06 target

1. **Policy record.** `policy_revision` stores only mode and cap. A standing policy also needs actor (a `service-*` principal), permitted action class, evidence class, scope (claim/vendor), expiry and escalation route. That is a W0 schema change.
2. **Policy executor.** Nothing runs evidence retrieval or factual follow-ups under policy today; every run is started by a person. Building one needs the record above and a test for each limit in this matrix.
3. **Simulator automation.** `POLICY_AUTOMATED` dispatch of `submit-claim` predates D06. Keep it limited to the simulated counterparty and decide its future together with D08.
4. **Mandated accept-denial:** Ronok chose to add it (2a); W0 implements it.
5. **Undecided sub-questions:** the pre-reading screen, and preparer/executor separation for operator credit applications.

None of these gaps is needed for the November 10 demonstration. The demo runs every judgment step as an explicit reviewer action.
