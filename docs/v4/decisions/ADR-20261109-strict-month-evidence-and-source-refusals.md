# Strict complete-month evidence and verified-source refusal audit

Status: implemented within the user's November 9 approval; combined compiler/hash integration and independent evaluation remain separate gates.

## Context and alternatives

The existing generic monthly path requires one incident. Whole-service monthly contracts that explicitly permit a complete monthly report could not be represented without inventing an incident. Removing incident requirements for every monthly contract would change the meaning of legacy obligations. Requiring customer telemetry universally would also reject otherwise supported provider-measurement contracts even when they require only an authoritative complete report and independently verified fees.

The selected design is an explicit source-derived `complete_service_month/1` capability. It applies only to a supported cited clause, UTC month, one product/plan, filing window and future-invoice remedy. Its separate join requires status and billing to have distinct authenticated subjects, keys and grants. Optional customer attribution must agree. Missing measurements, exclusions, fees or authority do not become zero or permission. Legacy incident rules remain unchanged. A change of evidence basis in overlapping activated terms is a material conflict without supported precedence; it never creates another monthly economic obligation.

Signed source requests whose valid proof lacks scope authorization previously stopped at 403 without an authenticated metadata record. Logging invalid signatures as authenticated sources would misattribute arbitrary traffic. Attaching a refusal to the foreign claim named by a sender would also cross the authority boundary. The selected design records only verified, current, unspent Ed25519 deliveries in a separate metadata-only journal and still returns 403. Invalid proofs, replay, expired timestamps, closed gates and HMAC fixture traffic are not attributed there. The journal never accepts bodies, proofs or nonces and does not change claim state. Persistence failure remains denied with generic 503.

## Independent model contribution and disagreement

Actual Claude Code subscription workers used Opus 5.5 with restricted file tools and no MCP/network, keys or private evaluation data. The journal and auth workers completed their bounded implementations. The xhigh monthly worker produced the initial core, which parent falsification tests corrected: customer attribution is optional; the shared source-clause validator is authoritative; present-null capability refuses; observation time cannot postdate server receipt; overlapping capability changes cannot be silently chosen.

A bounded high-effort follow-up critique confirmed those corrections. It raised conditional invoice-identity and Decimal concerns while explicitly excluding intake/schema from its read scope. Parent verification shows the signed envelope and enrolled grant already bind exact account/service/month, and the existing bounded decimal-string schema rejects nonfinite, negative and coerced values before arithmetic. Added parent amount tests confirm refusal; a measured zero remains valid evidence of no positive credit. The critique, disagreement and real sessions are preserved in the linked `disputes-monthly-20261109-opus-*` records.

## Validation and limits

The test ledger records all actual intermediate failures and final focused outputs. No existing tests or frozen expected outcomes were weakened. Mandatory ordinary-route controls require the source-derived compiler marker and do not skip when the dependency is absent. The integration owner binds the source semantics and runs the full suite before independent evaluation.

This supports a bounded declarative contract family, not arbitrary legal text or all historical filing evidence. Historical monthly filing receipts remain unsupported by the existing resource-only boundary. Signed assertions establish enrolled source attribution, not the truth of a customer's underlying contract or measurement. No human release, native Ramp write or vendor communication is created by these changes.

## Rollback

Revert the new monthly core and its compiler capability/hash binding together. Preserve stored whole-month claims and evidence; an older build must treat them as unsupported/read-only rather than fabricate incident identifiers or rewrite economic identity. Fresh version-bound review is required before any replacement semantics activates. Never delete historical approval or evidence records to make rollback appear clean.

The auth refusal hook and helper can be reverted together without accepting previously denied requests; the original 403 scope refusal remains. Keep the append-only journal as inert history and do not drop its table or rewrite first-seen timestamps. The temporal guard may remain as a conservative intake restriction for the new report kinds; if removing the kinds completely, coordinate that schema rollback with the monthly path. No financial record migration or external action is part of rollback.
