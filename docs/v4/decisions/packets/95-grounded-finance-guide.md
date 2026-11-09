# Decision packet 95 — deterministic finance next-steps and a grounded read-only guide

Sanitized. Contains design and test facts only; no credentials, customer captures or sealed evaluation material.

## Question

For the authored walkthrough's finance view, is the implemented design the right way to (a) tell a reviewer the next useful action from case state, (b) show calculation inputs and financial stages without double-counting, and (c) answer questions with a grounded, read-only guide while the model-data policy (D10) and guide-scope decision (D12) remain unrecorded?

## Implemented choice

- A pure Python summary computed from the existing server projection on every read. Ordered items: reconciliation conflict (exact decimal comparisons: posted > awarded, applied > posted, posted without a single credit record or verified destination read-back, balance outside original), missing agreement, claim filing deadline (open or closed, from the claim's own cutoff and the workspace clock), required approvals (from the claim domain's offered approve operations), open price review (billed vs governing amount per invoice line), vendor-requested evidence, months whose usage evidence is missing (explicitly "undetermined, not ineligible"), then the server-offered next step. Ineligible months are never listed as missing evidence. No amount is derived; amounts are copied strings.
- Projection additions only: claim filing cutoff/month/pending approvals/requested artifact; price lines as strings; month calculation inputs copied from the evaluator result; actor per coverage history row.
- Guide: fixed fact templates copied from the projection, each with an ID and section. Keyword topic and month retrieval with ranking; every answer sentence cites a fact. Abstains for no topic, names absent from the case, and judgment/prediction/legal questions. Imperative action requests get a read-only answer naming the current control. No model call: model-composed wording is the change that depends on D10/D12, so it is not coded. A one-line client change sends guide questions with the read session instead of a write signature.
- Ramp: the view shows the configured destination (Local ledger) and states no Ramp bill is linked; it links only a server-supplied native record. Native record pages gain a direct "Open in Ramp" route.
- The recorded external reviewer history is not imported into this workspace; its vendor panel is labeled as this workspace's scripted record, and the vendor review screen lists who recorded each revision.

## Alternatives considered

1. Keep the existing assembled guide (fixed explanation plan per intent). Rejected: not grounded in the walkthrough case and cannot abstain.
2. Ship an LLM composer disabled behind a policy flag. Rejected by the integration owner: D10/D12 are unrecorded, so even dormant code is out of scope.
3. Compute next actions in the browser. Rejected: money/state logic belongs to tested server code.

## Evidence

New tests: 21 summary tests over a real 12-state run plus constructed conflicts, missing agreement, closed window and unknown-amount parsing; 31 guide tests including number-grounding (every number in an answer appears in the projection), abstention, read-only requests, injected source text and question injection with zero row changes across both databases; 2 real-browser tests with live sign-in, signed actions, server-side session expiry and recovery, keyboard focus, 390px width, load/guide failure and empty states. Focused regression of affected areas: 338 passed. Unchanged existing UI and workflow tests pass.

## Strongest counterargument

Keyword retrieval is brittle: paraphrases may abstain or surface a less relevant fact, and template text is less helpful than model wording. A reviewer may over-trust a confident deterministic answer that omits context.

## Authorization boundary

No new financial, native, model or reviewer authority. The guide holds the existing write lock briefly because all POSTs do; a future model composer must not run under it.

## Rollback

Revert the view/guide commits; the projection additions are additive and unused elsewhere.
