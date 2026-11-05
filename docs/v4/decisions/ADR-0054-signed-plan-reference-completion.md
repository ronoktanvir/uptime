# ADR 0054 — Plan evidence from the exact signed filing join

## Decision

Accept the invoice and monitor identifiers already consumed by the same aggregate filing join as references for its plan field. Both signed statements must first match the reviewed plan exactly. Preserve valid literal identifiers and the existing strict wire schema. Retain the original filing contents and immutable terms/source pins.

## Alternatives and independent review

Changing the frozen witness to emit a literal plan would leave spaced plan names unrepresentable by the existing identifier schema. Widening every reference field would alter the protocol. A new plan witness type would duplicate already signed metadata. The selected mapping uses the current join's evidence dictionary and adds no source-store lookup.

The actual `claude-opus-5-5` review is session `5d03b1cc-fd8b-4c01-9d97-eafb48ea4f54`, packet SHA-256 `386f9b1a88847870142e754e4c56d87b984811da7a54484ac9618cac992aedd5`. The [packet](packets/54-signed-plan-reference-completion.md) and [review](reviews/54-signed-plan-reference-completion.json) are preserved.

Accept the local-join, exact-equality, conflicting-statement, namespace and mutation-test requirements. An independent coding review confirmed that all seven additive filing packets failed only the plan field before the change. The full diagnosis and public reproduction are retained separately.

The suggested blanket refusal for a literal/source identifier collision is unnecessary when both interpretations establish the same exact plan after successful joining. A positive collision control and a different-plan negative control verify that invariant. The [implementation disposition](../OPUS54-PLAN-REFERENCE-DISPOSITION.md) records the reasoning. The authorized reversible correction preserves separate human review and external-action gates.

## Verification and resulting limitation

The implementation owner passed180 scoped tests. Two isolated mutations each triggered two authority failures when plan equality or both scope-binding layers were removed. Root passed all67 focused plan and fee-reference tests after integration at `877f427`.

The same frozen additive cohort then delivered all seven originals and all seven denials over actual sockets, with8/8 arithmetic results. All146 scheduled observations became measurable. However, only1/7 expected denial dispositions and2/8 complete cases passed. The predicted7/7 disposition result was falsified. Independent diagnosis identifies additional bounded-language coverage limits, which require their own decision and tests. The original cohort remains2/10 complete, with known missing historical evidence preserved. All prior attempts remain recorded.

## Falsifiers and rollback

A reference from another claim, a mismatching plan, altered signed body or missing original field must withhold eligibility and dispatch. Any passing negative control requires disabling affected local submission and reverting the resolver correction. Preserve every original receipt, attempt and evidence hash. Apply further language changes only after independent failure classification.
