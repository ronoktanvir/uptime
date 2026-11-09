# Unresolved blockers — November 9, 2026

Each blocker names its type, the owner who can move it, what unblocks it and the evidence. Types follow the checklist: **bug**, **missing functionality**, **unverified behavior**, **external dependency**. "Team" means a recorded human decision. Requirement IDs refer to [the completion checklist](REQUIREMENTS.md).

## Hard restrictions (do not work around)

| Blocker | Type | Owner | What unblocks it | Evidence |
|:---|:---|:---|:---|:---|
| Agent-run native Ramp posting retest refused by automatic approval review ("possible cybersecurity risk"). `bills:write` is already granted, so a missing scope is not the cause | External dependency | Team, through the supported platform/admin route | A platform-level resolution. No model, browser, credential or alternate implementation may reroute it | [Handoff](../TEAM-DECISION-HANDOFF.md#native-execution-restriction-is-not-another-missing-scope-decision), [grants](../evidence/native-demo-grants-20261106.json) |
| No Uptime-origin Ramp write, vendor credit, award or bill application exists. The only native write is a person-posted note, verified by read-back | External dependency | Team (D02, D09) | A chosen native record and a supported credit workflow, run by an authorized person | VAL-2, VAL-3, O5, [read-back](../evidence/demo-path-87/human-ramp-note.json) |
| General signed release gate unsatisfied: no current `release_attestation.json`. The CalyxQuay local exception was a one-time bounded alternative and is now COMPLETED | External dependency | Team (D13) | Independent regression, security, unseen-vendor and unseen-dispute evidence plus a human release witness | [DEMO-PATH-87](../DEMO-PATH-87.md), [recorded review](../evidence/local-review-88/recorded-review-20261109.json) |
| Independent evaluations 84–86 remain paused. Gold answers are sealed outside Git; no corpus inference has run | Unverified behavior | Team (D13) | A recorded decision to resume. The verification lane holds finished runners on `work/release-evaluation-gent8`, not integrated | AGENTS.md (November 7), [pause checkpoint](../evidence/pause-20261106/checkpoint.json) |

## Decided, implementation in progress

| Blocker | Type | Owner | Status | Evidence |
|:---|:---|:---|:---|:---|
| D03 identity domains disagree in eight places. Spaced names onboard but cannot file, and a Northwind month degrades to INSUFFICIENT_EVIDENCE | Bug | `agent1`, `work/identity-pricing-89` | Ronok chose D03-A with a blocking guard (no override). Not merged | [Alternatives](D03-D04-ALTERNATIVES.md), e86-01/04 receipts |
| D04 scope requires ten fields for every obligation | Bug | Same | Ronok chose D04-C. Not merged | Same |
| Near-duplicate override authority (who may let a case-variant account file) | Missing functionality | Team | Pending; the guard blocks without an override until decided | [Alternatives](D03-D04-ALTERNATIVES.md#opus-55-critique) |

## Pending team decisions that block named changes

| Decision | Blocks exactly | Checklist items |
|:---|:---|:---|
| D01 delivery target | What the submission must prove versus later pilot work | VAL-10, CP6, OBL-* |
| D02 native record | Which Ramp object carries an identity-preserving case | O5, VAL-2, RAMP-AUTH |
| D05 autonomous onboarding | Automatic family discovery; the operator still selects the profile | O3, ONB-1, ONB-3, DEMO-SLACK |
| D06 action autonomy | Standing-policy actions, follow-up policy editor, the remainder-dispute path, near-duplicate override, a mandated `accept-denial` decision (W4 request: `ClaimDecision` action plus a `claim-closure` purpose; today only the legacy unmandated reviewer can accept a denial, and the code fails closed), and retraction of a stored mistaken record | LC-1, LC-4, UI-7, GF-15 |
| D07 evidence/financial coverage | Currencies, tax allocation, MSA precedence, production evidence connectors, and whether one status record may stand for complete month coverage (W4 F3, labelled `PROVISIONED_SINGLE_INCIDENT_RECORD` meanwhile) | FIN-1, FIN-6, AG-3, IF-3 |
| D08 claim delivery channel | Any real outbound claim or response | INV-5, AG-5, RG-2 |
| D09 credits | Native credit create/apply and award attribution | O4, VAL-3, RAMP-4/5 |
| D10 model data policy | Any model call with case or customer data; the guide's model composer | O6, AG-8, GF-20 |
| D11 deployment | Hosting, OAuth installation, durable jobs, monitoring | OAUTH-1, CONT-1, STACK-3/4/5 |
| D12 guide scope | A conversational guide beyond deterministic cited answers | UI-8, API-14 |
| D14 review policy | Retiring blanket consultation (the November 5 single-critique rule applies now) | ORCH-2 |

## Engineering items (no decision needed)

| Item | Type | Owner | Next step |
|:---|:---|:---|:---|
| `scripts/independent_final_fix_verifier.py` exits 1: its pinned originals (`independent_final_review_probes.py`) changed in `5463bcb` after pinning (reported by the verification lane) | Unverified behavior | W8 | Decide whether to re-pin with a new receipt or restore the verifier input; never overwrite the old receipt |
| Committed `docs/v4/audit/baseline-v2.json` no longer passes its provenance check (verification lane report) | Unverified behavior | W8 | Reproduce on `work/integration-90`; add a new receipt |
| Append-only audit of refused intake deliveries (W5 request F7, recommended by Opus) | Missing functionality | W0 | Small `auth.py` change; schedule after D03/D04 lands |
| W3 findings F4 (private filing override lacks agreement/effective date), F6 (`evidence_sha256` format-only); F5 touches D03 | Bug / unverified | W3 (`agent2`), F5 with `agent1` | Routed November 9 |
| Slack negative onboarding case absent | Missing functionality | W3 | Add a public-source fixture that must yield unsupported/insufficient terms |
| Timed human rehearsal and Northwind film | Missing functionality | W8 / presenter | [Rehearsal](REHEARSAL.md) on the presenter's machine |
| Disk capacity: the volume is nearly full; concurrent full suites exhausted it on November 9 | External dependency | Machine owner | Free space outside the repository; agents may delete only their own temporary trees |
| Uncommitted sign-in change in `$HOME/uptime` (branch `fix/browser-signin-challenge`). Copied and committed here as `2205f0a`; the original was left untouched | Unverified behavior | Owner of that checkout | After merge, decide whether to discard the duplicate working-tree change; the 8777 listener still serves from that checkout |
| Old unmerged branches with unique commits: `remediate/native_workflow` (offline workflow CLI, HTTP contract tests), `remediate/blind`, `remediate/ind_hold2` (frozen holdouts), `feat/native-qualification-59` (disabled, must not merge) | Unverified behavior | W1 / W8 | Disposition per branch. Holdouts and native qualification stay unmerged |

## Integration status of the November 9 specialist branches

The live list is in [STATUS.md](../STATUS.md#november-9-integration) after the merge suite. Branches that need team approval before integration (evaluation runners) stay out.
