# Novel dispute controls, workstream 89

These are **authored** public synthetic controls. The W4 dispute implementer wrote them on November 9, 2026 and froze them in Git before changing any application code. They are not independent, unseen, customer, or vendor material. A scripted test principal stands in for the reviewer; that is `SCRIPTED_NOT_ACTUAL_HUMAN` and is not evidence of human review accuracy or consent. Disclose this in presenter and handoff material. Product screens do not label it.

## What they test

The existing finite reply grammar (`uptime/correspondence_reason.py`) recognizes a bounded set of phrasings. The independent counterparty (`uptime/correspondence_vendor.py`) currently replies only in those phrasings. These controls supply vendor wording that the grammar does not recognize. They check that ordinary intake and the reviewed-interpretation path, not scenario IDs or expected wording, reach the right disposition:

- **Justified cure.** The counterparty asks for proof. The claimant drafts a supplement only after an authorized source delivers evidence that matches the filed scope. The original filing time and filing window carry over unchanged.
- **Accepted denial.** The counterparty's maintenance ground is substantiated by an independently authenticated notice that arrived at least 24 hours before the interval started. The case stops only after an explicit reviewer acceptance. Message order must not change the result.
- **Escalation.** Legal, discretionary, compound, changed-scope and injected text stays with a person. Model confidence or reviewer wording cannot create money or change the claim scope.

`cases.json` gives each case's authored text, the reading a reviewer would enter, the later evidence, and the frozen expected stage, category, disposition and ledger. The `counterparty_phrasing` block holds alternative renderings of the counterparty's own structured decisions. It does not change what the counterparty decides.

Before freezing, every text was checked to return `unknown` from the finite grammar at base commit `03b372e`. These controls exercise the reviewed path. They do not measure how well the grammar or a model generalizes. Expectations are never edited to make an implementation pass. A mismatch is recorded in `docs/v4/TEST-CHANGES-89-disputes.md`.
