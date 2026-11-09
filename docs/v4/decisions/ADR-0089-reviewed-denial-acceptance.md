# Decision 89: reviewed denial acceptance and an auditable dispute trace

Date: 2026-11-09. Workstream W4 (disputes). Branch `work/dispute-disposition-89`. Status: implemented and focused-tested. The integration owner runs the full suite after merge.

## Context

The assignment asks for three outcomes when a counterparty uses new wording that did not come from fixtures: a justified cure, an accepted denial, and escalation of ambiguous disagreements. Neither model confidence nor reviewer wording may change money or claim scope.

At base `03b372e`:
- The finite reply grammar handled only known phrasings.
- The counterparty simulator spoke only those phrasings.
- The reviewed-interpretation bridge (decision 60) kept closure of a correct denial informational.

Two probes showed concrete defects:
- **Order dependence.** A reviewed maintenance reading closed the claim automatically if the independent notice arrived *after* preparation. If the notice arrived *before*, the claim stayed in `HUMAN_REVIEW` indefinitely.
- **Stale rebuttal.** A drafted availability rebuttal stayed `RESPONSE_DRAFTED`, with no action, after later evidence made the claim ineligible.

Team decisions D03, D04, D06, D08 and D13 remain pending. The integration owner set these boundaries:
- acceptance must be an explicit authenticated human action;
- there is no automatic or policy-driven stop;
- there is no new financial effect;
- an unresolved waiver, condition or scope ground must not be erased.

## Decision

**Option 3 in the [decision packet](packets/89-reviewed-denial-acceptance.md).**

- **A new stage.** When an authenticated reviewer's reading of novel text maps to a single supported denial ground, and the existing deterministic engine substantiates that ground from authenticated evidence and governing terms, the case moves to `DENIAL_REVIEW`. This happens in either message order.
- **Explicit acceptance.** The only way out is the reviewer action `accept-denial`. It needs reviewer role, write authorization and the observe-only gate. Inside the write transaction it re-derives the basis from current evidence and terms, then records `denial_acceptance` = {actor, at, basis, basis_digest}.
- **No money effect.** Claimed, awarded, posted and applied amounts and submissions are unchanged. Only the disputed remainder becomes zero, because the dispute is closed.
- **Reopening.** A later conflicting reply or contradictory evidence returns the case to `HUMAN_REVIEW`. The acceptance is kept as history.
- **Escalation is preserved.** Compound, conditional, rejected, unsupported and changed-scope readings still map to `unknown` and escalate.
- **Pre-existing behavior kept.** The finite-grammar path's automatic closure of a confirmed maintenance denial is unchanged. It is recorded as D06-dependent.

The same change also:
- returns a drafted rebuttal or cure to `HUMAN_REVIEW` when later evidence removes its eligible basis;
- adds `GET /api/correspondence/claims/{id}/trace`, a read-only trace;
- separates the counterparty's structured `decide_claim` decision from `render` wording. Historical strings are byte-identical.

## Trace

The trace contains:
- evidence, with issuer, grant, digest and arrival times;
- each vendor reply, with its exact text, the interpretation origin (finite grammar, reviewed interpretation, or unresolved), the source span and its unit, the ground and the category;
- the governing agreement version, source hash, clauses, filing cutoff and original filing time;
- deterministic checks: the governing evaluation, the original filing inside its window, follow-ups preserving the original filing, the maintenance notice, the verified measurement, the denial basis, the explicit acceptance, and that the award does not exceed the claim;
- permitted next actions, category, disposition and ledger;
- a digest.

Categories: MISSING_EVIDENCE, CONTRACTUAL_DENIAL, INCORRECT_FACTUAL_ASSERTION, UNRESOLVED_DENIAL, PARTIAL_AWARD, AWARD_REPORTED, CHANGED_SCOPE, AMBIGUOUS_GROUNDS. A reviewer sees another reviewer's not-yet-applied reading only after saving their own blind entry, the same rule as the bridge.

## Independent criticism

One actual Claude Code Opus 5.5 critique of the implemented commit `3454b33` ran on November 9, 2026.

- Model `claude-opus-5-5`, session `95a8f57d-4a08-4e14-bfd8-9528e9c46e38`.
- Tools exactly `Glob`, `Grep`, `Read`; no MCP servers; 14 read-only tool calls; 100 seconds; exit 0.
- Inputs were public repository source and the same-team authored fixtures only.
- Receipt: [reviews/89-reviewed-denial-acceptance-critique.json](reviews/89-reviewed-denial-acceptance-critique.json), with the prompt, packet and stream hashes. The raw stream is kept outside Git.
- The parent edited `act()` in the working tree during the run. The critique's citations match the committed layout, so its findings refer to `3454b33`.

**Verdict:** adopt with named changes. No dissent on option 3: options 1 and 2 keep outcomes order-dependent, and option 4 lets wording relinquish a valid claim. Opus objected to the implementation, not the option.

| Opus finding | Lead decision | Change (`8083ab5`) and falsifier |
|---|---|---|
| 1. `accept-denial` skips the claim-decision mandate that guards every other money-affecting action | **Accepted, implemented within W4's lane.** `mandates.ClaimDecision.action` (W0-owned) cannot express a closure, and adding one changes authority under pending D06. Acceptance therefore **fails closed**: only the legacy unmandated `bears` reviewer exemption that `check_claim_decision` already grants may accept. Any principal with a mandate or claim decision is refused. Interface request sent to W0 (a `ClaimDecision` closure variant bound to the basis digest, and a `claim-closure` purpose). | `test_mandated_principal_cannot_accept_until_a_closure_decision_type_exists` |
| 2. View and action disagree for non-`bears` tenants | **Accepted.** The offer is computed by the same `closure_permitted` gate that `act` applies, so a hidden action can no longer succeed. | same test |
| 3. Acceptance isn't bound to what the reviewer saw | **Accepted.** The offered action carries `basis_digest`. Acceptance requires that exact digest through `POST /denial-acceptance`; the generic `/actions/accept-denial` route refuses. New evidence that still substantiates the ground changes the digest and is refused. | `test_acceptance_is_bound_to_the_basis_the_reviewer_saw`; mounted-route 409 checks |
| 4. A stale `DENIAL_REVIEW` keeps its stage, and the trace overstates it | **Accepted for the trace, partially for state.** `_denial_basis` now also requires the reviewed terms to match. The trace marks a `DENIAL_REVIEW` without a current basis as `stale_denial_review`, disposition `ESCALATE`, category `UNRESOLVED_DENIAL`, and keeps the remainder. A read never mutates state. Later evidence re-derives the stage on arrival. The filing cutoff is shown on the check, because a rebuttal window keeps running during review. | assertions added to `test_stale_authority_cannot_accept` |
| 5. An accepted denial survives losing its stated ground | **Accepted** for explicit acceptances: reopen when the recorded ground fails, even if the claim stays INELIGIBLE for another reason. The finite-grammar automatic closure keeps its existing rule (D06). | `test_explicit_acceptance_reopens_when_its_own_ground_fails` (mutation-checked: fails without the fix) |
| 6. Another reviewer's later reading can set the trace headline | **Accepted.** Only the requester's own latest review sets the headline. Other reviews remain rows behind the requester's own blind entry. | `test_trace_headline_uses_only_the_requesters_own_reading` |

The residual risk the packet names remains: a reviewer could label a waiver as maintenance while the deterministic maintenance check independently holds. The two-proposition limit, full byte coverage, per-proposition verdicts and `bundle_loses_meaning` narrow it but do not remove it. Human semantic review remains required, and the team should weigh it under D06.

## Validation

Commits:
- `4e50dbc`: frozen authored controls, before any implementation.
- `3454b33`: preferred implementation.
- `8083ab5`: critique fixes.

No pre-existing test was edited, skipped or re-expected. See [TEST-CHANGES-89-disputes.md](../TEST-CHANGES-89-disputes.md).

Focused results:
- **Existing tests only, on `3454b33`:** 849 passed.
- **Final source `8083ab5`:** 904 passed, 1 existing warning, 206.14s. This covers the correspondence, disputes, local-review-exception dispute, cross-claim and mounted v4 route tests, plus the 37 new tests in `tests/test_correspondence_disposition_89.py`.
- **First final attempt:** hung on an unchanged Playwright test under heavy machine load and was stopped; it is retained, not discarded.
- **Mutation check:** removing the ground re-derivation and the digest comparison made the two corresponding falsifiers fail.

Receipt: [evidence/dispute-disposition-89/verification.json](../evidence/dispute-disposition-89/verification.json).

The full `uv run --locked pytest` suite runs once after the integration owner merges.

**Acceptance against the assignment.** The novel authored cases exercise all three outcomes through ordinary intake and the reviewed path:
- **justified cure:** `n89-cure-endpoint` and the counterparty loop;
- **accepted denial:** `n89-denial-maintenance` in both orders, the counterparty loop, and the historical late-filing and threshold variants;
- **escalation:** legal, compound, changed-scope and injected text.

No case changed money or claim scope because of model output: a model candidate cannot act as a review, and a `confidence` field is rejected.

## Cross-workstream items decided in W4's lane

- **W0 interface request (blocked on D06):** add an `accept-denial` variant of `mandates.ClaimDecision` bound to `basis_sha256` and `claim_state_sha256` with `max_amount_cents=0`, plus a `claim-closure` purpose for `/denial-acceptance`. Until then acceptance fails closed for mandated principals.
- **W7 request:** `web/interpretation.js` and the case page should render the `accept-denial` offer by posting its `basis_digest` to its `route`, and should word the `DENIAL_REVIEW` preparation as recording a denial ground, not drafting a response. The API is complete. No W7 file was edited.
- **W5 findings, sent to W0 and gen5:**
  - **F1 (wrong-period record): accepted.** Refuse before storage, record the contradiction, clear any approval, and commit before returning 409, idempotent by `(tenant, account, source, event_id)` plus digest.
  - **F2 (foreign nested rows): accepted with modification.** Out-of-scope deliveries stay out of evidence but in front of a person, and void approval or escalate a pending cure or rebuttal.
  - **F8 (status origin): accepted** as an honest trace label.
  - F1, F2 and F8 land in follow-up branch `work/dispute-intake-scope-89b`, based on `work/integration-90`, because they reuse W5's `temporal_refusal` and `event_in_scope`.
  - **F3 (one status record treated as complete-month coverage): blocked on D07.** The trace already labels the assumption `month_coverage_basis = PROVISIONED_SINGLE_INCIDENT_RECORD`.
  - **F7 (supersede a stored mistaken record): blocked** on a retraction-authority decision (D06/D07). The proposed shape is a source-signed retraction that is kept as history and voids approvals.
  - **Signed channel:** contradictions on that channel stop at the grant's 403 and leave no per-case record. Closing that gap depends on W0's refusal-audit open item, not on forwarding refused bodies into the desk.
- **Evaluation86.** Its two pre-model setup refusals are D03/D04 input-domain rejections. Ronok's overview session relayed on 2026-11-09 that the team decided D03 ("bounded exact source IDs") and D04 ("typed scope variants"). The W4 dispute owner's earlier preference for explicit identity mappings is to be recorded as dissent in the integration owner's decision record. The frozen evaluation source and receipts stay unchanged. Agent1 implements the shared interfaces; evaluation86 is not resumed until those land and a resume is explicitly requested.

## Rollback

Revert the implementation commits. Before rolling back application code that has stored cases, map stored `DENIAL_REVIEW` rows to `HUMAN_REVIEW`. Stored `denial_acceptance` records are inert history and can stay. The frozen fixtures, the trace route (read-only) and the counterparty split carry no state. Reverting them changes no stored row, hash, signature or idempotency key. No Ramp, vendor, model-runtime or authority-file change is involved.

## Not established

These controls are same-team authored, with a scripted reviewer. They are not an independent unseen-dispute result, a human-review accuracy measure, or a real vendor channel (D08). The frozen evaluation86 worktree has not been resumed. Its two setup refusals reject account and contract names containing spaces, and claims lacking component, incident, invoice or region, before any model call. D03/D04 are now decided, but the shared interfaces have not yet landed.
