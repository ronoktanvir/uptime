# Decision packet 89: reviewed denial acceptance and the dispute trace

Sanitized for an independent critique. It contains public repository source and same-team authored synthetic controls only. There are no credentials, customer captures, private evaluator material or sealed answers.

## Question

How should the dispute workflow accept a correct contractual denial when the vendor's wording is outside the finite reply grammar, without letting model output, reviewer wording or message order change money or claim scope?

## Current evidence (base `03b372e`)

- `CorrespondenceDesk` parses vendor replies with a finite grammar. Unfamiliar wording becomes `HUMAN_REVIEW` with reason `unknown`.
- The reviewed-interpretation bridge (`InterpretationDesk`, decision 60) asks for the reviewer's own blind reading, then per-proposition verdicts, then a deterministic preview. `prepare` was allowed only for `RESPONSE_DRAFTED`, `NEEDS_EVIDENCE` and `AWAITING_NOTICE`. A deterministic `DENIAL_ACCEPTED` projection was only `closure_suggested`.
- Probe on base code: the outcome depended on message order. If the reviewer prepared a maintenance reading before the independent notice arrived, the later notice closed the claim automatically (`AWAITING_NOTICE → DENIAL_ACCEPTED`). If the notice arrived first, the claim stayed in `HUMAN_REVIEW` indefinitely, with closure only suggested.
- Probe on base code: after a vendor availability denial, the claimant drafted a rebuttal. Later evidence then made the claim ineligible, but the stage stayed `RESPONSE_DRAFTED` with no action and a full disputed remainder.
- The finite-grammar path already closes a confirmed maintenance denial automatically. That predates pending team decision D06 (person vs standing policy). It is preserved and not extended.
- The counterparty simulator answered only in phrases the claimant grammar recognizes.

## Constraints

D03, D04, D06, D08 and D13 are pending. Do not change `Scope` identity, required scope fields, stored hashes or authority files. There is no automatic or policy-driven acceptance. There is no new financial effect. An unresolved waiver, condition or scope ground must not be erased. Models propose; deterministic code controls money and authority.

## Options

1. **Status quo.** Closure stays informational. A correct denial in novel wording never stops, and message order still decides whether one closes.
2. **Bridge-only acceptance.** `prepare` directly applies `DENIAL_ACCEPTED` when the projection says so. This is simple but makes interpretation and stopping one step, and it leaves the review-before-notice auto-close in place.
3. **Recommended, implemented in `3454b33`.** A reviewed reading that the deterministic rules substantiate reaches a non-terminal `DENIAL_REVIEW` in either order. A separate explicit `accept-denial` action, with reviewer role, write authorization and the observe-only gate, re-derives the basis from current evidence and terms at transaction time. It then closes with `denial_acceptance` = {actor, at, basis, basis_digest}. Ledger, award and submissions are unchanged. Later contradictory evidence or a conflicting reply reopens the case to `HUMAN_REVIEW` and keeps the acceptance as history. Compound, conditional, rejected or unsupported readings still map to `unknown`, so they escalate. Accepting a denial is not limited by the filing window, because it sends nothing.
4. **Manual "close, no action" reviewer button without a deterministic basis.** Rejected: it lets human wording alone relinquish a valid claim.

Additive pieces in the same commit:
- A read-only `GET /trace` that classifies each counterparty assertion as MISSING_EVIDENCE, CONTRACTUAL_DENIAL, INCORRECT_FACTUAL_ASSERTION, UNRESOLVED_DENIAL, PARTIAL_AWARD, AWARD_REPORTED, CHANGED_SCOPE or AMBIGUOUS_GROUNDS. It links each to its source span and governing clauses, and lists the deterministic checks, permitted actions and disposition. Another reviewer's reading is shown only after the requester's own blind entry.
- A rebuttal or cure that loses its eligible basis returns to `HUMAN_REVIEW`.
- The counterparty's `decide_claim` (a structured code from private records) is separated from `render` (wording). The historical strings are byte-identical.

## Strongest counterargument

The reviewer supplies the meaning of novel text. A semantic mistake, for example marking a waiver as plain maintenance, can still lead to an explicit acceptance whenever the deterministic maintenance check independently holds. The deterministic check verifies the *ground*, not that the vendor's text contains *only* that ground. Full byte coverage and proposition-level verdicts reduce this risk but do not remove it.

## Falsifiers

The tests in `tests/test_correspondence_disposition_89.py` cover:
- order independence;
- short or missing notice;
- a compound ground;
- legal and injected text;
- partial and changed-scope awards;
- stale terms, the observe-only gate, a cross-tenant actor and a viewer;
- a model candidate used as a review;
- a `confidence` field;
- replies after acceptance and contradictory evidence after acceptance;
- out-of-order receipts;
- a silent counterparty;
- the rebuttal-withdrawal fix;
- mounted HTTP routes.

Result: 30 passed. The existing 849 dispute and correspondence tests pass unchanged.

## Rollback

Revert `3454b33`. Rows saved in `DENIAL_REVIEW` would then have no action. The rollback note maps them to `HUMAN_REVIEW` with no data loss. `denial_acceptance` records remain inert history.
