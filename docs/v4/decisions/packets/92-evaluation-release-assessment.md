# Decision packet 92 — when to spend the frozen evaluation84 first attempts, and what bar the release assessment uses

Sanitized: no customer data, credentials, sealed expected answers or model outputs. The corpus is fictional, independently authored and already published in the private repository.

## Context

- A fresh corpus of 6 contract sources (4 intended-supported, 2 intended-refusal) and 12 vendor replies (6 supported meanings, 6 review controls) was frozen with sealed expected answers held outside Git before any runtime result. Only one first attempt per case counts; later runs on examined cases are remediation, never a replacement score. Earlier independent results remain 0/50 supported replies and 0/4 supported contract extractions (3/6 complete reply meanings).
- A pre-registered decision (ADR-0084) fixes four separate views (supported extraction/meaning, appropriate refusal/review, stages reached through the normal application, downstream checks under scripted authority) and forbids one pooled success percentage. It does not define a release threshold. The team decision on the release-evidence bar (D13) is pending.
- The project instructions say the November 7 demo authorization does not resume the frozen evaluation worktrees. The user has now assigned an owner for unseen evaluation, harness validation, freeze and release assessment, but has not explicitly said to execute inference.
- Offline preflight on the current integration source (no model call, gold only stat'ed): all 6 contract inputs pass the runner and extraction-profile input contracts. All 12 replies are refused at the normal claim-intake schema: account/agreement names containing spaces fail the identifier domain (pending team decision D03) and component/incident/invoice/region are universally required (pending D04). A harness may not slug names or invent scope values.
- The onboarding runner signs as a draft reviewer. On that path the application never resolves governing-fee authority, so the two monthly positive contracts cannot produce exact money in shadow preview; the authored fee sources stay local facts.
- Validation found and fixed a runner defect: a 90 s poll against an 80 s provider bound, with server teardown after 10 s, could lose the job's own terminal state. Fixed with tests using provider doubles; 46 focused tests pass.

## Options

1. **Split (preferred).** Freeze source/runner/config at one commit. Run the 6-case onboarding first attempt only after the user explicitly resumes evaluation and approves the exact frozen requests (at most 6 public-text calls, one attempt each, sequential). Hold all 12 dispute first attempts until D03 and D04 are implemented through the normal route; record the per-case blocker now. Pre-register that monthly positive amounts on the draft path are reported as "fee authority not exercised", not as arithmetic errors.
2. Run all 18 now: disputes would record 12 setup refusals as their first attempts, consuming the cohort without any semantic observation.
3. Run nothing until D03/D04 land, keeping both cohorts aligned in time.
4. Translate names to identifiers in the harness so disputes pass intake — rejected: invents economic identity.

Release assessment: assess against the existing implemented release gate (four independently signed reports — regression, security/financial, unseen vendor, unanticipated dispute — plus a separate human release witness, bound to tested source, fresh within 24 hours) and ADR-0084's pre-registered rules. Report gate-by-gate status. Do not add an accuracy threshold; state that D13 must supply one before "gate satisfied" can be claimed for unseen-vendor or dispute coverage.

## Strongest counterargument to the preferred option

Running onboarding before disputes splits one cohort across two source versions and could invite the identity repair to be tuned on examined onboarding behaviour. Also, an onboarding-only result risks being presented as "the evaluation" while the dispute half is absent.

## Questions

Rank the options. Is the split valid evidence or a protocol violation? Is assessing against the implemented gate, with D13 unresolved, honest? What falsification checks should precede the first real call? Would you dissent?
