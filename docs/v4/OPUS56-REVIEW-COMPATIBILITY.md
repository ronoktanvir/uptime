# Response grammar: reviewed compatibility and preregistration

The original 37 public cases were committed alone in `ee244ca`, before any production edit. Their bytes and expectations remain unchanged. The separately preregistered `response-coverage-56-review.json` adds 35 public controls and records one explicit policy override: cross-sentence claim-pronoun inheritance is refused. Root accepted the narrower same-sentence rule from actual Opus56 review session `19ad791c`.

The grammar will deny combinations by default. The permitted combinations are:

| Assertions in the complete reply | Compatibility requirement |
| --- | --- |
| One availability assertion, optional denial frame and existing courtesy/signature frames | At most one explicit period; it must equal server `scope.month`. Vendor percentages never price or establish entitlement. |
| One late-filing assertion, optional denial frame and existing courtesy/signature frames | `it` is allowed only as the subject of a same-sentence `because` clause whose matrix object is explicitly the current claim/request/filing, with no intervening noun phrase. |
| One existing artifact request | Retain its type/reference restrictions and independent evidence gates. |
| One missing-artifact declaration followed by one request | Same artifact type and reference; `that document`/`it` can inherit only an immediately previous unique explicit artifact. No intervening sentence or competing artifact. |
| One existing unconditional service-credit grant, optionally with a restated claim or denied remainder | Preserve already supported partial grants without an explicit remainder; the unawarded balance remains pending in `PARTIAL_AWARD_REVIEW`. |
| One new compound grant-and-remainder form | Stated denied remainder required; grant plus remainder equals the immutable filed claim. An explicit stated claim must also equal it. |
| Any other pair, repeated substantive assertion, conflicting target, or more than one distinct parse | Unknown; no automatic disposition or financial action. |

Availability plus lateness, whole-claim denial plus award, artifact request plus award, and an otherwise supported clause plus a waiver are incompatible. Explicit period handling uses exactly the stored claim month; it infers neither a UTC calendar nor a billing-cycle boundary. No-period forms preserve existing behavior. Rolling, quarterly, relative or underqualified periods refuse. Two explicit qualifiers refuse, even when both match, rather than choosing an attachment.

The accepted partial-award meaning does not concede the remainder. The current desk stores the independently reported award, retains `ledger.disputed_remainder`, and offers no automatic legal waiver, cash payment, credit application or settlement. Review advice requiring rejection of every existing partial award without a stated remainder conflicts with that established behavior and was not adopted. The new conjunction forms are narrower and require the stated conserved remainder.

All USD tokens must have one understood role. Repeated grants, future/conditional grants, other currencies, cash refunds, discounts, tax qualifiers, negative or excess-precision amounts, unknown amount roles and extra substantive text refuse. The existing whole-reply completeness obligation remains; the implementation must remove cue/grammar drift rather than bypass completeness.

Planned verification includes the two immutable public corpora, output-compatible existing controls, mounted correct and mistaken denial paths, independently verified artifact cure and partial-award ledger conservation. Metamorphic controls swap/add periods, duplicate/reorder clauses, substitute artifact type/reference and add unsupported text. Isolated mutations remove completeness, period equality, artifact identity matching, monetary conservation, compatibility enforcement and ambiguity rejection; associated negative tests must fail. Full authority/source/history tests remain separate from parser coverage.

Root has commissioned an independent 100-case synthetic set, with at least 50 must-review cases, before that author reads any diagnosis or implementation. These inputs stay hidden from the implementer and must be sealed before production edits. Public corpus success is remediation evidence, not independence. The current independent socket result and failed prediction remain preserved. No production code changed while this compatibility matrix was prepared.
