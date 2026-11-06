# Decision81: explicit artifact-category guidance and reviewer repair

Status: accepted, bounded implementation.

## Diagnosis and decision

Frozen public76 reply02 requests a request log. The actual model preserved its literal document reference but returned a null artifact type. The block wire enum previously named resource_log, invoice_detail and scope_mapping without defining their meanings. That omission supports a guidance diagnosis; it does not establish that revised instructions will improve model extraction.

Define the three existing categories directly on the block schema field and in the prompt, matching the product's document-type labels. Keep the output shape, enum values and nullable field unchanged. Operational request/access logs belong to the incident/telemetry concept only when the source establishes their role; a support-request history or opaque identifier is not sufficient. Unstated, ambiguous, mixed or negated category evidence cannot justify automatic selection. Hydration never fills a type from an identifier.

A candidate with a missing type gets a visible, ordinary review note after the reviewer records an independent reading. The note leaves the dropdown unchanged and does not declare reference-only matching invalid. A reviewer may explicitly choose a supported type, explain the correction and preserve the complete source and literal reference. Existing reviewed-category metadata narrows the independently verified artifact match; it supplies neither evidence nor financial/action authority.

## Alternatives and actual criticism

Identifier-based category inference was rejected because spelling is not source evidence. Requiring every artifact to have a nonnull type would reject legitimate reference-only requests and encourage guessing. A dedicated category-witness selector could improve local citation precision but would require a schema migration across manual and model review. Whole-block grounding plus mandatory explicit review is retained for this bounded guidance repair; a witness becomes necessary if category metadata acquires authority beyond narrowing evidence matching.

Actual Opus5.5 critic session `a98da485-d845-451b-8175-e241c405f805` used only Glob/Grep/Read with empty MCP inventory. It concurred with the bounded repair, called out that `_same` omits field descriptions, warned that coarse source grounding cannot establish category semantics and recommended unchanged-source/reference review controls. The description therefore belongs directly on `BlockProposition.artifact_type`, with a test asserting that it reaches the serialized schema.

The critic requested a retained v2 runtime replay builder. The lead and root dissent: the preserved offline76 replay reads unchanged saved annotations, not the current provider-result parser. Old source commits and exact request/response artifacts already remain available. Current runtime must refuse stale request bytes; adding legacy acceptance would complicate that boundary. The new representation version records provenance, while the complete request hash, including schema and prompt, actually binds permission.

## Validation and limits

Public81 authored controls were frozen before implementation. New deterministic tests cover schema guidance, unchanged nullable shape, stale request/hash refusal, no automatic type inference, negative/mixed annotations, explicit reviewer correction, source/reference identity and unselected browser state. These tests supply annotations; they do not measure extraction quality or actual-human judgment.

No new model extraction run is needed for this limited result. Actual coding/criticism receipts are recorded separately. The original76 corpus, gold, requests, responses, annotations and baseline remain immutable. Any offline replay remains6/6 family matches and5/6 full expected semantics after78; human correction of the missing type is a separate workflow demonstration, not a replacement score.

Existing finance, independent verification, source freshness, review, approval and submission gates remain unchanged. Rollback restores the old block guidance/version and removes the missing-type note, retaining all receipts and frozen evaluation evidence. Restored requests still require their exact configured approvals.

## Actual implementation

Restricted Claude Code Opus5.5 session `27471efc-7a93-4b52-9c91-033201c4191d` completed in203.27s with exactly Edit/Glob/Grep/Read/Write, empty MCP inventory and no permission denials. It implemented the block-field description, shared prompt guidance, source_blocks_v3 provenance, candidate note and new deterministic/browser tests. Parent recorded documents, updated two expected-version assertions and strengthened the new source/effect controls. The stream/session/model/tool receipt is retained; provider identities are self-reported rather than cryptographic attestation.

The worktree includes78's integer/grouped numeric-issuance correction `8ae80cc`. No81 category correction changes that mapper or any financial/verification engine.
