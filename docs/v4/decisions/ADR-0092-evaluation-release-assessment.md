# ADR 0092: Spend evaluation84 first attempts in two sub-cohorts; assess release only against the existing gate

**Date:** November 9, 2026. **Lane:** unseen evaluation, cross-component verification and release evidence (`work/release-evaluation-gent8`). **Status:** the preparation and assessment parts are adopted. The user explicitly resumed the onboarding sub-cohort on November 9. Its six first attempts ran and accepted **0/4 supported extractions**; see [receipt](../evidence/release-evaluation-gent8/onboarding84-first-attempts.json). Dispute inference also waits on the D03/D04 implementation. Ronok decided D03-A and D04-C on November 9 (recorded on `work/integration-90`); implementation is in progress on `work/identity-pricing-89`. The release threshold waits on team decision D13, which is still pending.

## Decision

1. **Validate and freeze before the first attempt.** The onboarding runner had a terminal-state defect, now fixed in `c1fa513`. An offline preflight shows:
   - all 6 contracts fit the current input contracts;
   - all 12 replies are refused at claim intake, by D03 (account/agreement identity domain) and D04 (universally required component/incident/invoice/region).

   See [harness validation](../evaluation-gent8/HARNESS-VALIDATION.md).
2. **Split the cohort.** The 6-case onboarding first attempt may run once the user explicitly resumes evaluation and a person approves the exact requests in the same sitting. Dispute first attempts wait until D03 and D04 are implemented through the normal route. Running them now would spend 12 first attempts on known setup refusals and yield no semantic observation. The harness may not translate names into identifiers.
3. **Pre-register the remaining rules before any result:**
   - transport and setup failure accounting;
   - a contamination firewall around onboarding outputs;
   - the fee-authority cap on the two monthly contracts;
   - gold and scoring custody.
4. **Assess release only against the existing gate.** Release is assessed against the implemented signed release gate (`scripts/release_evidence.py`, [RELEASE-EVIDENCE](../RELEASE-EVIDENCE.md)) and ADR-0084's pre-registered interpretation rules. No accuracy threshold is invented. The unseen-vendor and dispute rows read "not assessable: D13 absent". See [release assessment](../evaluation-gent8/RELEASE-ASSESSMENT.md).

## Alternatives

| Option | Assessment |
|---|---|
| Split, onboarding first after the user's go-ahead | **Chosen.** It produces semantic evidence for the half that is not blocked and preserves the dispute half. |
| Run all 18 now | Rejected. The 12 dispute first attempts would all be setup refusals that are already known. |
| Wait for D03/D04 and run all 18 together | Defensible. It keeps one source version, but delays the only result that is not blocked. |
| Slug names or invent scope in the harness | Rejected. It would manufacture economic identity and scope. |

## Opus 5.5 critique

There was one tool-free critique, `claude-opus-5-5`, session `6d98fd01-1326-48cb-9508-f5949a066746`, verified from the response's model usage. Records: [Packet](packets/92-evaluation-release-assessment.md) · [Response](reviews/92-evaluation-release-assessment.json).

- **Ranking:** split > wait > run all > translate.
- **Its view of the split:** valid if pre-registered with separate freeze commits and never pooled.
- **Gate rows:** honest only if they read "not assessable: D13 absent".
- **Authorization:** assigning an owner does not authorize inference. The user must explicitly resume evaluation and approve the exact requests.
- **Dissent:** conditional, until a transport-failure rule and a contamination firewall were pre-registered.

| Opus point | Response |
|---|---|
| Pre-register transport failure as attempt or void | **Adopted.** A failure after the POST is accepted is the first attempt at its actual stage, never void and never retried. A refusal before any provider call (zero calls) is a setup failure; it is preserved and is not a semantic result. |
| Contamination firewall | **Adopted.** Raw outputs and per-case results stay in owner-only directories outside Git. Only stage counts are published before the D03/D04 designs are committed. Implementers get no outputs. |
| Dry run past 80 s before the first real call | **Adopted.** A fake CLI ran through the real `SafePublicClaude` profile and hung for 75 s. The 60 s transport bound fired. The job was recorded `UNCERTAIN`/`provider_timeout` as terminal, with no retry. |
| Report the structural cap on the draft path | **Adopted.** 2 of the 4 supported contracts cannot show money. Onboarding evidence does not transfer automatically to the non-draft release path. |
| Commit the per-case blocker records first | **Adopted.** Done in the committed preflight receipt. |
| The 24-hour freshness rule makes any run done now stale for release | **Agreed.** Recorded in the assessment. |
| "Sealed before any runtime result" and "gold only stat'ed" need evidence | **Partly met.** The freeze commit, manifest hashes and pause checkpoint predate any runtime result. Preflight tests use an audit hook to prove that no gold path is opened. Independent authorship rests on the corpus author record in `CORPUS.md`, which was not independently re-verified. |
| **Hash the sealed gold now to compare it with the freeze record** | **Declined: dissent recorded.** Hashing reads the bytes. The corpus protocol says nobody reads gold until the first attempts are terminal. Gold presence, owner and mode were checked with `lstat`. The scorer must verify every gold hash before decoding. A tamper check that reads the gold early is a protocol change for the team, not the evaluator. |

## Validation

| Check | Result |
|---|---|
| Focused suites | 67 passed in 65.86 s on the branch at `c1fa513` plus probes: restart probe 1, preflight 5, onboarding runner 41 (35 original tests unchanged), dispute infrastructure 20. |
| Audit gate | 118/118 PASS on `c1fa513` against a fresh V3 baseline of 73 PASS / 45 FAIL. |
| Full suite | `uv run --locked pytest` on `487a32f`: 4,035 passed, 1 warning in 791.25 s, exit 0 ([receipt](../evidence/release-evaluation-gent8/verification-487a32f.json)). |

No existing integration test changed; see [test ledger](../TEST-CHANGES-release-evaluation-gent8.md).

## Rollback

- Revert `c1fa513` to restore the paused runner bytes (still preserved in `adc1c83`).
- Drop the branch to remove the preflight, probes and documents.
- Corpus, gold, earlier receipts and the paused worktrees are untouched.
- No inference, approval, gold read, Ramp action, signature or reviewer action was taken. There is nothing external to undo.
