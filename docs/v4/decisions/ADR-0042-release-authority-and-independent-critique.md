# ADR 0042 — Substantive release evidence and independent review

Status is implemented with external and acceptance limits recorded in STATUS.md.

## Decision and alternatives

Require actual report schemas, failures/counts, source and holdout binding. Maintain separate registered authority for actual native operations. Draft work receives a narrower, safe lane in ADR45.

Opus identified a concrete arbitrary-file PASS defect. Adopted the report validation requirement. Added optional separated signers because native operation already has distinct source and effect issuers. A scripted signature still cannot establish a genuine human review. The prototype has no issued real release or native installation grant.

The original alternatives, costs and falsifiers remain in [the decision packet](packets/42-release-authority-and-independent-critique.md).

## Independent review and disagreement

Actual model is `claude-opus-5-5`, session `3ad587d9-dc08-4fc7-8eab-9af2fbb16edf`. The packet SHA-256 is `086d2d29d76122e94cf6b5e17ec808b886addb9d429eb8d86a3fe997b54991c5`. The full [review receipt](reviews/42-release-authority-and-independent-critique.json) retains the reply and model identity.

The adviser called TOCTOU, rounding and outbox idempotency open bugs without reproductions. Existing final-boundary rereads, exact currency checks and uncertainty reconciliation address those classes. They remain regression targets, and the review alone cannot establish a new exploit.

## Verification and rollback

tests/test_release_gate_v4.py; tests/test_ramp_native_binding.py; independent baseline 73/45 and corrected 118/0 on pinned source

Revert deployment gate registration and keep observation mode while replacing invalid evidence. Existing outbox deliveries remain immutable.
