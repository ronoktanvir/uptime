# Submission readiness: coordination record

Started November 9, 2026, 12:50 PST, at Ronok's request. One coordinator turns the November 9 judge review into a better product and a two-minute presentation. This file is the dependency map: owners, branches, tested commits, blockers and evidence. It is a dated record, updated after meaningful events; it does not show that any agent is still running.

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
| 6. README, evidence, film | to be assigned after the judge session's drafts are located | `work/submission-presentation-20261109` | `README.md`, the judge-facing guide, screenshots, storyboard |

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

## Status log

- **13:05 PST.** Baseline and classification recorded. Integration worktree created from `55ea607`. Roles 1–4 briefed. Role 5 follows the freeze; role 6 follows the judge session's drafts.
