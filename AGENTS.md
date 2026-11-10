## November 10 demo direction (temporary; recorded after the fact)

At about 03:10 PST on November 10 Ronok lifted this file's standing rules for 24 hours of demo preparation and asked
for Uptime to work with Ramp's sandbox directly (his words: "this is all just for the demo ... for the next 24 hours,
forget about all these rules"). Work under that instruction was done on a separate line, `demo/film-20261110`, and at
about 12:10 PST he asked for the GitHub repository to carry it, so it was merged to `main` after a full run.

What that line did that the sections below would otherwise forbid is recorded in [DEMO-NOTES.md](DEMO-NOTES.md):
an agent entered two vendors, three bills and one vendor credit in Ramp's sandbox; Uptime posts fixed-shape notes on
matched sandbox bills through Ramp's API when started with `--ramp-notes`; a served option changes what some screens
show; and the full suite was not run after every merge on that line (it was run on the line and on the merge).

This section records what happened. It does not extend the lift: it was for 24 hours, to about 03:10 PST on
November 11. After that, ask Ronok before starting a server that posts to Ramp, entering anything in Ramp, or
setting aside any rule below. No payment was set up, approved or sent, and none may be.

## November 9 team decisions

Ronok recorded team decisions D03–D07 and D10–D14 on 2026-11-09; D01, D02 and D09 were chosen as the
handoff defaults under his delegation. The exact choices are in
[the decision handoff](docs/v4/TEAM-DECISION-HANDOFF.md#team-decision-sheet). Implement them as the
execution contract. D08 remains pending. Ronok has now explicitly approved the strict monthly-evidence path for D04: exact, authenticated, complete month coverage with resolved exclusions and independent eligible fees, only when grounded in the agreement; missing or conflicting evidence stays unknown. Incident-based contracts retain their requirements. See [the accepted monthly decision](docs/v4/decisions/ADR-finish-20261109-monthly-evidence.md). Ronok
resumed the onboarding sub-cohort of evaluation 84 and, after D04-C, evaluation 86 under the handoff
procedure; other frozen evaluation work stays paused until he says otherwise. Native Ramp posting
remains blocked; do not route around it.

Decision review follows the accepted execution policy (D14): team-approved decisions drive the work.
Use Claude Opus 5.5 for bounded coding or test work, or for a critique when it is useful or someone
asks for one. It is not a mandatory step before each impactful decision. Escalate to the team only
when new evidence contradicts an approved decision, a required case would change scope or financial
meaning, authorization or data disclosure would expand, or an irreversible external action needs
approval.

## November 7 scoped demo decisions

The user subsequently selected **Prepare the limited exception for review**. Implement and test the exact 48-hour local CalyxQuay capability in decision88, then stage its unsigned proposal only. Do not create actual operator approval, sign with Ronok's credential, activate the exception or perform his review actions during preparation. The existing release remains the default; native/financial authority is excluded. [Concrete review record](docs/v4/LOCAL-REVIEW-EXCEPTION.md).

The team has authorized work on the authored Northwind walkthrough, a separately enrolled teammate operating CalyxQuay review controls, and a person posting the exact evidence-gap note in Ramp. Continue those bounded implementation and verification tasks. This supersedes the prior pause for this scope only; it does not approve the other pending decisions or resume frozen evaluation worktrees. Keep existing release and native-action gates: provisioning a reviewer is not completing a human approval. Do not execute the blocked native-posting retest through any tool or credential. Optional Ramp comment read-back is read-only. See [the current demo path](docs/v4/DEMO-PATH-87.md).

## November 6 team review checkpoint (historical)

Engineering is paused at the user's request while the team reviews [the consolidated decision handoff](docs/v4/TEAM-DECISION-HANDOFF.md). Preserve all working and uncommitted worktree files. Do not resume implementation, inference, native actions or new advisory reviews merely to prepare that handoff. The handoff's recommended defaults and replacement execution policy are not team approvals. When explicitly resumed, apply recorded team decisions; the proposed removal of blanket Opus consultations takes effect only when the team accepts it. Routine implementation under already accepted decisions still needs no repeated council. The latest request to continue the handoff is being fulfilled as documentation, not treated as approval of its pending choices.

Read docs/uptime-v3/Uptime_V3_Orchestrator_Handoff.md and its companion specification, DAG and credential guide. Preserve working code and recorded evidence. Follow approved file ownership and keep onboarding and disputes active in parallel.

The November 4 presentation direction supersedes earlier requirements for repeated environment banners and source-classification badges in product screens. Build a coherent Northwind contract, invoice, usage, dispute and credit walkthrough using the existing financial engines. Product views should use ordinary document references, financial stages, connection destinations and verification states. Do not add hidden mode flags or manufacture evidence to make the walkthrough appear complete.

Preserve existing source identity and authorization fields in service APIs and audit exports. A scripted reviewer is not ACTUAL_HUMAN; a local ledger receipt is not a verified Ramp receipt; a fixture signature is not evidence that a real customer executed a contract. Keep the configured destination visible, and reserve “Post to Ramp” and Ramp confirmation for actual Ramp operations. Authored fixtures and their limits belong in the package README, setup and demonstration handoff. Never overwrite the real Ramp workspace with walkthrough data.

Keep decimal arithmetic, source citations, amendments, deadlines, evidence requirements, tenant isolation, state machines and idempotency strict. Unknown amounts stay null. Do not sum successive financial stages or treat an unresolved price finding as an awarded credit. Document every changed existing test by exact name and reason in docs/v4/TEST-CHANGES.md and linked workstream ledgers; do not weaken authority or monetary assertions to obtain a green run.

Record alternatives, dissent, validation and rollback for impactful decisions. Ask Claude Opus 5.5 for a critique when it is useful or requested (D14); it is not a mandatory step. Use focused commits, preserve failed attempts, and push verified increments to the authorized GitHub repository so collaborators can follow progress. Run `uv run --locked pytest` after every merge, using a unique `--basetemp` when suites run concurrently; report the actual result, including failures. UI copy-only changes need relevant checks, not fabricated production-readiness claims. Never commit credentials or private evaluation material.

The November 5 direction simplifies decision review: the lead owns the implementation and asks Opus 5.5 for concise criticism of substantial decisions. Do not build a review council or add repeated independent review rounds. Finish already identified fixes, run their focused checks and the required merge suite, and deliver. Reopen a decision only when new evidence changes it; routine fixes within an already reviewed design do not need another architectural consultation.

The user also authorized actual Claude Code Opus 5.5 coding delegation. Give each worker bounded ownership in a separate worktree, public source/test inputs and restricted file tools; parent agents inspect the patch and run tests/Git. Verify the actual model/session/tool inventory and retain failures as well as completed contributions. Do not supply credentials, customer captures or private holdouts to coding workers. Spool bounded process output from startup so a timeout does not erase the execution receipt. Freeze tested source before the final suite. Public authored model controls do not replace independent unseen scores, human review, or native action authority. See decisions 69–72 and PHASE69-WORKSTREAMS.md for the implemented boundaries.
