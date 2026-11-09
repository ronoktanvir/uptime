# ADR 97: automatic rule-family selection (D05)

Status: phase 1 and phase 2 are merged into integration (phase 1 at `296ee1b`; phase 2, the server enforcement and the browser move to `profile: "auto"`, at `9b2097c`, reviewed by gent7), and the operator runbook at `9fa5769`. The independent unseen-vendor proof has **not** been run: gent8 holds a sealed pre-registered selection, and the run waits for Ronok’s go-ahead. November 9, 2026, America/Los_Angeles. Workstream W3. Owner decision: D05 "auto-select plus human approval" (Ronok, 2026-11-09, [team decision sheet](../TEAM-DECISION-HANDOFF.md#team-decision-sheet)).

## What the owner decided

Uptime selects among supported typed rule families from the source itself. Unsupported or ambiguous terms refuse with a concrete review requirement. A person approves before activation. The proof is an independently selected unseen vendor through the ordinary application path, kept separate from the legacy Atlassian proof.

## Design: validation decides

`uptime/vendor_family_selection.py`, behind the existing draft-signed routes with an explicit `profile: "auto"` body:

1. **Offline step.** The deterministic monthly parser compiles the complete source, and the source contains no resource-family language (`RESOURCE_MARKERS`). Then the monthly family is selected with no model call. Stage it with `POST /api/vendors/{id}/candidates`.
2. **Otherwise, one exact-approved proposal job per family.** `monthly-propositions` evaluates the monthly family (strict parser first, then guarded propositions); `resource-month` evaluates the resource family. Both share one attempt identifier. No job is queued until both exact requests are approved.
3. **Outcome, derived on read and never stored:**

| Outcome | When |
|---|---|
| `SELECTED` | Exactly one family validated the complete source, and every other family's grounded reading was refused. |
| `AMBIGUOUS` | More than one family validated this exact source in **any** attempt by **any** reviewer in the tenant. This is monotone: a retry cannot turn it back into a selection. |
| `NO_SUPPORTED_FAMILY` | Every family's grounded reading was refused. Each family's verified public diagnostic is the review requirement. |
| `INCOMPLETE` | A job was cancelled, uncertain or refused without a verified diagnostic, or a family produced no grounded reading (`OUTPUT_NOT_STRUCTURED`, `PROPOSAL_NOT_SOURCE_GROUNDED`). A new attempt identifier evaluates every family again. |
| `PENDING`, `NOT_SUBMITTED`, `APPROVAL_REQUIRED`, `PROVIDER_UNCONFIGURED` | Work not yet done. |

4. Every view reports, per family: state, refusal codes, explanations, exact passages, missing terms, and attempt counts across reviewers. `GET /api/vendors/{id}/requirements` rebuilds the same record for an installed artifact (`family_selection`), so the person approving sees why the losing family lost. An artifact installed from an operator-chosen profile or staged extraction reports `NOT_AUTOMATIC`.
5. A candidate cannot be staged from a job whose source is `AMBIGUOUS` (HTTP 409).
6. Human approval is unchanged: SHADOW, independent tests, interpretation acceptance where required, then approve and activate by a person.

Selection is outside the reviewed-semantics files. `vendor_model_jobs.py` is byte-identical: its SHA-256 is part of every proposal context pin. No evaluator revision changes.

Cost: at most two model calls and two operator approvals per non-canonical source. Canonical monthly sources need none.

## Opus 5.5 critique

One tool-free call, session `f57c7f16-ac61-4dce-8232-51d73184e6f3`. [Packet](../evidence/onboarding-89/opus-packet-d05-family-selection.txt) · [Response](../evidence/onboarding-89/opus-critique-d05-family-selection.json). Opus ranked validation-decided selection first (ahead of sequential, a model classifier, or a text classifier) and did not dissent on direction.

| Opus point | Resolution |
|---|---|
| The offline shortcut rests on an unproven grammar claim | **Accepted.** A deterministic resource-language guard was added, plus pin tests: a canonical source with a symptom clause is refused offline and by the strict parser, and a symptom/cause definition is refused under every monthly label. The guard is outside the semantics hash, so the pin tests carry its protection. |
| A flaky refusal can mask ambiguity; retries can fish for an outcome | **Accepted in part.** The outcome is monotone across attempts and reviewers: any second validated family makes it `AMBIGUOUS`, and a refusal without a grounded reading cannot rule a family out. **Disagreed** on requiring a *structural* code for the losing family; see below. |
| The validators differ in strictness | **Recorded.** Each view says whether the winner came through the strict parser or guarded propositions (propositions also require interpretation acceptance), and whether the loser was ruled out structurally or by a refused reading. |
| Selection could differ by reviewer | **Accepted.** Ambiguity and attempt counts are computed tenant-wide for the exact source context. |
| Phase 1 leaves operator-chosen profiles installable | **Accepted as a sequencing constraint.** Phase 2 (below) must merge before any proof run is called D05 evidence. |
| The approver must see why the loser lost | **Accepted.** See `family_selection` on the requirements view. |

### Disagreement: what rules a losing family out

Opus proposed that only a *structural* refusal (a deterministic finding about the source) may rule out the losing family. Before adopting that, I probed the real validators with the authored monthly prose source. A grounded resource reading of an ordinary monthly SLA is always refused at block level, because its filing clause states no UTC clock ("Filing cutoff must be a source-grounded UTC clock") and its period has no resource denominator. Those block refusals are not structural codes. Under Opus's rule the commonest kind of source could therefore never reach `SELECTED`: it would stay `INCOMPLETE` on every retry.

The two families' vocabularies are also nearly exclusive:
- A source fully covered by monthly clauses has no symptom, cause or evidence clause, which the resource family requires.
- Resource clauses have no monthly field.

The residual overlap is the resource family's aggregate service-month profile, whose fixed UTC period and fixed filing timestamps the monthly period and filing grammar does not accept.

**Resolution:** a losing family is ruled out by any refused *grounded* reading. A family with no grounded reading cannot be ruled out. Ambiguity remains monotone across attempts, and each view reports whether the loser was ruled out structurally or by a refused reading. **Revisit trigger:** any real attempt pair where both families validate, or a reviewer finding that a refused-reading loser should have won.

## Phase 2: retire operator-chosen profiles at candidate install

These ship together, because they break the current profile-select interface and two existing browser tests:
- `proposal-jobs/{job}/candidate` stages only the job automatic selection chose for its source and attempt.
- Operator-profile jobs (`monthly`, or a single profile without the other family) refuse with a concrete requirement.
- W7 replaces the "Extraction profile" select with automatic selection: send `profile: "auto"` and render the selection view.

The existing tests that change will be named in the W3 ledger.

## Not done

- The independently selected unseen vendor through the ordinary application path. This needs phase 2 merged, an independently chosen public source, operator approval of both exact requests, real inference, and a person's promotion and rollback.
- Grammar repairs for the evaluation 84 refusal causes. gent8's per-case diagnosis attributes them to the monthly vendor/agreement label rule, model-flagged clauses, and the aggregate period phrasing. These are reviewed-semantics changes, must be principled rather than fitted to the six examined cases, and would ride the batched semantics revision. The evaluation 84 score stays 0/4.

## Rollback

Revert the phase 1 commit. Explicit-profile requests behave exactly as before; the added `attempts()` read method is unused.
