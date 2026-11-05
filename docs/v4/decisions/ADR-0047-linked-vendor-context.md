# ADR 0047 — Exact native vendor associations

## Decision

Prioritize same-ID vendor detail reads for the bills already captured, within the existing shared detail budget. Retain coverage for both linked references and sampled inventory.

## Alternatives and cost

Inventory-only reads leave some captured bills without a resolvable vendor record. Reading the entire business inventory is unbounded. Prioritized linked reads complete the captured bill context using the existing twelve-detail budget. Vendor names and a persistent private label sidecar were deferred. The original [decision packet](packets/47-linked-vendor-context.md) retains the contemporaneous context and falsifiers.

## Independent review and disagreement

The authenticated model was `claude-opus-5-5`. Its [immutable review receipt](reviews/47-linked-vendor-context.json) records the exact model identity, session, packet hash, prompt hash and full response.

Accept Opus's bounded IDs-and-coverage proposal. The budget comes from explicit configuration, so the limit holds beyond the original six-bill sample. The implementation compares requested and returned native IDs, preserves conflicting list/detail evidence, and never uses merchant names as account or contract authority. Additional blanket permission requests for authorized read-only implementation were unnecessary.

## Verification

105 reader tests passed. The actual November5 UTC refresh matched all five vendors referenced by the six captured bills, plus seven inventory vendors. The vendor inventory remains truncated. Capture2265946dc34c21ecbf84daa536db765f1a237cebf32857c943fdf0a3786756ff is installed in the real local sandbox workspace. The final source-stable campaign and remaining limits are recorded in [engineering status](../STATUS.md).

## Rollback

Disable include_linked_vendors to restore the inventory-only capture strategy. Retain prior immutable captures and their original checksums. No names, contact details or new provider write permissions are required.

