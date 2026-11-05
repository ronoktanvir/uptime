# ADR 0050 — Legacy delimiter collision containment

## Decision

Retain safe historical keys, refuse ambiguous new resource/region identifiers, and reject an otherwise safe new scope if its canonical key already belongs to a different historical scope. Return readable REVIEW_REQUIRED archived evaluations with an unavailable current amount and preserved recorded amount.

## Alternatives and cost

Changing the key encoding immediately could split existing reservations. A tuple/length-prefixed representation with a verified alias migration is a longer-term option. Bounded refusal protects the existing registry but temporarily withholds amounts for affected scopes. Renaming evidence identifiers would invent provenance. The original [decision packet](packets/50-ambiguous-resource-identifiers.md) retains the contemporaneous context and falsifiers.

## Independent review and disagreement

The authenticated model was `claude-opus-5-5`. Its [immutable review receipt](reviews/50-ambiguous-resource-identifiers.json) records the exact model identity, session, packet hash, prompt hash and full response.

Accept Opus's objection that safe-looking new tuples can collide with older delimiter-bearing tuples. Existing reservation owner/full-scope checks were verified, and early intake now refuses before audit and claim rows are appended. Archived projection remains readable rather than failing the entire request. Source-byte tests confirm evaluator re-review after this change. The installed actual database has no claims/reservations, but this census establishes nothing about external deployments. Mixed pre-v2 writer fencing remains a deployment limitation.

## Verification

Worker352 scoped tests and21 final collision checks passed. Seeded historical resource cell/North versus regional cell plus North, and ordinary aggregate-service versus aggregate sentinel, refuse with unchanged financial and domain rows. Retry/supplement identities remain exact. Root reruns the merged guard, original-source and ordinary-request checks. The final source-stable campaign and remaining limits are recorded in [engineering status](../STATUS.md).

## Rollback

Preserve every historical receipt and reservation. A future migration must resolve complete original scopes into an injective representation, retain verified aliases, and fence old writers. Until reviewed, affected identities require manual reconciliation. No real human promotion or external financial effect is generated.

