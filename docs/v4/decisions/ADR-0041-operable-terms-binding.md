# ADR-0041: Operable terms binding

Recorded: 2026-11-04T16:58:23-08:00 (America/Los_Angeles). Status: **PARTIAL — binding path proposed; workbench unbound**.

## Decision and alternatives

Expose observed native bills as unbound until an independently authorized installation-specific terms/service binding supplies exact source, capture, line and effective-period evidence.

Name/amount assertion fabricates contracts. A Python-only evaluator is honest but operationally inaccessible. Protected binding intake can make it usable, at the cost of key custody, source retention and independent document/mandate verification; truthful UNBOUND display is the safe interim behavior.

## Independent Claude response and root analysis/dissent

The actual post-restart Claude Opus 5.5 receipt is [reviews/41-operable-terms-binding.json](reviews/41-operable-terms-binding.json); its sanitized input is [packets/41-operable-terms-binding.md](packets/41-operable-terms-binding.md). Receipt time: `2026-11-05T00:41:38.800932+00:00`; requested and confirmed model: `claude-opus-5-5`; status: `REVIEWED`; session: `11cd4b75-d20d-4853-84ff-9f7e640ae6ee`. This is an existing live review, not a new invocation or a reconstructed historical opinion.

**Opus:** Opus agrees with strict binding but favors UNBOUND/no money findings while agreements and measured lines are absent. It stresses that finance Ed25519 attestation does not authenticate the underlying agreement, supersession or exclusive rate card.

**Root position and reconciliation:** Accept the immediate UNBOUND recommendation and signing limitation. Dissent only from treating all mechanics as unfalsifiable: synthetic negative tests can test overlap/replay/scope controls, while they cannot establish actual customer agreement authenticity. An authenticated sandbox operator is not human commercial activation. The position originates in the linked root packet; this ADR's code/evidence reconciliation is for root's final review, not a claim that root has signed off the final build.

## Evidence, validation and exact falsifier

At main 1087804, ramp_workspace import/view calls evaluate_snapshot without bindings. ramp_findings accepts typed PriceBinding and refuses unsupported native quantities, but this is not a usable approved intake. price_authority HEAD 29f4d60 contains evaluator integration changes, no observed completed terms-authority intake. Sandbox receipts describe six expense-only bills and zero agreements.

Inspected main source baseline: `1087804986151624f395e9ea1c929c16ede6944d`. File paths below resolve in the integrated main release; some are not present in this older ADR-only worktree. The source pin controls this assessment if main advances.

- [uptime/ramp_workspace.py](../../../uptime/ramp_workspace.py)
- [uptime/ramp_findings.py](../../../uptime/ramp_findings.py)
- [uptime/pricing.py](../../../uptime/pricing.py)
- [docs/v4/RAMP-EVALUATION.md](../../../docs/v4/RAMP-EVALUATION.md)

Worker comparison: `remediate/price_authority` at `29f4d60`, inspected before any later intake work. Root must update this record when an actual committed intake is integrated and validated.

Relevant offline validation command, run from the integrated checkout:

```sh
UV_OFFLINE=1 uv run --locked pytest tests/test_ramp_findings_v4.py tests/test_pricing_binding.py -q
```

This command is a validation requirement, not a claim it ran for the final build. See [index validation](INDEX.md#validation-and-handoff) for the bounded checks actually executed by this ADR owner. No external calls, private credentials, customer files or heldout data were used. Application code and packet/review files were not edited.

**Exact falsifier / evidence needed:** Overlapping live rate cards accepted, a binding replayed against a new capture, cross-tenant digest accepted, unsigned/draft amendment applied, duplicate line mapping accepted or a missing record producing a money case falsifies the design. Closure requires an authenticated retained-byte intake wired into the workbench plus independent source/authority evidence.

## Versioned rollback

Disable binding intake and return affected observations to UNBOUND, preserving original agreement bytes, amendment chain, attestation/public-key provenance and evaluator hash in protected versioned custody. Revoke stale binding authority; never overwrite the old decision or publish a corrective native finding without separate approval. Revert this documentation commit if the record itself is wrong, preserving a corrective history. After any integration merge, root must run `uv run --locked pytest` and update final build evidence. No release-gate completion, cash recovery, customer integration, webhook registration, native write, or human activation follows from this ADR.

## Receipt integrity

- Packet SHA-256: `129eaaeede339b9bb70cd9c0d867b86154999696e12a4c1762032c3f4ac0dce4` (matches the receipt's `packet_sha256`).
- Response JSON SHA-256: `2848e41485f2d8d673a6c83c31be701d7e717c5f45947bbb556bc60c303b49f9`.
- Review-prompt SHA-256 recorded by receipt: `3013b2e1679fd43c039f16784ed72e1b555d66d3b16fb8172045a2d96648d556` (original prompt bytes were not reconstructed or independently rehashed).
- Canonical evidence directory: `/Users/ronoktanvir/Documents/Codex/2026-11-03/important-greenfield-project-initialization-this-is/outputs/Uptime-V4/docs/v4/decisions/{packets,reviews}`.
