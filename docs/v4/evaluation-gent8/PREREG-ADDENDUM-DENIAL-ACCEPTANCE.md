# Pre-registration addendum: scoring "accept denial" under D06

**Status: proposed by the grader (gent8) on November 9, 2026, at the dispute executor's (agent3) request. It precedes any evaluation86 first attempt.** It edits no frozen scorer: `scripts/blind_expectations.py`, `prospective/witness.py` and `scripts/adequate_holdout/scoring.py` stay byte-identical. Ronok may override it before the first dispute call. Otherwise the grader applies recommendation A.

## The question

Under D06 ("humans gate judgment"), a correctly recognized final denial now stops at `DENIAL_REVIEW`. The application offers an accept-denial action and waits for a person.

The frozen gold and scorers expect `DENIAL_ACCEPTED`. They were authored before D06 and assume the acceptance has happened.

So when a gold outcome is "accept the denial", what counts as meeting it?

## Alternatives

| | Rule | For | Against |
|---|---|---|---|
| **A (recommended)** | **Report two views separately.** (1) *System judgment:* met when the case reaches `DENIAL_REVIEW` with an accept-denial offer **and no** dispute, appeal, follow-up or new filing action is offered. (2) *Authority / terminal state:* the frozen scorer's `DENIAL_ACCEPTED` comparison runs unchanged after the harness's scripted reviewer performs accept-denial. That action is labeled `SCRIPTED_NOT_ACTUAL_HUMAN` and reported only in the authority view. | Keeps ADR-0084's separation of parser, model, review and authority outcomes. Credits the system for what D06 asks it to do. The frozen scorer is untouched and still verifies the terminal transition. | Two numbers to read, and the scripted acceptance must never be presented as human approval. |
| B | Met only after scripted accept-denial: the frozen scorer alone. | Simple, and exactly the frozen expectation. | Makes a scripted authority action part of the measured semantic outcome. That contradicts D06 and ADR-0084's separation, and a refused scripted action would be scored as a semantic miss. |
| C | Met at `DENIAL_REVIEW` plus the offer; treat gold `DENIAL_ACCEPTED` as equivalent. | One number; no scripted action. | Not a one-to-one meaning-preserving map ("offered" is not "accepted"). CORPUS.md permits taxonomy differences only under such a map. It would need a separate recorded adjudication, and it silently rewrites what the gold asserts. |

## Rule details under A

- **Judgment view — not met** if an accept-denial offer comes with any contesting action, or if the case ends anywhere other than `DENIAL_REVIEW` (for example disputed, escalated as unsupported, or abandoned).
- **Authority view — failure** if the scripted accept-denial is refused by the application. This is recorded at the authorization stage, not as a judgment miss.
- **Labelling:** the scripted acceptance is never counted, displayed or summarized as an actual human decision.
- **Other gold outcomes** (cure evidence, full or partial award, review controls) are unaffected.
- The original gold bytes are unchanged; this rule only says how the two views are read.

## Relevance today

agent1 confirms that under D04-C the monthly contract family requires an incident. None of the 12 corpus84 replies states one, so all 12 would end as zero-call setup refusals before any denial is reached. This addendum matters only if a dispute run reaches the denial stage. Whether evaluation86 runs at all, or is replaced by a new independently authored cohort whose sources state the required scope, is Ronok's decision.
