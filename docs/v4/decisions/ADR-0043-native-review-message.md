# ADR 0043 — A usable, redacted native bill finding

Status is implemented with external and acceptance limits recorded in STATUS.md.

## Decision and alternatives

Allow fixed evidence-required or source-verified price-review wording. Bind it to exact provider identifiers, current terms and reviewed bytes. Preserve the legacy fixed template for historical outbox records.

Hashes alone left the approver without a reason for review. Fixed text avoids externally controlled prose. Positive price context requires independent signed evidence and deterministic native-line comparison. Synthetic terms cannot drive a native comment.

The original alternatives, costs and falsifiers remain in [the decision packet](packets/43-native-review-message.md).

## Independent review and disagreement

Actual model is `claude-opus-5-5`, session `e690a4c1-f845-4663-a001-58577a327665`. The packet SHA-256 is `90e7810040c3278067b42ebf78594e302831595e4472a5e4dfc44575a640c408`. The full [review receipt](reviews/43-native-review-message.json) retains the reply and model identity.

Accepted Opus's concerns over implied entitlement, revocation and single-use review. Retained server-controlled UUID/digest fields, supported by the verified documented comment message schema. These fields are audit references inside plain text. The missing live grant means only controlled HTTP delivery is demonstrated.

## Verification and rollback

tests/test_ramp_native_reason.py uses actual installed finance-store resolution, revocation at write boundary, modified object, stale review and same-thread read-back

Disable the native binding config. Preserve uncertain outbox records and reconcile using read-only provider operations.
