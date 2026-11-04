# Independent dispute replay

All four examples use the ordinary Twilio Services APIs availability branch of the April 9, 2026 agreement. Sections 1 and 3 define the eligible fee basis, threshold, rate, claim contents and filing period. Section 4 contains the maintenance and short-interval exclusions. The simulator models one synthetic account and one continuous status interval per claim. It does not evaluate SendGrid connection rates, premium editions, negotiated overrides or multi-incident aggregation. [Twilio APIs SLA](https://www.twilio.com/en-us/legal/service-level-agreement/twilio-apis)

The published agreement is the public source. All records of incidents, notices, customer charges, approvals, exchanges and credit awards are fixture data. The replay uses UTC month boundaries. The 24-hour contact cooldown and maximum of one evidentiary supplement are demo policies. The simulator keeps supplements within the original claim window as a conservative filing policy. This is not a representation that the SLA sets an independent appeal deadline.

## Independent inputs and held-out answers

- The claimant reads its own dossier and archives under `claimant/`. It may submit only the scoped documents already in that dossier. The simulator requests an account/component record in the cure case because the summary fails to substantiate component scope. The named attachment is a simulated evidentiary request, not a prescribed Twilio document type.
- Local preflight independently checks agreement version, included API, plan, account scope, the continuous status interval, the original exclusion screen, the open filing window, documentary support and line-level charges. An unresolved or unsupported item blocks original filing. A previously unknown maintenance notice may be retrieved from the customer's support archive after the simulator supplies a specific denial reason.
- The simulator reads `simulator/records.json`, its own fee ledger, incident classification and document digests. It receives an approved ticket, not the case ID, claimant conclusion or oracle. Rehashing a fabricated record cannot register it with the simulator.
- `oracle/v1.json` was committed at `a01e9f8` before implementing the runtime. Only tests load it. SHA-256 is `f74f74098229c949956536fce23c191ff1fe49d0de062f7f6accf0aa108823f8`. The same team designed these synthetic fixtures. Mutation tests deliberately introduce overpayment and an improperly trusted attachment to check that the held-out expectations detect both.
- `traces/` contains the four actual replay outputs, with action order, approvals, digest-bound receipts, replies, postings and the terminal decision. All cases start in DRAFTED. The cure and partial award never create applied or posted credit.

## Service integration

The W0 service provisions a demo tenant explicitly. Its principal must come from authenticated server state. Unknown tenants read no cases. Every mutation checks the role again, including duplicate submissions. A viewer can read its own tenant's cases. Only a reviewer can act.

```python
from uptime.contracts import Principal
from uptime.disputes import DisputeDesk

desk = DisputeDesk("runtime/workbench.sqlite")
desk.seed("bears")
principal = Principal("bears", "demo-reviewer", "reviewer")
rows = desk.cases(principal)
case = desk.case(principal, "dispute-cure")
case = desk.act(principal, case["id"], case["actions"][0]["id"])
```

`case` and `act` return the CP1 case-detail JSON with stage, trace, sources, evidence, timeline, clauses, financials, actions, approval-bound submissions, vendor replies, filing cutoff and next contact time. The `ledger` object is authoritative for estimated, claimed, awarded and disputed remainder amounts. Posted and applied remain zero until joined to separate reconciliation records. Amounts are USD decimal strings. A duplicate successful action returns the latest state without repeating its side effect. Permission errors, unknown case IDs and `DisputeConflict` map to HTTP 403, 404 and 409.

Only an affirmative local dispatch grant on the cured-case fixture makes an already approved, independently eligible initial ticket a `policy_dispatchable` candidate. Redacted replay attachments, an intact approval digest and the server's separate global amount threshold govern automated dispatch. No response, unresolved exposure or settlement is eligible. The default mode is assisted.

A simulated send and vendor receipt commit in one SQLite transaction. A lost HTTP response can be replayed under the same action ID across process restarts. A transient simulator failure records its attempt under the unchanged idempotency key. A second failure routes to a human. The vendor's decision function has no transport or side effects.

Actions are stage-dependent and should be rendered from `case["actions"]`. The full cured trace uses `approve-claim → submit-claim → prepare-response → approve-response → advance-cooldown → submit-response`. The explicit replay action advances the display clock. A real injected clock disables this action and requires elapsed time. Expiry closes the case on attempted action. The durable receipt stores the approved ticket digest, actor and submitted artifact references.

## Reproduction

```sh
uv run --locked pytest -q tests/test_disputes.py
uv run --locked python -m uptime.disputes_replay dispute-cure
uv run --locked python -m uptime.disputes_replay dispute-denial
uv run --locked python -m uptime.disputes_replay dispute-review
uv run --locked python -m uptime.disputes_replay dispute-partial
```
