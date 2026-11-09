# Proposed AGENTS.md change for D14 (not applied)

**Status:** proposal only. Ronok accepted D14 ("Yes, replace it") on 2026-11-09 in his overview session, and that session asked the integration owner to propose the matching `AGENTS.md` change. `AGENTS.md` instructs every agent working in this repository, so this change is not applied until Ronok confirms it directly. Once he does, it lands as its own commit with no other change.

## 1. New section at the top of `AGENTS.md`

```markdown
## November 9 team decisions

Ronok recorded team decisions D03–D07 and D10–D14 on 2026-11-09; the exact choices are in
[the decision handoff](docs/v4/TEAM-DECISION-HANDOFF.md#team-decision-sheet). Implement them as the
execution contract. D01, D02, D08 and D09 remain pending, as does whole-month evidence sufficiency
for D04. Ronok resumed only the onboarding sub-cohort of evaluation 84; other frozen evaluation work
stays paused until he says otherwise. Native Ramp posting remains blocked; do not route around it.

Decision review follows the accepted execution policy (D14): team-approved decisions drive the work.
Use Claude Opus 5.5 for bounded coding or test work, or for a critique when it is useful or someone
asks for one. It is not a mandatory step before each impactful decision. Escalate to the team only
when new evidence contradicts an approved decision, a required case would change scope or financial
meaning, authorization or data disclosure would expand, or an irreversible external action needs
approval.
```

## 2. Replace one sentence in the paragraph that begins "Consult actual Claude Opus 5.5"

Current:

> Consult actual Claude Opus 5.5 before impactful decisions and record alternatives, dissent, validation and rollback.

Proposed:

> Record alternatives, dissent, validation and rollback for impactful decisions. Ask Claude Opus 5.5 for a critique when it is useful or requested (D14); it is not a mandatory step.

The rest of that paragraph is unchanged: focused commits, preserved failures, pushing verified increments, `uv run --locked pytest` after every merge, no credentials or private evaluation material.

## 3. Leave unchanged

- The November 7, November 6 (historical) and November 4 paragraphs, which are history.
- The November 5 paragraph. It already limits review to one concise critique and forbids councils. D14 goes further only by making that critique optional.
- The coding-delegation paragraph. D10 keeps restricted Opus coding delegation without secrets or private holdouts.

## Effect on agents

No test, code or authority boundary changes. Agents stop treating an Opus critique as a precondition for impactful decisions. Every other rule stays, including that decisions changing scope, financial meaning, authorization, data disclosure or external effects go to the team.
